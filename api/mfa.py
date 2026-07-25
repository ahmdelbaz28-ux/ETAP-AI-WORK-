"""
MFA Endpoints API Router
=======================
Handles all multi-factor authentication endpoints.
Separated from main engineering service for better modularity.
"""

import time
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/auth/mfa", tags=["mfa"])

# SECURITY AUDIT 2026-07-26 — S-24: Brute-force protection for TOTP verify.
# Tracks failed attempts per user_id. After MAX_FAILED_ATTEMPTS within
# LOCKOUT_WINDOW seconds, the endpoint rejects further attempts.
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_WINDOW = 300  # seconds (5 minutes)
_LOCKOUT_DURATION = 900  # seconds (15 minutes)
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}


@router.post("/totp/setup")
async def setup_totp(request: Request):
    """Set up TOTP-based MFA for a user."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        secret = totp.generate_secret(user_id)
        qr_uri = totp.generate_qr_code(user_id, secret)
        totp.generate_backup_codes(user_id)

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
            status_code=500, content={"success": False, "errors": ["Internal server error"], "trace_id": trace_id},
        )


@router.post("/totp/verify")
async def verify_totp(request: Request):
    """Verify a TOTP code for MFA."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        code = body.get("code")

        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not code:
            raise HTTPException(status_code=400, detail="code is required")

        # SECURITY AUDIT 2026-07-26 — S-24: Check lockout status.
        now = time.time()
        if user_id in _lockouts:
            if now - _lockouts[user_id] < _LOCKOUT_DURATION:
                remaining = int(_LOCKOUT_DURATION - (now - _lockouts[user_id]))
                raise HTTPException(
                    status_code=429,
                    detail=f"Account locked due to too many failed attempts. Try again in {remaining}s.",
                )
            else:
                # Lockout expired — clear
                del _lockouts[user_id]
                _failed_attempts.pop(user_id, None)

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        is_valid = totp.verify_code(user_id, code)

        if not is_valid:
            # SECURITY: Track failed attempt
            _failed_attempts[user_id].append(now)
            # Prune old attempts outside the window
            _failed_attempts[user_id] = [
                t for t in _failed_attempts[user_id] if now - t < _LOCKOUT_WINDOW
            ]
            if len(_failed_attempts[user_id]) >= _MAX_FAILED_ATTEMPTS:
                _lockouts[user_id] = now
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed MFA attempts. Account temporarily locked.",
                )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "valid": is_valid,
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
            status_code=500, content={"success": False, "errors": ["Internal server error"], "trace_id": trace_id},
        )
