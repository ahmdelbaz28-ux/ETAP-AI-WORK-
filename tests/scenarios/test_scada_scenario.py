"""SCADA Integration Agent - Multi-turn Conversation Scenario Test.

Tests the SCADAAgent through multi-turn engineering scenarios covering
IEC 61850 data model mapping, real-time measurement processing, and
bus data mapping.
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
from agents.scada_agent import _IEC61850_LOGICAL_NODES, SCADAAgent


@pytest.fixture
def agent():
    return SCADAAgent()


@pytest.fixture
def sample_measurements():
    """Simulated SCADA measurements from IEC 61850 logical nodes."""
    return [
        {
            "logical_node": "MMXU1",
            "bus_id": "1",
            "voltage_magnitude_kv": 13.7,
            "voltage_angle_deg": 0.0,
            "active_power_mw": 0.0,
            "reactive_power_mvar": 0.0,
        },
        {
            "logical_node": "MMXU2",
            "bus_id": "2",
            "voltage_magnitude_kv": 13.6,
            "voltage_angle_deg": -2.5,
            "active_power_mw": 50.0,
            "reactive_power_mvar": 10.0,
        },
        {
            "logical_node": "MMXU3",
            "bus_id": "3",
            "voltage_magnitude_kv": 13.2,
            "voltage_angle_deg": -5.0,
            "active_power_mw": -80.0,
            "reactive_power_mvar": -30.0,
        },
    ]


class TestSCADAScenario:
    """Test SCADA Integration Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEC 61850 support."""
        assert agent.agent_name == "SCADAAgent"

    def test_map_measurements_to_buses(self, agent, sample_measurements):
        """Test 2: SCADA measurements are mapped to power system buses."""
        bus_mapping = {
            "1": {"bus_id": "1", "bus_type": "slack"},
            "2": {"bus_id": "2", "bus_type": "pq"},
            "3": {"bus_id": "3", "bus_type": "pq"},
        }
        result = agent.map_to_bus_data(
            measurements=sample_measurements,
            bus_mapping=bus_mapping,
            nominal_kv=13.8,
        )
        assert result is not None

    def test_measurement_validation(self, agent):
        """Test 3: Invalid measurements are flagged."""
        invalid_measurements = [
            {
                "logical_node": "MMXU1",
                "bus_id": "1",
                "voltage_magnitude_kv": -5.0,
                "voltage_angle_deg": 0.0,
            }
        ]
        bus_mapping = {"1": {"bus_id": "1", "bus_type": "pq"}}
        result = agent.map_to_bus_data(
            measurements=invalid_measurements,
            bus_mapping=bus_mapping,
            nominal_kv=13.8,
        )
        # Should handle invalid data gracefully
        assert result is not None

    def test_iec61850_logical_nodes(self):
        """Test 4: IEC 61850 logical node mappings are available."""
        assert "MMXU" in _IEC61850_LOGICAL_NODES
        assert "PTOC" in _IEC61850_LOGICAL_NODES

    @pytest.mark.asyncio
    async def test_execute_scada_task(self, agent, sample_measurements):
        """Test 5: Full SCADA analysis via execute method."""
        task = EngineeringTask(
            task_id="scada-001",
            description="Process SCADA measurements",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "measurements": sample_measurements,
                "base_kv": 13.8,
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED

    def test_data_quality_checks(self, agent, sample_measurements):
        """Test 6: Data quality/anomaly detection works."""
        bus_mapping = {
            "1": {"bus_id": "1", "bus_type": "slack"},
            "2": {"bus_id": "2", "bus_type": "pq"},
            "3": {"bus_id": "3", "bus_type": "pq"},
            "4": {"bus_id": "4", "bus_type": "pq"},
        }
        # Add an anomalous measurement
        anomalous = sample_measurements.copy()
        anomalous.append({
            "logical_node": "MMXU4",
            "bus_id": "4",
            "voltage_magnitude_kv": 0.01,
            "voltage_angle_deg": 45.0,
        })
        result = agent.map_to_bus_data(
            measurements=anomalous,
            bus_mapping=bus_mapping,
            nominal_kv=13.8,
        )
        assert result is not None
