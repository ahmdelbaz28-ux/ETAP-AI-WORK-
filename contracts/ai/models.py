"""
contracts/ai/models.py — Nine Typed AI Execution Contracts (M2.2).

These Pydantic models define the canonical wire format for the AI execution
pipeline across Python and TypeScript runtimes.

Name Disambiguation (M2.1)
--------------------------
Each contract carries the ``Contract`` suffix to avoid shadowing existing
domain classes with identical short names:

+---------------------------+--------------------------------------------------+
| Contract class            | Colliding existing symbol                        |
+===========================+==================================================+
| ExecutionPlanContract     | engine.scalability.ExecutionPlan (dataclass)     |
| ExecutionContextContract  | src/core/types.ts:ExecutionContext (TS interface)|
| ValidationResultContract  | digital_twin.validation_gateway.ValidationResult |
| StudyResultContract       | core_model.specs.StudyResult (Pydantic)          |
+---------------------------+--------------------------------------------------+

Standards & Sources
-------------------
- Provenance fields: IEEE 1584-2018 §5 (traceability chain)
- Approval state: IEC 62351 §8 (maker-checker dual control)
- Trace contract: OpenTelemetry trace context propagation
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ApprovalStatus(str, Enum):
    """Status of a dual-control approval gate (maker-checker)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BYPASSED = "bypassed"  # only for non-critical auto-approvals


