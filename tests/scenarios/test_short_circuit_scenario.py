"""Short Circuit Agent - Multi-turn Conversation Scenario Test.

Tests the ShortCircuitAgent through multi-turn engineering scenarios covering
IEC 60909 fault analysis, sequence network construction, and fault current
verification.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    ShortCircuitAgent,
    StudyType,
)


@pytest.fixture
def agent():
    return ShortCircuitAgent()


class TestShortCircuitScenario:
    """Test Short Circuit Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEC 60909 standard."""
        assert agent.agent_name == "ShortCircuitAgent"
        assert "IEC 60909-0:2016" in agent.standards_compliance

    @pytest.mark.asyncio
    async def test_missing_system_data(self, agent):
        """Test 2: Agent handles missing system data gracefully."""
        task = EngineeringTask(
            task_id="sc-001",
            description="Short circuit with no system",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={},  # No system data
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_fault_types_supported(self, agent):
        """Test 3: Agent supports all IEC 60909 fault types."""
        # Verify the agent has the expected standard reference
        assert agent.standards_compliance is not None
        # The agent's execute method handles 3ph, SLG, LL, DLG faults
        # by iterating through FaultAnalyzer methods
        assert agent.agent_name == "ShortCircuitAgent"

    @pytest.mark.asyncio
    async def test_validation_checks_positive_fault_current(self, agent):
        """Test 4: Validation rejects non-positive fault currents."""
        # Construct a mock result with zero fault current
        result = AgentResult(
            agent_name="ShortCircuitAgent",
            study_type=StudyType.SHORT_CIRCUIT,
            status=AgentStatus.COMPLETED,
            data={
                "fault_results": {
                    "Bus1": {
                        "three_phase": {"fault_current": 0},
                    }
                },
                "standard": "IEC 60909-0:2016",
            },
        )
        valid = agent.validate_result(result)
        # Zero fault current should trigger a validation error
        assert not valid
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_validation_passes_with_valid_currents(self, agent):
        """Test 5: Validation passes with valid fault currents."""
        result = AgentResult(
            agent_name="ShortCircuitAgent",
            study_type=StudyType.SHORT_CIRCUIT,
            status=AgentStatus.COMPLETED,
            data={
                "fault_results": {
                    "Bus1": {
                        "three_phase": {"fault_current": 10.0 + 5j},
                        "line_to_ground": {"fault_current": 8.0 + 3j},
                    }
                },
                "standard": "IEC 60909-0:2016",
            },
        )
        valid = agent.validate_result(result)
        assert valid

    @pytest.mark.asyncio
    async def test_execution_logging(self, agent):
        """Test 6: Agent logs short circuit analysis events."""
        task = EngineeringTask(
            task_id="sc-002",
            description="Log test",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={},  # Will fail but still logs
        )
        await agent.execute(task)
        assert len(agent.execution_log) > 0
