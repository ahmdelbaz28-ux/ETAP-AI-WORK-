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
import hashlib
import json
import logging
import os
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


class CentralizedStateUnavailableError(RuntimeError):
    """Raised when centralized state is required in multi-replica topology but unavailable."""

    pass


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


class RedisExecutionStateStore(IExecutionStateStore):
    """Distributed, Redis-backed state store for multi-replica cluster deployments (Gap 8).

    Ensures that idempotency keys, execution states, and canonical results
    are synchronized across distributed worker replicas. In multi-replica
    topology, fails closed if Redis is unavailable.
    """

    def __init__(
        self,
        fallback_store: Optional[IExecutionStateStore] = None,
        ttl_seconds: int = 86400,
        strict_distributed: bool = False,
    ) -> None:
        self._fallback = fallback_store or InMemoryExecutionStateStore()
        self._ttl_seconds = ttl_seconds
        topo = os.getenv("DEPLOYMENT_TOPOLOGY", "").lower()
        self._strict_distributed = strict_distributed or (
            topo in ("multi_replica", "cluster", "distributed")
        )

    def _sync_get_redis(self) -> Any:
        try:
            import redis

            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(url, decode_responses=True)
            if self._strict_distributed:
                client.ping()
            return client
        except Exception as exc:
            if self._strict_distributed:
                raise CentralizedStateUnavailableError(
                    f"Centralized Redis state store is unavailable in multi-replica deployment: {exc}"
                ) from exc
            return None

    def get_idempotency(self, key: str) -> Optional[Tuple[CanonicalExecutionResult, float]]:
        r = self._sync_get_redis()
        if r is not None:
            try:
                raw = r.get(f"etap:idemp:{key}")
                if raw:
                    payload = json.loads(raw)
                    res = CanonicalExecutionResult.model_validate(payload["result"])
                    return (res, float(payload["timestamp"]))
                return None
            except CentralizedStateUnavailableError:
                raise
            except Exception as e:
                if self._strict_distributed:
                    raise CentralizedStateUnavailableError(
                        f"Redis get_idempotency failed in multi-replica deployment: {e}"
                    ) from e
                logger.debug("Redis get_idempotency error: %s (using fallback)", e)
        if self._strict_distributed:
            raise CentralizedStateUnavailableError(
                "Centralized Redis state store is mandatory in multi-replica topology (fail-closed)"
            )
        return self._fallback.get_idempotency(key)

    def set_idempotency(self, key: str, result: CanonicalExecutionResult, timestamp: float) -> None:
        r = self._sync_get_redis()
        if r is not None:
            try:
                payload = {
                    "result": result.model_dump(),
                    "timestamp": timestamp,
                }
                r.set(f"etap:idemp:{key}", json.dumps(payload, default=str), ex=self._ttl_seconds)
                return
            except CentralizedStateUnavailableError:
                raise
            except Exception as e:
                if self._strict_distributed:
                    raise CentralizedStateUnavailableError(
                        f"Redis set_idempotency failed in multi-replica deployment: {e}"
                    ) from e
                logger.debug("Redis set_idempotency error: %s", e)
        if self._strict_distributed:
            raise CentralizedStateUnavailableError(
                "Centralized Redis state store is mandatory in multi-replica topology (fail-closed)"
            )
        self._fallback.set_idempotency(key, result, timestamp)

    def get_result(self, execution_id: str) -> Optional[CanonicalExecutionResult]:
        r = self._sync_get_redis()
        if r is not None:
            try:
                raw = r.get(f"etap:res:{execution_id}")
                if raw:
                    return CanonicalExecutionResult.model_validate(json.loads(raw))
                return None
            except CentralizedStateUnavailableError:
                raise
            except Exception as e:
                if self._strict_distributed:
                    raise CentralizedStateUnavailableError(
                        f"Redis get_result failed in multi-replica deployment: {e}"
                    ) from e
                logger.debug("Redis get_result error: %s (using fallback)", e)
        if self._strict_distributed:
            raise CentralizedStateUnavailableError(
                "Centralized Redis state store is mandatory in multi-replica topology (fail-closed)"
            )
        return self._fallback.get_result(execution_id)

    def set_result(self, execution_id: str, result: CanonicalExecutionResult) -> None:
        r = self._sync_get_redis()
        if r is not None:
            try:
                r.set(
                    f"etap:res:{execution_id}",
                    json.dumps(result.model_dump(), default=str),
                    ex=self._ttl_seconds,
                )
                return
            except CentralizedStateUnavailableError:
                raise
            except Exception as e:
                if self._strict_distributed:
                    raise CentralizedStateUnavailableError(
                        f"Redis set_result failed in multi-replica deployment: {e}"
                    ) from e
                logger.debug("Redis set_result error: %s", e)
        if self._strict_distributed:
            raise CentralizedStateUnavailableError(
                "Centralized Redis state store is mandatory in multi-replica topology (fail-closed)"
            )
        self._fallback.set_result(execution_id, result)

    def reset(self) -> None:
        self._fallback.reset()


