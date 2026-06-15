"""Cable Sizing Agent - Multi-turn Conversation Scenario Test.

Tests the CableSizingAgent through multi-turn engineering scenarios covering
IEC 60364 ampacity, voltage drop, short-circuit temperature, and cable
recommendation.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.cable_sizing_agent import CableSizingAgent
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)


@pytest.fixture
def agent():
    return CableSizingAgent()


class TestCableSizingScenario:
    """Test Cable Sizing Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEC standards."""
        assert agent.agent_name == "CableSizingAgent"
        assert "IEC 60364-5-52" in agent.standards

    def test_ampacity_calculation(self, agent):
        """Test 2: Ampacity is calculated for standard Cu cable."""
        result = agent.calculate_ampacity(
            cross_section_mm2=70,
            conductor_material="Cu",
            insulation="XLPE",
            installation_method="in_air",
            ambient_temp_C=30.0,
            n_circuits=1,
        )
        assert isinstance(result, dict)
        # 70mm² Cu in air at 30°C → ~278A base
        assert result["derated_ampacity_A"] > 0
        assert result["derated_ampacity_A"] <= 278.0

    def test_ampacity_derating_temperature(self, agent):
        """Test 3: Ampacity decreases with higher ambient temperature."""
        amp_30c = agent.calculate_ampacity(
            cross_section_mm2=70, conductor_material="Cu",
            ambient_temp_C=30.0,
        )
        amp_50c = agent.calculate_ampacity(
            cross_section_mm2=70, conductor_material="Cu",
            ambient_temp_C=50.0,
        )
        assert amp_50c["derated_ampacity_A"] < amp_30c["derated_ampacity_A"]

    def test_ampacity_derating_grouping(self, agent):
        """Test 4: Ampacity decreases with more circuits in group."""
        amp_1 = agent.calculate_ampacity(
            cross_section_mm2=70, conductor_material="Cu",
            n_circuits=1,
        )
        amp_4 = agent.calculate_ampacity(
            cross_section_mm2=70, conductor_material="Cu",
            n_circuits=4,
        )
        assert amp_4["derated_ampacity_A"] < amp_1["derated_ampacity_A"]

    def test_voltage_drop_calculation(self, agent):
        """Test 5: Voltage drop is calculated for AC 3-phase."""
        result = agent.calculate_voltage_drop(
            load_current_A=200,
            cable_length_m=100,
            cross_section_mm2=70,
            conductor_material="Cu",
            system_voltage_V=400,
            power_factor=0.85,
        )
        assert isinstance(result, dict)
        vd_pct = result.get("voltage_drop_percent",
                            result.get("voltage_drop_pct", 0))
        assert vd_pct > 0

    def test_voltage_drop_longer_cable(self, agent):
        """Test 6: Longer cable produces higher voltage drop."""
        vd_100 = agent.calculate_voltage_drop(
            load_current_A=200, cable_length_m=100,
            cross_section_mm2=70, conductor_material="Cu",
            system_voltage_V=400, power_factor=0.85,
        )
        vd_200 = agent.calculate_voltage_drop(
            load_current_A=200, cable_length_m=200,
            cross_section_mm2=70, conductor_material="Cu",
            system_voltage_V=400, power_factor=0.85,
        )
        pct_100 = vd_100.get("voltage_drop_percent",
                              vd_100.get("voltage_drop_pct", 0))
        pct_200 = vd_200.get("voltage_drop_percent",
                              vd_200.get("voltage_drop_pct", 0))
        assert pct_200 > pct_100

    @pytest.mark.asyncio
    async def test_execute_cable_sizing_task(self, agent):
        """Test 7: Full cable sizing via execute method."""
        task = EngineeringTask(
            task_id="cable-001",
            description="Size cable for motor feeder",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "design_current_A": 250,
                "cable_length_m": 150,
                "voltage_V": 400,
                "conductor_material": "Cu",
                "insulation": "XLPE",
                "installation_method": "in_air",
                "ambient_temp_C": 40.0,
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
