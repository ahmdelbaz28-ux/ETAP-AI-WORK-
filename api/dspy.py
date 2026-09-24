"""
api/dspy.py — REST API endpoints for DSPy SLD Ingestion and Diagnostics.

Endpoints:
- POST /api/v1/dspy/ingest: Translate unverified SLD notes into SldIngestOutput
- POST /api/v1/dspy/diagnose: Synthesize diagnostic findings from study results

Guarded by:
- API key authentication (get_api_key)
- Feature flag enforcement (dspy_copilot)
- Strict input length caps (50,000 characters)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_api_key
from api.feature_flags import is_feature_enabled
from core_model.specs import StudyResult
from services.dspy_copilot.runtime import DspyIngestError, run_diagnose, run_ingest
from services.dspy_copilot.schemas import DiagnosticOutput, SldIngestOutput

router = APIRouter(prefix="/api/v1/dspy", tags=["dspy"])
MAX_PAYLOAD_LEN = 50000


class IngestRequest(BaseModel):
    sld_notes: str = Field(..., max_length=MAX_PAYLOAD_LEN, description="Raw unverified SLD text notes")


class DiagnoseRequest(BaseModel):
    study_data: dict[str, Any] = Field(..., description="StudyResult dictionary or native results")


@router.post(
    "/ingest",
    response_model=SldIngestOutput,
    summary="Ingest SLD notes into structured SystemSpec elements",
)
async def api_ingest_sld(
    payload: IngestRequest,
    _auth: Any = Depends(get_api_key),
) -> SldIngestOutput:
    """Translate raw single-line diagram descriptions into validated system elements."""
    if not is_feature_enabled("dspy_copilot"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSPy Copilot is currently disabled by feature flag ('dspy_copilot').",
        )

    if len(payload.sld_notes) > MAX_PAYLOAD_LEN:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="INPUT_TOO_LARGE: SLD notes exceed 50,000 character limit.",
        )

    try:
        return run_ingest(payload.sld_notes)
    except DspyIngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SLD ingestion failed: {exc}",
        ) from exc


@router.post(
    "/diagnose",
    response_model=DiagnosticOutput,
    summary="Run deterministic guards and AI diagnostic report",
)
async def api_diagnose_study(
    payload: DiagnoseRequest,
    _auth: Any = Depends(get_api_key),
) -> DiagnosticOutput:
    """Evaluate power-system study result against physical guards and synthesize diagnostic narrative."""
    if not is_feature_enabled("dspy_copilot"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSPy Copilot is currently disabled by feature flag ('dspy_copilot').",
        )

    # Validate study_data shape
    try:
        StudyResult.model_validate(payload.study_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid StudyResult payload: {exc}",
        ) from exc

    return run_diagnose(payload.study_data)
