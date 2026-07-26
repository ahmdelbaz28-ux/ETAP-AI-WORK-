"""
Tests for relays module — OvercurrentRelay, DistanceRelay, DifferentialRelay, DirectionalRelay.
"""

import math

import numpy as np
import pytest

from relays.relay import (
    DifferentialRelay,
    DirectionalRelay,
    DistanceRelay,
    OvercurrentRelay,
    Relay,
)

# ===========================================================================
# Base Relay
# ===========================================================================


class TestRelay:
    def test_default_pickup_is_false(self):
        r = Relay(relay_id=1)
        assert r.pickup is False
        assert r.trip is False

    def test_operate_doesnt_trip_by_default(self):
        r = Relay(relay_id=1)
        result = r.operate(5.0)
        assert result is False
        assert r.pickup is False

    def test_trip_time_inf_by_default(self):
        r = Relay(relay_id=1)
        assert r.trip_time(5.0) == float("inf")

    def test_name_default(self):
        r = Relay(relay_id=42)
        assert r.name == "Relay"


# ===========================================================================
# OvercurrentRelay
# ===========================================================================


class TestOvercurrentRelay:
    def test_pickup_below_threshold(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(0.5) is False

    def test_pickup_at_threshold(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(1.0) is True

    def test_pickup_above_threshold(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(2.0) is True

    def test_pickup_negative_current(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(-2.0) is True

    def test_trip_time_below_pickup(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.trip_time(0.5) == float("inf")

    def test_trip_time_standard_inverse(self):
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        t = r.trip_time(5.0)
        assert t > 0
        assert math.isfinite(t)

    def test_trip_time_very_inverse(self):
        r = OvercurrentRelay(relay_id=1, curve_type="very_inverse", TMS=0.5, Ip=1.0)
        t = r.trip_time(5.0)
        assert t > 0
        assert math.isfinite(t)

    def test_trip_time_extremely_inverse(self):
        r = OvercurrentRelay(relay_id=1, curve_type="extremely_inverse", TMS=0.3, Ip=1.0)
        t = r.trip_time(10.0)
        assert t > 0
        assert math.isfinite(t)

    def test_trip_time_long_inverse(self):
        r = OvercurrentRelay(relay_id=1, curve_type="long_inverse", TMS=0.2, Ip=1.0)
        t = r.trip_time(3.0)
        assert t > 0
        assert math.isfinite(t)

    def test_trip_time_decreases_with_higher_current(self):
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        t_low = r.trip_time(2.0)
        t_high = r.trip_time(10.0)
        assert t_high < t_low

    def test_trip_time_increases_with_tms(self):
        r1 = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=0.5, Ip=1.0)
        r2 = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=2.0, Ip=1.0)
        assert r2.trip_time(5.0) > r1.trip_time(5.0)

    def test_unknown_curve_raises(self):
        r = OvercurrentRelay(relay_id=1, curve_type="invalid_curve", TMS=1.0, Ip=1.0)
        with pytest.raises(ValueError, match="Unknown curve type"):
            r.trip_time(5.0)

    def test_operate_doesnt_trip_without_enough_time(self):
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        result = r.operate(5.0, t=0.0)
        assert result is False

    def test_operate_trips_with_sufficient_time(self):
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=0.1, Ip=1.0)
        result = r.operate(10.0, t=100.0)
        assert result is True

    def test_operate_resets_trip(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        r.trip = True
        result = r.operate(0.5, t=0.0)
        assert result is False
        assert r.trip is False

    def test_complex_current_pickup(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(complex(0.8, 0.6)) is True

    def test_complex_current_no_pickup(self):
        r = OvercurrentRelay(relay_id=1, Ip=1.0)
        assert r.pickup_logic(complex(0.5, 0.5)) is False

    def test_default_name(self):
        r = OvercurrentRelay(relay_id=5)
        assert r.name == "OvercurrentRelay"

    def test_curve_property(self):
        r = OvercurrentRelay(relay_id=1, curve_type="very_inverse")
        assert r.curve_type == "very_inverse"

    def test_tms_property(self):
        r = OvercurrentRelay(relay_id=1, TMS=0.75)
        assert pytest.approx(0.75) == r.TMS

    def test_ip_property(self):
        r = OvercurrentRelay(relay_id=1, Ip=0.8)
        assert r.Ip == pytest.approx(0.8)


# ===========================================================================
# DistanceRelay
# ===========================================================================


class TestDistanceRelay:
    def test_pickup_within_zone(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0)
        I = complex(3.0, 0)
        assert r.pickup_logic(V, I) is True

    def test_no_pickup_outside_zone(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0)
        I = complex(1.0, 0)
        assert r.pickup_logic(V, I) is False

    def test_no_pickup_zero_current(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0)
        I = complex(0, 0)
        assert r.pickup_logic(V, I) is False

    def test_operate_trips_when_picked_up(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0)
        I = complex(3.0, 0)
        result = r.operate(V, I)
        assert result is True
        assert r.trip is True

    def test_operate_no_trip_outside_zone(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0)
        I = complex(1.0, 0)
        result = r.operate(V, I)
        assert result is False
        assert r.trip is False

    def test_complex_impedance(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5)
        V = complex(1.0, 0.1)
        I = complex(2.0, 0.5)
        assert r.pickup_logic(V, I) is True

    def test_offset_angle(self):
        r = DistanceRelay(relay_id=1, impedance_setting=0.5, offset_angle=30)
        assert r.offset_angle == pytest.approx(np.radians(30))

    def test_default_name(self):
        r = DistanceRelay(relay_id=1)
        assert r.name == "DistanceRelay"


# ===========================================================================
# DifferentialRelay
# ===========================================================================


class TestDifferentialRelay:
    def test_no_pickup_balanced(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        assert r.pickup_logic(Ibias=1.0, Idiff=0.05) is False

    def test_pickup_high_differential(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        assert r.pickup_logic(Ibias=1.0, Idiff=0.5) is True

    def test_pickup_slope1_region(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        assert r.pickup_logic(Ibias=1.0, Idiff=0.31) is True
        assert r.pickup_logic(Ibias=1.0, Idiff=0.29) is False

    def test_pickup_slope2_region(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        assert r.pickup_logic(Ibias=3.0, Idiff=1.01) is True
        assert r.pickup_logic(Ibias=3.0, Idiff=0.99) is False

    def test_operate_trips_on_pickup(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        result = r.operate(Ibias=1.0, Idiff=0.5)
        assert result is True
        assert r.trip is True

    def test_operate_no_trip_balanced(self):
        r = DifferentialRelay(relay_id=1, Ip=0.1, slope1=0.2, slope2=0.5)
        result = r.operate(Ibias=1.0, Idiff=0.05)
        assert result is False
        assert r.trip is False

    def test_custom_slopes(self):
        r = DifferentialRelay(relay_id=1, Ip=0.2, slope1=0.3, slope2=0.6)
        assert r.slope1 == pytest.approx(0.3)
        assert r.slope2 == pytest.approx(0.6)
        assert r.Ip == pytest.approx(0.2)

    def test_default_name(self):
        r = DifferentialRelay(relay_id=1)
        assert r.name == "DifferentialRelay"


# ===========================================================================
# DirectionalRelay (uses numpy, use == not is for assertions)
# ===========================================================================


class TestDirectionalRelay:
    def test_pickup_forward_power(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(1.0, 0)
        assert r.pickup_logic(V, I)

    def test_no_pickup_reverse_power(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(-1.0, 0)
        assert not r.pickup_logic(V, I)

    def test_no_pickup_low_voltage(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.5, angle_offset=0)
        V = complex(0.1, 0)
        I = complex(1.0, 0)
        assert not r.pickup_logic(V, I)

    def test_no_pickup_zero_current(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(0, 0)
        assert not r.pickup_logic(V, I)

    def test_pickup_with_angle_offset(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=45)
        V = complex(1.0, 0)
        I = complex(0.707, -0.707)
        assert r.pickup_logic(V, I)

    def test_no_pickup_with_angle_offset_mismatch(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=45)
        V = complex(1.0, 0)
        I = complex(-0.707, 0.707)
        assert not r.pickup_logic(V, I)

    def test_operate_trips_forward(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(1.0, 0)
        result = r.operate(V, I)
        assert result
        assert r.trip

    def test_operate_no_trip_reverse(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(-1.0, 0)
        result = r.operate(V, I)
        assert not result
        assert not r.trip

    def test_inductive_forward(self):
        r = DirectionalRelay(relay_id=1, voltage_threshold=0.1, angle_offset=0)
        V = complex(1.0, 0)
        I = complex(0.707, -0.707)
        assert r.pickup_logic(V, I)

    def test_default_name(self):
        r = DirectionalRelay(relay_id=1)
        assert r.name == "DirectionalRelay"
