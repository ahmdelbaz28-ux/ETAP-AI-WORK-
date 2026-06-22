"""
AhmedETAP - Multi-Agent Orchestrator
========================================================
Chief Engineering Orchestrator that coordinates all specialized agents
for autonomous power system analysis and ETAP automation.

Architecture:
- Chief Orchestrator: Task decomposition & agent coordination
- Load Flow Agent: Newton-Raphson / Fast Decoupled methods
- Short Circuit Agent: IEC 60909 fault analysis
- Harmonic Agent: IEEE 519 compliance analysis
- OPF Agent: AC/DC optimal power flow
- Protection Agent: Relay coordination per IEC 60255
- ETAP Execution Agent: COM automation interface
- Validation Agent: Results verification & compliance checking
- Report Agent: Automated report generation (PDF/DOCX/XLSX)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List

import numpy as np

from core.tracing import trace_operation

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATING = "validating"


class StudyType(Enum):
    """Power system study types."""

    LOAD_FLOW = "load_flow"
    SHORT_CIRCUIT = "short_circuit"
    HARMONIC_ANALYSIS = "harmonic_analysis"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    PROTECTION_COORDINATION = "protection_coordination"
    MOTOR_STARTING = "motor_starting"
    TRANSIENT_STABILITY = "transient_stability"
    ARC_FLASH = "arc_flash"


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_name: str
    study_type: StudyType
    status: AgentStatus
    data: Dict[str, Any]
    validation_status: bool = False
    validation_errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class EngineeringTask:
    """Complete engineering task specification."""

    task_id: str
    description: str
    study_types: List[StudyType]
    parameters: Dict[str, Any]
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: AgentStatus = AgentStatus.IDLE
    results: List[AgentResult] = field(default_factory=list)


class BaseAgent:
    """Base class for all engineering agents.

    Integrates with the prompt management system so every agent can
    access its prompt-driven description, standards references, and
    execution guidance from ``prompts/`` YAML files (or LangWatch).

    Subclasses must set ``prompt_handle`` to the handle that matches
    their YAML prompt file (e.g. ``"load_flow_agent"``).  If not set,
    a handle is derived from the class name by converting CamelCase
    to snake_case and stripping the "Agent" suffix.
    """

    # Subclasses should override this to match their prompt YAML handle.
    prompt_handle: str = ""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.execution_log: List[Dict] = []

        # Derive prompt handle from class name if not explicitly set
        if not self.prompt_handle:
            self.prompt_handle = self._derive_prompt_handle()

        # Load prompt-driven metadata (description, standards, guidance)
        self._system_prompt: str | None = None
        self._prompt_metadata: Dict[str, Any] = {}
        self._load_prompt()

    def _derive_prompt_handle(self) -> str:
        """Derive a prompt handle from the class name.

        Examples:
            LoadFlowAgent       → load_flow_agent
            ShortCircuitAgent   → short_circuit_agent
            StabilityAgent      → stability_agent
        """
        name = self.__class__.__name__
        # Remove 'Agent' suffix if present
        if name.endswith("Agent"):
            name = name[:-5]
        # Convert CamelCase to snake_case
        import re

        name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
        return name

    def _load_prompt(self) -> None:
        """Load the prompt for this agent from the prompt management system.

        Uses the 3-tier fallback:
        1. LangWatch API (if configured)
        2. Local YAML file in prompts/
        3. Hardcoded default

        Failures are non-fatal — the agent can still operate without
        a prompt, using its hardcoded computational logic.
        """
        try:
            from agents.prompt_loader import get_prompt_metadata, get_system_prompt

            self._system_prompt = get_system_prompt(self.prompt_handle)
            self._prompt_metadata = get_prompt_metadata(self.prompt_handle)
            self.logger.info(
                "Prompt loaded for handle '%s' (%d chars)",
                self.prompt_handle,
                len(self._system_prompt) if self._system_prompt else 0,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to load prompt for handle '%s': %s. Agent will use hardcoded logic.",
                self.prompt_handle,
                exc,
            )
            self._system_prompt = None
            self._prompt_metadata = {}

    @property
    def system_prompt(self) -> str:
        """Return the loaded system prompt, or a default if unavailable."""
        if self._system_prompt:
            return self._system_prompt
        return f"{self.agent_name}: Computational agent for power system analysis."

    @property
    def prompt_model(self) -> str:
        """Return the model name from the prompt metadata, if available."""
        return self._prompt_metadata.get("model", "unknown")

    @property
    def prompt_temperature(self) -> float:
        """Return the temperature from the prompt metadata, if available."""
        return float(self._prompt_metadata.get("temperature", 0.2))

    def get_agent_info(self) -> Dict[str, Any]:
        """Return agent metadata including prompt-derived information.

        This is useful for API responses, logging, and debugging.
        """
        return {
            "agent_name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "model": self.prompt_model,
            "temperature": self.prompt_temperature,
            "prompt_loaded": self._system_prompt is not None,
            "status": self.status.value,
        }

    @trace_operation("BaseAgent.execute", attributes={"component": "orchestrator"})
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute agent task. Override in subclasses.

        Default implementation returns a FAILED AgentResult so that any
        subclass that forgets to override ``execute`` is detected early
        via the agent's own validation pipeline (rather than crashing
        the workflow with a NotImplementedError at runtime).
        """
        self.status = AgentStatus.FAILED
        self.log_execution(
            f"BaseAgent.execute invoked on {self.agent_name} (no override). Task={task.task_id}",
            level="ERROR",
        )
        return AgentResult(
            agent_name=self.agent_name,
            study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
            status=AgentStatus.FAILED,
            data={},
            validation_errors=[
                f"Agent '{self.agent_name}' does not implement execute(); "
                "override BaseAgent.execute in the concrete subclass."
            ],
        )

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate agent result. Override in subclasses.

        Default implementation performs the minimum sanity checks that
        apply to every result (status == COMPLETED, non-empty data,
        no pre-existing validation errors) and returns True if they
        all pass. Subclasses are expected to add domain-specific
        checks.
        """
        if result.status != AgentStatus.COMPLETED:
            result.validation_errors.append(
                f"Result status is {result.status.value}, expected completed"
            )
            return False
        if not result.data:
            result.validation_errors.append("Result data is empty")
            return False
        if result.validation_errors:
            return False
        return True

    def log_execution(self, message: str, level: str = "INFO"):
        """Log execution details."""
        entry = {
            'timestamp': datetime.now(UTC).isoformat(),
            'agent': self.agent_name,
            'level': level,
            'message': message
        }
        self.execution_log.append(entry)
        getattr(self.logger, level.lower())(message)


class LoadFlowAgent(BaseAgent):
    """Load Flow Analysis Agent.

    Prompt Handle: load_flow_agent

    Methods:
    - Newton-Raphson (full AC)
    - Fast Decoupled (approximate)
    - DC Power Flow (linearized)

    Validates:
    - Voltage limits (0.95 - 1.05 pu typical)
    - Convergence criteria
    - Power balance
    """

    prompt_handle = "load_flow_agent"

    def __init__(self):
        super().__init__("LoadFlowAgent")
        self.voltage_limits = {"min": 0.95, "max": 1.05}
        self.convergence_tolerance = 1e-6

    @trace_operation(
        "LoadFlowAgent.execute", attributes={"component": "orchestrator", "study_type": "load_flow"}
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute load flow analysis."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting load flow analysis for task {task.task_id}")

            # Import calculation engine
            from load_flow.load_flow import LoadFlowSolver

            # Extract system data from task parameters
            system_data = task.parameters.get("system")
            if not system_data:
                raise ValueError("System data not provided in task parameters")

            # Ensure system_data is handled consistently as a System object
            # LoadFlowSolver requires a System object, not a dictionary
            if isinstance(system_data, dict):
                raise TypeError(
                    "system_data must be a System object instance, not a dictionary. Ensure a valid System object is passed in task parameters."
                )

            # Run load flow
            solver = LoadFlowSolver(system_data)
            converged = solver.solve(
                max_iter=task.parameters.get("max_iterations", 100), tol=self.convergence_tolerance
            )

            # Extract results
            bus_results = {}
            for bus_id, bus in system_data.buses.items():
                bus_results[bus_id] = {
                    "voltage_magnitude_pu": abs(bus.voltage),
                    "voltage_angle_deg": np.degrees(np.angle(bus.voltage)),
                    "active_power_mw": bus.generation_power.real - bus.load_power.real,
                    "reactive_power_mvar": bus.generation_power.imag - bus.load_power.imag,
                }

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED if converged else AgentStatus.FAILED,
                data={
                    "converged": converged,
                    "buses": bus_results,
                    "iterations": solver.iterations if hasattr(solver, "iterations") else 0,
                    "method": "Newton-Raphson",
                },
            )

            # Validate results
            result.validation_status = self.validate_result(result)

            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Load flow completed in {execution_time:.2f}s, converged={converged}"
            )

            return result

        except Exception as e:
            self.log_execution(f"Load flow failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate load flow results."""
        if not result.data.get("converged"):
            result.validation_errors.append("Load flow did not converge")
            return False

        # Check voltage limits
        buses = result.data.get("buses", {})
        for bus_id, bus_data in buses.items():
            v_mag = bus_data.get("voltage_magnitude_pu", 0)
            if v_mag < self.voltage_limits["min"] or v_mag > self.voltage_limits["max"]:
                result.validation_errors.append(
                    f"Bus {bus_id} voltage {v_mag:.4f} pu outside limits "
                    f"[{self.voltage_limits['min']}, {self.voltage_limits['max']}]"
                )

        return len(result.validation_errors) == 0