class NodeStatus(str, Enum):
    """Execution status of a single plan node."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# M2.2 — Nine Typed Contracts
# ---------------------------------------------------------------------------


class ProvenanceContract(BaseModel):
    """Tracks the authoritative source and standard for any computed value.

    Based on IEEE 1584-2018 §5 traceability requirements.
    """

    source: str = Field(
        ...,
        description="Origin of the value: 'user_input', 'computed', 'project_data', or 'standard'.",
    )
    ref: str = Field(
        default="",
        description="Specific reference, e.g. 'IEC 60909:2016 §4.3.1' or task_id.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level 0.0–1.0; 1.0 = deterministic engine output.",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="ISO-8601 UTC timestamp when the value was produced.",
    )


class EvidenceContract(BaseModel):
    """Single piece of evidence supporting a computation or decision.

    Mandatory for fail-closed tool execution (Chat-First v3.0 §5.2).
    """

    key: str = Field(..., description="Short label identifying this evidence item.")
    value: Any = Field(..., description="The evidence value (numeric, string, or nested dict).")
    provenance: ProvenanceContract = Field(
        ...,
        description="Traceability chain for this evidence item.",
    )
    standard_clause: str = Field(
        default="",
        description="Normative clause (e.g. 'IEC 60909:2016 §4.3') that governs this value.",
    )


class PlanNodeContract(BaseModel):
    """Single node in an AI execution plan DAG.

    Represents one atomic study step with its dependencies and evidence.
    """

    node_id: str = Field(..., description="Unique identifier for this plan node.")
    study_type: str = Field(..., description="Canonical study type key (ADR-0001).")
    agent_id: str = Field(..., description="Target agent id from AGENT_REGISTRY.")
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of node_ids that must complete before this node runs.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Study parameters passed to the agent.",
    )
    status: NodeStatus = Field(default=NodeStatus.QUEUED)
    evidence: list[EvidenceContract] = Field(
        default_factory=list,
        description="Evidence items supporting parameters (fail-closed requirement).",
    )


class ExecutionPlanContract(BaseModel):
    """Structured DAG of study nodes to execute.

    Disambiguates from ``engine.scalability.ExecutionPlan`` (M2.1).
    """

    plan_id: str = Field(..., description="Globally unique plan identifier (UUID-4).")
    run_id: str = Field(..., description="Parent run identifier (UUID-4).")
    nodes: list[PlanNodeContract] = Field(..., description="Ordered list of plan nodes.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str = Field(default="", description="Human-readable plan description.")
    topological_order: list[str] = Field(
        default_factory=list,
        description="Topological sort of node_ids; empty means sequential execution.",
    )


class ExecutionContextContract(BaseModel):
    """Runtime context passed alongside an execution request.

    Disambiguates from ``src/core/types.ts:ExecutionContext`` (M2.1).
    Fields mirror the TypeScript interface in ``src/core/contracts/ai.ts``.
    """

    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation.")
    user_id: str = Field(..., description="Authenticated user identifier.")
    session_id: str = Field(default="", description="Current chat or API session id.")
    trace_id: str = Field(default="", description="OpenTelemetry trace id.")
    privacy_mode: bool = Field(
        default=False,
        description="If True, external LLM calls are blocked (PRIVACY_MODE_ACTIVE).",
    )
    source: str = Field(
        default="user_input",
        description="Provenance source label for fail-closed enforcement.",
    )


class ExecutionRequestContract(BaseModel):
    """Top-level AI execution request submitted to the Engineering Service.

    Wraps the plan and context into a single verifiable payload.
    """

    run_id: str = Field(..., description="Unique run identifier (UUID-4), generated by caller.")
    plan: ExecutionPlanContract
    context: ExecutionContextContract
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dry_run: bool = Field(
        default=False,
        description="If True, validate and plan but do not execute any studies.",
    )


class ValidationResultContract(BaseModel):
    """Result of a cross-runtime validation check.

    Disambiguates from ``digital_twin.validation_gateway.ValidationResult`` (M2.1).
    Used by the M2.4 registry sanity check and agent contract verification.
    """

    check_name: str = Field(..., description="Identifier of the validation rule.")
    passed: bool
    severity: str = Field(
        default="error",
        description="'error', 'warning', or 'info'.",
    )
    message: str = Field(default="")
    details: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StudyResultContract(BaseModel):
    """Wire result of a completed study node.

    Disambiguates from ``core_model.specs.StudyResult`` (M2.1).
    Adds the plan/run/node linkage required by M2.2 wire contract.
    """

    run_id: str = Field(..., description="Parent run identifier.")
    plan_id: str = Field(..., description="Parent plan identifier.")
    node_id: str = Field(..., description="Plan node that produced this result.")
    study_type: str = Field(..., description="Canonical study type key (ADR-0001).")
    agent_id: str = Field(..., description="Agent that executed this node.")
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    evidence: list[EvidenceContract] = Field(
        default_factory=list,
        description="Supporting evidence for computed values (IEEE 1584-2018 §5).",
    )
    execution_time_sec: float = Field(default=0.0)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalStateContract(BaseModel):
    """Dual-control maker-checker state for critical AI actions.

    Based on Chat-First v3.0 dual-control requirement (IEC 62351 §8).
    """

    action_id: str = Field(..., description="Unique identifier for the action requiring approval.")
    maker_id: str = Field(..., description="User who initiated (made) the action.")
    checker_id: Optional[str] = Field(
        default=None,
        description="User who approved or rejected; None if still pending.",
    )
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    action_type: str = Field(..., description="Type of action, e.g. 'execute_study', 'modify_config'.")
    payload_hash: str = Field(
        ...,
        description="SHA-256 hash of the action payload for integrity verification.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: Optional[datetime] = Field(default=None)
    reason: str = Field(default="", description="Checker's reason for approval or rejection.")


class ExecutionTraceContract(BaseModel):
    """Full execution trace for audit and observability.

    Captures the complete lifecycle of a run from request to completion,
    compatible with OpenTelemetry and Langfuse trace propagation.
    """

    run_id: str = Field(..., description="Run identifier (matches ExecutionRequestContract.run_id).")
    plan_id: str = Field(..., description="Plan identifier.")
    context: ExecutionContextContract
    node_results: list[StudyResultContract] = Field(
        default_factory=list,
        description="Results for each executed plan node, in completion order.",
    )
    validations: list[ValidationResultContract] = Field(
        default_factory=list,
        description="Contract and registry validations run before/after execution.",
    )
    approval: Optional[ApprovalStateContract] = Field(
        default=None,
        description="Maker-checker approval state if the run required dual control.",
    )
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = Field(default=None)
    total_execution_time_sec: float = Field(default=0.0)
    overall_success: bool = Field(default=False)
    langfuse_trace_url: str = Field(
        default="",
        description="Langfuse observability URL for this run (empty if tracing disabled).",
    )
