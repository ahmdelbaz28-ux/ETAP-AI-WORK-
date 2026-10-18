"""
Regression tests for Defect 5:
- All reference engineering execution must route through the canonical ExecutionOrchestrator gateway.
- Unknown study types must be rejected (fail-closed, HTTP 422) and NEVER silently default to LOAD_FLOW.
- MathGuard must distinguish genuine independent recomputation from self-consistency extraction.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.ahmed_etap_orchestrator import (
    AhmedETAPSkillAgent,
    MathGuard,
    MathGuardResult,
    canonicalize_study_type,
)
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    ChiefEngineeringOrchestrator,
    EngineeringTask,
    StudyType,
)


def test_unknown_study_type_fails_closed_in_default_lead_for():
    """AhmedETAPSkillAgent._default_lead_for must NOT silently return 'load_flow'."""
    assert AhmedETAPSkillAgent._default_lead_for("non_existent_study") == ""
    assert AhmedETAPSkillAgent._default_lead_for("invalid_magic_study") == ""
    assert AhmedETAPSkillAgent._default_lead_for("") == ""


@pytest.mark.asyncio
async def test_ahmed_etap_skill_agent_rejects_unknown_study():
    """AhmedETAPSkillAgent.execute must fail closed on unknown study types."""
    agent = AhmedETAPSkillAgent()
    task = EngineeringTask(
        task_id="test_unknown",
        description="test unknown",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"study_type": "unknown_study_xyz"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert any("Unknown or unsupported study_type" in err for err in result.validation_errors)


@pytest.mark.asyncio
async def test_ahmed_etap_routes_system_through_execution_orchestrator():
    """When a system model is provided, execution must route to ExecutionOrchestrator."""
    agent = AhmedETAPSkillAgent()
    mock_exec_res = AsyncMock()
    mock_exec_res.success = True
    mock_exec_res.data = {"bus_results": {"Bus1": {"voltage_magnitude_pu": 1.01}}}
    mock_exec_res.validation_status = "passed"
    mock_exec_res.errors = []

    mock_orch = AsyncMock()
    mock_orch.execute = AsyncMock(return_value=mock_exec_res)

    def independent_recompute():
        return 1.01

    independent_recompute.is_independent = True

    task = EngineeringTask(
        task_id="test_canonical",
        description="test canonical route",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "study_type": "load_flow",
            "project": {"name": "TestProj", "base_mva": 100.0, "base_kv": 13.8},
            "parameters": {
                "system": {"buses": [{"bus_id": "Bus1", "base_kv": 13.8}], "lines": []},
            },
            "recompute_fn": independent_recompute,
            "claim_value": 1.01,
            "claim_unit": "pu",
            "quantity_kind": "voltage",
            "budget_tokens": 8000,
        },
    )

    with patch("services.execution_orchestrator.get_execution_orchestrator", return_value=mock_orch):
        result = await agent.execute(task)
        assert mock_orch.execute.called
        assert result.status == AgentStatus.COMPLETED


def test_math_guard_flags_non_independent_recomputation():
    """When recomputation is extracted from lead agent, is_independent must be False and MathGuard must FAIL."""
    mg = MathGuard(tolerance_pct=0.01)

    # 1. Independent callable with proven independence
    def independent_fn():
        return 1.05

    independent_fn.is_independent = True

    res_indep = mg.validate(
        claim_value=1.05,
        recompute=independent_fn,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert res_indep.passed is True
    assert res_indep.is_independent is True
    assert res_indep.reason == ""

    # 2. Self-consistency extraction (is_independent = False) -> MUST FAIL CLOSED
    def extracted_fn():
        return 1.05

    extracted_fn.is_independent = False

    res_extracted = mg.validate(
        claim_value=1.05,
        recompute=extracted_fn,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert res_extracted.passed is False
    assert res_extracted.is_independent is False
    assert "not an independent" in res_extracted.reason.lower()


def test_math_guard_unverified_provenance_fails():
    """A callable with no provenance attribute defaults to is_independent=False and fails."""
    mg = MathGuard(tolerance_pct=0.01)

    def plain_fn():
        return 1.05

    res = mg.validate(
        claim_value=1.05,
        recompute=plain_fn,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert res.passed is False
    assert res.is_independent is False
    assert "not an independent" in res.reason.lower()


@pytest.mark.asyncio
async def test_ahmed_etap_canonical_exception_fails_closed_without_lead_agent_fallback():
    """Canonical dispatch exception must NOT fall back to direct lead_agent.execute."""
    agent = AhmedETAPSkillAgent()
    mock_lead = AsyncMock()
    mock_lead.agent_name = "load_flow"
    mock_lead.execute = AsyncMock()

    mock_orch = AsyncMock()
    mock_orch.execute = AsyncMock(side_effect=RuntimeError("Canonical orchestrator service unavailable"))

    task = EngineeringTask(
        task_id="test_canonical_fail",
        description="test canonical fail closed",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "study_type": "load_flow",
            "project": {"name": "TestProj", "base_mva": 100.0, "base_kv": 13.8},
            "parameters": {
                "system": {"buses": [{"bus_id": "Bus1", "base_kv": 13.8}], "lines": []},
            },
        },
    )

    with patch.object(agent, "_resolve_orchestrator") as mock_resolve:
        mock_chief = AsyncMock()
        mock_chief.agents = {"load_flow": mock_lead}
        mock_resolve.return_value = mock_chief

        with patch("services.execution_orchestrator.get_execution_orchestrator", return_value=mock_orch):
            result = await agent.execute(task)

            # Execution failed closed
            assert result.status == AgentStatus.FAILED
            assert any("Canonical execution failed" in err for err in result.validation_errors)
            # Lead agent must NEVER have been called as fallback
            assert not mock_lead.execute.called


@pytest.mark.asyncio
async def test_ahmed_etap_missing_required_system_fails_closed():
    """Missing system for a study requiring a system model fails closed without direct calculation."""
    agent = AhmedETAPSkillAgent()
    mock_lead = AsyncMock()
    mock_lead.agent_name = "load_flow"
    mock_lead.execute = AsyncMock()

    task = EngineeringTask(
        task_id="test_missing_system",
        description="test missing system fail closed",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "study_type": "load_flow",
            "project": {"name": "TestProj", "base_mva": 100.0, "base_kv": 13.8},
            "parameters": {},  # No 'system'
        },
    )

    with patch.object(agent, "_resolve_orchestrator") as mock_resolve:
        mock_chief = AsyncMock()
        mock_chief.agents = {"load_flow": mock_lead}
        mock_resolve.return_value = mock_chief

        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED
        assert any("requires a system model" in err for err in result.validation_errors)
        assert not mock_lead.execute.called
