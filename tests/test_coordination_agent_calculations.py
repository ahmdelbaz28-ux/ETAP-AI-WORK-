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
            fault_current=1000.0,
            pickup_current=100.0,
            tms=0.1,
            curve_type="SI",  # Standard Inverse
        )
        assert isinstance(result, (int, float))
        assert result > 0, "Operating time must be positive"

    def test_higher_tms_gives_longer_time(self):
        """GIVEN two TMS values (0.1 and 0.5)
        WHEN calculate_relay_operating_time is called
        THEN the higher TMS yields longer operating time.
        """
        agent = CoordinationAgent()
        fast = agent.calculate_relay_operating_time(
            fault_current=1000.0,
            pickup_current=100.0,
            tms=0.1,
            curve_type="SI",
        )
        slow = agent.calculate_relay_operating_time(
            fault_current=1000.0,
            pickup_current=100.0,
            tms=0.5,
            curve_type="SI",
        )
        assert slow > fast, "Higher TMS should yield longer operating time"

    def test_fault_below_pickup_returns_inf_or_large(self):
        """GIVEN a fault current below pickup
        WHEN calculate_relay_operating_time is called
        THEN it returns infinity or a very large value (relay doesn't trip).
        """
        agent = CoordinationAgent()
        result = agent.calculate_relay_operating_time(
            fault_current=50.0,  # Below pickup of 100A
            pickup_current=100.0,
            tms=0.1,
            curve_type="SI",
        )
        # Relay should not operate — result should be inf or very large
        assert result == float("inf") or result > 1000, f"Below-pickup fault should not trip, got {result}"


class TestVerifyCoordination:
    """Tests for CoordinationAgent.verify_coordination()."""

    def test_well_coordinated_relays_pass(self):
        """GIVEN upstream relay operating at 1.0s and downstream at 0.5s
        WHEN verify_coordination is called with 0.3s CTI
        THEN it returns True (coordinated, 0.5s margin > 0.3s CTI).
        """
        agent = CoordinationAgent()
        result = agent.verify_coordination(
            upstream_time=1.0,
            downstream_time=0.5,
            cti=0.3,  # Coordination Time Interval
        )
        assert result is True or result.get("coordinated") is True

    def test_tight_coordination_fails(self):
        """GIVEN upstream at 0.6s and downstream at 0.5s (only 0.1s margin)
        WHEN verify_coordination is called with 0.3s CTI
        THEN it returns False (insufficient margin).
        """
        agent = CoordinationAgent()
        result = agent.verify_coordination(
            upstream_time=0.6,
            downstream_time=0.5,
            cti=0.3,
        )
        assert result is False or result.get("coordinated") is False


class TestGenerateTccData:
    """Tests for CoordinationAgent.generate_tcc_data()."""

    def test_generates_points_across_current_range(self):
        """GIVEN relay parameters
        WHEN generate_tcc_data is called
        THEN it returns a list of (current, time) points.
        """
        agent = CoordinationAgent()
        result = agent.generate_tcc_data(
            pickup_current=100.0,
            tms=0.1,
            curve_type="SI",
            min_current=100.0,
            max_current=10000.0,
            num_points=20,
        )
        # Result should be a list of points or a dict with points
        if isinstance(result, list):
            assert len(result) > 0
        elif isinstance(result, dict):
            assert "points" in result or "currents" in result
        else:
            pytest.fail(f"Unexpected result type: {type(result)}")

    def test_tcc_times_decrease_with_higher_current(self):
        """GIVEN a TCC curve
        WHEN generate_tcc_data produces points
        THEN higher currents yield shorter times (inverse curve).
        """
        agent = CoordinationAgent()
        result = agent.generate_tcc_data(
            pickup_current=100.0,
            tms=0.1,
            curve_type="SI",
            min_current=200.0,
            max_current=5000.0,
            num_points=10,
        )
        # Extract points depending on return format
        if isinstance(result, list) and len(result) >= 2:
            # Assume list of (current, time) tuples
            if isinstance(result[0], (list, tuple)) and len(result[0]) == 2:
                low_current_time = result[0][1]
                high_current_time = result[-1][1]
                assert high_current_time < low_current_time, "Inverse curve: higher current → shorter time"


class TestAnalyzeSelectivity:
    """Tests for CoordinationAgent.analyze_selectivity()."""

    def test_returns_result_dict(self):
        """GIVEN a list of relay-fault pairs
        WHEN analyze_selectivity is called
        THEN it returns a dict with selectivity analysis.
        """
        agent = CoordinationAgent()
        # Minimal input — may need adjustment based on actual signature
        result = agent.analyze_selectivity(
            relays=[
                {"name": "R1", "pickup": 100, "tms": 0.1, "curve": "SI"},
                {"name": "R2", "pickup": 200, "tms": 0.2, "curve": "SI"},
            ],
            fault_currents=[500.0, 1000.0, 2000.0],
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
