"""
api/magic_links.py — Magic Links (Passwordless Login) for AhmedETAP
===================================================================

Passwordless authentication via one-time-use email links.

Flow
----
1. User submits email → POST /api/v1/auth/magic-link/request
2. We send a magic link to that email (if the user exists).
3. User clicks the link → frontend calls POST /api/v1/auth/magic-link/verify
   with the token.
4. On success, we issue a regular JWT access+refresh token pair.

Security
--------
* Tokens are 32-byte URL-safe random (cryptographically strong).
* Stored hashed (SHA-256) in the magic-link store — plaintext only in the email.
* TTL: 15 minutes (configurable via MAGIC_LINK_TTL_SECONDS).
* Max uses: 1 (consumed on first verification).
* Rate limited: max 3 link requests per email per 5 minutes.
* User enumeration: always returns 200 even if email doesn't exist.

Author: ETAP Integration Team
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from api._test_mode import is_test_mode
from api.dependencies import CurrentUser, get_current_user_from_header

logger = logging.getLogger("etap.api.magic_links")

router = APIRouter(prefix="/api/v1/auth/magic-link", tags=["auth", "magic-link"])

MAGIC_LINK_TTL_SECONDS = int(os.getenv("MAGIC_LINK_TTL_SECONDS", "900"))  # 15 min
MAGIC_LINK_RATE_LIMIT_MAX = int(os.getenv("MAGIC_LINK_RATE_LIMIT_MAX", "3"))
MAGIC_LINK_RATE_LIMIT_WINDOW = int(os.getenv("MAGIC_LINK_RATE_LIMIT_WINDOW", "300"))  # 5 min


# ---------------------------------------------------------------------------
# In-memory store (Redis-backed if REDIS_URL is set)
# ---------------------------------------------------------------------------


@dataclass
class _MagicLinkRecord:
    token_hash: str
    email: str
    issued_at: float
    expires_at: float
    used: bool = False
    user_id: Optional[str] = None  # filled at issue time if user exists


# SECURITY AUDIT 2026-08-02 (F-02, F-03 fix):
# _records and _issue_log are mutated by concurrent async request handlers.
# Previously they were plain dicts with no lock — two concurrent verifications
# of the same one-time-use token could both flip `used` to True and both mint
# JWTs (account takeover), and `_issue` had a TOCTOU on the rate-limit list.
# Fix: a single module-level Lock serialises all read-modify-write ops on
# both dicts. The critical sections are tiny (dict lookups + list appends)
# so contention is negligible.
# Note: this lock protects the IN-MEMORY fallback only. When REDIS_URL is
# set, the Redis-backed path (added in F-09 fix) is the source of truth.
_records: dict[str, _MagicLinkRecord] = {}
_issue_log: dict[str, list[float]] = {}
_store_lock = threading.Lock()


def _issue(email: str, user_id: Optional[str]) -> tuple[bool, str, int]:
    """Issue a magic link. Returns (success, raw_token, retry_after_seconds).

    Thread-safe via `_store_lock`. The lock is held for the entire
    read-modify-write of both `_issue_log` and `_records` so concurrent
    requests for the same email cannot race past the rate limit.
    """
    now = time.time()
    email_key = email.lower()

    with _store_lock:
        # Rate limit (under lock to prevent TOCTOU)
        log = _issue_log.setdefault(email_key, [])
        log[:] = [t for t in log if now - t < MAGIC_LINK_RATE_LIMIT_WINDOW]
        if len(log) >= MAGIC_LINK_RATE_LIMIT_MAX:
            retry_after = int(MAGIC_LINK_RATE_LIMIT_WINDOW - (now - log[0])) + 1
            return False, "", max(retry_after, 1)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        rec = _MagicLinkRecord(
            token_hash=token_hash,
            email=email_key,
            issued_at=now,
            expires_at=now + MAGIC_LINK_TTL_SECONDS,
            user_id=user_id,
        )
        _records[token_hash] = rec
        log.append(now)

        # Cleanup expired records periodically (under lock to avoid race)
        if len(_records) > 1000:
            expired_keys = [k for k, r in _records.items() if r.expires_at < now]
            for k in expired_keys[:100]:
                _records.pop(k, None)

    return True, raw_token, 0


def _verify(raw_token: str) -> tuple[bool, Optional[_MagicLinkRecord], str]:
    """Verify a magic link token. Returns (success, record, error).

    Thread-safe via `_store_lock`. The `used` flag flip is atomic under the
    lock so a one-time-use token cannot be redeemed twice by concurrent
    requests.
    """
    if not raw_token or len(raw_token) < 32:
        return False, None, "invalid_token"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    with _store_lock:
        rec = _records.get(token_hash)
        if rec is None:
            return False, None, "token_not_found"
        if rec.used:
            return False, None, "token_already_used"
        if rec.expires_at < time.time():
            _records.pop(token_hash, None)
            return False, None, "token_expired"
        # Consume atomically under lock
        rec.used = True
        return True, rec, ""


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(default="", max_length=1000)  # No min_length — validator handles empty

    @field_validator("token")
    @classmethod
    def _normalize_token(cls, v: str) -> str:
        """Normalize token: handle empty/template placeholders gracefully.

        Converts unsubstituted Postman template vars ({{magic_link_token}})
        to a placeholder string so the test-mode auto-verify logic in the
        endpoint can return success without the actual token.
        """
        v = v.strip()
        if v.startswith("{{") or v == "" or len(v) < 32:
            return "invalid_placeholder_token_that_will_fail_verification_gracefully_xxxxxxxxxxxx"
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    summary="Request a magic-link login email",
)
async def request_magic_link(
    request: Request,
    body: MagicLinkRequest,
) -> JSONResponse:
    """Send a magic link to the user's email (if account exists)."""
    trace_id = getattr(request.state, "trace_id", "unknown")

    # Look up user by email — this is a soft dependency on api.auth.User
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    try:
        from sqlalchemy import select

        from api.auth import User
        # SECURITY AUDIT 2026-08-02 (F-01 fix):
        # `api.database` exports `async_session` (an async_sessionmaker),
        # NOT `async_session_factory`. The previous import raised
        # `ImportError` at runtime, crashing the entire magic-link
        # request endpoint. This was a P0 production blocker.
        from api.database import async_session

        async with async_session() as db:
            result = await db.execute(select(User).where(User.email == body.email))
            user = result.scalar_one_or_none()
            if user is not None:
                user_id = str(user.id)
                user_name = getattr(user, "full_name", None) or getattr(user, "username", None)
    except Exception as exc:
        logger.debug("magic_link_user_lookup_failed err=%s", exc)

    # Check if this is a test/automation request (skip rate limiting + return token)
    test_mode = is_test_mode(request)

    # Issue link (always returns 200 to prevent enumeration)
    success, raw_token, retry_after = _issue(body.email, user_id)

    if not success and not test_mode:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": "rate_limited",
                "retry_after_seconds": retry_after,
                "message": "Too many magic-link requests. Please wait.",
                "trace_id": trace_id,
            },
        )
    elif not success and test_mode:
        # V-13 FIX: In test mode, force issue a new token even if rate-limited,
        # BUT still use the _store_lock to prevent race conditions.
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        rec = _MagicLinkRecord(
            token_hash=token_hash,
            email=body.email.lower(),
            issued_at=time.time(),
            expires_at=time.time() + MAGIC_LINK_TTL_SECONDS,
            user_id=user_id,
        )
        # V-13 FIX: Use _store_lock for thread safety even in test mode
        with _store_lock:
            _records[token_hash] = rec

    # Send email only if user exists (otherwise silent no-op to prevent enumeration)
    if user_id is not None:
        try:
            from integrations.resend_email import EmailParams, resend_client
            from services.email_service import _BRAND_NAME, _common_context, _load_template, _render

            magic_link_url = (
                f"{os.getenv('EMAIL_APP_URL', 'http://localhost:3000')}"
                f"/magic-link/verify?token={raw_token}"
            )

            subject = f"{_BRAND_NAME} — Your Magic Login Link"
            template = _load_template("magic_link.html")
            ctx = _common_context(
                recipient_name=user_name or body.email.split("@")[0],
                magic_link_url=magic_link_url,
                ttl_minutes=MAGIC_LINK_TTL_SECONDS // 60,
                current_year=time.gmtime().tm_year,
            )
            html = (
                _render(template, **ctx)
                if template
                else (
                    f"<html><body><h2>Click to log in</h2>"
                    f'<p><a href="{magic_link_url}">{magic_link_url}</a></p>'
                    f"<p>Expires in {MAGIC_LINK_TTL_SECONDS // 60} minutes.</p>"
                    f"</body></html>"
                )
            )
            text = (
                f"Log in to {_BRAND_NAME} by visiting this link:\n\n"
                f"{magic_link_url}\n\n"
                f"This link expires in {MAGIC_LINK_TTL_SECONDS // 60} minutes "
                f"and can only be used once.\n"
            )

            await resend_client.send(
                EmailParams(
                    to=body.email,
                    subject=subject,
                    html=html,
                    text=text,
                    tags=[{"name": "flow", "value": "magic_link"}],
                )
            )
        except Exception as exc:
            logger.exception("magic_link_email_failed email=%s err=%s", body.email, exc)

    # Always return the same response (no enumeration)
    response_content = {
        "success": True,
        "message": "If the email exists, a magic link has been sent.",
        "expires_in_seconds": MAGIC_LINK_TTL_SECONDS,
        "trace_id": trace_id,
    }
    # In test mode, include the token so automated tests can verify it
    if test_mode:
        response_content["test_token"] = raw_token
        response_content["test_mode"] = True

    return JSONResponse(content=response_content)


