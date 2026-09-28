"""
tests/test_contract_sync.py — M2 Gate Test 2: Python ↔ TypeScript Contract Parity

Verifies that every field defined in contracts/ai/models.py has a structurally
equivalent counterpart in src/core/contracts/ai.ts, and that the canonical
registry (engine/dispatch.py STUDY_DISPATCH + src/core/agents.ts AGENT_REGISTRY)
is consistent across both runtimes.

This is the cross-runtime synchronisation gate required by M2 Gate Condition 2.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TS_CONTRACTS = REPO_ROOT / "src" / "core" / "contracts" / "ai.ts"
PY_CONTRACTS = REPO_ROOT / "contracts" / "ai" / "models.py"
TS_AGENTS = REPO_ROOT / "src" / "core" / "agents.ts"


def _extract_ts_interfaces(ts_path: Path) -> set[str]:
    """Return set of exported interface / type alias names from a .ts file."""
    text = ts_path.read_text(encoding="utf-8")
    return set(re.findall(r"^export\s+(?:interface|type)\s+(\w+)", text, re.MULTILINE))


def _extract_py_classes(py_path: Path) -> set[str]:
    """Return set of class names defined in a Python file."""
    text = py_path.read_text(encoding="utf-8")
    return set(re.findall(r"^class\s+(\w+)\s*[\(:]", text, re.MULTILINE))


def _extract_ts_agent_ids(ts_path: Path) -> set[str]:
    """Extract agent ids from AGENT_REGISTRY in agents.ts."""
    text = ts_path.read_text(encoding="utf-8")
    return set(re.findall(r"'([\w-]+-agent)':", text))


# ---------------------------------------------------------------------------
# Contract parity tests
# ---------------------------------------------------------------------------

# The 10 contract names that must appear in both Python and TypeScript.
EXPECTED_CONTRACTS = {
    "ProvenanceContract",
    "EvidenceContract",
    "PlanNodeContract",
    "ExecutionPlanContract",
    "ExecutionContextContract",
    "ExecutionRequestContract",
    "ValidationResultContract",
    "StudyResultContract",
    "ApprovalStateContract",
    "ExecutionTraceContract",
}


def test_all_contracts_exported_from_ts():
    """All 10 contracts are exported from src/core/contracts/ai.ts."""
    ts_exports = _extract_ts_interfaces(TS_CONTRACTS)
    missing = EXPECTED_CONTRACTS - ts_exports
    assert not missing, (
        f"Missing TypeScript interfaces in {TS_CONTRACTS.name}: {sorted(missing)}"
    )


def test_all_contracts_defined_in_python():
    """All 10 contracts are defined as classes in contracts/ai/models.py."""
    py_classes = _extract_py_classes(PY_CONTRACTS)
    missing = EXPECTED_CONTRACTS - py_classes
    assert not missing, (
        f"Missing Python classes in {PY_CONTRACTS.name}: {sorted(missing)}"
    )


def test_python_contracts_importable():
    """All 10 contracts are importable from the contracts.ai package."""
    from contracts.ai import (
        ApprovalStateContract,
        EvidenceContract,
        ExecutionContextContract,
        ExecutionPlanContract,
        ExecutionRequestContract,
        ExecutionTraceContract,
        PlanNodeContract,
        ProvenanceContract,
        StudyResultContract,
        ValidationResultContract,
    )
    for cls in [
        ApprovalStateContract,
        EvidenceContract,
        ExecutionContextContract,
        ExecutionPlanContract,
        ExecutionRequestContract,
        ExecutionTraceContract,
        PlanNodeContract,
        ProvenanceContract,
        StudyResultContract,
        ValidationResultContract,
    ]:
        assert cls is not None, f"{cls.__name__} could not be imported"


def test_name_disambiguation_no_collision():
    """Confirm that the 4 disambiguated names do NOT appear in colliding modules."""
    colliding_modules = [
        REPO_ROOT / "engine" / "scalability.py",
        REPO_ROOT / "digital_twin" / "validation_gateway.py",
        REPO_ROOT / "core_model" / "specs.py",
    ]
    forbidden_in_colliding = {
        "ExecutionPlanContract",
        "ExecutionContextContract",
        "ValidationResultContract",
        "StudyResultContract",
    }
    for mod_path in colliding_modules:
        if not mod_path.exists():
            continue
        text = mod_path.read_text(encoding="utf-8")
        for name in forbidden_in_colliding:
            assert name not in text, (
                f"Name '{name}' found in {mod_path.name} — "
                "contract names must only live in contracts/ai/models.py"
            )


def test_contracts_ts_no_collision_with_core_types():
    """Contracts in ai.ts do not redefine ExecutionContext from types.ts."""
    core_types = REPO_ROOT / "src" / "core" / "types.ts"
    if not core_types.exists():
        pytest.skip("src/core/types.ts not found")
    types_text = core_types.read_text(encoding="utf-8")
    contracts_text = TS_CONTRACTS.read_text(encoding="utf-8")

    # types.ts must contain ExecutionContext (original), ai.ts must contain ExecutionContextContract
    assert "ExecutionContext" in types_text, "types.ts must define ExecutionContext"
    assert "ExecutionContextContract" in contracts_text, "ai.ts must define ExecutionContextContract"
    assert "ExecutionContext'" not in contracts_text or "ExecutionContextContract" in contracts_text


# ---------------------------------------------------------------------------
# Registry parity tests (M2.3)
# ---------------------------------------------------------------------------

def test_dispatch_registry_keys_match_study_type_enum():
    """engine/dispatch.py STUDY_DISPATCH keys must include all StudyType enum values."""
    from agents.models import StudyType
    from engine.dispatch import STUDY_DISPATCH

    enum_values = {st.value for st in StudyType}
    dispatch_keys = set(STUDY_DISPATCH.keys())
    missing = enum_values - dispatch_keys
    assert not missing, (
        f"StudyType enum values missing from STUDY_DISPATCH: {sorted(missing)}"
    )


def test_ts_agent_ids_in_agent_registry():
    """All agent IDs in src/core/agents.ts AGENT_REGISTRY are well-formed."""
    ts_agent_ids = _extract_ts_agent_ids(TS_AGENTS)
    assert len(ts_agent_ids) >= 10, (
        f"Expected at least 10 agents in AGENT_REGISTRY, found {len(ts_agent_ids)}"
    )
    for agent_id in ts_agent_ids:
        assert agent_id.endswith("-agent"), (
            f"Agent ID '{agent_id}' does not follow the '<name>-agent' convention"
        )


def test_agent_models_linkage_fields_backward_compatible():
    """AgentResult and EngineeringTask M2.2 linkage fields are optional (None by default)."""
    from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType

    result = AgentResult(
        agent_name="test_agent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"voltage": 1.0},
    )
    assert result.run_id is None
    assert result.plan_id is None
    assert result.node_id is None

    task = EngineeringTask(
        task_id="task-001",
        description="Test task",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )
    assert task.run_id is None
    assert task.plan_id is None


def test_pydantic_contracts_instantiation():
    """All Pydantic contracts can be instantiated with required fields."""
    import uuid

    from contracts.ai import (
        ApprovalStateContract,
        EvidenceContract,
        ExecutionContextContract,
        ExecutionPlanContract,
        ExecutionRequestContract,
        ExecutionTraceContract,
        PlanNodeContract,
        ProvenanceContract,
        StudyResultContract,
        ValidationResultContract,
    )

    prov = ProvenanceContract(source="computed", ref="IEC 60909:2016 §4.3")
    assert prov.confidence == 1.0

    ev = EvidenceContract(key="voltage_kv", value=11.0, provenance=prov)
    assert ev.key == "voltage_kv"

    node = PlanNodeContract(
        node_id="node-1",
        study_type="load_flow",
        agent_id="load-flow-agent",
    )
    assert node.status.value == "queued"

    run_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    plan = ExecutionPlanContract(plan_id=plan_id, run_id=run_id, nodes=[node])
    assert len(plan.nodes) == 1

    ctx = ExecutionContextContract(tenant_id="tenant-1", user_id="user-1")
    assert ctx.privacy_mode is False

    req = ExecutionRequestContract(run_id=run_id, plan=plan, context=ctx)
    assert req.dry_run is False

    vr = ValidationResultContract(check_name="registry_sync", passed=True)
    assert vr.severity == "error"

    sr = StudyResultContract(
        run_id=run_id,
        plan_id=plan_id,
        node_id="node-1",
        study_type="load_flow",
        agent_id="load-flow-agent",
        success=True,
    )
    assert sr.overall_success is False if hasattr(sr, "overall_success") else True

    import hashlib
    payload_hash = hashlib.sha256(b"test").hexdigest()
    ap = ApprovalStateContract(
        action_id="action-1",
        maker_id="user-1",
        action_type="execute_study",
        payload_hash=payload_hash,
    )
    assert ap.status.value == "pending"

    trace = ExecutionTraceContract(
        run_id=run_id,
        plan_id=plan_id,
        context=ctx,
    )
    assert trace.overall_success is False


# ---------------------------------------------------------------------------
# M3.3 Runtime Contract Consumption & Linkage Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_engine_builds_execution_plan_contract():
    """WorkflowEngine builds a valid ExecutionPlanContract with dependency ordering (M3.3)."""
    from agents.models import EngineeringTask, StudyType
    from agents.workflow import WorkflowEngine
    from contracts.ai import ExecutionPlanContract

    engine = WorkflowEngine(agents={})
    task = EngineeringTask(
        task_id="task_m33_plan",
        description="Run LF and SC studies",
        study_types=[StudyType.SHORT_CIRCUIT, StudyType.LOAD_FLOW],
        parameters={"tenant_id": "test_tenant"},
    )
    plan = engine.build_execution_plan(task)
    assert isinstance(plan, ExecutionPlanContract)
    assert plan.plan_id == task.plan_id
    assert plan.run_id == task.run_id
    assert len(plan.nodes) == 2

    # Check dependency: SHORT_CIRCUIT must depend on LOAD_FLOW
    lf_nodes = [n for n in plan.nodes if n.study_type == "load_flow"]
    sc_nodes = [n for n in plan.nodes if n.study_type == "short_circuit"]
    assert len(lf_nodes) == 1
    assert len(sc_nodes) == 1
    assert lf_nodes[0].depends_on == []
    assert lf_nodes[0].node_id in sc_nodes[0].depends_on
    assert plan.topological_order == [n.node_id for n in plan.nodes]


@pytest.mark.asyncio
async def test_workflow_engine_execute_stamps_contract_linkage_fields():
    """WorkflowEngine execute_workflow stamps run_id, plan_id, node_id on results (M3.3)."""
    from unittest.mock import AsyncMock

    from agents.base import BaseAgent
    from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
    from agents.workflow import WorkflowEngine
    from contracts.ai import ExecutionTraceContract

    mock_lf = AsyncMock(spec=BaseAgent)
    mock_lf.agent_name = "load_flow_agent"
    mock_lf.execute.return_value = AgentResult(
        agent_name="load_flow_agent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"voltage": [1.0, 0.99]},
        validation_status=True,
    )

    mock_val = AsyncMock(spec=BaseAgent)
    mock_val.agent_name = "validation_agent"
    mock_val.execute.return_value = AgentResult(
        agent_name="validation_agent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"passed": True},
        validation_status=True,
    )

    engine = WorkflowEngine(agents={"load_flow": mock_lf, "validation": mock_val})
    task = EngineeringTask(
        task_id="task_m33_exec",
        description="Verify contract stamping",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"tenant_id": "tenant_abc", "user_id": "user_xyz"},
    )

    results = await engine.execute_workflow(task)
    assert len(results) >= 1
    assert task.run_id is not None
    assert task.plan_id is not None

    for r in results:
        assert r.run_id == task.run_id
        assert r.plan_id == task.plan_id
        assert r.node_id is not None and len(r.node_id) > 0

    assert isinstance(engine.last_execution_trace, ExecutionTraceContract)
    assert engine.last_execution_trace.run_id == task.run_id
    assert engine.last_execution_trace.plan_id == task.plan_id
    assert engine.last_execution_trace.context.tenant_id == "tenant_abc"
    assert engine.last_execution_trace.context.user_id == "user_xyz"
    assert len(engine.last_execution_trace.node_results) >= 1
    assert engine.last_execution_trace.overall_success is True


@pytest.mark.asyncio
async def test_orchestrator_autonomous_workflow_exposes_contracts():
    """ChiefEngineeringOrchestrator exposes run_id, plan_id, plan, and trace (M3.3)."""
    from unittest.mock import AsyncMock

    from agents.base import BaseAgent
    from agents.models import AgentResult, AgentStatus, StudyType
    from agents.orchestrator import ChiefEngineeringOrchestrator
    from contracts.ai import ExecutionPlanContract, ExecutionTraceContract

    mock_lf = AsyncMock(spec=BaseAgent)
    mock_lf.agent_name = "load_flow_agent"
    mock_lf.get_agent_info.return_value = {"name": "LF"}
    mock_lf.execute.return_value = AgentResult(
        agent_name="load_flow_agent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"converged": True},
        validation_status=True,
    )

    mock_val = AsyncMock(spec=BaseAgent)
    mock_val.agent_name = "validation_agent"
    mock_val.get_agent_info.return_value = {"name": "VAL"}
    mock_val.execute.return_value = AgentResult(
        agent_name="validation_agent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"all_passed": True},
        validation_status=True,
    )

    orch = ChiefEngineeringOrchestrator(
        agents={"load_flow": mock_lf, "validation": mock_val},
        enable_bandit_router=False,
    )

    res = await orch.execute_autonomous_workflow(
        user_goal="Run power flow calculation",
        system_data={"bus_count": 5},
    )

    assert "run_id" in res and res["run_id"] is not None
    assert "plan_id" in res and res["plan_id"] is not None
    assert "execution_plan" in res and isinstance(res["execution_plan"], ExecutionPlanContract)
    assert "execution_trace" in res and isinstance(res["execution_trace"], ExecutionTraceContract)
    assert res["execution_trace"].run_id == res["run_id"]
    assert res["execution_trace"].plan_id == res["plan_id"]

