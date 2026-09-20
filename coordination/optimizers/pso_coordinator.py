"""
coordination/optimizers/pso_coordinator.py — Swarm-Optimized Protection Coordination.

Satisfies CoordinationEngineProtocol (engine/interfaces.py:103) using Particle
Swarm Optimization (PSO). Solves the continuous time-multiplier setting (TMS)
and pickup current optimization problem for upstream/downstream protective
relays under IEC 60255 / IEEE C37 standards, replacing naive linear sweeps.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from curves.curves import (
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
    calculate_iec_operating_time,
)
from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig

logger = logging.getLogger(__name__)


class PSOCoordinationEngine:
    """Protection coordination engine powered by Particle Swarm Optimization.

    Implements CoordinationEngineProtocol with continuous parameter exploration,
    simultaneous TMS and Pickup optimization, and strict grading margin compliance.
    """

    def __init__(
        self,
        default_margin_sec: float = 0.2,
        tms_search_min: float = 0.05,
        tms_search_max: float = 3.0,
        swarm_size: int = 40,
        max_iter: int = 60,
        seed: int = 42,
    ) -> None:
        self.default_margin_sec = default_margin_sec
        self.tms_search_min = tms_search_min
        self.tms_search_max = tms_search_max
        self.swarm_size = swarm_size
        self.max_iter = max_iter
        self.seed = seed
        self._pso_config = PSOConfig(
            swarm_size=self.swarm_size,
            max_iter=self.max_iter,
            seed=self.seed,
            tol=1e-6,
            patience=15,
        )

    def check_coordination(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
        fault_current: float,
    ) -> dict[str, Any]:
        """Check coordination between upstream and downstream relays for a given fault current."""
        t_up = upstream_relay.trip_time(fault_current)
        t_down = downstream_relay.trip_time(fault_current)

        margin = t_up - t_down
        coordinated = (t_down < t_up) and (margin >= self.default_margin_sec)

        return {
            "coordinated": coordinated,
            "upstream_time": t_up,
            "downstream_time": t_down,
            "margin": margin,
            "required_margin": self.default_margin_sec,
            "fault_current": fault_current,
        }

    def check_coordination_range(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
        fault_currents: list[float],
    ) -> list[dict[str, Any]]:
        """Check coordination over an array of fault currents."""
        return [
            self.check_coordination(upstream_relay, downstream_relay, If)
            for If in fault_currents
        ]

    def _calc_trip_time(self, tms: float, pickup: float, curve_type: str, current: float) -> float:
        """Compute trip time using IEC curve without mutating relay state."""
        res = calculate_iec_operating_time(
            i_fault=abs(current),
            i_setting=pickup,
            tms=tms,
            curve_type=curve_type,
            min_operating_time_s=MIN_OPERATING_TIME_S,
            max_multiplier=MAX_MULTIPLIER_OF_PICKUP,
        )
        return float(res["operating_time_s"])

    def suggest_tms_adjustment(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
        fault_currents: list[float],
        target_margin: float = 0.2,
    ) -> float | None:
        """Find optimal continuous TMS for upstream relay using PSO.

        Minimizes upstream clearing time while strictly enforcing selective grading
        margins (margin >= target_margin) across the entire fault current spectrum.
        """
        if not fault_currents:
            return None

        downstream_times = [
            downstream_relay.trip_time(If) for If in fault_currents
        ]
        pickup = getattr(upstream_relay, "Ip", getattr(upstream_relay, "ip", 1.0))
        curve_type = getattr(upstream_relay, "curve_type", "standard_inverse")

        def objective(x: np.ndarray) -> float:
            tms = x[0]
            violation = 0.0
            for i, If in enumerate(fault_currents):
                t_down = downstream_times[i]
                t_up = self._calc_trip_time(tms, pickup, curve_type, If)
                margin = t_up - t_down
                if margin < target_margin:
                    violation += (target_margin - margin)

            if violation > 0.0:
                return 1e5 + 1e4 * violation

            # Feasible: minimize upstream clearing times across all faults
            return float(tms)

        optimizer = ParticleSwarmOptimizer(self._pso_config)
        res = optimizer.optimize(
            fitness_fn=objective,
            lb=[self.tms_search_min],
            ub=[self.tms_search_max],
            initial_guess=np.array([getattr(upstream_relay, "TMS", getattr(upstream_relay, "tms", 0.5))]),
        )

        best_tms = float(res.best_position[0])

        # Verification check
        all_coordinated = True
        for i, If in enumerate(fault_currents):
            t_down = downstream_times[i]
            t_up = self._calc_trip_time(best_tms, pickup, curve_type, If)
            if (t_up - t_down) < (target_margin - 1e-4):
                all_coordinated = False
                break

        return best_tms if all_coordinated else None

    def optimize_coordination_2d(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
        fault_currents: list[float],
        target_margin: float = 0.2,
        pickup_min: Optional[float] = None,
        pickup_max: Optional[float] = None,
    ) -> dict[str, Any]:
        """Jointly optimize both TMS and Pickup current (2D search).

        Simultaneously explores the 2D space [TMS, Pickup] to produce the fastest
        possible fault clearance while maintaining full IEC 60255 selective grading.
        """
        if not fault_currents:
            raise ValueError("fault_currents list cannot be empty")

        current_pickup = getattr(upstream_relay, "Ip", getattr(upstream_relay, "ip", 1.0))
        p_min = pickup_min if pickup_min is not None else max(0.2, current_pickup * 0.5)
        p_max = pickup_max if pickup_max is not None else current_pickup * 2.5
        curve_type = getattr(upstream_relay, "curve_type", "standard_inverse")

        downstream_times = [
            downstream_relay.trip_time(If) for If in fault_currents
        ]

        def objective(x: np.ndarray) -> float:
            tms, pickup = x[0], x[1]
            violation = 0.0
            trip_time_sum = 0.0

            for i, If in enumerate(fault_currents):
                t_down = downstream_times[i]
                t_up = self._calc_trip_time(tms, pickup, curve_type, If)
                trip_time_sum += t_up

                margin = t_up - t_down
                if margin < target_margin:
                    violation += (target_margin - margin)

            if violation > 0.0:
                return 1e5 + 1e4 * violation

            # Feasible region: minimize total clearing time across faults
            return trip_time_sum

        optimizer = ParticleSwarmOptimizer(self._pso_config)
        res = optimizer.optimize(
            fitness_fn=objective,
            lb=[self.tms_search_min, p_min],
            ub=[self.tms_search_max, p_max],
            initial_guess=np.array([
                getattr(upstream_relay, "TMS", getattr(upstream_relay, "tms", 0.5)),
                current_pickup,
            ]),
        )

        opt_tms = float(res.best_position[0])
        opt_pickup = float(res.best_position[1])

        margins = []
        is_coordinated = True
        for i, If in enumerate(fault_currents):
            t_down = downstream_times[i]
            t_up = self._calc_trip_time(opt_tms, opt_pickup, curve_type, If)
            m = t_up - t_down
            margins.append(m)
            if m < target_margin - 1e-4:
                is_coordinated = False

        return {
            "optimal_tms": opt_tms,
            "optimal_pickup": opt_pickup,
            "coordinated": is_coordinated,
            "min_margin_sec": float(min(margins)),
            "avg_margin_sec": float(np.mean(margins)),
            "n_evaluations": res.n_evaluations,
            "convergence_history": res.convergence_history,
        }
