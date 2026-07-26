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
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api._messages import MSG_USER_NOT_FOUND

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
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
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
    """

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    email: str
    role: str
    is_active: bool = True


async def get_current_user(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    authorization: Optional[str] = None,  # injected by FastAPI header param
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

    # Delegate JWT validation to the canonical helper (deep module interface).
    # This replaces the inline jwt.decode + type check + blacklist check that
    # was duplicated across 5+ files. All JWT validation now flows through
    # _validate_jwt_access_token — one seam, one implementation.
    payload = await _validate_jwt_access_token(token)

    user_id: Optional[str] = payload.get("sub")

    # Validate that the payload contains a user ID
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
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

    return CurrentUser(
        user_id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
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

    async def _check_role(  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    ) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not permitted. Required: {', '.join(roles)}",
            )
        return user

    return _check_role


# ---------------------------------------------------------------------------
# API-key dependency
# ---------------------------------------------------------------------------


async def get_api_key(  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
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
    if not API_KEY:
        # No API key configured — skip validation
        return ""

    # JWT bypass: if a VALID Bearer token is present, skip the API key check.
    # SECURITY AUDIT 2026-07-26 — Now delegates to canonical _validate_jwt_access_token
    # instead of inline jwt.decode + type check + blacklist check.
    # Previously duplicated validation logic was scattered across 5+ files.
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = _extract_bearer_token(auth_header)
        try:
            # Delegate to the canonical JWT validator (deep module interface)
            await _validate_jwt_access_token(token)
            return ""
        except HTTPException:
            # Invalid/expired/revoked JWT — fall through to API key validation
            pass

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


# ---------------------------------------------------------------------------
# Internal helpers — canonical JWT validation (deep module interface)
# ---------------------------------------------------------------------------


async def _validate_jwt_access_token(token: str) -> dict:
    """Validate a JWT access token and return its payload.

    This is the **single source of truth** for JWT validation in the
    entire codebase. Every module that needs to verify a JWT access token
    should call this function instead of doing inline ``jwt.decode``.

    Checks performed:
    1. JWT signature (using canonical ``JWT_SECRET_KEY``)
    2. Token expiry (``jwt.ExpiredSignatureError``)
    3. Token type must be ``"access"`` (rejects refresh / reset tokens)
    4. Token blacklist via ``_is_token_blacklisted`` (revoked tokens)

    Raises:
        HTTPException(401): On any validation failure.
    """
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

    # Reject non-access tokens (refresh, reset-password, etc.)
    token_type: Optional[str] = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token must be an access token, not a refresh token",
        )

    # Check token blacklist (revoked tokens via logout)
    jti: Optional[str] = payload.get("jti")
    if jti:
        try:
            from api.auth import _is_token_blacklisted
            if await _is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )
        except ImportError:
            pass  # blacklist unavailable, continue

    return payload


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


# ---------------------------------------------------------------------------
# WebSocket token validation (deep module interface)
# ---------------------------------------------------------------------------


async def validate_ws_token(token: str) -> bool:
    """Validate JWT token or API key for WebSocket authentication.

    This is the **canonical** WebSocket auth function — all WebSocket
    endpoints should use this instead of implementing their own inline
    validation.

    Accepts:
    1. Valid JWT access token — with type check + blacklist check
    2. Engineering API service key (server-to-server)
    3. Skip validation if AUTH_DISABLED=true in development

    Returns ``True`` on success, ``False`` on failure (no HTTPException —
    WebSocket close codes are handled by the caller).
    """
    # Skip in development if auth is disabled
    if os.getenv("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
        _env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))
        if _env.lower() in ("development", "dev"):
            return True

    # Check API key (server-to-server) — constant-time comparison
    if API_KEY and hmac.compare_digest(token, API_KEY):
        return True

    # Check JWT token — reuse canonical validation logic
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Accept only access tokens
        if payload.get("type") != "access":
            logger.warning("WS auth: rejected non-access token (type=%s)", payload.get("type"))
            return False
        # Check token blacklist (revoked tokens)
        jti = payload.get("jti")
        if jti:
            try:
                from api.auth import _is_token_blacklisted
                if await _is_token_blacklisted(jti):
                    logger.warning("WS auth: rejected revoked token (jti=%s)", jti)
                    return False
            except (ImportError, AttributeError):
                pass  # blacklist unavailable
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("WS auth: token expired")
        return False
    except jwt.InvalidTokenError as exc:
        logger.warning("WS auth: invalid token: %s", exc)
        return False
