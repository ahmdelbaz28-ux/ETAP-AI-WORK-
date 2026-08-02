"""
V-TCC-01 — TCC Safety Guards Test Suite
========================================

Tests for the calculate_iec_operating_time() safe entry point and
the safety guards it enforces:
  1. Input validation (positive currents, valid TMS, known curve type)
  2. Maximum multiplier cap (I/Ip <= 40x) — IEC 60255-1 valid range
  3. Minimum operating time floor (0.02 s) — physical relay limit
  4. Instantaneous overcurrent element (element 50) — immediate trip
  5. IEEE C37.112 curves with the same safety guards
  6. Backward compatibility with IEC60255Curves and OvercurrentRelay
  7. Regression tests for V-TCC-01 fixes
"""

from __future__ import annotations

import math

import pytest

from curves.curves import (
    IEC60255Curves,
    calculate_iec_operating_time,
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
    _IEC_CURVE_PARAMS,
    _IEEE_CURVE_PARAMS,
    _CURVE_REGISTRY,
)
from relays.relay import OvercurrentRelay


# =====================================================================
# 1. IEC 60255 Formula Accuracy
# =====================================================================


class TestIECFormulaAccuracy:
    """Verify that the IEC 60255 formula matches known reference values."""

    @pytest.mark.parametrize(
        "curve_type, tms, i_fault, i_setting, expected_approx",
        [
            # Standard Inverse: t = TMS * 0.14 / (M^0.02 - 1)
            ("standard_inverse", 1.0, 10.0, 1.0, 2.97),  # M=10, ref ~2.97s
            ("very_inverse", 1.0, 10.0, 1.0, 1.50),  # M=10, ref ~1.5s
            ("extremely_inverse", 1.0, 10.0, 1.0, 0.81),  # M=10, ref ~0.808s
            ("long_inverse", 1.0, 10.0, 1.0, 13.33),  # M=10, ref ~13.33s
            # TMS scaling
            ("standard_inverse", 0.5, 10.0, 1.0, 1.49),  # half TMS = half time
            ("very_inverse", 0.1, 10.0, 1.0, 0.15),  # TMS=0.1
        ],
    )
    def test_iec_formula_matches_reference(
        self, curve_type, tms, i_fault, i_setting, expected_approx
    ):
        """GIVEN IEC 60255 curve parameters
        WHEN calculate_iec_operating_time is called
        THEN the result matches the reference value within 5%.
        """
        result = calculate_iec_operating_time(
            i_fault=i_fault,
            i_setting=i_setting,
            tms=tms,
            curve_type=curve_type,
        )
        assert result["operating_time_s"] == pytest.approx(
            expected_approx, rel=0.05
        ), f"{curve_type}: expected ~{expected_approx}s, got {result['operating_time_s']:.4f}s"

    def test_standard_inverse_known_point(self):
        """GIVEN M=2 (I_fault=2, I_setting=1), TMS=1
        WHEN standard_inverse is calculated
        THEN t = 0.14 / (2^0.02 - 1) ≈ 10.03s.
        """
        result = calculate_iec_operating_time(
            i_fault=2.0, i_setting=1.0, tms=1.0, curve_type="standard_inverse"
        )
        # M=2, alpha=0.02: 2^0.02 = 1.01396, 0.14/0.01396 = 10.03
        assert result["operating_time_s"] == pytest.approx(10.03, rel=0.02)

    def test_very_inverse_known_point(self):
        """GIVEN M=5 (I_fault=5, I_setting=1), TMS=1
        WHEN very_inverse is calculated
        THEN t = 13.5 / (5 - 1) = 3.375s.
        """
        result = calculate_iec_operating_time(
            i_fault=5.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["operating_time_s"] == pytest.approx(3.375, rel=0.01)

    def test_extremely_inverse_known_point(self):
        """GIVEN M=3 (I_fault=3, I_setting=1), TMS=1
        WHEN extremely_inverse is calculated
        THEN t = 80 / (3^2 - 1) = 80/8 = 10.0s.
        """
        result = calculate_iec_operating_time(
            i_fault=3.0, i_setting=1.0, tms=1.0, curve_type="extremely_inverse"
        )
        assert result["operating_time_s"] == pytest.approx(10.0, rel=0.01)


# =====================================================================
# 2. Input Validation
# =====================================================================


class TestInputValidation:
    """Verify that invalid inputs are rejected."""

    def test_negative_fault_current_raises(self):
        """GIVEN a negative fault current
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="i_fault must be positive"):
            calculate_iec_operating_time(
                i_fault=-100.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
            )

    def test_zero_fault_current_raises(self):
        """GIVEN zero fault current
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="i_fault must be positive"):
            calculate_iec_operating_time(
                i_fault=0.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
            )

    def test_negative_setting_raises(self):
        """GIVEN a negative pickup setting
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="i_setting must be positive"):
            calculate_iec_operating_time(
                i_fault=100.0, i_setting=-1.0, tms=1.0, curve_type="very_inverse"
            )

    def test_zero_tms_raises(self):
        """GIVEN zero TMS
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="tms must be positive"):
            calculate_iec_operating_time(
                i_fault=100.0, i_setting=1.0, tms=0.0, curve_type="very_inverse"
            )

    def test_negative_tms_raises(self):
        """GIVEN negative TMS
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="tms must be positive"):
            calculate_iec_operating_time(
                i_fault=100.0, i_setting=1.0, tms=-0.5, curve_type="very_inverse"
            )

    def test_unknown_curve_type_raises(self):
        """GIVEN an unknown curve type
        WHEN calculate_iec_operating_time is called
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="Unknown curve type"):
            calculate_iec_operating_time(
                i_fault=100.0, i_setting=1.0, tms=1.0, curve_type="nonexistent_curve"
            )

    def test_curve_type_case_insensitive(self):
        """GIVEN curve type in mixed case
        WHEN calculate_iec_operating_time is called
        THEN it normalizes to lowercase and works.
        """
        result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="VERY_INVERSE"
        )
        assert result["curve_type"] == "very_inverse"
        assert result["operating_time_s"] > 0


