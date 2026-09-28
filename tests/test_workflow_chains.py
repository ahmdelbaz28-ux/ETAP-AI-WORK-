"""
tests/test_workflow_chains.py — Integration tests for the 3 canonical multi-agent chains (M3.3).

Verifies inter-node data flow and cascading execution:
1. short_circuit -> protection_coordination -> arc_flash
2. load_flow -> optimal_power_flow -> load_flow (verification)
3. harmonic_analysis -> optimization -> harmonic_analysis (verification)
4. Predecessor failure/rejection yields AgentStatus.SKIPPED_WITH_REASON for dependent nodes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.base import BaseAgent
from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
from agents.workflow import WorkflowEngine


class MockChainAgent(BaseAgent):
    """Configurable mock agent tracking received inputs and returning scripted outputs."""

    def __init__(self, name: str, output_data: dict[str, Any], fail: bool = False, reject: bool = False) -> None:
        super().__init__(name)
        self.agent_name = name
        self.output_data = output_data
        self.fail = fail
        self.reject = reject
        self.received_tasks: list[EngineeringTask] = []

    async def execute(self, task: EngineeringTask) -> AgentResult:
        self.received_tasks.append(task)
        if self.fail:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={"error": "Simulated hardware engine failure"},
                validation_status=False,
                validation_errors=["Simulated failure"],
            )
        if self.reject:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.REJECTED,
                data={"violations": ["Constraint violation"]},
                validation_status=False,
                validation_errors=["Constraint violation"],
            )
        return AgentResult(
            agent_name=self.agent_name,
            study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data=dict(self.output_data),
            validation_status=True,
        )


@pytest.mark.asyncio
async def test_chain_1_short_circuit_protection_arc_flash():
    """Witness M3.3: short_circuit -> protection_coordination -> arc_flash data flow."""
    sc_agent = MockChainAgent("ShortCircuitAgent", {"fault_current_ka": 28.5, "ik_ss_ka": 26.2})
    prot_agent = MockChainAgent("ProtectionCoordinationAgent", {"clearing_time_s": 0.15, "curve": "IEC_NI"})
    af_agent = MockChainAgent("ArcFlashAgent", {"incident_energy_cal_cm2": 3.8, "ppe_category": "Category 2"})
    val_agent = MockChainAgent("ValidationAgent", {"passed": True})

    agents = {
        "short_circuit": sc_agent,
        "protection_coordination": prot_agent,
        "arc_flash": af_agent,
        "validation": val_agent,
    }

    engine = WorkflowEngine(agents=agents)
    task = EngineeringTask(
        task_id="task_chain_1",
        description="Chain 1: SC -> Protection -> ArcFlash",
        study_types=[StudyType.SHORT_CIRCUIT, StudyType.PROTECTION_COORDINATION, StudyType.ARC_FLASH],
        parameters={"base_voltage_kv": 11.0},
    )

    results = await engine.execute_workflow(task)

    # 1. Protection received fault current from Short Circuit
    assert len(prot_agent.received_tasks) == 1
    prot_params = prot_agent.received_tasks[0].parameters
    assert prot_params.get("fault_current_ka") == 28.5

    # 2. Arc Flash received both fault current and clearing time
    assert len(af_agent.received_tasks) == 1
    af_params = af_agent.received_tasks[0].parameters
    assert af_params.get("fault_current_ka") == 28.5
    assert af_params.get("clearing_time_s") == 0.15

    # 3. All studies completed successfully
    completed = [r for r in results if r.status == AgentStatus.COMPLETED]
    assert len(completed) >= 3


@pytest.mark.asyncio
async def test_chain_2_load_flow_opf_load_flow():
    """Witness M3.3: load_flow -> optimal_power_flow -> load_flow (verification) data flow."""
    lf_initial = {"bus_voltages": {1: 1.0, 2: 0.96}, "total_losses_mw": 2.4}
    opf_output = {"optimal_dispatch": {1: 42.0, 2: 28.0}, "control_setpoints": {"tap": 1.02}}
    lf_verified = {"bus_voltages": {1: 1.0, 2: 0.99}, "total_losses_mw": 1.8}

    # Tracking calls to load flow agent (called twice)
    lf_calls = []

    class LFMultiAgent(BaseAgent):
        def __init__(self):
            super().__init__("LoadFlowAgent")
            self.agent_name = "LoadFlowAgent"

        async def execute(self, task: EngineeringTask) -> AgentResult:
            lf_calls.append(task)
            out = lf_verified if len(lf_calls) > 1 else lf_initial
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data=out,
                validation_status=True,
            )

    lf_agent = LFMultiAgent()
    opf_agent = MockChainAgent("OptimalPowerFlowAgent", opf_output)
    val_agent = MockChainAgent("ValidationAgent", {"passed": True})

    agents = {
        "load_flow": lf_agent,
        "optimal_power_flow": opf_agent,
        "validation": val_agent,
    }

    engine = WorkflowEngine(agents=agents)
    task = EngineeringTask(
        task_id="task_chain_2",
        description="Chain 2: LF -> OPF -> Verify LF",
        study_types=[StudyType.LOAD_FLOW, StudyType.OPTIMAL_POWER_FLOW, StudyType.LOAD_FLOW],
        parameters={"system_id": "sys_42"},
    )

    results = await engine.execute_workflow(task)

    # 1. OPF received initial bus voltages from initial load flow
    assert len(opf_agent.received_tasks) == 1
    opf_params = opf_agent.received_tasks[0].parameters
    assert opf_params.get("bus_voltages") == {1: 1.0, 2: 0.96}

    # 2. Verification load flow received optimal dispatch & setpoints from OPF
    assert len(lf_calls) == 2
    verify_lf_params = lf_calls[1].parameters
    assert verify_lf_params.get("generator_dispatch") == {1: 42.0, 2: 28.0}
    assert verify_lf_params.get("control_settings") == {"tap": 1.02}


@pytest.mark.asyncio
async def test_chain_3_harmonics_filter_optimization_harmonics():
    """Witness M3.3: harmonic_analysis -> optimization -> harmonic_analysis (verification) data flow."""
    harm_initial = {"thd_voltage": 9.2, "harmonic_spectrum": {5: 6.5, 7: 4.8}}
    opt_output = {"filter_parameters": {"type": "single_tuned", "c_mvar": 6.0}, "projected_thd_v": 3.4}
    harm_verified = {"thd_voltage": 3.3, "harmonic_spectrum": {5: 1.8, 7: 1.2}}

    harm_calls = []

    class HarmMultiAgent(BaseAgent):
        def __init__(self):
            super().__init__("HarmonicAnalysisAgent")
            self.agent_name = "HarmonicAnalysisAgent"

        async def execute(self, task: EngineeringTask) -> AgentResult:
            harm_calls.append(task)
            out = harm_verified if len(harm_calls) > 1 else harm_initial
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.HARMONIC_ANALYSIS,
                status=AgentStatus.COMPLETED,
                data=out,
                validation_status=True,
            )

    harm_agent = HarmMultiAgent()
    opt_agent = MockChainAgent("OptimizationAgent", opt_output)
    val_agent = MockChainAgent("ValidationAgent", {"passed": True})

    agents = {
        "harmonic_analysis": harm_agent,
        "optimization": opt_agent,
        "validation": val_agent,
    }

    engine = WorkflowEngine(agents=agents)
    task = EngineeringTask(
        task_id="task_chain_3",
        description="Chain 3: Harmonics -> Filter Opt -> Verify Harmonics",
        study_types=[StudyType.HARMONIC_ANALYSIS, "optimization", StudyType.HARMONIC_ANALYSIS],
        parameters={"network": "grid_h"},
    )

    results = await engine.execute_workflow(task)

    # 1. Optimization received baseline THD from Harmonic Analysis
    assert len(opt_agent.received_tasks) == 1
    opt_params = opt_agent.received_tasks[0].parameters
    assert opt_params.get("baseline_thd_v") == 9.2

    # 2. Verification Harmonic Analysis received filter specs from Optimization
    assert len(harm_calls) == 2
    verify_harm_params = harm_calls[1].parameters
    assert verify_harm_params.get("installed_filters") == {"type": "single_tuned", "c_mvar": 6.0}


@pytest.mark.asyncio
async def test_predecessor_failure_cascades_skipped_with_reason():
    """Witness M3.2 / M3.3: When a predecessor fails, downstream dependent nodes get SKIPPED_WITH_REASON."""
    sc_failing_agent = MockChainAgent("ShortCircuitAgent", {}, fail=True)
    prot_agent = MockChainAgent("ProtectionCoordinationAgent", {"clearing_time_s": 0.15})
    val_agent = MockChainAgent("ValidationAgent", {"passed": True})

    agents = {
        "short_circuit": sc_failing_agent,
        "protection_coordination": prot_agent,
        "validation": val_agent,
    }

    engine = WorkflowEngine(agents=agents)
    task = EngineeringTask(
        task_id="task_fail_cascade",
        description="Test cascade skip on failure",
        study_types=[StudyType.SHORT_CIRCUIT, StudyType.PROTECTION_COORDINATION],
        parameters={},
    )

    results = await engine.execute_workflow(task)

    # Protection coordination should NOT have executed
    assert len(prot_agent.received_tasks) == 0

    # Protection coordination result must be SKIPPED_WITH_REASON
    prot_results = [r for r in results if getattr(r.study_type, "value", str(r.study_type)) in ("protection_coordination", "protection")]
    assert len(prot_results) == 1
    assert prot_results[0].status == AgentStatus.SKIPPED_WITH_REASON
    assert prot_results[0].validation_status is False
    assert "Predecessor node(s)" in prot_results[0].data["skip_reason"]
