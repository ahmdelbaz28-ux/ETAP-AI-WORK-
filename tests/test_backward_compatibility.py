"""
tests/test_backward_compatibility.py — Verify that registering the new
ETAPExpertAgent does NOT break any of the previously-registered agents
or study types.

This test was added after self-criticism: the previous integration commit
added etap_expert to the orchestrator but never verified that the 9
existing agents still work correctly.
"""

from __future__ import annotations

import pytest


def test_all_old_agents_still_registered():
    """All 8 core agents that existed before etap_expert must still be there."""
    from agents.orchestrator import ChiefEngineeringOrchestrator

    orch = ChiefEngineeringOrchestrator()
    expected_old_agents = {
        "load_flow",
        "short_circuit",
        "harmonic",
        "opf",
        "protection",
        "etap_execution",
        "validation",
        "report",
    }
    actual = set(orch.agents.keys())
    missing = expected_old_agents - actual
    assert not missing, f"Backward-compat broken — missing agents: {missing}"


def test_old_agents_keep_correct_class_names():
    """Old agents must still be instances of their original classes."""
    from agents.orchestrator import (
        ChiefEngineeringOrchestrator,
        ETAPExecutionAgent,
        HarmonicAnalysisAgent,
        LoadFlowAgent,
        OptimalPowerFlowAgent,
        ProtectionCoordinationAgent,
        ReportGenerationAgent,
        ShortCircuitAgent,
        ValidationAgent,
    )

    orch = ChiefEngineeringOrchestrator()
    assert isinstance(orch.agents["load_flow"], LoadFlowAgent)
    assert isinstance(orch.agents["short_circuit"], ShortCircuitAgent)
    assert isinstance(orch.agents["harmonic"], HarmonicAnalysisAgent)
    assert isinstance(orch.agents["opf"], OptimalPowerFlowAgent)
    assert isinstance(orch.agents["protection"], ProtectionCoordinationAgent)
    assert isinstance(orch.agents["etap_execution"], ETAPExecutionAgent)
    assert isinstance(orch.agents["validation"], ValidationAgent)
    assert isinstance(orch.agents["report"], ReportGenerationAgent)


def test_old_study_types_still_accepted():
    """All 16 previously-allowed study types must still pass validation."""
    from api.studies import StudyRequest

    old_study_types = [
        "load_flow",
        "short_circuit",
        "fault",
        "arc_flash",
        "protection_coordination",
        "coordination",
        "motor_starting",
        "harmonic_analysis",
        "optimal_power_flow",
        "etap_load_flow",
        "etap_short_circuit",
        "etap_arc_flash",
        "etap_harmonic_analysis",
        "etap_optimal_power_flow",
        "etap_motor_starting",
        "etap_protection_coordination",
    ]
    for st in old_study_types:
        req = StudyRequest(study_type=st, parameters={})
        assert req.study_type == st, f"Study type '{st}' was rejected by validator"


def test_invalid_study_type_still_rejected():
    """Unknown study types must still be rejected."""
    from pydantic import ValidationError

    from api.studies import StudyRequest

    with pytest.raises(ValidationError):
        StudyRequest(study_type="nonexistent_study_type", parameters={})


def test_load_flow_study_still_runs_with_system():
    """A real load_flow study with a proper system must still produce results
    (not break with the new etap_expert dispatch branch)."""
    from api.studies import (
        BusSpec,
        LoadSpec,
        SystemSpec,
        _build_system_from_spec,
        _run_native_study,
    )

    sys_spec = SystemSpec(
        name="compat-test",
        buses=[
            BusSpec(bus_id=1, base_kv=13.8, bus_type="slack"),
            BusSpec(bus_id=2, base_kv=13.8, bus_type="pq"),
        ],
        loads=[LoadSpec(load_id=1, bus_id=2, p_load=5.0, q_load=1.0)],
    )
    system = _build_system_from_spec(sys_spec)
    result = _run_native_study("load_flow", system, {})
    assert "converged" in result, f"load_flow no longer returns 'converged': {result}"
    # The result must not be an etap_expert response
    assert "classification" not in result, "load_flow was misrouted to etap_expert!"


def test_etap_expert_does_not_interfere_with_orchestrator_get_agents_info():
    """get_agents_info() must still return info for all old agents."""
    from agents.orchestrator import ChiefEngineeringOrchestrator

    orch = ChiefEngineeringOrchestrator()
    info = orch.get_agents_info()
    assert "agents" in info
    # All old agents must still appear
    for old_agent in [
        "load_flow",
        "short_circuit",
        "harmonic",
        "opf",
        "protection",
        "etap_execution",
        "validation",
        "report",
    ]:
        assert old_agent in info["agents"], f"Agent '{old_agent}' missing from get_agents_info()"


def test_old_prompts_still_loaded():
    """All previously-registered prompts must still load via the prompt loader."""
    from agents.prompt_loader import get_system_prompt

    old_handles = [
        "load_flow_agent",
        "short_circuit_agent",
        "harmonic_agent",
        "opf_agent",
        "protection_agent",
        "etap_engineer_agent",
        "validation_agent",
        "report_agent",
    ]
    for handle in old_handles:
        prompt = get_system_prompt(handle)
        assert prompt and len(prompt) > 20, f"Prompt '{handle}' no longer loads"
