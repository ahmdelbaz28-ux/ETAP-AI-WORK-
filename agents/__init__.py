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

<<<<<<< HEAD
from agents.arc_flash_agent import ArcFlashAgent
from agents.battery_storage_agent import BatteryStorageAgent
from agents.cable_sizing_agent import CableSizingAgent
from agents.digital_twin_agent import DigitalTwinAgent
from agents.earth_grid_agent import EarthGridAgent
from agents.etap_expert_agent import ETAPExpertAgent
from agents.etap_gui_agent import ETAPGUIAgent
from agents.motor_starting_agent import MotorStartingAgent
=======
from agents.battery_storage_agent import BatteryStorageAgent
from agents.cable_sizing_agent import CableSizingAgent
from agents.earth_grid_agent import EarthGridAgent
>>>>>>> origin/fix/scenario-tests-properly
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

<<<<<<< HEAD
# Mapping from StudyType to the agent that handles it.
#
# NOTE (audit item 2.10 — UI Coverage Audit 2026-07-29):
#   This map is a static registry. It is NOT used by the runtime study
#   dispatch path (api/studies.py dispatches via its own _run_native_study
#   + agent special-cases, and the orchestrator uses its own internal
#   dispatch). The map is consumed only by scripts/maintenance/verify_agents.py
#   (which does a substring check that the symbol exists — it does NOT
#   validate the values). Fixing the entries below therefore has no runtime
#   effect — it only corrects the registry so that tooling and future
#   dispatch code that consults this map see the right agent for each
#   study type.
#
#   Fixed in this commit:
#     - MOTOR_STARTING: was LoadFlowAgent (wrong) -> MotorStartingAgent
#     - ARC_FLASH:      was ShortCircuitAgent (wrong) -> ArcFlashAgent
#     - Added the 8 missing mappings required by the StudyType enum:
#       CABLE_SIZING, EARTH_GRID, RENEWABLE_INTEGRATION, BATTERY_STORAGE,
#       SCADA, DIGITAL_TWIN, ETAP_EXPERT, ETAP_GUI
#
#   NOTE: ALL_AGENT_CLASSES is intentionally NOT expanded in this commit.
#   The audit recommends adding the 12 missing BaseAgent subclasses, but
#   tests/test_agents.py::test_individual_agents instantiates each entry
#   with no args and calls .execute() with a LOAD_FLOW task — adding agents
#   whose constructors or execute() paths don't satisfy that contract would
#   break the test. Each candidate agent needs per-class verification before
#   being added to the registry. See audit item 2.10 follow-up.
=======
# Mapping from StudyType to the agent that handles it
>>>>>>> origin/fix/scenario-tests-properly
STUDY_TYPE_AGENT_MAP = {
    StudyType.LOAD_FLOW: LoadFlowAgent,
    StudyType.SHORT_CIRCUIT: ShortCircuitAgent,
    StudyType.HARMONIC_ANALYSIS: HarmonicAnalysisAgent,
    StudyType.OPTIMAL_POWER_FLOW: OptimalPowerFlowAgent,
    StudyType.PROTECTION_COORDINATION: ProtectionCoordinationAgent,
<<<<<<< HEAD
    StudyType.MOTOR_STARTING: MotorStartingAgent,
    StudyType.TRANSIENT_STABILITY: StabilityAgent,
    StudyType.ARC_FLASH: ArcFlashAgent,
    StudyType.CABLE_SIZING: CableSizingAgent,
    StudyType.EARTH_GRID: EarthGridAgent,
    StudyType.RENEWABLE_INTEGRATION: RenewableAgent,
    StudyType.BATTERY_STORAGE: BatteryStorageAgent,
    StudyType.SCADA: SCADAAgent,
    StudyType.DIGITAL_TWIN: DigitalTwinAgent,
    StudyType.ETAP_EXPERT: ETAPExpertAgent,
    StudyType.ETAP_GUI: ETAPGUIAgent,
=======
    StudyType.MOTOR_STARTING: LoadFlowAgent,  # Handled by LoadFlowAgent with motor model
    StudyType.TRANSIENT_STABILITY: StabilityAgent,
    StudyType.ARC_FLASH: ShortCircuitAgent,  # Requires fault current from ShortCircuitAgent
>>>>>>> origin/fix/scenario-tests-properly
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
<<<<<<< HEAD
    "MotorStartingAgent",
    "ArcFlashAgent",
    "DigitalTwinAgent",
    "ETAPExpertAgent",
    "ETAPGUIAgent",
=======
>>>>>>> origin/fix/scenario-tests-properly
    # Orchestrator
    "ChiefEngineeringOrchestrator",
    "get_orchestrator",
    # Registries
    "ALL_AGENT_CLASSES",
    "STUDY_TYPE_AGENT_MAP",
]
