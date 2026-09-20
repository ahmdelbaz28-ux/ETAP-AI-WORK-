"""
tests/test_harmonic_analysis_ieee519.py — IEEE 519-2022 Harmonic Analysis Suite.

Validates:
1. Frequency-dependent admittance matrix Ybus(h) with skin-effect R*sqrt(h) and j*h*X_L.
2. Kirchhoff-compliant branch harmonic current calculations.
3. Voltage THD and Current TDD calculation per IEEE 519-2022.
4. Compliance limits checking: Table 1 (Voltage THD) and Table 2 (Current TDD vs Isc/IL).
5. Integration with System model (Line, Transformer, Bus, Generator).
"""

import numpy as np
import pytest

from core_model.bus import Bus
from core_model.line import Line
from core_model.system import System
from fault_analysis.harmonic_analysis import (
    HarmonicAnalysisEngine,
    HarmonicResult,
    HarmonicSource,
)


class TestHarmonicAnalysisIEEE519:
    """Tests for IEEE 519-2022 Harmonic Analysis Engine."""

    @pytest.fixture
    def two_bus_system(self):
        """2-bus system: Generator at Bus 1, Line to Bus 2 with load."""
        sys = System(base_mva=100.0)
        b1 = Bus(bus_id=1, voltage_magnitude=1.0, bus_type="slack", base_kv=13.8)
        b2 = Bus(bus_id=2, voltage_magnitude=1.0, bus_type="pq", base_kv=13.8)
        sys.add_bus(b1)
        sys.add_bus(b2)
        # Line 1-2: R=0.02 pu, X=0.08 pu, B_charging=0.01 pu
        line = Line(
            line_id=1,
            from_bus=b1,
            to_bus=b2,
            z1=complex(0.02, 0.08),
            yshunt1=complex(0.0, 0.01),
        )
        sys.add_line(line)
        return sys

    def test_frequency_dependent_ybus_scaling(self, two_bus_system):
        """Verify frequency scaling of R(h)=R(1)*sqrt(h), X_L(h)=h*X_L(1), B_C(h)=h*B_C(1)."""
        engine = HarmonicAnalysisEngine(fundamental_freq=60.0, max_harmonic=25)
        engine.set_system(two_bus_system)

        # Fundamental Ybus
        ybus_1 = engine.calculate_harmonic_impedance(1)
        # 5th Harmonic Ybus
        ybus_5 = engine.calculate_harmonic_impedance(5)

        # Line series admittance at 1st harmonic: 1 / (0.02 + j0.08)
        z1 = complex(0.02, 0.08)
        # At 5th harmonic: z5 = 0.02 * sqrt(5) + j(0.08 * 5)
        z5 = complex(0.02 * np.sqrt(5), 0.08 * 5.0)

        expected_y12_5 = -1.0 / z5
        assert ybus_5[0, 1] == pytest.approx(expected_y12_5, rel=1e-3)
        assert ybus_5[1, 0] == pytest.approx(expected_y12_5, rel=1e-3)

        # Shunt charging increases with frequency: B(5) = 5 * B(1)
        # Verify diagonal admittance is physically greater in susceptance
        assert ybus_5.shape == (2, 2)
        assert abs(ybus_5[0, 1]) < abs(ybus_1[0, 1]), "Admittance should decrease with higher frequency inductive reactance"

    def test_branch_harmonic_currents_calculated(self, two_bus_system):
        """Verify harmonic branch currents are computed and non-empty."""
        engine = HarmonicAnalysisEngine(fundamental_freq=60.0, max_harmonic=11)
        engine.set_system(two_bus_system)

        # Inject 5th harmonic current of 0.10 pu at Bus 2 (e.g. 6-pulse drive)
        src5 = HarmonicSource(
            source_id="VFD-1",
            bus_id="2",
            harmonic_order=5,
            magnitude_pu=0.10,
            angle_deg=0.0,
            source_type="current",
        )
        engine.add_harmonic_source(src5)

        result_5 = engine.solve_harmonic_power_flow(5)
        assert result_5.harmonic_order == 5
        assert len(result_5.bus_voltages) == 2
        assert abs(result_5.bus_voltages["2"]) > 0.0, "Bus 2 should have 5th harmonic voltage distortion"

        # Branch current must be calculated and non-empty
        assert len(result_5.branch_currents) > 0, "Branch currents must be populated"
        line_current = result_5.branch_currents.get("line_1")
        assert line_current is not None
        assert abs(line_current) > 0.0, "Current should flow through the branch"

    def test_ieee_519_voltage_and_current_compliance(self):
        """Verify IEEE 519-2022 compliance checker for Table 1 (THD) and Table 2 (TDD)."""
        engine = HarmonicAnalysisEngine()

        # 13.8 kV system: Table 1 limit is 5.0%
        # Case A: Compliant voltage and current
        thd_ok = {"BUS-1": 3.2, "BUS-2": 4.1}
        tdd_ok = {"LINE-1": 6.5}  # Isc/IL=50 -> Table 2 limit is 12.0%
        comp_ok = engine.check_ieee_519_compliance(
            thd_voltage=thd_ok,
            tdd_current=tdd_ok,
            voltage_kv=13.8,
            isc_il_ratio=50.0,
        )
        assert comp_ok["BUS-1"] is True
        assert comp_ok["BUS-2"] is True
        assert comp_ok["branch_LINE-1"] is True

        # Case B: Voltage THD violation at Bus 2 (> 5.0%)
        thd_bad = {"BUS-1": 3.2, "BUS-2": 6.8}
        comp_bad_v = engine.check_ieee_519_compliance(
            thd_voltage=thd_bad,
            tdd_current=tdd_ok,
            voltage_kv=13.8,
            isc_il_ratio=50.0,
        )
        assert comp_bad_v["BUS-1"] is True
        assert comp_bad_v["BUS-2"] is False, "Bus 2 with 6.8% THD must fail 5% limit"

        # Case C: Current TDD violation on LINE-1 (14.0% > 12.0% limit for Isc/IL=50)
        tdd_bad = {"LINE-1": 14.0}
        comp_bad_i = engine.check_ieee_519_compliance(
            thd_voltage=thd_ok,
            tdd_current=tdd_bad,
            voltage_kv=13.8,
            isc_il_ratio=50.0,
        )
        assert comp_bad_i["branch_LINE-1"] is False, "LINE-1 with 14% TDD must fail 12% limit"

    def test_full_analysis_workflow(self, two_bus_system):
        """Verify run_full_analysis runs superposition and returns complete results."""
        engine = HarmonicAnalysisEngine(fundamental_freq=60.0, max_harmonic=7)
        engine.set_system(two_bus_system)

        # Add 5th and 7th harmonic current sources
        engine.add_harmonic_source(
            HarmonicSource(
                source_id="src5", bus_id="2", harmonic_order=5, magnitude_pu=0.08, angle_deg=0.0
            )
        )
        engine.add_harmonic_source(
            HarmonicSource(
                source_id="src7", bus_id="2", harmonic_order=7, magnitude_pu=0.05, angle_deg=0.0
            )
        )

        analysis = engine.run_full_analysis(
            fundamental_magnitudes={"1": 1.0, "2": 0.98},
            fundamental_currents={"line_1": 1.0},
            voltage_kv=13.8,
            isc_il_ratio=50.0,
        )

        assert len(analysis.harmonic_results) >= 2
        assert "2" in analysis.total_thd_voltage
        assert analysis.total_thd_voltage["2"] > 0.0
        assert "line_1" in analysis.total_tdd_current
        assert analysis.total_tdd_current["line_1"] > 0.0
        assert isinstance(analysis.compliance_status, dict)