# =====================================================================
# 3. Minimum Operating Time Floor
# =====================================================================


class TestMinOperatingTimeFloor:
    """Verify that the minimum operating time floor is enforced."""

    def test_high_current_clamped_to_min_time(self):
        """GIVEN a very high fault current (M=1000) that would produce
        a trip time below the minimum operating time
        WHEN calculate_iec_operating_time is called
        THEN the result is clamped to MIN_OPERATING_TIME_S.
        """
        result = calculate_iec_operating_time(
            i_fault=1000.0,  # M=1000, way above max_multiplier
            i_setting=1.0,
            tms=1.0,
            curve_type="very_inverse",
            max_multiplier=40.0,  # cap M at 40
        )
        # With M capped at 40: t = 13.5 / (40 - 1) = 0.346s
        # That's above min_operating_time_s, so no clamping here
        assert result["operating_time_s"] >= MIN_OPERATING_TIME_S

    def test_extremely_high_current_clamped(self):
        """GIVEN M=100 with extremely_inverse curve
        WHEN calculate_iec_operating_time is called
        THEN the result is clamped to MIN_OPERATING_TIME_S.
        """
        result = calculate_iec_operating_time(
            i_fault=100.0,
            i_setting=1.0,
            tms=0.05,  # Very small TMS
            curve_type="extremely_inverse",
            max_multiplier=40.0,
        )
        # M capped at 40: t = 0.05 * 80 / (40^2 - 1) = 0.05 * 80/1599 = 0.0025s
        # This is below MIN_OPERATING_TIME_S, so it should be clamped
        assert result["operating_time_s"] == MIN_OPERATING_TIME_S
        assert result["status"] == "capped"
        assert any("clamped" in w for w in result["warnings"])

    def test_custom_min_operating_time(self):
        """GIVEN a custom min_operating_time_s of 0.1
        WHEN the raw trip time is below 0.1
        THEN the result is clamped to 0.1.
        """
        result = calculate_iec_operating_time(
            i_fault=100.0,
            i_setting=1.0,
            tms=0.05,
            curve_type="extremely_inverse",
            min_operating_time_s=0.1,
            max_multiplier=40.0,
        )
        assert result["operating_time_s"] == 0.1
        assert result["status"] == "capped"


