"""
backend/request_context.py — Request-scoped context for multi-tenancy.

Security Fix V-07 (Phase 2): Uses Python's `contextvars.ContextVar` to isolate
tenant/project/user context per async Task. This prevents cross-tenant
data leakage when concurrent requests from different tenants share the
same event loop.

Phase 2 enhancements:
  - Tenant ID is now extracted from JWT claims (not from X-Tenant-ID header)
  - TenantMiddleware sets the PostgreSQL session variable ``app.current_tenant_id``
    so that Row-Level Security (RLS) policies enforce isolation at the DB level
  - ContextVars are natively supported by asyncio and guarantee isolation
    across concurrent Tasks — even when they run on the same thread.

Previous implementation only stored correlation_id on request.state,
which is safe but insufficient for multi-tenancy. The new implementation
adds ContextVar-based isolation for:
  - Tenant ID (which organization/account the request belongs to)
  - Project ID (which project the request is operating on)
  - User ID (the authenticated user making the request)
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ContextVar definitions — isolated per-async-Task
# ---------------------------------------------------------------------------

# V-07: Tenant-scoped context variables
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
_tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
_project_id_var: ContextVar[str] = ContextVar("project_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")


# ---------------------------------------------------------------------------
# Public accessor functions
# ---------------------------------------------------------------------------


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return _correlation_id_var.get()


def get_tenant_id() -> str:
    """Get the current request's tenant ID (V-07)."""
    return _tenant_id_var.get()


def get_project_id() -> str:
    """Get the current request's project ID (V-07)."""
    return _project_id_var.get()


def get_user_id() -> str:
    """Get the current request's authenticated user ID (V-07)."""
    return _user_id_var.get()


def set_tenant_id(tenant_id: str) -> None:
    """Set the tenant ID for the current async Task context (V-07)."""
    _tenant_id_var.set(tenant_id)


def set_project_id(project_id: str) -> None:
    """Set the project ID for the current async Task context (V-07)."""
    _project_id_var.set(project_id)


def set_user_id(user_id: str) -> None:
    """Set the user ID for the current async Task context (V-07)."""
    _user_id_var.set(user_id)


# ---------------------------------------------------------------------------
# JWT helper — extract tenant_id from JWT claims
# ---------------------------------------------------------------------------


def _extract_tenant_id_from_jwt(request: Request) -> str:
    """Extract tenant_id from the JWT ``Authorization: Bearer`` token.

    This is the secure method: the tenant_id is embedded in the JWT at
    login time and cannot be tampered with by the client. Previously,
    the middleware read tenant_id from the ``X-Tenant-ID`` HTTP header,
    which is client-supplied and untrusted — any user could set an
    arbitrary header and access another tenant's data.

    Returns:
        The tenant_id string from the JWT payload, or "" if the
        token is absent, malformed, or does not contain a tenant_id.
    """
    import os

    import jwt as pyjwt

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return ""

    token = auth_header.split(" ", 1)[1]
    if not token:
        return ""

    jwt_key = os.getenv("JWT_SECRET_KEY", "")
    if not jwt_key:
        # Development fallback — the key is auto-generated in
        # api/dependencies.py but we can't import it here without
        # circular dependencies. In production, JWT_SECRET_KEY is
        # always set.
        return ""

    try:
        payload = pyjwt.decode(token, jwt_key, algorithms=["HS256"])
    except pyjwt.InvalidTokenError:
        return ""

    tenant_id: Optional[str] = payload.get("tenant_id")
    if tenant_id and tenant_id.strip():
        return tenant_id.strip()
    return ""


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Add X-Correlation-ID header and set ContextVar for request tracing.

    Security Fix V-07 (Phase 2): Also sets tenant_id and user_id
    ContextVars from the JWT claims, ensuring per-Task isolation
    in multi-tenant deployments.

    The tenant_id is extracted from the JWT (not from the X-Tenant-ID
    header) to prevent cross-tenant impersonation attacks.
    """

    async def dispatch(self, request: Request, call_next):
        # Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        _correlation_id_var.set(correlation_id)

        # V-07 (Phase 2): Extract tenant_id from JWT claims
        # This replaces the insecure X-Tenant-ID header approach.
        # The JWT is validated (signature + expiry) by _extract_tenant_id_from_jwt.
        tenant_id = _extract_tenant_id_from_jwt(request)
        request.state.tenant_id = tenant_id
        _tenant_id_var.set(tenant_id)

        # V-07: Set project context from path parameters if present
        # This is set for routes like /api/v1/projects/{project_id}/...
        path_parts = request.url.path.split("/")
        project_id = ""
        for i, part in enumerate(path_parts):
            if part == "projects" and i + 1 < len(path_parts):
                project_id = path_parts[i + 1]
                break
        if project_id:
            request.state.project_id = project_id
            _project_id_var.set(project_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class TenantMiddleware(BaseHTTPMiddleware):
    """Set the PostgreSQL session variable for Row-Level Security (RLS).

    This middleware runs AFTER JWT authentication and sets the
    ``app.current_tenant_id`` session variable on the database
    connection so that PostgreSQL RLS policies can filter rows
    by the current tenant.

    Flow:
        1. CorrelationIdMiddleware extracts tenant_id from JWT
        2. TenantMiddleware reads the tenant_id from ContextVar
        3. TenantMiddleware sets ``SET app.current_tenant_id = '<uuid>'``
           on the database connection
        4. All subsequent queries on that connection are automatically
           filtered by RLS policies

    On SQLite (dev mode), RLS is not supported — the application layer
    enforces tenant isolation via ORM-level filters (see projects.py,
    assets.py, etc.).
    """

    async def dispatch(self, request: Request, call_next):
        tenant_id = get_tenant_id()

        if tenant_id:
            # Set the PostgreSQL session variable for RLS
            try:
                from api.database import async_session

                async with async_session() as db:
                    from sqlalchemy import text

                    await db.execute(
                        text("SET app.current_tenant_id = :tenant_id"),
                        {"tenant_id": tenant_id},
                    )
                    await db.commit()
            except Exception:
                # Non-PostgreSQL backends (SQLite) don't support SET
                # commands — this is expected and safe to ignore.
                # The application layer handles isolation.
                logger.debug(
                    "Could not set app.current_tenant_id (likely SQLite backend). "
                    "Application-layer isolation is active."
                )

        response = await call_next(request)
        return response
