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

import hashlib
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from api.database import get_db
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_optional_current_user_from_header,
)
from api.environment import auth_disabled_allowed, is_production_environment
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
from services.execution_orchestrator import get_execution_orchestrator
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
    "get_execution_orchestrator",
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
    """[LEGACY COMPATIBILITY WRAPPER]
    Synchronous compatibility shim delegating to StudyExecutor._dispatch.

    WARNING: This wrapper exists strictly for backward-compatibility with
    legacy unit tests. Production execution paths MUST NOT call this directly;
    all production requests must route through ExecutionOrchestrator via
    StudyExecutor conforming to the Canonical Execution Flow.
    """
    import warnings
    warnings.warn(
        "api.studies._run_native_study is a quarantined legacy compatibility wrapper. "
        "Production paths must use ExecutionOrchestrator.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning(
        "[LEGACY_QUARANTINE] api.studies._run_native_study called for '%s'.",
        study_type,
    )
    raw_res = StudyExecutor()._dispatch(study_type, system, parameters)
    if isinstance(raw_res, dict):
        raw_res["execution_path"] = "LEGACY_NON_AUTHORITATIVE"
        raw_res["authoritative"] = False
    return raw_res


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


def _extract_trusted_identity(
    req: Request | None,
    user: Optional[CurrentUser],
    api_key: str = "",
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> tuple[str, str, str]:
    """Extract authenticated caller identity fail-closed.
    Never trusts raw X-User-* or X-Tenant-ID headers without validated credential.
    """
    if user is not None and getattr(user, "user_id", None):
        uid = str(user.user_id).strip()
        tid = str(
            user.tenant_id
            or (getattr(req.state, "tenant_id", "") if req and hasattr(req, "state") else "")
            or ""
        ).strip()
        if not tid or tid.lower() in ("default", "none", "null"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trusted tenant identity required for authenticated user execution",
            )
        urole = str(getattr(user, "role", "engineer"))
        return uid, tid, urole

    if api_key:
        key_hash = hashlib.sha256(str(api_key).encode("utf-8")).hexdigest()[:12]
        uid = user_id or f"service_principal:{key_hash}"
        tid = (
            tenant_id
            or (getattr(req.state, "tenant_id", "") if req and hasattr(req, "state") else "")
            or (req.headers.get("x-tenant-id") if req and hasattr(req, "headers") else "")
            or f"service_tenant_{key_hash[:8]}"
        ).strip()
        urole = "service_principal"
        return uid, tid, urole

    if user_id and tenant_id and (req is None or getattr(req, "state", None) is None):
        return str(user_id).strip(), str(tenant_id).strip(), "engineer"

    if auth_disabled_allowed() or not is_production_environment():
        return (
            user_id or "service_principal:dev_test",
            tenant_id
            or (getattr(req.state, "tenant_id", "") if req and hasattr(req, "state") else "")
            or "service_tenant_dev",
            "engineer",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: valid JWT user session or trusted API-key service identity mandatory",
    )


@router.post(
    "/run",
    response_model=StudyResult,
    responses={400: {"description": "Invalid study request parameters"}},
)
@count_executions(skill_name="study")
@track_skill_operation("study")
async def run_study(
    req: Request = None,  # type: ignore
    payload: StudyRequest = None,  # type: ignore
    _: Annotated[str, Depends(get_api_key)] = "",
    user: Annotated[Optional[CurrentUser], Depends(get_optional_current_user_from_header)] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """Execute a power system study.

    Delegates to ExecutionOrchestrator which owns the full
    pipeline: validation -> cache -> dispatch -> scan -> risk -> serialize.
    """
    if not isinstance(req, Request):
        if req is not None:
            payload = req if isinstance(req, StudyRequest) else StudyRequest.model_validate(req)
        req = None  # type: ignore

    if isinstance(payload, dict):
        payload = StudyRequest.model_validate(payload)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing study request payload",
        )

    trace_id = (
        getattr(req.state, "trace_id", "unknown")
        if req is not None and hasattr(req, "state")
        else "unknown"
    )
    from core.bootstrap import _increment_counter

    _increment_counter("request")

    try:
        user_id, tenant_id, user_role = _extract_trusted_identity(
            req, user, _, user_id, tenant_id
        )

        # Route execution strictly through Canonical Execution Orchestrator
        # (Semantic cache governance is owned by the orchestrator at Step 10b)
        from services.execution_request import ExecutionRequest

        exec_request = ExecutionRequest.from_study_request(
            study_request=payload,
            user_id=user_id,
            tenant_id=tenant_id,
            user_role=user_role,
            trace_id=trace_id,
        )
        exec_request.user_role = user_role
        exec_request.metadata["role"] = user_role

        orchestrator = get_execution_orchestrator()
        canonical_res = await orchestrator.execute(exec_request)

        if canonical_res.status == "rejected":
            err_msg = (
                canonical_res.errors[0]
                if canonical_res.errors
                else "Invalid study request parameters"
            )
            if "AUTHENTICATION_REQUIRED" in err_msg or "TENANT_VALIDATION_FAILED" in err_msg:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)
            if "AUTHORIZATION_DENIED" in err_msg or "APPROVAL_REQUIRED" in err_msg or "MAKER_CHECKER_VIOLATION" in err_msg:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
            if "SCHEMA_VALIDATION_FAILED" in err_msg or "missing mandatory parameters" in err_msg.lower():
                detail_str = (
                    err_msg
                    if "invalid" in err_msg.lower()
                    else f"Invalid study request parameters: {err_msg}"
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail_str)
            if "MISSING_REQUIRED_SYSTEM_DATA" in err_msg or "SYSTEM_MODEL_REQUIRED" in err_msg:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)
            detail_str = (
                err_msg
                if "invalid" in err_msg.lower()
                else f"Invalid study request parameters: {err_msg}"
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail_str)

        if not canonical_res.success and canonical_res.errors:
            err_msg = canonical_res.errors[0]
            err_lower = err_msg.lower()
            if any(k in err_lower for k in (
                "validation error", "value error", "duplicate load",
                "not found in system buses", "requires system components",
                "missing_required_system_data", "unit normalization failed",
            )) or ("bus_id" in err_lower and "not found" in err_lower):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)

        result = canonical_res.to_study_result()
        # P5 ResultStore: persist the successful study summary and surface the
        # new result_id on the response.
        if req is not None and result and getattr(result, "success", False):
            await _persist_study_result(req, payload, result, trace_id, user)
        return result

    except HTTPException:
        raise
    except ValidationError as pve:
        _increment_counter("failed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {pve.errors() if hasattr(pve, 'errors') else str(pve)}",
        ) from pve
    except ValueError as ve:
        _increment_counter("failed")
        logger.warning(
            "study_run_validation_error study_type=%s error=%s",
            getattr(payload, "study_type", "unknown") if payload else "unknown",
            str(ve),
            extra={"trace_id": trace_id},
        )
        msg = str(ve)
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if any(k in msg.lower() for k in ("bus_id", "fault_type", "system spec", "duplicate load", "not found"))
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code, detail=f"Invalid study request parameters: {msg}"
        ) from ve
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


