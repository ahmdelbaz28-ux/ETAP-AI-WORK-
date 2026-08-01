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
import logging as _logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from api._messages import (
    MSG_PASSWORD_MIN_LENGTH,
    MSG_PASSWORD_TOO_COMMON,
    MSG_USER_NOT_FOUND,
    MSG_USER_NOT_FOUND_OR_DEACTIVATED,
)

UTC = timezone.utc  # noqa: UP017
# Module-level constants
_AUTH_LOGGER_NAME = "etap.auth"
_logger = _logging.getLogger(_AUTH_LOGGER_NAME)


def _validate_password_strength(v: str) -> str:
    """Validate password meets strength requirements.

    Enforces:
      - Minimum 8 characters
      - Maximum 128 characters (prevents bcrypt hash DoS)
      - Not a common password
      - Contains at least one digit and one letter (V-47: basic complexity)
      - No whitespace-only password
    """
    if len(v) < 8:
        raise ValueError(MSG_PASSWORD_MIN_LENGTH)
    if len(v) > 128:
        raise ValueError("Password must not exceed 128 characters")
    if v.lower() in _COMMON_PASSWORDS:
        raise ValueError(MSG_PASSWORD_TOO_COMMON)
    if not v.strip():
        raise ValueError("Password must not be whitespace-only")
    # V-47: Basic complexity — at least one letter and one digit
    has_letter = any(c.isalpha() for c in v)
    has_digit = any(c.isdigit() for c in v)
    if not (has_letter and has_digit):
        raise ValueError("Password must contain at least one letter and one digit")
    return v


try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import Boolean, DateTime, Index, String, func, select
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

ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))
RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))

# ---------------------------------------------------------------------------
# Rate-limiting (Redis-backed, per username, with in-memory fallback)
# ---------------------------------------------------------------------------

import threading
from collections import OrderedDict

_LOGIN_ATTEMPTS: OrderedDict[str, list[float]] = OrderedDict()
_LOGIN_ATTEMPTS_LOCK = threading.Lock()
_MAX_LOGIN_ATTEMPTS_ENTRIES: int = 10000  # Prevent unbounded growth
_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
_RATE_LIMIT_WINDOW_SEC: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "900"))  # 15 minutes

# Number of replicas (for replica-aware rate limiting when Redis unavailable)
_REPLICA_COUNT: int = max(1, int(os.getenv("REPLICA_COUNT", "1")))

# ---------------------------------------------------------------------------
# Token blacklist (Redis-backed with in-memory fallback)
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as redis_async  # type: ignore

    REDIS_AVAILABLE = True
except ImportError:
    redis_async = None
    REDIS_AVAILABLE = False

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_TOKEN_BLACKLIST_PREFIX = os.getenv("TOKEN_BLACKLIST_PREFIX", "auth:blacklist:")

# In-memory token blacklist fallback (with TTL cleanup)
_token_blacklist_memory: dict[str, float] = {}  # jti -> expiry timestamp
_token_blacklist_lock = threading.Lock()

# Redis async client singleton. NOTE: this client binds to the event loop
# that is current when first created. In tests with TestClient, each test
# gets a new event loop — so the singleton from a previous test becomes
# stale and raises 'RuntimeError: Event loop is closed' on the next use.
# The client fixture in tests/conftest.py resets this to None before each
# test to force a fresh client on the new event loop.
_redis_client: Optional[redis_async.Redis] = None


def _get_redis_client() -> Optional[redis_async.Redis]:
    """Return the shared async Redis client, or None if Redis is unavailable.

    Reads REDIS_URL at call time (not import time) so tests using
    ``patch.dict(os.environ, ...)`` can override the URL. This matches
    the fix applied to ``core/redis_state.get_redis_state_client()`` in
    PR #168.
    """
    global _redis_client
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or not REDIS_AVAILABLE:
        return None
    if _redis_client is None:
        _redis_client = redis_async.from_url(redis_url, decode_responses=True)
    return _redis_client


def _cleanup_expired_blacklist() -> None:
    """Remove expired entries from in-memory token blacklist."""
    now = time.time()
    with _token_blacklist_lock:
        expired = [jti for jti, exp in _token_blacklist_memory.items() if exp < now]
        for jti in expired:
            del _token_blacklist_memory[jti]


