"""
MFA Endpoints API Router
=======================
Handles all multi-factor authentication endpoints.

SECURITY AUDIT 2026-08-02 (F-04, F-05 fix — CRITICAL):
The previous version of this file had two critical vulnerabilities:

1. (F-04) `/totp/setup` and `/totp/verify` accepted `user_id` from the
   request body with NO authentication check. Any anonymous internet
   user could call `setup` with a victim's `user_id`, overwrite the
   victim's TOTP secret, then call `verify` with a code from their own
   authenticator app — full account takeover.

2. (F-05) `verify_totp` returned `{"success": True, "data": {"valid": False}}`
   on a failed verification (when the lockout threshold wasn't met).
   Clients that only inspect the `success` field treated failed MFA as
   successful MFA — silent MFA bypass.

Both are fixed below:
- Endpoints now require a valid JWT via `get_current_user_from_header`.
- The authenticated user's `user_id` is used; body-supplied `user_id`
  is REJECTED if it doesn't match the token subject.
- `verify_totp` returns `success: False` + HTTP 401 when `is_valid` is
  False, and only returns `success: True` when the code is valid.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api._messages import MSG_INTERNAL_ERROR
from api.dependencies import CurrentUser, get_current_user_from_header

router = APIRouter(prefix="/api/v1/auth/mfa", tags=["mfa"])

# SECURITY AUDIT 2026-07-26 — S-24: Brute-force protection for TOTP verify.
# Tracks failed attempts per user_id. After MAX_FAILED_ATTEMPTS within
# LOCKOUT_WINDOW seconds, the endpoint rejects further attempts.
# Uses threading.Lock for thread safety on shared state.
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_WINDOW = 300  # seconds (5 minutes)
_LOCKOUT_DURATION = 900  # seconds (15 minutes)
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}
_mfa_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Schemas (F-04 fix: explicit request bodies, no free-form user_id)
# ---------------------------------------------------------------------------


class TotpSetupRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/mfa/totp/setup``.

    Note: `user_id` is NOT accepted from the body. The authenticated user
    from the JWT is used. If a `user_id` is supplied, it MUST match the
    authenticated user or the request is rejected with 403.
    """

    user_id: str | None = Field(
        default=None,
        description=(
            "Optional. If supplied, MUST match the authenticated user. "
            "Providing another user's id returns 403."
        ),
    )


class TotpVerifyRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/mfa/totp/verify``."""

    code: str = Field(..., min_length=4, max_length=20, description="TOTP code from authenticator app")
    user_id: str | None = Field(
        default=None,
        description=(
            "Optional. If supplied, MUST match the authenticated user. "
            "Providing another user's id returns 403."
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/totp/setup")
async def setup_totp(
    request: Request,
    body: TotpSetupRequest = Body(default_factory=TotpSetupRequest),
    current_user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
):
    """Set up TOTP-based MFA for the authenticated user.

    SECURITY (F-04 fix): Requires a valid JWT. The TOTP secret is generated
    for `current_user.user_id` ONLY. A body-supplied `user_id` is rejected
    with 403 if it doesn't match the token subject.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        # F-04 fix: reject cross-user setup attempts
        if body.user_id is not None and body.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot set up MFA for a different user. The user_id in the body must match the authenticated user.",
            )

        target_user_id = current_user.user_id

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        secret = totp.generate_secret(target_user_id)
        qr_uri = totp.generate_qr_code(target_user_id, secret)
        totp.generate_backup_codes(target_user_id)

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "qr_code_uri": qr_uri,
                    # Note: secret and backup_codes are NOT exposed in the API response
                    # to prevent credential leakage. They are stored server-side only.
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("totp_setup_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post(
    "/totp/verify",
    responses={
        400: {"description": "Bad request — code is required"},
        401: {"description": "Invalid TOTP code"},
        403: {"description": "user_id does not match authenticated user"},
        429: {"description": "Too many failed MFA attempts — account temporarily locked"},
    },
)
async def verify_totp(
    request: Request,
    body: TotpVerifyRequest,
    current_user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
):
    """Verify a TOTP code for MFA.

    SECURITY (F-04 fix): Requires a valid JWT. The code is verified against
    `current_user.user_id` ONLY. A body-supplied `user_id` is rejected with
    403 if it doesn't match the token subject.

    SECURITY (F-05 fix): On invalid code, returns HTTP 401 with
    `success: False`. The previous version returned HTTP 200 with
    `success: True, data.valid: False` which caused silent MFA bypass
    for clients that only checked the `success` field.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        # F-04 fix: reject cross-user verification attempts
        if body.user_id is not None and body.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot verify MFA for a different user. The user_id in the body must match the authenticated user.",
            )

        target_user_id = current_user.user_id
        code = body.code

        # SECURITY AUDIT 2026-07-26 — S-24: Check lockout status.
        now = time.time()
        with _mfa_lock:
            if target_user_id in _lockouts:
                if now - _lockouts[target_user_id] < _LOCKOUT_DURATION:
                    remaining = int(_LOCKOUT_DURATION - (now - _lockouts[target_user_id]))
                    raise HTTPException(
                        status_code=429,
                        detail=f"Account locked due to too many failed attempts. Try again in {remaining}s.",
                    )
                else:
                    # Lockout expired — clear
                    del _lockouts[target_user_id]
                    _failed_attempts.pop(target_user_id, None)

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        is_valid = totp.verify_code(target_user_id, code)

        if not is_valid:
            # SECURITY: Track failed attempt (under lock)
            with _mfa_lock:
                _failed_attempts[target_user_id].append(now)
                # Prune old attempts outside the window
                _failed_attempts[target_user_id] = [
                    t for t in _failed_attempts[target_user_id] if now - t < _LOCKOUT_WINDOW
                ]
                if len(_failed_attempts[target_user_id]) >= _MAX_FAILED_ATTEMPTS:
                    _lockouts[target_user_id] = now
                    raise HTTPException(
                        status_code=429,
                        detail="Too many failed MFA attempts. Account temporarily locked.",
                    )
            # F-05 fix: return 401 + success=False on invalid code.
            # Previously returned 200 + success=True + valid=False which
            # caused silent MFA bypass for clients checking only `success`.
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": "invalid_code",
                    "message": "Invalid TOTP code.",
                    "data": {"valid": False},
                    "trace_id": trace_id,
                },
            )

        # On success: clear any prior failed attempts for this user
        with _mfa_lock:
            _failed_attempts.pop(target_user_id, None)
            _lockouts.pop(target_user_id, None)

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "valid": True,
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("totp_verify_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


__all__ = ["router"]