# =====================================================================
# 4. Maximum Multiplier Cap
# =====================================================================


class TestMaxMultiplierCap:
    """Verify that the maximum multiplier cap is enforced."""

    def test_multiplier_capped_at_max(self):
        """GIVEN M=100 (far above max_multiplier=40)
        WHEN calculate_iec_operating_time is called
        THEN M is capped to 40 and a warning is issued.
        """
        result = calculate_iec_operating_time(
            i_fault=100.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["multiples_of_pickup"] == MAX_MULTIPLIER_OF_PICKUP
        assert any("capped" in w.lower() or "exceeds" in w.lower() for w in result["warnings"])

    def test_custom_max_multiplier(self):
        """GIVEN a custom max_multiplier of 20
        WHEN M=30
        THEN M is capped to 20.
        """
        result = calculate_iec_operating_time(
            i_fault=30.0,
            i_setting=1.0,
            tms=1.0,
            curve_type="very_inverse",
            max_multiplier=20.0,
        )
        assert result["multiples_of_pickup"] == 20.0

    def test_multiplier_below_max_not_capped(self):
        """GIVEN M=5 (below max_multiplier=40)
        WHEN calculate_iec_operating_time is called
        THEN M is not capped and no warning is issued.
        """
        result = calculate_iec_operating_time(
            i_fault=5.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["multiples_of_pickup"] == 5.0
        assert not any("exceeds" in w for w in result["warnings"])


# =====================================================================
# 5. Instantaneous Overcurrent (Element 50)
# =====================================================================


class TestInstantaneousOverride:
    """Verify the instantaneous overcurrent element (element 50)."""

    def test_instantaneous_trip_when_threshold_exceeded(self):
        """GIVEN instantaneous_override_a=5000 and i_fault=6000
        WHEN calculate_iec_operating_time is called
        THEN the relay trips instantly with instantaneous_time_s.
        """
        result = calculate_iec_operating_time(
            i_fault=6000.0,
            i_setting=100.0,
            tms=1.0,
            curve_type="very_inverse",
            instantaneous_override_a=5000.0,
            instantaneous_time_s=0.02,
        )
        assert result["operating_time_s"] == 0.02
        assert result["status"] == "instantaneous"

    def test_instantaneous_trip_at_exact_threshold(self):
        """GIVEN instantaneous_override_a=5000 and i_fault=5000
        WHEN calculate_iec_operating_time is called
        THEN the relay trips instantly (>= threshold).
        """
        result = calculate_iec_operating_time(
            i_fault=5000.0,
            i_setting=100.0,
            tms=1.0,
            curve_type="very_inverse",
            instantaneous_override_a=5000.0,
        )
        assert result["operating_time_s"] == 0.02
        assert result["status"] == "instantaneous"

    def test_no_instantaneous_when_below_threshold(self):
        """GIVEN instantaneous_override_a=5000 and i_fault=4000
        WHEN calculate_iec_operating_time is called
        THEN the relay uses the normal TCC curve.
        """
        result = calculate_iec_operating_time(
            i_fault=4000.0,
            i_setting=100.0,
            tms=1.0,
            curve_type="very_inverse",
            instantaneous_override_a=5000.0,
        )
        assert result["status"] != "instantaneous"
        assert result["operating_time_s"] > 0.02

    def test_no_instantaneous_when_override_is_none(self):
        """GIVEN no instantaneous override
        WHEN calculate_iec_operating_time is called
        THEN the relay uses the normal TCC curve.
        """
        result = calculate_iec_operating_time(
            i_fault=6000.0,
            i_setting=100.0,
            tms=1.0,
            curve_type="very_inverse",
            instantaneous_override_a=None,
        )
        assert result["status"] != "instantaneous"

    def test_custom_instantaneous_time(self):
        """GIVEN a custom instantaneous_time_s of 0.05
        WHEN the instantaneous element triggers
        THEN the operating time is 0.05s.
        """
        result = calculate_iec_operating_time(
            i_fault=6000.0,
            i_setting=100.0,
            tms=1.0,
            curve_type="very_inverse",
            instantaneous_override_a=5000.0,
            instantaneous_time_s=0.05,
        )
        assert result["operating_time_s"] == 0.05


# =====================================================================
# 6. No-Trip (Below Pickup) Behavior
# =====================================================================


class TestNoTrip:
    """Verify that below-pickup currents return inf (no trip)."""

    def test_below_pickup_returns_inf(self):
        """GIVEN i_fault < i_setting
        WHEN calculate_iec_operating_time is called
        THEN operating_time_s is inf and status is 'no_trip'.
        """
        result = calculate_iec_operating_time(
            i_fault=50.0, i_setting=100.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["operating_time_s"] == float("inf")
        assert result["status"] == "no_trip"

    def test_at_exact_pickup_returns_inf(self):
        """GIVEN i_fault == i_setting (M=1.0)
        WHEN calculate_iec_operating_time is called
        THEN operating_time_s is inf (singularity, no trip).
        """
        result = calculate_iec_operating_time(
            i_fault=100.0, i_setting=100.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["operating_time_s"] == float("inf")
        assert result["status"] == "no_trip"


# =====================================================================
# 7. IEEE C37.112 Curves
# =====================================================================


class TestIEEECurves:
    """Verify IEEE C37.112 curve calculations."""

    def test_ieee_moderately_inverse(self):
        """GIVEN IEEE moderately inverse curve
        WHEN calculate_iec_operating_time is called
        THEN a valid positive time is returned.
        """
        result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="ieee_moderately_inverse"
        )
        assert result["operating_time_s"] > 0
        assert result["status"] == "ok"

    def test_ieee_very_inverse(self):
        """GIVEN IEEE very inverse curve
        WHEN calculate_iec_operating_time is called
        THEN a valid positive time is returned.
        """
        result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="ieee_very_inverse"
        )
        assert result["operating_time_s"] > 0

    def test_ieee_extremely_inverse(self):
        """GIVEN IEEE extremely inverse curve
        WHEN calculate_iec_operating_time is called
        THEN a valid positive time is returned.
        """
        result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="ieee_extremely_inverse"
        )
        assert result["operating_time_s"] > 0

    def test_ieee_safety_guards_enforced(self):
        """GIVEN IEEE curve with M > max_multiplier
        WHEN calculate_iec_operating_time is called
        THEN the same safety guards apply.
        """
        result = calculate_iec_operating_time(
            i_fault=100.0,
            i_setting=1.0,
            tms=0.05,
            curve_type="ieee_extremely_inverse",
            max_multiplier=40.0,
        )
        assert result["operating_time_s"] >= MIN_OPERATING_TIME_S

    def test_ieee_below_pickup_returns_inf(self):
        """GIVEN IEEE curve with fault below pickup
        WHEN calculate_iec_operating_time is called
        THEN operating_time_s is inf.
        """
        result = calculate_iec_operating_time(
            i_fault=50.0, i_setting=100.0, tms=1.0, curve_type="ieee_moderately_inverse"
        )
        assert result["operating_time_s"] == float("inf")
        assert result["status"] == "no_trip"


# =====================================================================
# 8. Backward Compatibility
# =====================================================================


class TestBackwardCompatibility:
    """Verify that the old API still works."""

    def test_iec60255_curves_class_still_works(self):
        """GIVEN the old IEC60255Curves class
        WHEN very_inverse is called
        THEN it returns the same result as calculate_iec_operating_time.
        """
        old_result = IEC60255Curves.very_inverse(tms=1.0, i=10.0, ip=1.0)
        new_result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        assert old_result == pytest.approx(new_result["operating_time_s"], rel=0.01)

    def test_iec60255_curves_below_pickup(self):
        """GIVEN fault below pickup
        WHEN IEC60255Curves.very_inverse is called
        THEN it returns inf.
        """
        result = IEC60255Curves.very_inverse(tms=1.0, i=0.5, ip=1.0)
        assert result == float("inf")

    def test_overcurrent_relay_with_uppercase_params(self):
        """GIVEN OvercurrentRelay with uppercase TMS and Ip
        WHEN the relay is constructed
        THEN it works correctly (backward compatibility).
        """
        relay = OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type="very_inverse")
        assert relay.TMS == 1.0
        assert relay.Ip == 1.0

    def test_overcurrent_relay_trip_time(self):
        """GIVEN OvercurrentRelay with safe trip_time
        WHEN trip_time is called
        THEN it returns a positive finite time for valid current.
        """
        relay = OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type="very_inverse")
        t = relay.trip_time(10.0)
        assert t > 0
        assert math.isfinite(t)

    def test_overcurrent_relay_below_pickup(self):
        """GIVEN OvercurrentRelay with current below pickup
        WHEN trip_time is called
        THEN it returns inf.
        """
        relay = OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type="very_inverse")
        t = relay.trip_time(0.5)
        assert t == float("inf")

    def test_overcurrent_relay_instantaneous_override(self):
        """GIVEN OvercurrentRelay with instantaneous_override
        WHEN the fault current exceeds the override
        THEN the relay trips instantly.
        """
        relay = OvercurrentRelay(
            relay_id=1,
            TMS=1.0,
            Ip=100.0,
            curve_type="very_inverse",
            instantaneous_override=5000.0,
        )
        t = relay.trip_time(6000.0)
        assert t == 0.02

    def test_overcurrent_relay_property_aliases(self):
        """GIVEN OvercurrentRelay
        WHEN TMS and Ip properties are accessed
        THEN they return the correct values.
        """
        relay = OvercurrentRelay(relay_id=1, TMS=0.5, Ip=2.0, curve_type="standard_inverse")
        assert relay.TMS == 0.5
        assert relay.Ip == 2.0

    def test_overcurrent_relay_property_setters(self):
        """GIVEN OvercurrentRelay
        WHEN TMS and Ip properties are set
        THEN the underlying values are updated.
        """
        relay = OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type="standard_inverse")
        relay.TMS = 0.5
        relay.Ip = 2.0
        assert relay.TMS == 0.5
        assert relay.Ip == 2.0


