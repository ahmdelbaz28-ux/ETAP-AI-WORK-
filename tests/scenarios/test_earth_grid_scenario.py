"""Earth Grid Agent - Multi-turn Conversation Scenario Test.

Tests the EarthGridAgent through multi-turn engineering scenarios covering
IEEE 80 mesh/step/touch voltage, allowable limits, and safety verification.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.earth_grid_agent import EarthGridAgent
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)


@pytest.fixture
def agent():
    return EarthGridAgent()


class TestEarthGridScenario:
    """Test Earth Grid Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEEE 80/81 standards."""
        assert agent.agent_name == "EarthGridAgent"
        assert "IEEE 80-2013" in agent.standards

    def test_surface_derating_factor(self, agent):
        """Test 2: Surface derating factor Cs is computed per IEEE 80."""
        Cs = agent._surface_derating_factor(
            rho_s=2000.0,
            rho_b=100.0,
            hs=0.1,
        )
        assert 0.0 < Cs <= 1.0

    def test_allowable_voltages(self, agent):
        """Test 3: Allowable touch and step voltages are computed."""
        result = agent._allowable_voltages(
            rho_s=2000.0,
            rho_b=100.0,
            hs=0.1,
            fault_duration_s=0.5,
            body_weight_kg=70.0,
        )
        assert "E_touch_allowable_V" in result
        assert "E_step_allowable_V" in result
        assert result["E_step_allowable_V"] > result["E_touch_allowable_V"]

    def test_allowable_voltages_longer_fault(self, agent):
        """Test 4: Longer fault duration reduces allowable voltages."""
        v_short = agent._allowable_voltages(
            rho_s=2000.0,
            rho_b=100.0,
            hs=0.1,
            fault_duration_s=0.3,
        )
        v_long = agent._allowable_voltages(
            rho_s=2000.0,
            rho_b=100.0,
            hs=0.1,
            fault_duration_s=1.0,
        )
        # Longer fault → lower allowable voltage
        assert v_long["E_touch_allowable_V"] < v_short["E_touch_allowable_V"]
        assert v_long["E_step_allowable_V"] < v_short["E_step_allowable_V"]

    @pytest.mark.asyncio
    async def test_execute_earth_grid_task(self, agent):
        """Test 5: Full earth grid analysis via execute method."""
        task = EngineeringTask(
            task_id="eg-001",
            description="Design earth grid for 132/11kV substation",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "grid_length_m": 100.0,
                "grid_width_m": 80.0,
                "soil_resistivity_ohm_m": 100.0,
                "fault_current_A": 10000.0,
                "fault_duration_s": 0.5,
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data is not None

    def test_higher_resistivity_higher_allowable(self, agent):
        """Test 6: Higher surface resistivity allows higher touch voltage."""
        v_low = agent._allowable_voltages(
            rho_s=500.0,
            rho_b=100.0,
            hs=0.1,
            fault_duration_s=0.5,
        )
        v_high = agent._allowable_voltages(
            rho_s=5000.0,
            rho_b=100.0,
            hs=0.1,
            fault_duration_s=0.5,
        )
        assert v_high["E_touch_allowable_V"] > v_low["E_touch_allowable_V"]
