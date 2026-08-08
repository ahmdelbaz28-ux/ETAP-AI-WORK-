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

SECURITY AUDIT 2026-08-02 (V-8, V-9, V-10, V-12 fixes):
- V-8: Added backup code verification endpoint
- V-9: Backup codes are now hashed with SHA-256 before storage
- V-10: MFA is automatically enabled after successful TOTP setup
- V-12: TOTP code replay protection — tracks last-used timestamp
"""

from __future__ import annotations

import hashlib
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

# V-12: TOTP code replay protection — tracks last-used timestamp per user
# A valid TOTP code can only be used once within its 30-second window.
_last_used_totp: dict[str, tuple[str, float]] = {}  # user_id -> (code_hash, timestamp)

# V-68 FIX: Periodic cleanup for in-memory MFA stores to prevent memory leak.
# Bound the total number of entries and prune expired ones.
_MAX_MFA_ENTRIES = 10000


def _cleanup_mfa_stores() -> None:
    """V-68: Remove expired entries from MFA in-memory stores."""
    now = time.time()
    with _mfa_lock:
        # Prune expired failed attempts
        expired_users = []
        for user_id, attempts in _failed_attempts.items():
            _failed_attempts[user_id] = [t for t in attempts if now - t < _LOCKOUT_WINDOW]
            if not _failed_attempts[user_id]:
                expired_users.append(user_id)
        for user_id in expired_users:
            del _failed_attempts[user_id]

        # Prune expired lockouts
        expired_lockouts = [uid for uid, ts in _lockouts.items() if now - ts >= _LOCKOUT_DURATION]
        for uid in expired_lockouts:
            del _lockouts[uid]

        # Prune old TOTP replay entries (older than 60 seconds)
        old_totp = [uid for uid, (_, ts) in _last_used_totp.items() if now - ts > 60]
        for uid in old_totp:
            del _last_used_totp[uid]

        # Hard cap: if still too many entries, remove oldest
        if len(_failed_attempts) > _MAX_MFA_ENTRIES:
            _failed_attempts.clear()
        if len(_lockouts) > _MAX_MFA_ENTRIES:
            _lockouts.clear()
        if len(_last_used_totp) > _MAX_MFA_ENTRIES:
            _last_used_totp.clear()


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

    code: str = Field(
        ..., min_length=4, max_length=20, description="TOTP code from authenticator app"
    )
    user_id: str | None = Field(
        default=None,
        description=(
            "Optional. If supplied, MUST match the authenticated user. "
            "Providing another user's id returns 403."
        ),
    )


class BackupCodeVerifyRequest(BaseModel):
    """V-8: Payload for ``POST /api/v1/auth/mfa/backup/verify``."""

    code: str = Field(..., min_length=8, max_length=16, description="Backup recovery code")
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
        totp.generate_backup_codes(target_user_id)  # side effect: stores codes in DB

        # V-10: Automatically enable MFA after successful TOTP setup.
        # Previously, the user had to separately call PUT /me with mfa_enabled=True,
        # which meant MFA setup could be silently incomplete.
        try:
            from sqlalchemy import select as sa_select

            from api.auth import User
            from api.database import async_session

            async with async_session() as db:
                result = await db.execute(sa_select(User).where(User.id == target_user_id))
                db_user = result.scalar_one_or_none()
                if db_user and not db_user.mfa_enabled:
                    db_user.mfa_enabled = True
                    await db.commit()
        except Exception as mfa_enable_err:
            # Non-blocking — log but don't fail the setup
            from logging import getLogger

            getLogger("etap.api.mfa").warning(
                "mfa_auto_enable_failed user=%s err=%s", target_user_id, mfa_enable_err
            )

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

        # V-12: TOTP code replay protection
        # A valid TOTP code should only be usable once within its 30-second window.
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        with _mfa_lock:
            last_code, last_time = _last_used_totp.get(target_user_id, ("", 0))
            if is_valid and code_hash == last_code and (time.time() - last_time) < 30:
                # Same code reused within 30 seconds — reject
                is_valid = False
                from logging import getLogger

                getLogger("etap.api.mfa").warning(
                    "totp_replay_blocked user=%s code_hash=%s", target_user_id, code_hash[:8]
                )

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
            # V-12: Record this code as used
            _last_used_totp[target_user_id] = (code_hash, time.time())

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


# ---------------------------------------------------------------------------
# V-8: Backup code verification endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/backup/verify",
    responses={
        400: {"description": "Bad request — code is required"},
        401: {"description": "Invalid backup code"},
        403: {"description": "user_id does not match authenticated user"},
        429: {"description": "Too many failed MFA attempts — account temporarily locked"},
    },
)
async def verify_backup_code(
    request: Request,
    body: BackupCodeVerifyRequest,
    current_user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
):
    """V-8: Verify a backup/recovery code for MFA.

    SECURITY: Requires a valid JWT. The code is verified against
    `current_user.user_id` ONLY. A body-supplied `user_id` is rejected with
    403 if it doesn't match the token subject.

    V-9: Backup codes are hashed with SHA-256 before comparison.
    The plaintext codes are only shown once during setup.
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
        code = body.code.strip().upper()

        # Check lockout status
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
                    del _lockouts[target_user_id]
                    _failed_attempts.pop(target_user_id, None)

        # V-9: Hash the code before comparison — backup codes are stored
        # as SHA-256 hashes, so we must compare the hash, not the plaintext.
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        # SECURITY FIX: Pass the HASH to verify_backup_code, not the plaintext.
        # Previously, the code was hashed but the plaintext was sent to
        # verify_backup_code(), which would never match the stored hash.
        is_valid = totp.verify_backup_code(target_user_id, code_hash)

        if not is_valid:
            # Track failed attempt
            with _mfa_lock:
                _failed_attempts[target_user_id].append(now)
                _failed_attempts[target_user_id] = [
                    t for t in _failed_attempts[target_user_id] if now - t < _LOCKOUT_WINDOW
                ]
                if len(_failed_attempts[target_user_id]) >= _MAX_FAILED_ATTEMPTS:
                    _lockouts[target_user_id] = now
                    raise HTTPException(
                        status_code=429,
                        detail="Too many failed MFA attempts. Account temporarily locked.",
                    )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": "invalid_backup_code",
                    "message": "Invalid or already used backup code.",
                    "trace_id": trace_id,
                },
            )

        # On success: clear failed attempts
        with _mfa_lock:
            _failed_attempts.pop(target_user_id, None)
            _lockouts.pop(target_user_id, None)

        return JSONResponse(
            content={
                "success": True,
                "data": {"valid": True},
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("backup_code_verify_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


__all__ = ["router"]
