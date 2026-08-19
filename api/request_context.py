"""
api/request_context.py — Request-scoped context for multi-tenancy.

Security Fix V-07 (Phase 2): Uses Python's `contextvars.ContextVar` to isolate
tenant/project/user context per async Task. This prevents cross-tenant
data leakage when concurrent requests from different tenants share the
same event loop.
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
    """Extract tenant_id from the JWT ``Authorization: Bearer`` token."""
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
    """Add X-Correlation-ID header and set ContextVar for request tracing."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        _correlation_id_var.set(correlation_id)

        tenant_id = _extract_tenant_id_from_jwt(request)
        request.state.tenant_id = tenant_id
        _tenant_id_var.set(tenant_id)

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
# SQLAlchemy RLS event handlers
# ---------------------------------------------------------------------------


def _set_tenant_before_query(conn, cursor, statement, parameters, context, executemany) -> None:
    """Set ``app.current_tenant_id`` before EVERY query on PostgreSQL."""
    tenant_id = get_tenant_id()
    if not tenant_id:
        return
    if conn.dialect.name != "postgresql":
        return
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
        logger.debug(
            "Could not set app.current_tenant_id "
            "(likely SQLite backend). "
            "Application-layer isolation is active."
        )


def _reset_tenant_on_checkin(dbapi_connection, _connection_record) -> None:
    """Clear the RLS session variable when a connection returns to the pool."""
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
    """Set the PostgreSQL session variable for Row-Level Security (RLS)."""

    _event_registered: bool = False

    async def dispatch(self, request: Request, call_next):
        if not TenantMiddleware._event_registered:
            self._register_connection_event()
            TenantMiddleware._event_registered = True

        response = await call_next(request)

        _tenant_id_var.set("")
        _correlation_id_var.set("")
        _project_id_var.set("")

        return response

    @staticmethod
    def _register_connection_event() -> None:
        """Register SQLAlchemy engine events for RLS tenant isolation."""
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
