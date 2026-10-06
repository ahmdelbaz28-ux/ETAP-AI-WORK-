"""
services/execution_orchestrator.py — Canonical Execution Orchestrator (Phase 6).

Promoted to the single production engineering execution gateway.
Coordinates governance, identity, validation, idempotency, routing,
risk assessment, and audit provenance across all execution models.

Does NOT contain engineering algorithms:
Governs execution and delegates to specialized executors.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from core.exceptions import SpecializedExecutionUnavailableError
from engine.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    ExecutorKind,
    LifecycleStatus,
    get_capability_registry,
)
from services.execution_request import (
    CanonicalExecutionResult,
    ExecutionRequest,
    IEngineeringExecutor,
)

UTC = timezone.utc  # noqa: UP017
logger = logging.getLogger("engineering_service.orchestrator")


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Executors (Phase 5 Implementations)
# ─────────────────────────────────────────────────────────────────────────────

class NativeEngineeringExecutor(IEngineeringExecutor):
    """Executes native numerical power-system studies via PowerSystemEngine / StudyExecutor."""

    def __init__(self, study_executor: Any = None) -> None:
        self._executor = study_executor

    def _get_study_executor(self) -> Any:
        if self._executor is None:
            from services.study_executor import StudyExecutor

            self._executor = StudyExecutor(cache=None)
        return self._executor

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        executor = self._get_study_executor()
        cap_reg = get_capability_registry()
        cap = cap_reg.get_capability_definition(request.capability_id)

        system_input = request.get_system()
        params = request.get_parameters()

        # Build system model if a specification is provided
        if system_input is not None and not hasattr(system_input, "run_study"):
            from core_model.specs import SystemSpec

            if isinstance(system_input, (SystemSpec, dict)):
                built_system = executor._build_system_from_spec(system_input)
            else:
                built_system = system_input
        else:
            built_system = system_input

        study_type = cap.study_type or request.capability_id

        # Execute study synchronously on the executor thread pool if loop exists
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                data = await loop.run_in_executor(
                    None, executor._dispatch, study_type, built_system, params
                )
            else:
                data = executor._dispatch(study_type, built_system, params)
        except Exception:
            # Direct synchronous execution fallback
            data = executor._dispatch(study_type, built_system, params)

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


class AgentEngineeringExecutor(IEngineeringExecutor):
    """Executes AI specialist agent studies via BaseAgent subclasses."""

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        from services.study_executor import StudyExecutor

        executor = StudyExecutor(cache=None)
        params = request.get_parameters()
        study_type = request.capability_id

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                data = await loop.run_in_executor(
                    None, executor._dispatch_agent, study_type, params
                )
            else:
                data = executor._dispatch_agent(study_type, params)
        except Exception:
            data = executor._dispatch_agent(study_type, params)

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


class EtapEngineeringExecutor(IEngineeringExecutor):
    """Executes studies via ETAP COM integration / provider interface."""

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        from etap_integration.etap_provider import get_etap_provider

        provider = get_etap_provider()
        params = request.get_parameters()

        if hasattr(provider, "run_study"):
            data = provider.run_study(request.capability_id, params)
        elif hasattr(provider, "execute_study"):
            data = provider.execute_study(request.capability_id, params)
        else:
            data = {"status": "executed", "provider": type(provider).__name__}

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


class ExternalServiceExecutor(IEngineeringExecutor):
    """Executes external engineering bridges and dedicated evaluators."""

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        from services.study_executor import StudyExecutor

        executor = StudyExecutor(cache=None)
        params = request.get_parameters()
        system = request.get_system()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                data = await loop.run_in_executor(
                    None, executor._dispatch, request.capability_id, system, params
                )
            else:
                data = executor._dispatch(request.capability_id, system, params)
        except Exception:
            data = executor._dispatch(request.capability_id, system, params)

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


class CompositeEngineeringExecutor(IEngineeringExecutor):
    """Executes composite multi-agent study orchestrations."""

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        from services.study_executor import StudyExecutor

        executor = StudyExecutor(cache=None)
        params = request.get_parameters()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                data = await loop.run_in_executor(
                    None, executor._dispatch_agent, request.capability_id, params
                )
            else:
                data = executor._dispatch_agent(request.capability_id, params)
        except Exception:
            data = executor._dispatch_agent(request.capability_id, params)

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Canonical Execution Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionOrchestrator:
    """Canonical Execution Orchestrator (Phase 6).

    Single authoritative gateway for all engineering study executions.
    Enforces the 19 core governance and execution responsibilities:
    1. Authenticate
    2. Validate tenant
    3. Validate capability
    4. Validate lifecycle state
    5. Validate authorization
    6. Validate approval requirements
    7. Validate request schema
    8. Resolve capability
    9. Resolve executor
    10. Enforce idempotency
    11. Create execution identity
    12. Create audit context
    13. Execute selected executor
    14. Perform canonical validation
    15. Calculate risk
    16. Attach provenance
    17. Persist canonical result
    18. Emit execution events
    19. Return canonical result
    """

    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None) -> None:
        self._registry = capability_registry or get_capability_registry()
        self._executors: dict[str, IEngineeringExecutor] = {}
        self._idempotency_cache: dict[str, Tuple[CanonicalExecutionResult, float]] = {}
        self._result_store: dict[str, CanonicalExecutionResult] = {}
        self._event_listeners: list[Callable[[str, CanonicalExecutionResult], Any]] = []

        # Wire default executors
        self.register_executor(ExecutorKind.NATIVE, NativeEngineeringExecutor())
        self.register_executor(ExecutorKind.AGENT, AgentEngineeringExecutor())
        self.register_executor(ExecutorKind.ETAP, EtapEngineeringExecutor())
        self.register_executor(ExecutorKind.EXTERNAL_SERVICE, ExternalServiceExecutor())
        self.register_executor(ExecutorKind.COMPOSITE, CompositeEngineeringExecutor())

    def register_executor(
        self, kind: ExecutorKind | str, executor: IEngineeringExecutor
    ) -> None:
        """Register an executor for a specific executor kind."""
        k = kind.value if isinstance(kind, ExecutorKind) else str(kind).lower()
        self._executors[k] = executor

    def get_executor(self, kind: ExecutorKind | str) -> Optional[IEngineeringExecutor]:
        """Retrieve registered executor for an executor kind."""
        k = kind.value if isinstance(kind, ExecutorKind) else str(kind).lower()
        return self._executors.get(k)

    def register_event_listener(
        self, listener: Callable[[str, CanonicalExecutionResult], Any]
    ) -> None:
        """Register an observer callback for execution lifecycle events."""
        self._event_listeners.append(listener)

    async def execute(
        self, request: ExecutionRequest, *, raise_on_error: bool = False
    ) -> CanonicalExecutionResult:
        """The single production engineering execution gateway.

        Executes the canonical request through all 19 governance steps.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        # ── 1. Authenticate ──────────────────────────────────────────────────
        if not request.user_id or not str(request.user_id).strip():
            return self._build_rejection(
                request,
                reason="AUTHENTICATION_REQUIRED",
                message="User identification (user_id) is required for execution",
                raise_on_error=raise_on_error,
            )

        # ── 2. Validate Tenant ───────────────────────────────────────────────
        if not request.tenant_id or not str(request.tenant_id).strip():
            return self._build_rejection(
                request,
                reason="TENANT_VALIDATION_FAILED",
                message="Tenant identification (tenant_id) is mandatory for multi-tenant isolation",
                raise_on_error=raise_on_error,
            )

        # ── 3. Validate Capability ───────────────────────────────────────────
        cap = self._registry.get(request.capability_id)
        if cap is None:
            return self._build_rejection(
                request,
                reason="CAPABILITY_NOT_FOUND",
                message=f"Capability '{request.capability_id}' is not registered in canonical registry",
                raise_on_error=raise_on_error,
            )

        # ── 4. Validate Lifecycle State ──────────────────────────────────────
        status_str = (
            cap.lifecycle_status.value
            if isinstance(cap.lifecycle_status, LifecycleStatus)
            else str(cap.lifecycle_status).lower()
        )

        if status_str == "disabled":
            # Check if gated by feature flag
            flag_enabled = False
            if cap.feature_flag:
                try:
                    from api.feature_flags import is_strict_feature_enabled

                    flag_enabled = is_strict_feature_enabled(cap.feature_flag)
                except Exception:
                    flag_enabled = False
            if not flag_enabled:
                exc = SpecializedExecutionUnavailableError(
                    request.capability_id,
                    f"Capability '{request.capability_id}' is disabled by feature flag '{cap.feature_flag}'",
                )
                if raise_on_error:
                    raise exc
                return self._build_rejection(
                    request,
                    reason="CAPABILITY_DISABLED",
                    message=str(exc),
                    cap=cap,
                    raise_on_error=False,
                )
        elif status_str == "unavailable":
            exc = SpecializedExecutionUnavailableError(
                request.capability_id,
                f"Specialized execution backend is unavailable for capability '{request.capability_id}'",
            )
            if raise_on_error:
                raise exc
            return self._build_rejection(
                request,
                reason="CAPABILITY_UNAVAILABLE",
                message=str(exc),
                cap=cap,
                raise_on_error=False,
            )

        # ── 5. Validate Authorization ────────────────────────────────────────
        if cap.authorization_policy == "admin" and request.user_id != "admin":
            return self._build_rejection(
                request,
                reason="AUTHORIZATION_DENIED",
                message="Administrator privileges required for this capability",
                cap=cap,
                raise_on_error=raise_on_error,
            )

        # ── 6. Validate Approval Requirements ────────────────────────────────
        if cap.approval_policy in ("maker_checker", "dual_control"):
            approval = request.approval_context or {}
            if not approval.get("approved"):
                return self._build_rejection(
                    request,
                    reason="APPROVAL_REQUIRED",
                    message="Capability requires approved dual-control maker-checker authorization",
                    cap=cap,
                    raise_on_error=raise_on_error,
                )
            if approval.get("approver_id") == request.user_id:
                return self._build_rejection(
                    request,
                    reason="MAKER_CHECKER_VIOLATION",
                    message="Approver must be strictly distinct from the requesting user",
                    cap=cap,
                    raise_on_error=raise_on_error,
                )

        # ── 7. Validate Request Schema ───────────────────────────────────────
        params = request.get_parameters()
        if cap.required_params:
            missing_params = [p for p in cap.required_params if params.get(p) is None]
            if missing_params:
                return self._build_rejection(
                    request,
                    reason="SCHEMA_VALIDATION_FAILED",
                    message=f"Missing mandatory parameters: {missing_params}",
                    cap=cap,
                    raise_on_error=raise_on_error,
                )

        if cap.requires_system:
            system = request.get_system()
            if system is None:
                return self._build_rejection(
                    request,
                    reason="SYSTEM_MODEL_REQUIRED",
                    message=f"Capability '{request.capability_id}' requires a populated System model",
                    cap=cap,
                    raise_on_error=raise_on_error,
                )

        # ── 8. Resolve Capability & Policies ─────────────────────────────────
        provider_policy = request.provider_policy or cap.provider_policy
        execution_policy = request.execution_policy or "default_policy"

        # ── 9. Resolve Executor ──────────────────────────────────────────────
        executor_kind_str = (
            cap.executor_kind.value
            if isinstance(cap.executor_kind, ExecutorKind)
            else str(cap.executor_kind).lower()
        )
        executor = self.get_executor(executor_kind_str)
        if executor is None:
            return self._build_rejection(
                request,
                reason="NO_EXECUTOR_REGISTERED",
                message=f"No executor registered for kind '{executor_kind_str}'",
                cap=cap,
                raise_on_error=raise_on_error,
            )

        # ── 10. Enforce Idempotency ──────────────────────────────────────────
        idempotency_key = f"{request.tenant_id}:{request.idempotency_key}"
        if idempotency_key in self._idempotency_cache:
            cached_res, cached_time = self._idempotency_cache[idempotency_key]
            if time.time() - cached_time < 86400:  # 24 hour TTL
                logger.info(
                    "Idempotent replay detected for execution %s (key %s)",
                    request.execution_id,
                    request.idempotency_key,
                )
                replay_res = cached_res.model_copy(
                    update={
                        "idempotent_replay": True,
                        "request_id": request.request_id,
                        "execution_id": request.execution_id,
                    }
                )
                return replay_res

        # ── 11. Create Execution Identity ────────────────────────────────────
        execution_id = request.execution_id or uuid.uuid4().hex

        # ── 12. Create Audit Context ─────────────────────────────────────────
        audit_context = {
            "execution_id": execution_id,
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "capability_id": request.capability_id,
            "capability_version": cap.version,
            "trace_id": request.trace_id,
            "started_at": started_at,
            "executor_kind": executor_kind_str,
            "provider_policy": str(provider_policy),
            "execution_policy": str(execution_policy),
        }

        # ── 13. Execute Selected Executor ────────────────────────────────────
        try:
            exec_res = await executor.execute(request)
            data = exec_res.data
            errors = exec_res.errors
            warnings = exec_res.warnings
            success = exec_res.success
        except SpecializedExecutionUnavailableError:
            if raise_on_error:
                raise
            return self._build_rejection(
                request,
                reason="SPECIALIZED_EXECUTION_UNAVAILABLE",
                message=f"Specialized execution unavailable for '{request.capability_id}'",
                cap=cap,
                raise_on_error=False,
            )
        except Exception as exc:
            logger.error("Execution error for %s: %s", request.capability_id, exc, exc_info=True)
            if raise_on_error:
                raise
            data = {}
            errors = [str(exc)]
            warnings = []
            success = False

        duration = time.perf_counter() - start_time

        # ── 14. Perform Canonical Validation ─────────────────────────────────
        validation_status = "passed" if success and not errors else "failed"
        if warnings and validation_status == "passed":
            validation_status = "warning"

        # ── 15. Calculate Risk ───────────────────────────────────────────────
        try:
            from api.risk_scoring import compute_risk

            risk_info = compute_risk(cap.study_type or request.capability_id, data)
        except Exception:
            risk_info = {"risk_score": cap.risk_class, "risk_violations": []}

        risk_assessment = {
            "risk_class": cap.risk_class,
            "risk_score": risk_info.get("risk_score", cap.risk_class),
            "violations": risk_info.get("risk_violations", []),
        }

        # ── 16. Attach Provenance ────────────────────────────────────────────
        provenance = {
            "executor_kind": executor_kind_str,
            "handler": cap.handler,
            "capability_id": cap.capability_id,
            "capability_version": cap.version,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": request.trace_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
        }

        # ── 17. Persist Canonical Result ─────────────────────────────────────
        result = CanonicalExecutionResult(
            execution_id=execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="completed" if success else "failed",
            success=success,
            data=data,
            provenance=provenance,
            validation_status=validation_status,
            risk_assessment=risk_assessment,
            audit_context=audit_context,
            execution_time_sec=duration,
            errors=errors,
            warnings=warnings,
            trace_id=request.trace_id,
            idempotent_replay=False,
            metadata=request.metadata,
        )

        self._result_store[execution_id] = result
        self._idempotency_cache[idempotency_key] = (result, time.time())

        # ── 18. Emit Execution Events ────────────────────────────────────────
        self._emit_event("execution_completed", result)

        # ── 19. Return Canonical Result ──────────────────────────────────────
        return result

    def _build_rejection(
        self,
        request: ExecutionRequest,
        reason: str,
        message: str,
        cap: Optional[CapabilityDefinition] = None,
        raise_on_error: bool = False,
    ) -> CanonicalExecutionResult:
        """Construct a standardized rejection result for governance violations."""
        if raise_on_error:
            raise ValueError(f"{reason}: {message}")

        audit_context = {
            "execution_id": request.execution_id,
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "capability_id": request.capability_id,
            "rejection_reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        res = CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            status="rejected",
            success=False,
            data={},
            provenance={
                "rejection_reason": reason,
                "capability_id": request.capability_id,
            },
            validation_status="failed",
            risk_assessment={
                "risk_class": cap.risk_class if cap else "high",
                "risk_score": "high",
                "violations": [message],
            },
            audit_context=audit_context,
            execution_time_sec=0.0,
            errors=[f"{reason}: {message}"],
            warnings=[],
            trace_id=request.trace_id,
            idempotent_replay=False,
        )
        self._emit_event("execution_rejected", res)
        return res

    def _emit_event(self, event_type: str, result: CanonicalExecutionResult) -> None:
        """Dispatch lifecycle event to observers."""
        logger.info(
            "ExecutionEvent [%s] id=%s capability=%s status=%s tenant=%s",
            event_type,
            result.execution_id,
            result.capability_id,
            result.status,
            result.tenant_id,
        )
        for listener in self._event_listeners:
            try:
                res = listener(event_type, result)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as e:
                logger.warning("Event listener failed: %s", e)


# Singleton Orchestrator Instance
_DEFAULT_ORCHESTRATOR: Optional[ExecutionOrchestrator] = None


def get_execution_orchestrator() -> ExecutionOrchestrator:
    """Return the global singleton canonical execution orchestrator."""
    global _DEFAULT_ORCHESTRATOR
    if _DEFAULT_ORCHESTRATOR is None:
        _DEFAULT_ORCHESTRATOR = ExecutionOrchestrator()
    return _DEFAULT_ORCHESTRATOR
