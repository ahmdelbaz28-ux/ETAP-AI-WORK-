"""
api/dspy.py — REST API endpoints for DSPy SLD Ingestion and Diagnostics.

Endpoints:
- POST /api/v1/dspy/ingest: Translate unverified SLD notes into SldIngestOutput (PROPOSAL only)
- POST /api/v1/dspy/diagnose: Synthesize diagnostic findings from study results

Security hardening (STEP 8):
- Both X-API-Key AND JWT Bearer (get_current_user_from_header) required.
- Non-empty tenant_id enforced on every request (HTTP 403 TENANT_REQUIRED).
- Role restricted to 'engineer' or 'admin' only (HTTP 403 INSUFFICIENT_ROLE).
- PRIVACY_MODE gate: external LLM denied if active (HTTP 403 PRIVACY_MODE_ACTIVE).
- Compound user/tenant/IP rate limiting key (ingest: 5/min, diagnose: 30/min).
- Strict feature flag — disabled in dev/test unless explicitly enabled.
- Input cap 50,000 characters enforced before deep processing (HTTP 413 INPUT_TOO_LARGE).
- Generic stable error codes; never raw provider/Pydantic exception text.
- Blocking LM calls run in asyncio.to_thread (event-loop safe).
- Ingest returns a PROPOSAL only; never executes a study automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from api.feature_flags import is_strict_feature_enabled
from api.rate_limit import get_client_ip, limiter
from core_model.specs import StudyResult
from services.dspy_copilot.runtime import DspyIngestError, run_diagnose, run_ingest
from services.dspy_copilot.schemas import DiagnosticOutput, SldIngestOutput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dspy", tags=["dspy"])
MAX_PAYLOAD_LEN = 50_000


def get_dspy_rate_limit_key(request: Request) -> str:
    """Compound rate limiting key for DSPy endpoints: user token/tenant + client IP."""
    client_ip = get_client_ip(request)
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            return f"tok:{token_hash}:{client_ip}"
    tenant_header = request.headers.get("x-tenant-id", "").strip()
    if tenant_header:
        return f"ten:{tenant_header}:{client_ip}"
    return f"ip:{client_ip}"


def _check_feature_enabled() -> None:
    """Raise 403 if dspy_copilot is not explicitly enabled (strict gate)."""
    if not is_strict_feature_enabled("dspy_copilot", default=False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FEATURE_DISABLED: DSPy Copilot is disabled by feature flag.",
        )


def _check_privacy_mode() -> None:
    """Raise 403 if PRIVACY_MODE is enabled (external LLM prohibited)."""
    if os.environ.get("PRIVACY_MODE", "false").lower() in ("true", "1", "yes", "on"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PRIVACY_MODE_ACTIVE: External LLM operations are prohibited when PRIVACY_MODE is enabled.",
        )


def _require_tenant(user: CurrentUser) -> None:
    """Raise 403 if tenant_id is missing or empty."""
    if not user.tenant_id or not user.tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TENANT_REQUIRED: Non-empty tenant_id is required for DSPy endpoints.",
        )


def _require_role(user: CurrentUser) -> None:
    """Raise 403 if user role is not engineer or admin."""
    if user.role not in ("engineer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INSUFFICIENT_ROLE: Only 'engineer' or 'admin' roles may access DSPy copilot.",
        )


class IngestRequest(BaseModel):
    sld_notes: str = Field(
        ..., description="Raw unverified SLD text notes"
    )


class DiagnoseRequest(BaseModel):
    study_data: dict[str, Any] = Field(
        ..., description="StudyResult dictionary or native results"
    )


@router.post(
    "/ingest",
    response_model=SldIngestOutput,
    summary="Ingest SLD notes into a structured PROPOSAL (not executed automatically)",
)
@limiter.limit("5/minute", key_func=get_dspy_rate_limit_key)
async def api_ingest_sld(
    request: Request,
    payload: IngestRequest,
    _auth: Any = Depends(get_api_key),
    current_user: CurrentUser = Depends(get_current_user_from_header),
) -> SldIngestOutput:
    """Translate raw SLD descriptions into validated system element PROPOSALS.

    The returned SldIngestOutput is a PROPOSAL ONLY.
    It is NOT automatically executed. A qualified engineer must review and
    approve it before using it in any study execution.
    """
    _check_feature_enabled()
    _check_privacy_mode()
    _require_tenant(current_user)
    _require_role(current_user)

    if len(payload.sld_notes) > MAX_PAYLOAD_LEN:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="INPUT_TOO_LARGE: SLD notes exceed 50,000 character limit.",
        )

    logger.info(
        "dspy_ingest user=%s tenant=%s len=%d",
        current_user.user_id,
        current_user.tenant_id,
        len(payload.sld_notes),
    )

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, run_ingest, payload.sld_notes)
    except Exception as exc:
        if isinstance(exc, DspyIngestError) or type(exc).__name__ == "DspyIngestError":
            reason = str(exc)
            if "flag_disabled" in reason:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="FEATURE_DISABLED",
                ) from exc
            if "INPUT_TOO_LARGE" in reason:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="INPUT_TOO_LARGE",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="INGEST_FAILED: SLD ingestion could not produce a valid proposal.",
            ) from exc
        logger.exception(
            "dspy_ingest_error user=%s tenant=%s",
            current_user.user_id,
            current_user.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTERNAL_ERROR",
        )


@router.post(
    "/diagnose",
    response_model=DiagnosticOutput,
    summary="Run deterministic guards and AI diagnostic report",
)
@limiter.limit("30/minute", key_func=get_dspy_rate_limit_key)
async def api_diagnose_study(
    request: Request,
    payload: DiagnoseRequest,
    _auth: Any = Depends(get_api_key),
    current_user: CurrentUser = Depends(get_current_user_from_header),
) -> DiagnosticOutput:
    """Evaluate a power-system study result against physical guards and synthesize a narrative.

    Deterministic guard findings are always authoritative.
    The LLM narrative is additive only and cannot override guard findings.
    """
    _check_feature_enabled()
    _check_privacy_mode()
    _require_tenant(current_user)
    _require_role(current_user)

    # 1. Enforce 50,000 char cap before deep processing (HTTP 413)
    raw_json = json.dumps(payload.study_data)
    if len(raw_json) > MAX_PAYLOAD_LEN:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="INPUT_TOO_LARGE: Study results payload exceeds 50,000 character limit.",
        )

    # 2. Validate study_data shape before deep processing (stable error, no payload echo)
    try:
        StudyResult.model_validate(payload.study_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="INVALID_STUDY_RESULT: Payload does not match StudyResult schema.",
        )

    logger.info(
        "dspy_diagnose user=%s tenant=%s",
        current_user.user_id,
        current_user.tenant_id,
    )

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, run_diagnose, payload.study_data)
    except Exception:
        logger.exception(
            "dspy_diagnose_error user=%s tenant=%s",
            current_user.user_id,
            current_user.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTERNAL_ERROR",
        )
