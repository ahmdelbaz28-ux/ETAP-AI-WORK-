"""
Test suite validating IEEE 1584-2018 ST benchmark cases and Arc Flash Labels.
"""

from __future__ import annotations

import json
import os

import pytest

from fault_analysis.arc_flash_engine import ArcFlashEngine
from fault_analysis.arc_flash_labels import ArcFlashLabelSpec

GOLD_CASES_DIR = os.path.join(os.path.dirname(__file__), "gold_cases")
ST_GOLD_FILE = os.path.join(GOLD_CASES_DIR, "ieee1584_st_published.json")

with open(ST_GOLD_FILE, encoding="utf-8") as _f:
    PUBLISHED_ST_CASES = json.load(_f)


class TestIEEE1584STBenchmarks:
    """Validate standard ST test cases from IEEE 1584-2018 Annex D against published values."""

    @pytest.mark.parametrize("case", PUBLISHED_ST_CASES)
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

        # 1. Full arc current must match published Annex D value within 5%
        pub_i = case["published_arc_current_ka"]
        assert abs(res.arc_current_ka - pub_i) / pub_i <= 0.05, (
            f"Case {case['case_id']}: Arc current {res.arc_current_ka} kA differs >5% from published {pub_i} kA"
        )

        # 2. Reduced arc current (VarCf) must match published reduced current within 5%
        pub_i_red = case["published_reduced_arc_current_ka"]
        assert abs(res.reduced_arc_current_ka - pub_i_red) / pub_i_red <= 0.05, (
            f"Case {case['case_id']}: Reduced current {res.reduced_arc_current_ka} kA differs >5% from published {pub_i_red} kA"
        )
        assert res.reduced_arc_current_ka < res.arc_current_ka, (
            f"Case {case['case_id']}: Reduced current must be strictly less than full arc current"
        )

        # 3. Incident energy must match published value within physical range
        pub_e = case["published_energy_cal_cm2"]
        assert abs(res.incident_energy_cal_cm2 - pub_e) / pub_e <= 0.15, (
            f"Case {case['case_id']}: Energy {res.incident_energy_cal_cm2} cal/cm2 differs >15% from published {pub_e}"
        )

        # 4. Arc flash boundary must be positive and proportional
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
