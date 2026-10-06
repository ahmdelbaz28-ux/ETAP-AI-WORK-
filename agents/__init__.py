from __future__ import annotations

"""AI Agents - Multi-agent engineering orchestration system.

Provides the AhmedETAP specialized engineering agents and a
ChiefEngineeringOrchestrator that coordinates them for autonomous power
system analysis and ETAP automation.

M4.2 note: the canonical agent-key namespace (27 canonical keys + 3 aliases)
lives in ``agents.registry`` as ``CANONICAL_AGENT_KEYS`` / ``AGENT_KEY_ALIASES``.
The class inventory below (``ALL_AGENT_CLASSES``) is a *class* list, not the
key namespace, and is intentionally a subset — see the audit note attached to
``ALL_AGENT_CLASSES``.

Core Agents (orchestrator.py):
    - LoadFlowAgent: Newton-Raphson / Fast Decoupled power flow analysis
    - ShortCircuitAgent: IEC 60909 fault current calculation
    - HarmonicAnalysisAgent: IEEE 519-2022 THD/TDD compliance
    - OptimalPowerFlowAgent: AC/DC optimal power flow with economic dispatch
    - ProtectionCoordinationAgent: IEC 60255 relay curve coordination
    - ETAPExecutionAgent: ETAP COM automation interface
    - ValidationAgent: Results verification & cross-validation
    - ReportGenerationAgent: Automated report generation (PDF/DOCX/XLSX)

Extended Agents (separate modules):
    - StabilityAgent: Transient & small-signal stability per IEEE 399
    - CableSizingAgent: Cable ampacity & voltage drop per IEC 60364
    - EarthGridAgent: Ground grid design per IEEE 80
    - RenewableAgent: DER integration analysis per IEEE 1547-2018
    - BatteryStorageAgent: BESS analysis per IEC 62933
    - SCADAAgent: IEC 61850 data model mapping & real-time processing

Orchestrator:
    - ChiefEngineeringOrchestrator: Task decomposition & agent coordination

Data Classes:
    - AgentStatus: Agent execution status enum (IDLE, RUNNING, COMPLETED, FAILED, VALIDATING)
    - AgentResult: Structured result from agent execution
    - EngineeringTask: Complete engineering task specification
    - StudyType: Power system study types enum
"""

from agents.arc_flash_agent import ArcFlashAgent
from agents.base import BaseAgent
from agents.battery_storage_agent import BatteryStorageAgent
from agents.cable_sizing_agent import CableSizingAgent
from agents.digital_twin_agent import DigitalTwinAgent
from agents.earth_grid_agent import EarthGridAgent
from agents.etap_expert_agent import ETAPExpertAgent
from agents.etap_gui_agent import ETAPGUIAgent
from agents.models import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    PlanningIntent,
    PlanningPlan,
    StudyType,
)
from agents.motor_starting_agent import MotorStartingAgent
from agents.orchestrator import (
    ChiefEngineeringOrchestrator,
    ETAPExecutionAgent,
    HarmonicAnalysisAgent,
    LoadFlowAgent,
    OptimalPowerFlowAgent,
    ProtectionCoordinationAgent,
    ReportGenerationAgent,
    ShortCircuitAgent,
    ValidationAgent,
    get_orchestrator,
)
from agents.renewable_agent import RenewableAgent
from agents.scada_agent import SCADAAgent
from agents.stability_agent import StabilityAgent

# Registry of all agent classes for easy iteration/discovery
ALL_AGENT_CLASSES = [
    LoadFlowAgent,
    ShortCircuitAgent,
    HarmonicAnalysisAgent,
    OptimalPowerFlowAgent,
    ProtectionCoordinationAgent,
    ETAPExecutionAgent,
    ValidationAgent,
    ReportGenerationAgent,
    StabilityAgent,
    CableSizingAgent,
    EarthGridAgent,
    RenewableAgent,
    BatteryStorageAgent,
    SCADAAgent,
]

# Mapping from StudyType to the agent that handles it.
# Authoritative projections from CapabilityRegistry (Phases 2 & 3).
from engine.capability_registry import get_capability_registry

STUDY_TYPE_AGENT_MAP: dict[StudyType, type[BaseAgent]] = (
    get_capability_registry().to_study_type_agent_map()
)

# WP4 (Iron Loop): register the unified ETAP COM execution agent projection.
ETAP_EXECUTION_AGENT_MAP: dict[StudyType, type[BaseAgent]] = (
    get_capability_registry().to_etap_execution_agent_map()
)

__all__ = [
    # Base classes and data structures
    "AgentStatus",
    "AgentResult",
    "BaseAgent",
    "EngineeringTask",
    "PlanningIntent",
    "PlanningPlan",
    "StudyType",
    # Core agents (orchestrator.py)
    "LoadFlowAgent",
    "ShortCircuitAgent",
    "HarmonicAnalysisAgent",
    "OptimalPowerFlowAgent",
    "ProtectionCoordinationAgent",
    "ETAPExecutionAgent",
    "ValidationAgent",
    "ReportGenerationAgent",
    # Extended agents
    "StabilityAgent",
    "CableSizingAgent",
    "EarthGridAgent",
    "RenewableAgent",
    "BatteryStorageAgent",
    "SCADAAgent",
    "MotorStartingAgent",
    "ArcFlashAgent",
    "DigitalTwinAgent",
    "ETAPExpertAgent",
    "ETAPGUIAgent",
    # Orchestrator
    "ChiefEngineeringOrchestrator",
    "get_orchestrator",
    # Registries
    "ALL_AGENT_CLASSES",
    "STUDY_TYPE_AGENT_MAP",
    "ETAP_EXECUTION_AGENT_MAP",
]
