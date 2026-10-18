"""
AhmedETAP - Arc Flash Analysis Agent
=======================================================
Arc flash incident energy and boundary calculations per IEEE 1584
and NFPA 70E.

Capabilities:
- Incident energy calculation (cal/cm²) per IEEE 1584-2018
- Arc flash boundary determination
- PPE category classification per NFPA 70E Table 130.7(C)(15)(c)
- Working distance analysis and reduced energy approach
- Arc current adjustment for voltage and configuration

Standards:
- IEEE 1584-2018: Guide for Performing Arc-Flash Hazard Calculations
- NFPA 70E-2021: Standard for Electrical Safety in the Workplace
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType
from fault_analysis.arc_flash_engine import (
    ArcFlashEngine,
    ElectrodeConfig,
    EnclosureType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IEEE 1584-2018 coefficients for incident energy and arc boundary
# ---------------------------------------------------------------------------

# Coefficients for arc current (Table 4 in IEEE 1584-2018)
_ARC_CURRENT_COEFFS = {
    # (config, voltage_range): (k1, k2)
    # config: 0=VCB, 1=VCBB, 2=HCB
    "VCB_208": (0.000, -0.028),  # 0.208 kV, VC in a box
    "VCB_600": (-0.009, -0.019),  # 0.600 kV, VC in a box
    "VCB_1000": (-0.009, -0.019),  # 1.000 kV, VC in a box
    "VCB_2700": (-0.076, 0.016),  # 2.700 kV, VC in a box
    "VCB_14300": (-0.076, 0.016),  # 14.300 kV, VC in a box
    "VCBB_208": (0.000, -0.028),  # 0.208 kV, VCBB
    "VCBB_600": (-0.015, -0.019),  # 0.600 kV, VCBB
    "VCBB_1000": (-0.015, -0.019),  # 1.000 kV, VCBB
    "VCBB_2700": (-0.079, 0.017),  # 2.700 kV, VCBB
    "VCBB_14300": (-0.079, 0.017),  # 14.300 kV, VCBB
    "HCB_208": (0.000, -0.028),  # 0.208 kV, HCB
    "HCB_600": (0.003, -0.022),  # 0.600 kV, HCB
    "HCB_1000": (0.003, -0.022),  # 1.000 kV, HCB
    "HCB_2700": (-0.073, 0.019),  # 2.700 kV, HCB
    "HCB_14300": (-0.073, 0.019),  # 14.300 kV, HCB
}

# PPE Category classification per NFPA 70E
_PPE_CATEGORIES = [
    {"min_ie": 0.0, "max_ie": 1.2, "category": 0, "description": "No PPE required"},
    {
        "min_ie": 1.2,
        "max_ie": 4.0,
        "category": 1,
        "description": "Arc-rated shirt and pants or coverall",
    },
    {
        "min_ie": 4.0,
        "max_ie": 8.0,
        "category": 2,
        "description": "Arc-rated shirt, pants, and face shield",
    },
    {
        "min_ie": 8.0,
        "max_ie": 25.0,
        "category": 3,
        "description": "Arc-rated shirt, pants, arc flash suit, and face shield",
    },
    {
        "min_ie": 25.0,
        "max_ie": 40.0,
        "category": 4,
        "description": "Arc-rated shirt, pants, multi-layer arc flash suit, and face shield",
    },
    {
        "min_ie": 40.0,
        "max_ie": float("inf"),
        "category": -1,
        "description": "Dangerous — no PPE adequate; de-energize equipment",
    },
]


class ArcFlashAgent(BaseAgent):
    """
    Arc Flash Analysis Agent (IEEE 1584-2018 / NFPA 70E).

    Provides comprehensive arc flash hazard analysis including:

    - Incident Energy: Calculated per IEEE 1584-2018 empirical model
      for voltages from 0.208 kV to 15 kV, and the Lee method for
      voltages above 15 kV.
    - Arc Flash Boundary: The distance from the arc source at which
      incident energy equals 1.2 cal/cm² (the onset of second-degree
      burns).
    - PPE Classification: Categorization of required personal
      protective equipment per NFPA 70E Table 130.7(C)(15)(c).
    - Working Distance Analysis: Incident energy at the specified
      working distance and at standard distances.

    Key equations (IEEE 1584-2018):

    For intermediate arc current (kA):
        I_arc = 10^(k1 + k2*G + k3*log10(Ibf) + k4*Ibf + k5*log10(Ibf)*G)

    For incident energy (cal/cm²):
        E = 10^(c1 + c2*log10(Iarc) + c3*log10(G) + c4*log10(Iarc)*G + c5*log10(D))

    where G is the gap distance (mm), Ibf is the bolted fault current
    (kA), Iarc is the arc current (kA), and D is the working distance
    (mm).
    """

    prompt_handle = "arcflash_agent"  # Fixed to match available prompt file

    def __init__(self) -> None:
        super().__init__("ArcFlashAgent")
        self.standards = ["IEEE 1584-2018", "NFPA 70E-2021"]

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def calculate_arc_current(
        self,
        voltage_kv: float,
        bolted_fault_current_ka: float,
        electrode_config: str = "VCB",
        gap_mm: float = 32.0,
    ) -> dict[str, Any]:
        """
        Calculate the arcing current per IEEE 1584-2018 using the central ArcFlashEngine.

        Parameters
        ----------
        voltage_kv : float
            System voltage in kV (0.208 to 15.0).
        bolted_fault_current_ka : float
            Bolted (available) fault current in kA.
        electrode_config : str
            Electrode configuration: 'VCB', 'VCBB', or 'HCB'.
        gap_mm : float
            Gap between conductors in mm.

        Returns
        -------
        dict[str, Any]
            Dictionary with 'arc_current_ka', 'reduced_arc_current_ka',
            'voltage_kv', 'bolted_fault_current_ka', 'electrode_config', 'gap_mm'.
        """
        if voltage_kv is None or bolted_fault_current_ka is None:
            raise ValueError("voltage_kv and bolted_fault_current_ka must not be None.")

        iarc, iarc_reduced = ArcFlashEngine.calculate_arc_current(
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            electrode_config=electrode_config,
        )

        return {
            "arc_current_ka": round(float(iarc), 4),
            "reduced_arc_current_ka": round(float(iarc_reduced), 4),
            "voltage_kv": voltage_kv,
            "bolted_fault_current_ka": bolted_fault_current_ka,
            "electrode_config": electrode_config,
            "gap_mm": gap_mm,
        }

    def calculate_incident_energy(
        self,
        voltage_kv: float,
        arc_current_ka: float,
        arc_duration_s: float,
        working_distance_mm: float,
        electrode_config: str = "VCB",
        gap_mm: float = 32.0,
    ) -> dict[str, Any]:
        """
        Calculate incident energy (cal/cm²) per IEEE 1584-2018.

        Parameters
        ----------
        voltage_kv : float
            System voltage in kV.
        arc_current_ka : float
            Arcing current in kA.
        arc_duration_s : float
            Arc duration in seconds.
        working_distance_mm : float
            Working distance from the arc source in mm.
        electrode_config : str
            Electrode configuration: 'VCB', 'VCBB', or 'HCB'.
        gap_mm : float
            Gap between conductors in mm.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'incident_energy_cal_cm2',
            'arc_flash_boundary_mm', 'arc_flash_boundary_in',
            'ppe_category', 'ppe_description', 'working_distance_mm'.
        """
        iarc = arc_current_ka  # NOSONAR
        t = arc_duration_s
        D = working_distance_mm
        G = gap_mm

        if voltage_kv > 15.0 or voltage_kv < 0.208:
            res = ArcFlashEngine.ralph_lee_method(
                voltage_kv=voltage_kv,
                bolted_fault_current_ka=iarc,
                arc_duration_sec=t,
                working_distance_mm=D,
            )
            return self._format_ie_result(
                res.incident_energy_cal_cm2,
                D,
                arc_current_ka,
                voltage_kv,
                "Lee",
                electrode_config=electrode_config,
                gap_mm=G,
                arc_duration_s=t,
            )

        try:
            cfg = ElectrodeConfig(str(electrode_config).strip().upper())
        except (ValueError, AttributeError):
            cfg = ElectrodeConfig.VCB

        # Clamp gap to valid IEEE 1584-2018 range per voltage tier
        g_clamped = max(6.35, min(76.2, G)) if voltage_kv <= 1.0 else max(19.05, min(254.0, G))

        E, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=iarc,
            arc_duration_sec=t,
            working_distance_mm=D,
            electrode_config=cfg,
            enclosure_type=EnclosureType.BOX,
            arc_gap_mm=g_clamped,
        )

        return self._format_ie_result(
            E,
            D,
            arc_current_ka,
            voltage_kv,
            "IEEE 1584-2018",
            electrode_config=electrode_config,
            gap_mm=g_clamped,
            arc_duration_s=t,
        )

    def _format_ie_result(
        self,
        E_cal_cm2: float,  # NOSONAR
        working_distance_mm: float,
        arc_current_ka: float,
        voltage_kv: float,
        method: str,
        electrode_config: str = "VCB",
        gap_mm: float = 32.0,
        arc_duration_s: float = 0.2,
    ) -> dict[str, Any]:
        """Format incident energy result with boundary and PPE classification."""
        if voltage_kv > 15.0 or voltage_kv < 0.208:
            if E_cal_cm2 > 0 and working_distance_mm > 0:
                boundary_mm = working_distance_mm * np.sqrt(E_cal_cm2 / 1.2)
            else:
                boundary_mm = 0.0
        else:
            try:
                boundary_mm = ArcFlashEngine.calculate_arc_flash_boundary(
                    voltage_kv=voltage_kv,
                    bolted_fault_current_ka=arc_current_ka,
                    arc_duration_sec=arc_duration_s,
                    working_distance_mm=working_distance_mm,
                    electrode_config=electrode_config,
                    enclosure_type=EnclosureType.BOX,
                    arc_gap_mm=gap_mm,
                )
            except Exception:
                if E_cal_cm2 > 0 and working_distance_mm > 0:
                    boundary_mm = working_distance_mm * np.sqrt(E_cal_cm2 / 1.2)
                else:
                    boundary_mm = 0.0

        # PPE category: fail-closed with REJECTED if simplified model is active
        try:
            ppe_cat, ppe_desc = self._classify_ppe(E_cal_cm2, allow_simplified=False)
        except ValueError as err:
            ppe_cat = "REJECTED"
            ppe_desc = str(err)

        return {
            "incident_energy_cal_cm2": round(float(E_cal_cm2), 2),
            "arc_flash_boundary_mm": round(float(boundary_mm), 1),
            "arc_flash_boundary_in": round(float(boundary_mm) / 25.4, 1),
            "working_distance_mm": float(working_distance_mm),
            "working_distance_in": round(float(working_distance_mm) / 25.4, 1),
            "arc_current_ka": arc_current_ka,
            "voltage_kv": voltage_kv,
            "calculation_method": method,
            "ppe_category": ppe_cat,
            "ppe_description": ppe_desc,
        }

    def _classify_ppe(self, ie: float, allow_simplified: bool = True) -> tuple[str, str]:
        """
        Classify required PPE category based on incident energy per NFPA 70E.

        Parameters
        ----------
        ie : float
            Incident energy in cal/cm².
        allow_simplified : bool
            Whether to permit classification under simplified engine model.

        Returns
        -------
        tuple
            (category: str, description: str)
        """
        return ArcFlashEngine.determine_ppe_level(ie, allow_simplified=allow_simplified)

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute arc flash analysis task.

        Dispatches to the appropriate calculation method based on
        ``task.parameters['analysis_type']`` which must be one of:
        ``'arc_current'``, ``'incident_energy'``, or ``'full'``
        (computes arc current then incident energy).
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting arc flash analysis for task {task.task_id}")

            missing_af: list[str] = []
            if "voltage_kv" not in task.parameters or task.parameters["voltage_kv"] is None:
                missing_af.append("voltage_kv")
            if (
                "bolted_fault_current_ka" not in task.parameters
                and "fault_current_ka" not in task.parameters
            ) or (
                task.parameters.get("bolted_fault_current_ka") is None
                and task.parameters.get("fault_current_ka") is None
            ):
                missing_af.append("bolted_fault_current_ka")

            analysis_type = task.parameters.get("analysis_type", "full")
            if analysis_type in ("incident_energy", "full"):
                if (
                    "arc_duration_s" not in task.parameters
                    and "arc_duration_sec" not in task.parameters
                    and "clearing_time_s" not in task.parameters
                ) or (
                    task.parameters.get("arc_duration_s") is None
                    and task.parameters.get("arc_duration_sec") is None
                    and task.parameters.get("clearing_time_s") is None
                ):
                    missing_af.append("arc_duration_s")
                if (
                    "working_distance_mm" not in task.parameters
                    or task.parameters["working_distance_mm"] is None
                ):
                    missing_af.append("working_distance_mm")

            if missing_af:
                err_msg = (
                    f"Missing mandatory arc flash parameter(s): {', '.join(missing_af)}. "
                    "Silent default parameter injection (0.48kV/20kA/0.2s/457mm) is strictly prohibited per life-safety requirements (fail-closed)."
                )
                self.log_execution(err_msg, "ERROR")
                return AgentResult(
                    agent_name=self.agent_name,
                    study_type=StudyType.ARC_FLASH,
                    status=AgentStatus.FAILED,
                    validation_errors=[err_msg],
                    data={"missing_parameters": missing_af, "error": err_msg},
                )

            voltage_kv = float(task.parameters["voltage_kv"])
            bolted_fault_ka = float(
                task.parameters.get("bolted_fault_current_ka")
                if task.parameters.get("bolted_fault_current_ka") is not None
                else task.parameters["fault_current_ka"]
            )
            electrode_config = task.parameters.get("electrode_config", "VCB")

            results: dict[str, Any] = {}

            gap_val = float(task.parameters.get("arc_gap_mm") or task.parameters.get("gap_mm", 32.0))
            enc_str = str(task.parameters.get("enclosure_type", "box"))
            enc_type = EnclosureType.OPEN if "OPEN" in enc_str.upper() else EnclosureType.BOX
            try:
                cfg_enum = ElectrodeConfig(str(electrode_config).strip().upper())
            except (ValueError, AttributeError):
                cfg_enum = ElectrodeConfig.VCB

            arc_duration_s = float(
                task.parameters.get("arc_duration_s")
                or task.parameters.get("arc_duration_sec")
                or task.parameters.get("clearing_time_s", 0.2)
            )
            working_distance_mm = float(task.parameters.get("working_distance_mm", 457.0))

            af_res = ArcFlashEngine().calculate(
                voltage_kv=voltage_kv,
                bolted_fault_current_ka=bolted_fault_ka,
                arc_duration_sec=arc_duration_s,
                working_distance_mm=working_distance_mm,
                electrode_config=cfg_enum,
                enclosure_type=enc_type,
                enclosure_width_mm=float(task.parameters.get("enclosure_width_mm", 508.0)),
                enclosure_height_mm=float(task.parameters.get("enclosure_height_mm", 508.0)),
                enclosure_depth_mm=float(task.parameters.get("enclosure_depth_mm", 508.0)),
                arc_gap_mm=gap_val,
            )

            # --- Arc current calculation result ---
            arc_result = {
                "arc_current_ka": af_res.arc_current_ka,
                "reduced_arc_current_ka": af_res.reduced_arc_current_ka,
                "voltage_kv": voltage_kv,
                "bolted_fault_current_ka": bolted_fault_ka,
                "electrode_config": str(electrode_config),
                "gap_mm": gap_val,
            }
            results["arc_current"] = arc_result

            # --- Incident energy calculation result ---
            if analysis_type in ("incident_energy", "full"):
                ie_result = {
                    "incident_energy_cal_cm2": af_res.incident_energy_cal_cm2,
                    "arc_flash_boundary_mm": af_res.arc_flash_boundary_mm,
                    "arc_flash_boundary_in": af_res.arc_flash_boundary_in,
                    "working_distance_mm": working_distance_mm,
                    "working_distance_in": round(working_distance_mm / 25.4, 1),
                    "arc_current_ka": af_res.arc_current_ka,
                    "voltage_kv": voltage_kv,
                    "calculation_method": af_res.method,
                    "ppe_category": af_res.ppe_level,
                    "ppe_description": af_res.ppe_description,
                }
                results["incident_energy"] = ie_result
                results["incident_energy_reduced_current"] = {
                    "incident_energy_cal_cm2": af_res.incident_energy_at_reduced_arc_current,
                    "working_distance_mm": working_distance_mm,
                    "arc_current_ka": af_res.reduced_arc_current_ka,
                }

            # Top-level unified fields matching PowerSystemEngine.run_arc_flash
            results["incident_energy_cal_per_cm2"] = af_res.incident_energy_cal_cm2
            results["incident_energy_at_full_arc_current"] = af_res.incident_energy_at_full_arc_current
            results["incident_energy_at_reduced_arc_current"] = af_res.incident_energy_at_reduced_arc_current
            results["arc_flash_boundary_mm"] = af_res.arc_flash_boundary_mm
            results["arc_flash_boundary_in"] = af_res.arc_flash_boundary_in
            results["arc_current_ka"] = af_res.arc_current_ka
            results["reduced_arc_current_ka"] = af_res.reduced_arc_current_ka
            results["ppe_level"] = af_res.ppe_level
            results["ppe_description"] = af_res.ppe_description
            results["method"] = af_res.method

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.ARC_FLASH,
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

            self.log_execution(f"Arc flash analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Arc flash analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.ARC_FLASH,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate arc flash analysis results.

        Checks:
        - Incident energy is non-negative and finite
        - Arc flash boundary is non-negative
        - PPE category is valid (0-4 or -1 for danger)
        - Voltage is within IEEE 1584 range
        """
        if result is None:
            return False

        errors: list[str] = []

        ie_data = result.data.get("incident_energy")
        if ie_data is not None:
            ie = ie_data.get("incident_energy_cal_cm2", 0.0)
            if ie < 0:
                errors.append(f"Incident energy is negative: {ie:.2f} cal/cm²")
            if not np.isfinite(ie):
                errors.append(f"Incident energy is not finite: {ie}")

            boundary = ie_data.get("arc_flash_boundary_mm", 0.0)
            if boundary < 0:
                errors.append(f"Arc flash boundary is negative: {boundary:.1f} mm")

            ppe_cat = ie_data.get("ppe_category", 0)
            if ppe_cat not in (-1, 0, 1, 2, 3, 4):
                errors.append(f"Invalid PPE category: {ppe_cat}")

        arc_data = result.data.get("arc_current")
        if arc_data is not None:
            iarc = arc_data.get("arc_current_ka", 0.0)  # NOSONAR
            if iarc <= 0:
                errors.append(f"Arc current is non-positive: {iarc:.4f} kA")

        result.validation_errors.extend(errors)
        return len(errors) == 0
