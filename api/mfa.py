"""
MFA Endpoints API Router
=======================
Handles all multi-factor authentication endpoints.
Separated from main engineering service for better modularity.
"""

import threading
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from api._messages import MSG_INTERNAL_ERROR
from api.dependencies import CurrentUser, get_current_user_from_header, require_role

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


@router.post("/totp/setup", dependencies=[Depends(require_role("admin", "super_admin"))])
async def setup_totp(request: Request, user: CurrentUser = Depends(get_current_user_from_header)):
    """Set up TOTP-based MFA for a user."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint

        # SECURITY: Only admin or the user themselves can set up MFA
        if user.role not in ("admin", "super_admin") and str(user.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="Cannot set up MFA for another user")

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
            status_code=500, content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
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
        with _mfa_lock:
            if user_id in _lockouts:
                if now - _lockouts[user_id] < _LOCKOUT_DURATION:
                    remaining = int(_LOCKOUT_DURATION - (now - _lockouts[user_id]))
                    raise HTTPException(
                        status_code=429,
                        detail="Too many failed MFA attempts. Please try again later.",
                    )
                else:
                    # Lockout expired — clear
                    del _lockouts[user_id]
                    _failed_attempts.pop(user_id, None)

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        is_valid = totp.verify_code(user_id, code)

        if not is_valid:
            # SECURITY: Track failed attempt (under lock)
            with _mfa_lock:
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
            status_code=500, content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )
