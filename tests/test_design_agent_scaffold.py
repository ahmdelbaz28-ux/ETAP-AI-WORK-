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