def get_celery_components() -> tuple[Any | None, Any | None, Any | None]:
    """Lazy load Celery components for async study tasks."""
    try:
        from celery.result import AsyncResult

        from worker.celery_app import app as celery_app
        from worker.tasks import execute_engineering_study_task

        return (AsyncResult, execute_engineering_study_task, celery_app)
    except ImportError as e:
        logger.warning("Celery not available: %s", e)
        return (None, None, None)


def _extract_caller_identity(
    request: Request,
    user: Optional[CurrentUser],
) -> tuple[str, str, str]:
    """Extract authoritative caller identity and tenant. Never trust raw unverified headers."""
    if user is not None:
        user_id = str(user.user_id).strip()
        tenant_id = str(user.tenant_id).strip() or "default"
        role = str(user.role).strip() or "engineer"
        return user_id, tenant_id, role

    # Service-principal authentication via valid API key
    req_state = getattr(request, "state", None)
    tenant_id = (getattr(req_state, "tenant_id", "") if req_state else "") or "service_tenant_async"
    user_id = (getattr(req_state, "user_id", "") if req_state else "") or "service_principal:api_caller"
    user_role = (getattr(req_state, "user_role", "") if req_state else "") or "admin"
    return user_id, tenant_id, user_role


@router.post(
    "/run_async",
    responses={
        200: {"description": "Task accepted for async processing"},
        202: {"description": "Task accepted for async processing"},
        400: {"description": "Invalid study request parameters"},
        401: {"description": "Unauthorized — missing or invalid credentials"},
        503: {"description": "Celery is not available for async processing"},
    },
)
async def run_study_async(
    payload: StudyRequest,
    req: Request,
    _: Annotated[str, Depends(get_api_key)],
    user: Annotated[Optional[CurrentUser], Depends(get_optional_current_user_from_header)],
) -> dict[str, Any]:
    """Execute an engineering study asynchronously using Celery with durable task ownership."""
    _validate_study_request(payload)

    _, execute_engineering_study_task, _ = get_celery_components()
    if not execute_engineering_study_task:
        raise HTTPException(
            status_code=503, detail="Celery is not available for async processing"
        )

    user_id, tenant_id, user_role = _extract_caller_identity(req, user)
    trace_id = getattr(req.state, "trace_id", None) or str(uuid.uuid4())

    try:
        task = execute_engineering_study_task.delay(
            {
                "study_type": payload.study_type,
                "data": payload.model_dump(),
                "trace_id": trace_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "user_role": user_role,
                "request_timestamp": str(time.time()),
            }
        )
    except Exception as exc:
        logger.exception("Failed to enqueue async study task: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue async study task to message broker",
        ) from exc

    from services.task_ownership import record_task_ownership

    record_task_ownership(
        task_id=task.id,
        user_id=user_id,
        tenant_id=tenant_id,
        user_role=user_role,
        study_type=payload.study_type,
        metadata={"trace_id": trace_id},
    )

    logger.info(
        "Enqueued async study task_id=%s study_type=%s user_id=%s tenant_id=%s",
        task.id,
        payload.study_type,
        user_id,
        tenant_id,
    )

    return {
        "task_id": task.id,
        "status": "accepted",
        "study_type": payload.study_type,
        "submitted_at": str(time.time()),
    }


