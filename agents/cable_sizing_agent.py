"""
AhmedETAP - Cable Sizing Agent
==================================================
Cable sizing and verification per IEC 60364 series.

Capabilities:
- Cable ampacity calculation based on installation method and grouping
- Voltage drop calculation for AC and DC systems
- Short-circuit temperature rating verification (IEC 60724 / IEC 60949)
- Cable recommendation with optimal cross-section selection

Standards:
- IEC 60364-5-52: Low-voltage electrical installations — Selection and
  erection of electrical equipment — Wiring systems
- IEC 60287: Electric cables — Calculation of the current rating
- IEC 60724: Short-circuit temperature limits
- IEC 60949: Calculation of thermally permissible short-circuit currents
"""

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, List

import numpy as np

from .orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference tables (IEC 60364-5-52 Table B.52.4 simplified)
# ---------------------------------------------------------------------------

# Base ampacity for Cu cables in air at 30 °C, 0.6/1 kV, single-core
# Key: cross-section in mm² -> current in A
_CU_XLPE_AIR_30C: Dict[float, float] = {
    1.5: 24,
    2.5: 33,
    4: 45,
    6: 58,
    10: 79,
    16: 107,
    25: 143,
    35: 176,
    50: 216,
    70: 278,
    95: 339,
    120: 392,
    150: 447,
    185: 509,
    240: 602,
    300: 697,
    400: 812,
}

# Base ampacity for Al cables in air at 30 °C, 0.6/1 kV, single-core
_AL_XLPE_AIR_30C: Dict[float, float] = {
    2.5: 26,
    4: 35,
    6: 46,
    10: 63,
    16: 85,
    25: 114,
    35: 141,
    50: 173,
    70: 222,
    95: 271,
    120: 314,
    150: 358,
    185: 408,
    240: 483,
    300: 559,
    400: 651,
}

# Resistance at 20 °C in Ω/km (copper)
_R20_CU: Dict[float, float] = {
    1.5: 12.1,
    2.5: 7.41,
    4: 4.61,
    6: 3.08,
    10: 1.83,
    16: 1.15,
    25: 0.727,
    35: 0.524,
    50: 0.387,
    70: 0.268,
    95: 0.193,
    120: 0.153,
    150: 0.124,
    185: 0.0991,
    240: 0.0754,
    300: 0.0601,
    400: 0.0470,
}

# Resistance at 20 °C in Ω/km (aluminium)
_R20_AL: Dict[float, float] = {
    2.5: 12.1,
    4: 7.41,
    6: 4.61,
    10: 3.08,
    16: 1.91,
    25: 1.20,
    35: 0.868,
    50: 0.641,
    70: 0.443,
    95: 0.320,
    120: 0.253,
    150: 0.206,
    185: 0.164,
    240: 0.125,
    300: 0.100,
    400: 0.0778,
}

# Standard cross-sections in mm² sorted ascending
_STANDARD_XSECTIONS: List[float] = sorted(_CU_XLPE_AIR_30C.keys())