_GLOBAL_EXECUTION_STATE_STORE: IExecutionStateStore = InMemoryExecutionStateStore()


def get_execution_state_store() -> IExecutionStateStore:
    """Return active canonical execution state store.

    Automatically provides RedisExecutionStateStore when running in
    multi-replica mode (DEPLOYMENT_TOPOLOGY in cluster/multi_replica)
    or when explicit centralized state is configured.
    """
    global _GLOBAL_EXECUTION_STATE_STORE
    topo = os.getenv("DEPLOYMENT_TOPOLOGY", "").lower()
    if topo in ("multi_replica", "cluster", "distributed"):
        if not isinstance(_GLOBAL_EXECUTION_STATE_STORE, RedisExecutionStateStore) or not getattr(
            _GLOBAL_EXECUTION_STATE_STORE, "_strict_distributed", False
        ):
            _GLOBAL_EXECUTION_STATE_STORE = RedisExecutionStateStore(
                fallback_store=None, strict_distributed=True
            )
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

        study_type = cap.study_type or request.capability_id

        # Deterministic single execution attempt (NO double-execution fallback)
        try:
            # Build system model if a specification is provided
            if system_input is not None and not hasattr(system_input, "run_study"):
                from core_model.specs import SystemSpec

                if isinstance(system_input, (SystemSpec, dict)):
                    built_system = executor._build_system_from_spec(system_input)
                else:
                    built_system = system_input
            else:
                built_system = system_input

            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                data = await loop.run_in_executor(
                    None, executor._dispatch, study_type, built_system, params
                )
            else:
                data = executor._dispatch(study_type, built_system, params)
        except Exception as exc:
            logger.exception("Native dispatch error for %s: %s", study_type, exc)
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap.version if cap else "1.0.0",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="native",
                provider="native",
                solver="native",
                engine_version="unknown",
                status="failed",
                success=False,
                data={},
                errors=[str(exc)],
                warnings=[],
                trace_id=request.trace_id,
            )

        # Parse outcome semantics
        is_dict = isinstance(data, dict)
        dict_data = data if is_dict else (data.to_dict() if hasattr(data, "to_dict") else {})
        from core.bootstrap import _to_jsonable

        dict_data = _to_jsonable(dict_data) or {}
        success = True
        errors: list[str] = []
        warnings: list[str] = []

        if is_dict:
            if data.get("success") is False:
                success = False
            if data.get("converged") is False and "converged" in data:
                success = False
                errors.append(f"Native study '{study_type}' did not converge")
            if data.get("errors"):
                errors.extend(str(e) for e in data["errors"])
                success = False
            if data.get("error"):
                errors.append(str(data["error"]))
                success = False
            if data.get("warnings"):
                warnings.extend(str(w) for w in data["warnings"])

        solver_opts = (
            getattr(request, "solver_options", {}) if hasattr(request, "solver_options") else {}
        )
        solver_method = None
        if isinstance(solver_opts, dict):
            solver_method = solver_opts.get("solver")
        if not solver_method:
            solver_method = (
                params.get("solver")
                or params.get("method")
                or (dict_data.get("solver") if is_dict else None)
                or ("newton_raphson" if "load_flow" in str(study_type).lower() else "native")
            )
        if not solver_method:
            solver_method = "native"

        return CanonicalExecutionResult(
            execution_id=request.execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            capability_version=cap.version if cap else "1.0.0",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind="native",
            provider="native",
            solver=solver_method,
            engine_version="unknown",
            status="completed" if success else "failed",
            success=success,
            data=dict_data,
            errors=errors,
            warnings=warnings,
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
                    built_system = StudyExecutor()._build_system_from_spec(spec)
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
            description=request.metadata.get("goal")
            or f"Agent execution for {request.capability_id}",
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
            if hasattr(executor, "provider")
            and type(executor.provider).__name__ not in ("Mock", "MagicMock")
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
            if hasattr(executor, "provider")
            and type(executor.provider).__name__ not in ("Mock", "MagicMock")
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
    """Executes external engineering bridges and remote solver endpoints.

    Phase 3 Contract:
    - Truly represents external execution boundary.
    - Requires configured external endpoint (via request metadata or environment).
    - If no external backend is configured, fails closed truthfully as unavailable.
    - Never invokes local StudyExecutor or relabels local execution as external.
    """

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        cap_reg = get_capability_registry()
        cap = cap_reg.get(request.capability_id)
        cap_version = cap.version if cap else "1.0.0"

        provider = (
            request.metadata.get("external_provider")
            or os.getenv(f"EXTERNAL_{request.capability_id.upper()}_PROVIDER")
            or os.getenv("EXTERNAL_SERVICE_PROVIDER")
            or "external_service"
        )
        endpoint = (
            request.metadata.get("external_endpoint")
            or os.getenv(f"EXTERNAL_{request.capability_id.upper()}_URL")
            or os.getenv("EXTERNAL_SERVICE_URL")
        )
        timeout_sec = float(
            request.metadata.get("timeout_sec")
            or os.getenv("EXTERNAL_SERVICE_TIMEOUT_SEC", "30.0")
        )

        # Fail closed if no external service backend is configured
        if not endpoint:
            logger.warning(
                "External service backend unavailable for %s: no external endpoint configured",
                request.capability_id,
            )
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap_version,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="external_service",
                provider=provider,
                solver="external",
                engine_version="unknown",
                status="failed",
                success=False,
                data={},
                errors=[
                    f"External service backend unavailable: No external endpoint configured for '{request.capability_id}'"
                ],
                warnings=[],
                provenance={
                    "executor_kind": "external_service",
                    "provider": provider,
                    "external_endpoint": None,
                    "external_execution_id": None,
                    "status": "unavailable",
                    "failure_reason": "NO_EXTERNAL_ENDPOINT_CONFIGURED",
                },
                trace_id=request.trace_id,
            )

        # Real external service HTTP bridge execution
        try:
            import httpx

            submission_payload = {
                "request_id": request.request_id,
                "execution_id": request.execution_id,
                "capability_id": request.capability_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "parameters": request.get_parameters(),
                "system": request.get_system(),
            }

            headers = {
                "X-Trace-ID": request.trace_id or "",
                "X-Tenant-ID": request.tenant_id,
                "X-User-ID": request.user_id,
            }

            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                response = await client.post(endpoint, json=submission_payload, headers=headers)

            ext_status_code = response.status_code
            ext_exec_id = response.headers.get("X-External-Execution-ID")

            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text}

            if isinstance(data, dict) and not ext_exec_id:
                ext_exec_id = data.get("external_execution_id") or data.get("execution_id")

            is_failed = (
                ext_status_code >= 400
                or (isinstance(data, dict) and data.get("success") is False)
                or (isinstance(data, dict) and str(data.get("status", "")).lower() in ("failed", "rejected", "unavailable"))
            )

            errors: list[str] = []
            if ext_status_code >= 400:
                errors.append(f"External service returned HTTP {ext_status_code}")
            if isinstance(data, dict):
                if data.get("errors"):
                    errors.extend(str(e) for e in data["errors"])
                elif data.get("error"):
                    errors.append(str(data["error"]))
                warnings = [str(w) for w in data.get("warnings", [])]
            else:
                warnings = []

            success = not is_failed and not errors

            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap_version,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="external_service",
                provider=provider,
                solver="external_http_bridge",
                engine_version="unknown",
                status="completed" if success else "failed",
                success=success,
                data=data if isinstance(data, dict) else {"response": data},
                errors=errors,
                warnings=warnings,
                provenance={
                    "executor_kind": "external_service",
                    "provider": provider,
                    "external_endpoint": endpoint,
                    "external_execution_id": ext_exec_id,
                    "external_status_code": ext_status_code,
                },
                trace_id=request.trace_id,
            )

        except Exception as exc:
            logger.exception("External service bridge request failed for %s: %s", request.capability_id, exc)
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap_version,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="external_service",
                provider=provider,
                solver="external_http_bridge",
                engine_version="unknown",
                status="failed",
                success=False,
                data={},
                errors=[f"External service call failed: {exc}"],
                warnings=[],
                provenance={
                    "executor_kind": "external_service",
                    "provider": provider,
                    "external_endpoint": endpoint,
                    "external_execution_id": None,
                    "failure_reason": str(exc),
                },
                trace_id=request.trace_id,
            )


