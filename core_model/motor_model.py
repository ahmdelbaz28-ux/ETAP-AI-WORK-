"""
Induction Motor Model for Power System Analysis

Supports:
- Motor starting current calculation
- Locked rotor current
- Acceleration time estimation
- Voltage dip contribution
- Short circuit contribution

Reference: IEEE Std 399 "IEEE Recommended Practice for Industrial and
Commercial Power Systems Analysis" (Brown Book)
"""

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class MotorParameters:
    """Induction motor electrical and mechanical parameters."""
    name: str = "Motor"
    rated_hp: float = 100.0         # Rated horsepower
    rated_kv: float = 0.46          # Rated voltage (kV)
    rated_rpm: float = 1800.0       # Rated speed (RPM)
    power_factor: float = 0.85      # Running power factor
    efficiency: float = 0.90        # Motor efficiency
    starting_pf: float = 0.20       # Starting power factor
    lr_current_multiplier: float = 6.0  # Locked rotor current / full load current
    inertia_constant_H: float = 0.5  # Inertia constant (seconds)
    x_d_prime: float = 0.20        # Transient reactance (per-unit)
    x_d_double_prime: float = 0.15  # Subtransient reactance (per-unit)
    r_stator: float = 0.01         # Stator resistance (per-unit)
    r_rotor: float = 0.02          # Rotor resistance (per-unit)
    slip_rated: float = 0.03       # Rated slip
    base_mva: float = 100.0        # System base MVA
    torque_speed_curve: dict = None # Optional: {slip: torque_pu}

    def __post_init__(self):
        """Calculate derived parameters."""
        self.rated_kw = self.rated_hp * 0.746
        self.rated_mva = self.rated_kw / (self.efficiency * self.power_factor * 1000)
        self.rated_current_a = (self.rated_mva * 1000) / (self.rated_kv * np.sqrt(3))
        self.sync_speed_rpm = 120 * 60 / max(1, round(self.rated_rpm / 3600) * 2) * 60
        if self.sync_speed_rpm == 0:
            self.sync_speed_rpm = 3600.0


