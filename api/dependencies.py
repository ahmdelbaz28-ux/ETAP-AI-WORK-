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
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db

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
            "Refusing to start with a default secret."
        )
    import logging as _logging
    import secrets as _secrets

    _jwt_key = _secrets.token_hex(32)
    _logging.getLogger(__name__).warning(
        "JWT_SECRET_KEY not set; using random key. "
        "Tokens will NOT survive restarts. Set JWT_SECRET_KEY in production."
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
            "Refusing to start with no API key."
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

    user_id: Optional[str] = payload.get("sub")
    token_type: Optional[str] = payload.get("type")

    if user_id is None or token_type != "access":
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
            detail="User not found",
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

    async def _check_role(
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


async def get_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> str:
    """Validate the ``X-API-Key`` header against the configured API key.

    Raises 401 if the key is missing or does not match. If no
    ``ENGINEERING_SERVICE_API_KEY`` is configured, the check is skipped
    (useful for local development).
    """
    if not API_KEY:
        # No API key configured — skip validation
        return ""

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
