"""
tests/test_opf_correctness.py — Rigorous Tests for DC-OPF with PTDF Branch Limits.

Tests:
1. Economic dispatch unconstrained by branch limits (merit-order dispatch).
2. Economic dispatch with binding branch thermal limits via PTDF (congestion management).
3. Verification that branch flows strictly adhere to S_max limits.
"""

from __future__ import annotations

import numpy as np
import pytest

from load_flow.optimal_power_flow import GeneratorCost, OptimalPowerFlowEngine


class TestOptimalPowerFlowCorrectness:
    """Test suite verifying DC-OPF economics and transmission constraints."""

    def test_unconstrained_economic_dispatch(self):
        """Cheap generator should be dispatched first up to load or capacity."""
        bus_ids = [1, 2, 3]
        # Gen 1 at Bus 1: cheap ($15/MWh), cap 100 MW
        # Gen 2 at Bus 2: expensive ($40/MWh), cap 100 MW
        costs = [
            GeneratorCost(generator_id=1, cost_coefficients=[0.0, 15.0, 0.0], p_min=0.0, p_max=100.0, q_min=-50.0, q_max=50.0),
            GeneratorCost(generator_id=2, cost_coefficients=[0.0, 40.0, 0.0], p_min=0.0, p_max=100.0, q_min=-50.0, q_max=50.0),
        ]

        # Form a standard 3-bus triangle
        # B_bus with x12=0.1, x23=0.1, x13=0.2
        Ybus = np.zeros((3, 3), dtype=complex)
        Ybus[0, 1] = Ybus[1, 0] = -1j / 0.1
        Ybus[1, 2] = Ybus[2, 1] = -1j / 0.1
        Ybus[0, 2] = Ybus[2, 0] = -1j / 0.2
        for i in range(3):
            Ybus[i, i] = -sum(Ybus[i, j] for j in range(3) if j != i)

        engine = OptimalPowerFlowEngine(Ybus, bus_ids, costs)
        engine.set_generator_locations({1: 1, 2: 2})
        # Load of 80 MW at Bus 3
        engine.set_load_data({1: 0.0, 2: 0.0, 3: 80.0})

        res = engine.solve_dc_opf()

        assert res.success is True
        # Gen 1 should serve all 80 MW since it is cheaper and capacity is 100 MW
        assert res.generator_dispatch[1].real == pytest.approx(80.0, abs=1e-3)
        assert res.generator_dispatch[2].real == pytest.approx(0.0, abs=1e-3)
        assert res.total_generation == pytest.approx(80.0, abs=1e-3)
        assert res.total_load == pytest.approx(80.0, abs=1e-3)

    def test_constrained_economic_dispatch_with_ptdf(self):
        """Branch thermal limit forces out-of-merit redispatch (congestion management)."""
        bus_ids = [1, 2, 3]
        # Gen 1 at Bus 1 (Slack): $45/MWh, cap 200 MW
        # Gen 2 at Bus 2: $10/MWh (very cheap!), cap 200 MW
        costs = [
            GeneratorCost(generator_id=1, cost_coefficients=[0.0, 45.0, 0.0], p_min=0.0, p_max=200.0, q_min=0.0, q_max=0.0),
            GeneratorCost(generator_id=2, cost_coefficients=[0.0, 10.0, 0.0], p_min=0.0, p_max=200.0, q_min=0.0, q_max=0.0),
        ]

        # 3-bus system: x12 = 0.1, x23 = 0.1, x13 = 0.2
        Ybus = np.zeros((3, 3), dtype=complex)
        Ybus[0, 1] = Ybus[1, 0] = -1j / 0.1
        Ybus[1, 2] = Ybus[2, 1] = -1j / 0.1
        Ybus[0, 2] = Ybus[2, 0] = -1j / 0.2
        for i in range(3):
            Ybus[i, i] = -sum(Ybus[i, j] for j in range(3) if j != i)

        engine = OptimalPowerFlowEngine(Ybus, bus_ids, costs)
        engine.set_generator_locations({1: 1, 2: 2})
        # 100 MW load at Bus 3
        engine.set_load_data({1: 0.0, 2: 0.0, 3: 100.0})

        # Set branch thermal limit on line (2, 3) to 65 MW
        # (Unconstrained Gen 2 would supply 100 MW and induce 75 MW flow on line 2->3.
        # With 65 MW limit, Gen 2 is capped at 60 MW, requiring Gen 1 to supply 40 MW).
        engine.set_branch_limits({(2, 3): 65.0})

        res = engine.solve_dc_opf()

        assert res.success is True
        flow_23 = res.branch_flows[(2, 3)].real if (2, 3) in res.branch_flows else -res.branch_flows[(3, 2)].real
        assert abs(flow_23) <= 65.0 + 1e-4

        # Gen 2 is curtailed to 60 MW, Gen 1 dispatches 40 MW
        assert res.generator_dispatch[2].real == pytest.approx(60.0, abs=1e-3)
        assert res.generator_dispatch[1].real == pytest.approx(40.0, abs=1e-3)
        assert res.total_generation == pytest.approx(100.0, abs=1e-3)
        assert len(res.constraint_violations) == 0

    def test_branch_flows_and_bus_voltages_populated(self):
        """DC-OPF results must contain branch flows and voltage angles."""
        bus_ids = [1, 2]
        costs = [
            GeneratorCost(generator_id=1, cost_coefficients=[0.0, 20.0, 0.0], p_min=0.0, p_max=100.0, q_min=0.0, q_max=0.0),
        ]
        Ybus = np.array([[ -10j, 10j ], [ 10j, -10j ]], dtype=complex)
        engine = OptimalPowerFlowEngine(Ybus, bus_ids, costs)
        engine.set_generator_locations({1: 1})
        engine.set_load_data({1: 0.0, 2: 50.0})
        engine.set_branch_reactances({(1, 2): 0.1})

        res = engine.solve_dc_opf()
        assert res.success is True
        assert len(res.branch_flows) > 0
        assert (1, 2) in res.branch_flows or (2, 1) in res.branch_flows
        flow = res.branch_flows[(1, 2)].real if (1, 2) in res.branch_flows else -res.branch_flows[(2, 1)].real
        assert flow == pytest.approx(50.0, abs=1e-3)
