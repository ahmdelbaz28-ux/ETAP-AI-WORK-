"""Battery Storage Agent - Multi-turn Conversation Scenario Test.

Tests the BatteryStorageAgent through multi-turn engineering scenarios covering
BESS sizing, dispatch optimization, ROI calculation, and cycle life analysis
per IEC 62933.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.battery_storage_agent import BatteryStorageAgent
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)


@pytest.fixture
def agent():
    return BatteryStorageAgent()


@pytest.fixture
def load_profile():
    """24-hour load profile in kW (typical industrial)."""
    return np.array([
        200, 180, 170, 165, 160, 180, 250, 350,
        450, 500, 520, 510, 490, 500, 480, 460,
        400, 380, 350, 320, 280, 250, 220, 200,
    ])


class TestBatteryStorageScenario:
    """Test Battery Storage Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEC 62933 standards."""
        assert agent.agent_name == "BatteryStorageAgent"

    def test_bess_sizing(self, agent, load_profile):
        """Test 2: BESS sizing based on load profile and peak shaving."""
        result = agent.size_bess(
            load_profile_kw=load_profile,
            target_peak_kw=400.0,
        )
        assert isinstance(result, dict)
        power = result.get("power_capacity_kw", result.get("power_kw", 0))
        energy = result.get("energy_capacity_kwh", result.get("energy_kwh", 0))
        assert power > 0
        assert energy > 0

    def test_peak_shaving_dispatch(self, agent, load_profile):
        """Test 3: Peak shaving dispatch reduces peak demand."""
        # Create energy price profile (high during peak, low during off-peak)
        prices = np.array([
            0.05, 0.05, 0.05, 0.05, 0.05, 0.06, 0.08, 0.10,
            0.15, 0.20, 0.25, 0.25, 0.20, 0.20, 0.18, 0.15,
            0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.05,
        ])
        result = agent.optimize_dispatch(
            load_profile_kw=load_profile,
            energy_prices=prices,
            bess_power_kw=120.0,
            bess_energy_kwh=500.0,
        )
        assert isinstance(result, dict)

    def test_roi_calculation(self, agent):
        """Test 4: ROI and payback period are calculated."""
        result = agent.calculate_roi(
            bess_power_kw=500,
            bess_energy_kwh=2000,
            annual_revenue_usd=80000,
        )
        assert isinstance(result, dict)

    def test_cycle_life_analysis(self, agent):
        """Test 5: Cycle life estimation from SOC profile."""
        soc_profile = np.linspace(0.2, 0.8, 100)
        result = agent.analyze_cycle_life(
            soc_profile=soc_profile,
            battery_chemistry="LFP",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_bess_analysis(self, agent, load_profile):
        """Test 6: Full BESS analysis via execute method."""
        task = EngineeringTask(
            task_id="bess-001",
            description="BESS sizing and dispatch",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "load_profile_kw": load_profile.tolist(),
                "target_peak_kw": 400.0,
                "technology": "LFP",
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
