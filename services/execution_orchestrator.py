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
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Tuple

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
# State Store Abstraction (Phase 11: Multi-Replica Ready)
# ─────────────────────────────────────────────────────────────────────────────

from abc import ABC, abstractmethod


class IExecutionStateStore(ABC):
    """Abstract interface for canonical execution state storage."""

    @abstractmethod
    def get_idempotency(self, key: str) -> Optional[Tuple[CanonicalExecutionResult, float]]:
        """Retrieve idempotent replay result and timestamp if present."""
        ...

    @abstractmethod
    def set_idempotency(self, key: str, result: CanonicalExecutionResult, timestamp: float) -> None:
        """Store idempotent result with timestamp."""
        ...

    @abstractmethod
    def get_result(self, execution_id: str) -> Optional[CanonicalExecutionResult]:
        """Retrieve stored canonical execution result."""
        ...

    @abstractmethod
    def set_result(self, execution_id: str, result: CanonicalExecutionResult) -> None:
        """Store canonical execution result."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Clear all stored state."""
        ...


class InMemoryExecutionStateStore(IExecutionStateStore):
    """Bounded, self-pruning in-memory store for single-replica environments."""

    def __init__(self, max_entries: int = 4096) -> None:
        self._max_entries = max_entries
        self.idempotency: dict[str, Tuple[CanonicalExecutionResult, float]] = {}
        self.results: dict[str, CanonicalExecutionResult] = {}

    def get_idempotency(self, key: str) -> Optional[Tuple[CanonicalExecutionResult, float]]:
        return self.idempotency.get(key)

    def set_idempotency(self, key: str, result: CanonicalExecutionResult, timestamp: float) -> None:
        if len(self.idempotency) >= self._max_entries:
            # Self-prune oldest 10%
            keys = list(self.idempotency.keys())[: self._max_entries // 10]
            for k in keys:
                self.idempotency.pop(k, None)
        self.idempotency[key] = (result, timestamp)

    def get_result(self, execution_id: str) -> Optional[CanonicalExecutionResult]:
        return self.results.get(execution_id)

    def set_result(self, execution_id: str, result: CanonicalExecutionResult) -> None:
        if len(self.results) >= self._max_entries:
            keys = list(self.results.keys())[: self._max_entries // 10]
            for k in keys:
                self.results.pop(k, None)
        self.results[execution_id] = result

    def reset(self) -> None:
        self.idempotency.clear()
        self.results.clear()


_GLOBAL_EXECUTION_STATE_STORE: IExecutionStateStore = InMemoryExecutionStateStore()


def get_execution_state_store() -> IExecutionStateStore:
    """Return active canonical execution state store."""
    return _GLOBAL_EXECUTION_STATE_STORE


def set_execution_state_store(store: IExecutionStateStore) -> None:
    """Swap execution state store (e.g. for multi-replica Redis or Postgres backing)."""
    global _GLOBAL_EXECUTION_STATE_STORE
    _GLOBAL_EXECUTION_STATE_STORE = store


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
            capability_version=cap.version if cap else "1.0.0",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind="native",
            provider="native",
            solver="newton_raphson" if "load_flow" in study_type else "native",
            status="completed",
            success=True,
            data=data if isinstance(data, dict) else (data.to_dict() if hasattr(data, "to_dict") else {}),
            trace_id=request.trace_id,
        )


class AgentEngineeringExecutor(IEngineeringExecutor):
    """Executes AI specialist agent studies via BaseAgent subclasses."""

    def __init__(self, agent_registry: Any = None) -> None:
        self._agents = agent_registry

    def _get_agents(self) -> dict[str, Any]:
        if self._agents is None:
            from agents.registry import create_agent_registry

            self._agents = create_agent_registry()
        return self._agents

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        from agents.models import AgentStatus, EngineeringTask, StudyType
        from engine.capability_registry import get_capability_registry

        cap_reg = get_capability_registry()
        cap = cap_reg.get(request.capability_id)
        agent_key = (cap.agent_key if cap else None) or request.capability_id

        # Resolve aliases
        alias_map = {
            "harmonic": "harmonic_analysis",
            "opf": "optimal_power_flow",
            "protection": "protection_coordination",
        }
        agent_key = alias_map.get(agent_key, agent_key)

        agents = self._get_agents()
        agent = agents.get(agent_key)
        if agent is None:
            raise SpecializedExecutionUnavailableError(
                request.capability_id,
                f"No agent registered for key '{agent_key}' in canonical agent registry",
            )

        params = request.get_parameters()
        system = request.get_system()
        built_system = None
        if system is not None:
            if isinstance(system, dict):
                try:
                    from core_model.specs import SystemSpec
                    from services.study_executor import StudyExecutor

                    spec = SystemSpec.model_validate(system)
                    built_system = StudyExecutor._build_system_from_spec(spec)
                except Exception:
                    built_system = system
            else:
                built_system = system
            params["system"] = built_system or system

        study_types: list[Any] = []
        if cap and cap.study_type:
            try:
                study_types = [StudyType(cap.study_type)]
            except ValueError:
                pass

        task = EngineeringTask(
            task_id=request.request_id or request.execution_id,
            description=request.metadata.get("goal") or f"Agent execution for {request.capability_id}",
            study_types=study_types,
            parameters=params,
        )

        try:
            if asyncio.iscoroutinefunction(getattr(agent, "execute", None)):
                agent_res = await agent.execute(task)
            else:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    agent_res = await loop.run_in_executor(None, agent.execute, task)
                else:
                    agent_res = agent.execute(task)
        except Exception as exc:
            logger.exception("Agent execution failed for %s: %s", agent_key, exc)
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap.version if cap else "1.0.0",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="agent",
                provider="agent",
                solver=type(agent).__name__,
                status="failed",
                success=False,
                data={},
                errors=[str(exc)],
                warnings=[],
                trace_id=request.trace_id,
            )

        status_enum = getattr(agent_res, "status", None)
        is_failed = status_enum == AgentStatus.FAILED or (
            hasattr(status_enum, "value") and status_enum.value == "failed"
        )
        errors = list(getattr(agent_res, "validation_errors", []) or [])
        warnings = list(getattr(agent_res, "warnings", []) or [])
        data = getattr(agent_res, "data", {}) or {}

        if is_failed and not errors:
            errors.append(f"Agent execution reported failure for '{request.capability_id}'")

        success = not is_failed and not errors

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            capability_version=cap.version if cap else "1.0.0",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind="agent",
            provider="agent",
            solver=type(agent).__name__,
            status="completed" if success else "failed",
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            trace_id=request.trace_id,
        )


