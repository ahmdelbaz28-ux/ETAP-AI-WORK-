"""
contracts/ai/__init__.py — AI Execution Contract namespace.

All contract classes live in contracts.ai.models and are re-exported here for
convenience.  Import them as::

    from contracts.ai import ExecutionRequestContract, StudyResultContract, ...

The Contract suffix distinguishes these canonical wire types from the
domain models that happen to share the same short name:

    ExecutionPlanContract   ≠  engine.scalability.ExecutionPlan         (dataclass)
    ExecutionContextContract ≠ src/core/types.ts:ExecutionContext        (TS interface)
    ValidationResultContract ≠ digital_twin.validation_gateway.ValidationResult  (dataclass)
    StudyResultContract     ≠  core_model.specs.StudyResult              (Pydantic)
"""

from __future__ import annotations

from contracts.ai.models import (
    ApprovalStateContract,
    EvidenceContract,
    ExecutionContextContract,
    ExecutionPlanContract,
    ExecutionRequestContract,
    ExecutionTraceContract,
    PlanNodeContract,
    ProvenanceContract,
    StudyResultContract,
    ValidationResultContract,
)

__all__ = [
    "ApprovalStateContract",
    "EvidenceContract",
    "ExecutionContextContract",
    "ExecutionPlanContract",
    "ExecutionRequestContract",
    "ExecutionTraceContract",
    "PlanNodeContract",
    "ProvenanceContract",
    "StudyResultContract",
    "ValidationResultContract",
]
