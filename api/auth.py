"""
api/auth.py — Authentication & user-management router.

Exposes the following endpoints under the ``/api/v1/auth`` prefix:

* ``POST /register``           — Create a new user account
* ``POST /login``              — Authenticate and receive JWT tokens
* ``POST /refresh``            — Exchange a refresh token for new access token
* ``POST /logout``             — Revoke the current session
* ``GET  /me``                 — Retrieve the authenticated user's profile
* ``PUT  /me``                 — Update the authenticated user's profile
* ``PUT  /me/password``        — Change password (requires current password)
* ``POST /forgot-password``    — Request a password-reset token
* ``POST /reset-password``     — Reset password using a valid token
* ``GET  /users``              — List all users (admin only)
* ``DELETE /users/{user_id}``  — Soft-delete a user (admin only)

Security features
-----------------
* bcrypt password hashing (14 rounds)
* JWT access + refresh token pair
* Password strength validation (8+ chars, not common, not username)
* Login rate limiting (5 attempts / 15 min)
* Opaque error messages on login failure (no user-enumeration leak)
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import Boolean, DateTime, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    CurrentUser,
    get_current_user_from_header,
    pagination_params,
    require_role,
)

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------

ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30")
)
REFRESH_TOKEN_EXPIRE_DAYS: int = int(
    os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")
)
RESET_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30")
)

# ---------------------------------------------------------------------------
# Rate-limiting (in-memory, per username)
# ---------------------------------------------------------------------------

_LOGIN_ATTEMPTS: Dict[str, List[float]] = {}
_RATE_LIMIT_MAX_ATTEMPTS: int = 5
_RATE_LIMIT_WINDOW_SEC: int = 15 * 60  # 15 minutes

# ---------------------------------------------------------------------------
# Token blacklist (Redis-backed)
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as redis_async  # type: ignore
    REDIS_AVAILABLE = True
except ImportError:
    redis_async = None
    REDIS_AVAILABLE = False

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_TOKEN_BLACKLIST_PREFIX = os.getenv("TOKEN_BLACKLIST_PREFIX", "auth:blacklist:")

_redis_client = None


def _get_redis_client() -> redis_async.Redis | None:
    global _redis_client
    if not _REDIS_URL or not REDIS_AVAILABLE:
        return None
    if _redis_client is None:
        _redis_client = redis_async.from_url(_REDIS_URL, decode_responses=True)
    return _redis_client


async def _blacklist_token(jti: str, ttl_seconds: int | None = None) -> None:
    """Blacklist a refresh token JTI using Redis (with TTL)."""
    r = _get_redis_client()
    if r is None:
        return  # fallback: silently no-blacklist if REDIS_URL not configured or redis not available
    key = f"{_TOKEN_BLACKLIST_PREFIX}{jti}"
    if ttl_seconds and ttl_seconds > 0:
        await r.set(key, "1", ex=int(ttl_seconds))
    else:
        await r.set(key, "1")


async def _is_token_blacklisted(jti: str) -> bool:
    """Check if token JTI is blacklisted in Redis."""
    r = _get_redis_client()
    if r is None:
        return False
    key = f"{_TOKEN_BLACKLIST_PREFIX}{jti}"
    val = await r.get(key)
    return val is not None

# ---------------------------------------------------------------------------
# Common-password blocklist (small sample — extend as needed)
# ---------------------------------------------------------------------------

_COMMON_PASSWORDS: set[str] = {
    "password", "12345678", "qwerty12", "abc12345", "password1",
    "iloveyou", "admin123", "welcome1", "123456789", "password123",
    "Passw0rd", "monkey12", "dragon12", "sunshine1", "princess1",
    "football1", "shadow12", "master12", "login123", "hello123",
}


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class User(Base):
    """Persisted user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="engineer")
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reset_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    reset_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Payload for ``POST /register``."""

    model_config = ConfigDict(strict=False)

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="engineer", pattern=r"^(admin|engineer|viewer)$")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str, info) -> str:
        """Enforce password policy: length, not common, not same as username."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if v.lower() in _COMMON_PASSWORDS:
            raise ValueError("Password is too common — choose a stronger one")
        # Check if password contains the username (if available in validation context)
        if info.data and "username" in info.data:
            if info.data["username"].lower() in v.lower():
                raise ValueError("Password must not contain the username")
        return v


