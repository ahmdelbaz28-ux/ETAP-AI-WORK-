"""
tests/test_unified_load_flow_solvers.py — Unified Solvers: FDLF (XB/BX) and DC Power Flow.

Validates:
1. Fast Decoupled Load Flow (XB and BX formulations) against IEEE benchmark systems.
2. Linearized DC Power Flow (non-iterative, active power balance, line flows).
3. Behavioral consistency between Newton-Raphson, Fast Decoupled, and DC Power Flow.
4. Solver dispatch integration via PowerSystemEngine.run_load_flow(solver_type=...).
"""

import numpy as np
import pytest

from engine.benchmarks.ieee_cases import (
    build_ieee_9bus_system,
    build_ieee_14bus_system,
)
from engine.engine import PowerSystemEngine
from load_flow.dc_flow import DCLoadFlowSolver
from load_flow.fast_decoupled import FastDecoupledSolver, FDLFFormulation
from load_flow.load_flow import LoadFlowSolver


class TestUnifiedLoadFlowSolvers:
    """Empirical verification of Fast Decoupled and DC load flow engines."""

    def test_fast_decoupled_xb_ieee9(self):
        """Test FDLF XB formulation on IEEE 9-bus benchmark system."""
        sys = build_ieee_9bus_system()
        solver = FastDecoupledSolver(sys, formulation=FDLFFormulation.XB)
        converged = solver.solve(max_iter=30, tol=1e-5)

        assert converged is True, "FDLF-XB failed to converge on IEEE 9-bus"
        assert solver.iterations <= 10, f"FDLF-XB took {solver.iterations} iterations (expected <= 10)"

        # Compare against Newton-Raphson
        nr_solver = LoadFlowSolver(sys)
        nr_solver.solve(max_iter=30, tol=1e-5)

        for bid in sys.buses.keys():
            v_fd = abs(solver.bus_voltages[bid])
            v_nr = abs(nr_solver.V[nr_solver.bus_index[bid]])
            err_pct = abs(v_fd - v_nr) / v_nr * 100.0
            assert err_pct < 1.0, f"Bus {bid} voltage difference {err_pct:.3f}% exceeds 1.0%"

    def test_fast_decoupled_bx_ieee9(self):
        """Test FDLF BX formulation on IEEE 9-bus benchmark system."""
        sys = build_ieee_9bus_system()
        solver = FastDecoupledSolver(sys, formulation=FDLFFormulation.BX)
        converged = solver.solve(max_iter=30, tol=1e-5)

        assert converged is True, "FDLF-BX failed to converge on IEEE 9-bus"
        assert solver.iterations <= 10, f"FDLF-BX took {solver.iterations} iterations"

    def test_fast_decoupled_ieee14(self):
        """Test FDLF on canonical IEEE 14-bus test feeder."""
        sys = build_ieee_14bus_system()
        solver = FastDecoupledSolver(sys, formulation=FDLFFormulation.XB)
        converged = solver.solve(max_iter=35, tol=1e-4)

        assert converged is True, "FDLF-XB failed to converge on IEEE 14-bus"
        assert len(solver.bus_voltages) == 14
        assert solver.losses["active_mw"] > 0.0

    def test_dc_power_flow_ieee9(self):
        """Test Linearized DC Power Flow on IEEE 9-bus system."""
        sys = build_ieee_9bus_system()
        dc_solver = DCLoadFlowSolver(sys)
        converged = dc_solver.solve()

        assert converged is True
        assert dc_solver.iterations == 1, "DC power flow must solve in exactly 1 step"

        results = dc_solver.get_results()
        # All voltages must be 1.0 pu
        for bid, v_mag in results["voltage_magnitudes"].items():
            assert v_mag == 1.0, f"DC flow bus {bid} voltage magnitude must be 1.0 pu"

        # Active power generation must balance load
        total_gen_p = sum(b.generation_power.real for b in sys.buses.values())
        total_load_p = sum(b.load_power.real for b in sys.buses.values())
        # In DC flow, losses are 0, so gen = load
        assert total_gen_p == pytest.approx(total_load_p, rel=1e-3)

        # Line flows should be populated
        assert len(results["branch_flows"]) > 0
        for branch_id, bflow in results["branch_flows"].items():
            assert "p_from_mw" in bflow
            assert bflow["p_loss_mw"] == 0.0

    def test_engine_solver_type_dispatch(self):
        """Test PowerSystemEngine dispatches properly based on solver_type parameter."""
        sys = build_ieee_9bus_system()
        engine = PowerSystemEngine(sys)

        # 1. Dispatch Newton-Raphson (default)
        res_nr = engine.run_load_flow(solver_type="newton_raphson")
        assert res_nr["converged"] is True

        # 2. Dispatch Fast Decoupled
        res_fd = engine.run_load_flow(solver_type="fast_decoupled")
        assert res_fd["converged"] is True
        assert "Fast Decoupled" in res_fd.get("method", "")

        # 3. Dispatch DC Power Flow
        res_dc = engine.run_load_flow(solver_type="dc_flow")
        assert res_dc["converged"] is True
        assert "DC Linearized" in res_dc.get("method", "")
