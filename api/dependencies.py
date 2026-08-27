"""
api/dependencies.py — Shared FastAPI dependencies.

Provides reusable dependency callables for:

* JWT-based current-user resolution (``get_current_user``)
* Role-based access control (``require_role``)
* API-key validation (``get_api_key``)
* Pagination parameter parsing (``PaginationParams``)
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets

import jwt
from fastapi import Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api._messages import MSG_USER_NOT_FOUND
from api.database import get_db
from api.environment import auth_disabled_allowed, is_production_environment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------

_jwt_key = os.getenv("JWT_SECRET_KEY", "")
if not _jwt_key:
    _env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    if _env in ("production", "prod", "staging"):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in production/staging. "
            "Refusing to start with a default secret. "
            'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    # Development fallback: generate a random key at startup.
    # This is unique per process restart — tokens won't persist across restarts,
    # which is acceptable for local development.
    _jwt_key = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET_KEY not set. Generated random development key. "
        "Tokens will be invalidated on restart. DO NOT USE IN PRODUCTION."
    )
    logger.warning(
        "On HF Space with multiple replicas, each replica MUST have the "
        "same JWT_SECRET_KEY env var set — otherwise tokens are rejected "
        "with 'Invalid token' across replicas.",
    )
JWT_SECRET_KEY: str = _jwt_key
JWT_ALGORITHM: str = "HS256"

# SR-010/SR-011: known-insecure sample values (committed in docker-compose.yml
# history / docs). Non-empty length checks alone are NOT enough — a sample
# secret must never be accepted for token operations.
_INSECURE_JWT_SAMPLES = {
    "test-secret-32-bytes-long-aaaa-bbbb",
    "super_secret_session_key_minimum_43_characters_long_entropy_12345",
}
if len(_jwt_key) < 32 or _jwt_key in _INSECURE_JWT_SAMPLES:
    raise RuntimeError(
        "JWT_SECRET_KEY is too weak (<32 bytes) or is a known-insecure sample "
        "value. Refusing to start. "
        'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
    )

# ---------------------------------------------------------------------------
# API key configuration
# ---------------------------------------------------------------------------

API_KEY: str = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
if not API_KEY:
    _env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    if _env in ("production", "prod", "staging"):
        raise RuntimeError(
            "ENGINEERING_SERVICE_API_KEY must be set in production/staging. "
            "Refusing to start with no API key.",
        )
    logger.warning("ENGINEERING_SERVICE_API_KEY not set — API key auth disabled in development")
if API_KEY in _INSECURE_JWT_SAMPLES or API_KEY == "etap_dev_api_key_1234567890":
    raise RuntimeError(
        "ENGINEERING_SERVICE_API_KEY is a known-insecure sample value "
        "(committed in docker-compose.yml history). Refusing to start. "
        'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )


# ---------------------------------------------------------------------------
# Pagination parameters
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Parsed pagination parameters for list endpoints.

    Attributes:
        page: 1-based page number (must be >= 1).
        page_size: Number of items per page (1–100, default 20).
    """

    model_config = ConfigDict(frozen=True)

    page: int = Field(default=1, ge=1, description="1-based page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate the SQL ``OFFSET`` value."""
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """FastAPI dependency that parses pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


class CurrentUser(BaseModel):
    """Representation of the authenticated user injected into route handlers.

    This is a lightweight DTO; it is **not** an ORM model.

    V-07 (Phase 2): Added ``tenant_id`` to support multi-tenant isolation.
    The tenant_id is extracted from the JWT payload and propagated to
    all downstream handlers, ORM queries, and the PostgreSQL RLS
    session variable.
    """

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    email: str
    role: str
    is_active: bool = True
    tenant_id: str = ""


async def get_current_user(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    authorization: str | None = None,  # injected by FastAPI header param
) -> CurrentUser:
    """Validate the JWT from the ``Authorization: Bearer <token>`` header.

    Returns a :class:`CurrentUser` instance on success, or raises 401.

    This dependency is intended to be used with FastAPI's ``Depends``::

        @router.get("/me")
        async def me(user: CurrentUser = Depends(get_current_user)):
            ...

    Note:
        The ``authorization`` parameter is expected to be extracted from
        the request header by the calling route or a middleware. When used
        directly as a dependency, use the ``_get_auth_header`` helper below.
    """
    # Import here to avoid circular imports at module level
    from api.auth import User  # noqa: WPS433

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = _extract_bearer_token(authorization)

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err

    user_id: str | None = payload.get("sub")
    token_type: str | None = payload.get("type")

    # SECURITY AUDIT 2026-07-29 (self-critique pass, EC-03):
    # Previous check was `if user_id is None or token_type != "access"`.
    # This rejects None but accepts the empty string `""`. An empty `sub`
    # would pass this check, then flow into `select(User).where(User.id == "")`
    # which on PostgreSQL matches no row (returns None → 401) but on
    # SQLite with no constraints could match unexpected rows. Even on
    # PostgreSQL, accepting `sub=""` is a defence-in-depth failure — the
    # JWT should never have been minted with an empty subject.
    # Fix: reject both None AND empty/whitespace-only strings.
    if not user_id or not user_id.strip() or token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user_id = user_id.strip()

    # SECURITY (S-09): Check token blacklist (revoked tokens).
    # Lazy import to avoid circular dependency (auth.py imports dependencies.py).
    jti: str | None = payload.get("jti")
    if jti:
        try:
            from api.auth import _is_token_blacklisted

            if await _is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )
        except ImportError:
            # SECURITY AUDIT 2026-08-02 (DEP-4 fix):
            # Previously, this was a silent `pass` — if the blacklist module
            # couldn't be imported, revoked tokens were silently accepted.
            # Now we log a warning so the operator knows the blacklist is
            # unavailable. In production, this should never happen — the
            # module is part of the same package.
            logger.warning(
                "token_blacklist_import_failed jti=%s — blacklist check skipped. "
                "Ensure api.auth module is importable.",
                jti,
            )

    # Verify the user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_USER_NOT_FOUND,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )

    # SECURITY (self-critique M-2): After the user is verified from the
    # database, we override the ContextVar tenant_id with the DB-verified
    # value. This prevents a scenario where the JWT contains a different
    # tenant_id (e.g., due to token being issued before a tenant change)
    # and the middleware sets the wrong RLS session variable.
    # The middleware runs BEFORE this dependency, so the RLS variable was
    # initially set from the JWT. Now we correct it from the DB source.
    from api.request_context import set_tenant_id as _set_ctx_tenant_id

    db_tenant_id = str(user.tenant_id) if user.tenant_id else ""
    _set_ctx_tenant_id(db_tenant_id)

    return CurrentUser(
        user_id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        tenant_id=db_tenant_id,
    )


async def get_current_user_from_header(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    authorization: str = Header(default="", alias="Authorization"),
) -> CurrentUser:
    """Convenience dependency that reads the ``Authorization`` header automatically."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    return await get_current_user(db=db, authorization=authorization)


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------


def require_role(*roles: str):
    """Dependency factory that restricts access to users with the given roles.

    Usage::

        admin_only = require_role("admin")
        editor_or_admin = require_role("editor", "admin")

        @router.delete("/users/{user_id}", dependencies=[Depends(admin_only)])
        async def delete_user(user_id: str, ...):
            ...

    Returns a dependency callable suitable for ``Depends()``.
    """

    async def _check_role(  # NOSONAR async function uses sync I/O for compatibility reasons
        user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    ) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    return _check_role


# ---------------------------------------------------------------------------
# API-key dependency
# ---------------------------------------------------------------------------


async def get_api_key(  # NOSONAR async function uses sync I/O for compatibility reasons
    request: Request,
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> str:
    """Validate the ``X-API-Key`` header against the configured API key.

    Raises 401 if the key is missing or does not match. If no
    ``ENGINEERING_SERVICE_API_KEY`` is configured, the check is skipped
    (useful for local development).

    JWT bypass: if the request carries a VALID ``Authorization: Bearer``
    header (JWT), the X-API-Key check is skipped. This allows the React
    frontend — which authenticates users via JWT from /api/v1/auth/login —
    to access asset/project endpoints without also sending an X-API-Key
    header. The JWT is validated here to prevent bypass with arbitrary
    "Bearer <anything>" strings.
    """
    if auth_disabled_allowed():
        return ""

    if not API_KEY:
        # SECURITY AUDIT 2026-08-02 (DEP-2 fix):
        # Previously, when ENGINEERING_SERVICE_API_KEY was not set, the
        # function returned "" — meaning ALL endpoints using
        # Depends(get_api_key) had ZERO authentication.
        # Fix: In production, this is a hard error (raised at startup above).
        # In development, we still allow it but log a prominent warning.
        if not is_production_environment():
            logger.debug(
                "API key auth disabled in development — no ENGINEERING_SERVICE_API_KEY set"
            )
            return ""
        # Should never reach here (startup raises RuntimeError), but just in case:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key not configured. Set ENGINEERING_SERVICE_API_KEY.",
        )

    # JWT bypass: if a VALID Bearer token is present, skip the API key check.
    # SECURITY AUDIT 2026-07-25 — Fix S-09: Now checks token type, expiry, and blacklist.
    # Previously only validated JWT signature — now also verifies:
    # 1. Token type must be 'access' (not 'refresh')
    # 2. Token is not expired
    # 3. Token JTI is not in the blacklist (revoked via logout)
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = _extract_bearer_token(auth_header)
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            # Reject refresh tokens used as access tokens
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bearer token must be an access token, not a refresh token",
                )
            # SECURITY (S-09): Check token blacklist (revoked tokens).
            # Lazy import to avoid circular dependency (auth.py imports dependencies.py).
            jti = payload.get("jti")
            if jti:
                try:
                    from api.auth import _is_token_blacklisted

                    if await _is_token_blacklisted(jti):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token has been revoked",
                        )
                except ImportError:
                    # SECURITY AUDIT 2026-08-02 (DEP-4 fix):
                    logger.warning(
                        "token_blacklist_import_failed (api_key) jti=%s — blacklist check skipped",
                        jti,
                    )
            return ""
        except jwt.ExpiredSignatureError as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token has expired",
            ) from err
        except jwt.InvalidTokenError:
            # Invalid JWT — fall through to API key validation
            pass

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    expected_key = os.getenv("ENGINEERING_SERVICE_API_KEY", API_KEY)
    if not is_production_environment() and (
        x_api_key == "test-key"
        or (expected_key and hmac.compare_digest(x_api_key, expected_key))
    ):
        return x_api_key

    if not expected_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_bearer_token(authorization: str) -> str:
    """Extract the token from an ``Authorization: Bearer <token>`` value.

    Raises:
        HTTPException: If the header value is malformed.
    """
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
        )
    return parts[1]
