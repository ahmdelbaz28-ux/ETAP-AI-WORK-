"""Arc Flash Agent - Multi-turn Conversation Scenario Test.

Tests the arc flash analysis through multi-turn engineering scenarios covering
IEEE 1584 incident energy calculation, arc flash boundary, and PPE category.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, EngineeringTask, StudyType
from fault_analysis.arc_flash_engine import ArcFlashEngine, ElectrodeConfig


class TestArcFlashScenario:
    """Test Arc Flash analysis with multi-turn engineering scenarios."""

    def test_engine_initialization(self):
        """Test 1: ArcFlashEngine initializes correctly."""
        engine = ArcFlashEngine()
        # Removed redundant `assert engine is not None` (SonarCloud S5727).
        # Verify the engine exposes its public calculation method instead.
        assert callable(getattr(engine, "calculate_incident_energy", None))

    def test_incident_energy_calculation(self):
        """Test 2: Incident energy is calculated with valid parameters."""
        engine = ArcFlashEngine()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        # IEEE 1584 calculation with typical LV parameters
        E_final, E_full, E_reduced = engine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=30.0,
            arc_duration_sec=0.5,
            working_distance_mm=610,
            electrode_config=ElectrodeConfig.VCB,
        )
        # Incident energy should be positive (cal/cm²)
        assert E_final > 0
        assert E_full > 0
        assert E_reduced > 0

    def test_arc_flash_boundary(self):
        """Test 3: Arc flash boundary is calculated."""
        # Calculate boundary directly
        boundary = ArcFlashEngine.calculate_arc_flash_boundary(
            voltage_kv=0.48,
            bolted_fault_current_ka=30.0,
            arc_duration_sec=0.5,
            working_distance_mm=610,
            electrode_config=ElectrodeConfig.VCB,
        )
        assert boundary > 0

    def test_high_voltage_scenario(self):
        """Test 4: Arc flash analysis works at MV levels."""
        engine = ArcFlashEngine()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_final, _, _ = engine.calculate_incident_energy(
            voltage_kv=13.8,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.3,
            working_distance_mm=910,
            electrode_config=ElectrodeConfig.VCB,
        )
        assert E_final > 0

    def test_electrode_configurations(self):
        """Test 5: Different electrode configurations are supported."""
        configs = [
            ElectrodeConfig.VCB,
            ElectrodeConfig.VCBB,
            ElectrodeConfig.HCB,
            ElectrodeConfig.VOA,
            ElectrodeConfig.HOA,
        ]
        engine = ArcFlashEngine()
        for config in configs:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            E_final, _, _ = engine.calculate_incident_energy(
                voltage_kv=0.48,
                bolted_fault_current_ka=25.0,
                arc_duration_sec=0.2,
                working_distance_mm=610,
                electrode_config=config,
            )
            assert E_final > 0

    def test_longer_duration_higher_energy(self):
        """Test 6: Longer arc duration produces higher incident energy."""
        engine = ArcFlashEngine()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        _, E_short, _ = engine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=30.0,
            arc_duration_sec=0.1,
            working_distance_mm=610,
            electrode_config=ElectrodeConfig.VCB,
        )  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        _, E_long, _ = engine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=30.0,
            arc_duration_sec=1.0,
            working_distance_mm=610,
            electrode_config=ElectrodeConfig.VCB,
        )
        # Longer duration → higher energy
        assert E_long > E_short
