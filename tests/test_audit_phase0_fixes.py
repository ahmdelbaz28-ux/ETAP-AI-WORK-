"""Unit tests verifying Phase 0 audit fixes (S-1, S-2, S-3)."""

from __future__ import annotations

import pytest
import numpy as np

from core_model.bus import Bus
from core_model.line import Line
from core_model.system import System
from engine.engine import PowerSystemEngine
from coordination.coordination import CoordinationEngine
from relays.relay import OvercurrentRelay


def _build_test_system() -> System:
    system = System(base_mva=100.0)
    bus1 = Bus(bus_id=1, base_kv=13.8, bus_type="slack", voltage_magnitude=1.0, voltage_angle=0.0)
    bus2 = Bus(bus_id=2, base_kv=13.8, bus_type="pq", load_power=0.1 + 0.05j)
    system.add_bus(bus1)
    system.add_bus(bus2)
    system.add_line(Line(line_id=1, from_bus=bus1, to_bus=bus2, z1=0.01 + 0.05j))
    return system


def test_s01_solver_parameter_propagation():
    """S-1: run_load_flow must accept and pass custom max_iter and tol to solver."""
    system = _build_test_system()
    engine = PowerSystemEngine(system)

    # With max_iter=1 and very tight tolerance, it should not converge in 1 iteration
    res_1 = engine.run_load_flow(max_iter=1, tol=1e-12)
    assert res_1["converged"] is False, "Load flow should not converge with max_iter=1 and tol=1e-12"

    # With normal iterations, it converges
    res_norm = engine.run_load_flow(max_iter=50, tol=1e-5)
    assert res_norm["converged"] is True, "Load flow should converge with normal parameters"


def test_s02_default_curve_type():
    """S-2: run_protection_coordination should succeed with default curve type (standard_inverse)."""
    engine = PowerSystemEngine()
    
    # Run protection coordination with no curve_type specified (testing default fallback)
    res = engine.run_protection_coordination(
        upstream_relay_id=1,
        downstream_relay_id=2,
        fault_currents=[2.0, 5.0, 10.0],
        relays_config={
            "upstream": {"tms": 0.5, "pickup_current_a": 100.0},
            "downstream": {"tms": 0.2, "pickup_current_a": 50.0},
        },
    )
    assert "error" not in res
    assert "results" in res
    assert len(res["results"]) == 3
    assert res["upstream_relay"]["curve_type"] == "standard_inverse"
    assert res["downstream_relay"]["curve_type"] == "standard_inverse"


def test_s03_custom_coordination_margin():
    """S-3: CoordinationEngine must respect default_margin_sec."""
    # Create upstream and downstream relays
    upstream = OvercurrentRelay(relay_id=1, tms=0.5, ip=100.0, curve_type="standard_inverse")
    downstream = OvercurrentRelay(relay_id=2, tms=0.1, ip=50.0, curve_type="standard_inverse")
    
    fault_current = 200.0  # 2x upstream, 4x downstream
    t_up = upstream.trip_time(fault_current)
    t_down = downstream.trip_time(fault_current)
    actual_margin = t_up - t_down
    assert actual_margin > 0
    
    # Margin engine with threshold higher than actual margin
    strict_margin = actual_margin + 0.05
    engine_strict = CoordinationEngine(default_margin_sec=strict_margin)
    res_strict = engine_strict.check_coordination(upstream, downstream, fault_current)
    assert res_strict["coordinated"] is False
    assert res_strict["required_margin"] == strict_margin
    
    # Margin engine with threshold lower than actual margin
    lenient_margin = max(0.01, actual_margin - 0.05)
    engine_lenient = CoordinationEngine(default_margin_sec=lenient_margin)
    res_lenient = engine_lenient.check_coordination(upstream, downstream, fault_current)
    assert res_lenient["coordinated"] is True
    assert res_lenient["required_margin"] == lenient_margin
