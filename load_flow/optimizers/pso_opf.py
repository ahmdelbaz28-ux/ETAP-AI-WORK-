"""
load_flow/optimizers/pso_opf.py — Swarm-Intelligence Hybrid AC-OPF Engine.

Solves the genuine non-convex AC Optimal Power Flow problem with continuous
generator active powers (Pg) and bus voltage magnitudes (|Vg|).
Integrates Particle Swarm Optimization (PSO) with full AC power-balance
evaluations to eliminate artificial voltage clamping (1.0 pu) and minimize
generation costs, network transmission losses, and voltage deviations.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig
from load_flow.optimal_power_flow import GeneratorCost, OPFResult

logger = logging.getLogger(__name__)


class PSOOptimalPowerFlow:
    """Hybrid Particle Swarm Optimization AC-OPF solver.

    Decision vector x:
        [P_g1, ..., P_gn, V_g1, ..., V_gn]
    Optimizes fuel costs, network losses, and voltage profiles while enforcing
    physical AC grid constraints and equipment limits.
    """

    def __init__(
        self,
        ybus: np.ndarray,
        bus_ids: List[int],
        generator_costs: List[GeneratorCost],
        gen_buses: Dict[int, int],
        load_data: Dict[int, complex],
        voltage_limits: Optional[Dict[int, Tuple[float, float]]] = None,
        branch_limits: Optional[Dict[Tuple[int, int], float]] = None,
        base_mva: float = 100.0,
        swarm_size: int = 40,
        max_iter: int = 70,
        seed: int = 42,
        enable_reanalysis: bool = True,
    ) -> None:
        self.Ybus = np.asarray(ybus, dtype=complex)
        self.bus_ids = list(bus_ids)
        self.n_buses = len(bus_ids)
        self.bus_index = {bid: idx for idx, bid in enumerate(bus_ids)}

        self.generator_costs = {gc.generator_id: gc for gc in generator_costs}
        self.gen_ids = sorted(self.generator_costs.keys())
        self.n_gen = len(self.gen_ids)
        self.gen_buses = gen_buses
        self.load_data = load_data
        self.base_mva = base_mva
        self.enable_reanalysis = enable_reanalysis

        # Limits
        self.voltage_limits = voltage_limits or dict.fromkeys(bus_ids, (0.90, 1.10))
        self.branch_limits = branch_limits or {}

        # Swarm config
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

    def _evaluate_ac_state(
        self, p_gen_dict: Dict[int, float], v_gen_dict: Dict[int, float]
    ) -> Tuple[bool, np.ndarray, float, float]:
        """Evaluate AC voltage profile and exact losses for a generator dispatch."""
        n = self.n_buses
        V = np.ones(n, dtype=complex)

        # Set generator voltage magnitudes
        for gid, bid in self.gen_buses.items():
            if bid in self.bus_index and gid in v_gen_dict:
                idx = self.bus_index[bid]
                V[idx] = complex(v_gen_dict[gid], 0.0)

        # Injections in per-unit
        p_inj = np.zeros(n, dtype=np.float64)
        q_inj = np.zeros(n, dtype=np.float64)

        for bid in self.bus_ids:
            idx = self.bus_index[bid]
            s_load = self.load_data.get(bid, 0.0 + 0.0j)
            p_inj[idx] -= float(s_load.real) / self.base_mva
            q_inj[idx] -= float(s_load.imag) / self.base_mva

        for gid, bid in self.gen_buses.items():
            if bid in self.bus_index:
                idx = self.bus_index[bid]
                p_inj[idx] += float(p_gen_dict.get(gid, 0.0)) / self.base_mva

        # Solve polar power flow for voltage profile
        pv_indices = [
            self.bus_index[bid]
            for gid, bid in self.gen_buses.items()
            if bid in self.bus_index and self.bus_index[bid] != 0
        ]
        pq_indices = [i for i in range(n) if i != 0 and i not in pv_indices]

        converged = False
        for _ in range(25):
            I = self.Ybus.dot(V)
            S_calc = V * np.conj(I)
            P_calc = S_calc.real
            Q_calc = S_calc.imag

            d_p = p_inj - P_calc
            d_q = q_inj - Q_calc

            mismatches = [d_p[i] for i in pv_indices + pq_indices] + [d_q[i] for i in pq_indices]
            if not mismatches or float(np.max(np.abs(mismatches))) < 1e-4:
                converged = True
                break

            angles = np.angle(V)
            v_mag = np.abs(V)

            for i in pv_indices + pq_indices:
                B_ii = float(self.Ybus[i, i].imag)
                if abs(B_ii) > 1e-4:
                    angles[i] += float(d_p[i]) / (-B_ii * (v_mag[i] ** 2 + 1e-4))

            for i in pq_indices:
                B_ii = float(self.Ybus[i, i].imag)
                if abs(B_ii) > 1e-4:
                    v_mag[i] += float(d_q[i]) / (-B_ii * (v_mag[i] + 1e-4))
                    v_mag[i] = np.clip(v_mag[i], 0.8, 1.2)

            V = v_mag * np.exp(1j * angles)

        # Transmission losses = Real(V * conj(Y * V))
        I_final = self.Ybus.dot(V)
        losses_pu = max(0.0, float(np.sum((V * np.conj(I_final)).real)))
        losses_mw = losses_pu * self.base_mva
        total_p_gen = sum(p_gen_dict.values())

        return converged, V, total_p_gen, losses_mw

    def solve(
        self,
        weight_cost: float = 1.0,
        weight_losses: float = 2.0,
        weight_voltage: float = 10.0,
        enable_reanalysis: Optional[bool] = None,
    ) -> OPFResult:
        """Execute AC-OPF with Multi-Objective PSO and independent Newton-Raphson re-analysis (M1.7)."""
        reanalysis_flag = self.enable_reanalysis if enable_reanalysis is None else bool(enable_reanalysis)
        lb = []
        ub = []
        x0 = []

        # Decision variables: [P_g1..P_gn, V_g1..V_gn]
        for gid in self.gen_ids:
            gc = self.generator_costs[gid]
            lb.append(float(gc.p_min))
            ub.append(float(gc.p_max))
            x0.append(float(gc.p_min + gc.p_max) / 2.0)

        for gid in self.gen_ids:
            bid = self.gen_buses.get(gid, self.bus_ids[0])
            vmin, vmax = self.voltage_limits.get(bid, (0.95, 1.05))
            lb.append(float(vmin))
            ub.append(float(vmax))
            x0.append(1.0)

        lb_arr = np.array(lb, dtype=np.float64)
        ub_arr = np.array(ub, dtype=np.float64)
        x0_arr = np.array(x0, dtype=np.float64)

        total_load = sum(self.load_data.get(bid, 0.0).real for bid in self.bus_ids)
        base_cost = sum(
            self.generator_costs[gid].cost(self.generator_costs[gid].p_min) for gid in self.gen_ids
        ) + 1.0

        def objective(x: np.ndarray) -> float:
            p_gen = {self.gen_ids[i]: float(x[i]) for i in range(self.n_gen)}
            v_gen = {self.gen_ids[i]: float(x[self.n_gen + i]) for i in range(self.n_gen)}

            tot_gen = sum(p_gen.values())
            converged, V, _, losses = self._evaluate_ac_state(p_gen, v_gen)

            # Strict penalty for active power supply shortfall or extreme surplus
            penalty = 0.0
            if not converged:
                penalty += 5000.0

            power_imbalance = (tot_gen - (total_load + losses))
            if abs(power_imbalance) > 0.01:
                penalty += 10000.0 * (power_imbalance ** 2)

            # Fuel cost
            fuel_cost = sum(self.generator_costs[gid].cost(p_gen[gid]) for gid in self.gen_ids)

            # Voltage deviations
            v_dev = 0.0
            for bid in self.bus_ids:
                idx = self.bus_index[bid]
                v_mag = abs(V[idx])
                vmin, vmax = self.voltage_limits.get(bid, (0.90, 1.10))
                if v_mag < vmin:
                    penalty += 500.0 * (vmin - v_mag) ** 2
                elif v_mag > vmax:
                    penalty += 500.0 * (v_mag - vmax) ** 2
                v_dev += (v_mag - 1.0) ** 2

            # Branch flow limits penalty: |S_ij| = |v_i * (y_ij* * (v_i* - v_j*))| * S_base
            for (b1, b2), limit_mva in self.branch_limits.items():
                if b1 in self.bus_index and b2 in self.bus_index:
                    i, j = self.bus_index[b1], self.bus_index[b2]
                    if abs(self.Ybus[i, j]) > 1e-6:
                        v1, v2 = V[i], V[j]
                        y_ij = -self.Ybus[i, j]
                        i_ij = y_ij * (v1 - v2)
                        s_flow = abs(v1 * np.conj(i_ij)) * self.base_mva
                        if s_flow > limit_mva:
                            penalty += 2000.0 * (s_flow - limit_mva) ** 2

            # Generator Q limits penalty
            for gid in self.gen_ids:
                gc = self.generator_costs[gid]
                bid = self.gen_buses.get(gid, self.bus_ids[0])
                idx = self.bus_index[bid]
                q_calc = float((V[idx] * np.conj(self.Ybus.dot(V)[idx])).imag) * self.base_mva
                if q_calc < gc.q_min:
                    penalty += 500.0 * (gc.q_min - q_calc) ** 2
                elif q_calc > gc.q_max:
                    penalty += 500.0 * (q_calc - gc.q_max) ** 2

            f_cost = fuel_cost / base_cost
            f_loss = losses / (total_load + 1e-4)

            return float(
                weight_cost * f_cost
                + weight_losses * f_loss
                + weight_voltage * v_dev
                + penalty
            )

        # Set initial guess to proportionally match load
        if sum(x0[:self.n_gen]) > 0:
            scale = total_load / sum(x0[:self.n_gen])
            for i in range(self.n_gen):
                x0_arr[i] = np.clip(x0_arr[i] * scale, lb_arr[i], ub_arr[i])

        optimizer = ParticleSwarmOptimizer(self._pso_config)
        res = optimizer.optimize(fitness_fn=objective, lb=lb_arr, ub=ub_arr, initial_guess=x0_arr)

        best_x = res.best_position
        best_p_gen = {self.gen_ids[i]: float(best_x[i]) for i in range(self.n_gen)}
        best_v_gen = {self.gen_ids[i]: float(best_x[self.n_gen + i]) for i in range(self.n_gen)}

        if reanalysis_flag:
            # Independent Newton-Raphson re-analysis from load_flow.solver (M1.7)
            try:
                from load_flow.solver import solve_load_flow_sparse

                buses = []
                for bid in self.bus_ids:
                    idx = self.bus_index[bid]
                    is_slack = (idx == 0)
                    is_gen = any(self.gen_buses.get(gid) == bid for gid in self.gen_ids)
                    s_load = self.load_data.get(bid, 0.0 + 0.0j)

                    p_g = sum(best_p_gen.get(gid, 0.0) for gid in self.gen_ids if self.gen_buses.get(gid) == bid)
                    v_target = 1.0
                    for gid in self.gen_ids:
                        if self.gen_buses.get(gid) == bid and gid in best_v_gen:
                            v_target = best_v_gen[gid]
                            break

                    bus_type = "slack" if is_slack else ("pv" if is_gen else "pq")
                    buses.append({
                        "bus_id": bid,
                        "bus_type": bus_type,
                        "voltage_magnitude": float(v_target),
                        "voltage_angle": 0.0,
                        "p_generation": float(p_g) / self.base_mva,
                        "q_generation": 0.0,
                        "p_load": float(s_load.real) / self.base_mva,
                        "q_load": float(s_load.imag) / self.base_mva,
                        "v_scheduled": float(v_target),
                    })

                branches = []
                for i, b1 in enumerate(self.bus_ids):
                    for j, b2 in enumerate(self.bus_ids):
                        if i < j and abs(self.Ybus[i, j]) > 1e-6:
                            y_val = -self.Ybus[i, j]
                            branches.append({
                                "from_bus": b1,
                                "to_bus": b2,
                                "impedance": 1.0 / y_val,
                                "shunt_admittance": 0.0j,
                                "tap_ratio": 1.0,
                                "phase_shift": 0.0,
                            })

                nr_res = solve_load_flow_sparse(buses, branches, options={"max_iter": 50, "tol": 1e-5})
                if nr_res.get("converged"):
                    conv = True
                    final_V = np.array([nr_res["voltages"][bid] for bid in self.bus_ids], dtype=complex)
                    I_final = self.Ybus.dot(final_V)
                    final_losses = max(0.0, float(np.sum((final_V * np.conj(I_final)).real))) * self.base_mva
                    final_gen = sum(best_p_gen.values())
                else:
                    conv, final_V, final_gen, final_losses = self._evaluate_ac_state(best_p_gen, best_v_gen)
                    conv = False
            except Exception as nr_err:
                logger.warning("Independent Newton-Raphson re-analysis error: %s", nr_err)
                _, final_V, final_gen, final_losses = self._evaluate_ac_state(best_p_gen, best_v_gen)
                conv = False
        else:
            conv, final_V, final_gen, final_losses = self._evaluate_ac_state(best_p_gen, best_v_gen)

        bus_voltages = {bid: final_V[self.bus_index[bid]] for bid in self.bus_ids}
        generator_dispatch = {}
        for gid in self.gen_ids:
            p_val = best_p_gen[gid]
            bid = self.gen_buses.get(gid, self.bus_ids[0])
            idx = self.bus_index[bid]
            q_val = float((final_V[idx] * np.conj(self.Ybus.dot(final_V)[idx])).imag) * self.base_mva
            generator_dispatch[gid] = complex(round(p_val, 4), round(q_val, 4))

        # Branch flows
        branch_flows: Dict[Tuple[int, int], complex] = {}
        for i, b1 in enumerate(self.bus_ids):
            for j, b2 in enumerate(self.bus_ids):
                if i != j and abs(self.Ybus[i, j]) > 1e-6:
                    v1 = final_V[i]
                    v2 = final_V[j]
                    y_ij = -self.Ybus[i, j]
                    i_ij = y_ij * (v1 - v2)
                    s_ij = v1 * np.conj(i_ij) * self.base_mva
                    branch_flows[(b1, b2)] = s_ij

        violations: List[str] = []
        for bid in self.bus_ids:
            v_m = abs(bus_voltages[bid])
            vmin, vmax = self.voltage_limits.get(bid, (0.90, 1.10))
            if v_m < vmin or v_m > vmax:
                violations.append(f"Bus {bid} voltage {v_m:.4f} pu outside [{vmin}, {vmax}]")

        # Evaluate branch limits
        for (b1, b2), s_ij in branch_flows.items():
            limit_mva = self.branch_limits.get((b1, b2), self.branch_limits.get((b2, b1)))
            if limit_mva is not None and abs(s_ij) > limit_mva + 1e-3:
                violations.append(
                    f"Branch ({b1}, {b2}) flow {abs(s_ij):.2f} MVA exceeds limit {limit_mva:.2f} MVA"
                )

        # Evaluate generator Q limits
        for gid in self.gen_ids:
            gc = self.generator_costs[gid]
            q_val = generator_dispatch[gid].imag
            if q_val < gc.q_min - 1e-3 or q_val > gc.q_max + 1e-3:
                violations.append(
                    f"Generator {gid} Q {q_val:.2f} MVAR outside [{gc.q_min}, {gc.q_max}]"
                )

        if not reanalysis_flag:
            success = False
            convergence_status = "Independent Newton-Raphson re-analysis disabled (M1.7 certification failure)"
        else:
            success = bool(conv and res.converged and len(violations) == 0)
            if success:
                convergence_status = "Optimal dispatch found and verified with independent Newton-Raphson re-analysis"
            elif not conv:
                convergence_status = "Independent Newton-Raphson AC power flow failed to converge"
            elif len(violations) > 0:
                if any("voltage" in v.lower() for v in violations):
                    convergence_status = f"Voltage constraints violated: {'; '.join(violations)}"
                else:
                    convergence_status = f"Constraints violated: {'; '.join(violations)}"
            else:
                convergence_status = "PSO iteration limit reached without convergence"

        total_cost = sum(self.generator_costs[gid].cost(best_p_gen[gid]) for gid in self.gen_ids)

        return OPFResult(
            success=success,
            objective_value=float(total_cost),
            generator_dispatch=generator_dispatch,
            bus_voltages=bus_voltages,
            branch_flows=branch_flows,
            total_generation=float(final_gen),
            total_load=float(total_load),
            total_losses=float(final_losses),
            constraint_violations=violations,
            iterations=res.n_iterations,
            method_used="Particle Swarm Optimization (Hybrid AC-OPF)",
            convergence_status=convergence_status,
        )
