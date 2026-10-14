"""Unit tests for physical units, dimensions, conversions, and boundary checks.

Validates core.units enhancements:
  - Custom unit definitions (pu, var, cal_cm2)
  - Expanded parameter dimensionality coverage (EXPECTED_DIMENSIONS)
  - Quantity parsing from strings, dicts, and Quantities
  - Quantity normalization to canonical SI/platform units and per-unit values
  - Cable sizing bridges (AWG <-> mm2, ft <-> m)
  - Authoritative SCADA control voltage envelope checks in api/approvals.py
  - Pre-flight physical unit dimension checks in services/study_executor.py
"""

from __future__ import annotations

import math

import pytest

from core.units import (
    AWG_TO_MM2,
    EXPECTED_DIMENSIONS,
    awg_to_mm2,
    deg_to_rad,
    ft_to_m,
    m_to_ft,
    mm2_to_nearest_awg,
    normalize_angle,
    normalize_quantity,
    parse_quantity,
    rad_to_deg,
    ureg,
    validate_parameter_dimension,
)


def test_pint_registry_custom_definitions():
    """Verify custom power system units are correctly registered and dimensionless/valid."""
    pu_q = ureg("1.05 pu")
    assert pu_q.magnitude == 1.05
    assert pu_q.dimensionless

    var_q = ureg("50 MVAr")
    assert var_q.magnitude == 50.0

    kvar_q = ureg("200 kvar")
    assert kvar_q.to("megavar").magnitude == 0.2

    cal_q = ureg("5.2 cal_cm2")
    assert cal_q.magnitude == 5.2


def test_parse_quantity_formats():
    """Verify parse_quantity supports strings, dicts, and Quantity instances."""
    # Strings
    q1 = parse_quantity("25.0 kA")
    assert q1 is not None and q1.magnitude == 25.0

    q2 = parse_quantity("120 V")
    assert q2 is not None and q2.to("kV").magnitude == 0.12

    q3 = parse_quantity("10 deg")
    assert q3 is not None and q3.magnitude == 10.0

    q4 = parse_quantity("1.05 pu")
    assert q4 is not None and q4.magnitude == 1.05

    # Dicts
    q_dict = parse_quantity({"value": 100, "unit": "MVA"})
    assert q_dict is not None and q_dict.magnitude == 100.0

    q_dict_angle = parse_quantity({"value": 30, "unit": "deg"})
    assert q_dict_angle is not None and q_dict_angle.magnitude == 30.0

    # Non-quantities return None
    assert parse_quantity(100) is None
    assert parse_quantity("not_a_number") is None
    assert parse_quantity({"foo": "bar"}) is None


def test_validate_parameter_dimension_matches():
    """Verify parameters match their expected dimensions."""
    # Voltage
    assert validate_parameter_dimension("base_kv", "13.8 kV")[0] is True
    assert validate_parameter_dimension("voltage_kv", "480 V")[0] is True
    assert validate_parameter_dimension("voltage_magnitude", "1.02 pu")[0] is True

    # Current
    assert validate_parameter_dimension("bolted_fault_current", "25 kA")[0] is True
    assert validate_parameter_dimension("current_ka", "1.2 kA")[0] is True
    assert validate_parameter_dimension("cable_ampacity", "200 A")[0] is True

    # Power
    assert validate_parameter_dimension("base_mva", "100 MVA")[0] is True
    assert validate_parameter_dimension("p_mw", "50 MW")[0] is True
    assert validate_parameter_dimension("q_mvar", "25 MVAr")[0] is True

    # Impedance
    assert validate_parameter_dimension("r1", "0.05 ohm")[0] is True
    assert validate_parameter_dimension("r1", "0.05 pu")[0] is True
    assert validate_parameter_dimension("line_impedance", "0.1 ohm")[0] is True

    # Angle
    assert validate_parameter_dimension("voltage_angle", "10 deg")[0] is True
    assert validate_parameter_dimension("phase_shift_deg", "30 deg")[0] is True

    # Frequency
    assert validate_parameter_dimension("frequency_hz", "50 Hz")[0] is True
    assert validate_parameter_dimension("frequency_hz", "60 Hz")[0] is True

    # Pure numeric values without unit always pass dimension check
    assert validate_parameter_dimension("base_mva", 100.0)[0] is True
    assert validate_parameter_dimension("bolted_fault_current", 25.0)[0] is True