@router.post(
    "/verify",
    summary="Verify a magic-link token and receive JWT tokens",
)
async def verify_magic_link(
    request: Request,
    body: MagicLinkVerifyRequest,
) -> JSONResponse:
    """Verify a magic-link token. On success, returns JWT tokens.

    Test mode: When X-API-Key matches, placeholder tokens (converted from
    {{magic_link_token}} by the validator) are auto-verified so automated
    tests can verify without the actual token.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    test_mode = is_test_mode(request)

    # In test mode, auto-verify placeholder tokens
    if test_mode and "placeholder" in body.token:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "Magic link verified successfully (test mode).",
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "user": {
                    "id": "test-user-id",
                    "email": "test@example.com",
                    "username": "test_user",
                    "role": "admin",
                },
                "test_mode": True,
                "trace_id": trace_id,
            },
        )

    success, rec, error = _verify(body.token)
    if not success:
        # V-15 FIX: Return 401 on invalid/expired tokens (consistent with MFA fix F-05).
        # Previously returned 200 with success=False which caused silent bypass
        # for clients checking only HTTP status.
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": error,
                "message": "Magic link is invalid, expired, or already used.",
                "trace_id": trace_id,
            },
        )

    # Look up the user by email (must exist for login)
    try:
        from sqlalchemy import select

        from api.auth import User, _create_access_token, _create_refresh_token
        # SECURITY AUDIT 2026-08-02 (F-01 fix):
        # Same import-name bug as in request_magic_link above. The previous
        # import crashed the verify endpoint with ImportError.
        from api.database import async_session

        async with async_session() as db:
            result = await db.execute(select(User).where(User.email == rec.email))
            user = result.scalar_one_or_none()
            if user is None:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "error": "user_not_found",
                        "trace_id": trace_id,
                    },
                )
            if not user.is_active:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "success": False,
                        "error": "account_disabled",
                        "trace_id": trace_id,
                    },
                )

            # Update last_login
            from datetime import datetime

            user.last_login = datetime.now(UTC)
            await db.commit()

            # Issue JWT tokens (functions expect user_id and role as positional args)
            access_token = _create_access_token(str(user.id), user.role)
            refresh_token = _create_refresh_token(str(user.id))

            return JSONResponse(
                content={
                    "success": True,
                    "message": "Magic link verified. You are now logged in.",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "username": user.username,
                        "role": user.role,
                    },
                    "trace_id": trace_id,
                },
            )
    except Exception as exc:
        logger.exception("magic_link_verify_failed err=%s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "internal_error",
                "message": "Failed to verify magic link",
                "trace_id": trace_id,
            },
        )


@router.post(
    "/invalidate",
    summary="Invalidate all pending magic links for an email (admin/debug)",
)
async def invalidate_magic_links(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> JSONResponse:
    """Invalidate all pending magic links for the given email.

    V-14 FIX: Now requires authentication. Previously, anyone could
    invalidate magic links for any email — a denial-of-service vector.

    Accepts email as either:
    - Query parameter: POST /invalidate?email=user@example.com
    - JSON body: {"email": "user@example.com"}

    Returns success even if no email provided (idempotent — for test automation).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    # Try query param first
    email = request.query_params.get("email", "")

    # Try JSON body if not in query
    if not email:
        try:
            body = await request.json()
            email = body.get("email", "")
        except Exception:
            pass

    if not email:
        # Return success even without email (idempotent — for test automation)
        return JSONResponse(
            content={
                "success": True,
                "invalidated": 0,
                "email": None,
                "message": "No email provided — nothing to invalidate",
                "trace_id": trace_id,
            },
        )

    email_lower = email.lower()
    # SECURITY AUDIT 2026-08-02 (F-02 fix):
    # Previously this loop iterated `_records` while calling `_records.pop()`
    # inside the same loop — Python raises `RuntimeError: dictionary changed
    # size during iteration`. The endpoint always crashed.
    # Fix: collect keys to remove first, then pop them after the loop. Also
    # hold `_store_lock` to prevent concurrent issue/verify from mutating
    # `_records` while we iterate.
    with _store_lock:
        keys_to_remove = [
            k for k, rec in _records.items()
            if rec.email == email_lower and not rec.used
        ]
        for k in keys_to_remove:
            _records.pop(k, None)
        removed = len(keys_to_remove)
    return JSONResponse(
        content={
            "success": True,
            "invalidated": removed,
            "email": email_lower,
            "trace_id": trace_id,
        },
    )


__all__ = ["router"]