class CableSizingAgent(BaseAgent):
    """
    Cable Sizing and Verification Agent (IEC 60364).

    Provides comprehensive cable selection including:
    - Ampacity derating for ambient temperature, grouping, and installation method
    - Voltage drop verification (AC three-phase, single-phase, and DC)
    - Short-circuit rating verification (adiabatic model per IEC 60949)
    - Optimal cable recommendation from standard cross-sections
    """

    prompt_handle = "cable_sizing_agent"

    def __init__(self) -> None:
        super().__init__("CableSizingAgent")
        self.standards = [
            "IEC 60364-5-52",
            "IEC 60287-1-1",
            "IEC 60724",
            "IEC 60949",
        ]

    # ------------------------------------------------------------------
    # Ampacity
    # ------------------------------------------------------------------

    def calculate_ampacity(
        self,
        cross_section_mm2: float,
        conductor_material: str = "Cu",
        insulation: str = "XLPE",
        installation_method: str = "in_air",
        ambient_temp_C: float = 30.0,
        n_circuits: int = 1,
        soil_resistivity_KmW: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate cable ampacity with derating factors per IEC 60364-5-52.

        Derating applied:
        1. Temperature correction factor (Table B.52.14)
        2. Grouping correction factor (Table B.52.17)
        3. Soil thermal resistivity factor (for direct burial)

        Parameters
        ----------
        cross_section_mm2 : int
            Conductor cross-section in mm².
        conductor_material : str
            ``'Cu'`` or ``'Al'``.
        insulation : str
            ``'XLPE'`` (90 °C max) or ``'PVC'`` (70 °C max).
        installation_method : str
            ``'in_air'``, ``'direct_buried'``, or ``'in_conduit'``.
        ambient_temp_C : float
            Ambient temperature in °C.
        n_circuits : int
            Number of circuits in the group (for grouping factor).
        soil_resistivity_KmW : float
            Soil thermal resistivity in K·m/W (only for direct burial).

        Returns
        -------
        Dict[str, Any]
            Ampacity result with all derating factors applied.
        """
        # Select base table
        if conductor_material == "Al":
            base_table = _AL_XLPE_AIR_30C
        else:
            base_table = _CU_XLPE_AIR_30C

        if cross_section_mm2 not in base_table:
            available = sorted(base_table.keys())
            return {
                "error": f"Cross-section {cross_section_mm2} mm² not in table. Available: {available}",
                "ampacity_A": 0.0,
            }

        I_base = base_table[cross_section_mm2]

        # Max conductor temperature
        max_temp = 90.0 if insulation.upper() == "XLPE" else 70.0

        # 1) Temperature correction factor (Table B.52.14 simplified)
        #    Ca = [(max_temp - ambient) / (max_temp - 30)]^0.5
        if ambient_temp_C >= max_temp:
            Ca = 0.0
        else:
            Ca = np.sqrt((max_temp - ambient_temp_C) / (max_temp - 30.0))

        # 2) Grouping correction factor (Table B.52.17 simplified)
        #    Approximate: Cg = 1 / sqrt(n) for n circuits touching
        if n_circuits <= 1:
            Cg = 1.0
        elif n_circuits <= 4:
            Cg = 0.80
        elif n_circuits <= 6:
            Cg = 0.70
        elif n_circuits <= 9:
            Cg = 0.60
        else:
            Cg = 0.50

        # 3) Soil thermal resistivity factor (for direct burial)
        if installation_method == "direct_buried":
            # Table B.52.15 simplified
            Cs_lookup = {
                0.5: 1.28,
                0.7: 1.15,
                1.0: 1.00,
                1.5: 0.89,
                2.0: 0.81,
                2.5: 0.76,
                3.0: 0.72,
            }
            # Interpolate
            rho_values = np.array(sorted(Cs_lookup.keys()))
            cs_values = np.array([Cs_lookup[r] for r in rho_values])
            Cs = float(np.interp(soil_resistivity_KmW, rho_values, cs_values))

            # Installation method base factor (buried rating ≈ 0.85 of in-air)
            method_factor = 0.85
        elif installation_method == "in_conduit":
            Cs = 1.0
            method_factor = 0.78  # Conduit reduces ampacity
        else:
            Cs = 1.0
            method_factor = 1.0

        I_derated = I_base * method_factor * Ca * Cg * Cs

        return {
            "cross_section_mm2": cross_section_mm2,
            "conductor_material": conductor_material,
            "insulation": insulation,
            "installation_method": installation_method,
            "base_ampacity_A": I_base,
            "temperature_correction_Ca": float(Ca),
            "grouping_correction_Cg": Cg,
            "soil_correction_Cs": Cs,
            "method_factor": method_factor,
            "ambient_temp_C": ambient_temp_C,
            "max_conductor_temp_C": max_temp,
            "n_circuits": n_circuits,
            "derated_ampacity_A": float(I_derated),
        }

    # ------------------------------------------------------------------
    # Voltage drop
    # ------------------------------------------------------------------

    def calculate_voltage_drop(
        self,
        load_current_A: float,
        cable_length_m: float,
        cross_section_mm2: float,
        conductor_material: str = "Cu",
        system_voltage_V: float = 400.0,
        power_factor: float = 0.85,
        n_phases: int = 3,
        frequency_Hz: float = 50.0,
    ) -> Dict[str, Any]:
        """
        Calculate voltage drop per IEC 60364-5-52 Annex G.

        For three-phase AC:
            ΔV = √3 × I × L × (R cos φ + X sin φ)

        For single-phase AC:
            ΔV = 2 × I × L × (R cos φ + X sin φ)

        For DC:
            ΔV = 2 × I × L × R

        Parameters
        ----------
        load_current_A : float
            Design load current in A.
        cable_length_m : float
            One-way cable length in metres.
        cross_section_mm2 : float
            Conductor cross-section in mm².
        conductor_material : str
            ``'Cu'`` or ``'Al'``.
        system_voltage_V : float
            Nominal system voltage in V (line-to-line for 3-phase).
        power_factor : float
            Load power factor (0 to 1).
        n_phases : int
            Number of phases (1 or 3).
        frequency_Hz : float
            System frequency in Hz.

        Returns
        -------
        Dict[str, Any]
            Voltage drop result in absolute and percentage terms.
        """
        # Resistance table selection
        r20_table = _R20_CU if conductor_material == "Cu" else _R20_AL

        if cross_section_mm2 not in r20_table:
            return {"error": f"Cross-section {cross_section_mm2} not found in resistance table"}

        R20 = r20_table[cross_section_mm2]  # Ω/km

        # Adjust resistance to operating temperature (≈ 80 °C for XLPE)
        alpha = 0.00393 if conductor_material == "Cu" else 0.00403  # temperature coefficient
        T_op = 80.0
        R_op = R20 * (1.0 + alpha * (T_op - 20.0))  # Ω/km

        # Reactance approximation (per IEC 60364-5-52 Annex G)
        # X ≈ 0.08 Ω/km for cables up to 300 mm² (conservative)
        X = 0.08  # Ω/km

        L_km = cable_length_m / 1000.0
        sin_phi = np.sqrt(1.0 - power_factor**2)

        if n_phases == 3:
            delta_V = np.sqrt(3) * load_current_A * L_km * (R_op * power_factor + X * sin_phi)
            reference_V = system_voltage_V
        elif n_phases == 1:
            delta_V = 2.0 * load_current_A * L_km * (R_op * power_factor + X * sin_phi)
            reference_V = (
                system_voltage_V / np.sqrt(3) if system_voltage_V > 250 else system_voltage_V
            )
        else:
            # DC
            delta_V = 2.0 * load_current_A * L_km * R_op
            reference_V = system_voltage_V

        delta_V_percent = (delta_V / reference_V) * 100.0 if reference_V > 0 else 0.0

        # Voltage at load end
        V_load = reference_V - delta_V

        return {
            "voltage_drop_V": float(delta_V),
            "voltage_drop_percent": float(delta_V_percent),
            "voltage_at_load_V": float(V_load),
            "resistance_per_km_ohm": R_op,
            "reactance_per_km_ohm": X,
            "cable_length_m": cable_length_m,
            "load_current_A": load_current_A,
            "power_factor": power_factor,
            "n_phases": n_phases,
            "system_voltage_V": system_voltage_V,
            "compliant_5pct": bool(delta_V_percent <= 5.0),
            "compliant_4pct": bool(delta_V_percent <= 4.0),
        }

    # ------------------------------------------------------------------
    # Short-circuit rating
    # ------------------------------------------------------------------

    def verify_short_circuit_rating(
        self,
        cross_section_mm2: float,
        conductor_material: str = "Cu",
        insulation: str = "XLPE",
        fault_current_kA: float = 25.0,
        fault_duration_s: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Verify cable short-circuit temperature rating per IEC 60949.

        The adiabatic short-circuit formula is:

            I²t = K² × S² × ln((θf + β) / (θi + β))

        where:
            K  = material constant
            S  = cross-section in mm²
            θf = final temperature (°C)
            θi = initial temperature (°C)
            β  = reciprocal of temperature coefficient (°C)

        Parameters
        ----------
        cross_section_mm2 : float
            Conductor cross-section in mm².
        conductor_material : str
            ``'Cu'`` or ``'Al'``.
        insulation : str
            ``'XLPE'`` or ``'PVC'``.
        fault_current_kA : float
            Prospective fault current in kA (rms).
        fault_duration_s : float
            Fault duration in seconds.

        Returns
        -------
        Dict[str, Any]
            Short-circuit verification result.
        """
        # Material constants (IEC 60949 Table 1)
        if conductor_material == "Cu":
            K = 226.0  # (As^0.5)/(mm²)
            beta = 234.5  # °C
        else:
            K = 148.0
            beta = 228.0

        # Temperature limits (IEC 60724)
        if insulation.upper() == "XLPE":
            theta_i = 90.0  # Initial (max operating) temp
            theta_f = 250.0  # Final (short-circuit limit) temp
        else:  # PVC
            theta_i = 70.0
            theta_f = 160.0

        S = cross_section_mm2
        I_fault = fault_current_kA * 1000.0  # Convert to A
        t = fault_duration_s

        # Permissible short-circuit energy (I²t)
        I2t_permissible = K**2 * S**2 * np.log((theta_f + beta) / (theta_i + beta))

        # Actual short-circuit energy
        I2t_actual = I_fault**2 * t

        # Permissible short-circuit current for the given duration
        I_permissible = np.sqrt(I2t_permissible / t) if t > 0 else float("inf")

        adequate = I2t_actual <= I2t_permissible

        return {
            "cross_section_mm2": cross_section_mm2,
            "conductor_material": conductor_material,
            "insulation": insulation,
            "fault_current_kA": fault_current_kA,
            "fault_duration_s": fault_duration_s,
            "actual_I2t_A2s": I2t_actual,
            "permissible_I2t_A2s": float(I2t_permissible),
            "permissible_fault_current_kA": float(I_permissible / 1000.0),
            "initial_temp_C": theta_i,
            "final_temp_limit_C": theta_f,
            "utilization_ratio": float(I2t_actual / I2t_permissible)
            if I2t_permissible > 0
            else float("inf"),
            "adequate": bool(adequate),
        }

    # ------------------------------------------------------------------
    # Cable recommendation
    # ------------------------------------------------------------------

    def recommend_cable(
        self,
        load_current_A: float,
        cable_length_m: float,
        system_voltage_V: float = 400.0,
        power_factor: float = 0.85,
        conductor_material: str = "Cu",
        insulation: str = "XLPE",
        installation_method: str = "in_air",
        ambient_temp_C: float = 40.0,
        n_circuits: int = 1,
        fault_current_kA: float = 25.0,
        fault_duration_s: float = 1.0,
        max_vdrop_percent: float = 5.0,
        n_phases: int = 3,
    ) -> Dict[str, Any]:
        """
        Recommend the smallest standard cable cross-section that satisfies
        all three criteria: ampacity, voltage drop, and short-circuit rating.

        Parameters
        ----------
        load_current_A : float
            Design current in A.
        cable_length_m : float
            Cable route length in metres.
        system_voltage_V : float
            Line-to-line voltage in V.
        power_factor : float
            Load power factor.
        conductor_material : str
            ``'Cu'`` or ``'Al'``.
        insulation : str
            ``'XLPE'`` or ``'PVC'``.
        installation_method : str
            ``'in_air'``, ``'direct_buried'``, ``'in_conduit'``.
        ambient_temp_C : float
            Ambient temperature in °C.
        n_circuits : int
            Number of parallel circuits in group.
        fault_current_kA : float
            Prospective fault current in kA.
        fault_duration_s : float
            Fault duration in seconds.
        max_vdrop_percent : float
            Maximum allowable voltage drop percentage.
        n_phases : int
            1 or 3 phase system.

        Returns
        -------
        Dict[str, Any]
            Optimal cable recommendation with full verification data.
        """
        base_table = _CU_XLPE_AIR_30C if conductor_material == "Cu" else _AL_XLPE_AIR_30C
        available_xsections = sorted(base_table.keys())

        candidate = None
        candidates_evaluated: List[Dict[str, Any]] = []

        for xsec in available_xsections:
            # 1. Ampacity check
            amp_result = self.calculate_ampacity(
                cross_section_mm2=xsec,
                conductor_material=conductor_material,
                insulation=insulation,
                installation_method=installation_method,
                ambient_temp_C=ambient_temp_C,
                n_circuits=n_circuits,
            )
            ampacity_ok = amp_result.get("derated_ampacity_A", 0) >= load_current_A

            # 2. Voltage drop check
            vd_result = self.calculate_voltage_drop(
                load_current_A=load_current_A,
                cable_length_m=cable_length_m,
                cross_section_mm2=xsec,
                conductor_material=conductor_material,
                system_voltage_V=system_voltage_V,
                power_factor=power_factor,
                n_phases=n_phases,
            )
            vdrop_ok = vd_result.get("voltage_drop_percent", 999) <= max_vdrop_percent

            # 3. Short-circuit check
            sc_result = self.verify_short_circuit_rating(
                cross_section_mm2=xsec,
                conductor_material=conductor_material,
                insulation=insulation,
                fault_current_kA=fault_current_kA,
                fault_duration_s=fault_duration_s,
            )
            sc_ok = sc_result.get("adequate", False)

            all_ok = ampacity_ok and vdrop_ok and sc_ok

            eval_entry = {
                "cross_section_mm2": xsec,
                "ampacity_ok": ampacity_ok,
                "vdrop_ok": vdrop_ok,
                "sc_ok": sc_ok,
                "all_criteria_met": all_ok,
                "derated_ampacity_A": amp_result.get("derated_ampacity_A", 0),
                "voltage_drop_percent": vd_result.get("voltage_drop_percent", 999),
                "sc_utilization": sc_result.get("utilization_ratio", 0),
            }
            candidates_evaluated.append(eval_entry)

            if all_ok and candidate is None:
                candidate = {
                    "recommended_cross_section_mm2": xsec,
                    "ampacity_result": amp_result,
                    "voltage_drop_result": vd_result,
                    "short_circuit_result": sc_result,
                }

        if candidate is None:
            return {
                "recommendation": "No standard cable satisfies all criteria",
                "candidates_evaluated": candidates_evaluated,
                "suggestion": "Consider parallel cables, larger ducts, or reduced load",
            }

        return {
            "recommendation": "Cable selected successfully",
            "recommended_cross_section_mm2": candidate["recommended_cross_section_mm2"],
            "ampacity_result": candidate["ampacity_result"],
            "voltage_drop_result": candidate["voltage_drop_result"],
            "short_circuit_result": candidate["short_circuit_result"],
            "candidates_evaluated": candidates_evaluated,
        }

    # ------------------------------------------------------------------
    # Agent execute
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute cable sizing analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        - ``'ampacity'``: Ampacity calculation
        - ``'voltage_drop'``: Voltage drop calculation
        - ``'short_circuit'``: Short-circuit verification
        - ``'recommend'``: Full cable recommendation
        - ``'full'``: All analyses (default)
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting cable sizing analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}
            p = task.parameters  # shorthand

            if analysis_type in ("ampacity", "full"):
                results["ampacity"] = self.calculate_ampacity(
                    cross_section_mm2=int(p.get("cross_section_mm2", 70)),
                    conductor_material=p.get("conductor_material", "Cu"),
                    insulation=p.get("insulation", "XLPE"),
                    installation_method=p.get("installation_method", "in_air"),
                    ambient_temp_C=float(p.get("ambient_temp_C", 40.0)),
                    n_circuits=int(p.get("n_circuits", 1)),
                    soil_resistivity_KmW=float(p.get("soil_resistivity_KmW", 1.0)),
                )

            if analysis_type in ("voltage_drop", "full"):
                results["voltage_drop"] = self.calculate_voltage_drop(
                    load_current_A=float(p.get("load_current_A", 200)),
                    cable_length_m=float(p.get("cable_length_m", 100)),
                    cross_section_mm2=int(p.get("cross_section_mm2", 70)),
                    conductor_material=p.get("conductor_material", "Cu"),
                    system_voltage_V=float(p.get("system_voltage_V", 400)),
                    power_factor=float(p.get("power_factor", 0.85)),
                    n_phases=int(p.get("n_phases", 3)),
                    frequency_Hz=float(p.get("frequency_Hz", 50)),
                )

            if analysis_type in ("short_circuit", "full"):
                results["short_circuit"] = self.verify_short_circuit_rating(
                    cross_section_mm2=int(p.get("cross_section_mm2", 70)),
                    conductor_material=p.get("conductor_material", "Cu"),
                    insulation=p.get("insulation", "XLPE"),
                    fault_current_kA=float(p.get("fault_current_kA", 25)),
                    fault_duration_s=float(p.get("fault_duration_s", 1.0)),
                )

            if analysis_type in ("recommend", "full"):
                results["recommendation"] = self.recommend_cable(
                    load_current_A=float(p.get("load_current_A", 200)),
                    cable_length_m=float(p.get("cable_length_m", 100)),
                    system_voltage_V=float(p.get("system_voltage_V", 400)),
                    power_factor=float(p.get("power_factor", 0.85)),
                    conductor_material=p.get("conductor_material", "Cu"),
                    insulation=p.get("insulation", "XLPE"),
                    installation_method=p.get("installation_method", "in_air"),
                    ambient_temp_C=float(p.get("ambient_temp_C", 40.0)),
                    n_circuits=int(p.get("n_circuits", 1)),
                    fault_current_kA=float(p.get("fault_current_kA", 25)),
                    fault_duration_s=float(p.get("fault_duration_s", 1.0)),
                    max_vdrop_percent=float(p.get("max_vdrop_percent", 5.0)),
                    n_phases=int(p.get("n_phases", 3)),
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # closest available StudyType
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "standards": self.standards,
                    "analysis_type": analysis_type,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Cable sizing analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Cable sizing analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """Validate cable sizing results against IEC criteria."""
        errors: List[str] = []

        amp = result.data.get("ampacity")
        if amp is not None:
            if amp.get("derated_ampacity_A", 0) <= 0:
                errors.append("Derated ampacity is zero or negative")

        vd = result.data.get("voltage_drop")
        if vd is not None:
            if not vd.get("compliant_5pct", True):
                errors.append(
                    f"Voltage drop {vd.get('voltage_drop_percent', 0):.2f}% exceeds 5% limit"
                )

        sc = result.data.get("short_circuit")
        if sc is not None:
            if not sc.get("adequate", True):
                errors.append(
                    f"Short-circuit rating inadequate: utilization ratio "
                    f"{sc.get('utilization_ratio', 0):.2f}"
                )

        rec = result.data.get("recommendation")
        if rec is not None and "No standard cable" in rec.get("recommendation", ""):
            errors.append("No suitable cable found meeting all criteria")

        result.validation_errors.extend(errors)
        return len(errors) == 0
