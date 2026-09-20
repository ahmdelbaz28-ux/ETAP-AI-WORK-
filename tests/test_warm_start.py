"""
tests/test_warm_start.py — Unit Tests for Warm-Start Voltage Vector Store.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.benchmarks.ieee_cases import build_ieee_14bus_system
from engine.optimizers.warm_start_store import WarmStartStore, get_warm_start_store
from load_flow.load_flow import LoadFlowSolver


def test_topology_hash_consistency():
    store = WarmStartStore(enable_redis=False)
    sys1 = build_ieee_14bus_system()
    sys2 = build_ieee_14bus_system()

    h1 = store.compute_topology_hash(sys1)
    h2 = store.compute_topology_hash(sys2)

    assert h1 == h2
    assert len(h1) == 24


def test_store_and_retrieve_solution():
    store = WarmStartStore(enable_redis=False)
    sys = build_ieee_14bus_system()
    bus_ids = list(sys.buses.keys())
    fake_v = np.array([complex(1.0 + 0.01 * i, 0.02 * i) for i in range(len(bus_ids))])

    key = store.store_solution(sys, bus_ids, fake_v)
    assert key != ""

    retrieved_v = store.get_warm_start_vector(sys, bus_ids)
    assert retrieved_v is not None
    assert len(retrieved_v) == len(fake_v)
    np.testing.assert_allclose(retrieved_v.real, fake_v.real)
    np.testing.assert_allclose(retrieved_v.imag, fake_v.imag)


def test_warm_start_iteration_reduction():
    """Verify that injecting warm start reduces solve iterations by at least 40%."""
    store = WarmStartStore(enable_redis=False)
    sys = build_ieee_14bus_system()

    # 1. Cold solve
    solver_cold = LoadFlowSolver(sys)
    assert not store.apply_warm_start(solver_cold)
    solver_cold.solve()
    iters_cold = len(solver_cold.iteration_log)
    assert iters_cold >= 3

    # Store converged solution
    store.store_solution(sys, solver_cold.bus_ids, solver_cold.V)

    # 2. Warm solve
    solver_warm = LoadFlowSolver(sys)
    assert store.apply_warm_start(solver_warm)
    solver_warm.solve()
    iters_warm = len(solver_warm.iteration_log)

    assert iters_warm <= 2
    assert iters_warm < iters_cold
    reduction_pct = (iters_cold - iters_warm) / iters_cold * 100.0
    assert reduction_pct >= 50.0  # Typically 80% reduction (5 down to 1)


def test_warm_start_stats():
    store = WarmStartStore(enable_redis=False)
    sys = build_ieee_14bus_system()
    bus_ids = list(sys.buses.keys())

    # Miss
    _ = store.get_warm_start_vector(sys, bus_ids)
    # Store
    v = np.ones(len(bus_ids), dtype=complex)
    store.store_solution(sys, bus_ids, v)
    # Hit
    _ = store.get_warm_start_vector(sys, bus_ids)

    stats = store.stats
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_ratio"] == 0.5