class CompositeEngineeringExecutor(IEngineeringExecutor):
    """Executes composite multi-stage and multi-agent study orchestrations."""

    def __init__(self, agent_executor: Any = None) -> None:
        self._agent_executor = agent_executor or AgentEngineeringExecutor()

    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        params = request.get_parameters()
        stages = (
            params.get("stages")
            or params.get("sub_studies")
            or (request.input.get("stages") if isinstance(request.input, dict) else None)
            or (request.input.get("sub_studies") if isinstance(request.input, dict) else None)
        )

        cap_reg = get_capability_registry()
        cap = cap_reg.get(request.capability_id)

        # ── Path A: Explicit multi-stage workflow execution (Stage 1 -> Stage 2 -> ... -> Stage N) ──
        if stages and isinstance(stages, (list, tuple)):
            from services.execution_orchestrator import get_execution_orchestrator

            orchestrator = get_execution_orchestrator()
            stages_executed: list[dict[str, Any]] = []
            aggregated_data: dict[str, Any] = {}
            previous_stage_result: Optional[dict[str, Any]] = None

            for idx, stage_item in enumerate(stages):
                stage_cap_id = (
                    stage_item if isinstance(stage_item, str) else stage_item.get("capability_id")
                )
                if not stage_cap_id:
                    return CanonicalExecutionResult(
                        execution_id=request.execution_id,
                        request_id=request.request_id,
                        capability_id=request.capability_id,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        executor_kind="composite",
                        status="failed",
                        success=False,
                        data={},
                        errors=[f"Stage {idx + 1} definition missing capability_id"],
                        trace_id=request.trace_id,
                    )

                stage_cap = cap_reg.get(stage_cap_id)
                if stage_cap is None:
                    return CanonicalExecutionResult(
                        execution_id=request.execution_id,
                        request_id=request.request_id,
                        capability_id=request.capability_id,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        executor_kind="composite",
                        status="failed",
                        success=False,
                        data={},
                        errors=[
                            f"Composite stage '{stage_cap_id}' is not registered in canonical registry"
                        ],
                        trace_id=request.trace_id,
                    )

                # Lifecycle availability check (fail-closed if stage disabled or unavailable)
                stage_status = (
                    stage_cap.lifecycle_status.value
                    if isinstance(stage_cap.lifecycle_status, LifecycleStatus)
                    else str(stage_cap.lifecycle_status).lower()
                )
                if stage_status in ("disabled", "unavailable"):
                    return CanonicalExecutionResult(
                        execution_id=request.execution_id,
                        request_id=request.request_id,
                        capability_id=request.capability_id,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        executor_kind="composite",
                        status="failed",
                        success=False,
                        data={},
                        errors=[f"Required composite stage '{stage_cap_id}' is {stage_status}"],
                        trace_id=request.trace_id,
                    )

                # Prepare stage input, passing forward data from earlier stages
                stage_params = dict(params)
                if isinstance(stage_item, dict):
                    stage_params.update(stage_item.get("parameters", {}))
                if previous_stage_result:
                    prior = dict(stage_params.get("prior_stage_results", {}))
                    prior.update(aggregated_data)
                    stage_params["prior_stage_results"] = prior

                stage_req = ExecutionRequest(
                    execution_id=f"{request.execution_id}_stage_{idx + 1}",
                    request_id=f"{request.request_id}_stage_{idx + 1}",
                    capability_id=stage_cap_id,
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    user_role=request.user_role,
                    input={
                        "system": request.get_system(),
                        "parameters": stage_params,
                    },
                    system_snapshot=request.system_snapshot,
                    trace_id=request.trace_id,
                    metadata={"parent_execution_id": request.execution_id, "stage_index": idx + 1},
                )

                stage_res = await orchestrator.execute(stage_req)

                if not stage_res.success or stage_res.status != "completed":
                    stage_err = (
                        "; ".join(stage_res.errors)
                        if stage_res.errors
                        else f"stage {stage_cap_id} failed"
                    )
                    return CanonicalExecutionResult(
                        execution_id=request.execution_id,
                        request_id=request.request_id,
                        capability_id=request.capability_id,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                        executor_kind="composite",
                        status="failed",
                        success=False,
                        data=aggregated_data,
                        errors=[
                            f"Composite workflow halted: stage {idx + 1} ('{stage_cap_id}') failed: {stage_err}"
                        ],
                        provenance={
                            "composite_workflow": {
                                "orchestration_type": "composite_multi_stage",
                                "capability_id": request.capability_id,
                                "failed_stage": stage_cap_id,
                                "stages_executed": stages_executed,
                                "verdict": "rejected",
                            }
                        },
                        trace_id=request.trace_id,
                    )

                stages_executed.append(
                    {
                        "stage_index": idx + 1,
                        "capability_id": stage_cap_id,
                        "execution_id": stage_res.execution_id,
                        "status": stage_res.status,
                        "executor_kind": stage_res.executor_kind,
                        "duration_sec": stage_res.execution_time_sec,
                    }
                )
                aggregated_data[stage_cap_id] = stage_res.data
                previous_stage_result = stage_res.data

            composite_provenance = {
                "orchestration_type": "composite_multi_stage",
                "capability_id": request.capability_id,
                "stages_executed": stages_executed,
                "stages_count": len(stages_executed),
                "verdict": "approved",
            }
            return CanonicalExecutionResult(
                execution_id=request.execution_id,
                request_id=request.request_id,
                capability_id=request.capability_id,
                capability_version=cap.version if cap else "1.0.0",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                executor_kind="composite",
                provider="composite",
                solver="composite_multi_stage_orchestrator",
                status="completed",
                success=True,
                data={
                    "composite_results": aggregated_data,
                    "stages": [s["capability_id"] for s in stages_executed],
                },
                provenance={"composite_workflow": composite_provenance},
                trace_id=request.trace_id,
            )

        # ── Path B: Multi-agent orchestration via AhmedETAPSkillAgent (Lead -> MathGuard -> PeerReview) ──
        res = await self._agent_executor.execute(request)
        res.executor_kind = "composite"

        stages_info = []
        lead_agent = res.data.get("lead_agent") or res.solver or request.capability_id
        reviewer_agent = res.data.get("reviewer_agent") or "validation"
        math_guard_passed = res.data.get("math_guard_passed", res.success)
        verdict = res.data.get("verdict") or ("approved" if res.success else "rejected")

        stages_info.append(
            {
                "stage": "lead_agent_execution",
                "agent": lead_agent,
                "status": "completed" if res.success else "failed",
            }
        )
        stages_info.append({"stage": "math_guard_validation", "passed": math_guard_passed})
        stages_info.append({"stage": "peer_review", "reviewer": reviewer_agent, "verdict": verdict})

        composite_provenance = {
            "orchestration_type": "composite_multi_agent",
            "capability_id": request.capability_id,
            "lead_agent": lead_agent,
            "reviewer_agent": reviewer_agent,
            "verdict": verdict,
            "math_guard_passed": math_guard_passed,
            "stages_executed": stages_info,
        }
        res.provenance["composite_workflow"] = composite_provenance
        return res


