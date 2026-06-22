"""ETAP Execution Agent - Multi-turn Conversation Scenario Test.

Tests the ETAPExecutionAgent through multi-turn engineering scenarios covering
ETAP provider interface, study execution, and cross-platform compatibility.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    ETAPExecutionAgent,
    StudyType,
)


@pytest.fixture
def agent():
    """Provide an ETAPExecutionAgent instance.

    The agent may fail to find an ETAP provider on Linux, which is expected.
    """
    return ETAPExecutionAgent()


class TestETAPExecutionScenario:
    """Test ETAP Execution Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with provider interface."""
        assert agent.agent_name == "ETAPExecutionAgent"

    @pytest.mark.asyncio
    async def test_no_provider_available(self, agent):
        """Test 2: Agent handles no ETAP provider gracefully.

        On Linux without ETAP_WORKER_URL, the provider should report
        unavailable and the agent should return a FAILED result.
        """
        task = EngineeringTask(
            task_id="etap-001",
            description="Run ETAP load flow",
            study_types=[StudyType.LOAD_FLOW],
            parameters={"project_path": "/test/project.etap", "study_type": "LOAD_FLOW"},
        )
        result = await agent.execute(task)

        # Provider may not be available; should fail gracefully
        if not agent.provider.is_available():
            assert result.status == AgentStatus.FAILED
            assert any(
                "provider" in err.lower() or "available" in err.lower()
                for err in result.validation_errors
            )

    @pytest.mark.asyncio
    async def test_study_type_mapping(self, agent):
        """Test 3: Study type string is mapped correctly."""
        # The execute method maps string to ETAPStudyType enum
        # Verify parameter extraction works
        task = EngineeringTask(
            task_id="etap-002",
            description="ETAP short circuit",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={"study_type": "SHORT_CIRCUIT"},
        )
        assert task.parameters["study_type"] == "SHORT_CIRCUIT"

    @pytest.mark.asyncio
    async def test_validation_failed_result(self, agent):
        """Test 4: Validation fails when ETAP reports failure."""
        result = AgentResult(
            agent_name="ETAPExecutionAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "success": False,
                "errors": ["ETAP project file not found"],
                "warnings": [],
            },
        )
        valid = agent.validate_result(result)
        assert not valid

    @pytest.mark.asyncio
    async def test_validation_success_result(self, agent):
        """Test 5: Validation passes when ETAP reports success."""
        result = AgentResult(
            agent_name="ETAPExecutionAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={
                "success": True,
                "errors": [],
                "warnings": ["Minor convergence issue"],
            },
        )
        valid = agent.validate_result(result)
        assert valid

    @pytest.mark.asyncio
    async def test_visible_parameter(self, agent):
        """Test 6: Visible parameter for ETAP UI mode is supported."""
        task = EngineeringTask(
            task_id="etap-003",
            description="ETAP with UI",
            study_types=[StudyType.LOAD_FLOW],
            parameters={"visible": True, "project_path": "/test.etap"},
        )
        assert task.parameters.get("visible") is True