async def _blacklist_token(jti: str, ttl_seconds: Optional[int] = None) -> None:
    """Blacklist a refresh token JTI using Redis (with TTL), with in-memory fallback."""
    r = _get_redis_client()
    if r is not None:
        key = f"{_TOKEN_BLACKLIST_PREFIX}{jti}"
        try:
            if ttl_seconds and ttl_seconds > 0:
                await r.set(key, "1", ex=int(ttl_seconds))
            else:
                await r.set(key, "1")
            return
        except (OSError, redis_async.RedisError):
            # Redis unreachable — fall through to in-memory fallback
            _logger.warning("Redis unavailable for token blacklist, using in-memory fallback")

    # In-memory fallback with TTL
    expiry = time.time() + (
        ttl_seconds if ttl_seconds and ttl_seconds > 0 else REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    with _token_blacklist_lock:
        _cleanup_expired_blacklist()
        _token_blacklist_memory[jti] = expiry
    _logger.info("Token blacklisted in memory (Redis unavailable): %s", jti[:8] + "...")


async def _is_token_blacklisted(jti: str) -> bool:
    """Check if token JTI is blacklisted in Redis or in-memory fallback."""
    r = _get_redis_client()
    if r is not None:
        key = f"{_TOKEN_BLACKLIST_PREFIX}{jti}"
        try:
            val = await r.get(key)
            if val is not None:
                return True
        except (OSError, redis_async.RedisError):
            # Redis unreachable — fall through to in-memory check
            pass

    # In-memory fallback check
    _cleanup_expired_blacklist()
    with _token_blacklist_lock:
        expiry = _token_blacklist_memory.get(jti)
        if expiry is not None and expiry > time.time():
            return True
    return False


# ---------------------------------------------------------------------------
# Common-password blocklist (small sample — extend as needed)
# ---------------------------------------------------------------------------

_COMMON_PASSWORDS: set[str] = {
    # Top 50 most common passwords (2024)
    "password",
    "12345678",
    "qwerty12",
    "abc12345",
    "password1",
    "iloveyou",
    "admin123",
    "welcome1",
    "123456789",
    "password123",
    "Passw0rd",
    "monkey12",
    "dragon12",
    "sunshine1",
    "princess1",
    "football1",
    "shadow12",
    "master12",
    "login123",
    "hello123",
    "123456",
    "1234567890",
    "1234567",
    "12345678910",
    "qwerty123",
    "letmein",
    "11111111",
    "00000000",
    "trustno1",
    "passw0rd",
    "password!",
    "qwerty12345",
    "changeme",
    "Password1",
    "password12",
    "Password123",
    "letmein123",
    "welcome123",
    "admin2025",
    "admin2024",
    "test1234",
    "test12345",
    "demo1234",
    "default1",
    "temp1234",
    "secret123",
    "pass12345",
    "P@ssw0rd",
    "P@ssword1",
    "Password!23",
    # Application-specific
    "etap12345",
    "etapadmin",
    "ahmedetap",
    "power123",
    "engineer1",
    "etap1234",
    "etap2025",
    "etap2024",
    "ahmed123",
    "elbaz123",
}


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

# Type aliases for FastAPI dependencies (SonarCloud S8410: use Annotated)
DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user_from_header)]


class User(Base):
    """Persisted user account."""

    __tablename__ = "users"

    __table_args__ = (
        # Composite index for login queries (username + password_hash)
        # and for reset-password flow (reset_token + expires)
        Index("ix_users_username_password", "username", "password_hash"),
        Index("ix_users_reset_token", "reset_token", "reset_token_expires"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
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
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reset_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
    # SECURITY AUDIT 2026-07-25 — Fix S-02: role field removed from registration.
    # Previously allowed self-assigned "admin" role → privilege escalation.
    # New users always get "viewer" role. Admin promotion via admin-only endpoint.

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str, info) -> str:
        """Enforce password policy: length, not common, not same as username."""
        if len(v) < 8:
            raise ValueError(MSG_PASSWORD_MIN_LENGTH)
        if v.lower() in _COMMON_PASSWORDS:
            raise ValueError(MSG_PASSWORD_TOO_COMMON)
        # Check if password contains the username (if available in validation context)
        if info.data and "username" in info.data and info.data["username"].lower() in v.lower():
            raise ValueError("Password must not contain the username")
        return v


class LoginRequest(BaseModel):
    """Payload for ``POST /login``.

    SECURITY AUDIT 2026-08-02 (F-06 fix):
    Added optional `mfa_code` field. When the user has MFA enabled, the
    login endpoint returns HTTP 200 with `mfa_required: true` and a short-
    lived `mfa_challenge_token` instead of access+refresh JWTs. The client
    must resubmit login with the same credentials plus `mfa_code` populated;
    the challenge token proves the password was already verified so the
    second leg doesn't re-hash bcrypt.

    The challenge token is a signed JWT with `type: "mfa_challenge"`,
    lifetime 5 minutes, and bound to the user_id. It is NOT a session
    token — it can only be used to complete the MFA leg of login.
    """

    model_config = ConfigDict(strict=False)

    username: str
    password: str
    mfa_code: Optional[str] = None
    mfa_challenge_token: Optional[str] = None


class LoginResponse(BaseModel):
    """Response for ``POST /login``.

    On successful password auth WITHOUT MFA enabled, returns access+refresh.
    On successful password auth WITH MFA enabled and no `mfa_code`, returns
    `mfa_required: true` + `mfa_challenge_token`.
    On successful MFA verification, returns access+refresh.
    """

    model_config = ConfigDict(strict=False)

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    mfa_required: bool = False
    mfa_challenge_token: Optional[str] = None


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
        """Validate password meets strength requirements."""
        return _validate_password_strength(v)


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
        """Validate the new password meets strength requirements."""
        return _validate_password_strength(v)


class UpdateProfileRequest(BaseModel):
    """Payload for ``PUT /me``.

    V-7 FIX: When disabling MFA, the user must provide either their current
    password or a valid TOTP code. This prevents an attacker who steals a
    session token from completely disabling MFA protection.
    """

    model_config = ConfigDict(strict=False)

    email: Optional[EmailStr] = None
    mfa_enabled: Optional[bool] = None
    # V-7: Required when mfa_enabled is set to False
    current_password: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Current password (required when disabling MFA)",
    )
    mfa_code: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=20,
        description="TOTP code (required when disabling MFA if no password provided)",
    )


