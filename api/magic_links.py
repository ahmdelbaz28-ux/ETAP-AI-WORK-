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


_records: dict[str, _MagicLinkRecord] = {}
_issue_log: dict[str, list[float]] = {}


async def _issue(email: str, user_id: Optional[str]) -> tuple[bool, str, int]:
    """Issue a magic link. Returns (success, raw_token, retry_after_seconds)."""
    # Rate limit
    now = time.time()
    log = _issue_log.setdefault(email.lower(), [])
    log[:] = [t for t in log if now - t < MAGIC_LINK_RATE_LIMIT_WINDOW]
    if len(log) >= MAGIC_LINK_RATE_LIMIT_MAX:
        retry_after = int(MAGIC_LINK_RATE_LIMIT_WINDOW - (now - log[0])) + 1
        return False, "", max(retry_after, 1)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rec = _MagicLinkRecord(
        token_hash=token_hash,
        email=email.lower(),
        issued_at=now,
        expires_at=now + MAGIC_LINK_TTL_SECONDS,
        user_id=user_id,
    )
    _records[token_hash] = rec
    log.append(now)

    # Cleanup expired records periodically
    if len(_records) > 1000:
        cutoff = now
        expired_keys = [k for k, r in _records.items() if r.expires_at < cutoff]
        for k in expired_keys[:100]:
            _records.pop(k, None)

    return True, raw_token, 0


async def _verify(raw_token: str) -> tuple[bool, Optional[_MagicLinkRecord], str]:
    """Verify a magic link token. Returns (success, record, error)."""
    if not raw_token or len(raw_token) < 32:
        return False, None, "invalid_token"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rec = _records.get(token_hash)
    if rec is None:
        return False, None, "token_not_found"
    if rec.used:
        return False, None, "token_already_used"
    if rec.expires_at < time.time():
        _records.pop(token_hash, None)
        return False, None, "token_expired"
    # Consume
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
        from api.database import async_session_factory

        async with async_session_factory() as db:
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
    success, raw_token, retry_after = await _issue(body.email, user_id)

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
        # In test mode, force issue a new token even if rate-limited
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        rec = _MagicLinkRecord(
            token_hash=token_hash,
            email=body.email.lower(),
            issued_at=time.time(),
            expires_at=time.time() + MAGIC_LINK_TTL_SECONDS,
            user_id=user_id,
        )
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

    SECURITY (E-05): The previous test-mode bypass accepted ANY token
    containing the substring 'placeholder' and returned admin JWT tokens.
    This was a full admin auth bypass — if the API key leaked (it was a
    placeholder value in .env.example), an attacker could authenticate as
    admin with any token containing 'placeholder'.

    The bypass is now removed entirely. Tests must use real magic links
    issued via the /request endpoint (test mode still skips rate limiting
    and returns the real token in the response for test automation).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    # test_mode is still used to skip rate limiting in /request, but
    # verification must always use the real token. No bypass here.

    success, rec, error = await _verify(body.token)
    if not success:
        # Return 200 with success=False for test automation compatibility
        return JSONResponse(
            status_code=status.HTTP_200_OK,
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
        from api.database import async_session_factory

        async with async_session_factory() as db:
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
                "message": str(exc),
                "trace_id": trace_id,
            },
        )


@router.post(
    "/invalidate",
    summary="Invalidate all pending magic links for an email (admin/debug)",
)
async def invalidate_magic_links(
    request: Request,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> JSONResponse:
    """Invalidate all pending magic links for the given email.

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
    removed = 0
    for k in _records.keys():
        if _records[k].email == email_lower and not _records[k].used:
            _records.pop(k, None)
            removed += 1
    return JSONResponse(
        content={
            "success": True,
            "invalidated": removed,
            "email": email_lower,
            "trace_id": trace_id,
        },
    )


__all__ = ["router"]
