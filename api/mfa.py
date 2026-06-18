"""
MFA Endpoints API Router
=======================
Handles all multi-factor authentication endpoints.
Separated from main engineering service for better modularity.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/auth/mfa", tags=["mfa"])


@router.post("/totp/setup")
async def setup_totp(request: Request):
    """Set up TOTP-based MFA for a user."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        from security.mfa import TOTPProvider
        totp = TOTPProvider()
        secret = totp.generate_secret(user_id)
        qr_uri = totp.generate_qr_code(user_id, secret)
        totp.generate_backup_codes(user_id)

        return JSONResponse(content={
            "success": True,
            "data": {
                "qr_code_uri": qr_uri,
                # Note: secret and backup_codes are NOT exposed in the API response
                # to prevent credential leakage. They are stored server-side only.
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("totp_setup_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


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

        from security.mfa import TOTPProvider
        totp = TOTPProvider()
        is_valid = totp.verify_code(user_id, code)

        return JSONResponse(content={
            "success": True,
            "data": {
                "valid": is_valid,
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("totp_verify_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})