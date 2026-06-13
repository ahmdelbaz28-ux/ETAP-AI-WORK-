"""Harmonic Analysis Agent - Multi-turn Conversation Scenario Test.

Tests the HarmonicAnalysisAgent through multi-turn engineering scenarios covering
IEEE 519 compliance, THD/TDD analysis, resonance detection, and filter design.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    HarmonicAnalysisAgent,
    StudyType,
)


@pytest.fixture
def agent():
    return HarmonicAnalysisAgent()


class TestHarmonicScenario:
    """Test Harmonic Analysis Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEEE 519 standard."""
        assert agent.agent_name == "HarmonicAnalysisAgent"
        assert agent.standard == "IEEE 519-2022"
        assert agent.max_harmonic_order == 50

    @pytest.mark.asyncio
    async def test_missing_system_data(self, agent):
        """Test 2: Agent handles missing system data gracefully."""
        task = EngineeringTask(
            task_id="harm-001",
            description="Harmonic analysis with no system",
            study_types=[StudyType.HARMONIC_ANALYSIS],
            parameters={},  # No system data
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_validation_with_violations(self, agent):
        """Test 3: Validation flags IEEE 519 violations."""
        result = AgentResult(
            agent_name="HarmonicAnalysisAgent",
            study_type=StudyType.HARMONIC_ANALYSIS,
            status=AgentStatus.COMPLETED,
            data={
                "thd_voltage": 8.5,  # >5% IEEE 519 limit
                "tdd_current": 12.0,
                "resonance_detected": False,
                "resonance_frequencies": [],
                "compliance_status": "non_compliant",
                "violations": ["THD exceeds 5% limit at Bus 3"],
                "standard": "IEEE 519-2022",
            },
        )
        valid = agent.validate_result(result)
        assert not valid  # Has violations

    @pytest.mark.asyncio
    async def test_validation_without_violations(self, agent):
        """Test 4: Validation passes with compliant results."""
        result = AgentResult(
            agent_name="HarmonicAnalysisAgent",
            study_type=StudyType.HARMONIC_ANALYSIS,
            status=AgentStatus.COMPLETED,
            data={
                "thd_voltage": 3.2,
                "tdd_current": 4.5,
                "resonance_detected": False,
                "resonance_frequencies": [],
                "compliance_status": "compliant",
                "violations": [],
                "standard": "IEEE 519-2022",
            },
        )
        valid = agent.validate_result(result)
        assert valid

    @pytest.mark.asyncio
    async def test_resonance_detection_flag(self, agent):
        """Test 5: Resonance detection flag is properly reported."""
        result = AgentResult(
            agent_name="HarmonicAnalysisAgent",
            study_type=StudyType.HARMONIC_ANALYSIS,
            status=AgentStatus.COMPLETED,
            data={
                "thd_voltage": 6.0,
                "tdd_current": 5.0,
                "resonance_detected": True,
                "resonance_frequencies": [350.0, 720.0],
                "compliance_status": "non_compliant",
                "violations": ["Resonance near 7th harmonic (350 Hz)"],
                "standard": "IEEE 519-2022",
            },
        )
        valid = agent.validate_result(result)
        # Resonance + violations → not valid
        assert not valid
        assert result.data["resonance_detected"] is True

    @pytest.mark.asyncio
    async def test_max_harmonic_order_configurable(self, agent):
        """Test 6: Maximum harmonic order can be configured."""
        agent.max_harmonic_order = 100
        assert agent.max_harmonic_order == 100
