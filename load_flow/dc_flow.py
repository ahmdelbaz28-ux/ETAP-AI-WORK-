"""
load_flow/dc_flow.py — Linearized DC Power Flow Solver.

Provides rapid, non-iterative, guaranteed solution of active power flow:
  P_inj = B_bus * theta
  P_ij = (theta_i - theta_j) / x_ij

Assumptions (standard DC power flow):
- Voltage magnitudes are 1.0 pu for all buses (|V| = 1.0)
- Voltage angle differences across lines are small (sin(d_theta) ~= d_theta)
- Line resistance is negligible relative to reactance (R << X)
- Reactive power and shunt elements are neglected
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core_model.system import System
from load_flow.base_solver import AbstractLoadFlowSolver

logger = logging.getLogger(__name__)


class DCLoadFlowSolver(AbstractLoadFlowSolver):
    """
    Linearized DC Power Flow Solver.
    """

    def __init__(self, system: System, options: Optional[Dict[str, Any]] = None):
        super().__init__(system, options)
        self.buses = list(system.buses.values())
        self.n = len(self.buses)
        self.bus_ids = [b.bus_id for b in self.buses]
        self.bus_index = {bid: idx for idx, bid in enumerate(self.bus_ids)}

        # Find slack bus
        slack_found = False
        for idx, b in enumerate(self.buses):
            if getattr(b, "bus_type", "pq").lower() == "slack":
                self.slack_index = idx
                slack_found = True
                break
        if not slack_found:
            raise ValueError("No slack bus found in system for DC load flow analysis (fail-closed).")

        self.non_slack_indices = [i for i in range(self.n) if i != self.slack_index]

        # Scheduled active power injections: P_gen - P_load
        self.P_spec = np.zeros(self.n, dtype=float)
        for idx, b in enumerate(self.buses):
            gen_p = getattr(b, "generation_power", 0j).real
            load_p = getattr(b, "load_power", 0j).real
            self.P_spec[idx] = gen_p - load_p

        # State vectors
        self.V = np.ones(self.n, dtype=float)  # Flat voltage = 1.0 pu
        self.theta = np.zeros(self.n, dtype=float)  # Angles in rad

    def solve(self, max_iter: int = 1, tol: float = 1e-6) -> bool:
        """
        Solve linear DC power flow directly via matrix inversion.
        """
        # Build DC susceptance matrix B_bus: B_ij = -1/x_ij, B_ii = sum(1/x_ij)
        B_bus = np.zeros((self.n, self.n), dtype=float)

        # Collect branches: lines and transformers
        branches: List[Tuple[Any, Any, str, float, float, float]] = []
        for line in self.system.lines:
            branches.append((
                line.from_bus.bus_id,
                line.to_bus.bus_id,
                str(line.line_id),
                float(line.z1.imag),
                1.0,
                0.0,
            ))
        for xf in self.system.transformers:
            z = xf.get_impedance("1")
            tap = float(getattr(xf, "tap_ratio", 1.0) or 1.0)
            shift = float(getattr(xf, "phase_shift", 0.0) or 0.0)
            branches.append((
                xf.from_bus.bus_id,
                xf.to_bus.bus_id,
                f"xfmr_{xf.transformer_id}",
                float(z.imag),
                tap,
                shift,
            ))

        for f_id, t_id, branch_id, x, tap, shift in branches:
            u = self.bus_index[f_id]
            v = self.bus_index[t_id]
            x_eff = x * tap
            if abs(x_eff) > 1e-12:
                b_val = 1.0 / x_eff
                B_bus[u, v] -= b_val
                B_bus[v, u] -= b_val
                B_bus[u, u] += b_val
                B_bus[v, v] += b_val
                if abs(shift) > 1e-12:
                    p_shift = shift * b_val
                    self.P_spec[u] -= p_shift
                    self.P_spec[v] += p_shift

        # Extract reduced system without slack bus
        ns_idx = self.non_slack_indices
        if not ns_idx:
            # 1-bus system
            self.converged = True
            self.iterations = 1
            self.bus_voltages[self.buses[0].bus_id] = complex(1.0, 0.0)
            self.bus_generation = {self.buses[0].bus_id: float(getattr(self.buses[0], "load_power", 0j).real)}
            return True

        B_red = B_bus[np.ix_(ns_idx, ns_idx)]
        P_red = self.P_spec[ns_idx]

        # Regularize diagonal if isolated buses exist
        for i in range(B_red.shape[0]):
            if abs(B_red[i, i]) < 1e-8:
                B_red[i, i] = 1.0

        try:
            # Solve linear system B_red * theta_red = P_red
            theta_red = np.linalg.solve(B_red, P_red)
            for sub_i, orig_i in enumerate(ns_idx):
                self.theta[orig_i] = float(theta_red[sub_i])
            self.theta[self.slack_index] = 0.0  # Slack reference angle

            # Calculate slack active power injection to balance system:
            # P_slack = sum(B_slack, j * theta_j)
            p_slack_calc = float(np.dot(B_bus[self.slack_index, :], self.theta))
            self.P_spec[self.slack_index] = p_slack_calc

            # Record generation in results without mutating input system model in-place
            slack_bus = self.buses[self.slack_index]
            p_slack_gen = p_slack_calc + getattr(slack_bus, "load_power", 0j).real
            self.bus_generation = {}
            for b in self.buses:
                if b.bus_id == slack_bus.bus_id:
                    self.bus_generation[b.bus_id] = float(p_slack_gen)
                else:
                    self.bus_generation[b.bus_id] = float(getattr(b, "generation_power", 0j).real)

            self.converged = True
            self.iterations = 1
        except np.linalg.LinAlgError as err:
            logger.error("Singular B matrix in DC load flow: %s", err)
            self.converged = False
            return False

        # Populate solved voltages: 1.0 * exp(j * theta)
        for idx, b in enumerate(self.buses):
            self.bus_voltages[b.bus_id] = float(self.V[idx]) * np.exp(1j * self.theta[idx])

        # Compute branch flows
        base_mva = getattr(self.system, "base_mva", 100.0)
        self.branch_flows = {}
        for f_id, t_id, branch_id, x, tap, shift in branches:
            u = self.bus_index[f_id]
            v = self.bus_index[t_id]
            x_eff = x * tap
            if abs(x_eff) > 1e-12:
                # P_ij = (theta_u - theta_v - shift) / x_eff in pu
                p_flow_pu = (self.theta[u] - self.theta[v] - shift) / x_eff
                p_flow_mw = p_flow_pu * base_mva
                self.branch_flows[branch_id] = {
                    "from_bus": f_id,
                    "to_bus": t_id,
                    "p_from_mw": p_flow_mw,
                    "q_from_mvar": 0.0,
                    "p_to_mw": -p_flow_mw,
                    "q_to_mvar": 0.0,
                    "p_loss_mw": 0.0,  # DC flow is lossless (R=0)
                    "q_loss_mvar": 0.0,
                }

        self.losses = {"active_mw": 0.0, "reactive_mvar": 0.0, "p_pu": 0.0, "q_pu": 0.0}
        return True

    def get_results(self) -> Dict[str, Any]:
        """Return standardized DC load flow results."""
        return {
            "converged": self.converged,
            "iterations": self.iterations,
            "method": "DC Linearized Load Flow",
            "bus_voltages": self.bus_voltages,
            "voltage_magnitudes": dict.fromkeys(self.bus_ids, 1.0),
            "voltage_angles_deg": {bid: float(np.degrees(self.theta[self.bus_index[bid]])) for bid in self.bus_ids},
            "branch_flows": self.branch_flows,
            "losses": self.losses,
            "bus_generation": getattr(self, "bus_generation", {}),
            "iteration_log": [{"iteration": 1, "max_mismatch": 0.0}],
        }
