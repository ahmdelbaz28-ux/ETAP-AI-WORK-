"""
motor_starting/engine.py — Dynamic Time-Domain Motor Starting Simulation Engine.

Simulates induction motor acceleration transients per IEEE 399 (Brown Book)
using 4th-Order Runge-Kutta (RK4) numerical integration of the mechanical
swing equation coupled to dynamic voltage dip and electrical network solver.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from motor_starting.motor_models import (
    DynamicMotorParams,
    InductionMotorDynamics,
    LoadProfile,
    MechanicalLoadModel,
    StartingMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class MotorStartingTrajectory:
    """Time-series trajectory of dynamic variables during motor starting."""

    time_s: List[float] = field(default_factory=list)
    speed_pu: List[float] = field(default_factory=list)
    speed_rpm: List[float] = field(default_factory=list)
    voltage_pu: List[float] = field(default_factory=list)
    current_pu: List[float] = field(default_factory=list)
    current_a: List[float] = field(default_factory=list)
    torque_elec_pu: List[float] = field(default_factory=list)
    torque_load_pu: List[float] = field(default_factory=list)
    bus_voltages_pu: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class MotorStartingResult:
    """Comprehensive outcome of dynamic motor starting simulation."""

    motor_id: str
    starting_method: str
    successful_start: bool
    acceleration_time_s: float
    max_voltage_dip_pct: float
    min_voltage_pu: float
    peak_starting_current_a: float
    peak_starting_current_pu: float
    final_slip: float
    final_speed_rpm: float
    stall_detected: bool
    status_message: str
    trajectory: MotorStartingTrajectory


class MotorStartingEngine:
    """
    4th-Order Runge-Kutta Dynamic Motor Starting Simulator (IEEE 399).
    """

    def __init__(
        self,
        motor_params: DynamicMotorParams,
        load_model: Optional[MechanicalLoadModel] = None,
        source_impedance: complex = complex(0.01, 0.05),
        source_voltage_pu: float = 1.0,
        starting_method: StartingMethod = StartingMethod.DOL,
        transition_time_s: float = 3.0,
        soft_start_ramp_time_s: float = 4.0,
        soft_start_initial_voltage: float = 0.35,
    ):
        self.params = motor_params
        self.motor = InductionMotorDynamics(motor_params)
        self.load = load_model or MechanicalLoadModel(profile=LoadProfile.QUADRATIC)
        self.z_source = source_impedance
        self.v_source = source_voltage_pu
        self.method = starting_method
        self.transition_time_s = transition_time_s
        self.soft_start_ramp_time_s = soft_start_ramp_time_s
        self.soft_start_v0 = soft_start_initial_voltage

        # Multi-bus network support
        self.adjacent_bus_impedances: Dict[str, complex] = {}

    def add_adjacent_bus(self, bus_id: str, transfer_impedance_ratio: complex):
        """Register an adjacent bus with its coupling ratio to motor bus voltage."""
        self.adjacent_bus_impedances[bus_id] = transfer_impedance_ratio

    def _get_applied_voltage_multiplier(self, t: float, speed_pu: float) -> float:
        """Calculate voltage scaling factor imposed by the starting method."""
        if self.method == StartingMethod.DOL:
            return 1.0

        elif self.method == StartingMethod.STAR_DELTA:
            # Star connection: 1 / sqrt(3) ~= 0.577 voltage until transition
            if t < self.transition_time_s and speed_pu < 0.85:
                return 1.0 / math.sqrt(3.0)
            return 1.0

        elif self.method == StartingMethod.AUTOTRANSFORMER_80:
            if t < self.transition_time_s and speed_pu < 0.85:
                return 0.80
            return 1.0

        elif self.method == StartingMethod.AUTOTRANSFORMER_65:
            if t < self.transition_time_s and speed_pu < 0.85:
                return 0.65
            return 1.0

        elif self.method == StartingMethod.SOFT_STARTER:
            # Linear ramp from v0 up to 1.0
            if t < self.soft_start_ramp_time_s:
                frac = t / self.soft_start_ramp_time_s
                return self.soft_start_v0 + (1.0 - self.soft_start_v0) * frac
            return 1.0

        elif self.method == StartingMethod.VFD:
            # Controlled frequency/voltage ramp
            if speed_pu < 0.95:
                return max(0.20, min(1.0, speed_pu + 0.15))
            return 1.0

        return 1.0

    def _compute_terminal_voltage_and_current(
        self, t: float, speed_pu: float
    ) -> Tuple[float, float, complex]:
        """
        Compute terminal voltage |V_t|, current magnitude in pu, and complex impedance.
        """
        slip = max(0.005, 1.0 - speed_pu)
        z_motor_nominal = self.motor.get_motor_impedance(slip)
        method_scale = self._get_applied_voltage_multiplier(t, speed_pu)

        # In star-delta or autotransformer, equivalent impedance is scaled:
        # Z_effective = Z_nominal / (method_scale^2)
        if method_scale < 1.0 and self.method in (
            StartingMethod.STAR_DELTA,
            StartingMethod.AUTOTRANSFORMER_80,
            StartingMethod.AUTOTRANSFORMER_65,
        ):
            z_motor = z_motor_nominal / (method_scale**2)
        else:
            z_motor = z_motor_nominal

        # Voltage divider across source impedance
        z_total = self.z_source + z_motor
        if abs(z_total) > 0:
            v_bus_complex = self.v_source * (z_motor / z_total)
            v_bus_mag = abs(v_bus_complex)
        else:
            v_bus_mag = self.v_source

        # Terminal voltage seen by the motor windings
        v_terminal = v_bus_mag * (method_scale if self.method == StartingMethod.SOFT_STARTER else 1.0)
        i_pu = v_bus_mag / abs(z_motor) if abs(z_motor) > 0 else 0.0

        return v_bus_mag, i_pu, z_motor

    def simulate(
        self,
        t_max_s: float = 12.0,
        dt_s: float = 0.005,
    ) -> MotorStartingResult:
        """
        Run 4th-order Runge-Kutta numerical integration of the swing equation.

        d(speed_pu)/dt = (Te - Tm) / (2H)
        where H = (J * w_sync^2) / (2 * P_base)
        """
        # Calculate inertia constant H in seconds
        w_sync = self.params.sync_omega
        p_base = self.params.rated_power_kw * 1000.0
        h_inertia = (self.params.total_j * (w_sync**2)) / (2.0 * p_base)
        two_h = max(2.0 * h_inertia, 0.2)  # Floor to prevent division by zero

        traj = MotorStartingTrajectory()
        traj.bus_voltages_pu[self.params.motor_id] = []
        for adj_bus in self.adjacent_bus_impedances:
            traj.bus_voltages_pu[adj_bus] = []

        t = 0.0
        w = 0.0  # Initial speed = 0 (locked rotor)
        steps = int(t_max_s / dt_s)

        min_v = 1.0
        max_i_a = 0.0
        max_i_pu = 0.0
        accel_time = -1.0
        stall_detected = False

        rated_speed_pu = self.params.rated_rpm / self.params.sync_rpm

        # Acceleration derivative function: f(t, w) = (Te - Tm) / (2H)
        def d_speed_dt(curr_t: float, curr_w: float) -> float:
            v_term, _, _ = self._compute_terminal_voltage_and_current(curr_t, curr_w)
            curr_slip = 1.0 - curr_w
            te = self.motor.calculate_developed_torque(curr_slip, v_term)
            tm = self.load.get_load_torque(curr_w)
            return (te - tm) / two_h

        for step in range(steps):
            v_bus, i_pu, _ = self._compute_terminal_voltage_and_current(t, w)
            slip = 1.0 - w
            te = self.motor.calculate_developed_torque(slip, v_bus)
            tm = self.load.get_load_torque(w)

            i_a = i_pu * self.params.rated_current_a
            min_v = min(min_v, v_bus)
            max_i_a = max(max_i_a, i_a)
            max_i_pu = max(max_i_pu, i_pu)

            # Record trajectory
            traj.time_s.append(round(t, 4))
            traj.speed_pu.append(round(w, 5))
            traj.speed_rpm.append(round(w * self.params.sync_rpm, 2))
            traj.voltage_pu.append(round(v_bus, 5))
            traj.current_pu.append(round(i_pu, 4))
            traj.current_a.append(round(i_a, 2))
            traj.torque_elec_pu.append(round(te, 4))
            traj.torque_load_pu.append(round(tm, 4))
            traj.bus_voltages_pu[self.params.motor_id].append(round(v_bus, 5))

            # Adjacent bus voltages based on transfer impedance
            for adj_bus, ratio in self.adjacent_bus_impedances.items():
                v_adj = 1.0 - abs(ratio) * (1.0 - v_bus)
                traj.bus_voltages_pu[adj_bus].append(round(v_adj, 5))

            # Check if accelerated to near rated operating speed (>= 95% of rated speed)
            if w >= 0.95 * rated_speed_pu and accel_time < 0:
                accel_time = t

            # Check for stall condition: Te <= Tm while w < 0.5 for > 2.0 seconds
            if t > 2.0 and w < 0.50 and (te - tm) <= 0.001:
                stall_detected = True
                break

            # RK4 Integration step
            k1 = d_speed_dt(t, w)
            k2 = d_speed_dt(t + 0.5 * dt_s, w + 0.5 * dt_s * k1)
            k3 = d_speed_dt(t + 0.5 * dt_s, w + 0.5 * dt_s * k2)
            k4 = d_speed_dt(t + dt_s, w + dt_s * k3)

            dw = (dt_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            w = max(0.0, min(1.0, w + dw))
            t += dt_s

            # Early exit if stable operating point reached
            if accel_time > 0 and t > accel_time + 1.0:
                break

        successful = (accel_time > 0) and not stall_detected
        max_dip_pct = (1.0 - min_v) * 100.0

        if stall_detected:
            msg = f"Motor STALLED during starting with method {self.method}. Accelerating torque collapsed below load torque."
        elif successful:
            msg = f"Motor successfully accelerated to rated speed in {accel_time:.2f}s. Max voltage dip: {max_dip_pct:.1f}%."
        else:
            msg = f"Motor acceleration incomplete within {t_max_s:.1f}s. Final speed: {w * self.params.sync_rpm:.0f} RPM."

        return MotorStartingResult(
            motor_id=self.params.motor_id,
            starting_method=self.method.value,
            successful_start=successful,
            acceleration_time_s=round(accel_time if successful else t_max_s, 3),
            max_voltage_dip_pct=round(max_dip_pct, 2),
            min_voltage_pu=round(min_v, 4),
            peak_starting_current_a=round(max_i_a, 2),
            peak_starting_current_pu=round(max_i_pu, 2),
            final_slip=round(1.0 - w, 4),
            final_speed_rpm=round(w * self.params.sync_rpm, 1),
            stall_detected=stall_detected,
            status_message=msg,
            trajectory=traj,
        )
