"""
tests/test_m5_assertions_rejected.py — Gate 3 Verification for Phase M5.

Verifies:
1. Deterministic EngineeringAssertionLayer.validate() enforces IEEE C84.1, IEC 60909,
   IEC 60255, IEEE 1584, IEC 60364, and IEEE C37.90 standards.
2. validate_fallback_output() is cleanly integrated and non-dead.
3. StudyExecutor._apply_post_execution_checks blocks on critical assertion failures.
4. WorkflowEngine sets AgentStatus.REJECTED on critical assertion failures.
5. Downstream DAG nodes depending on a REJECTED node are cascaded to SKIPPED_WITH_REASON
   and fail-closed, with overall_success=False exported to ExecutionTraceContract.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

UTC = timezone.utc

from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
from copilot.ai.engineering_assertions import (
    AssertionSeverity,
    EngineeringAssertionLayer,
    validate_fallback_output,
)
from services.study_executor import StudyExecutor

# ---------------------------------------------------------------------------
# 1. Deterministic EngineeringAssertionLayer Standards Checks
# ---------------------------------------------------------------------------


def test_assertion_layer_ieee_c84_1_voltage_bounds():
    """Verify IEEE C84.1 Range B hard limits reject invalid voltages."""
    layer = EngineeringAssertionLayer(strict_mode=False)

    # Valid: 1.02 pu (within Range A 0.95 - 1.05)
    valid_data = {"bus_voltages": {"Bus1": 1.02, "Bus2": 0.98}}
    rep_valid = layer.validate(valid_data, "load_flow")
    assert rep_valid.passed
    assert not rep_valid.has_critical_failures
    assert rep_valid.summary["failed"] == 0

    # Critical Violation: 1.25 pu (exceeds Range B max 1.08 pu)
    layer.clear()
    invalid_data = {"bus_voltages": {"Bus1": 1.25, "Bus2": 1.00}}
    rep_invalid = layer.validate(invalid_data, "load_flow")
    assert not rep_invalid.passed
    assert rep_invalid.has_critical_failures
    assert any(f.check_name == "voltage_range_b" for f in rep_invalid.failures)


def test_assertion_layer_iec_60909_short_circuit_bounds():
    """Verify IEC 60909 physical limit of 200 kA is enforced."""
    layer = EngineeringAssertionLayer(strict_mode=False)

    # Valid: 25 kA
    valid_data = {"fault_currents": {"Bus1": 25.0}}
    rep_valid = layer.validate(valid_data, "short_circuit")
    assert rep_valid.passed

    # Fatal: 250 kA (> 200 kA physical maximum)
    layer.clear()
    invalid_data = {"fault_currents": {"Bus1": 250.0}}
    rep_invalid = layer.validate(invalid_data, "short_circuit")
    assert not rep_invalid.passed
    assert rep_invalid.has_critical_failures
    fatal_failures = [f for f in rep_invalid.failures if f.severity == AssertionSeverity.FATAL]
    assert len(fatal_failures) >= 1
    assert fatal_failures[0].check_name == "fault_current_absolute"


def test_assertion_layer_ieee_1584_arc_flash_bounds():
    """Verify IEEE 1584 negative or extreme incident energy is rejected."""
    layer = EngineeringAssertionLayer(strict_mode=False)

    # Fatal: negative incident energy
    invalid_data = {"incident_energy": {"BusA": -5.0}}
    rep_invalid = layer.validate(invalid_data, "arc_flash")
    assert not rep_invalid.passed
    assert rep_invalid.has_critical_failures
    assert any(f.check_name == "arc_flash_energy_negative" for f in rep_invalid.failures)


def test_assertion_layer_coordination_selectivity():
    """Verify protection selectivity violation triggers critical assertion failure."""
    layer = EngineeringAssertionLayer(strict_mode=False)

    # Upstream relay trips at 0.1s while downstream trips at 0.3s (non-selective)
    invalid_data = {
        "selectivity_checks": [
            {
                "upstream_relay": "R1_Main",
                "downstream_relay": "R2_Feeder",
                "upstream_trip_s": 0.1,
                "downstream_trip_s": 0.3,
            }
        ]
    }
    rep_invalid = layer.validate(invalid_data, "protection_coordination")
    assert not rep_invalid.passed
    assert rep_invalid.has_critical_failures
    assert any(f.check_name == "coordination_selectivity_violation" for f in rep_invalid.failures)


def test_assertion_layer_cable_sizing_overload():
    """Verify IEC 60364 cable overload is flagged as FATAL fire hazard."""
    layer = EngineeringAssertionLayer(strict_mode=False)

    data = {
        "cable_loads_a": {"Cable_Feeder1": 450.0},
        "cable_ampacities_a": {"Cable_Feeder1": 300.0},
    }
    rep = layer.validate(data, "cable_sizing")
    assert not rep.passed
    assert rep.has_critical_failures
    assert any(f.check_name == "cable_overload" for f in rep.failures)


def test_validate_fallback_output_active_and_wired():
    """Verify validate_fallback_output() uses EngineeringAssertionLayer.validate()."""
    # Safe output
    is_safe, summary = validate_fallback_output(
        output_type="load_flow",
        output_data={"bus_voltages": {"B1": 1.01}},
        strict_mode=True,
    )
    assert is_safe
    assert summary["failed"] == 0

    # Dangerous output
    is_safe, summary = validate_fallback_output(
        output_type="load_flow",
        output_data={"bus_voltages": {"B1": 1.45}},
        strict_mode=False,
    )
    assert not is_safe
    assert summary["has_critical_failures"]


# ---------------------------------------------------------------------------
# 2. StudyExecutor Mandatory Enforcement
# ---------------------------------------------------------------------------


def test_study_executor_blocks_on_critical_assertion_failure():
    """StudyExecutor._apply_post_execution_checks must set status='failed' on critical assertion."""
    executor = StudyExecutor(cache=None)
    data = {
        "bus_voltages": {"Bus1": 1.35},  # critical violation (> 1.08 pu)
        "nominal_voltage_kv": 1.0,
    }
    errors: list[str] = []
    status = executor._apply_post_execution_checks(data, "load_flow", errors)

    assert status == "failed"
    assert len(errors) > 0
    assert "Engineering assertions blocked result" in errors[0]
    assert "engineering_assertion_failures" in data


# ---------------------------------------------------------------------------
# 3. WorkflowEngine: REJECTED Enforcement and Fail-Closed Cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_engine_sets_rejected_status_on_assertion_failure():
    """Verify that assertion failure in a workflow sets AgentStatus.REJECTED."""
    from agents.base import BaseAgent
    from agents.workflow import WorkflowEngine

    class MockBadLoadFlowAgent(BaseAgent):
        def __init__(self):
            super().__init__("mock_lf")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            return AgentResult(
                agent_name="mock_lf",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={"bus_voltages": {"Bus1": 1.40}},  # severe overvoltage
                validation_status=True,
            )

    engine = WorkflowEngine(agents={"load_flow": MockBadLoadFlowAgent()})

    task = EngineeringTask(
        task_id="test_wf_rejected_task",
        description="Run bad load flow",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )

    results = await engine.execute_workflow(task)
    lf_results = [r for r in results if r.agent_name == "mock_lf"]
    assert len(lf_results) == 1
    res = lf_results[0]

    # Must be marked REJECTED and validation_status=False
    assert res.status == AgentStatus.REJECTED
    assert not res.validation_status
    assert any("Engineering assertion FAILED" in err for err in res.validation_errors)


@pytest.mark.asyncio
async def test_workflow_engine_fail_closed_cascade_downstream_skipped():
    """Verify that a REJECTED node causes dependent downstream nodes to be SKIPPED_WITH_REASON."""
    from agents.base import BaseAgent
    from agents.workflow import WorkflowEngine

    executed_nodes: list[str] = []

    class MockFailingNode1Agent(BaseAgent):
        def __init__(self):
            super().__init__("agent_node_1")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            executed_nodes.append("node_1")
            return AgentResult(
                agent_name="agent_node_1",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={"bus_voltages": {"Bus1": 1.50}},  # Critical assertion violation
                validation_status=True,
            )

    class MockDownstreamNode2Agent(BaseAgent):
        def __init__(self):
            super().__init__("agent_node_2")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            executed_nodes.append("node_2")
            return AgentResult(
                agent_name="agent_node_2",
                study_type=StudyType.SHORT_CIRCUIT,
                status=AgentStatus.COMPLETED,
                data={"fault_currents": {"Bus1": 10.0}},
                validation_status=True,
            )

    engine = WorkflowEngine(
        agents={
            "load_flow": MockFailingNode1Agent(),
            "short_circuit": MockDownstreamNode2Agent(),
        }
    )

    # Define custom DAG where node_2 explicitly depends on node_1
    task = EngineeringTask(
        task_id="test_cascade_dag",
        description="Test DAG fail-closed propagation",
        study_types=[StudyType.LOAD_FLOW, StudyType.SHORT_CIRCUIT],
        parameters={
            "custom_nodes": [
                {
                    "node_id": "node_1",
                    "study_type": "load_flow",
                    "agent_id": "agent_node_1",
                    "depends_on": [],
                },
                {
                    "node_id": "node_2",
                    "study_type": "short_circuit",
                    "agent_id": "agent_node_2",
                    "depends_on": ["node_1"],
                },
            ]
        },
    )

    results = await engine.execute_workflow(task)

    # Node 1 executed and was REJECTED
    assert "node_1" in executed_nodes
    # Node 2 must NEVER have executed
    assert "node_2" not in executed_nodes

    node_1_res = next(r for r in results if getattr(r, "node_id", None) == "node_1")
    node_2_res = next(r for r in results if getattr(r, "node_id", None) == "node_2")

    assert node_1_res.status == AgentStatus.REJECTED
    assert not node_1_res.validation_status

    assert node_2_res.status == AgentStatus.SKIPPED_WITH_REASON
    assert not node_2_res.validation_status
    assert "node_1" in node_2_res.data.get("failed_dependencies", [])


@pytest.mark.asyncio
async def test_trace_export_overall_success_false_on_rejected_node():
    """ExecutionTraceContract must export overall_success=False and success=False when REJECTED."""
    from agents.base import BaseAgent
    from agents.workflow import WorkflowEngine

    class MockBadAgent(BaseAgent):
        def __init__(self):
            super().__init__("bad_agent")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            return AgentResult(
                agent_name="bad_agent",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={"bus_voltages": {"Bus1": 1.45}},
                validation_status=True,
            )

    engine = WorkflowEngine(agents={"load_flow": MockBadAgent()})

    task = EngineeringTask(
        task_id="trace_test_task",
        description="Trace export rejected test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "custom_nodes": [
                {
                    "node_id": "node_bad",
                    "study_type": "load_flow",
                    "agent_id": "bad_agent",
                    "depends_on": [],
                }
            ]
        },
    )

    results = await engine.execute_workflow(task)
    trace = engine.export_execution_trace(task, results)

    assert trace is not None
    assert not trace.overall_success

    bad_node_contract = next(nr for nr in trace.node_results if nr.node_id == "node_bad")
    assert not bad_node_contract.success


def test_engineering_assertion_warning_only_does_not_block_study_executor():
    """Item 4: Non-critical assertion violations (warnings) must not block StudyExecutor status."""
    from services.study_executor import StudyExecutor

    executor = StudyExecutor()
    # Voltage 1.06 pu is outside IEEE C84.1 Range A (0.95-1.05 pu),
    # but inside Range B (0.916-1.083 pu) -> severity is WARNING, not CRITICAL/FATAL
    warning_data = {
        "bus_voltages": {"Bus1": 1.06},
    }

    errors: list[str] = []
    status = executor._apply_post_execution_checks(warning_data, "load_flow", errors)
    assert status == "success"
    assert len(errors) == 0
    assert "engineering_assertion_warnings" in warning_data
    assert len(warning_data["engineering_assertion_warnings"]) > 0
    assert "blocked_severity" not in warning_data


@pytest.mark.asyncio
async def test_workflow_engine_warning_only_retains_completed_status():
    """Item 4: In WorkflowEngine, non-critical warnings keep status=COMPLETED and validation_status=True."""
    from agents.base import BaseAgent
    from agents.workflow import WorkflowEngine

    class MockWarningAgent(BaseAgent):
        def __init__(self):
            super().__init__("warning_agent")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            return AgentResult(
                agent_name="warning_agent",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={"bus_voltages": {"Bus1": 1.06}},  # Range A warning, not Range B critical
                validation_status=True,
            )

    engine = WorkflowEngine(agents={"load_flow": MockWarningAgent()})

    task = EngineeringTask(
        task_id="warning_test_task",
        description="Warning only load flow",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )

    results = await engine.execute_workflow(task)
    lf_res = next(r for r in results if r.agent_name == "warning_agent")

    assert lf_res.status == AgentStatus.COMPLETED
    assert lf_res.validation_status is True
    assert "engineering_assertion_warnings" in lf_res.data
    assert len(lf_res.data["engineering_assertion_warnings"]) > 0
    assert "blocked_severity" not in lf_res.data
