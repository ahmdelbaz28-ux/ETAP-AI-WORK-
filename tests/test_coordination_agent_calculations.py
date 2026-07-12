"""
Unit tests for agents/coordination_agent.py — Protection Coordination agent.

Tests the pure calculation methods (calculate_relay_operating_time,
verify_coordination, generate_tcc_data, analyze_selectivity) without
needing the full agent runtime.
"""
from __future__ import annotations

import pytest

from agents.coordination_agent import CoordinationAgent


class TestCoordinationAgentInit:
    """Tests for CoordinationAgent initialization."""

    def test_agent_initializes(self):
        """GIVEN no arguments
        WHEN CoordinationAgent is constructed
        THEN it creates an instance without error.
        """
        agent = CoordinationAgent()
        assert agent is not None

    def test_agent_has_calculation_methods(self):
        """GIVEN a CoordinationAgent instance
        THEN it has all expected calculation methods.
        """
        agent = CoordinationAgent()
        assert hasattr(agent, "calculate_relay_operating_time")
        assert hasattr(agent, "verify_coordination")
        assert hasattr(agent, "generate_tcc_data")
        assert hasattr(agent, "analyze_selectivity")
        assert hasattr(agent, "validate_result")


class TestCalculateRelayOperatingTime:
    """Tests for CoordinationAgent.calculate_relay_operating_time()."""

    def test_returns_positive_time_for_valid_inputs(self):
        """GIVEN valid relay parameters (IEC inverse curve)
        WHEN calculate_relay_operating_time is called
        THEN it returns a positive time in seconds.
        """
        agent = CoordinationAgent()
        # IEC Standard Inverse: TMS=0.1, pickup=100A, fault=1000A (10x pickup)
        result = agent.calculate_relay_operating_time(
            fault_current_a=1000.0,
            pickup_current_a=100.0,
            time_multiplier=0.1,
            curve_type="standard_inverse",
        )
        assert isinstance(result, dict)
        assert result["operating_time_s"] > 0, "Operating time must be positive"

    def test_higher_tms_gives_longer_time(self):
        """GIVEN two TMS values (0.1 and 0.5)
        WHEN calculate_relay_operating_time is called
        THEN the higher TMS yields longer operating time.
        """
        agent = CoordinationAgent()
        fast = agent.calculate_relay_operating_time(
            fault_current_a=1000.0,
            pickup_current_a=100.0,
            time_multiplier=0.1,
            curve_type="standard_inverse",
        )
        slow = agent.calculate_relay_operating_time(
            fault_current_a=1000.0,
            pickup_current_a=100.0,
            time_multiplier=0.5,
            curve_type="standard_inverse",
        )
        assert slow["operating_time_s"] > fast["operating_time_s"], "Higher TMS should yield longer operating time"

    def test_fault_below_pickup_returns_inf_or_large(self):
        """GIVEN a fault current below pickup
        WHEN calculate_relay_operating_time is called
        THEN it returns infinity or a very large value (relay doesn't trip).
        """
        agent = CoordinationAgent()
        result = agent.calculate_relay_operating_time(
            fault_current_a=50.0,  # Below pickup of 100A
            pickup_current_a=100.0,
            time_multiplier=0.1,
            curve_type="standard_inverse",
        )
        # Relay should not operate — result should be inf or very large
        assert result["operating_time_s"] == float("inf") or result["operating_time_s"] > 1000, f"Below-pickup fault should not trip, got {result}"


class TestVerifyCoordination:
    """Tests for CoordinationAgent.verify_coordination()."""

    def test_well_coordinated_relays_pass(self):
        """GIVEN upstream and downstream relays with coordinated settings
        WHEN verify_coordination is called
        THEN it returns coordinated=True.
        """
        agent = CoordinationAgent()
        upstream_relay = {
            "pickup_current_a": 100.0,
            "time_multiplier": 0.5,
            "curve_type": "standard_inverse",
        }
        downstream_relay = {
            "pickup_current_a": 100.0,
            "time_multiplier": 0.1,
            "curve_type": "standard_inverse",
        }
        result = agent.verify_coordination(
            upstream_relay=upstream_relay,
            downstream_relay=downstream_relay,
            fault_current_a=1000.0,
        )
        assert result.get("coordinated") is True

    def test_tight_coordination_fails(self):
        """GIVEN upstream and downstream relays with close settings
        WHEN verify_coordination is called
        THEN it returns coordinated=False (insufficient margin).
        """
        agent = CoordinationAgent()
        upstream_relay = {
            "pickup_current_a": 100.0,
            "time_multiplier": 0.1,
            "curve_type": "standard_inverse",
        }
        downstream_relay = {
            "pickup_current_a": 100.0,
            "time_multiplier": 0.1,
            "curve_type": "standard_inverse",
        }
        result = agent.verify_coordination(
            upstream_relay=upstream_relay,
            downstream_relay=downstream_relay,
            fault_current_a=1000.0,
        )
        assert result.get("coordinated") is False


class TestGenerateTccData:
    """Tests for CoordinationAgent.generate_tcc_data()."""

    def test_generates_points_across_current_range(self):
        """GIVEN relay parameters
        WHEN generate_tcc_data is called
        THEN it returns a dict with TCC points.
        """
        agent = CoordinationAgent()
        result = agent.generate_tcc_data(
            pickup_current_a=100.0,
            time_multiplier=0.1,
            curve_type="standard_inverse",
            min_multiplier=1.5,
            max_multiplier=40.0,
            num_points=20,
        )
        assert isinstance(result, dict)
        assert "current_a" in result
        assert "time_s" in result
        assert len(result["current_a"]) == 20
        assert len(result["time_s"]) == 20

    def test_tcc_times_decrease_with_higher_current(self):
        """GIVEN a TCC curve
        WHEN generate_tcc_data produces points
        THEN higher currents yield shorter times (inverse curve).
        """
        agent = CoordinationAgent()
        result = agent.generate_tcc_data(
            pickup_current_a=100.0,
            time_multiplier=0.1,
            curve_type="standard_inverse",
            min_multiplier=1.5,
            max_multiplier=40.0,
            num_points=10,
        )
        assert isinstance(result, dict)
        low_current_time = result["time_s"][0]
        high_current_time = result["time_s"][-1]
        assert high_current_time < low_current_time, "Inverse curve: higher current → shorter time"


class TestAnalyzeSelectivity:
    """Tests for CoordinationAgent.analyze_selectivity()."""

    def test_returns_result_dict(self):
        """GIVEN a relay chain and fault currents
        WHEN analyze_selectivity is called
        THEN it returns a dict with selectivity analysis.
        """
        agent = CoordinationAgent()
        relay_chain = [
            {"name": "R1", "pickup_current_a": 100.0, "time_multiplier": 0.1, "curve_type": "standard_inverse"},
            {"name": "R2", "pickup_current_a": 200.0, "time_multiplier": 0.2, "curve_type": "standard_inverse"},
        ]
        result = agent.analyze_selectivity(
            relay_chain=relay_chain,
            fault_currents_a=[500.0, 1000.0, 2000.0],
        )
        assert result is not None
        assert isinstance(result, dict)


class TestValidateResult:
    """Tests for CoordinationAgent.validate_result()."""

    def test_validates_none_result(self):
        """GIVEN None as a result
        WHEN validate_result is called
        THEN it returns False.
        """
        agent = CoordinationAgent()
        assert agent.validate_result(None) is False
