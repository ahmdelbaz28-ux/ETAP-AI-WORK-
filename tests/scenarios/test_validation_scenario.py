"""Validation Agent - Multi-turn Conversation Scenario Test.

Tests the ValidationAgent through multi-turn engineering scenarios covering
voltage limit checks, thermal verification, and standards compliance.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
    ValidationAgent,
)


@pytest.fixture
def agent():
    return ValidationAgent()


class TestValidationScenario:
    """Test Validation Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with standards configuration."""
        assert agent.agent_name == "ValidationAgent"
        assert "voltage_limits" in agent.standards
        assert agent.standards["voltage_limits"]["min"] == pytest.approx(0.95)
        assert agent.standards["voltage_limits"]["max"] == pytest.approx(1.05)

    @pytest.mark.asyncio
    async def test_validate_converged_load_flow(self, agent):
        """Test 2: Validates a converged load flow with good voltages."""
        lf_result = AgentResult(
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
        task = EngineeringTask(
            task_id="val-001",
            description="Validate load flow",
            study_types=[],
            parameters={"results": [lf_result]},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["overall_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_voltage_violations(self, agent):
        """Test 3: Flags buses with out-of-range voltages."""
        lf_result = AgentResult(
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
        task = EngineeringTask(
            task_id="val-002",
            description="Validate with voltage issues",
            study_types=[],
            parameters={"results": [lf_result]},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["overall_valid"] is False
        assert result.data["validation_summary"]["failed"] > 0

    @pytest.mark.asyncio
    async def test_validate_short_circuit_results(self, agent):
        """Test 4: Validates short circuit results for reasonable currents."""
        sc_result = AgentResult(
            agent_name="ShortCircuitAgent",
            study_type=StudyType.SHORT_CIRCUIT,
            status=AgentStatus.COMPLETED,
            data={
                "fault_results": {
                    "Bus1": {"three_phase": {"fault_current": 15.0 + 5j}},
                },
            },
        )
        task = EngineeringTask(
            task_id="val-003",
            description="Validate short circuit",
            study_types=[],
            parameters={"results": [sc_result]},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_empty_results_list(self, agent):
        """Test 5: Handles empty results list gracefully."""
        task = EngineeringTask(
            task_id="val-004",
            description="Validate empty",
            study_types=[],
            parameters={"results": []},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["validation_summary"]["total_checks"] == 0

    @pytest.mark.asyncio
    async def test_standards_checked(self, agent):
        """Test 6: All expected standards are checked."""
        task = EngineeringTask(
            task_id="val-005",
            description="Check standards",
            study_types=[],
            parameters={"results": []},
        )
        result = await agent.execute(task)
        assert "voltage_limits" in result.data["standards_checked"]
        assert "frequency_hz" in result.data["standards_checked"]