def test_validate_parameter_dimension_mismatches_rejected():
    """Verify dimension mismatches return (False, error_details)."""
    # Seconds in MVA field
    valid, err = validate_parameter_dimension("base_mva", "100 s")
    assert valid is False
    assert "Dimension mismatch for parameter 'base_mva'" in str(err)

    # Volts in Current field
    valid, err = validate_parameter_dimension("bolted_fault_current", "120 V")
    assert valid is False
    assert "Dimension mismatch for parameter 'bolted_fault_current'" in str(err)

    # Amperes in Voltage field
    valid, err = validate_parameter_dimension("base_kv", "50 A")
    assert valid is False
    assert "Dimension mismatch for parameter 'base_kv'" in str(err)

    # MVA in Frequency field
    valid, err = validate_parameter_dimension("frequency_hz", "100 MVA")
    assert valid is False
    assert "Dimension mismatch for parameter 'frequency_hz'" in str(err)


def test_normalize_quantity_conversions():
    """Verify deterministic conversion to canonical platform units and per-unit."""
    # Voltage: canonical is kV
    v_can, v_pu = normalize_quantity("120 V", "voltage", base_val=0.48)
    assert pytest.approx(v_can, rel=1e-5) == 0.12  # 0.12 kV
    assert pytest.approx(v_pu, rel=1e-5) == 0.25  # 0.12 / 0.48 pu

    # Per-unit voltage input
    v_can2, v_pu2 = normalize_quantity("1.05 pu", "voltage", base_val=13.8)
    assert pytest.approx(v_can2, rel=1e-5) == 14.49  # 1.05 * 13.8 kV
    assert pytest.approx(v_pu2, rel=1e-5) == 1.05

    # Power: canonical is MW
    p_can, p_pu = normalize_quantity("500 kW", "power", base_val=100.0)
    assert pytest.approx(p_can, rel=1e-5) == 0.5  # 0.5 MW
    assert pytest.approx(p_pu, rel=1e-5) == 0.005  # 0.5 / 100

    # Reactive power: canonical is MVAr
    q_can, q_pu = normalize_quantity("250 kvar", "reactive_power", base_val=100.0)
    assert pytest.approx(q_can, rel=1e-5) == 0.25  # 0.25 MVAr
    assert pytest.approx(q_pu, rel=1e-5) == 0.0025

    # Current: canonical is kA
    i_can, _ = normalize_quantity("2500 A", "current")
    assert pytest.approx(i_can, rel=1e-5) == 2.5  # 2.5 kA

    # Angle: canonical is rad
    ang_rad, _ = normalize_quantity("10 deg", "angle")
    assert pytest.approx(ang_rad, rel=1e-5) == math.radians(10.0)


def test_angle_conversion_helpers():
    """Verify deg_to_rad, rad_to_deg, and normalize_angle helpers."""
    assert pytest.approx(deg_to_rad(180.0), rel=1e-5) == math.pi
    assert pytest.approx(rad_to_deg(math.pi), rel=1e-5) == 180.0

    assert pytest.approx(normalize_angle("45 deg", "rad"), rel=1e-5) == math.radians(45.0)
    assert pytest.approx(normalize_angle(f"{math.pi / 2} rad", "deg"), rel=1e-5) == 90.0


def test_cable_bridge_conversions():
    """Verify AWG to mm2 and feet to meters conversions."""
    assert awg_to_mm2("4/0 AWG") == 107.2
    assert awg_to_mm2("14 AWG") == 2.08
    assert awg_to_mm2("unknown_size") is None

    assert mm2_to_nearest_awg(95.0) == "4/0 AWG"
    assert mm2_to_nearest_awg(50.0) == "1/0 AWG"

    assert pytest.approx(ft_to_m(1000.0), rel=1e-5) == 304.8
    assert pytest.approx(m_to_ft(304.8), rel=1e-5) == 1000.0


