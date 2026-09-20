"""
tests/test_pso_coordinator.py — Unit Tests for Swarm-Optimized Protection Coordination.
"""

from __future__ import annotations

import pytest

from coordination.optimizers.pso_coordinator import PSOCoordinationEngine
from engine.interfaces import CoordinationEngineProtocol
from relays.relay import OvercurrentRelay


@pytest.fixture
def relay_pair():
    r_down = OvercurrentRelay("R_DOWN", "RelayDown", "standard_inverse", tms=0.1, ip=1.0)
    r_up = OvercurrentRelay("R_UP", "RelayUp", "standard_inverse", tms=0.5, ip=1.5)
    faults = [3.0, 5.0, 8.0, 10.0, 15.0]
    return r_up, r_down, faults


def test_protocol_conformance():
    """Verify PSOCoordinationEngine satisfies CoordinationEngineProtocol interface."""
    engine = PSOCoordinationEngine()
    # CoordinationEngineProtocol requires check_coordination, check_coordination_range, and suggest_tms_adjustment
    assert callable(getattr(engine, "check_coordination", None))
    assert callable(getattr(engine, "check_coordination_range", None))
    assert callable(getattr(engine, "suggest_tms_adjustment", None))


def test_check_coordination(relay_pair):
    r_up, r_down, faults = relay_pair
    engine = PSOCoordinationEngine()

    res = engine.check_coordination(r_up, r_down, fault_current=5.0)
    assert "coordinated" in res
    assert "margin" in res
    assert "upstream_time" in res
    assert "downstream_time" in res
    assert res["upstream_time"] > res["downstream_time"]


def test_check_coordination_range(relay_pair):
    r_up, r_down, faults = relay_pair
    engine = PSOCoordinationEngine()

    range_results = engine.check_coordination_range(r_up, r_down, faults)
    assert len(range_results) == len(faults)
    for item in range_results:
        assert "coordinated" in item


def test_suggest_tms_adjustment_reaches_target_margin(relay_pair):
    r_up, r_down, faults = relay_pair
    engine = PSOCoordinationEngine(seed=42)

    target_margin = 0.2
    best_tms = engine.suggest_tms_adjustment(r_up, r_down, faults, target_margin=target_margin)

    assert best_tms is not None
    assert 0.05 <= best_tms <= 3.0

    # Verify that with best_tms, all margins strictly satisfy target_margin
    for If in faults:
        t_down = r_down.trip_time(If)
        t_up = engine._calc_trip_time(best_tms, r_up.Ip, r_up.curve_type, If)
        margin = t_up - t_down
        assert margin >= target_margin - 1e-4, f"Violation at fault {If}: margin {margin} < {target_margin}"


def test_optimize_coordination_2d(relay_pair):
    r_up, r_down, faults = relay_pair
    engine = PSOCoordinationEngine(seed=42)

    res_2d = engine.optimize_coordination_2d(r_up, r_down, faults, target_margin=0.2)

    assert res_2d["coordinated"] is True
    assert res_2d["optimal_tms"] > 0.05
    assert res_2d["optimal_pickup"] > 0.2
    assert res_2d["min_margin_sec"] >= 0.1999
    assert res_2d["n_evaluations"] > 0
