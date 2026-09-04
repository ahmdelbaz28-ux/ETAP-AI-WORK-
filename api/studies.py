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
from typing_extensions import Annotated

from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_optional_current_user_from_header,
)
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
            detail="Invalid study request parameters",
        ) from ve


def pre_flight_check(system: dict) -> Optional[dict]:
    """Re-export: validate system configuration before running a study.

    Delegates to StudyExecutor._pre_flight_check.
    """
    return StudyExecutor()._pre_flight_check(system)


# ---------------------------------------------------------------------------
# API endpoints — thin adapters over StudyExecutor
# ---------------------------------------------------------------------------


async def _persist_study_result(
    req: Request,
    payload: StudyRequest,
    result: StudyResult,
    trace_id: str,
    user: Optional[CurrentUser] = None,
) -> None:
    """Persist a successful study summary into the P5 ResultStore.

    The tenant_id is derived from the authenticated request context only
    (``request.state.tenant_id``, set by the JWT TenantMiddleware) — never
    from the request body. ``created_by`` is the authenticated user id from
    the validated JWT context (``CurrentUser.user_id``); it is ``None`` for
    service-to-service API-key callers, which have no user identity. Identity
    is NEVER read from the request body and NEVER fabricated. Failures are
    logged and swallowed so study execution semantics are never altered by
    result persistence.
    """
    tenant_id = (getattr(req.state, "tenant_id", "") or "").strip()
    created_by = (user.user_id if user is not None else "").strip() or None
    try:
        from api.results_store import persist_study_result

        result_id = await persist_study_result(
            tenant_id=tenant_id or "default",
            project_id=None,
            created_by=created_by,
            summary_json={
                "study_type": payload.study_type,
                "status": "success",
                "provider": result.provider or "native",
                "data": result.data,
                "warnings": result.warnings,
                "errors": result.errors,
                "execution_time_sec": result.execution_time_sec,
                "trace_id": trace_id,
            },
        )
        if result_id:
            result.result_id = result_id
    except Exception:  # pragma: no cover - resilience guard
        logger.warning(
            "study_result_persist_failed study_type=%s — result_id omitted",
            payload.study_type,
            extra={"trace_id": trace_id},
        )


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
    _: Annotated[str, Depends(get_api_key)],
    user: Annotated[Optional[CurrentUser], Depends(get_optional_current_user_from_header)],
):
    """Execute a power system study.

    Delegates to StudyExecutor.execute which owns the full
    pipeline: validation -> cache -> dispatch -> scan -> risk -> serialize.

    ``user`` is the optional authenticated ``CurrentUser`` (JWT context);
    it is used ONLY to stamp ``created_by`` on the persisted result. It is
    ``None`` for API-key-only callers — identity is never taken from the
    request body.
    """
    trace_id = getattr(req.state, "trace_id", "unknown")
    from core.bootstrap import _increment_counter

    _increment_counter("request")

    try:
        executor = StudyExecutor()
        result = await executor.execute(payload, trace_id=trace_id)
        # P5 ResultStore: persist the successful study summary and surface the
        # new result_id on the response. The tenant comes ONLY from the
        # authenticated request context (JWT TenantMiddleware) — never from the
        # request body. ``created_by`` comes ONLY from the authenticated user
        # context (validated JWT -> CurrentUser). A persistence failure degrades
        # gracefully: the study result is not failed, the field is simply left
        # unset.
        if result and getattr(result, "success", False):
            await _persist_study_result(req, payload, result, trace_id, user)
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
