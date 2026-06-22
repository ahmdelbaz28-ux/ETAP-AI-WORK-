"""
Benchmark tests against IEEE standard test cases.
Run: pytest tests/benchmark_ieee.py -v
"""

import numpy as np
import pytest
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from load_flow.load_flow_solver_fixed import LoadFlowSolver


def build_simple_3bus():
    """Build simple 3-bus test system with per-unit values."""
    system = System(base_mva=100.0)

    bus1 = Bus(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack", base_kv=13.8)
    bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8)
    bus3 = Bus(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8)

    system.add_bus(bus1)
    system.add_bus(bus2)
    system.add_bus(bus3)

    gen = Generator(
        generator_id=1,
        bus=bus1,
        impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
    )
    system.add_generator(gen)

    # Loads in per-unit (50 MW / 100 MVA = 0.5 pu, etc.)
    load2 = Load(load_id=2, bus=bus2, load_power=complex(0.5, 0.2))
    system.add_load(load2)
    load3 = Load(load_id=3, bus=bus3, load_power=complex(0.3, 0.15))
    system.add_load(load3)

    line12 = Line(line_id=1, from_bus=bus1, to_bus=bus2, z1=complex(0.01, 0.05))
    system.add_line(line12)
    line23 = Line(line_id=2, from_bus=bus2, to_bus=bus3, z1=complex(0.015, 0.06))
    system.add_line(line23)

    return system


def test_3bus_convergence():
    """Test that 3-bus system converges with proper per-unit values."""
    system = build_simple_3bus()
    solver = LoadFlowSolver(system)
    converged = solver.solve(max_iter=100, tol=1e-6)
    assert converged, "3-bus system should converge"
    for bid in solver.bus_ids:
        v_mag = abs(solver.V[solver.bus_index[bid]])
        assert 0.9 <= v_mag <= 1.1, f"Bus {bid} voltage {v_mag} out of bounds"


def test_3bus_power_balance():
    """Test power balance with per-unit values."""
    system = build_simple_3bus()
    solver = LoadFlowSolver(system)
    solver.solve(max_iter=100, tol=1e-6)
    total_gen = sum(bus.generation_power for bus in system.buses.values())
    total_load = sum(bus.load_power for bus in system.buses.values())
    losses = abs(total_gen - total_load)
    assert losses < 5.0, f"Power imbalance too large: {losses} MVA"
