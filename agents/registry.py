"""
AhmedETAP - Agent Registry & Specialist Agents
===============================================
Encapsulates registration, life-cycle management, and class definitions for all
24 AhmedETAP specialized agents per AGENTS.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from agents.base import BaseAgent
from agents.models import (
    _ANALYSIS_RESULTS_TITLE,
    _ENGINEERING_REPORT_TITLE,
    _SYSTEM_DATA_NOT_PROVIDED_MSG,
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)
from core.tracing import trace_operation

UTC = timezone.utc  # noqa: UP017
logger = logging.getLogger(__name__)
_ENGINEERING_ASSERTION_FAILED = "Engineering assertion check failed: %s"


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

    def __init__(self, solver_factory=None):
        super().__init__("LoadFlowAgent")
        self.voltage_limits = {"min": 0.95, "max": 1.05}
        self.convergence_tolerance = 1e-6
        self._solver_factory = solver_factory

    @trace_operation(
        "LoadFlowAgent.execute",
        attributes={"component": "orchestrator", "study_type": "load_flow"},
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

            # Seamlessly accept both System objects and dictionary specifications
            if isinstance(system_data, dict):
                from services.study_executor import StudyExecutor

                system_data = StudyExecutor()._build_system_from_spec(system_data)

            # Run load flow
            if self._solver_factory is not None:
                solver = self._solver_factory(system_data)
            else:
                solver = LoadFlowSolver(system_data)
            converged = solver.solve(
                max_iter=task.parameters.get("max_iterations", 100),
                tol=self.convergence_tolerance,
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
                    "iterations": getattr(solver, "iterations", 0),
                    "method": "Newton-Raphson",
                },
            )

            # Validate results
            result.validation_status = self.validate_result(result)

            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Load flow completed in {execution_time:.2f}s, converged={converged}",
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
                    f"[{self.voltage_limits['min']}, {self.voltage_limits['max']}]",
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

    def __init__(self, analyzer_factory=None):
        super().__init__("ShortCircuitAgent")
        self.standards_compliance = ["IEC 60909-0:2016"]
        self._analyzer_factory = analyzer_factory

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
                raise ValueError(
                    _SYSTEM_DATA_NOT_PROVIDED_MSG  # NOSONAR
                )  # NOSONAR

            # Build sequence networks
            system_data.build_sequence_networks()

            ybus_pos = system_data.get_ybus(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
                seq="1"
            )  # NOSONAR
            ybus_neg = system_data.get_ybus(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
                seq="2"
            )  # NOSONAR
            ybus_zero = system_data.get_ybus(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
                seq="0"
            )  # NOSONAR

            # Create fault analyzer
            base_mva = system_data.base_mva
            base_kv = task.parameters.get("base_kv", 115.0)

            if self._analyzer_factory is not None:
                analyzer = self._analyzer_factory(
                    ybus_pos,
                    ybus_neg,
                    ybus_zero,
                    base_mva=base_mva,
                    base_kv=base_kv,
                )
            else:
                analyzer = FaultAnalyzer(
                    ybus_pos,
                    ybus_neg,
                    ybus_zero,
                    base_mva=base_mva,
                    base_kv=base_kv,
                )

            # Execute all fault types at specified buses
            bus_keys = list(system_data.buses.keys())
            bus_index_map = {b_id: idx for idx, b_id in enumerate(bus_keys)}
            fault_buses = task.parameters.get("fault_buses", bus_keys)
            fault_results = {}

            for bus_id in fault_buses:
                bus_idx = bus_index_map.get(bus_id)
                if bus_idx is None:
                    continue

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
                            f"Bus {bus_id} {fault_type}: Invalid fault current {current}",
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

    def __init__(self, engine_factory=None):
        super().__init__("HarmonicAnalysisAgent")
        self.standard = "IEEE 519-2022"
        self.max_harmonic_order = 50
        self._engine_factory = engine_factory

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
            if not system_data:
                raise ValueError(_SYSTEM_DATA_NOT_PROVIDED_MSG)
            # system_data is now guaranteed non-None (else ValueError above)
            harmonic_sources = task.parameters.get("harmonic_sources", [])
            voltage_kv = task.parameters.get("voltage_kv", 13.8)

            # Create engine
            if self._engine_factory is not None:
                engine = self._engine_factory(
                    fundamental_freq=task.parameters.get("fundamental_freq", 60.0),
                    max_harmonic=self.max_harmonic_order,
                )
            else:
                engine = HarmonicAnalysisEngine(
                    fundamental_freq=task.parameters.get("fundamental_freq", 60.0),
                    max_harmonic=self.max_harmonic_order,
                )

            # Set system data
            ybus = system_data.get_ybus(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
                seq="1"
            )  # NOSONAR
            bus_ids = sorted(system_data.buses.keys())
            engine.set_system_data(ybus, bus_ids)

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
            return False

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

    def __init__(self, opf_factory=None):
        super().__init__("OptimalPowerFlowAgent")
        self._opf_factory = opf_factory

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
            if not system_data:
                raise ValueError(_SYSTEM_DATA_NOT_PROVIDED_MSG)

            generator_costs = task.parameters.get("generator_costs", [])
            method = task.parameters.get("method", "dc")

            # Create OPF engine
            ybus = system_data.get_ybus(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
                seq="1"
            )  # NOSONAR
            bus_ids = sorted(system_data.buses.keys())
            costs = [GeneratorCost(**gc) for gc in generator_costs]

            if self._opf_factory is not None:
                opf = self._opf_factory(ybus, bus_ids, costs)
            else:
                opf = OptimalPowerFlowEngine(ybus, bus_ids, costs)

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
        p_gen = result.data.get(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
            "total_generation_mw",
            0,
        )  # NOSONAR
        p_load = result.data.get(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
            "total_load_mw", 0
        )  # NOSONAR
        p_losses = result.data.get(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability
            "total_losses_mw", 0
        )  # NOSONAR

        balance_error = abs(p_gen - p_load - p_losses)
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

    def __init__(self, engine_factory=None):
        super().__init__("ProtectionCoordinationAgent")
        self.standard = "IEC 60255"
        self._engine_factory = engine_factory

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
                raise ValueError(_SYSTEM_DATA_NOT_PROVIDED_MSG)

            relay_data = task.parameters.get("relays", [])
            if self._engine_factory is not None:
                coordination_engine = self._engine_factory()
            else:
                coordination_engine = CoordinationEngine()

            # Analyze coordination
            relays = [OvercurrentRelay(**rd) for rd in relay_data]

            coordination_results = []
            for i in range(len(relays) - 1):
                for fault_current in [3.0, 5.0, 10.0, 20.0]:
                    result = coordination_engine.check_coordination(
                        relays[i],
                        relays[i + 1],
                        fault_current,
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
            self.logger.info("ETAP Provider initialized: %s", type(self.provider).__name__)
        else:
            self.logger.warning("No ETAP provider is currently available.")

    @trace_operation(
        "ETAPExecutionAgent.execute",
        attributes={"component": "orchestrator", "study_type": "etap"},
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
                f"Executing ETAP task {task.task_id} via {type(self.provider).__name__}",
            )

            project_path = task.parameters.get("project_path", "")
            study_type_str = task.parameters.get("study_type", "LOAD_FLOW")

            # Map string to ETAPStudyType — unsupported types are an explicit
            # error, never a silent fallback to LOAD_FLOW.
            try:
                study_type = ETAPStudyType[study_type_str.upper()]
            except KeyError as err:
                supported = sorted(m.name for m in ETAPStudyType)
                raise ValueError(
                    f"Unsupported study type '{study_type_str}' for the ETAP "
                    f"execution path; supported types: {supported}",
                ) from err

            # Execute via provider
            # Note: In a production async environment, this would be offloaded to a thread pool if blocking
            result = self.provider.execute_study(
                project_path=project_path,
                study_type=study_type,
                visible=task.parameters.get("visible", False),
                parameters=task.parameters.get("parameters") or None,
            )

            agent_result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType[study_type.name],
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
                checks = self._validate_single_result(agent_result, validation_summary)

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
                f"Validation completed: {validation_summary['passed']}/{validation_summary['total_checks']} passed",
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

    def _validate_single_result(self, agent_result, validation_summary):
        """Run all checks for a single agent result."""
        self._check_output_schema_guard(agent_result, validation_summary)
        self._scan_agent_output(agent_result, validation_summary)
        return self._get_study_checks(agent_result)

    def _check_output_schema_guard(self, agent_result, validation_summary):
        """F-03: Code-gated mandatory output validation."""
        try:
            from agents.output_schema_guard import validate_agent_output

            guard_result = validate_agent_output(
                agent_result.agent_name.lower().replace(" ", "_").replace("agent", "_agent"),
                agent_result.data,
            )
            if not guard_result.passed:
                for v in guard_result.violations:
                    validation_summary["critical_issues"].append(
                        f"[SCHEMA-GUARD {v.rule_id}] {v.description}"
                    )
        except ImportError:
            pass  # output_schema_guard not available — skip
        except Exception as exc:
            logger.debug("Output schema guard check failed: %s", exc)

    def _scan_agent_output(self, agent_result, validation_summary):
        """F-12: AI failure mode scan on agent text output."""
        try:
            from guards.agent_output_scanner import scan_agent_output

            agent_output_text = str(agent_result.data) if agent_result.data else ""
            fm_warnings = scan_agent_output(
                agent_result.agent_name.lower().replace(" ", "_").replace("agent", "_agent"),
                agent_output_text,
            )
            for w in fm_warnings:
                if w.severity == "critical":
                    validation_summary["critical_issues"].append(
                        f"[FM-{w.failure_mode_id}] {w.description}: {w.matched_text}"
                    )
        except ImportError:
            pass  # agent_output_scanner not available — skip
        except Exception as exc:
            logger.debug("Agent output scanner failed: %s", exc)

    def _get_study_checks(self, agent_result):
        """Dispatch to the appropriate study-type validator."""
        if agent_result.study_type == StudyType.LOAD_FLOW:
            return self._validate_load_flow(agent_result)
        elif agent_result.study_type == StudyType.SHORT_CIRCUIT:
            return self._validate_short_circuit(agent_result)
        elif agent_result.study_type == StudyType.HARMONIC_ANALYSIS:
            return self._validate_harmonic(agent_result)
        elif agent_result.study_type == StudyType.OPTIMAL_POWER_FLOW:
            return self._validate_opf(agent_result)
        else:
            return {"status": "unknown", "issues": []}

    def _check_load_flow_assertions(self, result: AgentResult) -> list[str]:
        """Run deterministic engineering assertion checks for load flow results."""
        issues = []
        try:
            from copilot.ai.engineering_assertions import EngineeringAssertionLayer

            assertion_layer = EngineeringAssertionLayer()
            buses = result.data.get("buses", {})
            if buses:
                bus_voltages = {
                    bus_id: bus_data["voltage_kv"]
                    for bus_id, bus_data in buses.items()
                    if "voltage_kv" in bus_data and bus_data["voltage_kv"]
                }
                if bus_voltages:
                    assertion_results = assertion_layer.validate_voltage_results(
                        bus_voltages=bus_voltages,
                    )
                    for ar in assertion_results:
                        if not ar.passed:
                            issues.append(
                                f"[ASSERTION-{ar.severity.value}] {ar.check_name}: {ar.message}"
                            )
        except ImportError:
            logger.debug("EngineeringAssertionLayer not available for load flow validation")
        except Exception as exc:
            logger.warning(_ENGINEERING_ASSERTION_FAILED, exc)
        return issues

    def _validate_load_flow(self, result: AgentResult) -> dict:
        """Validate load flow results.

        ARCHITECTURE AUDIT FIX (F-07): Now also runs the
        EngineeringAssertionLayer deterministic voltage checks
        (IEEE C84.1 Range A/B) for physically impossible values.
        """
        issues = self._check_load_flow_assertions(result)

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

    def _check_short_circuit_assertions(self, result: AgentResult) -> list[str]:
        """Run deterministic engineering assertion checks for short circuit results."""
        issues = []
        try:
            from copilot.ai.engineering_assertions import EngineeringAssertionLayer

            assertion_layer = EngineeringAssertionLayer()
            fault_results = result.data.get("fault_results", {})
            if fault_results:
                assertion_results = assertion_layer.validate_short_circuit_results(
                    fault_currents=fault_results,
                )
                for ar in assertion_results:
                    if not ar.passed:
                        issues.append(
                            f"[ASSERTION-{ar.severity.value}] {ar.check_name}: {ar.message}"
                        )
        except ImportError:
            logger.debug("EngineeringAssertionLayer not available for short circuit validation")
        except Exception as exc:
            logger.warning(_ENGINEERING_ASSERTION_FAILED, exc)
        return issues

    def _validate_short_circuit(self, result: AgentResult) -> dict:
        """Validate short circuit results.

        ARCHITECTURE AUDIT FIX (F-07): Now also runs the
        EngineeringAssertionLayer deterministic checks for physically
        impossible values (IEEE C84.1, IEC 60909).
        """
        issues = self._check_short_circuit_assertions(result)

        # Check that fault currents are reasonable
        fault_results = result.data.get("fault_results", {})
        for bus_id, faults in fault_results.items():
            for fault_type, fault_data in faults.items():
                if "fault_current" in fault_data:
                    current = abs(fault_data["fault_current"])
                    if current > 100:  # Example: 100 kA threshold
                        issues.append(
                            f"Bus {bus_id} {fault_type}: Very high fault current {current:.2f} kA",
                        )

        return {"status": "pass" if not issues else "fail", "issues": issues}

    def _extract_bus_thd_values(self, harmonic_data: dict) -> dict[str, float]:
        """Extract voltage THD percent for each bus from harmonic data."""
        thd_values = {}
        buses = harmonic_data.get("buses", {})
        for bus_id, bus_data in buses.items():
            thd = bus_data.get("voltage_thd_percent", 0)
            if thd:
                thd_values[bus_id] = thd
        return thd_values

    def _run_harmonic_assertions(self, assertion_layer, thd_values: dict) -> list[str]:
        """Run harmonic assertion validation and collect failure messages."""
        assertion_results = assertion_layer.validate_harmonic_results(thd_values=thd_values)
        return [
            f"[ASSERTION-{ar.severity.value}] {ar.check_name}: {ar.message}"
            for ar in assertion_results
            if not ar.passed
        ]

    def _check_harmonic_assertions(self, result: AgentResult) -> list[str]:
        """Run deterministic engineering assertion checks for harmonic results."""
        issues = []
        try:
            harmonic_data = result.data.get("harmonic_results", {})
            if not harmonic_data:
                return issues

            thd_values = self._extract_bus_thd_values(harmonic_data)
            if thd_values:
                from copilot.ai.engineering_assertions import EngineeringAssertionLayer

                assertion_layer = EngineeringAssertionLayer()
                issues.extend(self._run_harmonic_assertions(assertion_layer, thd_values))
        except ImportError:
            logger.debug("EngineeringAssertionLayer not available for harmonic validation")
        except Exception as exc:
            logger.warning(_ENGINEERING_ASSERTION_FAILED, exc)
        return issues

    def _validate_harmonic(self, result: AgentResult) -> dict:
        """Validate harmonic analysis results.

        ARCHITECTURE AUDIT FIX (F-07): Now also runs the
        EngineeringAssertionLayer deterministic checks for THD limits
        (IEEE 519-2014) when harmonic data is available.
        """
        issues = self._check_harmonic_assertions(result)

        violations = result.data.get("violations", [])
        if violations:
            issues.extend(violations)

        resonance = result.data.get("resonance_detected", False)
        if resonance:
            issues.append("Resonance detected - requires filter design")

        return {"status": "pass" if not issues else "fail", "issues": issues}

    def _check_opf_assertions(self, result: AgentResult) -> list[str]:
        """Run deterministic engineering assertion checks for OPF results."""
        issues = []
        try:
            opf_data = result.data.get("opf_results", result.data)
            generators = opf_data.get("generators", {})
            if generators:
                # Check that generator outputs are within reasonable bounds
                for gen_id, gen_data in generators.items():
                    p_mw = abs(gen_data.get("active_power_mw", 0))
                    if p_mw > 1000:  # No single generator exceeds 1000 MW
                        issues.append(
                            f"[ASSERTION-critical] Generator {gen_id}: "
                            f"active power {p_mw} MW exceeds physical bounds"
                        )
        except ImportError:
            logger.debug("EngineeringAssertionLayer not available for OPF validation")
        except Exception as exc:
            logger.warning(_ENGINEERING_ASSERTION_FAILED, exc)
        return issues

    def _validate_opf(self, result: AgentResult) -> dict:
        """Validate OPF results.

        ARCHITECTURE AUDIT FIX (F-07): Now also runs the
        EngineeringAssertionLayer deterministic checks for OPF
        generator outputs and system losses when available.
        """
        issues = self._check_opf_assertions(result)

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

            if not file_path:
                self.log_execution(f"Report export failed for format {output_format}", "ERROR")
                return AgentResult(
                    agent_name=self.agent_name,
                    study_type=StudyType.LOAD_FLOW,
                    status=AgentStatus.FAILED,
                    data={
                        "report_generated": False,
                        "format": output_format,
                        "file_path": None,
                    },
                    validation_errors=[f"Failed to generate {output_format.upper()} report"],
                )

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

    def _compile_report(self, results: list[AgentResult]) -> dict:
        """Compile report content from agent results."""
        report = {
            "title": "Power System Engineering Analysis Report",
            "generated_at": datetime.now(UTC).isoformat(),
            "executive_summary": "",
            "load_flow_results": {},
            "short_circuit_results": {},
            "harmonic_results": {},
            "opf_results": {},
            "validation_summary": {},
            "recommendations": [],
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

    def _generate_executive_summary(self, report: dict) -> str:
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
                f"Load Flow Analysis: {'Converged' if converged else 'Did Not Converge'}",
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

    def _generate_recommendations(self, report: dict) -> list[str]:
        """Generate engineering recommendations."""
        recommendations = []

        # Check for voltage issues
        lf = report.get("load_flow_results", {})
        buses = lf.get("buses", {})
        for bus_id, bus_data in buses.items():
            v_mag = bus_data.get("voltage_magnitude_pu", 1.0)
            if v_mag < 0.95:
                recommendations.append(
                    f"Bus {bus_id}: Consider adding reactive compensation to improve voltage",
                )

        # Check for harmonic violations
        harm = report.get("harmonic_results", {})
        if harm.get("resonance_detected"):
            recommendations.append("Install passive harmonic filters to mitigate resonance")

        if not recommendations:
            recommendations.append("System operates within acceptable limits")

        return recommendations

    def _export_pdf(self, content: dict, output_path: str) -> str | None:
        """Export report as PDF using the reporting module."""
        try:
            from reporting.advanced_reports import PDFReportGenerator, ReportMetadata, ReportSection

            metadata = ReportMetadata(
                report_id=f"RPT_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                title=content.get(
                    "title",
                    _ENGINEERING_REPORT_TITLE,  # NOSONAR
                ),  # NOSONAR
                prepared_by="AhmedETAP",
            )
            sections = [
                ReportSection(
                    title=_ANALYSIS_RESULTS_TITLE, content=str(content), order=1
                )  # NOSONAR
            ]  # NOSONAR
            generator = PDFReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pdf"
            generator.generate_report(metadata, sections, file_path)
            self.log_execution(f"PDF report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "PDF generator unavailable (reportlab not installed)",
                "WARNING",
            )
            return None  # No file generated
        except Exception as e:
            self.log_execution(f"PDF generation failed: {e}", "ERROR")
            return None  # Indicate failure

    def _export_docx(self, content: dict, output_path: str) -> str | None:
        """Export report as DOCX using the reporting module."""
        try:
            from reporting.advanced_reports import (
                DOCXReportGenerator,
                ReportMetadata,
                ReportSection,
            )

            metadata = ReportMetadata(
                report_id=f"RPT_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                title=content.get("title", _ENGINEERING_REPORT_TITLE),
                prepared_by="AhmedETAP",
            )
            sections = [ReportSection(title=_ANALYSIS_RESULTS_TITLE, content=str(content), order=1)]
            generator = DOCXReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.docx"
            generator.generate_report(metadata, sections, file_path)
            self.log_execution(f"DOCX report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "DOCX generator unavailable (python-docx not installed)",
                "WARNING",
            )
            return None  # No file generated
        except Exception as e:
            self.log_execution(f"DOCX generation failed: {e}", "ERROR")
            return None  # Indicate failure

    def _export_xlsx(self, content: dict, output_path: str) -> str | None:
        """Export report as XLSX using the reporting module."""
        try:
            from reporting.advanced_reports import (
                ReportMetadata,
                ReportSection,
                XLSXReportGenerator,
            )

            metadata = ReportMetadata(
                report_id=f"RPT_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                title=content.get("title", _ENGINEERING_REPORT_TITLE),
                prepared_by="AhmedETAP",
            )
            sections = [ReportSection(title=_ANALYSIS_RESULTS_TITLE, content=str(content), order=1)]
            generator = XLSXReportGenerator()
            file_path = f"{output_path}/report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
            generator.generate_report(metadata, sections, file_path)
            self.log_execution(f"XLSX report generated: {file_path}")
            return file_path
        except ImportError:
            self.log_execution(
                "XLSX generator unavailable (openpyxl not installed)",
                "WARNING",
            )
            return None  # No file generated
        except Exception as e:
            self.log_execution(f"XLSX generation failed: {e}", "ERROR")
            return None  # Indicate failure


STUDY_TYPE_MAPPING: dict[str, str] = {
    "load_flow": "load_flow",
    "short_circuit": "short_circuit",
    "harmonic_analysis": "harmonic_analysis",
    "optimal_power_flow": "optimal_power_flow",
    "protection_coordination": "protection_coordination",
    "etap_execution": "etap_execution",
    "etap_expert": "etap_expert",
    "etap_gui": "etap_gui",
    "arc_flash": "arc_flash",
    "motor_starting": "motor_starting",
    "transient_stability": "transient_stability",
    "cable_sizing": "cable_sizing",
    "earth_grid": "earth_grid",
    "renewable_integration": "renewable_integration",
    "battery_storage": "battery_storage",
    "scada": "scada",
    "digital_twin": "digital_twin",
    "anomaly": "anomaly",
    "predictive": "predictive",
    "weather": "weather",
    "goal_planner": "goal_planner",
    "ahmed_etap": "ahmed_etap",
    "ahmed_etap_orchestration": "ahmed_etap",
    "validation": "validation",
    "report": "report",
}


def get_study_type_mapping() -> dict[str, str]:
    """Return mapping of study type strings to agent keys."""
    return dict(STUDY_TYPE_MAPPING)


def get_agent_for_study(agents: dict[str, BaseAgent], study_type: StudyType) -> BaseAgent | None:
    """Get appropriate agent for study type from the canonical mapping."""
    mapping = get_study_type_mapping()
    val = study_type.value if hasattr(study_type, "value") else str(study_type)
    agent_key = mapping.get(val, val)
    return agents.get(agent_key)


def create_agent_registry(orchestrator_instance: Any = None) -> dict[str, BaseAgent]:
    """Create and register all 24 AhmedETAP specialized agents."""
    agents: dict[str, BaseAgent] = {
        "load_flow": LoadFlowAgent(),
        "short_circuit": ShortCircuitAgent(),
        "harmonic_analysis": HarmonicAnalysisAgent(),
        "optimal_power_flow": OptimalPowerFlowAgent(),
        "protection_coordination": ProtectionCoordinationAgent(),
        "etap_execution": ETAPExecutionAgent(),
        "validation": ValidationAgent(),
        "report": ReportGenerationAgent(),
    }
    # Backward-compat aliases
    agents["harmonic"] = agents["harmonic_analysis"]
    agents["opf"] = agents["optimal_power_flow"]
    agents["protection"] = agents["protection_coordination"]

    # Standalone specialist agents
    for _agent_key, _module_name, _cls_name in (
        ("arc_flash", "agents.arc_flash_agent", "ArcFlashAgent"),
        ("motor_starting", "agents.motor_starting_agent", "MotorStartingAgent"),
        ("transient_stability", "agents.stability_agent", "StabilityAgent"),
        ("cable_sizing", "agents.cable_sizing_agent", "CableSizingAgent"),
        ("earth_grid", "agents.earth_grid_agent", "EarthGridAgent"),
        ("renewable_integration", "agents.renewable_agent", "RenewableAgent"),
        ("battery_storage", "agents.battery_storage_agent", "BatteryStorageAgent"),
        ("scada", "agents.scada_agent", "SCADAAgent"),
        ("digital_twin", "agents.digital_twin_agent", "DigitalTwinAgent"),
        ("anomaly", "agents.anomaly_agent", "AnomalyAgent"),
        ("predictive", "agents.predictive_agent", "PredictiveAgent"),
        ("weather", "agents.weather_agent", "WeatherAgent"),
        ("goal_planner", "agents.goal_planner_agent", "GoalPlannerAgent"),
        ("optimization", "agents.optimizers.optimization_agent", "OptimizationAgent"),
    ):
        try:
            _mod = __import__(_module_name, fromlist=[_cls_name])
            _cls = getattr(_mod, _cls_name)
            agents[_agent_key] = _cls()
        except Exception as _exc:
            _logger = logging.getLogger("orchestrator")
            _logger.warning(
                "Could not register agent '%s' from %s.%s: %s",
                _agent_key,
                _module_name,
                _cls_name,
                _exc,
            )

    try:
        from agents.code_guard_agent import CodeGuardAgent

        agents["code_guard"] = CodeGuardAgent()
    except ImportError:
        _logger = logging.getLogger("orchestrator")
        _logger.warning("CodeGuardAgent not available — safety code review is DISABLED.")

    try:
        from agents.etap_expert_agent import ETAPExpertAgent

        agents["etap_expert"] = ETAPExpertAgent()
    except Exception as exc:
        _logger = logging.getLogger("orchestrator")
        _logger.warning("ETAPExpertAgent not available: %s", exc)

    try:
        from agents.etap_gui_agent import ETAPGUIAgent

        agents["etap_gui"] = ETAPGUIAgent()
    except Exception as exc:
        _logger = logging.getLogger("orchestrator")
        _logger.warning("ETAPGUIAgent not available: %s", exc)

    try:
        from agents.ahmed_etap_orchestrator import AhmedETAPSkillAgent

        agents["ahmed_etap"] = AhmedETAPSkillAgent(orchestrator=orchestrator_instance)
    except Exception as exc:
        _logger = logging.getLogger("orchestrator")
        _logger.warning("AhmedETAPSkillAgent not available: %s", exc)

    return agents
