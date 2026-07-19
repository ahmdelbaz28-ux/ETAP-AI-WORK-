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
from fastapi import Depends, Header, HTTPException, Query, Request, status
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
            "Refusing to start with a default secret.",
        )
    import hashlib as _hashlib
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _hostname = os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", "unknown"))
    _seed = f"etap-dev-{_hostname}"
    _jwt_key = _hashlib.sha256(_seed.encode()).hexdigest()
    _logger.warning(
        "JWT_SECRET_KEY not set; using deterministic fallback (hostname=%s). "
        "Tokens survive restarts on same host but are NOT cryptographically "
        "secure. Set JWT_SECRET_KEY in production.", _hostname,
    )
    _logger.warning(
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


def _get_current_api_key() -> str:
    """Get the current API key from the environment at CALL time (not import time).

    SECURITY FIX: Previously, get_api_key() used the module-level API_KEY
    variable which was read once at import. If the env var changed after
    import (e.g., in tests), the old value was used. Now reads the env
    var at call time, so monkeypatching os.environ in tests works.
    """
    return os.getenv("ENGINEERING_SERVICE_API_KEY", API_KEY)


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
        # SECURITY (HI-NEW-09): require exp + sub claims — a token without
        # an expiry could be used forever if stolen. Without sub, the token
        # has no user identity.
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
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

    JWT bypass: if the request carries a valid ``Authorization: Bearer``
    header (JWT), the X-API-Key check is skipped. This allows the React
    frontend — which authenticates users via JWT from /api/v1/auth/login —
    to access asset/project endpoints without also sending an X-API-Key
    header. Without this bypass, every authenticated UI request to
    /assets, /projects returns 401.
    """
    # SECURITY: Check AUTH_DISABLED at CALL TIME (not import time).
    # Previously, api/routes.py read _AUTH_DISABLED at module load and
    # get_api_key() used that static value. Tests that monkeypatch the
    # env var couldn't override the behavior.
    _auth_disabled = os.getenv("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in (
        "true", "1", "yes",
    )
    _current_key = _get_current_api_key()
    if _auth_disabled or not _current_key:
        # Auth disabled or no API key configured — skip validation
        return ""

    # SECURITY (CR-NEW-09): The previous implementation accepted ANY
    # 'Bearer ...' header and returned "" (success) without validating
    # the JWT. This meant endpoints depending ONLY on get_api_key()
    # (without a separate CurrentUser dependency) could be accessed
    # with any string after 'Bearer ' — a complete auth bypass.
    #
    # Now: if a Bearer token is present, we REQUIRE it to be a valid JWT.
    # If JWT validation fails, we raise 401. If it succeeds, we return
    # "" (the JWT path is handled by the downstream CurrentUser dep).
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty Bearer token",
            )
        # Validate the JWT — raises HTTPException(401) on invalid/expired
        try:
            jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {exc}",
            ) from exc
        return ""  # JWT is valid — downstream CurrentUser will load the user

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if not hmac.compare_digest(x_api_key, _get_current_api_key()):
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


# ---------------------------------------------------------------------------
# Ownership authorization helpers (CR-NEW-07, CR-NEW-08)
# ---------------------------------------------------------------------------


def check_resource_ownership(
    resource_owner_id: str | None,
    current_user: CurrentUser,
    resource_name: str = "Resource",
) -> None:
    """Raise 403 if *current_user* does not own the resource and is not admin.

    SECURITY (CR-NEW-07,08): Centralized ownership check to prevent
    unauthorized access to other users' projects, assets, templates, etc.
    Any authenticated user could previously read/modify/delete ANY
    resource by ID — a horizontal privilege escalation.

    Usage::

        check_resource_ownership(project.created_by, current_user, "Project")

    Admins bypass the ownership check (they can access any resource for
    support/audit purposes).
    """
    if resource_owner_id is None:
        # Resource has no owner (legacy data) — deny access to be safe
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{resource_name} has no owner — access denied.",
        )
    if str(resource_owner_id) != str(current_user.user_id) and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to access this {resource_name.lower()}.",
        )
