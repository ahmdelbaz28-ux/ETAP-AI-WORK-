"""
motor_starting/motor_models.py — Induction Motor & Mechanical Load Models (IEEE 399).

Provides:
- Induction motor equivalent electrical models
- Torque-speed curves (Thevenin equivalent & Kloss formulation)
- Mechanical load torque profiles (constant, quadratic fan/pump, linear)
- Starting methods: Direct-on-Line (DOL), Star-Delta, Soft-Starter, VFD
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class StartingMethod(str, Enum):
    DOL = "DOL"
    STAR_DELTA = "star_delta"
    SOFT_STARTER = "soft_starter"
    VFD = "VFD"
    AUTOTRANSFORMER_80 = "autotransformer_80"
    AUTOTRANSFORMER_65 = "autotransformer_65"


class LoadProfile(str, Enum):
    QUADRATIC = "quadratic"  # Centrifugal pump / fan (T = T0 + (1-T0)*w^2)
    CONSTANT = "constant"    # Hoist, conveyor, compressor (T = constant)
    LINEAR = "linear"        # Calenders, paper machines (T = T0 + k*w)


@dataclass
class DynamicMotorParams:
    """Detailed electrical and mechanical parameters for dynamic motor starting."""

    motor_id: str = "M1"
    rated_hp: float = 200.0
    rated_kv: float = 0.460  # 460 V line-to-line
    rated_rpm: float = 1780.0
    poles: int = 4
    frequency_hz: float = 60.0

    # Electrical parameters (per-unit on motor base)
    r_stator: float = 0.020     # Rs
    x_stator: float = 0.080     # Xs
    r_rotor: float = 0.025      # Rr
    x_rotor: float = 0.080      # Xr
    x_magnetizing: float = 3.00 # Xm

    # Performance characteristics
    rated_efficiency: float = 0.94
    rated_power_factor: float = 0.88
    locked_rotor_mult: float = 6.2  # LRA / FLA
    breakdown_torque_pu: float = 2.4 # T_max / T_rated
    starting_torque_pu: float = 1.5  # T_start / T_rated

    # Inertia
    inertia_j_motor: float = 3.5  # kg*m^2 (motor rotor inertia)
    inertia_j_load: float = 7.0   # kg*m^2 (driven equipment inertia)

    def __post_init__(self):
        self.sync_rpm = 120.0 * self.frequency_hz / self.poles
        self.sync_omega = self.sync_rpm * 2.0 * math.pi / 60.0
        self.rated_omega = self.rated_rpm * 2.0 * math.pi / 60.0
        self.rated_power_kw = self.rated_hp * 0.7457
        self.rated_kva = self.rated_power_kw / (self.rated_efficiency * self.rated_power_factor)
        self.rated_current_a = (self.rated_kva * 1000.0) / (math.sqrt(3.0) * self.rated_kv * 1000.0)
        self.rated_torque_nm = (self.rated_power_kw * 1000.0) / self.rated_omega
        self.total_j = self.inertia_j_motor + self.inertia_j_load


class InductionMotorDynamics:
    """Computes electromechanical torque and impedance across the slip range [1.0, 0.0]."""

    def __init__(self, params: DynamicMotorParams):
        self.p = params
        self._precompute_thevenin()

    def _precompute_thevenin(self):
        """Precompute Thevenin equivalent of stator and magnetizing branch."""
        zm = complex(0.0, self.p.x_magnetizing)
        zs = complex(self.p.r_stator, self.p.x_stator)
        # Zth = (Zs * Zm) / (Zs + Zm)
        zth = (zs * zm) / (zs + zm)
        self.r_th = zth.real
        self.x_th = zth.imag
        # Vth_ratio = |Zm / (Zs + Zm)|
        self.v_th_ratio = abs(zm / (zs + zm))

        # Slip at maximum torque: s_max = Rr / sqrt(Rth^2 + (Xth + Xr)^2)
        denom = math.sqrt(self.r_th**2 + (self.x_th + self.p.x_rotor)**2)
        self.s_max = self.p.r_rotor / denom if denom > 0 else 0.15

    def get_motor_impedance(self, slip: float) -> complex:
        """
        Calculate total motor equivalent impedance Z_motor(s) at given slip.
        """
        s = max(float(slip), 1e-4)
        # Rotor branch: Rr/s + j Xr
        z_rotor = complex(self.p.r_rotor / s, self.p.x_rotor)
        # Magnetizing branch: j Xm
        z_mag = complex(0.0, self.p.x_magnetizing)
        # Parallel combination of rotor and magnetizing branch
        z_parallel = (z_rotor * z_mag) / (z_rotor + z_mag)
        # Add stator impedance
        z_total = complex(self.p.r_stator, self.p.x_stator) + z_parallel
        return z_total

    def calculate_developed_torque(self, slip: float, v_terminal_pu: float) -> float:
        """
        Calculate electrical developed torque Te in per-unit using Thevenin model.
        Te is proportional to (v_terminal_pu)^2.
        """
        s = max(float(slip), 1e-4)
        v_eff = v_terminal_pu * self.v_th_ratio

        # 3-phase developed torque in per-unit:
        # Te = [Vth^2 * (Rr / s)] / [ (Rth + Rr/s)^2 + (Xth + Xr)^2 ]
        numerator = (v_eff**2) * (self.p.r_rotor / s)
        denominator = (self.r_th + self.p.r_rotor / s)**2 + (self.x_th + self.p.x_rotor)**2
        if denominator <= 0:
            return 0.0

        te_raw = numerator / denominator
        # Normalize to rated torque at rated slip
        s_rated = (self.p.sync_rpm - self.p.rated_rpm) / self.p.sync_rpm
        num_rated = (self.v_th_ratio**2) * (self.p.r_rotor / s_rated)
        den_rated = (self.r_th + self.p.r_rotor / s_rated)**2 + (self.x_th + self.p.x_rotor)**2
        te_rated = num_rated / den_rated if den_rated > 0 else 1.0

        return te_raw / te_rated


class MechanicalLoadModel:
    """Calculates mechanical resisting torque of the driven load."""

    def __init__(
        self,
        profile: LoadProfile = LoadProfile.QUADRATIC,
        t_breakaway_pu: float = 0.20,
        t_rated_pu: float = 1.0,
    ):
        self.profile = profile
        self.t_breakaway = t_breakaway_pu
        self.t_rated = t_rated_pu

    def get_load_torque(self, speed_pu: float) -> float:
        """
        Calculate mechanical load resisting torque in per-unit of motor rated torque.
        speed_pu = w / w_sync
        """
        w = max(0.0, min(float(speed_pu), 1.05))

        if self.profile == LoadProfile.CONSTANT:
            # Constant torque (e.g. positive displacement pump, extruder)
            return self.t_rated
        elif self.profile == LoadProfile.LINEAR:
            # Linear torque (e.g. friction calender)
            return self.t_breakaway + (self.t_rated - self.t_breakaway) * w
        else:
            # Quadratic torque (e.g. centrifugal fan, centrifugal pump, blower)
            return self.t_breakaway + (self.t_rated - self.t_breakaway) * (w**2)
