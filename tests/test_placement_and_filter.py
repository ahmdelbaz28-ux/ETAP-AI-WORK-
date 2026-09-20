"""
tests/test_placement_and_filter.py — Unit Tests for Optimal Placement and Filter Design.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.optimizers.filter_design_pso import HarmonicFilterOptimizer
from engine.optimizers.placement_pso import OptimalPlacementPSO


def test_capacitor_placement_loss_reduction():
    # 4-bus network
    ybus = np.array([
        [10.0 - 20.0j, -5.0 + 10.0j, -5.0 + 10.0j, 0.0],
        [-5.0 + 10.0j, 15.0 - 30.0j, 0.0, -10.0 + 20.0j],
        [-5.0 + 10.0j, 0.0, 15.0 - 30.0j, -10.0 + 20.0j],
        [0.0, -10.0 + 20.0j, -10.0 + 20.0j, 20.0 - 40.0j],
    ], dtype=complex)

    bus_ids = [1, 2, 3, 4]
    load_data = {
        2: complex(20.0, 10.0),
        3: complex(25.0, 15.0),
        4: complex(40.0, 30.0),
    }

    opt = OptimalPlacementPSO(
        ybus=ybus,
        bus_ids=bus_ids,
        load_data=load_data,
        candidate_buses=[2, 3, 4],
        max_total_q_mvar=25.0,
        max_per_bus_q_mvar=15.0,
        swarm_size=35,
        max_iter=50,
        seed=42,
    )

    result = opt.optimize_capacitor_placement()

    assert result.loss_reduction_pct > 20.0
    assert result.optimized_losses_mw < result.initial_losses_mw
    assert result.min_voltage_after >= result.min_voltage_before
    assert len(result.optimal_allocations) > 0


def test_harmonic_filter_ieee_519_compliance():
    opt = HarmonicFilterOptimizer(
        nominal_voltage_kv=13.8,
        system_frequency_hz=60.0,
        short_circuit_mva=150.0,
        harmonic_currents_a={5: 45.0, 7: 28.0, 11: 14.0, 13: 10.0},
        seed=42,
    )

    res = opt.design_filter_for_harmonic(target_harmonic=5, target_q_kvar=750.0)

    assert res.thd_v_after_pct < res.thd_v_before_pct
    assert res.ieee_519_compliant is True
    assert res.thd_v_after_pct <= 5.0
    for h, v_pct in res.individual_harmonics_after_pct.items():
        assert v_pct <= 3.0, f"Harmonic {h} voltage {v_pct}% exceeds 3.0%"

    assert res.resistance_ohms > 0.0
    assert res.inductance_mh > 0.0
    assert res.capacitance_uf > 0.0
    assert 20.0 <= res.quality_factor <= 100.0