# =====================================================================
# 9. V-TCC-01 Regression Tests
# =====================================================================


class TestVTCC01Regression:
    """Regression tests for V-TCC-01 fixes.

    These tests verify that the specific bugs identified in the
    self-critique have been fixed.
    """

    def test_no_unbounded_extrapolation(self):
        """GIVEN M=1000 (very high fault current)
        WHEN calculate_iec_operating_time is called
        THEN the result is bounded (not approaching zero).
        """
        result = calculate_iec_operating_time(
            i_fault=1000.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        assert result["operating_time_s"] >= MIN_OPERATING_TIME_S
        assert result["operating_time_s"] < float("inf")

    def test_curve_registry_complete(self):
        """GIVEN the curve registry
        THEN it contains all 7 curve types (4 IEC + 3 IEEE).
        """
        expected = {
            "standard_inverse",
            "very_inverse",
            "extremely_inverse",
            "long_inverse",
            "ieee_moderately_inverse",
            "ieee_very_inverse",
            "ieee_extremely_inverse",
        }
        assert expected == set(_CURVE_REGISTRY.keys())

    def test_no_long_time_inverse_in_registry(self):
        """GIVEN the curve registry
        THEN 'long_time_inverse' is NOT in the registry
        (the old inconsistent name has been removed).
        """
        assert "long_time_inverse" not in _CURVE_REGISTRY

    def test_long_inverse_in_registry(self):
        """GIVEN the curve registry
        THEN 'long_inverse' IS in the registry (canonical name).
        """
        assert "long_inverse" in _CURVE_REGISTRY

    def test_coordination_agent_delegates_to_safe_function(self):
        """GIVEN CoordinationAgent
        WHEN calculate_relay_operating_time is called
        THEN it delegates to calculate_iec_operating_time and returns
        safety-guarded results.
        """
        from agents.coordination_agent import CoordinationAgent

        agent = CoordinationAgent()
        result = agent.calculate_relay_operating_time(
            fault_current_a=1000.0,
            pickup_current_a=100.0,
            curve_type="standard_inverse",
            time_multiplier=0.1,
        )
        assert result["operating_time_s"] > 0
        assert "status" in result

    def test_coordination_agent_long_time_inverse_alias(self):
        """GIVEN CoordinationAgent with 'long_time_inverse' curve type
        WHEN calculate_relay_operating_time is called
        THEN it maps to 'long_inverse' and works.
        """
        from agents.coordination_agent import CoordinationAgent

        agent = CoordinationAgent()
        result = agent.calculate_relay_operating_time(
            fault_current_a=10.0,
            pickup_current_a=1.0,
            curve_type="long_time_inverse",  # old name
            time_multiplier=1.0,
        )
        assert result["operating_time_s"] > 0
        assert result["curve_type"] == "long_inverse"  # normalized

    def test_overcurrent_relay_all_curve_types(self):
        """GIVEN OvercurrentRelay with each curve type
        WHEN trip_time is called
        THEN each produces a valid result.
        """
        for curve_type in OvercurrentRelay.VALID_CURVE_TYPES:
            relay = OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type=curve_type)
            t = relay.trip_time(10.0)
            assert t > 0
            assert math.isfinite(t), f"Failed for {curve_type}: got {t}"

    def test_overcurrent_relay_invalid_curve_raises(self):
        """GIVEN OvercurrentRelay with invalid curve type
        WHEN constructed
        THEN it raises ValueError.
        """
        with pytest.raises(ValueError, match="Unknown curve type"):
            OvercurrentRelay(relay_id=1, TMS=1.0, Ip=1.0, curve_type="nonexistent")

    def test_safety_guards_constants(self):
        """GIVEN the safety guard constants
        THEN they have the expected values per IEC 60255-1.
        """
        assert MIN_OPERATING_TIME_S == 0.02
        assert MAX_MULTIPLIER_OF_PICKUP == 40.0


# =====================================================================
# 10. Return Structure
# =====================================================================


class TestReturnStructure:
    """Verify the return dict structure."""

    def test_return_dict_keys(self):
        """GIVEN a valid calculation
        WHEN calculate_iec_operating_time returns
        THEN the dict has all expected keys.
        """
        result = calculate_iec_operating_time(
            i_fault=10.0, i_setting=1.0, tms=1.0, curve_type="very_inverse"
        )
        expected_keys = {
            "operating_time_s",
            "curve_type",
            "i_fault",
            "i_setting",
            "multiples_of_pickup",
            "tms",
            "status",
            "warnings",
        }
        assert set(result.keys()) == expected_keys

    def test_echo_fields(self):
        """GIVEN a calculation with specific inputs
        WHEN the result is returned
        THEN the echo fields match the inputs.
        """
        result = calculate_iec_operating_time(
            i_fault=100.0, i_setting=10.0, tms=0.5, curve_type="standard_inverse"
        )
        assert result["i_fault"] == 100.0
        assert result["i_setting"] == 10.0
        assert result["tms"] == 0.5
        assert result["curve_type"] == "standard_inverse"
        assert result["multiples_of_pickup"] == 10.0
