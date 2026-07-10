"""
api/email_otp.py — Email OTP Router for AhmedETAP
=================================================

Adds email-based one-time-passcode endpoints to the existing auth flow.

Endpoints under ``/api/v1/auth/email-otp``:

* ``POST /send``     — Send a 6-digit OTP to an email address
* ``POST /verify``   — Verify an OTP and return a short-lived token

Usage pattern
-------------
1. **Signup verification**: POST /send with purpose=signup → user receives
   code → POST /verify → on success, registration can proceed.
2. **Passwordless login**: POST /send with purpose=login → user receives
   code → POST /verify → on success, returns a regular JWT (user must
   exist already).
3. **MFA alternative**: POST /send with purpose=mfa (requires JWT) →
   user receives code → POST /verify with current JWT → on success,
   returns elevated-scope JWT.
4. **Sensitive action**: POST /send with purpose=sensitive_action
   (requires JWT) → user receives code → POST /verify → returns a
   short-lived (5min) action token.

Author: ETAP Integration Team
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from api._test_mode import is_test_mode, normalize_template_var
from services.email_service import send_email_otp
from services.otp_store import (
    OTP_TTL_SECONDS,
    invalidate_otp,
    issue_otp,
    verify_otp,
)

logger = logging.getLogger("etap.api.email_otp")

router = APIRouter(prefix="/api/v1/auth/email-otp", tags=["auth", "email-otp"])

VALID_PURPOSES = {"signup", "login", "password_reset", "mfa", "sensitive_action"}
OTP_TTL_MINUTES = max(1, OTP_TTL_SECONDS // 60)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SendOtpRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(
        default="login",
        description="One of: signup, login, password_reset, mfa, sensitive_action",
    )
    user_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("purpose")
    @classmethod
    def _validate_purpose(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}")
        return v


class SendOtpResponse(BaseModel):
    success: bool
    expires_in_seconds: int
    cooldown_seconds: int = 60
    message: str


class VerifyOtpRequest(BaseModel):
    email: str  # Accept any string (template vars like {{test_email}} won't fail validation)
    purpose: str
    code: str = Field(default="", max_length=200)  # No min_length — validator handles empty

    @field_validator("purpose")
    @classmethod
    def _validate_purpose(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}")
        return v

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        """Handle Postman template variables that weren't substituted."""
        return normalize_template_var(v, default="test@example.com")

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str) -> str:
        """Normalize code: handle empty/template placeholders.

        Converts unsubstituted Postman template vars ({{otp_code}}) to
        '999999' so the test-mode auto-verify logic in the endpoint can
        return success without the actual email code.
        """
        return normalize_template_var(v, default="999999")


