"""
tests/test_pso_opf.py — Unit Tests for Hybrid AC Optimal Power Flow Engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from load_flow.optimal_power_flow import GeneratorCost, OPFResult
from load_flow.optimizers.pso_opf import PSOOptimalPowerFlow


@pytest.fixture
def sample_3bus_network():
    ybus = np.array([
        [10.0 - 20.0j, -5.0 + 10.0j, -5.0 + 10.0j],
        [-5.0 + 10.0j, 10.0 - 20.0j, -5.0 + 10.0j],
        [-5.0 + 10.0j, -5.0 + 10.0j, 10.0 - 20.0j],
    ], dtype=complex)

    bus_ids = [1, 2, 3]
    costs = [
        GeneratorCost(generator_id=1, cost_coefficients=[100.0, 20.0, 0.05], p_min=10.0, p_max=100.0, q_min=-50.0, q_max=50.0),
        GeneratorCost(generator_id=2, cost_coefficients=[80.0, 15.0, 0.08], p_min=10.0, p_max=80.0, q_min=-40.0, q_max=40.0),
    ]
    gen_buses = {1: 1, 2: 2}
    load_data = {3: complex(60.0, 20.0)}
    return ybus, bus_ids, costs, gen_buses, load_data


def test_pso_ac_opf_convergence(sample_3bus_network):
    ybus, bus_ids, costs, gen_buses, load_data = sample_3bus_network

    pso_opf = PSOOptimalPowerFlow(
        ybus=ybus,
        bus_ids=bus_ids,
        generator_costs=costs,
        gen_buses=gen_buses,
        load_data=load_data,
        swarm_size=35,
        max_iter=50,
        seed=42,
    )

    result = pso_opf.solve()

    assert isinstance(result, OPFResult)
    assert result.success is True
    assert result.objective_value > 0.0
    assert result.total_generation >= result.total_load
    assert result.total_losses >= 0.0

    # Ensure real AC voltages are calculated (not placeholder 1.0 pu)
    for bid in bus_ids:
        assert bid in result.bus_voltages
        v_mag = abs(result.bus_voltages[bid])
        assert 0.85 <= v_mag <= 1.15
        # Verify it is not an exact flat 1.0 + 0j dummy on non-slack buses
        if bid == 3:
            assert v_mag != 1.0

    # Verify active power balance: P_gen = P_load + P_losses within 1 MW
    imbalance = abs(result.total_generation - (result.total_load + result.total_losses))
    assert imbalance < 1.0
