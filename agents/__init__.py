"""AI Agents - Multi-agent engineering orchestration system.

Provides 15 specialized engineering agents and a ChiefEngineeringOrchestrator
that coordinates them for autonomous power system analysis and ETAP automation.

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

from agents.battery_storage_agent import BatteryStorageAgent
from agents.cable_sizing_agent import CableSizingAgent
from agents.earth_grid_agent import EarthGridAgent
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    BaseAgent,
    ChiefEngineeringOrchestrator,
    EngineeringTask,
    ETAPExecutionAgent,
    HarmonicAnalysisAgent,
    LoadFlowAgent,
    OptimalPowerFlowAgent,
    ProtectionCoordinationAgent,
    ReportGenerationAgent,
    ShortCircuitAgent,
    StudyType,
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

# Mapping from StudyType to the agent that handles it
STUDY_TYPE_AGENT_MAP = {
    StudyType.LOAD_FLOW: LoadFlowAgent,
    StudyType.SHORT_CIRCUIT: ShortCircuitAgent,
    StudyType.HARMONIC_ANALYSIS: HarmonicAnalysisAgent,
    StudyType.OPTIMAL_POWER_FLOW: OptimalPowerFlowAgent,
    StudyType.PROTECTION_COORDINATION: ProtectionCoordinationAgent,
    StudyType.MOTOR_STARTING: LoadFlowAgent,  # Handled by LoadFlowAgent with motor model
    StudyType.TRANSIENT_STABILITY: StabilityAgent,
    StudyType.ARC_FLASH: ShortCircuitAgent,  # Requires fault current from ShortCircuitAgent
}

__all__ = [
    # Base classes and data structures
    "AgentStatus",
    "AgentResult",
    "BaseAgent",
    "EngineeringTask",
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
    # Orchestrator
    "ChiefEngineeringOrchestrator",
    "get_orchestrator",
    # Registries
    "ALL_AGENT_CLASSES",
    "STUDY_TYPE_AGENT_MAP",
]
