"""
Tests for coordination module — CoordinationEngine.
"""

import math

import numpy as np
import pytest

from coordination.coordination import CoordinationEngine
from relays.relay import OvercurrentRelay


class TestCoordinationEngine:
    def make_relays(self, upstream_TMS=1.0, downstream_TMS=0.2, upstream_Ip=1.0, downstream_Ip=1.0):
        upstream = OvercurrentRelay(
            relay_id=1,
            name="Upstream",
            curve_type="standard_inverse",
            TMS=upstream_TMS,
            Ip=upstream_Ip,
        )
        downstream = OvercurrentRelay(
            relay_id=2,
            name="Downstream",
            curve_type="standard_inverse",
            TMS=downstream_TMS,
            Ip=downstream_Ip,
        )
        return upstream, downstream

    def test_coordinated_upstream_downstream(self):
        up, down = self.make_relays(upstream_TMS=1.0, downstream_TMS=0.2)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=5.0)
        assert result["coordinated"] is True
        assert result["upstream_time"] > result["downstream_time"]
        assert result["margin"] >= 0.2

    def test_not_coordinated_reversed(self):
        up, down = self.make_relays(upstream_TMS=0.1, downstream_TMS=2.0)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=5.0)
        # Upstream trips first — not coordinated
        assert result["coordinated"] is False

    def test_coordination_range_all_ok(self):
        up, down = self.make_relays(upstream_TMS=1.0, downstream_TMS=0.2)
        engine = CoordinationEngine()
        currents = [2.0, 5.0, 10.0, 20.0]
        results = engine.check_coordination_range(up, down, currents)
        assert len(results) == 4
        assert all(r["coordinated"] for r in results)

    def test_coordination_range_some_fail(self):
        up, down = self.make_relays(upstream_TMS=0.1, downstream_TMS=1.0)
        engine = CoordinationEngine()
        currents = [2.0, 5.0, 10.0]
        results = engine.check_coordination_range(up, down, currents)
        # At least some should fail
        assert any(not r["coordinated"] for r in results)

    def test_coordination_result_fields(self):
        up, down = self.make_relays()
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=5.0)
        assert "coordinated" in result
        assert "upstream_time" in result
        assert "downstream_time" in result
        assert "margin" in result
        assert "required_margin" in result
        assert "fault_current" in result
        assert result["required_margin"] == 0.2
        assert result["fault_current"] == 5.0

    def test_suggest_tms_adjustment_finds_solution(self):
        up, down = self.make_relays(upstream_TMS=0.1, downstream_TMS=0.2)
        engine = CoordinationEngine()
        currents = [2.0, 5.0, 10.0, 20.0]
        suggested = engine.suggest_tms_adjustment(up, down, currents, target_margin=0.2)
        assert suggested is not None
        assert suggested > 0.1  # Should suggest higher TMS

    def test_suggest_tms_with_higher_tms_works(self):
        up, down = self.make_relays(upstream_TMS=0.5, downstream_TMS=0.3)
        engine = CoordinationEngine()
        currents = [3.0, 5.0, 8.0, 15.0]
        suggested = engine.suggest_tms_adjustment(up, down, currents, target_margin=0.2)
        assert suggested is not None

    def test_coordination_at_limit_margin(self):
        up = OvercurrentRelay(relay_id=1, curve_type="very_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="very_inverse", TMS=0.3, Ip=1.0)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=8.0)
        # Should be coordinated with some margin
        assert result["margin"] >= 0 or result["coordinated"] is True

    def test_different_curve_types(self):
        up = OvercurrentRelay(relay_id=1, curve_type="extremely_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=5.0)
        # Should still produce valid timings
        assert result["upstream_time"] > 0
        assert result["downstream_time"] > 0

    def test_long_inverse_curves(self):
        up = OvercurrentRelay(relay_id=1, curve_type="long_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="long_inverse", TMS=0.3, Ip=1.0)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=3.0)
        assert result["upstream_time"] > result["downstream_time"]

    def test_empty_fault_currents(self):
        up, down = self.make_relays()
        engine = CoordinationEngine()
        results = engine.check_coordination_range(up, down, [])
        assert results == []

    def test_single_fault_current(self):
        up, down = self.make_relays()
        engine = CoordinationEngine()
        results = engine.check_coordination_range(up, down, [5.0])
        assert len(results) == 1

    def test_margin_calculation_accuracy(self):
        up, down = self.make_relays(upstream_TMS=1.0, downstream_TMS=0.2)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=5.0)
        expected_margin = result["upstream_time"] - result["downstream_time"]
        assert abs(result["margin"] - expected_margin) < 1e-10

    def test_unknown_curve_in_suggest(self):
        up = OvercurrentRelay(relay_id=1, curve_type="invalid_curve", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        engine = CoordinationEngine()
        with pytest.raises(ValueError, match="Unknown curve type"):
            engine.suggest_tms_adjustment(up, down, fault_currents=[5.0], target_margin=0.2)

    def test_different_pickup_currents(self):
        up = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=2.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=0.5)
        engine = CoordinationEngine()
        result = engine.check_coordination(up, down, fault_current=3.0)
        # Both should pick up since 3.0 > Ip
        assert math.isfinite(result["upstream_time"])
        assert math.isfinite(result["downstream_time"])

    def test_default_margin_setting(self):
        engine = CoordinationEngine(default_margin_sec=0.3)
        assert engine.default_margin_sec == 0.3

    def test_tms_search_defaults(self):
        engine = CoordinationEngine()
        assert engine.tms_search_min == 0.1
        assert engine.tms_search_max == 10.0
        assert engine.tms_search_steps == 100

    def test_tms_search_custom(self):
        engine = CoordinationEngine(tms_search_min=0.05, tms_search_max=5.0, tms_search_steps=50)
        assert engine.tms_search_min == 0.05
        assert engine.tms_search_max == 5.0
        assert engine.tms_search_steps == 50