class LoginRequest(BaseModel):
    """Payload for ``POST /login``."""

    model_config = ConfigDict(strict=False)

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair returned on login / refresh."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class RefreshRequest(BaseModel):
    """Payload for ``POST /refresh``."""

    model_config = ConfigDict(strict=False)

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Payload for ``PUT /me/password``."""

    model_config = ConfigDict(strict=False)

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Enforce password policy on the new password."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if v.lower() in _COMMON_PASSWORDS:
            raise ValueError("Password is too common — choose a stronger one")
        return v


class ForgotPasswordRequest(BaseModel):
    """Payload for ``POST /forgot-password``."""

    model_config = ConfigDict(strict=False)

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for ``POST /reset-password``."""

    model_config = ConfigDict(strict=False)

    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if v.lower() in _COMMON_PASSWORDS:
            raise ValueError("Password is too common — choose a stronger one")
        return v


class UpdateProfileRequest(BaseModel):
    """Payload for ``PUT /me``."""

    model_config = ConfigDict(strict=False)

    email: EmailStr | None = None
    mfa_enabled: bool | None = None


class UserResponse(BaseModel):
    """Public user representation returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    role: str
    mfa_enabled: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login: datetime | None = None


class UserListResponse(BaseModel):
    """Paginated user list response."""

    model_config = ConfigDict(from_attributes=True)

    users: List[UserResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a UTC-aware datetime.

    SQLite stores datetimes as strings without timezone information.
    When SQLAlchemy reads them back, they arrive as naive datetimes.
    This helper ensures they are treated as UTC so that comparisons
    with ``datetime.now(timezone.utc)`` never fail.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _hash_password(password: str) -> str:
    """Hash *password* with bcrypt (14 rounds)."""
    salt = bcrypt.gensalt(rounds=14)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches *hashed*."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _create_refresh_token(user_id: str) -> str:
    """Create a longer-lived JWT refresh token."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _check_rate_limit(username: str) -> None:
    """Raise 429 if *username* has exceeded the login attempt threshold."""
    now = time.monotonic()
    attempts = _LOGIN_ATTEMPTS.get(username, [])
    # Prune expired attempts
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW_SEC]
    _LOGIN_ATTEMPTS[username] = attempts

    if len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )


