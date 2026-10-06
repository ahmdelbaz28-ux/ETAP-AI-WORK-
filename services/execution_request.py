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

from pydantic import BaseModel, ConfigDict, Field

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
        return None

    @classmethod
    def from_study_request(
        cls,
        study_request: Any,
        user_id: str = "anonymous",
        tenant_id: str = "default",
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExecutionRequest:
        """Create an ExecutionRequest from an existing StudyRequest for seamless integration."""
        capability_id = getattr(study_request, "study_type", "load_flow")
        params = getattr(study_request, "parameters", {})
        system = getattr(study_request, "system", None)
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
    engine_version: str = "2.1.0"
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

    def to_study_result(self) -> Any:
        """Convert CanonicalExecutionResult to legacy StudyResult for API backwards compatibility."""
        from core_model.specs import StudyResult

        return StudyResult(
            success=self.success,
            data=self.data,
            results=self.data,
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
