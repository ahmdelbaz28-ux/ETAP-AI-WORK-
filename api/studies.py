"""
Study Execution API Router
==========================
Handles all power system study execution endpoints.

Per the C3 refactoring: all execution logic lives in
``services/study_executor.py`` (``StudyExecutor`` deep module) and the
dispatch table in ``engine/dispatch.py``. This file is a **thin adapter**
that:

1. Defines the FastAPI router and endpoints.
2. Re-exports Spec/Request/Result classes for backward compatibility.
3. Re-exports ``_run_native_study``, ``_build_system_from_spec``,
   ``_to_jsonable``, ``pre_flight_check`` as thin wrappers around
   ``StudyExecutor`` so the 12 test files and ``api/validation.py`` that
   import them directly continue to work without modification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import get_api_key
from api.feature_flags import get_disabled_studies
from core.metrics import count_executions, track_skill_operation
from core_model.bus import Bus  # noqa: F401 — re-exported for backward compat
from core_model.generator import Generator  # noqa: F401
from core_model.line import Line  # noqa: F401
from core_model.load import Load  # noqa: F401
from core_model.specs import (  # noqa: F401 — re-exported for backward compat
    BusSpec,
    GeneratorSpec,
    LineSpec,
    LoadSpec,
    StudyRequest,
    StudyResult,
    SystemSpec,
    TransformerSpec,
)
from core_model.system import System  # noqa: F401
from core_model.transformer import Transformer  # noqa: F401
from services.study_executor import StudyExecutor

logger = logging.getLogger("engineering_service")

__all__ = [
    "BusSpec",
    "GeneratorSpec",
    "LineSpec",
    "LoadSpec",
    "StudyRequest",
    "StudyResult",
    "SystemSpec",
    "TransformerSpec",
    "Bus",
    "Generator",
    "Line",
    "Load",
    "System",
    "Transformer",
    "router",
    "get_study_types",
    "run_study",
    "_to_jsonable",
    "_build_system_from_spec",
    "_run_native_study",
    "_validate_study_request",
    "pre_flight_check",
    "StudyExecutor",
]

router = APIRouter(prefix="/api/v1/studies", tags=["studies"])


# ---------------------------------------------------------------------------
# Backward-compat wrappers — delegate to StudyExecutor
# ---------------------------------------------------------------------------


def _to_jsonable(obj: Any) -> Any:
    """Re-export: recursively convert numpy/engine types to JSON-native.

    Delegates to StudyExecutor._to_jsonable.
    """
    return StudyExecutor()._to_jsonable(obj)


def _build_system_from_spec(spec: SystemSpec) -> Any:
    """Re-export: build a Python System from a SystemSpec.

    Delegates to StudyExecutor._build_system_from_spec.
    """
    return StudyExecutor()._build_system_from_spec(spec)


def _run_native_study(
    study_type: str,
    system: Optional[Any],
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Re-export: dispatch a study to its handler via STUDY_DISPATCH.

    This is a synchronous convenience wrapper around
    StudyExecutor._dispatch. It preserves the exact function signature
    and validation behavior that the 12 test files and api/validation.py
    expect.
    """
    return StudyExecutor()._dispatch(study_type, system, parameters)


def _validate_study_request(payload: StudyRequest) -> None:
    """Re-export: validate feature flag, system requirement, pre-flight.

    Delegates to StudyExecutor._validate_request.
    Raises HTTPException on validation failure (preserving the
    original contract for any code that catches it).
    """
    try:
        StudyExecutor()._validate_request(payload)
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=str(ve),
        ) from ve


def pre_flight_check(system: dict) -> Optional[dict]:
    """Re-export: validate system configuration before running a study.

    Delegates to StudyExecutor._pre_flight_check.
    """
    return StudyExecutor()._pre_flight_check(system)


# ---------------------------------------------------------------------------
# API endpoints — thin adapters over StudyExecutor
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=StudyResult,
    responses={400: {"description": "Invalid study request parameters"}},
)
@count_executions(skill_name="study")
@track_skill_operation("study")
async def run_study(
    req: Request,
    payload: StudyRequest,
    _: str = Depends(get_api_key),
):
    """Execute a power system study.

    Delegates to StudyExecutor.execute which owns the full
    pipeline: validation -> cache -> dispatch -> scan -> risk -> serialize.
    """
    trace_id = getattr(req.state, "trace_id", "unknown")
    from core.bootstrap import _increment_counter

    _increment_counter("request")

    try:
        executor = StudyExecutor()
        result = await executor.execute(payload, trace_id=trace_id)
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        _increment_counter("failed")
        logger.warning(
            "study_run_validation_error study_type=%s error=%s",
            payload.study_type,
            str(ve),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=400, detail="Invalid study request parameters"
        ) from ve  # NOSONAR
    except Exception as e:
        _increment_counter("failed")
        logger.exception(
            "study_run_failed study_type=%s error=%s",
            payload.study_type,
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Study execution failed",
        ) from e  # NOSONAR


@router.get("/types")
async def get_study_types(request: Request):
    """Return the list of supported power system study types."""
    disabled = {d["study_type"] for d in get_disabled_studies()}
    from api.shared_handlers import STUDY_TYPES

    return {
        "study_types": [t for t in STUDY_TYPES if t not in disabled],
        "disabled_studies": get_disabled_studies(),
    }