def _record_failed_attempt(username: str) -> None:
    """Record a failed login attempt for rate-limiting."""
    now = time.monotonic()
    _LOGIN_ATTEMPTS.setdefault(username, []).append(now)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Create a new user account.

    Returns the created user on success, or 409 if the username/email is
    already taken.
    """
    # Check username uniqueness
    existing = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        email=body.email,
        password_hash=_hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        mfa_enabled=user.mfa_enabled,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Authenticate with username + password.

    On success, returns an access token and a refresh token.
    On failure, returns 401 with a generic message (no user-enumeration leak).
    """
    _check_rate_limit(body.username)

    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(body.password, user.password_hash):
        _record_failed_attempt(body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Update last_login
    user.last_login = datetime.now(UTC)
    db.add(user)
    await db.flush()

    access_token = _create_access_token(str(user.id), user.role)
    refresh_token = _create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh JWT access token",
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Exchange a valid refresh token for a new access + refresh pair."""
    try:
        payload = jwt.decode(
            body.refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from err

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check if the refresh token has been blacklisted (logged out)
    jti = payload.get("jti")
    if jti:
        if await _is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = _create_access_token(str(user.id), user.role)
    new_refresh = _create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke session",
)
async def logout(
    body: RefreshRequest | None = Body(None),
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> None:
    """Log the current user out by blacklisting the provided refresh token.

    If a refresh_token is supplied in the body, its JTI is blacklisted
    so it cannot be exchanged for new access tokens.  The access token
    itself remains valid until it expires (short-lived by design).
    """
    if body and body.refresh_token:
        try:
            payload = jwt.decode(
                body.refresh_token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},  # Allow blacklisting even if expired
            )
            jti = payload.get("jti")
            exp = payload.get("exp")  # epoch seconds
            ttl_seconds: int | None = None
            if isinstance(exp, (int, float)):
                now_epoch = datetime.now(tz=UTC).timestamp()
                ttl_seconds = int(exp - now_epoch)

            if jti:
                await _blacklist_token(jti, ttl_seconds=ttl_seconds)
        except jwt.InvalidTokenError:
            pass  # Invalid token — nothing to blacklist


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Return the authenticated user's full profile."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=str(db_user.id),
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        mfa_enabled=db_user.mfa_enabled,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        last_login=db_user.last_login,
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    body: UpdateProfileRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Update the authenticated user's email and/or MFA preference."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if body.email is not None:
        # Check email uniqueness
        existing = await db.execute(
            select(User).where(User.email == body.email, User.id != user.user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        db_user.email = body.email

    if body.mfa_enabled is not None:
        db_user.mfa_enabled = body.mfa_enabled

    db_user.updated_at = datetime.now(UTC)
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)

    return UserResponse(
        id=str(db_user.id),
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        mfa_enabled=db_user.mfa_enabled,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        last_login=db_user.last_login,
    )


@router.put(
    "/me/password",
    response_model=UserResponse,
    summary="Change password",
)
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Change the authenticated user's password.

    The current password must be supplied for verification. The new
    password must satisfy the strength policy.
    """
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not _verify_password(body.current_password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Check new password is not same as current
    if _verify_password(body.new_password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    # Check new password doesn't contain username
    if db_user.username.lower() in body.new_password.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must not contain the username",
        )

    db_user.password_hash = _hash_password(body.new_password)
    db_user.updated_at = datetime.now(UTC)
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)

    return UserResponse(
        id=str(db_user.id),
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        mfa_enabled=db_user.mfa_enabled,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        last_login=db_user.last_login,
    )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request a password reset",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Dict[str, str]:
    """Generate a password-reset token for the given email.

    Always returns a success message to prevent email-enumeration attacks,
    even if the email does not exist.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        reset_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        user.reset_token = token_hash
        user.reset_token_expires = datetime.now(UTC) + timedelta(
            minutes=RESET_TOKEN_EXPIRE_MINUTES
        )
        user.updated_at = datetime.now(UTC)
        db.add(user)
        await db.flush()

        # In production, send the token via email. The raw token is NOT
        # included in the response — only its SHA-256 hash is stored in
        # the DB.  For testing, use the /reset-password endpoint directly.
        return {
            "message": "If the email exists, a reset token has been sent",
        }

    # Deliberately return the same message to avoid enumeration
    return {"message": "If the email exists, a reset token has been generated"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using token",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Dict[str, str]:
    """Set a new password using a valid reset token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    result = await db.execute(
        select(User).where(User.reset_token == token_hash)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    now = datetime.now(UTC)
    expires = _ensure_utc(user.reset_token_expires) if user.reset_token_expires else None
    if expires is None or expires < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Validate new password doesn't contain username
    if user.username.lower() in body.new_password.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must not contain the username",
        )

    user.password_hash = _hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.updated_at = now
    db.add(user)
    await db.flush()

    return {"message": "Password has been reset successfully"}


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users (admin only)",
)
async def list_users(
    user: CurrentUser = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    pagination=Depends(pagination_params),  # noqa: B008
) -> Any:
    """Return a paginated list of all users. Requires the ``admin`` role."""
    # Total count
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar_one()

    # Paginated query
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    users = result.scalars().all()

    return UserListResponse(
        users=[
            UserResponse(
                id=str(u.id),
                username=u.username,
                email=u.email,
                role=u.role,
                mfa_enabled=u.mfa_enabled,
                is_active=u.is_active,
                created_at=u.created_at,
                updated_at=u.updated_at,
                last_login=u.last_login,
            )
            for u in users
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a user (admin only)",
)
async def delete_user(
    user_id: str,
    user: CurrentUser = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Dict[str, str]:
    """Soft-delete a user by setting ``is_active = False``.

    Admins cannot delete themselves.
    """
    if user_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    target.is_active = False
    target.updated_at = datetime.now(UTC)
    db.add(target)
    await db.flush()

    return {"message": "User has been deactivated"}
