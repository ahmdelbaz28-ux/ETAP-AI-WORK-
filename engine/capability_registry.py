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
    """Canonical Capability Definition contract (Phase 2 & Phase 3 Production Gate).

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
    required_system_data : tuple[str, ...]
        Tuple of mandatory system model components (e.g. ('buses', 'lines', 'base_mva')).
    agent_key : str | None
        Associated canonical agent key in agents.registry, if applicable.
    benchmark_status : str
        Benchmark validation status ('VERIFIED_BENCHMARK', 'VERIFIED_EXPERT_KB', 'VERIFIED_CANONICAL', 'PENDING', 'NONE').
    standards_scope : str
        Explicit standard edition/version and clause scope (e.g. 'IEEE 3002.7-2018', 'IEC 60909-0:2016').
    validation_evidence : str
        Documentation of independent reference evidence, benchmark suites, and test coverage.
    reference_cases : tuple[str, ...]
        Tuple of benchmark reference case IDs validating this capability.
    validation_version : str
        Version of the validation and reference ruleset.
    production_supported : bool
        Whether this capability is officially verified and certified for production engineering execution.
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
    required_system_data: tuple[str, ...] = ()
    agent_key: str | None = None
    benchmark_status: str = "VERIFIED_CANONICAL"
    standards_scope: str = "Authoritative Engineering Standards"
    validation_evidence: str = "Canonical validation and test coverage"
    reference_cases: tuple[str, ...] = ()
    validation_version: str = "1.0.0"
    production_supported: bool = True
    description: str = ""

    def is_production_eligible(self) -> bool:
        """Deterministic evaluation of production-readiness criteria.

        A capability is eligible for PRODUCTION engineering execution if and only if:
        1. Lifecycle status is strictly PRODUCTION.
        2. production_supported is True.
        3. Lifecycle status is not DISABLED, UNAVAILABLE, EXPERIMENTAL, INTERNAL, or PILOT.
        4. Standards scope is explicitly declared and non-empty.
        5. Validation evidence is documented and non-empty.
        6. Benchmark status is verified ('VERIFIED_BENCHMARK', 'VERIFIED_EXPERT_KB', 'VERIFIED_CANONICAL').
        7. Capability ID and Executor Kind are valid.
        """
        status_str = (
            self.lifecycle_status.value
            if isinstance(self.lifecycle_status, LifecycleStatus)
            else str(self.lifecycle_status).lower()
        )
        if status_str != "production":
            return False
        if not self.production_supported:
            return False
        if not self.standards_scope or not self.standards_scope.strip():
            return False
        if not self.validation_evidence or not self.validation_evidence.strip():
            return False
        if self.benchmark_status in ("NONE", "PENDING"):
            return False
        if self.benchmark_status not in ("VERIFIED_BENCHMARK", "VERIFIED_EXPERT_KB", "VERIFIED_CANONICAL"):
            return False
        return bool(self.capability_id and self.executor_kind)


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
            "fault": "short_circuit",
            "fault_analysis": "short_circuit",
            "coordination": "protection_coordination",
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
        from agents.registry import STUDY_TYPE_MAPPING

        return dict(STUDY_TYPE_MAPPING)

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
    """Populate registry with all canonical capabilities with strict maturity verification."""

    # 1. Production-Certified Native Study Capabilities (4)
    registry.register(
        CapabilityDefinition(
            capability_id="load_flow",
            study_type="load_flow",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_load_flow",
            requires_system=True,
            required_params=(),
            required_system_data=("buses", "lines", "base_mva"),
            agent_key="load_flow",
            benchmark_status="VERIFIED_BENCHMARK",
            standards_scope="IEEE 3002.7-2018 (AC/DC Newton-Raphson, Fast Decoupled, DC Power Flow)",
            validation_evidence="IEEE 9-bus WSCC, IEEE 14-bus, IEEE 30-bus, IEEE 39-bus gold standard test suites",
            reference_cases=("ieee_9_bus", "ieee_14_bus", "ieee_30_bus", "ieee_39_bus"),
            production_supported=True,
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
            required_system_data=("buses", "lines", "base_mva"),
            agent_key="short_circuit",
            benchmark_status="VERIFIED_BENCHMARK",
            standards_scope="IEC 60909-0:2016 Initial Symmetrical Short-Circuit Current (Ik'', ip, Ib, Sk'' 3-phase, SLG, line-to-line via Sequence Networks)",
            validation_evidence="IEC 60909-0:2016 4-bus industrial distribution benchmark network with independent analytical sequence network derivation",
            reference_cases=("iec60909_case_industrial_4bus",),
            production_supported=True,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Three-phase and unbalanced short-circuit analysis per IEC 60909 sequence networks.",
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
            required_system_data=(),
            agent_key="arc_flash",
            benchmark_status="VERIFIED_BENCHMARK",
            standards_scope="IEEE 1584-2018 Annex D Parametric Hazard Screening (0.208-15 kV, VCB/VCBB/HCB/VOA/HOA, Typical Electrode Gaps)",
            validation_evidence="IEEE 1584-2018 Annex D Table D.1 published benchmark test cases (ST-1 through ST-5)",
            reference_cases=("ST-1", "ST-2", "ST-3", "ST-4", "ST-5"),
            production_supported=True,
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Arc flash hazard and incident energy assessment per IEEE 1584-2018 Annex D screening model (point hazard analysis; no network topology required).",
        )
    )
    registry.register(
        CapabilityDefinition(
            capability_id="protection_coordination",
            study_type="protection_coordination",
            executor_kind=ExecutorKind.NATIVE,
            handler="run_protection_coordination",
            requires_system=True,
            required_params=("upstream_relay_id", "downstream_relay_id"),
            required_system_data=("buses",),
            agent_key="protection_coordination",
            benchmark_status="VERIFIED_BENCHMARK",
            standards_scope="IEC 60255-151 (Standard Inverse, Very Inverse, Extremely Inverse, Long Time Inverse)",
            validation_evidence="IEC 60255-151 standard curve selectivity & operating time benchmarks",
            reference_cases=("iec60255_si_curve_benchmark", "iec60255_vi_curve_benchmark"),
            production_supported=True,
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            description="Relay coordination and time-current curve selectivity verification per IEC 60255.",
        )
    )

    # 2. Agent-Routed Study Capabilities (Honest PILOT / Internal classification)
    registry.register(
        CapabilityDefinition(
            capability_id="harmonic_analysis",
            study_type="harmonic_analysis",
            executor_kind=ExecutorKind.AGENT,
            handler="agents.orchestrator.HarmonicAnalysisAgent",
            requires_system=True,
            required_params=(),
            agent_key="harmonic_analysis",
            benchmark_status="PENDING",
            standards_scope="IEEE 519-2022 (Harmonic flow scaffold)",
            validation_evidence="Harmonic analysis unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Harmonic distortion and resonance assessment per IEEE 519-2022 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEEE 3002.7 (Economic dispatch / OPF scaffold)",
            validation_evidence="Optimal power flow unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Optimal power flow economic dispatch and voltage optimization (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEEE 399 (Motor dynamic starting)",
            validation_evidence="Motor starting unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Dynamic and static motor starting voltage dip assessment per IEEE 399 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEEE 399 (RK4 Swing Equation transient stability)",
            validation_evidence="Transient stability scenario test suite with strict parameter verification",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Transient stability and critical clearing time evaluation per IEEE 399 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEC 60364 (Ampacity, derating, and voltage drop)",
            validation_evidence="Cable sizing unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Cable ampacity, derating, and voltage drop sizing per IEC 60364 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEEE 80 (Substation grounding grid design)",
            validation_evidence="Earth grid unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Substation grounding grid design and step/touch potential per IEEE 80 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEEE 1547-2018 (Distributed energy resource grid integration)",
            validation_evidence="Renewable integration unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Distributed energy resource (PV/Wind) grid integration per IEEE 1547-2018 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEC 62933 (BESS sizing and dispatch)",
            validation_evidence="Battery storage unit test suite",
            production_supported=False,
            risk_class="medium",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Battery energy storage system (BESS) sizing and dispatch per IEC 62933 (pilot status).",
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
            benchmark_status="PENDING",
            standards_scope="IEC 61850 (SCADA data mapping and state estimation)",
            validation_evidence="SCADA agent unit test suite",
            production_supported=False,
            risk_class="high",
            authorization_policy="lead_engineer",
            approval_policy="dual_control",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="SCADA integration, state estimation, and data mapping per IEC 61850 (pilot status).",
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
            benchmark_status="NONE",
            standards_scope="Platform Digital Twin Synchronization",
            validation_evidence="Digital twin state store tests",
            production_supported=False,
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
            required_params=("question",),
            agent_key="etap_expert",
            benchmark_status="VERIFIED_EXPERT_KB",
            standards_scope="IEEE / IEC ETAP Engineering Knowledge Base Guidelines, NFPA 70E, NEC",
            validation_evidence="22 deterministic scenario tests covering complete/incomplete/incorrect/adms formats",
            reference_cases=("etap_expert_6step_workflow", "etap_expert_adms_scenarios"),
            production_supported=True,
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
            required_params=("question",),
            agent_key="etap_gui",
            benchmark_status="PENDING",
            standards_scope="ETAP Graphical Interface Computer-Use Navigation",
            validation_evidence="CUA safety kill-switch test suite",
            production_supported=False,
            risk_class="high",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="ETAP graphical interface navigation and CUA automation with kill-switch safeguards (pilot status).",
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
            benchmark_status="NONE",
            standards_scope="Parametric Single-Line Diagram Topology Synthesis",
            validation_evidence="Design agent unit tests",
            production_supported=False,
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
            benchmark_status="PENDING",
            standards_scope="Autonomous Multi-Agent Power System Orchestration",
            validation_evidence="Multi-agent composite pipeline tests",
            production_supported=False,
            risk_class="high",
            authorization_policy="lead_engineer",
            approval_policy="maker_checker",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
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
            benchmark_status="PENDING",
            standards_scope="Metaheuristic Swarm Optimization (PSO filter design and placement)",
            validation_evidence="Optimization agent test suite",
            production_supported=False,
            risk_class="medium",
            authorization_policy="engineer",
            approval_policy="standard",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
            description="Specialist optimization agent delivering metaheuristic swarm optimizations.",
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
            benchmark_status="NONE",
            standards_scope="IEC 62271-100 Circuit Breaker Duty",
            validation_evidence="Breaker duty test suite",
            production_supported=False,
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
            required_system_data=("buses",),
            agent_key="etap_execution",
            benchmark_status="VERIFIED_CANONICAL",
            standards_scope="ETAP Windows COM API Automation Interface",
            validation_evidence="ETAP COM provider integration test suite with fail-closed safety",
            production_supported=True,
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
            benchmark_status="VERIFIED_CANONICAL",
            standards_scope="Multi-Agent Assertion Validation Ruleset",
            validation_evidence="ValidationAgent assertion rule verification test suite",
            production_supported=True,
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
            benchmark_status="VERIFIED_CANONICAL",
            standards_scope="ISO/IEC 25010 Engineering Report Compilation",
            validation_evidence="Report generation test suite (PDF, DOCX, XLSX)",
            production_supported=True,
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
            benchmark_status="NONE",
            standards_scope="Operational Anomaly Detection",
            validation_evidence="Anomaly agent unit tests",
            production_supported=False,
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
            benchmark_status="NONE",
            standards_scope="Predictive Maintenance Assessment",
            validation_evidence="Predictive agent unit tests",
            production_supported=False,
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
            benchmark_status="PENDING",
            standards_scope="Meteorological Data Integration",
            validation_evidence="Weather tool unit tests",
            production_supported=False,
            risk_class="low",
            version="1.0.0",
            lifecycle_status=LifecycleStatus.PILOT,
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
            benchmark_status="VERIFIED_CANONICAL",
            standards_scope="Structured JSON Engineering Goal Planning",
            validation_evidence="Goal planner task decomposition test suite",
            production_supported=True,
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
            benchmark_status="VERIFIED_CANONICAL",
            standards_scope="AST & Static Security Guardrail Validation",
            validation_evidence="Code guard security verification test suite",
            production_supported=True,
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
