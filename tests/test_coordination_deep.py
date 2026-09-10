"""
Deep Coordination Tests - coordination/coordination.py + curves/curves.py + relays/relay.py

Covers:
- check_coordination() coordinated/uncoordinated cases
- check_coordination_range() full fault current sweep
- suggest_tms_adjustment() finding valid TMS
- IEC curve operating times: standard_inverse, very_inverse, extremely_inverse
- OvercurrentRelay.trip_time() safety guards
"""

from __future__ import annotations

import pytest

from coordination.coordination import CoordinationEngine
from curves.curves import (
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
    calculate_iec_operating_time,
)
from relays.relay import OvercurrentRelay


@pytest.fixture(name="engine")
def fixture_engine():
    return CoordinationEngine()


@pytest.fixture(name="coordinated_pair")
def fixture_coordinated_pair():
    up = OvercurrentRelay(relay_id=1, name="Up", TMS=0.3, Ip=1.0)
    down = OvercurrentRelay(relay_id=2, name="Down", TMS=0.15, Ip=1.0)
    return up, down


@pytest.fixture(name="uncoordinated_pair")
def fixture_uncoordinated_pair():
    up = OvercurrentRelay(relay_id=1, name="Up", TMS=0.05, Ip=1.0)
    down = OvercurrentRelay(relay_id=2, name="Down", TMS=0.5, Ip=1.0)
    return up, down


