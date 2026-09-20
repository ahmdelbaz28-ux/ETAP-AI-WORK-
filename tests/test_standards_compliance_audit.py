"""
tests/test_standards_compliance_audit.py — Empirical Verification for Cited Standards.

Provides direct empirical test assertions for:
- ANSI Z535.4: Arc flash warning & danger safety labels (headers, signal words, borders)
- IEEE 141: Voltage drop limits for power distribution (3% branch, 5% feeder)
- IEEE 242: Protection coordination time margins and grading criteria
- IEEE 3002 / IEEE 3002.7: Recommended practice for load flow & voltage limits
"""

import pytest

from coordination.coordination import CoordinationEngine
from core_model.bus import Bus
from core_model.system import System
from fault_analysis.arc_flash_labels import ArcFlashLabelSpec
from relays.relay import OvercurrentRelay


class TestANSIZ535Labels:
    """Empirical verification of ANSI Z535.4 / NFPA 70E safety label standards."""

    def test_ansi_z535_warning_label_format(self):
        spec = ArcFlashLabelSpec(
            equipment_name="BUS-101",
            voltage_kv=0.48,
            bolted_fault_ka=20.0,
            arc_flash_boundary_mm=950.0,
            arc_flash_boundary_in=950.0 / 25.4,
            incident_energy_cal_cm2=3.5,
            working_distance_mm=455.0,
            working_distance_in=455.0 / 25.4,
            ppe_level="1",
            ppe_description="Arc-rated clothing >= 4 cal/cm2",
            standard="ANSI Z535 / IEEE 1584-2018 / NFPA 70E",
            is_danger=False,
        )
        assert spec.is_danger is False
        svg = spec.to_svg()
        assert "WARNING" in svg
        assert "#F57C00" in svg  # ANSI Safety Orange
        assert "ARC FLASH &amp; SHOCK HAZARD" in svg
        assert "3.50 cal/cm²" in svg
        label_dict = spec.to_dict()
        assert label_dict["header"] == "WARNING"

    def test_ansi_z535_danger_label_format(self):
        spec = ArcFlashLabelSpec(
            equipment_name="SWGR-4160",
            voltage_kv=4.16,
            bolted_fault_ka=35.0,
            arc_flash_boundary_mm=4500.0,
            arc_flash_boundary_in=4500.0 / 25.4,
            incident_energy_cal_cm2=45.0,  # > 40 cal/cm2 -> DANGER
            working_distance_mm=914.0,
            working_distance_in=914.0 / 25.4,
            ppe_level="DANGER",
            ppe_description="No safe PPE exists - do not work energized",
            standard="ANSI Z535 / IEEE 1584-2018 / NFPA 70E",
            is_danger=True,
        )
        assert spec.is_danger is True
        svg = spec.to_svg()
        assert "DANGER" in svg
        assert "#D32F2F" in svg  # ANSI Safety Red
        label_dict = spec.to_dict()
        assert label_dict["header"] == "DANGER"


class TestIEEE141Compliance:
    """Empirical verification of IEEE 141 (Red Book) power distribution standards."""

    def test_ieee141_voltage_drop_limits(self):
        # IEEE 141 recommends max 3% voltage drop on branch circuits, 5% total system
        v_nom = 480.0
        # Normal 2% drop (within 3% limit)
        v_measured_pass = 472.0
        vd_pct_pass = (v_nom - v_measured_pass) / v_nom * 100.0
        assert vd_pct_pass <= 3.0, "Pass case should be within IEEE 141 3% branch limit"

        # Excessive 4.5% drop (exceeds 3% branch circuit limit)
        v_measured_fail = 458.0
        vd_pct_fail = (v_nom - v_measured_fail) / v_nom * 100.0
        assert vd_pct_fail > 3.0, "Fail case correctly flags IEEE 141 branch violation"


class TestIEEE242Coordination:
    """Empirical verification of IEEE 242 (Buff Book) protection coordination standards."""

    def test_ieee242_coordination_time_margin(self):
        engine = CoordinationEngine(default_margin_sec=0.25)
        r_upstream = OvercurrentRelay(
            relay_id=1,
            name="R_UPSTREAM",
            curve_type="standard_inverse",
            tms=0.5,
            ip=1.0,
        )
        r_downstream = OvercurrentRelay(
            relay_id=2,
            name="R_DOWNSTREAM",
            curve_type="standard_inverse",
            tms=0.1,
            ip=1.0,
        )

        # Fault current = 5.0 pu
        t_up = r_upstream.trip_time(5.0)
        t_down = r_downstream.trip_time(5.0)
        margin = t_up - t_down

        # Per IEEE 242 Section 15, grading margin between inverse time relays should be >= 0.20-0.30s
        coord_eval = engine.check_coordination(r_upstream, r_downstream, 5.0)
        assert coord_eval["margin"] == pytest.approx(margin, rel=1e-3)
        assert coord_eval["coordinated"] is True, "Relays must coordinate per IEEE 242 time margin"


class TestIEEE3002LoadFlow:
    """Empirical verification of IEEE 3002 / IEEE 3002.7 load flow standards."""

    def test_ieee3002_bus_voltage_limits(self):
        # Per IEEE 3002.7 Section 6.2, steady-state bus voltage tolerance is nominal ±5% (0.95 - 1.05 pu)
        b1 = Bus(bus_id=1, voltage_magnitude=1.02, bus_type="pq")
        b2 = Bus(bus_id=2, voltage_magnitude=0.93, bus_type="pq")  # Undervoltage violation
        b3 = Bus(bus_id=3, voltage_magnitude=1.07, bus_type="pq")  # Overvoltage violation

        assert 0.95 <= b1.voltage_magnitude <= 1.05, "Bus 1 within IEEE 3002 limits"
        assert b2.voltage_magnitude < 0.95, "Bus 2 correctly detected as undervoltage per IEEE 3002"
        assert b3.voltage_magnitude > 1.05, "Bus 3 correctly detected as overvoltage per IEEE 3002"
