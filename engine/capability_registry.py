"""
engine/capability_registry.py — Canonical Capability Contract & Unified Registry.

Phase 2 & Phase 3 authoritative implementation.
Single source of truth for all engineering capabilities, specialist agents,
study executors, and external bridges across the platform.

All dispatch tables (engine.dispatch.STUDY_DISPATCH), agent mappings
(agents.STUDY_TYPE_AGENT_MAP, agents.ETAP_EXECUTION_AGENT_MAP), and namespace
declarations (agents.registry.CANONICAL_AGENT_KEYS) are projections derived
from this canonical registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Canonical Capability Contract
# ─────────────────────────────────────────────────────────────────────────────

class ExecutorKind(str, Enum):
    """Execution model for an engineering capability."""

    NATIVE = "native"
    AGENT = "agent"
    ETAP = "etap"
    EXTERNAL_SERVICE = "external_service"
    COMPOSITE = "composite"


class LifecycleStatus(str, Enum):
    """Authoritative lifecycle status of a capability."""

    EXPERIMENTAL = "experimental"
    INTERNAL = "internal"
    PILOT = "pilot"
    PRODUCTION = "production"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CapabilityDefinition:
    """Canonical Capability Definition contract (Phase 2).

    Attributes
    ----------
    capability_id : str
        Unique identifier for the capability (e.g. 'load_flow', 'breaker_duty').
    study_type : str | None
        Associated canonical StudyType value or dispatch key, if applicable.
    executor_kind : ExecutorKind | str
        Execution model: native, agent, etap, external_service, composite.
    input_schema : Any
        Input parameter schema specification or model definition.
    output_schema : Any
        Output result schema specification or return model.
    requires_system : bool
        Whether this capability requires a populated System/SystemSpec model.
    provider_policy : Any
        Execution provider selection policy (e.g. 'internal_python', 'etap_com').
    validation_policy : Any
        Pre/post-execution validation criteria and standards compliance rules.
    authorization_policy : Any
        Role-based access control or permission tier (e.g. 'engineer', 'admin').
    approval_policy : Any
        Maker-checker dual-control requirement or automated approval policy.
    feature_flag : str | None
        Feature flag governing activation, if gated.
    risk_class : str
        Operational risk level ('low', 'medium', 'high', 'critical').
    version : str
        Semantic version of the capability contract.
    lifecycle_status : LifecycleStatus | str
        Lifecycle status: production, pilot, internal, experimental, disabled, unavailable.
    handler : str
        Execution handler identifier (method name, class path, or endpoint).
    required_params : tuple[str, ...]
        Tuple of mandatory parameter names in request payload.
    agent_key : str | None
        Associated canonical agent key in agents.registry, if applicable.
    description : str
        Human-readable capability documentation.
    """

    capability_id: str
    study_type: str | None
    executor_kind: ExecutorKind | str
    input_schema: Any = None
    output_schema: Any = None
    requires_system: bool = False
    provider_policy: Any = "internal_python"
    validation_policy: Any = "standard_validation"
    authorization_policy: Any = "engineer"
    approval_policy: Any = "standard"
    feature_flag: str | None = None
    risk_class: str = "low"
    version: str = "1.0.0"
    lifecycle_status: LifecycleStatus | str = LifecycleStatus.PRODUCTION
    handler: str = ""
    required_params: tuple[str, ...] = ()
    agent_key: str | None = None
    description: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Canonical Capability Registry
# ─────────────────────────────────────────────────────────────────────────────

class CapabilityRegistry:
    """Unified Canonical Capability Registry.

    Promoted to single source of truth for the platform. Manages all
    CapabilityDefinition instances and produces projections for dispatch
    and agent routing.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._study_type_index: dict[str, str] = {}
        self._agent_key_index: dict[str, str] = {}
        self._aliases: dict[str, str] = {
            "harmonic": "harmonic_analysis",
            "opf": "optimal_power_flow",
            "protection": "protection_coordination",
        }

    def register(self, cap: CapabilityDefinition) -> None:
        """Register a canonical capability definition."""
        if cap.capability_id in self._capabilities:
            raise ValueError(f"Capability '{cap.capability_id}' already registered")
        self._capabilities[cap.capability_id] = cap
        if cap.study_type:
            self._study_type_index[cap.study_type] = cap.capability_id
        if cap.agent_key:
            self._agent_key_index[cap.agent_key] = cap.capability_id

    def get_capability_definition(self, capability_id: str) -> CapabilityDefinition:
        """Lookup capability definition by capability_id (or alias)."""
        if capability_id in self._capabilities:
            return self._capabilities[capability_id]
        resolved = self._aliases.get(capability_id)
        if resolved and resolved in self._capabilities:
            return self._capabilities[resolved]
        raise KeyError(f"Capability '{capability_id}' not found in canonical registry")

    def get(self, capability_id: str, default: Any = None) -> CapabilityDefinition | None:
        """Lookup capability definition or return default."""
        try:
            return self.get_capability_definition(capability_id)
        except KeyError:
            return default

    def get_by_study_type(self, study_type: str) -> CapabilityDefinition | None:
        """Lookup capability definition by study type string."""
        cap_id = self._study_type_index.get(study_type)
        if cap_id:
            return self._capabilities[cap_id]
        return None

    def get_by_agent_key(self, agent_key: str) -> CapabilityDefinition | None:
        """Lookup capability definition by agent key."""
        resolved = self._aliases.get(agent_key, agent_key)
        cap_id = self._agent_key_index.get(resolved)
        if cap_id:
            return self._capabilities[cap_id]
        return None

    def list_capabilities(self) -> list[CapabilityDefinition]:
        """Return all registered capability definitions."""
        return list(self._capabilities.values())

    def all_capabilities(self) -> dict[str, CapabilityDefinition]:
        """Return dictionary of all registered capability definitions."""
        return dict(self._capabilities)

    # ── Projections for Architecture Compatibility ────────────────────────

    def get_dispatch_capabilities(self) -> dict[str, CapabilityDefinition]:
        """Return the 20 dispatchable capabilities for engine.dispatch.STUDY_DISPATCH."""
        return {
            cap.study_type: cap
            for cap in self._capabilities.values()
            if cap.study_type is not None
        }

    def to_canonical_agent_keys(self) -> frozenset[str]:
        """Project the 27 canonical agent keys."""
        return frozenset(
            cap.agent_key
            for cap in self._capabilities.values()
            if cap.agent_key is not None
        )

    def to_agent_key_aliases(self) -> Mapping[str, str]:
        """Project the backward-compatible agent key aliases."""
        return dict(self._aliases)

    def to_study_type_mapping(self) -> dict[str, str]:
        """Project study_type string to agent_key mapping."""
        mapping: dict[str, str] = {}
        for cap in self._capabilities.values():
            if cap.study_type and cap.agent_key:
                mapping[cap.study_type] = cap.agent_key
            elif cap.agent_key:
                mapping[cap.agent_key] = cap.agent_key
        # Explicit mapping for ahmed_etap_orchestration
        mapping["ahmed_etap_orchestration"] = "ahmed_etap"
        return mapping

    def to_study_type_agent_map(self) -> dict[Any, Any]:
        """Project StudyType enum to BaseAgent class mapping for agents.__init__.py."""
        from agents.arc_flash_agent import ArcFlashAgent
        from agents.battery_storage_agent import BatteryStorageAgent
        from agents.cable_sizing_agent import CableSizingAgent
        from agents.digital_twin_agent import DigitalTwinAgent
        from agents.earth_grid_agent import EarthGridAgent
        from agents.etap_expert_agent import ETAPExpertAgent
        from agents.etap_gui_agent import ETAPGUIAgent
        from agents.models import StudyType
        from agents.motor_starting_agent import MotorStartingAgent
        from agents.orchestrator import (
            HarmonicAnalysisAgent,
            LoadFlowAgent,
            OptimalPowerFlowAgent,
            ProtectionCoordinationAgent,
            ShortCircuitAgent,
        )
        from agents.renewable_agent import RenewableAgent
        from agents.scada_agent import SCADAAgent
        from agents.stability_agent import StabilityAgent

        class_map: dict[str, type] = {
            "load_flow": LoadFlowAgent,
            "short_circuit": ShortCircuitAgent,
            "harmonic_analysis": HarmonicAnalysisAgent,
            "optimal_power_flow": OptimalPowerFlowAgent,
            "protection_coordination": ProtectionCoordinationAgent,
            "motor_starting": MotorStartingAgent,
            "transient_stability": StabilityAgent,
            "arc_flash": ArcFlashAgent,
            "cable_sizing": CableSizingAgent,
            "earth_grid": EarthGridAgent,
            "renewable_integration": RenewableAgent,
            "battery_storage": BatteryStorageAgent,
            "scada": SCADAAgent,
            "digital_twin": DigitalTwinAgent,
            "etap_expert": ETAPExpertAgent,
            "etap_gui": ETAPGUIAgent,
        }
        res: dict[Any, Any] = {}
        for st in StudyType:
            if st.value in class_map:
                res[st] = class_map[st.value]
        return res

    def to_etap_execution_agent_map(self) -> dict[Any, Any]:
        """Project StudyType enum to ETAPExecutionAgent mapping for provider execution."""
        from agents.models import StudyType
        from agents.orchestrator import ETAPExecutionAgent

        supported_studies = (
            StudyType.LOAD_FLOW,
            StudyType.SHORT_CIRCUIT,
            StudyType.ARC_FLASH,
            StudyType.HARMONIC_ANALYSIS,
            StudyType.OPTIMAL_POWER_FLOW,
            StudyType.MOTOR_STARTING,
            StudyType.PROTECTION_COORDINATION,
            StudyType.TRANSIENT_STABILITY,
        )
        return dict.fromkeys(supported_studies, ETAPExecutionAgent)


