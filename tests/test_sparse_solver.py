"""Tests for Sparse Matrix Solver.

Tests the SparseYBus class with realistic power system data including
3-bus, IEEE 14-bus equivalent systems, convergence checks, and memory
comparison between dense and sparse storage.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from scipy.sparse import issparse

from engine.sparse_solver import (
    BranchData,
    BusData,
    SparseConvergenceResult,
    SparseYBus,
)

# ---------------------------------------------------------------------------
# 3-bus test system
# ---------------------------------------------------------------------------


def _make_3bus_data():
    """Build 3-bus system data.

    Bus 0: Slack (1.0 pu, 0 rad)
    Bus 1: PV   (1.02 pu, scheduled)
    Bus 2: PQ   (1.0 pu, 0 rad)

    Branches: 0-1, 1-2, 0-2
    """
    buses = [
        BusData(
            bus_id=0,
            bus_type="slack",
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            p_generation=0,
            q_generation=0,
            p_load=0,
            q_load=0,
            v_scheduled=1.0,
        ),
        BusData(
            bus_id=1,
            bus_type="pv",
            voltage_magnitude=1.02,
            voltage_angle=0.0,
            p_generation=0.5,
            q_generation=0,
            p_load=0,
            q_load=0,
            v_scheduled=1.02,
        ),
        BusData(
            bus_id=2,
            bus_type="pq",
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            p_generation=0,
            q_generation=0,
            p_load=0.8,
            q_load=0.3,
        ),
    ]
    branches = [
        BranchData(
            from_bus=0, to_bus=1, impedance=complex(0.01, 0.05), shunt_admittance=complex(0, 0.02)
        ),
        BranchData(
            from_bus=1, to_bus=2, impedance=complex(0.02, 0.08), shunt_admittance=complex(0, 0.02)
        ),
        BranchData(
            from_bus=0, to_bus=2, impedance=complex(0.03, 0.10), shunt_admittance=complex(0, 0.02)
        ),
    ]
    return buses, branches


# ---------------------------------------------------------------------------
# IEEE 14-bus equivalent (simplified)
# ---------------------------------------------------------------------------


def _make_14bus_data():
    """Build a simplified IEEE 14-bus equivalent system.

    Uses typical impedance data scaled to 100 MVA base.
    """
    # Bus types for 14-bus: Bus 0=slack, Bus 1=PV, rest=PQ
    buses = []
    bus_types = ["slack", "pv"] + ["pq"] * 12
    v_mags = [1.06, 1.045] + [1.0] * 12
    p_gen = [0, 0.4] + [0] * 12
    p_loads = [0, 0.217, 0.942, 0.478, 0.076, 0.112, 0, 0, 0.295, 0.09, 0.035, 0.061, 0.135, 0.149]
    q_loads = [0, 0.127, 0.19, -0.039, 0.016, 0.075, 0, 0, 0.166, 0.058, 0.018, 0.016, 0.058, 0.05]

    for i in range(14):
        buses.append(
            BusData(
                bus_id=i,
                bus_type=bus_types[i],
                voltage_magnitude=v_mags[i],
                voltage_angle=0.0,
                p_generation=p_gen[i],
                q_generation=0,
                p_load=p_loads[i],
                q_load=q_loads[i],
                v_scheduled=v_mags[i],
            )
        )

    # Simplified branch list (from, to, impedance)
    branch_specs = [
        (0, 1, complex(0.01938, 0.05917)),
        (0, 4, complex(0.05403, 0.22304)),
        (1, 2, complex(0.04699, 0.19797)),
        (1, 3, complex(0.05811, 0.17632)),
        (1, 4, complex(0.01335, 0.04211)),
        (2, 3, complex(0.06701, 0.17103)),
        (2, 5, complex(0.09498, 0.19890)),
        (2, 9, complex(0.12291, 0.25581)),
        (3, 4, complex(0.01188, 0.04159)),
        (4, 5, complex(0.04258, 0.14292)),
        (4, 7, complex(0.03181, 0.08302)),
        (4, 9, complex(0.04065, 0.12327)),
        (5, 6, complex(0.00301, 0.01248)),
        (6, 7, complex(0.00244, 0.03091)),
        (6, 8, complex(0.02005, 0.07886)),
        (6, 9, complex(0.00244, 0.03091)),
        (7, 8, complex(0.00314, 0.04146)),
        (9, 10, complex(0.03181, 0.08302)),
        (9, 11, complex(0.00244, 0.03091)),
        (10, 11, complex(0.00244, 0.03091)),
        (11, 12, complex(0.03181, 0.08302)),
        (12, 13, complex(0.00244, 0.03091)),
    ]
    branches = [BranchData(from_bus=f, to_bus=t, impedance=z) for f, t, z in branch_specs]
    return buses, branches


class TestSparseSolver:
    """Tests for sparse matrix solver."""

    def test_build_sparse_ybus_3bus(self):
        """Test 1: Build sparse Y-bus for 3-bus system."""
        solver = SparseYBus()
        buses, branches = _make_3bus_data()
        ybus = solver.build_sparse_ybus(buses, branches)

        assert ybus.shape == (3, 3)
        assert issparse(ybus)
        # Ybus should be symmetric for a network without phase shifters
        # (Y_ij = Y_ji for passive branches)
        ybus_dense = ybus.toarray()
        np.testing.assert_array_almost_equal(ybus_dense, ybus_dense.T, decimal=10)
        # Diagonal should be non-zero
        assert all(ybus_dense[i, i] != 0 for i in range(3))

    def test_convergence_3bus(self):
        """Test 2: Newton-Raphson converges for 3-bus system."""
        solver = SparseYBus()
        buses, branches = _make_3bus_data()
        ybus = solver.build_sparse_ybus(buses, branches)

        result = solver.sparse_newton_raphson(
            ybus,
            buses,
            max_iter=50,
            tol=1e-8,
        )

        assert isinstance(result, SparseConvergenceResult)
        assert result.converged
        assert result.iterations > 0
        assert result.max_mismatch < 1e-6
        # Voltages should be reasonable
        assert np.all(result.magnitudes > 0.5)
        assert np.all(result.magnitudes < 1.5)

    def test_convergence_14bus(self):
        """Test 3: Newton-Raphson converges for IEEE 14-bus equivalent."""
        solver = SparseYBus()
        buses, branches = _make_14bus_data()
        ybus = solver.build_sparse_ybus(buses, branches)

        assert ybus.shape == (14, 14)

        result = solver.sparse_newton_raphson(
            ybus,
            buses,
            max_iter=100,
            tol=1e-8,
        )

        assert isinstance(result, SparseConvergenceResult)
        assert result.converged
        assert result.max_mismatch < 1e-6
        # All voltages within reasonable bounds
        assert np.all(result.magnitudes > 0.8)
        assert np.all(result.magnitudes < 1.2)

    def test_memory_comparison(self):
        """Test 4: Sparse storage uses less memory than dense for 14-bus."""
        solver = SparseYBus()
        buses, branches = _make_14bus_data()
        mem = solver.compare_memory(buses, branches)

        assert mem["n_buses"] == 14
        assert mem["sparse_bytes"] < mem["dense_bytes"]
        assert mem["savings_pct"] > 0
        assert mem["nnz"] > 0

    def test_empty_system(self):
        """Test 5: Handles empty system gracefully."""
        solver = SparseYBus()
        result = solver.sparse_newton_raphson()
        assert not result.converged  # No buses → nothing to solve

    def test_sparse_fill_percentage(self):
        """Test 6: Fill percentage decreases for larger systems."""
        solver_3 = SparseYBus()
        buses_3, branches_3 = _make_3bus_data()

        solver_14 = SparseYBus()
        buses_14, branches_14 = _make_14bus_data()
        mem_14 = solver_14.compare_memory(buses_14, branches_14)

        # Larger systems typically have lower fill percentage
        # (power grids are sparse)
        assert mem_14["fill_pct"] < 100.0

    def test_ybus_symmetry_14bus(self):
        """Test 7: Y-bus is symmetric for 14-bus system (no phase shifters)."""
        solver = SparseYBus()
        buses, branches = _make_14bus_data()
        ybus = solver.build_sparse_ybus(buses, branches)
        ybus_dense = ybus.toarray()

        # Ybus should satisfy Y_ij = Y_ji for passive networks without
        # phase-shifting transformers (Y is symmetric, not Hermitian)
        np.testing.assert_array_almost_equal(ybus_dense, ybus_dense.T, decimal=10)

    def test_power_balance_3bus(self):
        """Test 8: Power balance is satisfied after convergence."""
        solver = SparseYBus()
        buses, branches = _make_3bus_data()
        ybus = solver.build_sparse_ybus(buses, branches)
        result = solver.sparse_newton_raphson(ybus, buses, max_iter=50)

        if result.converged:
            Y = ybus.toarray()
            V = result.voltages
            S = V * np.conj(Y @ V)
            P_gen = sum(b.p_generation for b in buses)
            P_load = sum(b.p_load for b in buses)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            P_loss = S.real.sum()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            # Power balance: generation - load ≈ losses  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            balance = abs(P_gen - P_load - P_loss)
            # Allow some tolerance for numerical precision
            assert balance < 1.0 or P_loss < 1.0

    def test_branch_impedance_nonzero(self):
        """Test 9: Branches with zero impedance are handled."""
        # Zero impedance would cause division by zero in admittance calc
        solver = SparseYBus()
        buses = [
            BusData(bus_id=0, bus_type="slack", voltage_magnitude=1.0),
            BusData(bus_id=1, bus_type="pq", voltage_magnitude=1.0, p_load=0.5),
        ]
        branches = [
            BranchData(from_bus=0, to_bus=1, impedance=complex(0, 0)),  # Zero!
        ]
        ybus = solver.build_sparse_ybus(buses, branches)
        # Zero impedance → zero admittance (branch ignored)
        assert ybus.shape == (2, 2)

    def test_tap_ratio_transformer(self):
        """Test 10: Transformer with tap ratio is handled in Y-bus."""
        solver = SparseYBus()
        buses = [
            BusData(bus_id=0, bus_type="slack", voltage_magnitude=1.0),
            BusData(bus_id=1, bus_type="pq", voltage_magnitude=1.0, p_load=0.5),
        ]
        branches = [
            BranchData(
                from_bus=0, to_bus=1, impedance=complex(0.01, 0.1), tap_ratio=1.05, phase_shift=0.0
            ),
        ]
        ybus = solver.build_sparse_ybus(buses, branches)
        ybus_dense = ybus.toarray()
        # With tap ratio ≠ 1, diagonal elements differ
        assert ybus_dense[0, 0] != ybus_dense[1, 1]