class MotorModel:
    """
    Induction Motor Model for Power System Analysis.
    """

    def __init__(self, params: MotorParameters):
        """
        Initialize motor model.

        Parameters:
        params (MotorParameters): Motor parameters.
        """
        self.params = params
        self._calculate_derived()

    def _calculate_derived(self):
        """Calculate derived parameters in system per-unit."""
        p = self.params
        # Motor base MVA
        self.motor_base_mva = p.rated_mva
        # Per-unit on system base
        self.mva_ratio = self.motor_base_mva / p.base_mva
        # Impedances on system base
        self.x_d_prime_sys = p.x_d_prime / self.mva_ratio if self.mva_ratio > 0 else p.x_d_prime
        self.x_d_double_prime_sys = p.x_d_double_prime / self.mva_ratio if self.mva_ratio > 0 else p.x_d_double_prime

    def full_load_current(self, system_kv: float = None) -> float:
        """
        Calculate full load current in amps.

        Parameters:
        system_kv (float): System voltage in kV.

        Returns:
        float: Full load current in amps.
        """
        p = self.params
        kv = system_kv or p.rated_kv
        if kv <= 0:
            return 0.0
        return (p.rated_mva * 1000) / (kv * np.sqrt(3))

    def starting_current(self, system_kv: float = None) -> float:
        """
        Calculate starting (locked rotor) current in amps.

        Parameters:
        system_kv (float): System voltage in kV.

        Returns:
        float: Starting current in amps.
        """
        fla = self.full_load_current(system_kv)
        return fla * self.params.lr_current_multiplier

    def starting_current_pu(self) -> float:
        """
        Calculate starting current in per-unit on system base.

        Returns:
        float: Starting current in per-unit.
        """
        # I_start = V / X_d" (approximately)
        V = 1.0  # per-unit
        I_start = V / self.x_d_double_prime_sys
        return I_start * self.mva_ratio

    def locked_rotor_current_pu(self) -> complex:
        """
        Calculate locked rotor current in per-unit (complex).

        The locked rotor impedance is approximately:
        Z_lr = R_s + jX_lr

        Returns:
        complex: Locked rotor current in per-unit.
        """
        p = self.params
        # Locked rotor impedance (simplified)
        Z_lr = complex(p.r_stator, p.x_d_double_prime)
        if abs(Z_lr) > 0:
            I_lr = 1.0 / Z_lr  # at rated voltage
        else:
            I_lr = complex(0, 0)
        return I_lr * self.mva_ratio

    def running_current_pu(self) -> complex:
        """
        Calculate running current in per-unit (complex).

        Returns:
        complex: Running current in per-unit.
        """
        p = self.params
        # Running impedance
        pf_angle = np.arccos(p.power_factor)
        I_running = self.mva_ratio * (np.cos(pf_angle) - 1j * np.sin(pf_angle))
        return I_running

    def acceleration_time(self, load_torque_fraction: float = 0.3,
                          voltage_fraction: float = 1.0) -> float:
        """
        Estimate motor acceleration time.

        t_acc = (2 * H) / (T_motor_avg - T_load_avg)

        Where:
        H = inertia constant
        T_motor_avg = average motor torque during acceleration
        T_load_avg = average load torque during acceleration

        Parameters:
        load_torque_fraction (float): Load torque as fraction of rated torque.
        voltage_fraction (float): Applied voltage as fraction of rated.

        Returns:
        float: Acceleration time in seconds.
        """
        p = self.params
        H = p.inertia_constant_H

        # Average motor torque during acceleration (simplified)
        # Typically 1.0-1.5 pu of rated torque
        T_motor_avg = 1.2 * voltage_fraction**2  # Torque proportional to V^2

        # Average load torque (typically 0.3 for fans, 0.1 for pumps)
        T_load_avg = load_torque_fraction

        delta_T = T_motor_avg - T_load_avg
        if delta_T <= 0:
            return float('inf')  # Motor cannot accelerate

        t_acc = (2 * H) / delta_T
        return t_acc

    def voltage_dip_contribution(self, source_impedance: complex,
                                  system_kv: float = None) -> Tuple[float, float]:
        """
        Calculate voltage dip during motor starting.

        Parameters:
        source_impedance (complex): Source impedance in per-unit.
        system_kv (float): System voltage in kV.

        Returns:
        tuple: (voltage_dip_percent, voltage_at_motor_pu)
        """
        # Motor starting impedance
        p = self.params
        pf_angle = np.arccos(p.starting_pf)
        Z_motor_start = self.x_d_double_prime_sys / self.mva_ratio
        Z_motor = Z_motor_start * (np.cos(pf_angle) + 1j * np.sin(pf_angle))
        Z_motor = Z_motor / self.mva_ratio  # on system base

        # Voltage divider
        V_source = 1.0  # per-unit
        Z_total = source_impedance + Z_motor
        if abs(Z_total) > 0:
            V_motor = V_source * Z_motor / Z_total
        else:
            V_motor = V_source

        V_motor_mag = abs(V_motor)
        dip_percent = (1.0 - V_motor_mag) * 100.0

        return dip_percent, V_motor_mag

    def short_circuit_contribution(self, fault_type: str = 'three_phase',
                                    t: float = 0.0) -> complex:
        """
        Calculate motor contribution to short-circuit current.

        For induction motors, the contribution decays quickly.
        I_motor(t) = I_0 * exp(-t / T')

        Parameters:
        fault_type (str): Type of fault.
        t (float): Time after fault in seconds.

        Returns:
        complex: Motor short-circuit contribution in per-unit.
        """
        p = self.params

        # Initial subtransient current
        I_double_prime = 1.0 / complex(p.r_stator, p.x_d_double_prime)

        # Transient current
        I_prime = 1.0 / complex(p.r_stator, p.x_d_prime)

        # Time constants (simplified)
        T_double_prime = p.x_d_double_prime / (2 * np.pi * 60 * p.r_rotor)  # subtransient
        T_prime = p.x_d_prime / (2 * np.pi * 60 * p.r_rotor)  # transient

        # DC offset decay
        T_dc = p.x_d_double_prime / (2 * np.pi * 60 * p.r_stator)

        # Current at time t
        if t <= 0:
            I_motor = I_double_prime * self.mva_ratio
        else:
            I_ac = (I_double_prime - I_prime) * np.exp(-t / T_double_prime) + \
                   I_prime * np.exp(-t / T_prime)
            I_dc = np.sqrt(2) * I_double_prime * np.exp(-t / T_dc)
            I_motor = (I_ac + I_dc) * self.mva_ratio

        return I_motor

    def get_torque_speed(self, slip: float) -> float:
        """
        Calculate motor torque at a given slip using simplified equivalent circuit.

        T = V^2 * R2/s / (omega_s * ((R1 + R2/s)^2 + (X1 + X2)^2))

        Parameters:
        slip (float): Motor slip (0 to 1).

        Returns:
        float: Torque in per-unit of rated torque.
        """
        if slip <= 0:
            return 0.0

        p = self.params
        V = 1.0  # per-unit
        R1 = p.r_stator
        R2 = p.r_rotor
        X1 = p.x_d_double_prime * 0.5  # approximate
        X2 = p.x_d_double_prime * 0.5  # approximate
        omega_s = 2 * np.pi * 60  # synchronous speed

        R2_s = R2 / slip
        Z_total = complex(R1 + R2_s, X1 + X2)
        I = V / Z_total
        T = (abs(I)**2 * R2_s) / omega_s

        # Normalize to rated torque
        R2_rated = R2 / p.slip_rated
        Z_rated = complex(R1 + R2_rated, X1 + X2)
        I_rated = V / Z_rated
        T_rated = (abs(I_rated)**2 * R2_rated) / omega_s

        if T_rated > 0:
            return T / T_rated
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        p = self.params
        return {
            'name': p.name,
            'rated_hp': p.rated_hp,
            'rated_kv': p.rated_kv,
            'rated_rpm': p.rated_rpm,
            'power_factor': p.power_factor,
            'efficiency': p.efficiency,
            'lr_current_multiplier': p.lr_current_multiplier,
            'x_d_prime': p.x_d_prime,
            'x_d_double_prime': p.x_d_double_prime,
            'r_stator': p.r_stator,
            'r_rotor': p.r_rotor,
            'slip_rated': p.slip_rated,
            'base_mva': p.base_mva,
        }
