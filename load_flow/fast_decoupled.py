"""
load_flow/fast_decoupled.py — Fast Decoupled Load Flow (Stott & Alsac 1974).

Implements both canonical formulations:
1. XB formulation (Stott & Alsac standard):
   - B' ignores resistance and shunts (assumes high X/R).
   - B'' includes branch reactance and shunt susceptances.
2. BX formulation (Monticelli et al.):
   - B' accounts for series resistance.
   - B'' is simplified reactance matrix.

Provides rapid convergence with constant, pre-factorized LU decomposition matrices.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import linalg

from core_model.system import System
from load_flow.base_solver import AbstractLoadFlowSolver

logger = logging.getLogger(__name__)


class FDLFFormulation(str, Enum):
    XB = "XB"
    BX = "BX"


class FastDecoupledSolver(AbstractLoadFlowSolver):
    """
    Fast Decoupled Load Flow solver implementing XB and BX methods.
    """

    def __init__(
        self,
        system: System,
        formulation: FDLFFormulation = FDLFFormulation.XB,
        options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(system, options)
        self.formulation = formulation
        self.buses = list(system.buses.values())
        self.n = len(self.buses)
        self.bus_ids = [b.bus_id for b in self.buses]
        self.bus_index = {bid: idx for idx, bid in enumerate(self.bus_ids)}

        # Identify bus types
        self.slack_indices: List[int] = []
        self.pv_indices: List[int] = []
        self.pq_indices: List[int] = []

        for idx, b in enumerate(self.buses):
            btype = getattr(b, "bus_type", "pq").lower()
            if btype == "slack":
                self.slack_indices.append(idx)
            elif btype == "pv":
                self.pv_indices.append(idx)
            else:
                self.pq_indices.append(idx)

        # Non-slack indices for P-theta (PV + PQ)
        self.p_theta_indices = sorted(self.pv_indices + self.pq_indices)
        # PQ indices for Q-V
        self.q_v_indices = sorted(self.pq_indices)

        # Build Ybus for power mismatch calculations
        self.Ybus = system.get_ybus(seq="1")
        self.G = self.Ybus.real
        self.B = self.Ybus.imag

        # State vectors: V (magnitude) and theta (angles in rad)
        self.V = np.array([float(getattr(b, "voltage_magnitude", 1.0)) for b in self.buses], dtype=float)
        self.theta = np.array([float(getattr(b, "voltage_angle", 0.0)) for b in self.buses], dtype=float)

        # Scheduled generations and loads
        self.P_spec = np.zeros(self.n, dtype=float)
        self.Q_spec = np.zeros(self.n, dtype=float)
        for idx, b in enumerate(self.buses):
            gen = getattr(b, "generation_power", 0j)
            load = getattr(b, "load_power", 0j)
            self.P_spec[idx] = gen.real - load.real
            self.Q_spec[idx] = gen.imag - load.imag

        # Build and factorize B' and B'' matrices
        self._build_and_factorize_matrices()

    def _build_and_factorize_matrices(self) -> None:
        """Construct constant B' and B'' matrices and compute their LU factors."""
        n_p = len(self.p_theta_indices)
        n_q = len(self.q_v_indices)

        B_prime = np.zeros((n_p, n_p), dtype=float)
        B_double_prime = np.zeros((n_q, n_q), dtype=float)

        p_map = {orig_idx: sub_idx for sub_idx, orig_idx in enumerate(self.p_theta_indices)}
        q_map = {orig_idx: sub_idx for sub_idx, orig_idx in enumerate(self.q_v_indices)}

        # Collect branches: lines and transformers
        branches: List[Tuple[Any, Any, float, float, float]] = []
        for line in self.system.lines:
            branches.append((
                line.from_bus.bus_id,
                line.to_bus.bus_id,
                float(line.z1.real),
                float(line.z1.imag),
                float(getattr(line, "yshunt1", 0j).imag) if hasattr(line, "yshunt1") else 0.0,
            ))
        for xf in self.system.transformers:
            z = xf.get_impedance("1")
            y_sh = xf.get_shunt_admittance("1")
            branches.append((
                xf.from_bus.bus_id,
                xf.to_bus.bus_id,
                float(z.real),
                float(z.imag),
                float(y_sh.imag),
            ))

        for f_id, t_id, r, x, b_shunt in branches:
            u_orig = self.bus_index[f_id]
            v_orig = self.bus_index[t_id]
            z2 = r**2 + x**2
            if z2 <= 1e-12:
                continue

            # Invert reactances / susceptances
            b_line = x / z2
            b_inv_x = 1.0 / x if abs(x) > 1e-12 else b_line

            # 1. B' matrix (P-theta)
            # XB formulation neglects r (b_inv_x); BX uses b_line
            b_p_elem = b_inv_x if self.formulation == FDLFFormulation.XB else b_line
            if u_orig in p_map and v_orig in p_map:
                ui, vi = p_map[u_orig], p_map[v_orig]
                B_prime[ui, vi] -= b_p_elem
                B_prime[vi, ui] -= b_p_elem
                B_prime[ui, ui] += b_p_elem
                B_prime[vi, vi] += b_p_elem
            elif u_orig in p_map:
                ui = p_map[u_orig]
                B_prime[ui, ui] += b_p_elem
            elif v_orig in p_map:
                vi = p_map[v_orig]
                B_prime[vi, vi] += b_p_elem

            # 2. B'' matrix (Q-V, PQ buses only)
            # XB uses b_line + shunt; BX uses b_inv_x + shunt
            b_q_elem = b_line if self.formulation == FDLFFormulation.XB else b_inv_x
            if u_orig in q_map and v_orig in q_map:
                ui, vi = q_map[u_orig], q_map[v_orig]
                B_double_prime[ui, vi] -= b_q_elem
                B_double_prime[vi, ui] -= b_q_elem
                B_double_prime[ui, ui] += b_q_elem + 0.5 * b_shunt
                B_double_prime[vi, vi] += b_q_elem + 0.5 * b_shunt
            elif u_orig in q_map:
                ui = q_map[u_orig]
                B_double_prime[ui, ui] += b_q_elem + 0.5 * b_shunt
            elif v_orig in q_map:
                vi = q_map[v_orig]
                B_double_prime[vi, vi] += b_q_elem + 0.5 * b_shunt

        # Regularize to guarantee positive definiteness on isolated or small test cases
        for i in range(n_p):
            if abs(B_prime[i, i]) < 1e-6:
                B_prime[i, i] = 1.0
        for i in range(n_q):
            if abs(B_double_prime[i, i]) < 1e-6:
                B_double_prime[i, i] = 1.0

        # Compute LU factorizations
        self.lu_p = linalg.lu_factor(B_prime)
        self.lu_q = linalg.lu_factor(B_double_prime) if n_q > 0 else None

    def _calculate_power_injections(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute calculated active and reactive power injections P_calc, Q_calc."""
        v = self.V * np.exp(1j * self.theta)
        I = np.dot(self.Ybus, v)
        S = v * np.conj(I)
        return S.real, S.imag

    def solve(self, max_iter: int = 100, tol: float = 1e-5) -> bool:
        """Execute Fast Decoupled Load Flow alternating iterations."""
        self.iteration_log = []
        self.converged = False

        for it in range(1, max_iter + 1):
            P_calc, Q_calc = self._calculate_power_injections()

            # Active power mismatches
            dp = self.P_spec - P_calc
            dq = self.Q_spec - Q_calc

            max_p_err = np.max(np.abs(dp[self.p_theta_indices])) if self.p_theta_indices else 0.0
            max_q_err = np.max(np.abs(dq[self.q_v_indices])) if self.q_v_indices else 0.0
            max_mismatch = max(max_p_err, max_q_err)

            self.iteration_log.append({
                "iteration": it,
                "max_p_mismatch": float(max_p_err),
                "max_q_mismatch": float(max_q_err),
                "max_mismatch": float(max_mismatch),
            })

            if max_mismatch <= tol:
                self.converged = True
                self.iterations = it
                break

            # 1. P-theta step: solve B' * d_theta = dP / V
            if self.p_theta_indices:
                v_p = self.V[self.p_theta_indices]
                dp_scaled = dp[self.p_theta_indices] / v_p
                d_theta = linalg.lu_solve(self.lu_p, dp_scaled)
                self.theta[self.p_theta_indices] += d_theta

            # Recompute P/Q after angle update for improved stability
            _, Q_calc = self._calculate_power_injections()
            dq = self.Q_spec - Q_calc

            # 2. Q-V step: solve B'' * d_V = dQ / V
            if self.q_v_indices and self.lu_q is not None:
                v_q = self.V[self.q_v_indices]
                dq_scaled = dq[self.q_v_indices] / v_q
                d_v = linalg.lu_solve(self.lu_q, dq_scaled)
                self.V[self.q_v_indices] += d_v

        # Populate solved voltages: V * exp(j * theta)
        for idx, b in enumerate(self.buses):
            self.bus_voltages[b.bus_id] = self.V[idx] * np.exp(1j * self.theta[idx])

        self.compute_branch_flows_and_losses()
        return self.converged

    def get_results(self) -> Dict[str, Any]:
        """Return standardized load flow result dictionary."""
        return {
            "converged": self.converged,
            "iterations": self.iterations,
            "method": f"Fast Decoupled ({self.formulation.value})",
            "bus_voltages": self.bus_voltages,
            "voltage_magnitudes": {bid: abs(v) for bid, v in self.bus_voltages.items()},
            "voltage_angles_deg": {bid: float(np.degrees(np.angle(v))) for bid, v in self.bus_voltages.items()},
            "branch_flows": self.branch_flows,
            "losses": self.losses,
            "iteration_log": self.iteration_log,
        }