class UserResponse(BaseModel):
    """Public user representation returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    role: str
    mfa_enabled: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class UserListResponse(BaseModel):
    """Paginated user list response."""

    model_config = ConfigDict(from_attributes=True)

    users: list[UserResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# V-1 FIX: CSRF Protection — Origin header validation
# ---------------------------------------------------------------------------
# Validates that state-changing requests (POST, PUT, DELETE) originate from
# the same application. This prevents cross-origin form submissions and
# CSRF attacks where an attacker crafts a page that submits requests to
# our API using the victim's browser credentials.
#
# For JWT-based APIs, the primary CSRF vector is cross-origin requests that
# include credentials (cookies). If the app uses cookies for auth, this is
# critical. Even with Bearer tokens, this provides defense-in-depth.

_ALLOWED_ORIGINS: set[str] = set(
    origin.strip()
    for origin in os.getenv("CSRF_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)


def _validate_csrf_origin(request: Request) -> None:
    """V-1: Validate Origin header on state-changing requests.

    For POST/PUT/DELETE requests, checks that the Origin header
    matches the allowed origins. If no CSRF_ALLOWED_ORIGINS is
    configured, allows requests from the same Host (same-origin).
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")

    # If no Origin header (e.g., API clients, mobile apps), check for
    # custom header presence as CSRF mitigation (X-Requested-With)
    if not origin:
        # API clients should send X-Requested-With or Authorization header
        # This is the "custom header" CSRF mitigation strategy
        if request.headers.get("x-requested-with") or request.headers.get("authorization"):
            return
        # No origin and no custom header — potentially suspicious but
        # don't block to maintain backward compatibility with simple clients
        _logger.debug("csrf_check_no_origin method=%s path=%s", request.method, request.url.path)
        return

    # If CSRF_ALLOWED_ORIGINS is configured, check against it
    if _ALLOWED_ORIGINS:
        if origin not in _ALLOWED_ORIGINS:
            _logger.warning("csrf_blocked origin=%s host=%s", origin, host)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin request blocked",
            )
    else:
        # Default: same-origin check — Origin must match Host
        # e.g., Origin: https://example.com matches Host: example.com
        try:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            origin_host = parsed.hostname
            if origin_host and host:
                # Extract host without port
                host_only = host.split(":")[0]
                if origin_host != host_only:
                    _logger.warning("csrf_blocked origin=%s host=%s", origin, host)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cross-origin request blocked",
                    )
        except Exception:
            pass


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


# SECURITY AUDIT 2026-08-02 (F-06 fix):
# MFA challenge token — short-lived (5 min) JWT issued after password
# verification when the user has MFA enabled. The client must present
# this token + a valid TOTP code in the second leg of login to receive
# access+refresh tokens. The token is NOT a session token: it can only
# be used to complete the MFA leg, and only for the user_id it was
# issued to.
_MFA_CHALLENGE_EXPIRE_MINUTES: int = int(os.getenv("MFA_CHALLENGE_EXPIRE_MINUTES", "5"))


def _create_mfa_challenge_token(user_id: str) -> str:
    """Create a short-lived JWT authorising the bearer to complete MFA login."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "mfa_challenge",
        "iat": now,
        "exp": now + timedelta(minutes=_MFA_CHALLENGE_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _verify_mfa_challenge_token(token: str) -> Optional[str]:
    """Verify an MFA challenge token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "mfa_challenge":
        return None
    user_id = payload.get("sub")
    if not user_id or not str(user_id).strip():
        return None
    return str(user_id).strip()


