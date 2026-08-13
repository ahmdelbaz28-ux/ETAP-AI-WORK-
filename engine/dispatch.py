"""
Unified Study Dispatch Table
=============================

Single source of truth for routing study requests to their handlers across
both runtimes (ADR-0002). Covers all 16 canonical ``StudyType`` values
(ADR-0001) plus the three special study types used by the ETAP skill pipeline.

Each entry maps a canonical ``study_type`` string to a ``StudyRegistration``
that declares:

- ``handler_type``: One of
    - ``"native"``  — handled synchronously by ``PowerSystemEngine``
    - ``"agent"``   — handled by a ``BaseAgent`` subclass in the Python runtime
    - ``"external"`` — handled by the Engineering Service API (HTTP)

- ``handler``: Handler identifier (module path or class name or endpoint)

- ``requires_system``: Whether the study needs a ``System`` model

- ``required_params``: Tuple of parameter names that must be present in the
  request ``parameters`` dict before dispatch

Native types are the 4 already handled by ``PowerSystemEngine.run_study``;
they are kept in this table for completeness and discoverability. The
``_STUDY_REGISTRY`` in ``engine/engine.py`` is retained as a deprecation
shim but new code should consult ``STUDY_DISPATCH`` here.

Agent-routed types reuse the ``STUDY_TYPE_AGENT_MAP`` from
``agents/__init__.py`` so there is a single mapping from study type to
agent class — no duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents import STUDY_TYPE_AGENT_MAP
from agents.models import StudyType

# Re-export so callers can iterate all keys without importing separately.
__all__ = ["StudyRegistration", "STUDY_DISPATCH", "ALL_STUDY_TYPES"]

# Canonical snake_case keys (ADR-0001). All StudyType enum values
# plus the one extra special type used by the ETAP skill pipeline.
ALL_STUDY_TYPES: tuple[str, ...] = tuple(st.value for st in StudyType) + (
    "ahmed_etap_orchestration",
)


@dataclass(frozen=True)
class StudyRegistration:
    """Registration entry for a single study type in the dispatch table.

    Attributes
    ----------
    handler_type
        ``"native"``  — PowerSystemEngine (Python synchronous)
        ``"agent"``   — BaseAgent subclass (Python, may call LLM or engine)
        ``"external"`` — Engineering Service HTTP endpoint (TS/Mastra)
    handler
        For ``"native"``: the ``PowerSystemEngine`` method name (e.g.
        ``"run_load_flow"``). For ``"agent"``: the fully-qualified class
        path or the class itself. For ``"external"``: the HTTP endpoint.
    requires_system
        If True, the study requires a populated ``System`` object in the
        request parameters.
    required_params
        Parameter keys that must be present (non-None) in the request's
        ``parameters`` dict before dispatch.
    """

    handler_type: Literal["native", "agent", "external"]
    handler: str
    requires_system: bool
    required_params: tuple[str, ...]


# ---------------------------------------------------------------------------
# Native handler method names — mirror the 4-entry _STUDY_REGISTRY in engine.py
# ---------------------------------------------------------------------------
_NATIVE_METHODS: dict[str, str] = {
    "load_flow": "run_load_flow",
    "short_circuit": "run_fault_analysis",
    "protection_coordination": "run_protection_coordination",
    "arc_flash": "run_arc_flash",
}

# ---------------------------------------------------------------------------
# Agent class names — mirror STUDY_TYPE_AGENT_MAP (single source of truth
# is agents/__init__.py:STUDY_TYPE_AGENT_MAP; we reference the classes here
# so the dispatch table is self-describing without importing lazily).
# ---------------------------------------------------------------------------
# Map study_type string → agent class name for agent-routed studies.
# This mirrors STUDY_TYPE_AGENT_MAP keys/values but uses string class names
# to avoid forcing eager imports of all 12 agent modules at table-build time.
# The StudyExecutor resolves the class via STUDY_TYPE_AGENT_MAP at dispatch.


def _build_dispatch() -> dict[str, StudyRegistration]:
    """Build the complete dispatch table from the canonical StudyType enum
    and the STUDY_TYPE_AGENT_MAP in agents/__init__.py."""
    dispatch: dict[str, StudyRegistration] = {}

    # Native studies — handled by PowerSystemEngine.
    native_specs: dict[str, tuple[bool, tuple[str, ...]]] = {
        "load_flow": (True, ()),
        "short_circuit": (True, ("bus_id",)),
        "arc_flash": (
            False,
            ("voltage_kv", "bolted_fault_current_ka", "arc_duration_sec", "working_distance_mm"),
        ),
        "protection_coordination": (
            True,
            ("upstream_relay_id", "downstream_relay_id", "fault_currents"),
        ),
    }
    for study_type, (requires_system, required_params) in native_specs.items():
        dispatch[study_type] = StudyRegistration(
            handler_type="native",
            handler=_NATIVE_METHODS[study_type],
            requires_system=requires_system,
            required_params=required_params,
        )

    # Agent-routed studies — derive from STUDY_TYPE_AGENT_MAP.
    # Skip the 4 native types already handled above (they appear in
    # STUDY_TYPE_AGENT_MAP because agent classes exist for DI, but the
    # native PowerSystemEngine path takes priority).
    native_values = set(native_specs.keys())
    for study_type_enum, agent_cls in STUDY_TYPE_AGENT_MAP.items():
        if study_type_enum.value in native_values:
            continue
        handler = f"{agent_cls.__module__}.{agent_cls.__name__}"
        requires_system = study_type_enum not in (
            StudyType.ETAP_EXPERT,
            StudyType.ETAP_GUI,
        )
        dispatch[study_type_enum.value] = StudyRegistration(
            handler_type="agent",
            handler=handler,
            requires_system=requires_system,
            required_params=(),
        )

    # Special study types not in the StudyType enum
    dispatch["ahmed_etap_orchestration"] = StudyRegistration(
        handler_type="external",
        handler="AhmedETAPSkillAgent",
        requires_system=False,
        required_params=(),
    )

    return dispatch


STUDY_DISPATCH: dict[str, StudyRegistration] = _build_dispatch()
