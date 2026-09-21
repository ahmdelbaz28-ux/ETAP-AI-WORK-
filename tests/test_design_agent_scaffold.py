"""
Unit tests for Generative Design Agent Scaffold (Stage 7).
Verifies:
1. Agent registration in create_specialist_agents()
2. Fail-closed safety when 'generative_design' feature flag is disabled
3. Parameter validation without guessing when enabled
4. Correct engineering synthesis when enabled with valid parameters
"""

from __future__ import annotations

import pytest

from agents.design_agent import DesignAgent
from agents.models import AgentStatus, EngineeringTask, StudyType
from agents.registry import create_agent_registry, create_specialist_agents


@pytest.mark.asyncio
async def test_design_agent_registration():
    """Verify DesignAgent is properly registered in specialist agents registry."""
    agents = create_specialist_agents()
    assert "generative_design" in agents
    assert isinstance(agents["generative_design"], DesignAgent)
    assert agents["generative_design"].prompt_handle == "design_agent"
    assert create_agent_registry()["generative_design"] is not None


@pytest.mark.asyncio
async def test_design_agent_fail_closed_when_flag_disabled(monkeypatch):
    """Verify agent fails closed when generative_design flag is disabled."""
    monkeypatch.setenv("FEATURE_FLAG_GENERATIVE_DESIGN", "false")
    agent = DesignAgent()
    task = EngineeringTask(
        task_id="task_des_fail_closed",
        description="Generative design with disabled flag",
        study_types=[StudyType.GENERATIVE_DESIGN],
        parameters={"primary_voltage_kv": 66.0, "secondary_voltage_kv": 11.0, "total_load_mva": 25.0},
    )

    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.validation_errors
    assert "Feature flag 'generative_design' is disabled" in result.validation_errors[0]
    assert result.data["summary"].get("reason") == "flag_disabled"


@pytest.mark.asyncio
async def test_design_agent_parameter_validation_when_enabled(monkeypatch):
    """Verify agent rejects missing parameters without guessing."""
    monkeypatch.setenv("FEATURE_FLAG_GENERATIVE_DESIGN", "true")
    agent = DesignAgent()
    task = EngineeringTask(
        task_id="task_des_param_val",
        description="Generative design missing parameters",
        study_types=[StudyType.GENERATIVE_DESIGN],
        parameters={"primary_voltage_kv": 66.0},  # Missing secondary and load
    )

    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.validation_errors
    assert "Missing required design parameters" in result.validation_errors[0]


@pytest.mark.asyncio
async def test_design_agent_synthesis_success(monkeypatch):
    """Verify generative topology synthesis with valid engineering inputs."""
    monkeypatch.setenv("FEATURE_FLAG_GENERATIVE_DESIGN", "true")
    agent = DesignAgent()
    task = EngineeringTask(
        task_id="task_des_success",
        description="Generative design standard substation",
        study_types=[StudyType.GENERATIVE_DESIGN],
        parameters={
            "primary_voltage_kv": 66.0,
            "secondary_voltage_kv": 11.0,
            "total_load_mva": 40.0,
            "redundancy": "N-1",
            "num_feeders": 6,
        },
    )

    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert not result.validation_errors
    assert result.data["summary"]["status"] == "success"
    assert result.data["summary"]["transformer_count"] == 2
    assert result.data["summary"]["transformer_mva_each"] >= 40.0
    assert "topology" in result.data
    topology = result.data["topology"]
    assert "Double-bus" in topology["bus_configuration"]
    assert topology["protection_scheme"]["transformer_differential_87t"] is True


# ---------------------------------------------------------------------------
# S5 Dispatch regression tests (commit 7617d30be introduced GENERATIVE_DESIGN)
# ---------------------------------------------------------------------------

