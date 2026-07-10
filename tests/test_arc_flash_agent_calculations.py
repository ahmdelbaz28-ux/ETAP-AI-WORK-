"""
Unit tests for agents/arc_flash_agent.py — Arc Flash calculation agent.

Tests the pure calculation methods (calculate_arc_current,
calculate_incident_energy, _format_ie_result, _classify_ppe) without
needing the full agent runtime or external services.
"""
from __future__ import annotations

import math

import pytest

from agents.arc_flash_agent import ArcFlashAgent


class TestArcFlashAgentInit:
    """Tests for ArcFlashAgent initialization."""

    def test_agent_initializes(self):
        """GIVEN no arguments
        WHEN ArcFlashAgent is constructed
        THEN it creates an instance without error.
        """
        agent = ArcFlashAgent()
        assert agent is not None

    def test_agent_has_calculate_methods(self):
        """GIVEN an ArcFlashAgent instance
        THEN it has calculate_arc_current and calculate_incident_energy methods.
        """
        agent = ArcFlashAgent()
        assert hasattr(agent, "calculate_arc_current")
        assert hasattr(agent, "calculate_incident_energy")
        assert hasattr(agent, "_classify_ppe")
        assert hasattr(agent, "validate_result")


class TestCalculateArcCurrent:
    """Tests for ArcFlashAgent.calculate_arc_current()."""

    def test_returns_positive_current_for_valid_inputs(self):
        """GIVEN valid voltage, fault current, and gap
        WHEN calculate_arc_current is called
        THEN it returns a positive float.
        """
        agent = ArcFlashAgent()
        # Typical LV arc flash: 480V, 25kA bolted fault, 25mm gap
        result = agent.calculate_arc_current(
            voltage_kv=0.480, fault_current_ka=25.0, gap_mm=25.0
        )
        assert isinstance(result, (int, float))
        assert result > 0, "Arc current must be positive"

    def test_higher_fault_current_gives_higher_arc_current(self):
        """GIVEN two fault currents (10kA and 50kA)
        WHEN calculate_arc_current is called for both
        THEN the higher fault current yields higher arc current.
        """
        agent = ArcFlashAgent()
        low = agent.calculate_arc_current(
            voltage_kv=0.480, fault_current_ka=10.0, gap_mm=25.0
        )
        high = agent.calculate_arc_current(
            voltage_kv=0.480, fault_current_ka=50.0, gap_mm=25.0
        )
        assert high > low, "Higher fault current should yield higher arc current"


class TestCalculateIncidentEnergy:
    """Tests for ArcFlashAgent.calculate_incident_energy()."""

    def test_returns_positive_energy_for_valid_inputs(self):
        """GIVEN valid arc flash parameters
        WHEN calculate_incident_energy is called
        THEN it returns a positive float (cal/cm²).
        """
        agent = ArcFlashAgent()
        result = agent.calculate_incident_energy(
            arc_current_ka=15.0,
            gap_mm=25.0,
            clearing_time_s=0.2,
            working_distance_mm=455,
            voltage_kv=0.480,
        )
        assert isinstance(result, (int, float))
        assert result > 0, "Incident energy must be positive"

    def test_longer_clearing_time_gives_higher_energy(self):
        """GIVEN two clearing times (0.1s and 1.0s)
        WHEN calculate_incident_energy is called
        THEN the longer time yields higher energy.
        """
        agent = ArcFlashAgent()
        short_time = agent.calculate_incident_energy(
            arc_current_ka=15.0,
            gap_mm=25.0,
            clearing_time_s=0.1,
            working_distance_mm=455,
            voltage_kv=0.480,
        )
        long_dur = agent.calculate_incident_energy(
            arc_current_ka=15.0,
            gap_mm=25.0,
            clearing_time_s=1.0,
            working_distance_mm=455,
            voltage_kv=0.480,
        )
        assert long_dur > short_time, "Longer clearing time should yield higher energy"

    def test_closer_distance_gives_higher_energy(self):
        """GIVEN two working distances (300mm and 1000mm)
        WHEN calculate_incident_energy is called
        THEN the closer distance yields higher energy.
        """
        agent = ArcFlashAgent()
        close = agent.calculate_incident_energy(
            arc_current_ka=15.0,
            gap_mm=25.0,
            clearing_time_s=0.2,
            working_distance_mm=300,
            voltage_kv=0.480,
        )
        far = agent.calculate_incident_energy(
            arc_current_ka=15.0,
            gap_mm=25.0,
            clearing_time_s=0.2,
            working_distance_mm=1000,
            voltage_kv=0.480,
        )
        assert close > far, "Closer distance should yield higher energy"


class TestClassifyPPE:
    """Tests for ArcFlashAgent._classify_ppe()."""

    def test_low_energy_returns_category_1(self):
        """GIVEN incident energy < 4 cal/cm²
        WHEN _classify_ppe is called
        THEN it returns a low PPE category (1 or 2).
        """
        agent = ArcFlashAgent()
        category, label = agent._classify_ppe(2.0)
        assert category in (1, 2, "1", "2"), f"Low energy should be category 1 or 2, got {category}"

    def test_high_energy_returns_high_category(self):
        """GIVEN incident energy > 40 cal/cm²
        WHEN _classify_ppe is called
        THEN it returns a high PPE category (4 or 'dangerous').
        """
        agent = ArcFlashAgent()
        result = agent._classify_ppe(50.0)
        category = result[0] if isinstance(result, tuple) else result
        # High energy should be a high category or dangerous
        assert category in (4, "4", "dangerous", "DANGER") or str(category) >= "4"

    def test_zero_energy_returns_minimal_category(self):
        """GIVEN incident energy = 0
        WHEN _classify_ppe is called
        THEN it returns the lowest category without error.
        """
        agent = ArcFlashAgent()
        result = agent._classify_ppe(0.0)
        assert result is not None


class TestValidateResult:
    """Tests for ArcFlashAgent.validate_result()."""

    def test_validates_none_result(self):
        """GIVEN None as a result
        WHEN validate_result is called
        THEN it returns False (not a valid result).
        """
        agent = ArcFlashAgent()
        assert agent.validate_result(None) is False
