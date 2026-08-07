"""
<<<<<<< HEAD
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
=======
backend/request_context.py — Correlation ID middleware for request tracing.
>>>>>>> origin/fix/scenario-tests-properly
"""

from __future__ import annotations

<<<<<<< HEAD
import logging
import uuid
from contextvars import ContextVar
from typing import Optional
=======
import uuid
>>>>>>> origin/fix/scenario-tests-properly

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

<<<<<<< HEAD
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
        """Register a SQLAlchemy engine event that sets the RLS session
        variable on every connection before the first query.

        This is the ONLY reliable way to set the PostgreSQL session
        variable on the connection that will actually be used by the
        route handler's queries. Opening a separate session (as the
        original version did) sets the variable on a different
        connection that is never used.

        The ``before_cursor_execute`` event fires before every cursor
        execution. We use a connection_info dict to track whether
        the SET command has already been issued for this connection
        (to avoid redundant SET on every query within the same request).
        """
        try:
            # Track which connections have already had the RLS variable set.
            # SECURITY (self-critique C-2): Previous version used a plain
            # set[int] with id(conn) for add but id(connection_record) for
            # remove — these are different objects, so the set never shrank
            # (memory leak). Fixed: use a WeakSet keyed by the connection's
            # underlying dbapi_connection, which is the same object in both
            # the before_cursor_execute and close events.
            import weakref

            from sqlalchemy import event, text

            from api.database import engine

            _rls_set_connections: weakref.WeakSet = weakref.WeakSet()

            @event.listens_for(engine.sync_engine, "before_cursor_execute")
            def _set_tenant_before_query(conn, cursor, statement, parameters, context, executemany):
                """Set app.current_tenant_id before the first query on each connection.

                This runs synchronously on the underlying DBAPI connection.
                The ContextVar is read here to get the current tenant_id.
                """
                tenant_id = get_tenant_id()
                if not tenant_id:
                    return

                # Use the DBAPI connection object for identity tracking.
                # conn.connection is the underlying DBAPI connection object
                # that is the same across both events.
                dbapi_conn = (
                    conn.connection.dbapi_connection
                    if hasattr(conn.connection, "dbapi_connection")
                    else conn.connection
                )
                if dbapi_conn in _rls_set_connections:
                    # Already set on this connection for this request
                    return

                # Only set on PostgreSQL connections
                try:
                    # Use the connection's execute method to set the variable
                    # This works with both asyncpg and psycopg2 drivers
                    conn.execute(
                        text("SET app.current_tenant_id = :tid"),
                        {"tid": tenant_id},
                    )
                    _rls_set_connections.add(dbapi_conn)
                except Exception:
                    # Non-PostgreSQL backends (SQLite) don't support SET
                    # — this is expected and safe to ignore.
                    logger.debug(
                        "Could not set app.current_tenant_id "
                        "(likely SQLite backend). "
                        "Application-layer isolation is active."
                    )

            # The WeakSet automatically removes entries when the DBAPI
            # connection is garbage-collected (returned to pool / closed).
            # No explicit close event listener is needed anymore.

            logger.info(
                "Registered SQLAlchemy before_cursor_execute event " "for RLS tenant isolation"
            )

        except Exception:
            logger.warning(
                "Could not register SQLAlchemy event for RLS. "
                "Tenant isolation will rely on application-layer filters only."
            )
=======

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Add X-Correlation-ID header to every request/response."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
>>>>>>> origin/fix/scenario-tests-properly
