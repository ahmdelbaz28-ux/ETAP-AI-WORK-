"""
load_flow/base_solver.py — Standard Abstract Base Class for Load Flow Solvers.

Defines unified interface for all native power flow solvers:
- Newton-Raphson (dense and sparse)
- Fast Decoupled (XB and BX formulations)
- Linearized DC Power Flow
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from core_model.system import System

logger = logging.getLogger(__name__)


class AbstractLoadFlowSolver(ABC):
    """
    Abstract Base Class for all power flow solvers.

    Ensures consistent API, data structures, and result reporting across
    Newton-Raphson, Fast Decoupled, and DC flow engines.
    """

    def __init__(self, system: System, options: Optional[Dict[str, Any]] = None):
        self.system = system
        self.options = options or {}
        self.converged: bool = False
        self.iterations: int = 0
        self.iteration_log: List[Dict[str, Any]] = []

        # Complex voltage phasors at each bus: bus_id -> complex(V_mag, V_ang_rad)
        self.bus_voltages: Dict[int, complex] = {}
        # Power flows on branches: branch_id -> {from_bus, to_bus, P_from, Q_from, P_to, Q_to}
        self.branch_flows: Dict[int, Dict[str, Any]] = {}
        # System total losses: {'active_mw': float, 'reactive_mvar': float}
        self.losses: Dict[str, float] = {"active_mw": 0.0, "reactive_mvar": 0.0, "p_pu": 0.0, "q_pu": 0.0}

    @abstractmethod
    def solve(self, max_iter: int = 100, tol: float = 1e-6) -> bool:
        """
        Execute power flow solution.

        Parameters
        ----------
        max_iter : int
            Maximum number of iterations.
        tol : float
            Mismatch convergence tolerance.

        Returns
        -------
        bool
            True if converged within tolerance and max_iter, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_results(self) -> Dict[str, Any]:
        """
        Return standard formatted dictionary of load flow results.
        """
        raise NotImplementedError

    def compute_branch_flows_and_losses(self) -> None:
        """
        Standard calculation of line flows and system losses from solved voltages.
        """
        base_mva = getattr(self.system, "base_mva", 100.0)
        total_p_loss = 0.0
        total_q_loss = 0.0

        # Process lines
        for line in self.system.lines:
            f_id = line.from_bus.bus_id
            t_id = line.to_bus.bus_id
            if f_id not in self.bus_voltages or t_id not in self.bus_voltages:
                continue

            v_f = self.bus_voltages[f_id]
            v_t = self.bus_voltages[t_id]
            z_line = line.z1
            y_series = 1.0 / z_line if abs(z_line) > 1e-12 else 0.0
            y_shunt = getattr(line, "yshunt1", 0.0j) / 2.0

            i_ft = (v_f - v_t) * y_series + v_f * y_shunt
            i_tf = (v_t - v_f) * y_series + v_t * y_shunt

            s_ft = v_f * np.conj(i_ft)
            s_tf = v_t * np.conj(i_tf)

            p_loss_line = (s_ft.real + s_tf.real)
            q_loss_line = (s_ft.imag + s_tf.imag)
            total_p_loss += p_loss_line
            total_q_loss += q_loss_line

            self.branch_flows[line.line_id] = {
                "from_bus": f_id,
                "to_bus": t_id,
                "p_from_mw": s_ft.real * base_mva,
                "q_from_mvar": s_ft.imag * base_mva,
                "p_to_mw": s_tf.real * base_mva,
                "q_to_mvar": s_tf.imag * base_mva,
                "p_loss_mw": p_loss_line * base_mva,
                "q_loss_mvar": q_loss_line * base_mva,
            }

        # Process transformers
        if hasattr(self.system, "transformers"):
            for tx in self.system.transformers:
                f_id = tx.from_bus.bus_id
                t_id = tx.to_bus.bus_id
                if f_id not in self.bus_voltages or t_id not in self.bus_voltages:
                    continue

                v_f = self.bus_voltages[f_id]
                v_t = self.bus_voltages[t_id]
                z_tx = tx.z1
                tap = getattr(tx, "tap_ratio", 1.0) or 1.0
                y_tx = 1.0 / z_tx if abs(z_tx) > 1e-12 else 0.0

                i_ft = (v_f / tap - v_t) * y_tx / tap
                i_tf = (v_t - v_f / tap) * y_tx

                s_ft = v_f * np.conj(i_ft)
                s_tf = v_t * np.conj(i_tf)

                p_loss_tx = (s_ft.real + s_tf.real)
                q_loss_tx = (s_ft.imag + s_tf.imag)
                total_p_loss += p_loss_tx
                total_q_loss += q_loss_tx

                tx_key = f"xfmr_{tx.transformer_id}"
                self.branch_flows[tx_key] = {
                    "from_bus": f_id,
                    "to_bus": t_id,
                    "p_from_mw": s_ft.real * base_mva,
                    "q_from_mvar": s_ft.imag * base_mva,
                    "p_to_mw": s_tf.real * base_mva,
                    "q_to_mvar": s_tf.imag * base_mva,
                    "p_loss_mw": p_loss_tx * base_mva,
                    "q_loss_mvar": q_loss_tx * base_mva,
                }

        self.losses = {
            "active_mw": float(total_p_loss * base_mva),
            "reactive_mvar": float(total_q_loss * base_mva),
            "p_pu": float(total_p_loss),
            "q_pu": float(total_q_loss),
        }
