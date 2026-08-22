"""Test scipy.linprog fix in optimal_power_flow.py (P1 correctness fix).

Regression test asserting the DC-OPF solver passes the equality-constraint
matrix using scipy's correct keyword ``A_eq`` (not the typo ``a_eq``).
"""

from unittest.mock import patch

import numpy as np
import pytest

from load_flow.optimal_power_flow import GeneratorCost, OptimalPowerFlowEngine


def test_optimal_power_flow_uses_A_eq():
    """scipy.linprog must be called with A_eq (not the a_eq typo)."""
    ybus = np.zeros((2, 2))
    bus_ids = [0, 1]
    generator_costs = [
        GeneratorCost(
            generator_id=0,
            cost_coefficients=[0, 1, 0],
            p_min=0,
            p_max=100,
            q_min=0,
            q_max=0,
        ),
        GeneratorCost(
            generator_id=1,
            cost_coefficients=[0, 1, 0],
            p_min=0,
            p_max=100,
            q_min=0,
            q_max=0,
        ),
    ]

    opf_engine = OptimalPowerFlowEngine(ybus, bus_ids, generator_costs)
    opf_engine.set_load_data({0: 150.0 + 0j, 1: 50.0 + 0j})
    opf_engine.set_generator_locations({0: 0, 1: 1})  # Map generator_id -> bus_id

    with patch("load_flow.optimal_power_flow.linprog") as mock_linprog:
        mock_linprog.return_value = type("Result", (), {"x": np.zeros(2), "success": True})

        opf_engine.solve_dc_opf()

        assert mock_linprog.called
        _, kwargs = mock_linprog.call_args
        assert "A_eq" in kwargs, "scipy.linprog should use A_eq, not a_eq"
        assert "a_eq" not in kwargs, "scipy.linprog typo a_eq must not be used"
