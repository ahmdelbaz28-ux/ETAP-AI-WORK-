"""
services/execution_request.py — Canonical Execution Request Contract (Phase 4 & Phase 5).

Establishes:
1. ExecutionRequest: Single authoritative production execution request contract.
2. CanonicalExecutionResult: Canonical result envelope across all engines.
3. IEngineeringExecutor: Unified common executor interface protocol.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

UTC = timezone.utc  # noqa: UP017


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Canonical Execution Request
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionRequest(BaseModel):
    """Canonical Execution Request contract (Phase 4).

    Encapsulates all governance, identity, policy, and engineering input required
    to execute a power-system study or agent task deterministically and auditably.

    Attributes
    ----------
    execution_id : str
        Globally unique execution identifier (UUID hex).
    request_id : str
        Originating client or task request identifier.
    tenant_id : str
        Tenant identifier for multi-tenant isolation.
    user_id : str
        Authenticated user or service identity.
    capability_id : str
        Target canonical capability ID from CapabilityRegistry.
    capability_version : str
        Contract version of the requested capability.
    input : Any
        Input parameters, SystemSpec, or study-specific configuration.
    system_snapshot : dict[str, Any] | None
        Optional serialized snapshot of the power system topology at execution time.
    provider_policy : str | dict[str, Any] | None
        Provider selection policy (e.g. 'internal_python', 'windows_etap_com').
    execution_policy : str | dict[str, Any] | None
        Execution constraints (timeout, retry limits, circuit breaker settings).
    approval_context : dict[str, Any] | None
        Maker-checker approval details (approver_id, approval_timestamp, stamp).
    idempotency_key : str
        Key to prevent duplicate execution across retries.
    trace_id : str
        Distributed tracing identifier (W3C / OpenTelemetry).
    metadata : dict[str, Any]
        Supplementary operational tags, session IDs, and client telemetry.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    execution_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Globally unique execution identifier",
    )
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Originating request identifier",
    )
    tenant_id: str = Field(default="default", description="Tenant identifier")
    user_id: str = Field(default="anonymous", description="User identifier")
    user_role: str = Field(default="engineer", description="Authenticated user or service role")
    capability_id: str = Field(..., description="Target capability identifier")
    capability_version: str = Field(default="1.0.0", description="Capability contract version")
    input: Any = Field(default_factory=dict, description="Engineering study input or payload")
    system_snapshot: Optional[dict[str, Any]] = Field(
        default=None, description="System topology snapshot"
    )
    provider_policy: Optional[Any] = Field(
        default=None, description="Provider resolution policy"
    )
    execution_policy: Optional[Any] = Field(
        default=None, description="Execution parameters policy"
    )
    approval_context: Optional[dict[str, Any]] = Field(
        default=None, description="Maker-checker approval record"
    )
    idempotency_key: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Idempotency key for replay prevention",
    )
    trace_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Distributed tracing identifier",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Supplementary metadata and tags"
    )

    def get_parameters(self) -> dict[str, Any]:
        """Extract study parameters dictionary from input."""
        if isinstance(self.input, dict):
            if "parameters" in self.input and isinstance(self.input["parameters"], dict):
                return dict(self.input["parameters"])
            return dict(self.input)
        if hasattr(self.input, "parameters") and isinstance(self.input.parameters, dict):
            return dict(self.input.parameters)
        return {}

    def get_system(self) -> Any:
        """Extract power system model or spec from input."""
        if isinstance(self.input, dict):
            return self.input.get("system") or self.input.get("system_spec")
        if hasattr(self.input, "system"):
            return self.input.system
        if hasattr(self.input, "system_spec"):
            return self.input.system_spec
        return None

    @classmethod
    def from_study_request(
        cls,
        study_request: Any,
        user_id: str = "anonymous",
        tenant_id: str = "default",
        user_role: str = "engineer",
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExecutionRequest:
        """Create an ExecutionRequest from an existing StudyRequest for seamless integration."""
        raw_capability_id = getattr(study_request, "study_type", "load_flow")
        alias_map = {
            "fault": "short_circuit",
            "fault_analysis": "short_circuit",
            "coordination": "protection_coordination",
            "harmonic": "harmonic_analysis",
            "opf": "optimal_power_flow",
            "protection": "protection_coordination",
        }
        capability_id = alias_map.get(raw_capability_id, raw_capability_id)
        params = dict(getattr(study_request, "parameters", {}) or {})
        system = getattr(study_request, "system", None) or getattr(study_request, "system_spec", None)
        if system is not None:
            from core_model.specs import SystemSpec
            if isinstance(system, SystemSpec):
                from services.study_service import _build_system_from_spec
                system = _build_system_from_spec(system)
        if capability_id in ("short_circuit", "fault", "fault_analysis"):
            if "bus_id" not in params and system:
                buses = getattr(system, "buses", None) or (system.get("buses") if isinstance(system, dict) else None)
                if buses:
                    if isinstance(buses, dict):
                        first_bus = next(iter(buses.values()))
                    elif isinstance(buses, (list, tuple)):
                        first_bus = buses[0]
                    else:
                        first_bus = None
                    bid = getattr(first_bus, "bus_id", None) if not isinstance(first_bus, dict) else first_bus.get("bus_id")
                    if bid is not None:
                        params["bus_id"] = bid
        elif capability_id == "arc_flash":
            if "voltage_kv" not in params:
                params["voltage_kv"] = 13.8
            if "bolted_fault_current_ka" not in params:
                params["bolted_fault_current_ka"] = 20.0
            if "arc_duration_sec" not in params:
                params["arc_duration_sec"] = 0.1
            if "working_distance_mm" not in params:
                params["working_distance_mm"] = 610.0
        elif capability_id in ("protection_coordination", "coordination", "protection"):
            if "upstream_relay_id" not in params:
                params["upstream_relay_id"] = 1
            if "downstream_relay_id" not in params:
                params["downstream_relay_id"] = 2
        task_id = getattr(study_request, "task_id", None) or uuid.uuid4().hex
        pe_stamp = getattr(study_request, "pe_stamp", None)

        input_payload: dict[str, Any] = {
            "parameters": params,
            "system": system,
            "use_etap": getattr(study_request, "use_etap", False),
            "etap_project_path": getattr(study_request, "etap_project_path", None),
        }

        approval = None
        if pe_stamp:
            approval = {"pe_stamp": pe_stamp, "approved": True}

        return cls(
            request_id=task_id,
            user_id=user_id,
            tenant_id=tenant_id,
            user_role=user_role,
            capability_id=capability_id,
            input=input_payload,
            approval_context=approval,
            trace_id=trace_id or uuid.uuid4().hex,
            idempotency_key=idempotency_key or uuid.uuid4().hex,
            metadata=metadata or {},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Canonical Execution Result (Phase 4 / Phase 5 Output Envelope)
# ─────────────────────────────────────────────────────────────────────────────

class CanonicalExecutionResult(BaseModel):
    """Canonical Execution Result contract (Phase 4 & Phase 5).

    Standard result envelope returned by all execution engines across the platform.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    execution_id: str
    request_id: str
    capability_id: str
    tenant_id: str
    user_id: str
    capability_version: str = "1.0.0"
    executor_kind: str = "native"
    provider: str = "native"
    solver: str = ""
    engine_version: str = "unknown"
    input_snapshot_hash: str = ""
    system_snapshot_hash: str = ""
    parameter_hash: str = ""
    status: str = "completed"  # completed, failed, rejected, idempotent_replay
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation_status: str = "passed"  # passed, failed, warning
    validation_report: dict[str, Any] = Field(default_factory=dict)
    risk_class: str = "low"
    risk_score: float = 0.0
    risk_assessment: dict[str, Any] = Field(default_factory=dict)
    audit_context: dict[str, Any] = Field(default_factory=dict)
    execution_time_sec: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace_id: str = ""
    task_id: str = ""
    result_id: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    approval_state: Optional[str] = None
    idempotent_replay: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    authoritative: bool = True
    execution_path: str = "CANONICAL_PRODUCTION"

    @model_validator(mode="after")
    def enforce_authoritative_boundary(self) -> CanonicalExecutionResult:
        """Enforce strict boundary: INTERNAL_NON_AUTHORITATIVE can never masquerade as authoritative production output."""
        data_exec_path = self.data.get("execution_path") if isinstance(self.data, dict) else None
        prov_exec_path = self.provenance.get("execution_path") if isinstance(self.provenance, dict) else None
        data_auth = self.data.get("authoritative") if isinstance(self.data, dict) else None
        prov_auth = self.provenance.get("authoritative") if isinstance(self.provenance, dict) else None

        if (
            data_exec_path in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE")
            or prov_exec_path in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE")
            or data_auth is False
            or prov_auth is False
            or self.execution_path in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE")
            or not self.authoritative
        ):
            self.authoritative = False
            effective_path = data_exec_path or prov_exec_path or self.execution_path
            if effective_path not in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE"):
                effective_path = "INTERNAL_NON_AUTHORITATIVE"
            self.execution_path = effective_path
            if isinstance(self.data, dict):
                self.data["authoritative"] = False
                self.data["execution_path"] = effective_path
            if isinstance(self.provenance, dict):
                self.provenance["authoritative"] = False
                self.provenance["execution_path"] = effective_path
            if isinstance(self.audit_context, dict):
                self.audit_context["authoritative"] = False
                self.audit_context["execution_path"] = effective_path
        return self

    def to_study_result(self, study_type: str | None = None) -> Any:
        """Convert CanonicalExecutionResult to legacy StudyResult for API backwards compatibility."""
        from core.bootstrap import _to_jsonable
        from core_model.specs import StudyResult

        clean_data = _to_jsonable(self.data)
        st = study_type or self.capability_id

        # In legacy StudyResult contract, execution succeeded if simulation produced data
        # even if physical solution did not converge, provided status was not rejected/aborted.
        legacy_success = self.success
        if not legacy_success and self.data and isinstance(self.data, dict):
            if self.data.get("converged") is False and self.status not in ("rejected", "unauthorized", "unsupported"):
                legacy_success = True

        return StudyResult(
            study_type=st,
            success=legacy_success,
            data=clean_data,
            results=clean_data,
            warnings=self.warnings,
            errors=self.errors,
            execution_time_sec=self.execution_time_sec,
            trace_id=self.trace_id,
            task_id=self.task_id or self.request_id,
            execution_id=self.execution_id,
            request_id=self.request_id,
            tenant_id=self.tenant_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            provider=self.provider,
            executor_kind=self.executor_kind,
            solver=self.solver,
            engine_version=self.engine_version,
            input_snapshot_hash=self.input_snapshot_hash,
            system_snapshot_hash=self.system_snapshot_hash,
            parameter_hash=self.parameter_hash,
            validation_status=self.validation_status in ("passed", True, 1),
            validation_report=self.validation_report,
            risk_class=self.risk_class,
            risk_score=self.risk_score,
            provenance=self.provenance,
            result_id=self.result_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            approval_state=self.approval_state,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Common Executor Interface Contract
# ─────────────────────────────────────────────────────────────────────────────

class IEngineeringExecutor(ABC):
    """Common engineering executor interface (Phase 5).

    Every executor kind (native, agent, etap, external, composite) adheres
    to this protocol while preserving its independent computational engine.
    """

    @abstractmethod
    async def execute(self, request: ExecutionRequest) -> CanonicalExecutionResult:
        """Execute request under canonical contract."""
        raise NotImplementedError


def is_authoritative_production_result(result: Any) -> bool:
    """Deterministic predicate checking if an execution result is canonically authoritative for production use."""
    if not getattr(result, "success", False):
        return False
    if not getattr(result, "authoritative", True):
        return False
    if getattr(result, "execution_path", "") in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE"):
        return False
    prov = getattr(result, "provenance", {}) or {}
    if (
        prov.get("execution_path") in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE")
        or prov.get("authoritative") is False
    ):
        return False
    data = getattr(result, "data", {}) or {}
    return not (
        data.get("execution_path") in ("INTERNAL_NON_AUTHORITATIVE", "LEGACY_NON_AUTHORITATIVE")
        or data.get("authoritative") is False
    )

