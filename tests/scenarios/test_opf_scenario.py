"""Optimal Power Flow Agent - Multi-turn Conversation Scenario Test.

Tests the OptimalPowerFlowAgent through multi-turn engineering scenarios covering
DC-OPF, AC-OPF, economic dispatch, and power balance verification.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    OptimalPowerFlowAgent,
    StudyType,
)


@pytest.fixture
def agent():
    return OptimalPowerFlowAgent()


class TestOPFScenario:
    """Test Optimal Power Flow Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes correctly."""
        assert agent.agent_name == "OptimalPowerFlowAgent"

    @pytest.mark.asyncio
    async def test_missing_system_data(self, agent):
        """Test 2: Agent handles missing system data."""
        task = EngineeringTask(
            task_id="opf-001",
            description="OPF with no system",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={},  # No system data
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_validation_non_convergent_opf(self, agent):
        """Test 3: Validation flags non-convergent OPF."""
        result = AgentResult(
            agent_name="OptimalPowerFlowAgent",
            study_type=StudyType.OPTIMAL_POWER_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "success": False,
                "objective_value": 0,
                "generator_dispatch": {},
                "total_generation_mw": 0,
                "total_load_mw": 100,
                "total_losses_mw": 0,
                "method": "dc",
            },
        )
        valid = agent.validate_result(result)
        assert not valid

    @pytest.mark.asyncio
    async def test_validation_power_balance(self, agent):
        """Test 4: Validation checks power balance within tolerance."""
        result = AgentResult(
            agent_name="OptimalPowerFlowAgent",
            study_type=StudyType.OPTIMAL_POWER_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "success": True,
                "objective_value": 5000.0,
                "generator_dispatch": {"G1": {"P_MW": 80, "Q_MVAR": 20}},
                "total_generation_mw": 100.0,
                "total_load_mw": 95.0,
                "total_losses_mw": 5.0,
                "method": "dc",
            },
        )
        valid = agent.validate_result(result)
        assert valid  # Gen = Load + Losses → 100 = 95 + 5

    @pytest.mark.asyncio
    async def test_validation_power_balance_error(self, agent):
        """Test 5: Validation rejects large power balance errors."""
        result = AgentResult(
            agent_name="OptimalPowerFlowAgent",
            study_type=StudyType.OPTIMAL_POWER_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "success": True,
                "objective_value": 5000.0,
                "generator_dispatch": {},
                "total_generation_mw": 100.0,
                "total_load_mw": 80.0,
                "total_losses_mw": 5.0,  # 100 ≠ 80 + 5
                "method": "dc",
            },
        )
        valid = agent.validate_result(result)
        assert not valid

    @pytest.mark.asyncio
    async def test_opf_method_selection(self, agent):
        """Test 6: Task can specify DC or AC OPF method."""
        task_dc = EngineeringTask(
            task_id="opf-dc",
            description="DC-OPF",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"method": "dc"},
        )
        task_ac = EngineeringTask(
            task_id="opf-ac",
            description="AC-OPF",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"method": "ac"},
        )
        # Method parameter is extracted in execute; just verify task construction
        assert task_dc.parameters["method"] == "dc"
        assert task_ac.parameters["method"] == "ac"