def test_dispatch_generative_design_requires_system_false():
    """GENERATIVE_DESIGN must have requires_system=False in STUDY_DISPATCH.

    Root cause (commit 7617d30be): dispatch.py:136-139 originally only had
    ETAP_EXPERT and ETAP_GUI in the requires_system=False exception tuple.
    GENERATIVE_DESIGN was added to StudyType without being added to that
    exception, so it incorrectly received requires_system=True.
    Fix: added StudyType.GENERATIVE_DESIGN to the exception tuple (S5).
    """
    from engine.dispatch import STUDY_DISPATCH

    reg = STUDY_DISPATCH.get("generative_design")
    assert reg is not None, "generative_design missing from STUDY_DISPATCH"
    assert reg.handler_type == "agent", (
        f"Expected handler_type='agent', got '{reg.handler_type}'"
    )
    assert reg.requires_system is False, (
        "GENERATIVE_DESIGN should not require a System model — "
        "it is a conversational scaffold agent (commit 7617d30be)"
    )


def test_dispatch_etap_expert_and_gui_still_false():
    """Regression: ETAP_EXPERT and ETAP_GUI must keep requires_system=False.

    Guards against accidentally removing existing entries from the exception
    tuple while adding GENERATIVE_DESIGN (S5 fix).
    """
    from engine.dispatch import STUDY_DISPATCH

    for key in ("etap_expert", "etap_gui"):
        reg = STUDY_DISPATCH.get(key)
        if reg is None:
            continue  # etap_gui is optional (headless env)
        assert reg.requires_system is False, (
            f"{key} should not require a System model — "
            "it is a conversational agent (commit 7617d30be)"
        )


def test_dispatch_generative_design_flag_disabled_returns_failed(monkeypatch):
    """generative_design with flag closed → agent FAILED + no system demand.

    Verifies the fail-closed + dispatch fix together:
    1. The dispatch entry exists with requires_system=False (S5 fix).
    2. The agent rejects the task when the flag is disabled (pre-existing).
    """
    import asyncio

    from engine.dispatch import STUDY_DISPATCH

    # dispatch-level: entry exists with requires_system=False
    reg = STUDY_DISPATCH["generative_design"]
    assert reg.requires_system is False

    # agent-level: explicit reject when flag off
    monkeypatch.setenv("FEATURE_FLAG_GENERATIVE_DESIGN", "false")
    agent = DesignAgent()
    task = EngineeringTask(
        task_id="task_dispatch_regression",
        description="dispatch regression: flag disabled",
        study_types=[StudyType.GENERATIVE_DESIGN],
        parameters={"primary_voltage_kv": 66.0, "secondary_voltage_kv": 11.0, "total_load_mva": 25.0},
    )
    result = asyncio.get_event_loop().run_until_complete(agent.execute(task))
    assert result.status == AgentStatus.FAILED
    assert result.data["summary"].get("reason") == "flag_disabled"


def test_dispatch_generative_design_flag_enabled_no_system_required(monkeypatch):
    """generative_design with flag open → works without a System object.

    Verifies the fix ensures no requires_system gate blocks the agent
    when the feature flag is enabled.
    """
    import asyncio

    from engine.dispatch import STUDY_DISPATCH

    reg = STUDY_DISPATCH["generative_design"]
    assert reg.requires_system is False  # dispatch fix confirmed

    monkeypatch.setenv("FEATURE_FLAG_GENERATIVE_DESIGN", "true")
    agent = DesignAgent()
    task = EngineeringTask(
        task_id="task_dispatch_enabled",
        description="dispatch regression: flag enabled, no system needed",
        study_types=[StudyType.GENERATIVE_DESIGN],
        parameters={
            "primary_voltage_kv": 66.0,
            "secondary_voltage_kv": 11.0,
            "total_load_mva": 40.0,
            "redundancy": "N-1",
            "num_feeders": 6,
        },
    )
    result = asyncio.get_event_loop().run_until_complete(agent.execute(task))
    # Agent executes fully without any system-model demand
    assert result.status == AgentStatus.COMPLETED
    assert result.data["summary"]["status"] == "success"