class EtapEngineeringExecutor(IEngineeringExecutor):
    """Executes studies via ETAP COM integration / provider interface."""

    def __init__(self, etap_executor: Any = None) -> None:
        self._executor = etap_executor

    def _get_etap_executor(self) -> Any:
        if self._executor is None:
            from etap_integration.etap_provider import get_etap_executor

            self._executor = get_etap_executor()
        return self._executor

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        executor = self._get_etap_executor()
        cap_reg = get_capability_registry()
        cap = cap_reg.get(request.capability_id)
        params = request.get_parameters()

        provider_name = (
            type(executor.provider).__name__
            if hasattr(executor, "provider") and type(executor.provider).__name__ not in ("Mock", "MagicMock")
            else "etap"
        )

        # Fail closed immediately if underlying provider is unavailable
        if not executor.is_available():
            err_msg = f"ETAP backend ({provider_name}) is unavailable or disabled"
            logger.warning("EtapEngineeringExecutor fail-closed: %s", err_msg)
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap.version if cap else "1.0.0",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="etap",
                provider=provider_name,
                solver="etap",
                status="failed",
                success=False,
                data={"unavailable": True},
                errors=[err_msg],
                warnings=[],
                trace_id=request.trace_id,
            )

        project_path = (
            params.get("etap_project_path")
            or params.get("project_path")
            or (request.input.get("etap_project_path") if isinstance(request.input, dict) else "")
            or ""
        )

        study_type = (cap.study_type if cap and cap.study_type else None) or request.capability_id

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                etap_res = await loop.run_in_executor(
                    None,
                    executor.execute_study,
                    project_path,
                    study_type,
                    False,
                    params,
                    request.execution_id,
                    request.tenant_id,
                )
            else:
                etap_res = executor.execute_study(
                    project_path=project_path,
                    study_type=study_type,
                    parameters=params,
                    execution_id=request.execution_id,
                    tenant_id=request.tenant_id,
                )
        except Exception as exc:
            logger.exception("ETAP execution threw exception: %s", exc)
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap.version if cap else "1.0.0",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="etap",
                provider=provider_name,
                solver="etap",
                status="failed",
                success=False,
                data={},
                errors=[str(exc)],
                warnings=[],
                trace_id=request.trace_id,
            )

        success = bool(getattr(etap_res, "success", False))
        data = getattr(etap_res, "data", {}) or {}
        errors = list(getattr(etap_res, "errors", []) or [])
        warnings = list(getattr(etap_res, "warnings", []) or [])

        provider_name = (
            type(executor.provider).__name__
            if hasattr(executor, "provider") and type(executor.provider).__name__ not in ("Mock", "MagicMock")
            else "etap"
        )

        if not success and not errors:
            errors.append("ETAP study reported execution failure")

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            capability_version=cap.version if cap else "1.0.0",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind="etap",
            provider=provider_name,
            solver="etap",
            status="completed" if success else "failed",
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
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
        except Exception as exc:
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="external_service",
                status="failed",
                success=False,
                data={},
                errors=[str(exc)],
                trace_id=request.trace_id,
            )

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind="external_service",
            status="completed",
            success=True,
            data=data,
            trace_id=request.trace_id,
        )