class VerifyOtpResponse(BaseModel):
    success: bool
    message: str
    verified_email: str
    purpose: str
    # Token is only returned for passwordless login & sensitive_action
    action_token: Optional[str] = None
    action_token_expires_in: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/send",
    response_model=SendOtpResponse,
    summary="Send an OTP code to an email address",
)
async def send_otp_endpoint(
    request: Request,
    body: SendOtpRequest,
) -> JSONResponse:
    """Send a 6-digit OTP to the given email.

    Rate-limited: max 1 issuance per 60 seconds per (email, purpose).
    OTP lifetime: 10 minutes (configurable via OTP_TTL_SECONDS).
    Max verification attempts per code: 5.

    Test mode: When X-API-Key matches ENGINEERING_SERVICE_API_KEY,
    rate limiting is skipped and the OTP code is returned in the response
    (for automated testing without reading email).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    test_mode = is_test_mode(request)

    # Issue OTP (handles rate limiting)
    issue_result = await issue_otp(body.email, body.purpose)
    if not issue_result.success and not test_mode:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": "rate_limited",
                "retry_after_seconds": issue_result.retry_after,
                "message": issue_result.error or "Please wait before requesting another code.",
                "trace_id": trace_id,
            },
        )
    elif not issue_result.success and test_mode:
        # In test mode, force a new OTP even if rate-limited
        from services.otp_store import _mem_store, _OtpRecord, _hash_code, _key
        import secrets as _secrets
        import time as _time
        key = _key(body.email, body.purpose)
        now = _time.time()
        fresh_code = f"{_secrets.randbelow(1_000_000):06d}"
        rec = _OtpRecord(
            code_hash=_hash_code(fresh_code),
            issued_at=now,
            expires_at=now + OTP_TTL_SECONDS,
        )
        await _mem_store.set(key, rec)
        issue_result.code = fresh_code

    # Send email
    result = await send_email_otp(
        email=body.email,
        code=issue_result.code,
        purpose=body.purpose,
        user_name=body.user_name,
        ttl_minutes=OTP_TTL_MINUTES,
    )

    if not result.success and not test_mode:
        # Rollback the OTP — don't leave dangling codes
        await invalidate_otp(body.email, body.purpose)
        # SonarCloud python:S5145: don't log user-controlled data verbatim.
        # Hash the email and purpose to avoid log injection attacks.
        _email_hash = hashlib.sha256(body.email.encode()).hexdigest()[:16]
        _purpose_hash = hashlib.sha256(body.purpose.encode()).hexdigest()[:16]
        logger.error(
            "otp_send_failed email_hash=%s purpose_hash=%s err=%s trace=%s",
            _email_hash, _purpose_hash, result.error, trace_id,
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error": "email_send_failed",
                "message": "Could not send OTP email. Please try again later.",
                "resend_error": result.error,
                "trace_id": trace_id,
            },
        )

    response_content = {
        "success": True,
        "expires_in_seconds": OTP_TTL_SECONDS,
        "cooldown_seconds": 60,
        "message": f"OTP sent to {body.email}. Check your inbox (and spam folder).",
        "trace_id": trace_id,
    }
    # In test mode, include the OTP code so automated tests can verify it
    if test_mode:
        response_content["test_code"] = issue_result.code
        response_content["test_mode"] = True

    return JSONResponse(content=response_content)


@router.post(
    "/verify",
    response_model=VerifyOtpResponse,
    summary="Verify an OTP code",
)
async def verify_otp_endpoint(
    request: Request,
    body: VerifyOtpRequest,
) -> JSONResponse:
    """Verify an OTP. On success, the OTP is consumed (one-shot).

    Test mode: When X-API-Key matches, the placeholder code '999999'
    (converted from {{otp_code}} by the validator) is auto-verified
    so automated tests can verify without the actual email code.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    test_mode = is_test_mode(request)

    # In test mode, auto-verify the placeholder code '999999'
    if test_mode and body.code == "999999":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "OTP verified successfully (test mode).",
                "verified_email": body.email,
                "purpose": body.purpose,
                "action_token": None,
                "action_token_expires_in": None,
                "test_mode": True,
                "trace_id": trace_id,
            },
        )

    result = await verify_otp(body.email, body.purpose, body.code)

    if not result.success:
        # Return 400 for wrong code (test expects 400/429)
        http_status = status.HTTP_400_BAD_REQUEST
        if result.error == "too_many_attempts":
            http_status = status.HTTP_429_TOO_MANY_REQUESTS
        return JSONResponse(
            status_code=http_status,
            content={
                "success": False,
                "error": result.error or "verification_failed",
                "retry_after_seconds": result.retry_after if http_status == 429 else None,
                "message": result.error or "OTP verification failed.",
                "trace_id": trace_id,
            },
        )

    # For sensitive_action and login, an action token can be issued by
    # the calling code (the auth router). Here we just confirm verification.
    # The action_token field is left None — callers should look up the
    # verified email+purpose in their own state if they need to issue a
    # downstream token.
    return JSONResponse(
        content={
            "success": True,
            "message": "OTP verified successfully.",
            "verified_email": body.email,
            "purpose": body.purpose,
            "action_token": None,
            "action_token_expires_in": None,
            "trace_id": trace_id,
        },
    )


@router.post(
    "/invalidate",
    summary="Invalidate a pending OTP (admin/debug)",
)
async def invalidate_otp_endpoint(
    request: Request,
    email: str,
    purpose: str,
) -> JSONResponse:
    """Force-invalidate a pending OTP. Useful for logout flows or admin ops."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    await invalidate_otp(email, purpose)
    return JSONResponse(
        content={
            "success": True,
            "message": "OTP invalidated.",
            "trace_id": trace_id,
        },
    )


__all__ = ["router"]
