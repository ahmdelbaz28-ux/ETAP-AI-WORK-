"""
Test suite validating IEEE 1584-2018 ST benchmark cases and Arc Flash Labels.
"""

from __future__ import annotations

import pytest
import math

from fault_analysis.arc_flash_engine import ArcFlashEngine, ElectrodeConfig, EnclosureType
from fault_analysis.ieee1584_database import (
    IEEE_1584_ST_CASES,
    calculate_arcing_current_ieee1584,
    calculate_enclosure_correction_factor,
)
from fault_analysis.arc_flash_labels import ArcFlashLabelSpec


class TestIEEE1584STBenchmarks:
    """Validate standard ST test cases from IEEE 1584-2018 Annex D."""

    @pytest.mark.parametrize("case", IEEE_1584_ST_CASES)
    def test_st_case_execution(self, case):
        engine = ArcFlashEngine()
        res = engine.calculate(
            voltage_kv=case["voltage_kv"],
            bolted_fault_current_ka=case["bolted_fault_current_ka"],
            arc_duration_sec=case["arc_duration_sec"],
            working_distance_mm=case["working_distance_mm"],
            electrode_config=case["electrode_config"],
            enclosure_type=case["enclosure_type"],
        )

        # 1. Arc current should be in physical range
        min_i, max_i = case["expected_arc_current_range"]
        assert min_i <= res.arc_current_ka <= max_i, (
            f"Case {case['case_id']}: Arc current {res.arc_current_ka} kA outside [{min_i}, {max_i}]"
        )

        # 2. Incident energy must be within expected magnitude range
        min_e, max_e = case["expected_energy_cal_range"]
        assert min_e <= res.incident_energy_cal_cm2 <= max_e, (
            f"Case {case['case_id']}: Energy {res.incident_energy_cal_cm2} cal/cm2 outside [{min_e}, {max_e}]"
        )

        # 3. Arc flash boundary must be positive and proportional
        assert res.arc_flash_boundary_mm > 0.0
        assert res.arc_flash_boundary_in > 0.0


class TestArcFlashLabels:
    """Verify NFPA 70E Arc Flash Label generation."""

    def test_label_creation_warning(self):
        engine = ArcFlashEngine()
        calc_res = engine.calculate(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
        )
        label = ArcFlashLabelSpec.from_calculation_result(
            equipment_name="MCC-01 Main Bus",
            result=calc_res,
            upstream_device="CB-101",
        )
        assert label.equipment_name == "MCC-01 Main Bus"
        assert label.is_danger is False
        svg = label.to_svg()
        assert "WARNING" in svg
        assert "MCC-01 Main Bus" in svg
        assert "CB-101" in svg

    def test_label_creation_danger(self):
        engine = ArcFlashEngine()
        # High duration -> >40 cal/cm2
        calc_res = engine.calculate(
            voltage_kv=13.8,
            bolted_fault_current_ka=40.0,
            arc_duration_sec=8.0,
            working_distance_mm=457.0,
        )
        label = ArcFlashLabelSpec.from_calculation_result(
            equipment_name="SWG-13.8kV Bus A",
            result=calc_res,
        )
        assert label.is_danger is True
        svg = label.to_svg()
        assert "DANGER" in svg