class CompositeEngineeringExecutor(IEngineeringExecutor):
    """Executes composite multi-agent study orchestrations."""

    def __init__(self, agent_executor: Any = None) -> None:
        self._agent_executor = agent_executor or AgentEngineeringExecutor()

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        return await self._agent_executor.execute(request)


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

    def __init__(
        self,
        capability_registry: Optional[CapabilityRegistry] = None,
        state_store: Optional[IExecutionStateStore] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._registry = capability_registry or get_capability_registry()
        self._executors: dict[str, IEngineeringExecutor] = {}
        self._state_store = state_store or get_execution_state_store()
        self._event_listeners: list[Callable[[str, CanonicalExecutionResult], Any]] = []

        # Wire default executors
        native_exec = kwargs.get("native_executor") or NativeEngineeringExecutor()
        self.register_executor(ExecutorKind.NATIVE, native_exec)
        self.register_executor(ExecutorKind.AGENT, AgentEngineeringExecutor())
        self.register_executor(ExecutorKind.ETAP, EtapEngineeringExecutor())
        self.register_executor(ExecutorKind.EXTERNAL_SERVICE, ExternalServiceExecutor())
        self.register_executor(ExecutorKind.COMPOSITE, CompositeEngineeringExecutor())

    @property
    def _idempotency_cache(self) -> dict:
        if isinstance(self._state_store, InMemoryExecutionStateStore):
            return self._state_store.idempotency
        return {}

    @property
    def _result_store(self) -> dict:
        if isinstance(self._state_store, InMemoryExecutionStateStore):
            return self._state_store.results
        return {}

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
        cap = self._registry.get(request.capability_id) or self._registry.get(
            request.capability_id.lower()
        )
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
        cached_entry = self._state_store.get_idempotency(idempotency_key)
        if cached_entry is not None:
            cached_res, cached_time = cached_entry
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
            errors = list(exec_res.errors or [])
            warnings = list(exec_res.warnings or [])
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
            logger.exception("Execution error for %s: %s", request.capability_id, exc)
            if raise_on_error:
                raise
            data = {}
            errors = [str(exc)]
            warnings = []
            success = False

        duration = time.perf_counter() - start_time

        # ── 14. Perform Canonical Validation (Phase 5: Real Authority) ──────
        validation_report = {}
        if success and data:
            try:
                from copilot.ai.engineering_assertions import EngineeringAssertionLayer

                assertion_layer = EngineeringAssertionLayer(strict_mode=False)
                study_key = cap.study_type or request.capability_id
                report = assertion_layer.validate(data, study_key)
                validation_report = report.to_dict()

                if not report.passed or report.has_critical_failures:
                    success = False
                    validation_status = "failed"
                    crit_msgs = [
                        f.message
                        for f in report.failures
                        if getattr(f.severity, "value", str(f.severity)) in ("critical", "fatal")
                    ]
                    max_sev = (
                        "fatal"
                        if any(
                            getattr(f.severity, "value", str(f.severity)) == "fatal"
                            for f in report.failures
                        )
                        else "critical"
                    )
                    err_msg = (
                        f"Canonical engineering assertions blocked result: {len(crit_msgs)} {max_sev.upper()} "
                        f"violations detected ({'; '.join(crit_msgs[:2])})"
                    )
                    errors.insert(0, err_msg)
                elif getattr(report, "warnings", []):
                    validation_status = "warning"
                    for w in report.warnings:
                        warnings.append(f"[Validation Warning] {w.message}")
                elif getattr(report, "failures", []):
                    validation_status = "warning"
                else:
                    validation_status = "passed"
            except Exception as val_exc:
                logger.exception("Canonical validation error: %s", val_exc)
                validation_status = "failed"
                success = False
                errors.append(f"Canonical validation error: {val_exc}")
        elif not success:
            validation_status = "failed"
        else:
            validation_status = "passed"

        # ── 15. Calculate Risk ───────────────────────────────────────────────
        try:
            from api.risk_scoring import compute_risk

            risk_info = compute_risk(cap.study_type or request.capability_id, data)
        except Exception:
            risk_info = {"risk_score": 0.1 if success else 1.0, "risk_violations": []}

        raw_score = risk_info.get("risk_score", 0.0)
        risk_level_map = {"low": 0.1, "medium": 0.4, "high": 0.7, "critical": 1.0}
        if isinstance(raw_score, (int, float)):
            risk_score = float(raw_score)
            risk_class = cap.risk_class
        elif isinstance(raw_score, str) and raw_score.lower() in risk_level_map:
            risk_score = risk_level_map[raw_score.lower()]
            risk_class = raw_score.lower()
        else:
            try:
                risk_score = float(raw_score or 0.0)
                risk_class = cap.risk_class
            except (ValueError, TypeError):
                risk_score = 0.1 if success else 1.0
                risk_class = cap.risk_class

        risk_assessment = {
            "risk_class": risk_class,
            "risk_score": risk_score,
            "violations": risk_info.get("risk_violations", []),
        }

        # ── 16. Attach Provenance & Compute Input Hashes ──────────────────────
        import hashlib
        import json

        def _safe_hash(obj: Any) -> str:
            if not obj:
                return ""
            try:
                s = json.dumps(obj, sort_keys=True, default=str)
                return hashlib.sha256(s.encode("utf-8")).hexdigest()
            except Exception:
                return hashlib.sha256(str(obj).encode("utf-8")).hexdigest()

        param_hash = _safe_hash(params)
        sys_hash = _safe_hash(request.system_snapshot or request.get_system())
        input_hash = _safe_hash(request.input)

        provenance = {
            "executor_kind": executor_kind_str,
            "handler": cap.handler,
            "capability_id": cap.capability_id,
            "capability_version": cap.version,
            "provider": getattr(exec_res, "provider", executor_kind_str) if 'exec_res' in locals() else executor_kind_str,
            "solver": getattr(exec_res, "solver", cap.handler) if 'exec_res' in locals() else cap.handler,
            "engine_version": getattr(exec_res, "engine_version", "2.1.0") if 'exec_res' in locals() else "2.1.0",
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
            capability_version=cap.version,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind=executor_kind_str,
            provider=getattr(exec_res, "provider", executor_kind_str) if 'exec_res' in locals() else executor_kind_str,
            solver=getattr(exec_res, "solver", cap.handler) if 'exec_res' in locals() else cap.handler,
            engine_version=getattr(exec_res, "engine_version", "2.1.0") if 'exec_res' in locals() else "2.1.0",
            input_snapshot_hash=input_hash,
            system_snapshot_hash=sys_hash,
            parameter_hash=param_hash,
            status="completed" if success else "failed",
            success=success,
            data=data,
            provenance=provenance,
            validation_status=validation_status,
            validation_report=validation_report,
            risk_class=cap.risk_class,
            risk_score=risk_score,
            risk_assessment=risk_assessment,
            audit_context=audit_context,
            execution_time_sec=duration,
            errors=errors,
            warnings=warnings,
            trace_id=request.trace_id,
            task_id=request.request_id,
            result_id=f"res_{uuid.uuid4().hex}",
            created_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            approval_state=request.approval_context.get("state") if request.approval_context else None,
            idempotent_replay=False,
            metadata=request.metadata,
        )

        self._state_store.set_result(execution_id, result)
        self._state_store.set_idempotency(idempotency_key, result, time.time())

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