class ShortCircuitAgent(BaseAgent):
    """Short Circuit / Fault Analysis Agent.

    Prompt Handle: short_circuit_agent

    Standards: IEC 60909-0:2016

    Fault Types:
    - Three-phase fault
    - Line-to-ground fault
    - Line-to-line fault
    - Double line-to-ground fault

    Calculates:
    - Initial symmetrical short-circuit current (Ik")
    - Peak making current (ip)
    - Breaking current (Ib)
    - DC component
    """

    prompt_handle = "short_circuit_agent"

    def __init__(self):
        super().__init__("ShortCircuitAgent")
        self.standards_compliance = ["IEC 60909-0:2016"]

    @trace_operation(
        "ShortCircuitAgent.execute",
        attributes={"component": "orchestrator", "study_type": "short_circuit"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute short circuit analysis."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting short circuit analysis for task {task.task_id}")

            from fault_analysis.fault import FaultAnalyzer

            system_data = task.parameters.get("system")
            if not system_data:
                raise ValueError("System data not provided")

            # Build sequence networks
            system_data.build_sequence_networks()

            Ybus_pos = system_data.get_ybus(seq="1")
            Ybus_neg = system_data.get_ybus(seq="2")
            Ybus_zero = system_data.get_ybus(seq="0")

            # Create fault analyzer
            base_mva = system_data.base_mva
            base_kv = task.parameters.get("base_kv", 115.0)

            analyzer = FaultAnalyzer(
                Ybus_pos, Ybus_neg, Ybus_zero, base_mva=base_mva, base_kv=base_kv
            )

            # Execute all fault types at specified buses
            fault_buses = task.parameters.get("fault_buses", list(system_data.buses.keys()))
            fault_results = {}

            for bus_id in fault_buses:
                bus_idx = list(system_data.buses.keys()).index(bus_id)

                faults = {
                    "three_phase": analyzer.three_phase_fault(bus_idx),
                    "line_to_ground": analyzer.line_to_ground_fault(bus_idx),
                    "line_to_line": analyzer.line_to_line_fault(bus_idx),
                    "double_line_to_ground": analyzer.double_line_to_ground_fault(bus_idx),
                }

                fault_results[bus_id] = faults

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.SHORT_CIRCUIT,
                status=AgentStatus.COMPLETED,
                data={
                    "fault_results": fault_results,
                    "standard": "IEC 60909-0:2016",
                    "base_mva": base_mva,
                    "base_kv": base_kv,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Short circuit analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Short circuit analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.SHORT_CIRCUIT,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate short circuit results."""
        fault_results = result.data.get("fault_results", {})

        if not fault_results:
            result.validation_errors.append("No fault results generated")
            return False

        # Check that all fault currents are positive
        for bus_id, faults in fault_results.items():
            for fault_type, fault_data in faults.items():
                if "fault_current" in fault_data:
                    current = abs(fault_data["fault_current"])
                    if current <= 0:
                        result.validation_errors.append(
                            f"Bus {bus_id} {fault_type}: Invalid fault current {current}"
                        )

        return len(result.validation_errors) == 0


class HarmonicAnalysisAgent(BaseAgent):
    """Harmonic Analysis Agent.

    Prompt Handle: harmonic_agent

    Standard: IEEE 519-2022

    Capabilities:
    - Harmonic impedance calculation
    - THD/TDD analysis
    - Resonance detection
    - Filter design
    - Compliance checking
    """

    prompt_handle = "harmonic_agent"

    def __init__(self):
        super().__init__("HarmonicAnalysisAgent")
        self.standard = "IEEE 519-2022"
        self.max_harmonic_order = 50

    @trace_operation(
        "HarmonicAnalysisAgent.execute",
        attributes={"component": "orchestrator", "study_type": "harmonic"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute harmonic analysis."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting harmonic analysis for task {task.task_id}")

            from fault_analysis.harmonic_analysis import HarmonicAnalysisEngine, HarmonicSource

            system_data = task.parameters.get("system")
            harmonic_sources = task.parameters.get("harmonic_sources", [])
            voltage_kv = task.parameters.get("voltage_kv", 13.8)

            # Create engine
            engine = HarmonicAnalysisEngine(
                fundamental_freq=task.parameters.get("fundamental_freq", 60.0),
                max_harmonic=self.max_harmonic_order,
            )

            # Set system data
            Ybus = system_data.get_ybus(seq="1")
            bus_ids = sorted(system_data.buses.keys())
            engine.set_system_data(Ybus, bus_ids)

            # Add harmonic sources
            for source_data in harmonic_sources:
                source = HarmonicSource(**source_data)
                engine.add_harmonic_source(source)

            # Run analysis
            result_data = engine.run_full_analysis(voltage_kv=voltage_kv)

            # Generate report
            report = engine.generate_report(result_data)

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.HARMONIC_ANALYSIS,
                status=AgentStatus.COMPLETED,
                data={
                    "thd_voltage": result_data.total_thd_voltage,
                    "tdd_current": result_data.total_tdd_current,
                    "resonance_detected": result_data.resonance_detected,
                    "resonance_frequencies": result_data.resonance_frequencies,
                    "compliance_status": result_data.compliance_status,
                    "violations": result_data.violations,
                    "report": report,
                    "standard": self.standard,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Harmonic analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Harmonic analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.HARMONIC_ANALYSIS,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate harmonic analysis results."""
        violations = result.data.get("violations", [])

        if violations:
            result.validation_errors.extend(violations)
            # Violations mean non-compliance, not invalid analysis
            # Return True since the analysis itself was valid

        return True


class OptimalPowerFlowAgent(BaseAgent):
    """Optimal Power Flow Agent.

    Prompt Handle: opf_agent

    Methods:
    - DC-OPF (Linear Programming)
    - AC-OPF (Interior Point Method)

    Objectives:
    - Economic dispatch (minimize cost)
    - Loss minimization
    - Voltage profile optimization
    """

    prompt_handle = "opf_agent"

    def __init__(self):
        super().__init__("OptimalPowerFlowAgent")

    @trace_operation(
        "OptimalPowerFlowAgent.execute",
        attributes={"component": "orchestrator", "study_type": "opf"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute optimal power flow."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting OPF analysis for task {task.task_id}")

            from load_flow.optimal_power_flow import GeneratorCost, OptimalPowerFlowEngine

            system_data = task.parameters.get("system")
            generator_costs = task.parameters.get("generator_costs", [])
            method = task.parameters.get("method", "dc")

            # Create OPF engine
            Ybus = system_data.get_ybus(seq="1")
            bus_ids = sorted(system_data.buses.keys())
            costs = [GeneratorCost(**gc) for gc in generator_costs]

            opf = OptimalPowerFlowEngine(Ybus, bus_ids, costs)

            # Set load data
            load_data = {}
            for bus_id, bus in system_data.buses.items():
                load_data[bus_id] = bus.load_power
            opf.set_load_data(load_data)

            # Set generator locations
            gen_buses = task.parameters.get("generator_locations", {})
            opf.set_generator_locations(gen_buses)

            # Solve OPF
            opf_result = opf.solve_opf(method=method)

            # Generate report
            report = opf.generate_report(opf_result)

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.OPTIMAL_POWER_FLOW,
                status=AgentStatus.COMPLETED if opf_result.success else AgentStatus.FAILED,
                data={
                    "success": opf_result.success,
                    "objective_value": opf_result.objective_value,
                    "generator_dispatch": {
                        gid: {"P_MW": dispatch.real, "Q_MVAR": dispatch.imag}
                        for gid, dispatch in opf_result.generator_dispatch.items()
                    },
                    "total_generation_mw": opf_result.total_generation,
                    "total_load_mw": opf_result.total_load,
                    "total_losses_mw": opf_result.total_losses,
                    "method": opf_result.method_used,
                    "report": report,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"OPF completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"OPF failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.OPTIMAL_POWER_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate OPF results."""
        if not result.data.get("success"):
            result.validation_errors.append("OPF did not converge")
            return False

        # Check power balance
        P_gen = result.data.get("total_generation_mw", 0)
        P_load = result.data.get("total_load_mw", 0)
        P_losses = result.data.get("total_losses_mw", 0)

        balance_error = abs(P_gen - P_load - P_losses)
        if balance_error > 1.0:  # Allow 1 MW tolerance
            result.validation_errors.append(f"Power balance error: {balance_error:.2f} MW")
            return False

        return True


class ProtectionCoordinationAgent(BaseAgent):
    """Protection Coordination Agent.

    Prompt Handle: protection_agent

    Standard: IEC 60255

    Capabilities:
    - Relay coordination analysis
    - Time-current curve generation
    - Coordination margin verification
    - Fuse-relay coordination
    """

    prompt_handle = "protection_agent"

    def __init__(self):
        super().__init__("ProtectionCoordinationAgent")
        self.standard = "IEC 60255"

    @trace_operation(
        "ProtectionCoordinationAgent.execute",
        attributes={"component": "orchestrator", "study_type": "protection"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting protection coordination for task {task.task_id}")

            from coordination.coordination import CoordinationEngine
            from relays.relay import OvercurrentRelay

            system_data = task.parameters.get("system")
            if not system_data:
                raise ValueError("System data not provided")

            relay_data = task.parameters.get("relays", [])
            coordination_engine = CoordinationEngine()

            # Analyze coordination
            relays = [OvercurrentRelay(**rd) for rd in relay_data]

            coordination_results = []
            for i in range(len(relays) - 1):
                for fault_current in [3.0, 5.0, 10.0, 20.0]:
                    result = coordination_engine.check_coordination(
                        relays[i], relays[i + 1], fault_current
                    )
                    coordination_results.append(result)

            all_coordinated = all(r.get("coordinated", False) for r in coordination_results)

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.PROTECTION_COORDINATION,
                status=AgentStatus.COMPLETED,
                data={
                    "all_coordinated": all_coordinated,
                    "coordination_results": coordination_results,
                    "relay_count": len(relays),
                    "standard": self.standard,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Protection coordination completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Protection coordination failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.PROTECTION_COORDINATION,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        violations = []
        coordination_results = result.data.get("coordination_results", [])

        for cr in coordination_results:
            if not cr.get("coordinated", True):
                violations.append(f"Coordination issue: margin {cr.get('margin', 0):.3f}s")

        if violations:
            result.validation_errors.extend(violations)
            return False
        return True


class ETAPExecutionAgent(BaseAgent):
    """ETAP Execution Agent - Unified Provider Interface.

    Prompt Handle: etap_engineer_agent

    Capabilities:
    - Execute studies via Local (Windows) or Remote (API) providers
    - Launch/close ETAP application
    - Open/create projects
    - Extract results

    Cross-platform compatible via RemoteEtapProvider.
    """

    prompt_handle = "etap_engineer_agent"

    def __init__(self):
        super().__init__("ETAPExecutionAgent")
        from etap_integration.etap_provider import get_etap_provider

        self.provider = get_etap_provider()

        if self.provider.is_available():
            self.logger.info(f"ETAP Provider initialized: {type(self.provider).__name__}")
        else:
            self.logger.warning("No ETAP provider is currently available.")

    @trace_operation(
        "ETAPExecutionAgent.execute", attributes={"component": "orchestrator", "study_type": "etap"}
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute ETAP automation task using the configured provider."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        if not self.provider.is_available():
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=["No ETAP provider available (Linux requires ETAP_WORKER_URL)"],
            )

        try:
            from etap_integration.etap_provider import ETAPStudyType

            self.log_execution(
                f"Executing ETAP task {task.task_id} via {type(self.provider).__name__}"
            )

            project_path = task.parameters.get("project_path")
            study_type_str = task.parameters.get("study_type", "LOAD_FLOW")

            # Map string to ETAPStudyType enum
            try:
                study_type = ETAPStudyType[study_type_str.upper()]
            except KeyError:
                study_type = ETAPStudyType.LOAD_FLOW

            # Execute via provider
            # Note: In a production async environment, this would be offloaded to a thread pool if blocking
            result = self.provider.execute_study(
                project_path=project_path,
                study_type=study_type,
                visible=task.parameters.get("visible", False),
            )

            agent_result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED if result.success else AgentStatus.FAILED,
                data={
                    "success": result.success,
                    "data": result.data,
                    "warnings": result.warnings,
                    "errors": result.errors,
                    "provider": type(self.provider).__name__,
                },
            )

            agent_result.validation_status = self.validate_result(agent_result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            agent_result.execution_time = execution_time

            return agent_result

        except Exception as e:
            self.log_execution(f"ETAP execution failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate ETAP execution results."""
        if not result.data.get("success"):
            errors = result.data.get("errors", [])
            result.validation_errors.extend(errors)
            return False

        return True


class ValidationAgent(BaseAgent):
    """Validation & Verification Agent.

    Prompt Handle: validation_agent

    Performs comprehensive validation of all engineering results:
    - Voltage limits check
    - Thermal loading verification
    - Protection coordination margins
    - IEEE/IEC standards compliance
    - Equipment rating verification
    """

    prompt_handle = "validation_agent"

    def __init__(self):
        super().__init__("ValidationAgent")
        self.standards = {
            "voltage_limits": {"min": 0.95, "max": 1.05},
            "frequency_hz": 60.0,
            "temperature_rise_C": 65,
        }

    @trace_operation("ValidationAgent.execute", attributes={"component": "orchestrator"})
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Validate engineering results."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting validation for task {task.task_id}")

            results_to_validate = task.parameters.get("results", [])
            validation_summary = {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": [],
                "critical_issues": [],
            }

            for agent_result in results_to_validate:
                # Validate based on study type
                if agent_result.study_type == StudyType.LOAD_FLOW:
                    checks = self._validate_load_flow(agent_result)
                elif agent_result.study_type == StudyType.SHORT_CIRCUIT:
                    checks = self._validate_short_circuit(agent_result)
                elif agent_result.study_type == StudyType.HARMONIC_ANALYSIS:
                    checks = self._validate_harmonic(agent_result)
                elif agent_result.study_type == StudyType.OPTIMAL_POWER_FLOW:
                    checks = self._validate_opf(agent_result)
                else:
                    checks = {"status": "unknown", "issues": []}

                validation_summary["total_checks"] += 1
                if checks["status"] == "pass":
                    validation_summary["passed"] += 1
                else:
                    validation_summary["failed"] += 1
                    validation_summary["critical_issues"].extend(checks["issues"])

            overall_valid = validation_summary["failed"] == 0

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # Generic
                status=AgentStatus.COMPLETED,
                data={
                    "validation_summary": validation_summary,
                    "overall_valid": overall_valid,
                    "standards_checked": list(self.standards.keys()),
                },
            )

            result.validation_status = overall_valid
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Validation completed: {validation_summary['passed']}/{validation_summary['total_checks']} passed"
            )
            return result

        except Exception as e:
            self.log_execution(f"Validation failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def _validate_load_flow(self, result: AgentResult) -> Dict:
        """Validate load flow results."""
        issues = []

        if not result.data.get("converged"):
            issues.append("Load flow did not converge")
            return {"status": "fail", "issues": issues}

        # Check voltages
        buses = result.data.get("buses", {})
        for bus_id, bus_data in buses.items():
            v_mag = bus_data.get("voltage_magnitude_pu", 0)
            if v_mag < self.standards["voltage_limits"]["min"]:
                issues.append(f"Bus {bus_id}: Undervoltage {v_mag:.4f} pu")
            elif v_mag > self.standards["voltage_limits"]["max"]:
                issues.append(f"Bus {bus_id}: Overvoltage {v_mag:.4f} pu")

        return {"status": "pass" if not issues else "fail", "issues": issues}

    def _validate_short_circuit(self, result: AgentResult) -> Dict:
        """Validate short circuit results."""
        issues = []

        # Check that fault currents are reasonable
        fault_results = result.data.get("fault_results", {})
        for bus_id, faults in fault_results.items():
            for fault_type, fault_data in faults.items():
                if "fault_current" in fault_data:
                    current = abs(fault_data["fault_current"])
                    if current > 100:  # Example: 100 kA threshold
                        issues.append(
                            f"Bus {bus_id} {fault_type}: Very high fault current {current:.2f} kA"
                        )

        return {"status": "pass" if not issues else "fail", "issues": issues}

    def _validate_harmonic(self, result: AgentResult) -> Dict:
        """Validate harmonic analysis results."""
        issues = []

        violations = result.data.get("violations", [])
        if violations:
            issues.extend(violations)

        resonance = result.data.get("resonance_detected", False)
        if resonance:
            issues.append("Resonance detected - requires filter design")

        return {"status": "pass" if not issues else "fail", "issues": issues}

    def _validate_opf(self, result: AgentResult) -> Dict:
        """Validate OPF results."""
        issues = []

        if not result.data.get("success"):
            issues.append("OPF did not converge")

        return {"status": "pass" if not issues else "fail", "issues": issues}


class ReportGenerationAgent(BaseAgent):
    """Report Generation Agent.

    Prompt Handle: report_agent

    Generates professional engineering reports in multiple formats:
    - PDF (with charts and tables)
    - DOCX (Microsoft Word)
    - XLSX (Excel spreadsheets)

    Report Sectionsences:
    - Executive Summary
    - System Description
    - Study Results
    - Compliance Analysis
    - Recommendations
    """

    prompt_handle = "report_agent"

    def __init__(self):
        super().__init__("ReportGenerationAgent")

    @trace_operation("ReportGenerationAgent.execute", attributes={"component": "orchestrator"})
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Generate engineering report."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting report generation for task {task.task_id}")

            results = task.parameters.get("results", [])
            output_format = task.parameters.get("format", "pdf")
            output_path = task.parameters.get("output_path", "./reports")

            # Generate report content
            report_content = self._compile_report(results)

            # Export in requested format
            if output_format == "pdf":
                file_path = self._export_pdf(report_content, output_path)
            elif output_format == "docx":
                file_path = self._export_docx(report_content, output_path)
            elif output_format == "xlsx":
                file_path = self._export_xlsx(report_content, output_path)
            else:
                raise ValueError(f"Unsupported format: {output_format}")

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # Generic
                status=AgentStatus.COMPLETED,
                data={
                    "report_generated": True,
                    "format": output_format,
                    "file_path": file_path,
                    "sections": list(report_content.keys()),
                },
            )

            result.validation_status = True
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Report generated: {file_path}")
            return result

        except Exception as e:
            self.log_execution(f"Report generation failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def _compile_report(self, results: List[AgentResult]) -> Dict:
        """Compile report content from agent results."""
        report = {
            'title': 'Power System Engineering Analysis Report',
            'generated_at': datetime.now(UTC).isoformat(),
            'executive_summary': '',
            'load_flow_results': {},
            'short_circuit_results': {},
            'harmonic_results': {},
            'opf_results': {},
            'validation_summary': {},
            'recommendations': []
        }

        for result in results:
            if result.study_type == StudyType.LOAD_FLOW:
                report["load_flow_results"] = result.data
            elif result.study_type == StudyType.SHORT_CIRCUIT:
                report["short_circuit_results"] = result.data
            elif result.study_type == StudyType.HARMONIC_ANALYSIS:
                report["harmonic_results"] = result.data
            elif result.study_type == StudyType.OPTIMAL_POWER_FLOW:
                report["opf_results"] = result.data

        # Generate executive summary
        report["executive_summary"] = self._generate_executive_summary(report)

        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(report)

        return report

    def _generate_executive_summary(self, report: Dict) -> str:
        """Generate executive summary text."""
        summary_lines = [
            "EXECUTIVE SUMMARY",
            "=" * 60,
            "",
            f"Report Generatedenced on: {report['generated_at']}",
            "",
        ]

        # Load flow summary
        lf = report.get("load_flow_results", {})
        if lf:
            converged = lf.get("converged", False)
            summary_lines.append(
                f"Load Flow Analysis: {'Converged' if converged else 'Did Not Converge'}"
            )

        # Short circuit summary
        sc = report.get("short_circuit_results", {})
        if sc:
            summary_lines.append("Short Circuit Analysis: Completed per IEC 60909")

        # Harmonic summary
        harm = report.get("harmonic_results", {})
        if harm:
            violations = harm.get("violations", [])
            summary_lines.append(f"Harmonic Analysis: {len(violations)} IEEE 519 violations found")

        return "\n".join(summary_lines)

    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate engineering recommendations."""
        recommendations = []

        # Check for voltage issues
        lf = report.get("load_flow_results", {})
        buses = lf.get("buses", {})
        for bus_id, bus_data in buses.items():
            v_mag = bus_data.get("voltage_magnitude_pu", 1.0)
            if v_mag < 0.95:
                recommendations.append(
                    f"Bus {bus_id}: Consider adding reactive compensation to improve voltage"
                )

        # Check for harmonic violations
        harm = report.get("harmonic_results", {})
        if harm.get("resonance_detected"):
            recommendations.append("Install passive harmonic filters to mitigate resonance")

        if not recommendations:
            recommendations.append("System operates within acceptable limits")

        return recommendations

    def _export_pdf(self, content: Dict, output_path: str) -> str:
        """Export report as PDF using the reporting module."""
        try:
            from reporting.advanced_reports import PDFReportGenerator, ReportMetadata

            metadata = ReportMetadata(
                title=content.get('title', 'Engineering Report'),
                author='AhmedETAP',
                date=datetime.now(UTC).isoformat()
            )
            generator = PDFReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pdf"
            generator.generate_report(metadata, content, file_path)
            self.log_execution(f"PDF report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "PDF generator unavailable (reportlab not installed) — using placeholder", "WARNING"
            )
            return ""  # No file generated
        except Exception as e:
            self.log_execution(f"PDF generation failed: {e}", "ERROR")
            return ""  # Indicate failure

    def _export_docx(self, content: Dict, output_path: str) -> str:
        """Export report as DOCX using the reporting module."""
        try:
            from reporting.advanced_reports import DOCXReportGenerator, ReportMetadata

            metadata = ReportMetadata(
                title=content.get('title', 'Engineering Report'),
                author='AhmedETAP',
                date=datetime.now(UTC).isoformat()
            )
            generator = DOCXReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.docx"
            generator.generate_report(metadata, content, file_path)
            self.log_execution(f"DOCX report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "DOCX generator unavailable (python-docx not installed) — using placeholder",
                "WARNING",
            )
            return ""  # No file generated
        except Exception as e:
            self.log_execution(f"DOCX generation failed: {e}", "ERROR")
            return ""  # Indicate failure

    def _export_xlsx(self, content: Dict, output_path: str) -> str:
        """Export report as XLSX using the reporting module."""
        try:
            from reporting.advanced_reports import ReportMetadata, XLSXReportGenerator

            metadata = ReportMetadata(
                title=content.get('title', 'Engineering Report'),
                author='AhmedETAP',
                date=datetime.now(UTC).isoformat()
            )
            generator = XLSXReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
            generator.generate_report(metadata, content, file_path)
            self.log_execution(f"XLSX report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "XLSX generator unavailable (openpyxl not installed) — using placeholder", "WARNING"
            )
            return ""  # No file generated
        except Exception as e:
            self.log_execution(f"XLSX generation failed: {e}", "ERROR")
            return ""  # Indicate failure


class ChiefEngineeringOrchestrator:
    """
    Chief Engineering Orchestrator Agent.

    Prompt Handle: power_system_coordinator_agent

    Coordinates all specialized agents to execute complete engineering workflows.

    Workflow Example:
    User Goal: "Optimize this industrial power network"

    Orchestrator executes:
    1. Load Flow Analysis → Validate
    2. Loss Calculation
    3. OPF Optimization
    4. Capacitor Placement Suggestion
    5. Fault Analysis → Validate
    6. Harmonic Analysis → Validate
    7. Report Generation

    All without additional user intervention.
    """

    prompt_handle = "power_system_coordinator_agent"

    def __init__(self):
        self.agents = {
            "load_flow": LoadFlowAgent(),
            "short_circuit": ShortCircuitAgent(),
            "harmonic": HarmonicAnalysisAgent(),
            "opf": OptimalPowerFlowAgent(),
            "protection": ProtectionCoordinationAgent(),
            "etap_execution": ETAPExecutionAgent(),
            "validation": ValidationAgent(),
            "report": ReportGenerationAgent(),
        }

        # Guard-skills agent for automatic code quality review
        self._code_guard_agent = None
        try:
            from agents.code_guard_agent import CodeGuardAgent

            self._code_guard_agent = CodeGuardAgent()
            self.agents["code_guard"] = self._code_guard_agent
        except ImportError:
            self.logger = logging.getLogger("orchestrator")
            self.logger.info("CodeGuardAgent not available — guard-skills review disabled")

        self.task_queue: List[EngineeringTask] = []
        self.completed_tasks: Dict[str, EngineeringTask] = {}
        self.logger = logging.getLogger("orchestrator")

        # Load orchestrator's own prompt for coordination guidance
        self._system_prompt: str | None = None
        self._load_prompt()

    def _load_prompt(self) -> None:
        """Load the orchestrator's prompt for coordination guidance."""
        try:
            from agents.prompt_loader import get_system_prompt

            self._system_prompt = get_system_prompt(self.prompt_handle)
            self.logger.info(
                "Orchestrator prompt loaded from handle '%s' (%d chars)",
                self.prompt_handle,
                len(self._system_prompt) if self._system_prompt else 0,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to load orchestrator prompt: %s. Using default coordination logic.",
                exc,
            )

    def get_agents_info(self) -> Dict[str, Any]:
        """Return metadata for all registered agents including prompt info."""
        return {
            "orchestrator": {
                "prompt_handle": self.prompt_handle,
                "prompt_loaded": self._system_prompt is not None,
            },
            "agents": {key: agent.get_agent_info() for key, agent in self.agents.items()},
        }

    async def submit_task(self, task: EngineeringTask):
        """Submit engineering task for execution."""
        self.task_queue.append(task)
        self.logger.info(f"Task submitted: {task.task_id} - {task.description}")

    @trace_operation("execute_autonomous_workflow", attributes={"component": "orchestrator"})
    async def execute_autonomous_workflow(
        self, user_goal: str, system_data: Any, parameters: Dict = None
    ) -> Dict[str, Any]:
        """
        Execute complete autonomous engineering workflow based on user goal.

        Parameters:
        user_goal: Natural language description of desired outcome
        system_data: Power system model
        parameters: Additional parameters

        Returns:
        Complete workflow results
        """
        self.logger.info(f"Starting autonomous workflow for goal: {user_goal}")

        # Parse user goal and determine required studies
        required_studies = self._parse_user_goal(user_goal)

        # Create task
        task = EngineeringTask(
            task_id=f"workflow_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            description=user_goal,
            study_types=required_studies,
            parameters={"system": system_data, **(parameters or {})},
        )

        # Execute workflow
        results = await self._execute_workflow(task)

        # Store completed task
        task.results = results
        task.status = AgentStatus.COMPLETED
        self.completed_tasks[task.task_id] = task

        self.logger.info(f"Workflow completed: {task.task_id}")

        return {
            "task_id": task.task_id,
            "goal": user_goal,
            "studies_performed": [r.study_type.value for r in results],
            "results": results,
            "all_validated": all(r.validation_status for r in results),
        }

    def _parse_user_goal(self, goal: str) -> List[StudyType]:
        """Parse user goal to determine required studies."""
        goal_lower = goal.lower()
        studies = []

        # Keyword-based study selection
        if any(kw in goal_lower for kw in ["load flow", "power flow", "voltage"]):
            studies.append(StudyType.LOAD_FLOW)

        if any(kw in goal_lower for kw in ["fault", "short circuit", "sc"]):
            studies.append(StudyType.SHORT_CIRCUIT)

        if any(kw in goal_lower for kw in ["harmonic", "distortion", "thd"]):
            studies.append(StudyType.HARMONIC_ANALYSIS)

        if any(kw in goal_lower for kw in ["optimize", "optimization", "opf", "economic"]):
            studies.append(StudyType.OPTIMAL_POWER_FLOW)

        if any(kw in goal_lower for kw in ["protect", "coordination", "relay"]):
            studies.append(StudyType.PROTECTION_COORDINATION)

        # If no specific studies identified, run comprehensive analysis
        if not studies:
            studies = [StudyType.LOAD_FLOW, StudyType.SHORT_CIRCUIT, StudyType.HARMONIC_ANALYSIS]

        return studies

    @trace_operation("_execute_workflow", attributes={"component": "orchestrator"})
    async def _execute_workflow(self, task: EngineeringTask) -> List[AgentResult]:
        """Execute workflow by coordinating agents with parallel execution."""
        results = []

        # Determine execution order based on dependencies
        execution_order = self._determine_execution_order(task.study_types)

        # Separate load flow (must run first) from independent studies
        dependent_studies = []
        independent_studies = []

        for study_type in execution_order:
            if study_type == StudyType.LOAD_FLOW:
                dependent_studies.append(study_type)
            else:
                independent_studies.append(study_type)

        # Phase 1: Run load flow first (dependency for others)
        for study_type in dependent_studies:
            agent = self._get_agent_for_study(study_type)
            if agent:
                self.logger.info(f"Executing {study_type.value} via {agent.agent_name}")
                result = await agent.execute(task)
                results.append(result)
                if not result.validation_status:
                    self.logger.warning(
                        f"Validation failed for {study_type.value}: {result.validation_errors}"
                    )

        # Phase 2: Run independent studies in parallel
        if independent_studies:
            parallel_tasks = []
            for study_type in independent_studies:
                agent = self._get_agent_for_study(study_type)
                if agent:
                    self.logger.info(f"Executing {study_type.value} via {agent.agent_name}")
                    parallel_tasks.append(agent.execute(task))

            if parallel_tasks:
                parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                for pr in parallel_results:
                    if isinstance(pr, Exception):
                        self.logger.error(f"Parallel agent failed: {pr}")
                    else:
                        results.append(pr)
                        if not pr.validation_status:
                            self.logger.warning(f"Validation failed: {pr.validation_errors}")

        # Phase 3: Final validation pass
        validation_task = EngineeringTask(
            task_id=f"validation_{task.task_id}",
            description="Final validation of all results",
            study_types=[],
            parameters={"results": results},
        )

        validation_result = await self.agents["validation"].execute(validation_task)
        results.append(validation_result)

        # Phase 3.5: Guard-skills code quality review (if enabled)
        # Automatically review any AI-generated code in the task parameters
        if self._code_guard_agent:
            try:
                code_to_review = task.parameters.get("source", "")
                if code_to_review:
                    guard_task = EngineeringTask(
                        task_id=f"guard_{task.task_id}",
                        description="AI code quality guard review",
                        study_types=[],
                        parameters={
                            "source": code_to_review,
                            "guard_type": "all",
                            "language": "python",
                        },
                    )
                    guard_result = await self._code_guard_agent.execute(guard_task)
                    results.append(guard_result)
                    if not guard_result.validation_status:
                        self.logger.warning(
                            "Guard-skills review found MUST_FIX violations: %s",
                            guard_result.data.get("must_fix_total", 0),
                        )
            except Exception as guard_err:
                self.logger.warning("Guard review failed (non-blocking): %s", guard_err)

        # Phase 4: Generate report if all validations pass
        if validation_result.validation_status:
            report_task = EngineeringTask(
                task_id=f"report_{task.task_id}",
                description="Generate final report",
                study_types=[],
                parameters={"results": results, "format": "pdf", "output_path": "./reports"},
            )

            report_result = await self.agents["report"].execute(report_task)
            results.append(report_result)

        return results

    def _determine_execution_order(self, study_types: List[StudyType]) -> List[StudyType]:
        """Determine optimal execution order based on dependencies."""
        # Load flow should run first (provides base case)
        # Then fault analysis, harmonics, OPF

        priority_order = {
            StudyType.LOAD_FLOW: 1,
            StudyType.SHORT_CIRCUIT: 2,
            StudyType.HARMONIC_ANALYSIS: 3,
            StudyType.OPTIMAL_POWER_FLOW: 4,
            StudyType.PROTECTION_COORDINATION: 5,
        }

        return sorted(study_types, key=lambda x: priority_order.get(x, 99))

    def _get_agent_for_study(self, study_type: StudyType) -> BaseAgent | None:
        """Get appropriate agent for study type."""
        agent_mapping = {
            StudyType.LOAD_FLOW: "load_flow",
            StudyType.SHORT_CIRCUIT: "short_circuit",
            StudyType.HARMONIC_ANALYSIS: "harmonic",
            StudyType.OPTIMAL_POWER_FLOW: "opf",
            StudyType.PROTECTION_COORDINATION: "protection",
        }

        agent_key = agent_mapping.get(study_type)
        return self.agents.get(agent_key)

    def get_study_type_mapping(self) -> Dict[str, str]:
        """Return mapping of study type strings to agent keys.

        Provides a convenience lookup for external callers that identify
        studies by human-readable names (e.g. ``"load_flow"``) and need
        to resolve them to the corresponding agent key registered in
        ``self.agents``.

        Returns:
            Dict mapping study type strings to agent key strings.
        """
        return {
            "load_flow": "load_flow",
            "short_circuit": "short_circuit",
            "harmonic": "harmonic",
            "harmonic_analysis": "harmonic",
            "opf": "opf",
            "optimal_power_flow": "opf",
            "protection": "protection",
            "protection_coordination": "protection",
            "etap_execution": "etap_execution",
            "validation": "validation",
            "report": "report",
        }

    @trace_operation("execute_parallel_studies", attributes={"component": "orchestrator"})
    async def execute_parallel_studies(
        self,
        study_types: List[str],
        system_data: Any,
        parameters: Dict[str, Any] | None = None,
        max_workers: int = 4,
        benchmark: bool = False,
    ) -> Dict[str, Any]:
        """Execute multiple independent studies in parallel.

        Accepts a list of study type strings, resolves each to the
        appropriate agent, creates ``EngineeringTask`` objects, and runs
        them concurrently using ``asyncio.gather``.  An optional
        *benchmark* mode also executes the same studies sequentially
        and includes a timing comparison in the result dict.

        Args:
            study_types: List of study type strings (e.g.
                ``["load_flow", "short_circuit"]``).  Each string is
                resolved via :meth:`get_study_type_mapping`.
            system_data: Power system model data passed to every study.
            parameters: Optional dict of extra parameters merged into
                each task's ``parameters`` field.
            max_workers: Upper bound on concurrent coroutines (used to
                size the asyncio Semaphore that gates execution).
            benchmark: If ``True``, also run all studies sequentially
                and include a timing comparison in the result.

        Returns:
            Dict with keys:

                - ``task_id`` – unique workflow identifier
                - ``study_types`` – the resolved study type list
                - ``parallel_results`` – dict mapping study type to
                  ``AgentResult``
                - ``parallel_time_seconds`` – wall-clock time for the
                  parallel run
                - ``sequential_results`` – (only when *benchmark* is
                  True) dict mapping study type to ``AgentResult``
                - ``sequential_time_seconds`` – (only when *benchmark*
                  is True) wall-clock time for the sequential run
                - ``speedup_factor`` – (only when *benchmark* is True)
                  ``sequential_time / parallel_time``
                - ``benchmark`` – whether benchmark mode was active
        """
        parameters = parameters or {}
        study_type_map = self.get_study_type_mapping()

        # -----------------------------------------------------------
        # Resolve study type strings → (agent_key, agent) pairs
        # -----------------------------------------------------------
        resolved: List[tuple] = []  # [(study_str, agent_key, agent)]
        for study_str in study_types:
            agent_key = study_type_map.get(study_str)
            if agent_key is None:
                self.logger.warning("Unknown study type '%s' – skipping", study_str)
                continue
            agent = self.agents.get(agent_key)
            if agent is None:
                self.logger.warning(
                    "No agent registered for key '%s' (study '%s') – skipping",
                    agent_key,
                    study_str,
                )
                continue
            resolved.append((study_str, agent_key, agent))

        if not resolved:
            self.logger.error("No valid study types resolved – nothing to execute")
            return {
                "task_id": None,
                "study_types": [],
                "parallel_results": {},
                "parallel_time_seconds": 0.0,
                "benchmark": benchmark,
            }

        task_id = (
            f"parallel_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        )

        # -----------------------------------------------------------
        # Helper: create an EngineeringTask for a single study
        # -----------------------------------------------------------
        def _make_task(study_str: str, agent_key: str) -> EngineeringTask:
            return EngineeringTask(
                task_id=f"{task_id}_{study_str}",
                description=f"Parallel study: {study_str}",
                study_types=[s for s in StudyType if s.value == study_str or s.value == agent_key][
                    :1
                ],  # best-effort StudyType match
                parameters={"system": system_data, **parameters},
            )

        # -----------------------------------------------------------
        # Semaphore to cap concurrency at max_workers
        # -----------------------------------------------------------
        semaphore = asyncio.Semaphore(max_workers)

        async def _run_with_semaphore(
            study_str: str, agent: BaseAgent, task: EngineeringTask
        ) -> tuple:
            """Run a single agent.execute, bounded by the semaphore."""
            async with semaphore:
                self.logger.info(
                    "[parallel] Starting %s via %s",
                    study_str,
                    agent.agent_name,
                )
                try:
                    result = await agent.execute(task)
                    self.logger.info(
                        "[parallel] Completed %s (status=%s)",
                        study_str,
                        result.status.value,
                    )
                    return (study_str, result)
                except Exception as exc:
                    self.logger.error("[parallel] Failed %s: %s", study_str, exc)
                    # Return a failure AgentResult instead of propagating
                    return (
                        study_str,
                        AgentResult(
                            agent_name=agent.agent_name,
                            study_type=task.study_types[0]
                            if task.study_types
                            else StudyType.LOAD_FLOW,
                            status=AgentStatus.FAILED,
                            data={},
                            validation_status=False,
                            validation_errors=[str(exc)],
                        ),
                    )

        # -----------------------------------------------------------
        # Parallel execution
        # -----------------------------------------------------------
        self.logger.info(
            "Starting parallel execution of %d studies (max_workers=%d)",
            len(resolved),
            max_workers,
        )
        parallel_start = time.perf_counter()

        parallel_coros = [
            _run_with_semaphore(study_str, agent, _make_task(study_str, agent_key))
            for study_str, agent_key, agent in resolved
        ]
        parallel_raw = await asyncio.gather(*parallel_coros, return_exceptions=True)

        parallel_time = time.perf_counter() - parallel_start

        parallel_results: Dict[str, AgentResult] = {}
        for item in parallel_raw:
            if isinstance(item, Exception):
                self.logger.error("[parallel] Unexpected exception: %s", item)
                continue
            study_str, result = item
            parallel_results[study_str] = result

        result: Dict[str, Any] = {
            "task_id": task_id,
            "study_types": [s for s, _, _ in resolved],
            "parallel_results": parallel_results,
            "parallel_time_seconds": round(parallel_time, 4),
            "benchmark": benchmark,
        }

        # -----------------------------------------------------------
        # Optional benchmark: sequential execution for comparison
        # -----------------------------------------------------------
        if benchmark:
            self.logger.info("Benchmark: running studies sequentially for comparison")
            sequential_start = time.perf_counter()

            sequential_results: Dict[str, AgentResult] = {}
            for study_str, agent_key, agent in resolved:
                task = _make_task(study_str, agent_key)
                self.logger.info(
                    "[sequential] Starting %s via %s",
                    study_str,
                    agent.agent_name,
                )
                try:
                    seq_result = await agent.execute(task)
                    sequential_results[study_str] = seq_result
                except Exception as exc:
                    self.logger.error("[sequential] Failed %s: %s", study_str, exc)
                    sequential_results[study_str] = AgentResult(
                        agent_name=agent.agent_name,
                        study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                        status=AgentStatus.FAILED,
                        data={},
                        validation_status=False,
                        validation_errors=[str(exc)],
                    )

            sequential_time = time.perf_counter() - sequential_start

            speedup = sequential_time / parallel_time if parallel_time > 0 else float("inf")

            result["sequential_results"] = sequential_results
            result["sequential_time_seconds"] = round(sequential_time, 4)
            result["speedup_factor"] = round(speedup, 2)

            self.logger.info(
                "Benchmark complete – parallel: %.4fs, sequential: %.4fs, speedup: %.2fx",
                parallel_time,
                sequential_time,
                speedup,
            )

        self.logger.info(
            "Parallel studies completed: task_id=%s, studies=%d, parallel_time=%.4fs",
            task_id,
            len(parallel_results),
            parallel_time,
        )

        return result

    async def get_task_status(self, task_id: str) -> EngineeringTask | None:
        """Get status of a task."""
        return self.completed_tasks.get(task_id)


# Singleton instance
_orchestrator = None


def get_orchestrator() -> ChiefEngineeringOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChiefEngineeringOrchestrator()
    return _orchestrator