@router.get(
    "/task_status/{task_id}",
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized — missing or invalid credentials"},
        403: {"description": "Forbidden — insufficient permissions"},
        404: {"description": "Task not found"},
        503: {"description": "Celery is not available"},
    },
)
async def get_task_status(
    task_id: str,
    req: Request,
    _: Annotated[str, Depends(get_api_key)],
    user: Annotated[Optional[CurrentUser], Depends(get_optional_current_user_from_header)],
) -> dict[str, Any]:
    """Get the status of an async study task with tenant isolation and ownership enforcement."""
    user_id, tenant_id, user_role = _extract_caller_identity(req, user)

    from services.task_ownership import (
        TaskAccessForbiddenError,
        TaskOwnershipError,
        TaskTenantMismatchError,
        verify_task_access,
    )

    try:
        verify_task_access(
            task_id=task_id,
            caller_user_id=user_id,
            caller_tenant_id=tenant_id,
            caller_role=user_role,
        )
    except TaskTenantMismatchError as exc:
        # Cross-tenant: non-disclosing 404
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except TaskOwnershipError as exc:
        # Missing ownership metadata: fail-closed 404
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except TaskAccessForbiddenError as exc:
        # Same tenant, not owner/admin: 403 Forbidden
        raise HTTPException(status_code=403, detail="Insufficient permissions to access task") from exc

    celeryasyncresult, _, celery_app = get_celery_components()
    if not celeryasyncresult or not celery_app:
        raise HTTPException(status_code=503, detail="Celery is not available")

    try:
        task_result = celeryasyncresult(task_id, app=celery_app)
        response: dict[str, Any] = {
            "task_id": task_id,
            "status": task_result.status,
            "result": None,
        }

        if task_result.ready():
            if task_result.successful():
                res = task_result.result
                response["result"] = res
                if isinstance(res, dict) and res.get("success") is False:
                    response["status"] = "FAILURE"
                    if "errors" in res:
                        response["error"] = res["errors"]
            elif task_result.failed():
                response["status"] = "FAILURE"
                response["error"] = str(task_result.info)

        if task_result.status == "PROGRESS":
            response["meta"] = task_result.info

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting task status for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/types")
async def get_study_types(request: Request):
    """Return the list of supported power system study types."""
    disabled = {d["study_type"] for d in get_disabled_studies()}
    from api.shared_handlers import STUDY_TYPES

    return {
        "study_types": [t for t in STUDY_TYPES if t not in disabled],
        "disabled_studies": get_disabled_studies(),
    }


class StudyReRunRequest(BaseModel):
    project_id: str
    tool: str = "load_flow"
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("/re-run")
async def re_run_study(
    body: StudyReRunRequest,
    _: Annotated[str, Depends(get_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
    user: Annotated[Optional[CurrentUser], Depends(get_optional_current_user_from_header)] = None,
):
    """Execute study re-run with updated solver parameters, idempotency, and revision tracking."""
    from api.approvals import _replay_idempotent, _store_idempotent
    from api.services.study_execution_service import execute_study_re_run

    tenant_id = (user.tenant_id if user and getattr(user, "tenant_id", None) else None) or "default"
    endpoint = f"POST /api/v1/studies/re-run/{body.project_id}"

    if idempotency_key:
        cached = await _replay_idempotent(db, idempotency_key, endpoint, tenant_id)
        if cached is not None:
            return cached

    result = await execute_study_re_run(
        project_id=body.project_id,
        tool=body.tool,
        params=body.parameters,
        user=user,
        db=db,
    )

    if idempotency_key:
        await _store_idempotent(db, idempotency_key, endpoint, tenant_id, result)

    return result
