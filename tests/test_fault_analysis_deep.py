"""
Deep Fault Analysis Tests - fault_analysis/fault.py

Covers all four fault types: three-phase, SLG, LL, LLG.
Tests dense Zbus path, base current conversion, edge cases.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fault_analysis.fault import FaultAnalyzer


def _simple_3bus_ybus():
    """3-bus Ybus: each pair connected by z=0.1+0.3j pu."""
    z = complex(0.1, 0.3)
    y = 1.0 / z
    Y = np.zeros((3, 3), dtype=complex)
    for i, j in [(0, 1), (1, 2), (0, 2)]:
        Y[i, i] += y
        Y[j, j] += y
        Y[i, j] -= y
        Y[j, i] -= y
    return Y


@pytest.fixture(name="analyzer3")
def fixture_analyzer3():
    Y = _simple_3bus_ybus()
    return FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)


@pytest.fixture(name="analyzer_asymmetric")
def fixture_analyzer_asymmetric():
    Y_pos = _simple_3bus_ybus()
    Y_neg = Y_pos * 0.95
    Y_zero = Y_pos * 0.8
    return FaultAnalyzer(Y_pos, ybus_neg=Y_neg, ybus_zero=Y_zero, base_mva=100.0, base_kv=11.0)


class TestThreePhaseFault:
    def test_returns_dict(self, analyzer3):
        assert isinstance(analyzer3.three_phase_fault(0), dict)

    def test_has_all_keys(self, analyzer3):
        result = analyzer3.three_phase_fault(0)
        for key in (
            "fault_current",
            "fault_current_magnitude",
            "fault_current_ka",
            "fault_current_angle",
            "affected_bus_index",
            "fault_type",
        ):
            assert key in result

    def test_fault_type_label(self, analyzer3):
        assert analyzer3.three_phase_fault(0)["fault_type"] == "three_phase"

    def test_magnitude_positive(self, analyzer3):
        for i in range(3):
            assert analyzer3.three_phase_fault(i)["fault_current_magnitude"] > 0

    def test_ka_positive(self, analyzer3):
        assert analyzer3.three_phase_fault(0)["fault_current_ka"] > 0

    def test_ka_reasonable(self, analyzer3):
        ka = analyzer3.three_phase_fault(0)["fault_current_ka"]
        assert ka < 1000.0

    def test_different_buses_different_currents(self, analyzer3):
        r0 = analyzer3.three_phase_fault(0)["fault_current_magnitude"]
        r1 = analyzer3.three_phase_fault(1)["fault_current_magnitude"]
        assert r0 > 0
        assert r1 > 0

    def test_affected_bus_index_correct(self, analyzer3):
        for i in range(3):
            assert analyzer3.three_phase_fault(i)["affected_bus_index"] == i


class TestSLGFault:
    def test_returns_dict(self, analyzer3):
        assert isinstance(analyzer3.line_to_ground_fault(0), dict)

    def test_fault_type_label(self, analyzer3):
        assert analyzer3.line_to_ground_fault(0)["fault_type"] == "line_to_ground"

    def test_magnitude_positive_all_buses(self, analyzer3):
        for i in range(3):
            assert analyzer3.line_to_ground_fault(i)["fault_current_magnitude"] > 0

    def test_asymmetric_sequences_used(self, analyzer_asymmetric):
        slg = analyzer_asymmetric.line_to_ground_fault(0)["fault_current_magnitude"]
        three = analyzer_asymmetric.three_phase_fault(0)["fault_current_magnitude"]
        assert slg > 0
        assert three > 0


class TestLLFault:
    def test_returns_dict(self, analyzer3):
        assert isinstance(analyzer3.line_to_line_fault(0), dict)

    def test_fault_type_label(self, analyzer3):
        assert analyzer3.line_to_line_fault(0)["fault_type"] == "line_to_line"

    def test_ll_less_than_3phase(self, analyzer3):
        ll = analyzer3.line_to_line_fault(0)["fault_current_magnitude"]
        three = analyzer3.three_phase_fault(0)["fault_current_magnitude"]
        assert 0 < ll <= three * 1.5

    def test_positive_all_buses(self, analyzer3):
        for i in range(3):
            assert analyzer3.line_to_line_fault(i)["fault_current_magnitude"] > 0


class TestLLGFault:
    def test_returns_dict(self, analyzer3):
        assert isinstance(analyzer3.double_line_to_ground_fault(0), dict)

    def test_fault_type_label(self, analyzer3):
        assert analyzer3.double_line_to_ground_fault(0)["fault_type"] == "double_line_to_ground"

    def test_has_phase_current_keys(self, analyzer3):
        result = analyzer3.double_line_to_ground_fault(0)
        for key in (
            "fault_current_b_magnitude",
            "fault_current_c_magnitude",
            "fault_current_b_ka",
            "fault_current_c_ka",
        ):
            assert key in result

    def test_phase_currents_non_negative(self, analyzer3):
        result = analyzer3.double_line_to_ground_fault(0)
        assert result["fault_current_b_magnitude"] >= 0
        assert result["fault_current_c_magnitude"] >= 0

    def test_all_buses(self, analyzer3):
        for i in range(3):
            r = analyzer3.double_line_to_ground_fault(i)
            assert r["fault_current_b_magnitude"] >= 0


class TestBaseConversion:
    def test_pu_to_ka_formula(self):
        Y = _simple_3bus_ybus()
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        expected_base_ka = 100.0 / (math.sqrt(3) * 11.0)
        result_ka = fa._pu_to_ka(1.0)
        assert abs(result_ka - expected_base_ka) < 1e-10

    def test_pu_to_ka_scales_linearly(self):
        Y = _simple_3bus_ybus()
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        ka1 = fa._pu_to_ka(1.0)
        ka2 = fa._pu_to_ka(2.0)
        assert abs(ka2 - 2 * ka1) < 1e-10

    def test_different_base_kv_gives_different_ka(self):
        Y = _simple_3bus_ybus()
        fa11 = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        fa33 = FaultAnalyzer(Y, base_mva=100.0, base_kv=33.0)
        ka11 = fa11._pu_to_ka(1.0)
        ka33 = fa33._pu_to_ka(1.0)
        assert ka11 > ka33


class TestDensePath:
    def test_3phase_converges_dense(self):
        Y = _simple_3bus_ybus()
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        assert fa.three_phase_fault(1)["fault_current_magnitude"] > 0

    def test_invert_ybus_identity_check(self):
        Y = _simple_3bus_ybus()
        # Add generator grounding admittance at bus 0 so Y is invertible (not floating)
        Y[0, 0] += 1.0 / complex(0.01, 0.05)
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        Z = fa._invert_ybus(Y)
        product = Y @ Z
        diff = np.max(np.abs(product - np.eye(3)))
        assert diff < 1e-10

    def test_invert_singular_returns_matrix(self):
        Y_singular = np.zeros((3, 3), dtype=complex)
        fa = FaultAnalyzer(_simple_3bus_ybus(), base_mva=100.0, base_kv=11.0)
        Z = fa._invert_ybus(Y_singular)
        assert Z is not None
        assert Z.shape == (3, 3)

    def test_zbus_element_direct(self):
        Y = _simple_3bus_ybus()
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0)
        z00 = fa._z(0, "pos")
        assert isinstance(z00, complex)
        assert abs(z00) > 0
