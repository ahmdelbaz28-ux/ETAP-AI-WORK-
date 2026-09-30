"""M4.4 — ML provenance, synthetic-data policy, three-truths gate, honest ack.

Gate evidence this file must produce (per ``docs/ai-integration/m4-plan.md``):

1. ``allow_synthetic=false`` in production — proven by an execution test.
2. Mandatory provenance on every predictive result:
   ``model_version`` / ``input_window`` / ``drift_state``.
3. The three-truths validation gateway is *wired* into
   ``DigitalTwinAgent.execute`` and can veto ``validation_status``.
4. ``all_validated`` is no longer a self-acknowledgement — it requires an
   independent ValidationAgent pass and fails closed.
5. ``predictive`` / ``anomaly`` are context-bound: not executable study types.
"""

from __future__ import annotations

import pytest

from agents.digital_twin_agent import DigitalTwinAgent
from agents.models import EngineeringTask, StudyType
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    ChiefEngineeringOrchestrator,
)
from agents.predictive_agent import (
    MODEL_VERSION,
    REQUIRED_PROVENANCE_KEYS,
    PredictiveAgent,
    resolve_allow_synthetic,
    synthetic_data_allowed,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. allow_synthetic MUST be false in production (the M4 gate test)
# ─────────────────────────────────────────────────────────────────────────────

def test_synthetic_allowed_in_dev_but_blocked_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("ENV", raising=False)
    assert synthetic_data_allowed() is True

    for env in ("production", "prod", "staging"):
        monkeypatch.setenv("ENVIRONMENT", env)
        assert synthetic_data_allowed() is False, f"synthetic allowed in {env}"


def test_resolve_allow_synthetic_honours_prod_gate(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENV", raising=False)

    requested = EngineeringTask(
        task_id="prod-1",
        description="synthetic request in prod",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"allow_synthetic": True},
    )
    assert resolve_allow_synthetic(requested) is False

    not_requested = EngineeringTask(
        task_id="prod-2",
        description="no synthetic",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )
    assert resolve_allow_synthetic(not_requested) is False


@pytest.mark.asyncio
async def test_predictive_agent_never_generates_synthetic_data_in_production(monkeypatch):
    """THE M4.4 gate test: prod + allow_synthetic=True ⇒ no synthetic output."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENV", raising=False)

    agent = PredictiveAgent()
    task = EngineeringTask(
        task_id="prod-synthetic",
        description="Forecast load with synthetic allowed",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "short_term_forecast", "allow_synthetic": True},
    )

    result = await agent.execute(task)

    forecast = result.data.get("short_term_forecast", {})
    assert forecast.get("status") != "synthetic_demo", (
        "synthetic demo data was produced in a production environment"
    )
    assert forecast.get("status") == "untrained"

    provenance = result.data.get("provenance", {})
    assert provenance.get("synthetic_data_used") is False
    assert provenance.get("allow_synthetic_requested") is True
    assert provenance.get("allow_synthetic_resolved") is False
    assert provenance.get("environment") == "production"


@pytest.mark.asyncio
async def test_predictive_agent_synthetic_still_works_outside_production(monkeypatch):
    """Control: the gate must not disable the documented demo path in dev."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("ENV", raising=False)

    agent = PredictiveAgent()
    task = EngineeringTask(
        task_id="dev-synthetic",
        description="Forecast load demo",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "short_term_forecast", "allow_synthetic": True},
    )

    result = await agent.execute(task)
    forecast = result.data.get("short_term_forecast", {})
    assert forecast.get("status") == "synthetic_demo"
    assert result.data["provenance"]["synthetic_data_used"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mandatory provenance: model_version / input_window / drift_state
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predictive_result_carries_mandatory_provenance(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("ENV", raising=False)

    agent = PredictiveAgent()
    task = EngineeringTask(
        task_id="prov-1",
        description="Forecast with real data",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "short_term_forecast",
            "historical_load_mw": [100.0 + 5.0 * (i % 24) for i in range(168)],
        },
    )

    result = await agent.execute(task)
    provenance = result.data.get("provenance")

    assert isinstance(provenance, dict), "provenance block missing"
    for key in REQUIRED_PROVENANCE_KEYS:
        assert key in provenance, f"mandatory provenance key missing: {key}"
    assert provenance["model_version"] == MODEL_VERSION
    assert provenance["input_window"] == 168
    assert provenance["drift_state"] in {"stable", "drifting", "degraded", "unknown"}
    assert result.validation_status is True


def test_validate_result_rejects_missing_provenance():
    agent = PredictiveAgent()

    bare = AgentResult(
        agent_name="PredictiveAgent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"analysis_type": "short_term_forecast"},
    )
    assert agent.validate_result(bare) is False
    assert any("provenance" in e.lower() for e in bare.validation_errors)

    partial = AgentResult(
        agent_name="PredictiveAgent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={"provenance": {"model_version": MODEL_VERSION}},
    )
    assert agent.validate_result(partial) is False
    assert any("input_window" in e for e in partial.validation_errors)


def test_drift_state_never_fabricated():
    """No MAPE ⇒ honest 'unknown', never a fabricated 'stable'."""
    from agents.predictive_agent import derive_drift_state

    assert derive_drift_state({}) == "unknown"
    assert derive_drift_state({"short_term_forecast": {"mape_percent": 3.1}}) == "stable"
    assert derive_drift_state({"short_term_forecast": {"mape_percent": 9.5}}) == "drifting"
    assert derive_drift_state({"short_term_forecast": {"mape_percent": 42.0}}) == "degraded"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Three-truths validation gateway is wired into DigitalTwinAgent
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_three_truths_gate_is_wired_and_honest_when_not_applicable():
    agent = DigitalTwinAgent()
    task = EngineeringTask(
        task_id="dt-1",
        description="Data quality only",
        study_types=[StudyType.DIGITAL_TWIN],
        parameters={"analysis_type": "data_quality", "measurements": []},
    )

    result = await agent.execute(task)

    gate = result.data.get("three_truths")
    assert isinstance(gate, dict), "three-truths gate not wired into execute()"
    assert gate["applicable"] is False
    assert gate["performed"] is False
    assert "no layer objects" in gate["reason"]
    assert result.validation_status is True  # inapplicable ⇒ not a failure


class _EmptySystem:
    """Minimal electrical-system stub: zero buses ⇒ gateway blocking failures."""

    buses: dict = {}

    def get_ybus(self, base):  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_three_truths_gate_vetoes_result_on_blocking_failure():
    agent = DigitalTwinAgent()
    task = EngineeringTask(
        task_id="dt-2",
        description="Data quality with an invalid electrical model",
        study_types=[StudyType.DIGITAL_TWIN],
        parameters={
            "analysis_type": "data_quality",
            "measurements": [],
            "system": _EmptySystem(),
        },
    )

    result = await agent.execute(task)

    gate = result.data["three_truths"]
    assert gate["applicable"] is True
    assert gate["performed"] is True
    assert gate["passed"] is False
    assert gate["blocking_failures"] >= 1
    assert gate["layers_provided"] == ["system"]
    assert result.validation_status is False
    assert any("three-truths" in e.lower() for e in result.validation_errors)


# ─────────────────────────────────────────────────────────────────────────────
# 4. all_validated requires an EXTERNAL check (no self-acknowledgement)
# ─────────────────────────────────────────────────────────────────────────────

def _converged_result(validation_status: bool = True) -> AgentResult:
    return AgentResult(
        agent_name="LoadFlowAgent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        validation_status=validation_status,
        data={"converged": True},
    )


@pytest.mark.asyncio
async def test_all_validated_requires_external_validation_not_just_self_report(monkeypatch):
    """Self-report alone must NOT produce all_validated=True."""
    orchestrator = ChiefEngineeringOrchestrator()

    async def mock_execute(task):  # noqa: ARG001
        # Producer claims its own work is valid — but no external check exists.
        return [_converged_result(validation_status=True)]

    monkeypatch.setattr(orchestrator, "_execute_workflow", mock_execute)
    orchestrator.agents.pop("validation", None)

    outcome = await orchestrator.execute_autonomous_workflow(
        user_goal="Evaluate grid voltage stability and power flow",
        system_data={"buses": 14},
    )

    assert outcome["self_reported_valid"] is True
    assert outcome["all_validated"] is False, (
        "all_validated must not be true without an independent validation pass"
    )
    assert outcome["external_validation"]["performed"] is False
    assert outcome["external_validation"]["reason"] == "validation_agent_missing"


@pytest.mark.asyncio
async def test_all_validated_true_only_with_external_pass(monkeypatch):
    orchestrator = ChiefEngineeringOrchestrator()

    async def mock_execute(task):  # noqa: ARG001
        return [_converged_result(validation_status=True)]

    monkeypatch.setattr(orchestrator, "_execute_workflow", mock_execute)

    outcome = await orchestrator.execute_autonomous_workflow(
        user_goal="Evaluate grid voltage stability and power flow",
        system_data={"buses": 14},
    )

    assert outcome["self_reported_valid"] is True
    assert outcome["external_validation"]["performed"] is True
    assert outcome["external_validation"]["passed"] is True
    assert outcome["all_validated"] is True


@pytest.mark.asyncio
async def test_all_validated_false_when_self_report_false(monkeypatch):
    orchestrator = ChiefEngineeringOrchestrator()

    async def mock_execute(task):  # noqa: ARG001
        return [_converged_result(validation_status=False)]

    monkeypatch.setattr(orchestrator, "_execute_workflow", mock_execute)

    outcome = await orchestrator.execute_autonomous_workflow(
        user_goal="Evaluate grid voltage stability and power flow",
        system_data={"buses": 14},
    )

    assert outcome["self_reported_valid"] is False
    assert outcome["all_validated"] is False


@pytest.mark.asyncio
async def test_all_validated_fails_closed_on_empty_results(monkeypatch):
    """`all([])` was vacuously True before M4.4 — now empty ⇒ False."""
    orchestrator = ChiefEngineeringOrchestrator()

    async def mock_execute(task):  # noqa: ARG001
        return []

    monkeypatch.setattr(orchestrator, "_execute_workflow", mock_execute)

    outcome = await orchestrator.execute_autonomous_workflow(
        user_goal="Evaluate grid voltage stability and power flow",
        system_data={"buses": 14},
    )

    assert outcome["all_validated"] is False
    assert outcome["self_reported_valid"] is False
    assert outcome["external_validation"]["reason"] == "no_results"


# ─────────────────────────────────────────────────────────────────────────────
# 5. predictive / anomaly are context-bound — never executable study types
# ─────────────────────────────────────────────────────────────────────────────

def test_context_bound_keys_rejected_by_study_executor():
    from services.study_executor import _NATIVE_ALIASES, STUDY_DISPATCH

    native_allowed = set(STUDY_DISPATCH) | set(_NATIVE_ALIASES)
    for key in ("predictive", "anomaly"):
        assert key not in native_allowed, (
            f"context-bound capability '{key}' became an executable study type"
        )


def test_context_bound_keys_are_not_study_type_members():
    from agents.registry import CONTEXT_BOUND_AGENT_KEYS

    study_members = {s.value for s in StudyType}
    leaked = CONTEXT_BOUND_AGENT_KEYS & study_members
    assert not leaked, f"context-bound keys leaked into StudyType: {leaked}"



# ─────────────────────────────────────────────────────────────────────────────
# 6. M4.2 — Mastra plans, Python executes (contract adapter)
# ─────────────────────────────────────────────────────────────────────────────

def _single_node_plan(**overrides) -> dict:
    plan = {
        "plan_id": "plan-m42-1",
        "run_id": "run-m42-1",
        "description": "M4.2 boundary adapter plan",
        "nodes": [
            {
                "node_id": "n1",
                "study_type": "load_flow",
                "agent_id": "load-flow-agent",
                "depends_on": [],
                "parameters": {"system": {"buses": []}},
            }
        ],
    }
    plan.update(overrides)
    return plan


@pytest.mark.asyncio
async def test_execute_execution_plan_returns_trace_contract(monkeypatch):
    orchestrator = ChiefEngineeringOrchestrator()
    captured: dict = {}

    async def fake_execute(task):  # noqa: ARG001
        captured["task"] = task
        return [_converged_result()]

    monkeypatch.setattr(orchestrator, "_execute_workflow", fake_execute)

    trace = await orchestrator.execute_execution_plan(
        _single_node_plan(),
        context_parameters={"tenant_id": "tenant-42", "user_id": "user-7"},
    )

    from contracts.ai.models import ExecutionTraceContract

    assert isinstance(trace, ExecutionTraceContract)
    assert trace.plan_id == "plan-m42-1"
    assert trace.run_id == "run-m42-1"

    # The plan's own DAG was handed to the engine (M3 scheduling reused)
    task = captured["task"]
    assert task.plan_id == "plan-m42-1"
    assert task.run_id == "run-m42-1"
    assert task.parameters["tenant_id"] == "tenant-42"
    assert [n["node_id"] for n in task.parameters["custom_nodes"]] == ["n1"]
    assert task.parameters["custom_nodes"][0]["study_type"] == "load_flow"

    # M4.4 independent validation is recorded on the trace
    checks = [v.check_name for v in trace.validations]
    assert "independent_validation" in checks
    assert trace.overall_success is True


@pytest.mark.asyncio
async def test_execute_execution_plan_folds_in_independent_validation(monkeypatch):
    """overall_success must NOT survive when the external check disagrees."""
    orchestrator = ChiefEngineeringOrchestrator()

    async def fake_execute(task):  # noqa: ARG001
        # Self-reported valid, but no independent agent will confirm it.
        return [_converged_result(validation_status=True)]

    monkeypatch.setattr(orchestrator, "_execute_workflow", fake_execute)
    orchestrator.agents.pop("validation", None)

    trace = await orchestrator.execute_execution_plan(_single_node_plan())

    independent = [v for v in trace.validations if v.check_name == "independent_validation"]
    assert independent and independent[0].passed is False
    assert trace.overall_success is False


@pytest.mark.asyncio
async def test_execute_execution_plan_rejects_unknown_study_type():
    orchestrator = ChiefEngineeringOrchestrator()
    plan = _single_node_plan(
        nodes=[{"node_id": "n1", "study_type": "teleportation", "agent_id": "x"}]
    )
    with pytest.raises(ValueError, match="unknown study type"):
        await orchestrator.execute_execution_plan(plan)


@pytest.mark.asyncio
async def test_execute_execution_plan_rejects_empty_plan():
    orchestrator = ChiefEngineeringOrchestrator()
    with pytest.raises(ValueError, match="no nodes"):
        await orchestrator.execute_execution_plan(_single_node_plan(nodes=[]))


@pytest.mark.asyncio
async def test_execute_execution_plan_rejects_malformed_payload():
    orchestrator = ChiefEngineeringOrchestrator()
    with pytest.raises(ValueError, match="invalid ExecutionPlanContract"):
        await orchestrator.execute_execution_plan({"plan_id": "only-an-id"})


@pytest.mark.asyncio
async def test_execute_execution_plan_accepts_typed_contract_object():
    from contracts.ai.models import ExecutionPlanContract, PlanNodeContract

    orchestrator = ChiefEngineeringOrchestrator()

    async def fake_execute(task):  # noqa: ARG001
        return [_converged_result()]

    monkeypatch_target = orchestrator
    monkeypatch_target._execute_workflow = fake_execute  # type: ignore[method-assign]

    plan = ExecutionPlanContract(
        plan_id="typed-plan",
        run_id="typed-run",
        nodes=[
            PlanNodeContract(
                node_id="n1",
                study_type="short_circuit",
                agent_id="short-circuit-agent",
            )
        ],
    )
    trace = await orchestrator.execute_execution_plan(plan)
    assert trace.plan_id == "typed-plan"
    assert trace.run_id == "typed-run"

