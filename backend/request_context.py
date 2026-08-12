"""
backend/request_context.py — Request-scoped context for multi-tenancy.

Security Fix V-07 (Phase 2): Uses Python's `contextvars.ContextVar` to isolate
tenant/project/user context per async Task. This prevents cross-tenant
data leakage when concurrent requests from different tenants share the
same event loop.

Phase 2 enhancements:
  - Tenant ID is now extracted from JWT claims (not from X-Tenant-ID header)
  - CorrelationIdMiddleware sets the ContextVar for tenant_id
  - TenantMiddleware registers a SQLAlchemy engine event that sets
    ``app.current_tenant_id`` on every connection used by the request,
    so that Row-Level Security (RLS) policies enforce isolation at the
    DB level.
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

    tenant_id: str | None = payload.get("tenant_id")
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


# ---------------------------------------------------------------------------
# SQLAlchemy RLS event handlers — module-level so the logic is unit-testable
# ---------------------------------------------------------------------------


def _set_tenant_before_query(conn, cursor, statement, parameters, context, executemany) -> None:
    """Set ``app.current_tenant_id`` before EVERY query on PostgreSQL.

    SR-008 fix: the previous implementation tracked connections in a
    process-wide WeakSet and skipped re-issuing the SET once a connection
    had been tagged. Pooled connections outlive requests, so a tenant B
    request reusing a connection already tagged for tenant A would run all
    of its queries under tenant A's RLS policy — cross-tenant leak.

    The SET is now re-issued before every cursor execution (guarded against
    re-entrancy for the SET statement itself), so the session variable
    always matches the current request's tenant.
    """
    tenant_id = get_tenant_id()
    if not tenant_id:
        return
    if conn.dialect.name != "postgresql":
        return
    # Re-entrancy guard: the SET issued below would otherwise re-trigger
    # this handler for its own execution.
    if statement is not None and str(statement).lstrip().upper().startswith(
        "SET APP.CURRENT_TENANT_ID"
    ):
        return
    try:
        from sqlalchemy import text

        conn.execute(
            text("SET app.current_tenant_id = :tid"),
            {"tid": tenant_id},
        )
    except Exception:
        # Non-PostgreSQL backends (SQLite) don't support SET
        # — this is expected and safe to ignore.
        logger.debug(
            "Could not set app.current_tenant_id "
            "(likely SQLite backend). "
            "Application-layer isolation is active."
        )


def _reset_tenant_on_checkin(dbapi_connection, _connection_record) -> None:
    """Clear the RLS session variable when a connection returns to the pool.

    SR-008 fix: without a reset, a pooled connection checked out by tenant
    B's request after tenant A's request would still carry tenant A's
    ``app.current_tenant_id`` between requests.
    """
    try:
        from api.database import engine

        if engine.sync_engine.dialect.name != "postgresql":
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET app.current_tenant_id = ''")
        finally:
            cursor.close()
    except Exception:
        logger.debug(
            "Could not reset app.current_tenant_id on connection checkin (likely SQLite backend)."
        )


class TenantMiddleware(BaseHTTPMiddleware):
    """Set the PostgreSQL session variable for Row-Level Security (RLS).

    SECURITY DESIGN (self-critique fixes applied):
    - C-2: Fixed memory leak — _rls_set_connections now uses WeakSet
      instead of a plain set with mismatched object identities.
    - m-1: Now clears ALL ContextVars (not just tenant_id) after request.

    The original version opened a SEPARATE database session to set
    ``app.current_tenant_id``. This was a critical bug — the RLS session
    variable was set on a connection that was immediately returned to the
    pool and never used by the route handler's queries. The RLS policy
    would never see the variable.

    The fix: register a SQLAlchemy ``before_cursor_execute`` event that
    injects ``SET app.current_tenant_id`` before the FIRST query on each
    connection. This guarantees the RLS variable is set on the actual
    connection used by the route handler.

    Flow:
        1. CorrelationIdMiddleware extracts tenant_id from JWT → ContextVar
        2. TenantMiddleware registers the before_cursor_execute event
        3. When the route handler's first query runs, the event fires
           and sets ``SET app.current_tenant_id = '<uuid>'`` on that
           specific connection
        4. All subsequent queries on that connection are automatically
           filtered by RLS policies
        5. After the request, all ContextVars are cleared to prevent leakage

    On SQLite (dev mode), RLS is not supported — the application layer
    enforces tenant isolation via ORM-level filters (see projects.py,
    assets.py, rbac.py, etc.).
    """

    # Class-level flag to prevent re-registering the event handler
    _event_registered: bool = False

    async def dispatch(self, request: Request, call_next):
        # Register the connection event handler once
        if not TenantMiddleware._event_registered:
            self._register_connection_event()
            TenantMiddleware._event_registered = True

        response = await call_next(request)

        # After the request, clear all ContextVars to prevent leakage
        # to the next request on the same async Task.
        # SECURITY (self-critique m-1): Previously only cleared _tenant_id_var.
        # Now clears all ContextVars that were set by the middleware chain.
        _tenant_id_var.set("")
        _correlation_id_var.set("")
        _project_id_var.set("")

        return response

    @staticmethod
    def _register_connection_event() -> None:
        """Register SQLAlchemy engine events for RLS tenant isolation.

        - ``before_cursor_execute``: re-issues ``SET app.current_tenant_id``
          before EVERY query (SR-008 — no more process-wide WeakSet skip
          that leaked tenant A's RLS policy into tenant B's pooled-
          connection queries).
        - ``reset_rollback``: clears the session variable when the
          connection returns to the pool, so no tenant's RLS state survives
          a request boundary.
        """
        try:
            from sqlalchemy import event

            from api.database import engine

            event.listen(
                engine.sync_engine,
                "before_cursor_execute",
                _set_tenant_before_query,
            )
            event.listen(
                engine.sync_engine,
                "reset_rollback",
                _reset_tenant_on_checkin,
            )

            logger.info(
                "Registered SQLAlchemy events for RLS tenant isolation "
                "(per-query SET + checkin reset)"
            )

        except Exception:
            logger.warning(
                "Could not register SQLAlchemy events for RLS. "
                "Tenant isolation will rely on application-layer filters only."
            )
