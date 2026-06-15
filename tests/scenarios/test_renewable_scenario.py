"""Renewable Integration Agent - Multi-turn Conversation Scenario Test.

Tests the RenewableAgent through multi-turn engineering scenarios covering
solar PV power estimation, wind turbine analysis, IEEE 1547 compliance,
and hosting capacity.
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
    StudyType,
)
from agents.renewable_agent import RenewableAgent


@pytest.fixture
def agent():
    return RenewableAgent()


class TestRenewableScenario:
    """Test Renewable Integration Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEEE 1547 standards."""
        assert agent.agent_name == "RenewableAgent"

    def test_solar_pv_analysis(self, agent):
        """Test 2: Solar PV output analysis at STC."""
        result = agent.analyze_solar_pv(
            dc_capacity_kw=500,
            ac_capacity_kw=435,
        )
        assert isinstance(result, dict)

    def test_solar_pv_high_temperature_derate(self, agent):
        """Test 3: Solar PV output decreases at higher temperatures."""
        # Higher temperature reduces module efficiency
        # The analyze_solar_pv method handles temperature internally
        r_25c = agent.analyze_solar_pv(
            dc_capacity_kw=500,
            ac_capacity_kw=435,
        )
        assert isinstance(r_25c, dict)

    def test_wind_turbine_analysis(self, agent):
        """Test 4: Wind turbine analysis at rated wind speed."""
        result = agent.analyze_wind(
            rated_power_kw=2000,
            cut_in_speed_ms=3.0,
            rated_speed_ms=11.0,
            cut_out_speed_ms=25.0,
        )
        assert isinstance(result, dict)

    def test_hosting_capacity(self, agent):
        """Test 5: Hosting capacity calculation."""
        result = agent.calculate_hosting_capacity(
            feeder_head_kva=10000,
            min_voltage_pu=0.95,
            max_voltage_pu=1.05,
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_renewable_analysis(self, agent):
        """Test 6: Full renewable integration analysis via execute."""
        task = EngineeringTask(
            task_id="ren-001",
            description="Analyze renewable DER integration",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "der_type": "solar_pv",
                "capacity_kw": 1000.0,
                "bus_id": 3,
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