# ─────────────────────────────────────────────────────────────────────────────
# Factory & Built-in Canonical Population
# ─────────────────────────────────────────────────────────────────────────────

def _populate_canonical_registry(registry: CapabilityRegistry) -> None:
    """Populate registry with all canonical capabilities established in Batch 1."""

    # 1. Native Study Capabilities (4)
    registry.register(
        CapabilityDefinition(
            capability_id="load_flow",
            study_type="load_flow",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_load_flow",
            requires_system=True,
            required_params=(),
            agent_key="load_flow",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Newton-Raphson / Fast Decoupled AC/DC power flow analysis per IEEE 3002.7.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="short_circuit",
            study_type="short_circuit",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_fault_analysis",
            requires_system=True,
            required_params=("bus_id",),
            agent_key="short_circuit",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Three-phase and unbalanced short-circuit analysis per IEC 60909.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="arc_flash",
            study_type="arc_flash",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_arc_flash",
            requires_system=False,
            required_params=(
                "voltage_kv",
                "bolted_fault_current_ka",
                "arc_duration_sec",
                "working_distance_mm",
            ),
            agent_key="arc_flash",
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Arc flash hazard and incident energy assessment per IEEE 1584-2018.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="protection_coordination",
            study_type="protection_coordination",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_protection_coordination",
            requires_system=True,
            required_params=("upstream_relay_id", "downstream_relay_id", "fault_currents"),
            agent_key="protection_coordination",
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Relay coordination and time-current curve selectivity verification per IEC 60255.",
        )
    )

    # 2. Agent-Routed Study Capabilities (13)
    registry.register(
        CapabilityDefinition(
            capability_id="harmonic_analysis",
            study_type="harmonic_analysis",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.orchestrator.HarmonicAnalysisAgent",
            requires_system=True,
            required_params=(),
            agent_key="harmonic_analysis",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Harmonic distortion and resonance assessment per IEEE 519-2022.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="optimal_power_flow",
            study_type="optimal_power_flow",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.orchestrator.OptimalPowerFlowAgent",
            requires_system=True,
            required_params=(),
            agent_key="optimal_power_flow",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Optimal power flow economic dispatch and voltage optimization.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="motor_starting",
            study_type="motor_starting",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.motor_starting_agent.MotorStartingAgent",
            requires_system=True,
            required_params=(),
            agent_key="motor_starting",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Dynamic and static motor starting voltage dip assessment per IEEE 399.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="transient_stability",
            study_type="transient_stability",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.stability_agent.StabilityAgent",
            requires_system=True,
            required_params=(),
            agent_key="transient_stability",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Transient stability and critical clearing time evaluation per IEEE 399.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="cable_sizing",
            study_type="cable_sizing",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.cable_sizing_agent.CableSizingAgent",
            requires_system=True,
            required_params=(),
            agent_key="cable_sizing",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Cable ampacity, derating, and voltage drop sizing per IEC 60364.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="earth_grid",
            study_type="earth_grid",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.earth_grid_agent.EarthGridAgent",
            requires_system=True,
            required_params=(),
            agent_key="earth_grid",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Substation grounding grid design and step/touch potential per IEEE 80.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="renewable_integration",
            study_type="renewable_integration",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.renewable_agent.RenewableAgent",
            requires_system=True,
            required_params=(),
            agent_key="renewable_integration",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Distributed energy resource (PV/Wind) grid integration per IEEE 1547-2018.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="battery_storage",
            study_type="battery_storage",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.battery_storage_agent.BatteryStorageAgent",
            requires_system=True,
            required_params=(),
            agent_key="battery_storage",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Battery energy storage system (BESS) sizing and dispatch per IEC 62933.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="scada",
            study_type="scada",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.scada_agent.SCADAAgent",
            requires_system=True,
            required_params=(),
            agent_key="scada",
            risk_class="high",
            authorization_policy="lead_engineer",
            approval_policy="dual_control",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="SCADA integration, state estimation, and data mapping per IEC 61850.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="digital_twin",
            study_type="digital_twin",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.digital_twin_agent.DigitalTwinAgent",
            requires_system=True,
            required_params=(),
            agent_key="digital_twin",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.UNAVAILABLE,
            description="Real-time digital twin synchronization (fails closed until computational backend available).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="etap_expert",
            study_type="etap_expert",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.etap_expert_agent.ETAPExpertAgent",
            requires_system=False,
            required_params=(),
            agent_key="etap_expert",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="ETAP expert knowledge base reasoning and engineering guidance.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="etap_gui",
            study_type="etap_gui",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.etap_gui_agent.ETAPGUIAgent",
            requires_system=False,
            required_params=(),
            agent_key="etap_gui",
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="ETAP graphical interface navigation and CUA automation with kill-switch safeguards.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="generative_design",
            study_type="generative_design",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.design_agent.DesignAgent",
            requires_system=False,
            required_params=(),
            agent_key="generative_design",
            feature_flag="generative_design",
            risk_class="high",
            version="0.1.0",
            lifecycle_status=LifecycleStatus.DISABLED,
            description="Generative SLD topology synthesis (scaffold status; disabled by default).",
        )
    )

    # 3. External / Bridge Study Capabilities (3)
    registry.register(
        CapabilityDefinition(
            capability_id="ahmed_etap_orchestration",
            study_type="ahmed_etap_orchestration",
            executor_kind=ExecutorKind.COMPOSITE,
            handler="AhmedETAPSkillAgent",
            requires_system=False,
            required_params=(),
            agent_key="ahmed_etap",
            risk_class="high",
            authorization_policy="lead_engineer",
            approval_policy="maker_checker",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Autonomous multi-agent study orchestrator combining load flow, short circuit, and protection.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="optimization",
            study_type="optimization",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.optimizers.optimization_agent.OptimizationAgent",
            requires_system=False,
            required_params=(),
            agent_key="optimization",
            risk_class="medium",
            authorization_policy="engineer",
            approval_policy="standard",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Specialist optimization agent delivering metaheuristic swarm optimizations (PSO placement, filter design).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="breaker_duty",
            study_type="breaker_duty",
            executor_kind=ExecutorKind.EXTERNAL_SERVICE,
            handler="breaker_duty.evaluator.BreakerDutyEvaluator",
            requires_system=False,
            required_params=(),
            agent_key=None,
            feature_flag="breaker_duty",
            risk_class="high",
            version="0.1.0",
            lifecycle_status=LifecycleStatus.DISABLED,
            description="Circuit breaker interrupting rating and stress evaluation per IEC 62271-100 (disabled by default).",
        )
    )

    # 4. Specialist Non-Study Canonical Agents (8)
    registry.register(
        CapabilityDefinition(
            capability_id="etap_execution",
            study_type=None,
            executor_kind=ExecutorKind.ETAP,
            handler="agents.orchestrator.ETAPExecutionAgent",
            requires_system=True,
            required_params=(),
            agent_key="etap_execution",
            risk_class="high",
            authorization_policy="lead_engineer",
            approval_policy="maker_checker",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="ETAP Windows COM automation provider interface for multi-study execution.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="validation",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.orchestrator.ValidationAgent",
            requires_system=False,
            required_params=(),
            agent_key="validation",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Multi-agent result cross-checking and engineering assertion validation.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="report",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.orchestrator.ReportGenerationAgent",
            requires_system=False,
            required_params=(),
            agent_key="report",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Automated engineering report compilation (PDF, DOCX, XLSX).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="anomaly",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.anomaly_agent.AnomalyAgent",
            requires_system=False,
            required_params=(),
            agent_key="anomaly",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.INTERNAL,
            description="Context-bound operational anomaly detection (M4.4 non-study agent).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="predictive",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.predictive_agent.PredictiveAgent",
            requires_system=False,
            required_params=(),
            agent_key="predictive",
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.INTERNAL,
            description="Context-bound predictive maintenance assessment (M4.4 non-study agent).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="weather",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.weather_agent.WeatherAgent",
            requires_system=False,
            required_params=(),
            agent_key="weather",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Meteorological data integration for renewables and thermal rating analysis.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="goal_planner",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.goal_planner_agent.GoalPlannerAgent",
            requires_system=False,
            required_params=(),
            agent_key="goal_planner",
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Structured engineering goal decomposition and task planning.",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="code_guard",
            study_type=None,
            executor_kind=ExecutorKind.AGENT,
            handler="agents.code_guard_agent.CodeGuardAgent",
            requires_system=False,
            required_params=(),
            agent_key="code_guard",
            risk_class="high",
            authorization_policy="admin",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Code guardrail verification and AST security validation.",
        )
    )


# Singleton Registry Instance
_DEFAULT_REGISTRY: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """Return the global singleton canonical capability registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        reg = CapabilityRegistry()
        _populate_canonical_registry(reg)
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY


def get_capability_definition(capability_id: str) -> CapabilityDefinition:
    """Convenience helper to lookup a capability definition from the canonical registry."""
    return get_capability_registry().get_capability_definition(capability_id)