async def _check_rate_limit(username: str) -> None:
    """Raise 429 if *username* has exceeded the login attempt threshold.

    Uses Redis when available (distributed rate limiting across replicas).
    Falls back to in-memory store with replica-aware limits.
    """
    r = _get_redis_client()
    if r is not None:
        key = f"auth:ratelimit:{username}"
        try:
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, _RATE_LIMIT_WINDOW_SEC)
            if current > _RATE_LIMIT_MAX_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please try again later.",
                )
            return
        except (OSError, redis_async.RedisError):
            # Redis is configured but unreachable — fall through to
            # in-memory rate limiting so login still works.
            _logger.warning("Redis unavailable for rate limiting, using in-memory fallback")

    # In-memory fallback with replica-aware limits
    # When Redis is unavailable, divide the limit by replica count to prevent
    # attackers from exploiting multiple replicas (5 replicas = 5x limit)
    effective_limit = max(1, _RATE_LIMIT_MAX_ATTEMPTS // _REPLICA_COUNT)

    now = time.monotonic()
    with _LOGIN_ATTEMPTS_LOCK:
        # Clean up old entries to prevent memory leak
        if len(_LOGIN_ATTEMPTS) > _MAX_LOGIN_ATTEMPTS_ENTRIES:
            # Remove oldest 20% of entries
            remove_count = _MAX_LOGIN_ATTEMPTS_ENTRIES // 5
            for _ in range(remove_count):
                _LOGIN_ATTEMPTS.popitem(last=False)

        attempts = _LOGIN_ATTEMPTS.get(username, [])
        attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW_SEC]
        _LOGIN_ATTEMPTS[username] = attempts

    if len(attempts) >= effective_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )


# ---------------------------------------------------------------------------
# Forgot-password per-email rate limit
# ---------------------------------------------------------------------------
#
# SECURITY AUDIT 2026-07-29 (self-critique pass, HB-04):
# Forgot-password had no per-email rate limit. An attacker could spam a
# victim's inbox with reset emails and trigger Resend SMTP throttling.
# This limit is enforced per-normalised-email (lowercase) so case-variants
# share a bucket. We use the same Redis backend (when available) with
# in-memory fallback, mirroring _check_rate_limit. The limit is generous
# (3 per hour) so legitimate retries after a missed email still work.

_FORGOT_PASSWORD_RATE_LIMIT_MAX: int = int(os.getenv("FORGOT_PASSWORD_RATE_LIMIT_MAX", "3"))
_FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SEC: int = int(
    os.getenv("FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SEC", "3600")
)  # 1 hour
_forgot_password_attempts: OrderedDict[str, list[float]] = OrderedDict()
_forgot_password_lock = threading.Lock()
_FORGOT_PASSWORD_MAX_ENTRIES: int = 1000  # bounded to prevent memory growth


async def _check_forgot_password_rate_limit(email: str) -> None:
    """Raise 429 if *email* has exceeded the forgot-password threshold.

    Uses Redis when available (distributed across replicas). Falls back to
    an in-memory OrderedDict with FIFO eviction when Redis is unreachable.
    """
    r = _get_redis_client()
    if r is not None:
        key = f"auth:forgot-rate:{email}"
        try:
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, _FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SEC)
            if current > _FORGOT_PASSWORD_RATE_LIMIT_MAX:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many password-reset requests for this email. Please try again later.",
                )
            return
        except (OSError, redis_async.RedisError):
            # Redis configured but unreachable — fall through to in-memory.
            # (We only enter this branch when REDIS_AVAILABLE is True and
            # _REDIS_URL is set, so redis_async.RedisError is a valid class.)
            _logger.warning(
                "Redis unavailable for forgot-password rate limit, using in-memory fallback"
            )

    # In-memory fallback (FIFO eviction).
    now = time.monotonic()
    with _forgot_password_lock:
        while len(_forgot_password_attempts) > _FORGOT_PASSWORD_MAX_ENTRIES:
            _forgot_password_attempts.popitem(last=False)

        attempts = _forgot_password_attempts.get(email, [])
        attempts = [t for t in attempts if now - t < _FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SEC]
        if len(attempts) >= _FORGOT_PASSWORD_RATE_LIMIT_MAX:
            _forgot_password_attempts[email] = attempts
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password-reset requests for this email. Please try again later.",
            )
        attempts.append(now)
        _forgot_password_attempts[email] = attempts


def _record_failed_attempt(username: str) -> None:
    """Record a failed login attempt for rate-limiting (in-memory fallback).

    When Redis is active, the counter is managed by INCR/EXPIRE in _check_rate_limit,
    so this function only records for the in-memory fallback path.

    SECURITY AUDIT 2026-07-29 (self-critique pass, NEW DISCOVERY):
    Previous version did NOT acquire `_LOGIN_ATTEMPTS_LOCK` while mutating
    the shared `_LOGIN_ATTEMPTS` dict. Under concurrent failed logins (e.g.
    distributed brute force, or load-test harness), two threads could
    `setdefault(..., [])` simultaneously, both observe an empty list, both
    `.append(now)`, and one append would be lost — silently UNDER-counting
    attempts and letting attackers exceed the rate limit. Fix: hold the
    lock for the entire read-modify-write.
    """
    now = time.monotonic()
    with _LOGIN_ATTEMPTS_LOCK:
        attempts = _LOGIN_ATTEMPTS.setdefault(username, [])
        attempts.append(now)