class TestCheckCoordination:
    def test_coordinated_pair_passes(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["coordinated"] is True

    def test_uncoordinated_pair_fails(self, engine, uncoordinated_pair):
        up, down = uncoordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["coordinated"] is False

    def test_result_has_required_keys(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=8.0)
        for key in (
            "coordinated",
            "upstream_time",
            "downstream_time",
            "margin",
            "required_margin",
            "fault_current",
        ):
            assert key in result

    def test_margin_positive_when_coordinated(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["margin"] > 0

    def test_downstream_trips_first_when_coordinated(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["downstream_time"] < result["upstream_time"]

    def test_fault_current_stored(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=15.0)
        assert result["fault_current"] == 15.0

    def test_required_margin_is_0_2(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["required_margin"] == 0.2

    def test_times_are_positive(self, engine, coordinated_pair):
        up, down = coordinated_pair
        result = engine.check_coordination(up, down, fault_current=10.0)
        assert result["upstream_time"] > 0
        assert result["downstream_time"] > 0


class TestCheckCoordinationRange:
    def test_all_coordinated(self, engine, coordinated_pair):
        up, down = coordinated_pair
        results = engine.check_coordination_range(up, down, [5, 8, 12, 20])
        assert all(r["coordinated"] for r in results)

    def test_result_count_matches(self, engine, coordinated_pair):
        up, down = coordinated_pair
        faults = [3, 5, 7, 9, 11]
        results = engine.check_coordination_range(up, down, faults)
        assert len(results) == len(faults)

    def test_each_result_has_keys(self, engine, coordinated_pair):
        up, down = coordinated_pair
        results = engine.check_coordination_range(up, down, [10.0])
        for key in ("coordinated", "upstream_time", "downstream_time", "margin"):
            assert key in results[0]

    def test_none_coordinated_for_reversed(self, engine, uncoordinated_pair):
        up, down = uncoordinated_pair
        results = engine.check_coordination_range(up, down, [5, 8, 12])
        assert not all(r["coordinated"] for r in results)


class TestSuggestTMSAdjustment:
    def test_returns_float(self, engine, uncoordinated_pair):
        up, down = uncoordinated_pair
        tms = engine.suggest_tms_adjustment(up, down, [5.0, 10.0, 20.0])
        assert tms is not None
        assert isinstance(tms, float)

    def test_in_valid_range(self, engine, uncoordinated_pair):
        up, down = uncoordinated_pair
        tms = engine.suggest_tms_adjustment(up, down, [5.0, 10.0, 20.0])
        assert engine.tms_search_min <= tms <= engine.tms_search_max

    def test_already_coordinated_returns_valid(self, engine, coordinated_pair):
        up, down = coordinated_pair
        tms = engine.suggest_tms_adjustment(up, down, [5.0, 10.0, 20.0])
        assert tms is not None


class TestIECOperatingTime:
    def test_returns_dict_with_operating_time(self):
        result = calculate_iec_operating_time(5.0, 1.0, 0.3, "standard_inverse")
        assert "operating_time_s" in result
        assert result["operating_time_s"] > 0

    def test_time_decreases_higher_current(self):
        t1 = calculate_iec_operating_time(5.0, 1.0, 0.3, "standard_inverse")["operating_time_s"]
        t2 = calculate_iec_operating_time(10.0, 1.0, 0.3, "standard_inverse")["operating_time_s"]
        assert t2 < t1

    def test_time_increases_higher_tms(self):
        t1 = calculate_iec_operating_time(5.0, 1.0, 0.1, "standard_inverse")["operating_time_s"]
        t2 = calculate_iec_operating_time(5.0, 1.0, 0.5, "standard_inverse")["operating_time_s"]
        assert t2 > t1

    def test_minimum_time_enforced(self):
        result = calculate_iec_operating_time(1000.0, 1.0, 0.01, "standard_inverse")
        assert result["operating_time_s"] >= MIN_OPERATING_TIME_S - 1e-9

    @pytest.mark.parametrize(
        "curve_type",
        [
            "standard_inverse",
            "very_inverse",
            "extremely_inverse",
        ],
    )
    def test_all_curves_positive(self, curve_type):
        result = calculate_iec_operating_time(5.0, 1.0, 0.3, curve_type)
        assert result["operating_time_s"] > 0

    def test_constants_are_positive(self):
        assert MIN_OPERATING_TIME_S > 0
        assert MAX_MULTIPLIER_OF_PICKUP > 1.0


class TestOvercurrentRelay:
    def test_trip_time_decreasing_with_current(self):
        relay = OvercurrentRelay(relay_id=1, name="R1", TMS=0.3, Ip=1.0)
        t5 = relay.trip_time(5.0)
        t10 = relay.trip_time(10.0)
        assert t10 < t5

    def test_trip_time_positive(self):
        relay = OvercurrentRelay(relay_id=1, name="R1", TMS=0.3, Ip=1.0)
        for If in [2.0, 5.0, 10.0, 50.0]:
            assert relay.trip_time(If) > 0

    def test_relay_attributes(self):
        relay = OvercurrentRelay(relay_id=42, name="TestRelay", TMS=0.5, Ip=2.0)
        assert relay.relay_id == 42
        assert relay.TMS == 0.5
        assert relay.Ip == 2.0

    def test_relay_name_stored(self):
        relay = OvercurrentRelay(relay_id=1, name="FeederRelay", TMS=0.3, Ip=1.0)
        assert relay.name == "FeederRelay"

    def test_lower_tms_shorter_time(self):
        r1 = OvercurrentRelay(relay_id=1, name="R1", TMS=0.1, Ip=1.0)
        r2 = OvercurrentRelay(relay_id=2, name="R2", TMS=0.5, Ip=1.0)
        assert r1.trip_time(5.0) < r2.trip_time(5.0)

    def test_higher_pickup_longer_time(self):
        """Higher Ip setting means higher multiple needed for same current."""
        r1 = OvercurrentRelay(relay_id=1, name="R1", TMS=0.3, Ip=0.5)
        r2 = OvercurrentRelay(relay_id=2, name="R2", TMS=0.3, Ip=2.0)
        # At fault=5.0, r1 has multiple=10x, r2 has multiple=2.5x -> r1 trips faster
        t1 = r1.trip_time(5.0)
        t2 = r2.trip_time(5.0)
        assert t1 < t2