def test_approvals_voltage_envelope_with_explicit_units():
    """Verify api/approvals.py voltage validation with explicit unit arguments."""
    from unittest.mock import Mock

    from api.approvals import _validate_control_action_authoritative

    # Case 1: 4.16 kV with explicit unit="kV" (must PASS, not be rejected as > 1.20 pu)
    action1 = Mock()
    action1.args = {
        "target": "bus_101",
        "action_type": "set_voltage_setpoint",
        "target_value": 4.16,
        "unit": "kV",
    }
    valid1, details1, _ = _validate_control_action_authoritative(action1)
    assert valid1 is True

    # Case 2: String with unit "4.16 kV" in target_value (must PASS)
    action2 = Mock()
    action2.args = {
        "target": "bus_101",
        "action_type": "set_voltage_setpoint",
        "target_value": "4.16 kV",
    }
    valid2, details2, _ = _validate_control_action_authoritative(action2)
    assert valid2 is True

    # Case 3: 1.05 pu with explicit unit="pu" (must PASS)
    action3 = Mock()
    action3.args = {
        "target": "bus_101",
        "action_type": "set_voltage_setpoint",
        "target_value": 1.05,
        "unit": "pu",
    }
    valid3, details3, _ = _validate_control_action_authoritative(action3)
    assert valid3 is True

    # Case 4: 1.5 pu with explicit unit="pu" (must FAIL: outside [0.80, 1.20])
    action4 = Mock()
    action4.args = {
        "target": "bus_101",
        "action_type": "set_voltage_setpoint",
        "target_value": 1.5,
        "unit": "pu",
    }
    valid4, details4, code4 = _validate_control_action_authoritative(action4)
    assert valid4 is False
    assert code4 == "ENVELOPE_VIOLATION"


def test_study_executor_pre_flight_units():
    """Verify _pre_flight_units detects dimension mismatches on system components."""
    from services.study_executor import StudyExecutor

    executor = StudyExecutor()

    # Valid system
    valid_system = {
        "base_mva": "100 MVA",
        "buses": [
            {"bus_id": "1", "base_kv": "13.8 kV", "voltage_magnitude": "1.0 pu", "voltage_angle": "0.0 deg"}
        ],
        "lines": [
            {"line_id": "L1", "r1": "0.05 ohm", "x1": "0.1 ohm"}
        ],
        "transformers": [
            {"transformer_id": "T1", "rating_mva": "25 MVA", "r1": "0.01 pu", "x1": "0.08 pu"}
        ],
        "loads": [
            {"load_id": "LD1", "p_mw": "10 MW", "q_mvar": "5 MVAr"}
        ],
        "generators": [
            {"generator_id": "G1", "mva_rating": "50 MVA", "p_mw": "40 MW", "voltage_setpoint": "1.02 pu"}
        ],
    }
    err = executor._pre_flight_units(valid_system)
    assert err is None

    # Mismatch in Bus base_kv (e.g. kA in kV field)
    invalid_bus_system = {
        "buses": [{"bus_id": "1", "base_kv": "25 kA"}]
    }
    err = executor._pre_flight_units(invalid_bus_system)
    assert err is not None
    assert "Bus 1 base_kv dimension mismatch" in err["error"]

    # Mismatch in Line r1 (e.g. Volts in impedance field)
    invalid_line_system = {
        "lines": [{"line_id": "L1", "r1": "120 V"}]
    }
    err = executor._pre_flight_units(invalid_line_system)
    assert err is not None
    assert "Line L1 parameter 'r1' dimension mismatch" in err["error"]

    # Mismatch in Load p_mw (e.g. Seconds in power field)
    invalid_load_system = {
        "loads": [{"load_id": "LD1", "p_mw": "100 s"}]
    }
    err = executor._pre_flight_units(invalid_load_system)
    assert err is not None
    assert "Load LD1 parameter 'p_mw' dimension mismatch" in err["error"]
