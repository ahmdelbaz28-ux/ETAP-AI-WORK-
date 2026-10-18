"""
Regression tests for Defect 5:
- All reference engineering execution must route through the canonical ExecutionOrchestrator gateway.
- Unknown study types must be rejected (fail-closed, HTTP 422) and NEVER silently default to LOAD_FLOW.
- MathGuard must distinguish genuine independent recomputation from self-consistency extraction.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest

from agents.ahmed_etap_orchestrator import (
    AhmedETAPSkillAgent,
    MathGuard,
    MathGuardResult,
    TrustedCalculatorRegistry,
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
    mock_exec_res.data = {"fault_current_ka": 20.0}
    mock_exec_res.validation_status = "passed"
    mock_exec_res.errors = []

    mock_orch = AsyncMock()
    mock_orch.execute = AsyncMock(return_value=mock_exec_res)

    # Physical parameters: I_fault = 13.8 kV / (sqrt(3) * 0.3983716857) = 20.0 kA
    v_kv = 13.8
    z_ohm = (v_kv * 1000.0) / (math.sqrt(3) * 20.0 * 1000.0)

    task = EngineeringTask(
        task_id="test_canonical",
        description="test canonical route",
        study_types=[StudyType.SHORT_CIRCUIT],
        parameters={
            "study_type": "short_circuit",
            "tenant_id": "tenant-auth-01",
            "user_id": "usr-eng-01",
            "project": {"name": "TestProj", "base_mva": 100.0, "base_kv": 13.8},
            "parameters": {
                "system": {"buses": [{"bus_id": "Bus1", "base_kv": 13.8}], "lines": []},
                "voltage_kv": v_kv,
                "z_ohm": z_ohm,
            },
            "claim_value": 20.0,
            "claim_unit": "kA",
            "quantity_kind": "current",
            "budget_tokens": 8000,
        },
    )

    with patch("services.execution_orchestrator.get_execution_orchestrator", return_value=mock_orch):
        result = await agent.execute(task)
        assert mock_orch.execute.called
        assert result.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_caller_injected_recompute_fn_ignored():
    """Caller-injected recompute_fn in task parameters cannot bypass internal trusted calculator."""
    agent = AhmedETAPSkillAgent()
    mock_exec_res = AsyncMock()
    mock_exec_res.success = True
    mock_exec_res.data = {"bus_results": {"Bus1": {"voltage_magnitude_pu": 1.01}}}
    mock_exec_res.validation_status = "passed"
    mock_exec_res.errors = []

    mock_orch = AsyncMock()
    mock_orch.execute = AsyncMock(return_value=mock_exec_res)

    def malicious_recompute():
        return 1.01

    malicious_recompute.is_independent = True
    malicious_recompute._provenance = "domain_engine"

    task = EngineeringTask(
        task_id="test_unauthorized_recompute",
        description="test untrusted recompute injection",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "study_type": "load_flow",
            "tenant_id": "tenant-auth-01",
            "user_id": "usr-eng-01",
            "project": {"name": "TestProj", "base_mva": 100.0, "base_kv": 13.8},
            "parameters": {
                "system": {"buses": [{"bus_id": "Bus1", "base_kv": 13.8}], "lines": []},
            },
            # Malicious attempt to inject untrusted callback
            "recompute_fn": malicious_recompute,
            "claim_value": 1.01,
            "claim_unit": "pu",
            "quantity_kind": "voltage",
            "budget_tokens": 8000,
        },
    )

    with patch("services.execution_orchestrator.get_execution_orchestrator", return_value=mock_orch):
        result = await agent.execute(task)
        # Must FAIL closed because load_flow has no registered independent calculator
        # and malicious_recompute was ignored
        assert result.status == AgentStatus.FAILED


def test_math_guard_self_asserted_provenance_rejected():
    """A callable that self-asserts is_independent=True and _provenance='domain_engine' MUST STILL FAIL.

    Proof that caller-controlled trust assertions cannot authorize MathGuard validation.
    """
    mg = MathGuard(tolerance_pct=0.01)

    # 1. Caller-created function asserting domain_engine provenance without registry binding -> FAILS
    def caller_crafted_fn():
        return 1.05

    caller_crafted_fn.is_independent = True
    caller_crafted_fn._provenance = "domain_engine"

    res_crafted = mg.validate(
        claim_value=1.05,
        recompute=caller_crafted_fn,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert res_crafted.passed is False
    assert res_crafted.is_independent is False
    assert "lacks authenticated internal registry provenance" in res_crafted.reason


def test_math_guard_registered_trusted_calculator_succeeds():
    """Only genuine calculators registered in TrustedCalculatorRegistry can pass MathGuard."""
    mg = MathGuard(tolerance_pct=0.01)

    # Trusted calculator registered through internal registry
    trusted_calc = TrustedCalculatorRegistry.create(
        calculator_id="test_bus_voltage",
        study_type="load_flow",
        quantity_kind="voltage",
        unit="pu",
        fn=lambda: 1.05,
    )

    res_trusted = mg.validate(
        claim_value=1.05,
        recompute=trusted_calc,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert res_trusted.passed is True
    assert res_trusted.is_independent is True
    assert res_trusted.reason == ""


def test_math_guard_unit_and_tolerance_mismatch_fails():
    """Mismatched unit, mismatched quantity, or tolerance violation must fail closed."""
    mg = MathGuard(tolerance_pct=0.01)

    trusted_calc = TrustedCalculatorRegistry.create(
        calculator_id="test_current_calc",
        study_type="short_circuit",
        quantity_kind="current",
        unit="kA",
        fn=lambda: 20.0,
    )

    # 1. Tolerance mismatch: claim=25.0 vs recomputed=20.0
    res_tol = mg.validate(
        claim_value=25.0,
        recompute=trusted_calc,
        quantity_kind="current",
        claim_unit="kA",
    )
    assert res_tol.passed is False
    assert "tolerance" in res_tol.reason.lower() or "mismatch" in res_tol.reason.lower()

    # 2. Quantity mismatch: calculator is "current" but validation requested "voltage"
    res_quant = mg.validate(
        claim_value=20.0,
        recompute=trusted_calc,
        quantity_kind="voltage",
        claim_unit="kV",
    )
    assert res_quant.passed is False
    assert "QUANTITY_MISMATCH" in res_quant.reason

    # 3. Unit mismatch: expected "A" but calculator is "kA"
    res_unit = mg.validate(
        claim_value=20.0,
        recompute=trusted_calc,
        quantity_kind="current",
        claim_unit="kA",
        expected_unit="A",
    )
    assert res_unit.passed is False
    assert "UNIT_MISMATCH" in res_unit.reason


def test_build_domain_recompute_requires_explicit_power_factor():
    """_build_domain_recompute must require explicit power factor and reject silent defaults (0.85)."""
    from agents.ahmed_etap_orchestrator import ProjectRef

    proj = ProjectRef(name="Test", base_mva=100.0, base_kv=13.8)

    # Cable sizing missing power factor -> returns None
    recompute_no_pf = AhmedETAPSkillAgent._build_domain_recompute(
        "cable_sizing",
        {"power_kw": 500.0, "voltage_v": 400.0},
        proj,
    )
    assert recompute_no_pf is None

    # Cable sizing with explicit valid power factor -> returns valid independent callback
    recompute_with_pf = AhmedETAPSkillAgent._build_domain_recompute(
        "cable_sizing",
        {"power_kw": 500.0, "voltage_v": 400.0, "power_factor": 0.88},
        proj,
    )
    assert recompute_with_pf is not None
    assert recompute_with_pf.is_independent is True
    assert getattr(recompute_with_pf, "_provenance", None) == "domain_engine"

    # Transformer sizing missing power factor -> returns None
    recompute_xfmr_no_pf = AhmedETAPSkillAgent._build_domain_recompute(
        "transformer_sizing",
        {"load_kw": 800.0},
        proj,
    )
    assert recompute_xfmr_no_pf is None

    # Transformer sizing with explicit valid power factor -> returns valid callback
    recompute_xfmr_pf = AhmedETAPSkillAgent._build_domain_recompute(
        "transformer_sizing",
        {"load_kw": 800.0, "power_factor": 0.90},
        proj,
    )
    assert recompute_xfmr_pf is not None
    assert recompute_xfmr_pf.is_independent is True
    assert getattr(recompute_xfmr_pf, "_provenance", None) == "domain_engine"


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
            "tenant_id": "tenant-auth-01",
            "user_id": "usr-eng-01",
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
