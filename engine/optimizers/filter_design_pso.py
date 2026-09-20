"""
engine/optimizers/filter_design_pso.py — Passive Harmonic Filter Design Optimizer.

Optimizes Single-Tuned and High-Pass Passive Harmonic Filters (R, L, C parameters)
using Particle Swarm Optimization to achieve full IEEE 519 compliance (THD_v <= 5%,
individual harmonic V_h <= 3%) while minimizing equipment footprint and MVAR cost.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig

logger = logging.getLogger(__name__)


@dataclass
class FilterDesignResult:
    """Outcome of IEEE 519 compliant harmonic filter optimization."""

    harmonic_order: int
    resistance_ohms: float
    inductance_mh: float
    capacitance_uf: float
    tuned_frequency_hz: float
    quality_factor: float
    q_reactive_kvar: float
    thd_v_before_pct: float
    thd_v_after_pct: float
    ieee_519_compliant: bool
    individual_harmonics_after_pct: Dict[int, float]
    estimated_filter_cost_usd: float
    converged: bool


class HarmonicFilterOptimizer:
    """Swarm optimizer for passive harmonic filter design complying with IEEE 519."""

    def __init__(
        self,
        nominal_voltage_kv: float = 13.8,
        system_frequency_hz: float = 60.0,
        short_circuit_mva: float = 250.0,
        harmonic_currents_a: Optional[Dict[int, float]] = None,
        swarm_size: int = 35,
        max_iter: int = 60,
        seed: int = 42,
    ) -> None:
        self.v_kv = nominal_voltage_kv
        self.v_phase_v = (nominal_voltage_kv * 1000.0) / math.sqrt(3.0)
        self.f0 = system_frequency_hz
        self.omega0 = 2.0 * math.pi * self.f0
        self.s_sc_mva = short_circuit_mva

        # System Thevenin impedance at fundamental
        # Z_sc = V^2 / S_sc
        self.z_sc_ohm = (nominal_voltage_kv ** 2) / short_circuit_mva
        self.x_sc_ohm = self.z_sc_ohm * 0.98  # predominantly inductive
        self.r_sc_ohm = self.z_sc_ohm * 0.20

        # Harmonic current injections: e.g. 5th, 7th, 11th, 13th from 6-pulse non-linear load
        self.harmonics = harmonic_currents_a or {
            5: 35.0,   # 5th harmonic current (Amperes)
            7: 22.0,   # 7th
            11: 12.0,  # 11th
            13: 8.0,   # 13th
        }

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

    def _calc_system_impedance(self, h: int) -> complex:
        """System Thevenin impedance at harmonic order h."""
        return complex(self.r_sc_ohm * math.sqrt(h), h * self.x_sc_ohm)

    def _calc_thd(self, filter_params: Optional[Tuple[float, float, float]] = None) -> Tuple[float, Dict[int, float]]:
        """Calculate Total Harmonic Distortion (THD_v) and individual harmonic voltages in percent."""
        v_h_dict: Dict[int, float] = {}
        sum_v_sq = 0.0

        for h, i_h in self.harmonics.items():
            z_sys = self._calc_system_impedance(h)

            if filter_params is not None:
                r_ohm, l_h, c_f = filter_params
                omega_h = 2.0 * math.pi * self.f0 * h
                # Filter impedance: Z_f = R + j(w_h * L - 1 / (w_h * C))
                x_c = 1.0 / (omega_h * c_f + 1e-12)
                x_l = omega_h * l_h
                z_filt = complex(r_ohm, x_l - x_c)

                # Parallel impedance of system and filter
                z_total = (z_sys * z_filt) / (z_sys + z_filt)
            else:
                z_total = z_sys

            v_h = abs(i_h * z_total)
            v_h_pct = (v_h / self.v_phase_v) * 100.0
            v_h_dict[h] = v_h_pct
            sum_v_sq += v_h_pct ** 2

        thd_pct = math.sqrt(sum_v_sq)
        return thd_pct, v_h_dict

    def design_filter_for_harmonic(
        self,
        target_harmonic: int = 5,
        target_q_kvar: float = 600.0,
    ) -> FilterDesignResult:
        """Design optimal single-tuned passive filter for specified harmonic order.

        Minimizes THD_v and individual harmonic voltage while ensuring tuned frequency
        accurately tracks target harmonic (typically 4.85x for 5th harmonic to prevent resonance).
        """
        thd_before, _ = self._calc_thd(None)

        # Baseline estimates from target Q
        # Q = V^2 / X_c => X_c = V^2 / Q
        q_phase = (target_q_kvar * 1000.0) / 3.0
        x_c_approx = (self.v_phase_v ** 2) / q_phase
        c_approx = 1.0 / (self.omega0 * x_c_approx)  # Farads

        # Resonance at h: omega_r^2 = 1 / (L * C) => L = 1 / ( (h * omega0)^2 * C )
        target_freq = target_harmonic * self.f0 * 0.98  # 2% de-tuned per IEEE 519 best practice
        omega_r = 2.0 * math.pi * target_freq
        l_approx = 1.0 / ((omega_r ** 2) * c_approx)

        # Decision variables: [R_ohm, L_h, C_farad]
        # Ranges:
        # R: [0.1, 10.0] Ohms
        # L: [0.5 * l_approx, 2.0 * l_approx]
        # C: [0.5 * c_approx, 2.0 * c_approx]
        lb = [0.1, l_approx * 0.4, c_approx * 0.4]
        ub = [8.0, l_approx * 2.5, c_approx * 2.5]
        x0 = [1.0, l_approx, c_approx]

        def objective(x: np.ndarray) -> float:
            r_ohm, l_h, c_f = float(x[0]), float(x[1]), float(x[2])

            thd_after, v_h_dict = self._calc_thd((r_ohm, l_h, c_f))

            # Tuned frequency
            f_tuned = 1.0 / (2.0 * math.pi * math.sqrt(max(1e-12, l_h * c_f)))
            f_err = abs(f_tuned - target_freq) / target_freq

            # IEEE 519 constraints: THD <= 5.0%, V_h <= 3.0%
            penalty = 0.0
            if thd_after > 5.0:
                penalty += 1000.0 * (thd_after - 5.0) ** 2

            for h, v_pct in v_h_dict.items():
                if v_pct > 3.0:
                    penalty += 500.0 * (v_pct - 3.0) ** 2

            # Quality factor Q = sqrt(L/C) / R (typical desired: 30 <= Q <= 80)
            q_factor = math.sqrt(l_h / (c_f + 1e-12)) / (r_ohm + 1e-6)
            q_penalty = 0.0
            if q_factor < 20.0:
                q_penalty += 10.0 * (20.0 - q_factor)
            elif q_factor > 100.0:
                q_penalty += 10.0 * (q_factor - 100.0)

            # Equipment cost proportional to C (kVAR) and L (Henry)
            q_kvar = (3.0 * (self.v_phase_v ** 2) * (self.omega0 * c_f)) / 1000.0

            return float(thd_after + 20.0 * f_err + 0.01 * q_penalty + 0.005 * q_kvar + penalty)

        optimizer = ParticleSwarmOptimizer(self._pso_config)
        res = optimizer.optimize(fitness_fn=objective, lb=lb, ub=ub, initial_guess=np.array(x0))

        best_r = float(res.best_position[0])
        best_l = float(res.best_position[1])
        best_c = float(res.best_position[2])

        thd_after, v_h_after = self._calc_thd((best_r, best_l, best_c))
        f_tuned = 1.0 / (2.0 * math.pi * math.sqrt(best_l * best_c))
        q_factor = math.sqrt(best_l / best_c) / best_r
        total_q_kvar = (3.0 * (self.v_phase_v ** 2) * (self.omega0 * best_c)) / 1000.0

        compliant = (thd_after <= 5.0) and all(v <= 3.0 for v in v_h_after.values())
        cost_usd = total_q_kvar * 35.0 + best_l * 1000.0 * 20.0  # Estimated component price

        return FilterDesignResult(
            harmonic_order=target_harmonic,
            resistance_ohms=round(best_r, 4),
            inductance_mh=round(best_l * 1000.0, 3),
            capacitance_uf=round(best_c * 1e6, 3),
            tuned_frequency_hz=round(f_tuned, 2),
            quality_factor=round(q_factor, 2),
            q_reactive_kvar=round(total_q_kvar, 2),
            thd_v_before_pct=round(thd_before, 2),
            thd_v_after_pct=round(thd_after, 2),
            ieee_519_compliant=compliant,
            individual_harmonics_after_pct={h: round(v, 2) for h, v in v_h_after.items()},
            estimated_filter_cost_usd=round(cost_usd, 2),
            converged=res.converged,
        )
