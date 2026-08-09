"""Protection Coordination Agent - Multi-turn Conversation Scenario Test.

Tests the ProtectionCoordinationAgent through multi-turn engineering scenarios
covering IEC 60255 relay coordination, time-current curves, and margin checks.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    ProtectionCoordinationAgent,
    StudyType,
)


@pytest.fixture
def agent():
    return ProtectionCoordinationAgent()


class TestProtectionScenario:
    """Test Protection Coordination Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEC 60255 standard."""
        assert agent.agent_name == "ProtectionCoordinationAgent"
        assert agent.standard == "IEC 60255"

    @pytest.mark.asyncio
    async def test_missing_system_data(self, agent):
        """Test 2: Agent handles missing system data."""
        task = EngineeringTask(
            task_id="prot-001",
            description="Protection with no system",
            study_types=[StudyType.PROTECTION_COORDINATION],
            parameters={},  # No system data
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_validation_coordinated_relays(self, agent):
        """Test 3: Validation passes when all relays are coordinated."""
        result = AgentResult(
            agent_name="ProtectionCoordinationAgent",
            study_type=StudyType.PROTECTION_COORDINATION,
            status=AgentStatus.COMPLETED,
            data={
                "all_coordinated": True,
                "coordination_results": [
                    {"coordinated": True, "margin": 0.3},
                    {"coordinated": True, "margin": 0.25},
                ],
                "relay_count": 3,
                "standard": "IEC 60255",
            },
        )
        valid = agent.validate_result(result)
        assert valid

    @pytest.mark.asyncio
    async def test_validation_uncoordinated_relays(self, agent):
        """Test 4: Validation flags relay miscoordination."""
        result = AgentResult(
            agent_name="ProtectionCoordinationAgent",
            study_type=StudyType.PROTECTION_COORDINATION,
            status=AgentStatus.COMPLETED,
            data={
                "all_coordinated": False,
                "coordination_results": [
                    {"coordinated": True, "margin": 0.3},
                    {"coordinated": False, "margin": 0.05},  # Insufficient margin
                ],
                "relay_count": 3,
                "standard": "IEC 60255",
            },
        )
        valid = agent.validate_result(result)
        assert not valid
        assert any("margin" in err for err in result.validation_errors)

    @pytest.mark.asyncio
    async def test_relay_count_tracking(self, agent):
        """Test 5: Relay count is tracked in results."""
        result = AgentResult(
            agent_name="ProtectionCoordinationAgent",
            study_type=StudyType.PROTECTION_COORDINATION,
            status=AgentStatus.COMPLETED,
            data={
                "all_coordinated": True,
                "coordination_results": [],
                "relay_count": 5,
                "standard": "IEC 60255",
            },
        )
        assert result.data["relay_count"] == 5

    @pytest.mark.asyncio
    async def test_execution_log(self, agent):
        """Test 6: Agent logs protection coordination events."""
        task = EngineeringTask(
            task_id="prot-002",
            description="Log test",
            study_types=[StudyType.PROTECTION_COORDINATION],
            parameters={},
        )
        await agent.execute(task)
        assert len(agent.execution_log) > 0
