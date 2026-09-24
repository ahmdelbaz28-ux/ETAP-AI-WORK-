"""
api/dspy.py — REST API endpoints for DSPy SLD Ingestion and Diagnostics.

Endpoints:
- POST /api/v1/dspy/ingest: Translate unverified SLD notes into SldIngestOutput (PROPOSAL only)
- POST /api/v1/dspy/diagnose: Synthesize diagnostic findings from study results

Security hardening (STEP 8):
- Both X-API-Key AND JWT Bearer (get_current_user_from_header) required.
- Non-empty tenant_id enforced on every request.
- Per-endpoint rate limits (ingest: 5/min, diagnose: 30/min).
- Strict feature flag — disabled in dev/test unless explicitly enabled.
- Generic stable error codes; never raw provider/Pydantic exception text.
- Blocking LM calls run in asyncio.to_thread (event-loop safe).
- Ingest returns a PROPOSAL only; never executes a study automatically.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from api.feature_flags import is_strict_feature_enabled
from api.rate_limit import limiter
from core_model.specs import StudyResult
from services.dspy_copilot.runtime import DspyIngestError, run_diagnose, run_ingest
from services.dspy_copilot.schemas import DiagnosticOutput, SldIngestOutput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dspy", tags=["dspy"])
MAX_PAYLOAD_LEN = 50_000


def _check_feature_enabled() -> None:
    """Raise 403 if dspy_copilot is not explicitly enabled (strict gate)."""
    if not is_strict_feature_enabled("dspy_copilot", default=False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FEATURE_DISABLED: DSPy Copilot is disabled by feature flag.",
        )


def _require_tenant(user: CurrentUser) -> None:
    """Raise 403 if tenant_id is missing or empty."""
    if not user.tenant_id or not user.tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TENANT_REQUIRED: Non-empty tenant_id is required for DSPy endpoints.",
        )


class IngestRequest(BaseModel):
    sld_notes: str = Field(
        ..., max_length=MAX_PAYLOAD_LEN, description="Raw unverified SLD text notes"
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
@limiter.limit("5/minute")
async def api_ingest_sld(
    request: Request,  # Required by SlowAPI rate limiter
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
    _require_tenant(current_user)

    # Validate payload length before deep processing
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
        # run_ingest is blocking (LM call) — run in thread pool
        return await asyncio.to_thread(run_ingest, payload.sld_notes)
    except DspyIngestError as exc:
        reason = str(exc)
        # Map known stable codes to stable HTTP responses; never leak provider text
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
    except Exception:
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
@limiter.limit("30/minute")
async def api_diagnose_study(
    request: Request,  # Required by SlowAPI rate limiter
    payload: DiagnoseRequest,
    _auth: Any = Depends(get_api_key),
    current_user: CurrentUser = Depends(get_current_user_from_header),
) -> DiagnosticOutput:
    """Evaluate a power-system study result against physical guards and synthesize a narrative.

    Deterministic guard findings are always authoritative.
    The LLM narrative is additive only and cannot override guard findings.
    """
    _check_feature_enabled()
    _require_tenant(current_user)

    # Validate study_data shape before deep processing (stable error, no payload echo)
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
        # run_diagnose is blocking (LM call) — run in thread pool
        return await asyncio.to_thread(run_diagnose, payload.study_data)
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

