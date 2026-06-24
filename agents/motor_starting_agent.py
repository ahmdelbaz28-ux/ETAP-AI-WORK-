"""
AhmedETAP - Motor Starting Analysis Agent
=============================================================
Motor starting current, voltage dip, torque, and acceleration analysis
per IEEE 399 (Brown Book).

Capabilities:
- Motor starting current calculation (full voltage, reduced voltage)
- Voltage dip analysis at motor bus and adjacent buses
- Starting torque and acceleration time estimation
- Starting method comparison (DOL, star-delta, auto-transformer, VFD)
- NEMA motor starting code letter analysis

Standards:
- IEEE 399-1997: Recommended Practice for Industrial and Commercial
  Power System Analysis (Brown Book)
- NEMA MG-1: Motors and Generators
- IEC 60034: Rotating Electrical Machines
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017

UTC = UTC
from typing import Any, Dict, List, Optional

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NEMA starting code letters — locked-rotor kVA/hp ranges
# ---------------------------------------------------------------------------

_NEMA_CODE_LETTERS: Dict[str, tuple] = {
    "A": (0.0, 3.15),
    "B": (3.15, 3.55),
    "C": (3.55, 4.0),
    "D": (4.0, 4.5),
    "E": (4.5, 5.0),
    "F": (5.0, 5.6),
    "G": (5.6, 6.3),
    "H": (6.3, 7.1),
    "J": (7.1, 8.0),
    "K": (8.0, 9.0),
    "L": (9.0, 10.0),
    "M": (10.0, 11.2),
    "N": (11.2, 12.5),
    "P": (12.5, 14.0),
    "R": (14.0, 16.0),
    "S": (16.0, 18.0),
    "T": (18.0, 20.0),
    "U": (20.0, 22.4),
    "V": (22.4, float("inf")),
}

# Typical locked-rotor current multiplier (LRA/FLA) by starting method
_LR_MULTIPLIERS: Dict[str, float] = {
    "DOL": 6.0,  # Direct-On-Line
    "star_delta": 2.0,  # Star-Delta (current = 1/3 of DOL)
    "autotransformer_80": 3.84,  # Auto-transformer 80% tap
    "autotransformer_65": 2.54,  # Auto-transformer 65% tap
    "autotransformer_50": 1.50,  # Auto-transformer 50% tap
    "soft_starter": 3.0,  # Typical soft starter
    "VFD": 1.5,  # Variable Frequency Drive
}


class MotorStartingAgent(BaseAgent):
    """
    Motor Starting Analysis Agent (IEEE 399).

    Provides comprehensive motor starting analysis including:

    - Starting Current: Locked-rotor current calculation based on motor
      code letter, rated current, and starting method.  Supports DOL,
      star-delta, auto-transformer, soft starter, and VFD methods.
    - Voltage Dip: Per-unit voltage drop at the motor bus and adjacent
      buses during motor starting, using simplified impedance network.
    - Starting Torque: Torque at locked-rotor conditions and how it
      varies with the starting method (torque ∝ voltage²).
    - Acceleration Time: Time for the motor to reach rated speed,
      estimated from the average accelerating torque and total inertia.

    Key equations:

    Locked-rotor current:
        I_LR = code_kVA_per_hp × hp / (√3 × V_rated)

    Voltage dip (simplified):
        ΔV = (Z_source × I_start) / V_rated × 100%

    Acceleration time:
        t_acc = (2π × J_total × ΔN) / (30 × T_accel_avg)

    where J_total is the total moment of inertia (motor + load),
    ΔN is the speed change, and T_accel_avg is the average net torque.
    """

    prompt_handle = "motor_starting_agent"

    def __init__(self) -> None:
        super().__init__("MotorStartingAgent")
        self.standards = ["IEEE 399-1997", "NEMA MG-1", "IEC 60034"]
        self.system_frequency: float = 60.0  # Hz

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def calculate_starting_current(
        self,
        motor_hp: float,
        voltage_v: float,
        nema_code: str = "F",
        starting_method: str = "DOL",
        fla_a: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate motor starting (locked-rotor) current.

        Parameters
        ----------
        motor_hp : float
            Motor rated horsepower.
        voltage_v : float
            Motor rated voltage in volts (line-to-line).
        nema_code : str
            NEMA starting code letter (A–V), default 'F'.
        starting_method : str
            Starting method: 'DOL', 'star_delta',
            'autotransformer_80', 'autotransformer_65',
            'autotransformer_50', 'soft_starter', 'VFD'.
        fla_a : Optional[float]
            Motor full-load amperes. If not provided, estimated
            from hp and voltage.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'lra_a', 'lra_per_fla', 'starting_method',
            'nema_code', 'fla_a'.
        """
        # Estimate FLA if not provided (rule of thumb: ~1 A/hp at 460V)
        if fla_a is None:
            fla_a = motor_hp * 746.0 / (voltage_v * np.sqrt(3) * 0.85 * 0.88)

        # Get locked-rotor kVA/hp from NEMA code
        code = nema_code.upper()
        if code in _NEMA_CODE_LETTERS:
            lr_kva_per_hp = _NEMA_CODE_LETTERS[code][1]  # Use upper bound
        else:
            lr_kva_per_hp = 5.6  # Default to code F

        # DOL locked-rotor current (from NEMA code)
        lr_kva = lr_kva_per_hp * motor_hp
        lra_dol = lr_kva * 1000.0 / (np.sqrt(3) * voltage_v)

        # Apply starting method reduction factor
        # All methods scale from the DOL LRA computed above
        method_current_ratios: Dict[str, float] = {
            "DOL": 1.0,
            "star_delta": 1.0 / 3.0,  # Current = 1/3 of DOL line current
            "autotransformer_80": 0.64,  # 0.8² × DOL (tap ratio squared)
            "autotransformer_65": 0.42,  # 0.65² × DOL
            "autotransformer_50": 0.25,  # 0.5² × DOL
            "soft_starter": 0.50,  # Typical 50% of DOL
            "VFD": 0.25,  # VFD limits starting current to ~25% of DOL
        }

        current_ratio = method_current_ratios.get(starting_method, 1.0)
        lra_actual = lra_dol * current_ratio

        lra_per_fla = lra_actual / fla_a if fla_a > 0 else 0.0

        return {
            "lra_a": round(float(lra_actual), 2),
            "lra_per_fla": round(float(lra_per_fla), 2),
            "lra_dol_a": round(float(lra_dol), 2),
            "starting_method": starting_method,
            "nema_code": code,
            "fla_a": round(float(fla_a), 2),
            "lr_kva_per_hp": float(lr_kva_per_hp),
            "motor_hp": motor_hp,
            "voltage_v": voltage_v,
        }

    def calculate_voltage_dip(
        self,
        source_voltage_pu: float,
        source_impedance_pu: complex,
        motor_starting_current_a: float,
        motor_rated_voltage_v: float,
        motor_rated_mva: float,
        system_base_mva: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Calculate voltage dip during motor starting.

        Uses simplified voltage divider: the source impedance and the
        motor starting impedance form a voltage divider.

        Parameters
        ----------
        source_voltage_pu : float
            Source (utility or generator) voltage in per-unit.
        source_impedance_pu : complex
            Source Thevenin impedance in per-unit on system base.
        motor_starting_current_a : float
            Motor locked-rotor current in amperes.
        motor_rated_voltage_v : float
            Motor rated voltage in volts.
        motor_rated_mva : float
            Motor rated MVA.
        system_base_mva : float
            System base MVA for per-unit conversion.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'motor_bus_voltage_pu', 'voltage_dip_percent',
            'source_impedance_pu'.
        """
        # Motor starting impedance in per-unit
        # Z_motor_start = V_rated / (√3 × I_LR) converted to pu on system base
        z_motor_ohm = motor_rated_voltage_v / (np.sqrt(3) * motor_starting_current_a)
        z_base_ohm = (motor_rated_voltage_v**2) / (motor_rated_mva * 1e6)
        # Per-unit base conversion: Z_pu_new = Z_pu_old × (S_base_new / S_base_old)
        # when voltage bases are equal.  Here S_base_new = system_base_mva,
        # S_base_old = motor_rated_mva.
        z_motor_pu = z_motor_ohm / z_base_ohm * (system_base_mva / motor_rated_mva)

        # Voltage divider: V_motor = V_source × Z_motor / (Z_source + Z_motor)
        z_total = source_impedance_pu + complex(z_motor_pu, 0)
        motor_voltage_pu = source_voltage_pu * abs(z_motor_pu / z_total)

        voltage_dip_pct = (source_voltage_pu - motor_voltage_pu) / source_voltage_pu * 100.0

        return {
            "motor_bus_voltage_pu": round(float(motor_voltage_pu), 4),
            "voltage_dip_percent": round(float(voltage_dip_pct), 2),
            "source_voltage_pu": source_voltage_pu,
            "source_impedance_r_pu": round(float(source_impedance_pu.real), 6),
            "source_impedance_x_pu": round(float(source_impedance_pu.imag), 6),
            "motor_starting_impedance_pu": round(float(z_motor_pu), 6),
            "assessment": self._assess_voltage_dip(motor_voltage_pu),
        }

    def _assess_voltage_dip(self, v_pu: float) -> str:
        """Assess voltage dip severity per IEEE 399 guidelines."""
        if v_pu >= 0.95:
            return "Acceptable — voltage dip within normal limits"
        elif v_pu >= 0.90:
            return "Marginal — voltage dip noticeable but may be acceptable"
        elif v_pu >= 0.80:
            return "Concerning — may cause contactor drop-out or process disruption"
        elif v_pu >= 0.70:
            return "Significant — likely to cause contactor drop-out and process issues"
        else:
            return "Severe — motor may stall; reduced-voltage starting required"

    def calculate_starting_torque(
        self,
        rated_torque_nm: float,
        lra_per_fla: float,
        starting_method: str = "DOL",
        motor_bus_voltage_pu: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate starting torque considering voltage dip and method.

        Starting torque is proportional to the square of the applied
        voltage and the ratio of locked-rotor torque to rated torque.

        Parameters
        ----------
        rated_torque_nm : float
            Motor rated torque in Nm.
        lra_per_fla : float
            Ratio of locked-rotor current to full-load current.
        starting_method : str
            Starting method applied.
        motor_bus_voltage_pu : float
            Per-unit voltage at motor bus during starting.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'starting_torque_nm', 'torque_per_rated',
            'starting_method', 'voltage_factor'.
        """
        # For star-delta and autotransformer, voltage reduces proportionally
        # but torque reduces as voltage squared
        method_voltage_ratios: Dict[str, float] = {
            "DOL": 1.0,
            "star_delta": 1.0 / np.sqrt(3),  # Voltage reduced to 1/√3
            "autotransformer_80": 0.80,
            "autotransformer_65": 0.65,
            "autotransformer_50": 0.50,
            "soft_starter": 0.70,  # Typical
            "VFD": 1.0,  # VFD can provide full torque at low frequency
        }

        v_ratio = method_voltage_ratios.get(starting_method, 1.0)
        combined_voltage_factor = (v_ratio * motor_bus_voltage_pu) ** 2

        # Starting torque ratio: T_start/T_rated ≈ (V/V_rated)²
        # Typical LRT/FLT ratio is ~1.5-2.8 for standard motors
        # Using lra_per_fla as a proxy for the motor's starting characteristics
        # but torque scales with V² regardless of current ratio
        lrt_per_flt = lra_per_fla * 0.4  # Approximate LRT/FLT from LRA/FLA
        torque_ratio = lrt_per_flt * combined_voltage_factor
        starting_torque = rated_torque_nm * torque_ratio

        return {
            "starting_torque_nm": round(float(starting_torque), 2),
            "torque_per_rated": round(float(torque_ratio), 4),
            "starting_method": starting_method,
            "method_voltage_ratio": round(float(v_ratio), 4),
            "motor_bus_voltage_pu": motor_bus_voltage_pu,
            "voltage_factor": round(float(combined_voltage_factor), 4),
            "rated_torque_nm": rated_torque_nm,
        }

    def calculate_acceleration_time(
        self,
        j_total_kgm2: float,
        rated_speed_rpm: float,
        avg_accelerating_torque_nm: float,
    ) -> Dict[str, Any]:
        """
        Estimate motor acceleration time from standstill to rated speed.

        Parameters
        ----------
        j_total_kgm2 : float
            Total moment of inertia (motor + load) in kg·m².
        rated_speed_rpm : float
            Motor rated speed in RPM.
        avg_accelerating_torque_nm : float
            Average net (accelerating) torque over the speed range in Nm.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'acceleration_time_s', 'rated_speed_rpm',
            'j_total_kgm2'.
        """
        omega_rated = 2.0 * np.pi * rated_speed_rpm / 60.0
        if avg_accelerating_torque_nm > 0:
            t_acc = j_total_kgm2 * omega_rated / avg_accelerating_torque_nm
        else:
            t_acc = float("inf")

        return {
            "acceleration_time_s": round(float(t_acc), 2),
            "rated_speed_rpm": rated_speed_rpm,
            "j_total_kgm2": j_total_kgm2,
            "avg_accelerating_torque_nm": round(float(avg_accelerating_torque_nm), 2),
            "omega_rated_rad_s": round(float(omega_rated), 2),
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute motor starting analysis task.

        Dispatches to the appropriate analysis method based on
        ``task.parameters['analysis_type']`` which must be one of:
        ``'starting_current'``, ``'voltage_dip'``, ``'torque'``,
        ``'acceleration_time'``, or ``'full'`` (runs all).
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting motor starting analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}

            # Common parameters
            motor_hp = float(task.parameters.get("motor_hp", 100.0))
            voltage_v = float(task.parameters.get("voltage_v", 460.0))
            nema_code = task.parameters.get("nema_code", "F")
            starting_method = task.parameters.get("starting_method", "DOL")
            fla_a = task.parameters.get("fla_a")
            fla_val = float(fla_a) if fla_a is not None else None
            rated_rpm = float(task.parameters.get("rated_speed_rpm", 1800.0))

            # Always compute rated_torque so it is available for any analysis type
            rated_torque = (motor_hp * 746) / (rated_rpm * 2 * np.pi / 60) if rated_rpm > 0 else 0

            # --- Starting current ---
            if analysis_type in ("starting_current", "full"):
                sc_result = self.calculate_starting_current(
                    motor_hp=motor_hp,
                    voltage_v=voltage_v,
                    nema_code=nema_code,
                    starting_method=starting_method,
                    fla_a=fla_val,
                )
                results["starting_current"] = sc_result

            # --- Voltage dip ---
            if analysis_type in ("voltage_dip", "full"):
                source_v_pu = float(task.parameters.get("source_voltage_pu", 1.0))
                z_r = float(task.parameters.get("source_impedance_r_pu", 0.01))
                z_x = float(task.parameters.get("source_impedance_x_pu", 0.05))
                source_z_pu = complex(z_r, z_x)

                lra_a = results.get("starting_current", {}).get(
                    "lra_a",
                    fla_val * 6.0 if fla_val else motor_hp * 6.0,
                )
                motor_mva = motor_hp * 0.746 / 1000.0  # Approximate

                vd_result = self.calculate_voltage_dip(
                    source_voltage_pu=source_v_pu,
                    source_impedance_pu=source_z_pu,
                    motor_starting_current_a=lra_a,
                    motor_rated_voltage_v=voltage_v,
                    motor_rated_mva=motor_mva,
                )
                results["voltage_dip"] = vd_result

            # --- Starting torque ---
            if analysis_type in ("torque", "full"):
                rated_torque = float(task.parameters.get("rated_torque_nm", rated_torque))
                lra_per_fla = results.get("starting_current", {}).get("lra_per_fla", 6.0)
                motor_v_pu = results.get("voltage_dip", {}).get("motor_bus_voltage_pu", 0.85)

                tq_result = self.calculate_starting_torque(
                    rated_torque_nm=rated_torque,
                    lra_per_fla=lra_per_fla,
                    starting_method=starting_method,
                    motor_bus_voltage_pu=motor_v_pu,
                )
                results["starting_torque"] = tq_result

            # --- Acceleration time ---
            if analysis_type in ("acceleration_time", "full"):
                rated_torque = float(task.parameters.get("rated_torque_nm", rated_torque))
                j_total = float(task.parameters.get("j_total_kgm2", 10.0))
                avg_torque = results.get("starting_torque", {}).get(
                    "starting_torque_nm", rated_torque * 0.5
                )

                acc_result = self.calculate_acceleration_time(
                    j_total_kgm2=j_total,
                    rated_speed_rpm=rated_rpm,
                    avg_accelerating_torque_nm=avg_torque,
                )
                results["acceleration_time"] = acc_result

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.MOTOR_STARTING,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "analysis_type": analysis_type,
                    "standards": self.standards,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Motor starting analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Motor starting analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.MOTOR_STARTING,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate motor starting analysis results.

        Checks:
        - Starting current is positive and finite
        - Voltage dip is between 0 and 100%
        - Motor bus voltage is positive
        - Acceleration time is positive (or infinite for stall)
        """
        errors: List[str] = []

        sc_data = result.data.get("starting_current")
        if sc_data is not None:
            lra = sc_data.get("lra_a", 0.0)
            if lra <= 0:
                errors.append(f"Starting current is non-positive: {lra:.2f} A")
            lra_per = sc_data.get("lra_per_fla", 0.0)
            if lra_per < 1.0:
                errors.append(f"LRA/FLA ratio suspiciously low: {lra_per:.2f}")

        vd_data = result.data.get("voltage_dip")
        if vd_data is not None:
            dip = vd_data.get("voltage_dip_percent", 0.0)
            if dip < 0 or dip > 100:
                errors.append(f"Voltage dip out of range: {dip:.2f}%")
            v_pu = vd_data.get("motor_bus_voltage_pu", 1.0)
            if v_pu <= 0 or v_pu > 1.5:
                errors.append(f"Motor bus voltage out of range: {v_pu:.4f} pu")

        acc_data = result.data.get("acceleration_time")
        if acc_data is not None:
            t_acc = acc_data.get("acceleration_time_s", 0.0)
            if t_acc < 0:
                errors.append(f"Acceleration time is negative: {t_acc:.2f} s")

        result.validation_errors.extend(errors)
        return len(errors) == 0
