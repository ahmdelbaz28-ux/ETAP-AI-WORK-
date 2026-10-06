"""
Unified Study Dispatch Table
=============================

Authoritative projection and adapter over Canonical CapabilityRegistry (ADR-0002, Phase 8).
Routes study requests to their handlers across runtimes.
Covers all 17 canonical StudyType values plus specialized orchestration types.

Each entry maps a canonical study_type string to a StudyRegistration that declares:
- handler_type: One of "native", "agent", "external"
- handler: Handler identifier (PowerSystemEngine method name, agent class, or bridge)
- requires_system: Whether the study needs a System model
- required_params: Tuple of required parameter names
- executor_kind: Canonical ExecutorKind ("native", "agent", "etap", "external_service", "composite")
- capability_id: Canonical capability identifier
- description: Human-readable description
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.models import StudyType
from engine.capability_registry import get_capability_registry

# Re-export so callers can iterate all keys without importing separately.
__all__ = ["StudyRegistration", "STUDY_DISPATCH", "ALL_STUDY_TYPES"]

# Canonical snake_case keys (ADR-0001). All StudyType enum values
# plus the special orchestration type.
ALL_STUDY_TYPES: tuple[str, ...] = tuple(st.value for st in StudyType) + (
    "ahmed_etap_orchestration",
)


@dataclass(frozen=True)
class StudyRegistration:
    """Registration entry for a single study type in the dispatch table.

    Projected directly from Canonical CapabilityRegistry (Phase 8).

    Attributes
    ----------
    handler_type : Literal["native", "agent", "external"]
        High-level handler classification (backward compatible).
    handler : str
        For 'native': method name in StudyExecutor / PowerSystemEngine (e.g. 'run_load_flow').
        For 'agent': specialist agent class or import path.
        For 'etap': ETAP provider study identifier.
        For 'external_service': external service / evaluator bridge identifier.
        For 'composite': composite multi-agent orchestrator identifier.
    requires_system : bool
        Whether this study requires a populated System model.
    required_params : tuple[str, ...]
        Tuple of mandatory parameter keys.
    executor_kind : str
        Canonical ExecutorKind from CapabilityRegistry ('native', 'agent', 'etap', 'external_service', 'composite').
    capability_id : str
        Canonical capability ID in CapabilityRegistry.
    description : str
        Capability description.
    """

    handler_type: Literal["native", "agent", "external"]
    handler: str
    requires_system: bool
    required_params: tuple[str, ...]
    executor_kind: str = "native"
    capability_id: str = ""
    description: str = ""


def _build_dispatch() -> dict[str, StudyRegistration]:
    """Build the complete dispatch table as an authoritative projection
    from the canonical CapabilityRegistry (Phases 2, 3 & 8).

    Separates responsibilities:
    - CapabilityRegistry is the single source of truth for capabilities, metadata, and lifecycle.
    - STUDY_DISPATCH is an adapter/projection mapping each capability to its execution handler.

    Routes each study type to the correct handler based on executor_kind:
    - native: maps to StudyExecutor handler method (e.g. run_load_flow)
    - agent: maps to specialist agent class from CapabilityRegistry
    - etap: maps to ETAP provider execution bridge
    - external_service: maps to dedicated evaluator / external bridge
    - composite: maps to composite skill orchestration agent
    """
    registry = get_capability_registry()
    dispatch: dict[str, StudyRegistration] = {}

    for study_type, cap in registry.get_dispatch_capabilities().items():
        ek = cap.executor_kind.value if hasattr(cap.executor_kind, "value") else str(cap.executor_kind)

        if ek == "native":
            handler_type: Literal["native", "agent", "external"] = "native"
            handler = cap.handler
        elif ek == "agent":
            handler_type = "agent"
            handler = cap.handler
        elif ek == "etap":
            handler_type = "external"
            handler = cap.handler or "etap_integration.etap_provider"
        elif ek == "composite":
            handler_type = "external"
            handler = cap.handler or "AhmedETAPSkillAgent"
        elif ek == "external_service":
            handler_type = "external"
            handler = cap.handler or "external_service_bridge"
        else:
            handler_type = "external"
            handler = cap.handler

        dispatch[study_type] = StudyRegistration(
            handler_type=handler_type,
            handler=handler,
            requires_system=cap.requires_system,
            required_params=cap.required_params,
            executor_kind=ek,
            capability_id=cap.capability_id,
            description=cap.description,
        )

    return dispatch


STUDY_DISPATCH: dict[str, StudyRegistration] = _build_dispatch()

