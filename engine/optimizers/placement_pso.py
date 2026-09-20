"""
engine/optimizers/placement_pso.py — Optimal Capacitor & DER Placement & Sizing via PSO.

Determines the optimal bus locations and capacities for shunt capacitor banks
and Distributed Energy Resources (DERs, e.g. Solar PV, BESS) to minimize
active transmission/distribution losses and improve network voltage profiles
within IEEE 1547 / IEEE 3002 standards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig

logger = logging.getLogger(__name__)


@dataclass
class PlacementResult:
    """Outcome of optimal capacitor or DER placement study."""

    optimal_allocations: Dict[int, float]  # bus_id -> capacity (kVAR or kW)
    initial_losses_mw: float
    optimized_losses_mw: float
    loss_reduction_pct: float
    voltage_profile_before: Dict[int, float]  # bus_id -> |V| in pu
    voltage_profile_after: Dict[int, float]  # bus_id -> |V| in pu
    min_voltage_before: float
    min_voltage_after: float
    estimated_investment_cost: float
    n_evaluations: int
    converged: bool


class OptimalPlacementPSO:
    """Swarm optimizer for optimal shunt capacitor and DER siting and sizing."""

    def __init__(
        self,
        ybus: np.ndarray,
        bus_ids: List[int],
        load_data: Dict[int, complex],
        candidate_buses: Optional[List[int]] = None,
        base_mva: float = 100.0,
        max_total_q_mvar: float = 10.0,
        max_per_bus_q_mvar: float = 5.0,
        cost_per_kvar: float = 30.0,  # Estimated $/kVAR installed
        swarm_size: int = 35,
        max_iter: int = 60,
        seed: int = 42,
    ) -> None:
        self.Ybus = np.asarray(ybus, dtype=complex)
        self.bus_ids = list(bus_ids)
        self.n_buses = len(bus_ids)
        self.bus_index = {bid: idx for idx, bid in enumerate(bus_ids)}
        self.load_data = load_data
        self.base_mva = base_mva
        self.max_total_q_mvar = max_total_q_mvar
        self.max_per_bus_q_mvar = max_per_bus_q_mvar
        self.cost_per_kvar = cost_per_kvar

        # Candidates: default to all PQ (load) buses
        self.candidate_buses = candidate_buses or [
            bid for bid in self.bus_ids if bid != self.bus_ids[0]
        ]
        self.n_candidates = len(self.candidate_buses)

        self.swarm_size = swarm_size
        self.max_iter = max_iter
        self.seed = seed
        self._pso_config = PSOConfig(
            swarm_size=self.swarm_size,
            max_iter=self.max_iter,
            seed=self.seed,
            tol=1e-5,
            patience=15,
        )

    def _solve_power_flow(self, q_injections_mvar: Dict[int, float]) -> Tuple[np.ndarray, float]:
        """Solve power flow for given reactive power injections (capacitors)."""
        n = self.n_buses
        V = np.ones(n, dtype=complex)

        p_inj = np.zeros(n, dtype=np.float64)
        q_inj = np.zeros(n, dtype=np.float64)

        for bid in self.bus_ids:
            idx = self.bus_index[bid]
            s_load = self.load_data.get(bid, 0.0 + 0.0j)
            p_inj[idx] -= float(s_load.real) / self.base_mva
            q_inj[idx] -= float(s_load.imag) / self.base_mva

        # Add capacitor injections (positive Q injection into bus)
        for bid, q_mvar in q_injections_mvar.items():
            if bid in self.bus_index:
                idx = self.bus_index[bid]
                q_inj[idx] += float(q_mvar) / self.base_mva

        pq_indices = [i for i in range(n) if i != 0]

        for _ in range(25):
            I = self.Ybus.dot(V)
            S_calc = V * np.conj(I)
            P_calc = S_calc.real
            Q_calc = S_calc.imag

            d_p = p_inj - P_calc
            d_q = q_inj - Q_calc

            mismatches = [d_p[i] for i in pq_indices] + [d_q[i] for i in pq_indices]
            if not mismatches or float(np.max(np.abs(mismatches))) < 1e-4:
                break

            angles = np.angle(V)
            v_mag = np.abs(V)

            for i in pq_indices:
                B_ii = float(self.Ybus[i, i].imag)
                if abs(B_ii) > 1e-4:
                    angles[i] += float(d_p[i]) / (-B_ii * (v_mag[i] ** 2 + 1e-4))
                    v_mag[i] += float(d_q[i]) / (-B_ii * (v_mag[i] + 1e-4))
                    v_mag[i] = np.clip(v_mag[i], 0.8, 1.2)

            V = v_mag * np.exp(1j * angles)

        I_final = self.Ybus.dot(V)
        losses_pu = max(0.0, float(np.sum((V * np.conj(I_final)).real)))
        losses_mw = losses_pu * self.base_mva

        return V, losses_mw

    def optimize_capacitor_placement(
        self,
        weight_loss: float = 10.0,
        weight_voltage: float = 50.0,
        weight_cost: float = 0.1,
    ) -> PlacementResult:
        """Run PSO to find optimal shunt capacitor sizes and locations."""
        # 1. Base case evaluation (zero compensation)
        v_base, loss_base = self._solve_power_flow({})
        v_base_dict = {bid: float(abs(v_base[self.bus_index[bid]])) for bid in self.bus_ids}

        # Decision variables: Q_c for each candidate bus [0, max_per_bus_q_mvar]
        lb = [0.0] * self.n_candidates
        ub = [self.max_per_bus_q_mvar] * self.n_candidates

        def objective(x: np.ndarray) -> float:
            q_dict = {self.candidate_buses[i]: float(x[i]) for i in range(self.n_candidates)}

            tot_q = sum(q_dict.values())
            penalty = 0.0
            if tot_q > self.max_total_q_mvar:
                penalty += 1000.0 * (tot_q - self.max_total_q_mvar) ** 2

            V, losses = self._solve_power_flow(q_dict)

            # Voltage deviations from 1.0 pu and bounds [0.95, 1.05]
            v_dev = 0.0
            for bid in self.bus_ids:
                v_mag = abs(V[self.bus_index[bid]])
                if v_mag < 0.95:
                    penalty += 500.0 * (0.95 - v_mag) ** 2
                elif v_mag > 1.05:
                    penalty += 500.0 * (v_mag - 1.05) ** 2
                v_dev += (v_mag - 1.0) ** 2

            # Normalized objective terms: all in [0, 1] range
            loss_norm = losses / (loss_base + 1e-4)
            cost_norm = tot_q / (self.max_total_q_mvar + 1e-4)

            return float(
                weight_loss * loss_norm
                + weight_voltage * v_dev
                + weight_cost * cost_norm
                + penalty
            )

        optimizer = ParticleSwarmOptimizer(self._pso_config)
        res = optimizer.optimize(fitness_fn=objective, lb=lb, ub=ub)

        best_q_raw = {self.candidate_buses[i]: float(res.best_position[i]) for i in range(self.n_candidates)}
        # Threshold out negligible capacitors (< 0.05 MVAR)
        best_q = {bid: round(val, 3) for bid, val in best_q_raw.items() if val >= 0.05}

        v_opt, loss_opt = self._solve_power_flow(best_q)
        v_opt_dict = {bid: float(abs(v_opt[self.bus_index[bid]])) for bid in self.bus_ids}

        loss_reduction = max(0.0, loss_base - loss_opt)
        reduction_pct = (loss_reduction / loss_base * 100.0) if loss_base > 0 else 0.0
        tot_kvar = sum(best_q.values()) * 1000.0
        invest_cost = tot_kvar * self.cost_per_kvar

        return PlacementResult(
            optimal_allocations=best_q,
            initial_losses_mw=round(loss_base, 4),
            optimized_losses_mw=round(loss_opt, 4),
            loss_reduction_pct=round(reduction_pct, 2),
            voltage_profile_before=v_base_dict,
            voltage_profile_after=v_opt_dict,
            min_voltage_before=round(min(v_base_dict.values()), 4),
            min_voltage_after=round(min(v_opt_dict.values()), 4),
            estimated_investment_cost=round(invest_cost, 2),
            n_evaluations=res.n_evaluations,
            converged=res.converged,
        )