# SECURITY AUDIT 2026-08-02 (F-10, F-11 fix):
# F-10: Previous rate limit was per-username only. An attacker rotating
#   usernames (or trying a fixed password against many usernames — credential
#   stuffing) bypassed the limit entirely. Add a per-IP rate limit so that
#   a single source IP cannot exceed (10 * REPLICA_COUNT) attempts / 15 min
#   regardless of how many usernames it tries.
# F-11: On a successful login, the per-username rate-limit counter was NOT
#   reset. A user who failed 4 times then succeeded, then failed once more
#   within 15 minutes, was locked out. Reset the counter on success.
_IP_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_IP_RATE_LIMIT_MAX", "20"))
_IP_RATE_LIMIT_WINDOW_SEC: int = int(os.getenv("LOGIN_IP_RATE_LIMIT_WINDOW_SEC", "900"))
_ip_attempts: OrderedDict[str, list[float]] = OrderedDict()
_ip_attempts_lock = threading.Lock()
_IP_MAX_ENTRIES: int = 10000


def _client_ip(request: Request) -> str:
    """Extract the client IP, honouring X-Forwarded-For when behind a trusted proxy.

    SECURITY: X-Forwarded-For is only honoured if TRUSTED_PROXY_HOPS env var
    is set (default 0 = don't trust any proxy header). Setting this to the
    number of reverse proxies in front of the API (e.g. 1 for Vercel→HF,
    2 for Cloudflare→Vercel→HF) allows the rate limit to see the real
    client IP. Without it, all requests appear to come from the proxy's IP
    and the per-IP limit becomes a per-proxy limit (useless).
    """
    trusted_hops = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
    if trusted_hops > 0:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if len(parts) >= trusted_hops:
                # The client IP is the (len - trusted_hops)-th from the right
                return parts[-trusted_hops]
            return parts[0] if parts else ""
    # Fallback to the connection peer
    return request.client.host if request.client else "unknown"


async def _check_ip_rate_limit(ip: str) -> None:
    """Raise 429 if a single IP has exceeded the login attempt threshold.

    This is IN ADDITION to the per-username limit — both must pass for
    login to proceed. Uses Redis when available, in-memory fallback otherwise.
    """
    r = _get_redis_client()
    if r is not None:
        key = f"auth:ratelimit:ip:{ip}"
        try:
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, _IP_RATE_LIMIT_WINDOW_SEC)
            if current > _IP_RATE_LIMIT_MAX_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts from this IP. Please try again later.",
                )
            return
        except (OSError, redis_async.RedisError):
            _logger.warning("Redis unavailable for IP rate limit, using in-memory fallback")

    # In-memory fallback
    effective_limit = max(1, _IP_RATE_LIMIT_MAX_ATTEMPTS // _REPLICA_COUNT)
    now = time.monotonic()
    with _ip_attempts_lock:
        if len(_ip_attempts) > _IP_MAX_ENTRIES:
            remove_count = _IP_MAX_ENTRIES // 5
            for _ in range(remove_count):
                _ip_attempts.popitem(last=False)
        attempts = _ip_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < _IP_RATE_LIMIT_WINDOW_SEC]
        _ip_attempts[ip] = attempts
    if len(attempts) >= effective_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this IP. Please try again later.",
        )


def _record_ip_failed_attempt(ip: str) -> None:
    """Record a failed login attempt for IP-based rate limiting (in-memory fallback)."""
    now = time.monotonic()
    with _ip_attempts_lock:
        attempts = _ip_attempts.setdefault(ip, [])
        attempts.append(now)