# ─────────────────────────────────────────────────────────────────────────────
def _compute_standards_hash(
    cap: Optional[CapabilityDefinition],
    params: dict[str, Any],
    request: ExecutionRequest,
) -> str:
    """Deterministic hash of applicable validation policy, engineering standards, and rule versions."""
    import json

    val_policy = str(getattr(cap, "validation_policy", "default") or "default")
    cap_ver = str(getattr(cap, "version", "1.0.0") or "1.0.0")
    study_type = str(getattr(cap, "study_type", "") or "")
    std_param = (
        str(
            params.get("standard")
            or params.get("std")
            or (request.metadata or {}).get("standard")
            or ""
        )
        .strip()
        .upper()
    )
    standards_context = {
        "validation_policy": val_policy,
        "capability_version": cap_ver,
        "study_type": study_type,
        "standard": std_param,
        "rule_set_version": "v1.0-canonical-assertions",
    }
    s = json.dumps(standards_context, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


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

    def register_executor(self, kind: ExecutorKind | str, executor: IEngineeringExecutor) -> None:
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
        user_id_str = str(request.user_id or "").strip()
        if not user_id_str or user_id_str.lower() in ("anonymous", "none", "null"):
            return self._build_rejection(
                request,
                reason="AUTHENTICATION_REQUIRED",
                message="Valid authenticated user identification (user_id) is required. Anonymous access is strictly prohibited.",
                raise_on_error=raise_on_error,
            )

        # ── 2. Validate Tenant ───────────────────────────────────────────────
        tenant_id_str = str(request.tenant_id or "").strip()
        if not tenant_id_str or tenant_id_str.lower() in ("default", "none", "null"):
            return self._build_rejection(
                request,
                reason="TENANT_VALIDATION_FAILED",
                message="Valid tenant identification (tenant_id) is mandatory for multi-tenant isolation. 'default' tenant is forbidden.",
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
        if cap.authorization_policy:
            auth_policy = str(cap.authorization_policy).lower().strip()
            raw_role = getattr(request, "user_role", None) or (request.metadata or {}).get(
                "role", ""
            )
            user_role = str(raw_role or "").lower().strip()
            if not user_role:
                return self._build_rejection(
                    request,
                    reason="AUTHORIZATION_DENIED",
                    message=f"Missing trusted user role for capability protected by policy '{auth_policy}'",
                    cap=cap,
                    raise_on_error=raise_on_error,
                )

            if auth_policy == "admin":
                if user_role != "admin" and request.user_id != "admin":
                    return self._build_rejection(
                        request,
                        reason="AUTHORIZATION_DENIED",
                        message="Administrator privileges required for this capability",
                        cap=cap,
                        raise_on_error=raise_on_error,
                    )
            elif auth_policy in ("lead_engineer", "lead"):
                if user_role not in ("lead_engineer", "lead", "admin", "service_principal"):
                    return self._build_rejection(
                        request,
                        reason="AUTHORIZATION_DENIED",
                        message=f"Lead engineer role required for capability '{request.capability_id}' (current: '{user_role}')",
                        cap=cap,
                        raise_on_error=raise_on_error,
                    )
            elif auth_policy in ("engineer", "standard"):
                if user_role not in (
                    "engineer",
                    "lead_engineer",
                    "lead",
                    "admin",
                    "service_principal",
                ):
                    return self._build_rejection(
                        request,
                        reason="AUTHORIZATION_DENIED",
                        message=f"Engineer role required for capability '{request.capability_id}' (current: '{user_role}')",
                        cap=cap,
                        raise_on_error=raise_on_error,
                    )
            elif auth_policy in ("viewer", "read_only", "any"):
                pass
            else:
                return self._build_rejection(
                    request,
                    reason="AUTHORIZATION_DENIED",
                    message=f"Unknown authorization policy '{auth_policy}' for capability '{request.capability_id}'",
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
            missing_params = [
                p
                for p in cap.required_params
                if params.get(p) is None
                or (isinstance(params.get(p), str) and not params.get(p).strip())
            ]
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
        try:
            cached_entry = self._state_store.get_idempotency(idempotency_key)
        except CentralizedStateUnavailableError as csu_err:
            logger.error(
                "Centralized state store unavailable during idempotency check: %s", csu_err
            )
            return self._build_rejection(
                request,
                reason="CENTRALIZED_STATE_UNAVAILABLE",
                message=f"Multi-replica centralized state store unavailable: {csu_err}",
                cap=cap,
                raise_on_error=raise_on_error,
            )

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

        # ── 12b. Canonical Semantic Cache Resolution (Gap 1 & Gap 2) ─────────
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
        standards_hash = _compute_standards_hash(cap, params, request)

        use_cache = False
        try:
            from api.feature_flags import is_feature_enabled, is_strict_feature_enabled

            use_cache = is_strict_feature_enabled("token_governance") or is_feature_enabled(
                "token_governance", default=False
            )
        except Exception:
            use_cache = False

        if request.metadata.get("use_cache", True) and use_cache:
            try:
                from api.semantic_cache_redis import get_distributed_semantic_cache

                cache = get_distributed_semantic_cache()
                sys_obj = request.get_system() or request.system_snapshot
                sys_dict = (
                    sys_obj.model_dump()
                    if hasattr(sys_obj, "model_dump")
                    else (sys_obj if isinstance(sys_obj, dict) else {})
                )
                prov_key = (
                    request.provider_policy
                    or getattr(cap, "provider_policy", None)
                    or executor_kind_str
                ).lower()
                cached_entry = await cache.lookup(
                    system_data=sys_dict,
                    parameters=params,
                    agent_handle=cap.study_type or request.capability_id,
                    tenant_id=request.tenant_id,
                    provider=prov_key,
                    capability_id=request.capability_id,
                    capability_version=cap.version,
                    executor_kind=executor_kind_str,
                    solver=getattr(cap, "handler", executor_kind_str),
                    engine_version=getattr(cap, "engine_version", "1.0.0"),
                    standards_hash=standards_hash,
                )
                if cached_entry and getattr(cached_entry, "result", None):
                    cached_raw = cached_entry.result
                    if isinstance(cached_raw, dict):
                        cached_tenant = cached_raw.get("tenant_id")
                        cached_prov = cached_raw.get("provider")
                        cached_succ = cached_raw.get("success", False)
                        cached_val_status = cached_raw.get("validation_status")
                        cached_cap = cached_raw.get("capability_id")
                        cached_kind = cached_raw.get("executor_kind")
                        orig_prov = cached_raw.get("provenance")
                        orig_val_report = cached_raw.get("validation_report")

                        # Authoritative cache hit requires authentic provenance & valid status
                        if (
                            cached_succ
                            and orig_prov
                            and isinstance(orig_prov, dict)
                            and (not cached_tenant or str(cached_tenant) == str(request.tenant_id))
                            and (not cached_prov or str(cached_prov).lower() == prov_key)
                            and (
                                not cached_cap
                                or str(cached_cap).lower() == request.capability_id.lower()
                            )
                            and (
                                not cached_kind
                                or str(cached_kind).lower() == executor_kind_str.lower()
                            )
                            and cached_val_status in ("passed", "warning")
                        ):
                            cached_data = cached_raw.get("data", cached_raw)
                            logger.info(
                                "Canonical cache hit for capability %s tenant %s",
                                request.capability_id,
                                request.tenant_id,
                            )
                            orig_solver = cached_raw.get("solver") or getattr(
                                cap, "handler", executor_kind_str
                            )
                            orig_engine_ver = cached_raw.get("engine_version") or getattr(
                                cap, "engine_version", "1.0.0"
                            )
                            orig_risk_score = cached_raw.get("risk_score")
                            orig_risk_class = cached_raw.get("risk_class") or cap.risk_class
                            orig_risk_assessment = cached_raw.get("risk_assessment") or {}

                            return CanonicalExecutionResult(
                                execution_id=execution_id,
                                request_id=request.request_id,
                                capability_id=request.capability_id,
                                capability_version=cap.version,
                                tenant_id=request.tenant_id,
                                user_id=request.user_id,
                                executor_kind=executor_kind_str,
                                provider=cached_prov or prov_key,
                                solver=orig_solver,
                                engine_version=orig_engine_ver,
                                input_snapshot_hash=cached_raw.get("input_snapshot_hash")
                                or input_hash,
                                system_snapshot_hash=cached_raw.get("system_snapshot_hash")
                                or sys_hash,
                                parameter_hash=cached_raw.get("parameter_hash") or param_hash,
                                status="completed",
                                success=True,
                                data=cached_data if isinstance(cached_data, dict) else {},
                                validation_status=cached_val_status,
                                validation_report=orig_val_report
                                if isinstance(orig_val_report, dict)
                                else {"cached": True, "source": "canonical_semantic_cache"},
                                risk_class=orig_risk_class,
                                risk_score=float(
                                    orig_risk_score if orig_risk_score is not None else 0.1
                                ),
                                risk_assessment=orig_risk_assessment,
                                provenance={
                                    **orig_prov,
                                    "cached": True,
                                    "cache_hit_at": datetime.now(timezone.utc).isoformat(),
                                    "replayed_for_execution_id": execution_id,
                                    "replayed_for_tenant_id": request.tenant_id,
                                    "replayed_for_user_id": request.user_id,
                                },
                                audit_context={
                                    **audit_context,
                                    "cached": True,
                                    "original_execution_id": cached_raw.get("execution_id"),
                                },
                                execution_time_sec=time.perf_counter() - start_time,
                            )
            except Exception as cache_err:
                logger.debug("Canonical semantic cache lookup error: %s", cache_err)

        # ── 13. Execute Selected Executor ────────────────────────────────────
        exec_res: Optional[CanonicalExecutionResult] = None
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

        final_provider = (
            getattr(exec_res, "provider", None)
            or getattr(cap, "provider_policy", None)
            or executor_kind_str
        )
        final_solver = (
            getattr(exec_res, "solver", None) or getattr(cap, "handler", None) or executor_kind_str
        )
        final_engine_version = (
            getattr(exec_res, "engine_version", None)
            or getattr(cap, "engine_version", None)
            or "unknown"
        )

        provenance = {
            "executor_kind": executor_kind_str,
            "handler": cap.handler,
            "capability_id": cap.capability_id,
            "capability_version": cap.version,
            "provider": final_provider,
            "solver": final_solver,
            "engine_version": final_engine_version,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": request.trace_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
        }
        if exec_res and hasattr(exec_res, "provenance") and isinstance(exec_res.provenance, dict):
            for k, v in exec_res.provenance.items():
                if k not in provenance or k in (
                    "composite_workflow",
                    "stages",
                    "stages_executed",
                    "sub_studies",
                ):
                    provenance[k] = v

        # ── 17. Persist Canonical Result ─────────────────────────────────────
        result = CanonicalExecutionResult(
            execution_id=execution_id,
            request_id=request.request_id,
            capability_id=request.capability_id,
            capability_version=cap.version,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            executor_kind=executor_kind_str,
            provider=final_provider,
            solver=final_solver,
            engine_version=final_engine_version,
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
            approval_state=request.approval_context.get("state")
            if request.approval_context
            else None,
            idempotent_replay=False,
            metadata=request.metadata,
        )

        try:
            self._state_store.set_result(execution_id, result)
            self._state_store.set_idempotency(idempotency_key, result, time.time())
        except CentralizedStateUnavailableError as csu_err:
            logger.error(
                "Centralized state store unavailable during result persistence: %s", csu_err
            )
            if raise_on_error:
                raise
            return self._build_rejection(
                request,
                reason="CENTRALIZED_STATE_UNAVAILABLE",
                message=f"Multi-replica centralized state store failed to persist result: {csu_err}",
                cap=cap,
                raise_on_error=False,
            )

        # ── 17b. Store Validated Result in Canonical Semantic Cache ──────────
        if (
            success
            and validation_status in ("passed", "warning")
            and use_cache
            and request.metadata.get("use_cache", True)
        ):
            try:
                from api.semantic_cache_redis import get_distributed_semantic_cache

                cache = get_distributed_semantic_cache()
                sys_obj = request.get_system() or request.system_snapshot
                sys_dict = (
                    sys_obj.model_dump()
                    if hasattr(sys_obj, "model_dump")
                    else (sys_obj if isinstance(sys_obj, dict) else {})
                )
                prov_key = (
                    request.provider_policy
                    or getattr(cap, "provider_policy", None)
                    or executor_kind_str
                ).lower()
                await cache.store(
                    system_data=sys_dict,
                    parameters=params,
                    agent_handle=cap.study_type or request.capability_id,
                    result=result.model_dump() if hasattr(result, "model_dump") else result.dict(),
                    tenant_id=request.tenant_id,
                    provider=prov_key,
                    capability_id=request.capability_id,
                    capability_version=cap.version,
                    executor_kind=executor_kind_str,
                    solver=final_solver,
                    engine_version=final_engine_version,
                    standards_hash=standards_hash,
                )
            except Exception as store_err:
                logger.debug("Failed to store canonical result in semantic cache: %s", store_err)

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
