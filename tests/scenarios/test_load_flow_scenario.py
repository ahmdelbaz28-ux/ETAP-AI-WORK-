"""Load Flow Agent - Multi-turn Conversation Scenario Test.

Tests the LoadFlowAgent through multi-turn engineering scenarios covering
Newton-Raphson convergence, voltage violation detection, and solver
interaction with the orchestrator task framework.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    LoadFlowAgent,
    StudyType,
)


@pytest.fixture
def agent():
    """Provide a fresh LoadFlowAgent instance."""
    return LoadFlowAgent()


# ---------------------------------------------------------------------------
# Scenario Tests
# ---------------------------------------------------------------------------


class TestLoadFlowScenario:
    """Test Load Flow Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with correct defaults."""
        assert agent.agent_name == "LoadFlowAgent"
        assert agent.status == AgentStatus.IDLE
        assert agent.convergence_tolerance == 1e-6
        assert agent.voltage_limits["min"] == 0.95
        assert agent.voltage_limits["max"] == 1.05

    @pytest.mark.asyncio
    async def test_load_flow_missing_system_data(self, agent):
        """Test 2: Agent handles missing system data gracefully."""
        task = EngineeringTask(
            task_id="lf-002",
            description="Load flow with missing system data",
            study_types=[StudyType.LOAD_FLOW],
            parameters={},  # No system data
        )
        result = await agent.execute(task)

        assert result.status == AgentStatus.FAILED
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_voltage_violation_detection(self, agent):
        """Test 3: Agent correctly flags voltage violations.

        Creates a mock result with out-of-range voltages and verifies
        the validation method catches them.
        """
        result = AgentResult(
            agent_name="LoadFlowAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "converged": True,
                "buses": {
                    "Bus1": {"voltage_magnitude_pu": 1.00},
                    "Bus2": {"voltage_magnitude_pu": 0.90},  # Below 0.95
                    "Bus3": {"voltage_magnitude_pu": 1.08},  # Above 1.05
                },
            },
        )
        valid = agent.validate_result(result)
        assert not valid
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_validation_on_valid_result(self, agent):
        """Test 4: Validation passes with in-range voltages."""
        result = AgentResult(
            agent_name="LoadFlowAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "converged": True,
                "buses": {
                    "Bus1": {"voltage_magnitude_pu": 1.00},
                    "Bus2": {"voltage_magnitude_pu": 0.98},
                    "Bus3": {"voltage_magnitude_pu": 0.97},
                },
            },
        )
        valid = agent.validate_result(result)
        assert valid

    @pytest.mark.asyncio
    async def test_non_convergent_result(self, agent):
        """Test 5: Non-convergent result is flagged."""
        result = AgentResult(
            agent_name="LoadFlowAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "converged": False,
                "buses": {},
            },
        )
        valid = agent.validate_result(result)
        assert not valid

    @pytest.mark.asyncio
    async def test_execution_log_populated(self, agent):
        """Test 6: Agent logs execution events."""
        task = EngineeringTask(
            task_id="lf-004",
            description="Log test",
            study_types=[StudyType.LOAD_FLOW],
            parameters={},  # Will fail but still logs
        )
        await agent.execute(task)
        assert len(agent.execution_log) > 0