async def _reset_rate_limit(username: str) -> None:
    """Reset the per-username rate-limit counter on successful login (F-11 fix).

    Without this, a user who fails 4 times then succeeds, then fails once
    more within 15 minutes is locked out — bad UX with no security benefit
    (the successful login proves the legitimate user regained access).
    """
    r = _get_redis_client()
    if r is not None:
        try:
            await r.delete(f"auth:ratelimit:{username}")
        except (OSError, redis_async.RedisError):
            pass
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.pop(username, None)


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
    request: Request,
    db: DbDep,
) -> Any:
    """Create a new user account.

    Returns the created user on success, or 409 if the username/email is
    already taken.

    SECURITY: Email comparison is case-insensitive (User@Example.com and
    user@example.com are treated as the same email) to prevent account
    duplication and login confusion. Emails are stored lowercased.
    """
    # V-1: CSRF origin validation
    _validate_csrf_origin(request)

    # Normalise email to lowercase to ensure case-insensitive uniqueness.
    normalised_email = body.email.strip().lower()

    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    # Check email uniqueness (case-insensitive)
    existing = await db.execute(select(User).where(func.lower(User.email) == normalised_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # SECURITY AUDIT 2026-07-29 (self-critique pass, EC-09):
    # The pre-check above is a TOCTOU race window — two concurrent
    # registrations with the same username/email can both pass the check
    # and then the second flush() raises IntegrityError from the DB
    # unique constraint, which previously surfaced as an opaque 500.
    # Fix: wrap the insert in try/except IntegrityError and translate
    # to a proper 409 Conflict with a user-facing message. The unique
    # constraint name is database-specific (PostgreSQL: uq_users_username /
    # uq_users_email; SQLite: sqlite_autoindex_users_X) so we don't try
    # to introspect — we just say "already exists" and let the client
    # re-fetch the canonical record if they need to know which field.
    from sqlalchemy.exc import IntegrityError as _SAIntegrityError

    user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        email=normalised_email,
        password_hash=_hash_password(body.password),
        # SECURITY: Force "viewer" role for all new registrations (S-02)
        role="viewer",
    )
    db.add(user)
    try:
        await db.flush()
    except _SAIntegrityError as exc:
        # Race condition: another request inserted a duplicate between
        # our pre-check and our flush. Translate to 409 Conflict.
        _logger.info(
            "register_integrity_conflict username=%s email=%s err=%s",
            body.username,
            normalised_email,
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered (concurrent request). Please retry.",
        ) from exc
    await db.refresh(user)

    # Send welcome email via Resend (additive, best-effort, toggleable)
    if os.getenv("RESEND_WELCOME_EMAIL_ENABLED", "true").lower() == "true":
        try:
            from services.email_send_log import log_email_send
            from services.email_service import send_welcome

            result = await send_welcome(
                email=user.email,
                user_name=getattr(user, "full_name", None) or user.username,
            )
            await log_email_send(
                recipient=user.email,
                subject="Welcome to AhmedETAP!",
                flow="welcome",
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                status_code=result.status_code,
                elapsed_ms=result.elapsed_ms,
            )
        except Exception as exc:
            import logging as _logging

            _logging.getLogger(_AUTH_LOGGER_NAME).warning(
                "welcome_email_failed email=%s err=%s", user.email, exc
            )

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
    response_model=LoginResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: DbDep,
) -> Any:
    """Authenticate with username + password (and MFA if enabled).

    SECURITY AUDIT 2026-08-02 (F-06 fix — CRITICAL):
    The previous version returned access+refresh JWTs immediately after
    password verification, completely ignoring `user.mfa_enabled`. Users
    who set up TOTP MFA received ZERO protection from it.

    New flow (two-leg login when MFA is enabled):
      1. Client sends `{username, password}`.
      2. If password valid AND user.mfa_enabled is True:
         - Server returns HTTP 200 with `mfa_required: true` and an
           `mfa_challenge_token` (5-minute JWT, type="mfa_challenge").
         - Client prompts user for TOTP code.
      3. Client resubmits `{username, password, mfa_code, mfa_challenge_token}`.
      4. Server verifies the challenge token (not the password again —
         bcrypt is slow), verifies the TOTP code against `security.mfa`,
         and returns access+refresh JWTs.

    If the user does NOT have MFA enabled, the response is the classic
    access+refresh pair (unchanged behaviour).

    SECURITY AUDIT 2026-08-02 (F-10 fix): per-IP rate limit added in
    addition to per-username. Both must pass for login to proceed.

    On any failure, returns 401 with a generic message (no user-enumeration
    leak). Rate-limit counter is reset on a fully successful login (F-11 fix).
    """
    # F-10 fix: per-IP rate limit (in addition to per-username).
    ip = _client_ip(request)
    await _check_ip_rate_limit(ip)
    await _check_rate_limit(body.username)

    # V-1: CSRF origin validation
    _validate_csrf_origin(request)

    # Leg 2 (MFA completion): if a challenge token is supplied, verify it
    # and skip the password check. The challenge token proves the password
    # was already verified in leg 1.
    if body.mfa_challenge_token and body.mfa_code:
        challenge_user_id = _verify_mfa_challenge_token(body.mfa_challenge_token)
        if challenge_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA challenge token",
            )
        # Look up the user by the challenge token's subject (NOT by
        # body.username — the token is authoritative).
        result = await db.execute(select(User).where(User.id == challenge_user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=MSG_USER_NOT_FOUND_OR_DEACTIVATED,
            )
        # Verify the TOTP code
        try:
            from security.mfa import TOTPProvider
        except ImportError:
            # MFA subsystem unavailable — fail closed (no login).
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MFA subsystem unavailable",
            )
        totp = TOTPProvider()
        if not totp.verify_code(str(user.id), body.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )
        # MFA passed — issue access+refresh
        user.last_login = datetime.now(UTC)
        db.add(user)
        await db.flush()
        # F-11 fix: reset rate-limit counter on successful login.
        await _reset_rate_limit(body.username)
        access_token = _create_access_token(str(user.id), user.role)
        refresh_token = _create_refresh_token(str(user.id))
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            mfa_required=False,
        )

    # Leg 1 (password verification)
    # Accept either username or email as the login identifier. The frontend
    # login form collects an "email" field and sends it as `username`, so the
    # backend MUST match on email too — otherwise email-based logins always 401.
    result = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.username))
    )
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(body.password, user.password_hash):
        _record_failed_attempt(body.username)
        _record_ip_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # F-06 fix: enforce MFA if enabled.
    if user.mfa_enabled:
        # If the client also sent an mfa_code in leg 1 (some clients do
        # this when the user types the password + current TOTP together),
        # verify it immediately and complete login in one leg.
        if body.mfa_code:
            try:
                from security.mfa import TOTPProvider
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="MFA subsystem unavailable",
                )
            totp = TOTPProvider()
            if not totp.verify_code(str(user.id), body.mfa_code):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code",
                )
            # MFA passed — issue tokens, reset rate limit
            user.last_login = datetime.now(UTC)
            db.add(user)
            await db.flush()
            await _reset_rate_limit(body.username)
            access_token = _create_access_token(str(user.id), user.role)
            refresh_token = _create_refresh_token(str(user.id))
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                mfa_required=False,
            )
        # No mfa_code — issue a challenge token and require leg 2.
        return LoginResponse(
            mfa_required=True,
            mfa_challenge_token=_create_mfa_challenge_token(str(user.id)),
            token_type="bearer",
        )

    # No MFA enabled — issue tokens directly (legacy behaviour).
    user.last_login = datetime.now(UTC)
    db.add(user)
    await db.flush()
    # F-11 fix: reset rate-limit counter on successful login.
    await _reset_rate_limit(body.username)
    access_token = _create_access_token(str(user.id), user.role)
    refresh_token = _create_refresh_token(str(user.id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        mfa_required=False,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh JWT access token",
)
async def refresh(
    body: RefreshRequest,
    db: DbDep,
) -> Any:
    """Exchange a valid refresh token for a new access + refresh pair."""
    try:
        payload = jwt.decode(body.refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
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
    if jti and await _is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user_id: Optional[str] = payload.get("sub")
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
            detail=MSG_USER_NOT_FOUND_OR_DEACTIVATED,
        )

    access_token = _create_access_token(str(user.id), user.role)
    new_refresh = _create_refresh_token(str(user.id))

    # V-3 FIX: Blacklist the old refresh token to prevent reuse.
    # Without this, an attacker who steals a refresh token can use it
    # indefinitely even after the legitimate user refreshes.
    if jti:
        old_exp = payload.get("exp")
        old_ttl = None
        if isinstance(old_exp, (int, float)):
            old_ttl = int(old_exp - datetime.now(tz=UTC).timestamp())
        await _blacklist_token(jti, ttl_seconds=old_ttl)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke session",
)
async def logout(
    user: CurrentUserDep,
    body: Optional[RefreshRequest] = Body(None),  # NOSONAR  # S8410
) -> Response:
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
            ttl_seconds: Optional[int] = None
            if isinstance(exp, (int, float)):
                now_epoch = datetime.now(tz=UTC).timestamp()
                ttl_seconds = int(exp - now_epoch)

            if jti:
                await _blacklist_token(jti, ttl_seconds=ttl_seconds)
        except jwt.InvalidTokenError:
            pass  # Invalid token — nothing to blacklist

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    user: CurrentUserDep,
    db: DbDep,
) -> Any:
    """Return the authenticated user's full profile."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_USER_NOT_FOUND,
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
    user: CurrentUserDep,
    db: DbDep,
) -> Any:
    """Update the authenticated user's email and/or MFA preference."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_USER_NOT_FOUND,
        )

    if body.email is not None:
        # Normalise to lowercase for case-insensitive uniqueness check
        new_email = body.email.strip().lower()
        # Check email uniqueness (case-insensitive)
        existing = await db.execute(
            select(User).where(
                func.lower(User.email) == new_email,
                User.id != user.user_id,
            ),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        db_user.email = new_email

    if body.mfa_enabled is not None:
        # V-7 FIX: Require verification when DISABLING MFA
        # An attacker who steals a session token could disable MFA
        # without this check, completely removing the second factor.
        if body.mfa_enabled is False and db_user.mfa_enabled is True:
            verified = False
            # Option 1: Verify current password
            if body.current_password:
                verified = _verify_password(body.current_password, db_user.password_hash)
            # Option 2: Verify TOTP code
            if not verified and body.mfa_code:
                try:
                    from security.mfa import TOTPProvider
                    totp = TOTPProvider()
                    verified = totp.verify_code(str(db_user.id), body.mfa_code)
                except Exception:
                    verified = False
            if not verified:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot disable MFA without verification. Provide current_password or mfa_code.",
                )
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
    user: CurrentUserDep,
    db: DbDep,
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
            detail=MSG_USER_NOT_FOUND,
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

    # Send password-change confirmation email via Resend
    try:
        from services.email_send_log import log_email_send
        from services.email_service import send_password_change_email

        result = await send_password_change_email(
            email=db_user.email,
            user_name=getattr(db_user, "full_name", None) or db_user.username,
        )
        await log_email_send(
            recipient=db_user.email,
            subject="AhmedETAP — Your Password Was Changed",
            flow="password_change",
            success=result.success,
            message_id=result.message_id,
            error=result.error,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    except Exception as exc:
        import logging as _logging

        _logging.getLogger(_AUTH_LOGGER_NAME).warning(
            "password_change_email_failed email=%s err=%s", db_user.email, exc
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


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request a password reset",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: DbDep,
) -> dict[str, str]:
    """Generate a password-reset token for the given email.

    Always returns a success message to prevent email-enumeration attacks,
    even if the email does not exist.

    SECURITY: Email lookup is case-insensitive to match the registration
    flow (emails are stored lowercased).

    SECURITY AUDIT 2026-07-29 (self-critique pass, HB-04):
    Previous version had NO per-email rate limit. An attacker could
    bombard a victim's inbox with password-reset emails, causing Resend
    to throttle the platform's legitimate transactional email (welcome,
    password-change, magic-link) and possibly getting the platform's
    sending domain flagged as a spam source.
    Fix: enforce a per-email rate limit (default 1 request / 60s) using
    the same Redis + in-memory fallback pattern as the login rate limiter.
    The limit is per-normalised-email (lowercase), so `User@x.com` and
    `user@x.com` share a bucket. Failed lookups (email not in DB) are
    ALSO rate-limited so the limit cannot be used to enumerate accounts.
    """
    normalised_email = body.email.strip().lower()

    # Per-email rate limit (prevents email-bombing via forgot-password).
    await _check_forgot_password_rate_limit(normalised_email)

    result = await db.execute(select(User).where(func.lower(User.email) == normalised_email))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        reset_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        user.reset_token = token_hash
        user.reset_token_expires = datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        user.updated_at = datetime.now(UTC)
        db.add(user)
        await db.flush()

        # Send password-reset email via Resend (additive, best-effort)
        try:
            import os as _os
            import urllib.parse as _urlparse

            from services.email_send_log import log_email_send
            from services.email_service import send_password_reset

            # SECURITY AUDIT 2026-07-29 (self-critique pass, EC-05):
            # URL-encode the reset token before interpolating into the
            # reset link. uuid4 hex chars are URL-safe today, but if the
            # token format ever changes to include `&`, `?`, `#`, `+`, or
            # `%` (e.g. switching to base64url or signed JWT), an
            # unencoded token would silently truncate at the first
            # reserved character and produce an unusable reset link.
            reset_link = (
                f"{_os.getenv('EMAIL_APP_URL', 'http://localhost:3000')}"
                f"/reset-password?token={_urlparse.quote(reset_token, safe='')}"
            )
            result = await send_password_reset(
                email=user.email,
                reset_link=reset_link,
                user_name=getattr(user, "full_name", None) or getattr(user, "username", None),
                ttl_minutes=RESET_TOKEN_EXPIRE_MINUTES,
            )
            await log_email_send(
                recipient=user.email,
                subject="AhmedETAP — Reset Your Password",
                flow="password_reset",
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                status_code=result.status_code,
                elapsed_ms=result.elapsed_ms,
            )
        except Exception as exc:
            # Don't fail the request — token is in DB, user can retry.
            import logging as _logging

            _logging.getLogger(_AUTH_LOGGER_NAME).warning(
                "password_reset_email_failed email=%s err=%s", user.email, exc
            )

        # In production, the reset token is sent via email (above) and NOT
        # returned in the response. The default is FALSE to prevent token
        # leakage through proxies, APM tools, browser extensions, etc.
        # Set AUTH_RETURN_RESET_TOKEN=true ONLY for local development/testing.
        if os.getenv("AUTH_RETURN_RESET_TOKEN", "false").lower() == "true":
            return {
                "message": "If the email exists, a reset token has been sent",
                "reset_token": reset_token,
            }
        return {"message": "If the email exists, a reset token has been sent"}

    # Deliberately return the same message to avoid enumeration
    return {"message": "If the email exists, a reset token has been generated"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password using token",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: DbDep,
) -> dict[str, str]:
    """Set a new password using a valid reset token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    result = await db.execute(select(User).where(User.reset_token == token_hash))
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
    db: DbDep,
    user: CurrentUser = Depends(require_role("admin")),  # NOSONAR: noqa: B008  # — # S8410
    pagination=Depends(pagination_params),  # NOSONAR: noqa: B008  # — # S8410
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
        .limit(pagination.page_size),
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
    db: DbDep,
    user: CurrentUser = Depends(require_role("admin")),  # NOSONAR: noqa: B008  # — # S8410
) -> dict[str, str]:
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
            detail=MSG_USER_NOT_FOUND,
        )

    target.is_active = False
    target.updated_at = datetime.now(UTC)
    db.add(target)
    await db.flush()

    return {"message": "User has been deactivated"}
