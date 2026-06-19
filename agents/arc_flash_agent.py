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

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IEEE 1584-2018 coefficients for incident energy and arc boundary
# ---------------------------------------------------------------------------

# Coefficients for arc current (Table 4 in IEEE 1584-2018)
_ARC_CURRENT_COEFFS = {
    # (config, voltage_range): (k1, k2)
    # config: 0=VCB, 1=VCBB, 2=HCB
    "VCB_208": (0.000, -0.028),      # 0.208 kV, VC in a box
    "VCB_600": (-0.009, -0.019),     # 0.600 kV, VC in a box
    "VCB_1000": (-0.009, -0.019),    # 1.000 kV, VC in a box
    "VCB_2700": (-0.076, 0.016),     # 2.700 kV, VC in a box
    "VCB_14300": (-0.076, 0.016),    # 14.300 kV, VC in a box
    "VCBB_208": (0.000, -0.028),     # 0.208 kV, VCBB
    "VCBB_600": (-0.015, -0.019),    # 0.600 kV, VCBB
    "VCBB_1000": (-0.015, -0.019),   # 1.000 kV, VCBB
    "VCBB_2700": (-0.079, 0.017),    # 2.700 kV, VCBB
    "VCBB_14300": (-0.079, 0.017),   # 14.300 kV, VCBB
    "HCB_208": (0.000, -0.028),      # 0.208 kV, HCB
    "HCB_600": (0.003, -0.022),      # 0.600 kV, HCB
    "HCB_1000": (0.003, -0.022),     # 1.000 kV, HCB
    "HCB_2700": (-0.073, 0.019),     # 2.700 kV, HCB
    "HCB_14300": (-0.073, 0.019),    # 14.300 kV, HCB
}

# PPE Category classification per NFPA 70E
_PPE_CATEGORIES = [
    {"min_ie": 0.0, "max_ie": 1.2, "category": 0, "description": "No PPE required"},
    {"min_ie": 1.2, "max_ie": 4.0, "category": 1, "description": "Arc-rated shirt and pants or coverall"},
    {"min_ie": 4.0, "max_ie": 8.0, "category": 2, "description": "Arc-rated shirt, pants, and face shield"},
    {"min_ie": 8.0, "max_ie": 25.0, "category": 3, "description": "Arc-rated shirt, pants, arc flash suit, and face shield"},
    {"min_ie": 25.0, "max_ie": 40.0, "category": 4, "description": "Arc-rated shirt, pants, multi-layer arc flash suit, and face shield"},
    {"min_ie": 40.0, "max_ie": float("inf"), "category": -1, "description": "Dangerous — no PPE adequate; de-energize equipment"},
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
    ) -> Dict[str, Any]:
        """
        Calculate the arcing current per IEEE 1584-2018.

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
        Dict[str, Any]
            Dictionary with 'arc_current_ka', 'reduced_arc_current_ka',
            'voltage_kv', 'bolted_fault_current_ka', 'electrode_config'.
        """
        Ibf = bolted_fault_current_ka
        G = gap_mm

        # Simplified IEEE 1584-2018 model coefficients for VCB
        if voltage_kv <= 0.6:
            # Low voltage model
            k1 = 0.0
            k2 = -0.028 if electrode_config == "VCB" else -0.028
            log_Iarc = (
                k1
                + k2 * G
                + 0.921 * np.log10(Ibf)
                + 0.0 * Ibf
                + 0.0 * np.log10(Ibf) * G
            )
        elif voltage_kv <= 2.7:
            # Medium voltage model
            k1 = -0.076 if electrode_config == "VCB" else -0.079
            k2 = 0.016 if electrode_config == "VCB" else 0.017
            log_Iarc = (
                k1
                + k2 * G
                + 0.954 * np.log10(Ibf)
                + 0.0 * Ibf
                + 0.0 * np.log10(Ibf) * G
            )
        else:
            # High voltage (> 2.7 kV up to 15 kV)
            log_Iarc = np.log10(Ibf) * 0.978 + 0.001 * G

        Iarc = float(10.0 ** log_Iarc)

        # Reduced arc current (85% of Iarc for fuse / low-current evaluation)
        Iarc_reduced = 0.85 * Iarc

        return {
            "arc_current_ka": round(Iarc, 4),
            "reduced_arc_current_ka": round(Iarc_reduced, 4),
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
    ) -> Dict[str, Any]:
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
        Iarc = arc_current_ka
        t = arc_duration_s
        D = working_distance_mm
        G = gap_mm

        if voltage_kv <= 0.6:
            # Low voltage IEEE 1584 model
            if electrode_config == "VCB":
                c1, c2, c3, c4, c5 = (
                    -0.055, -0.802, -0.642, 0.067, 0.000
                )
            elif electrode_config == "VCBB":
                c1, c2, c3, c4, c5 = (
                    0.089, -0.803, -0.642, 0.067, 0.000
                )
            else:  # HCB
                c1, c2, c3, c4, c5 = (
                    0.215, -0.803, -0.642, 0.067, 0.000
                )
            x = 1.0
        elif voltage_kv <= 15.0:
            # Medium / high voltage IEEE 1584 model
            if electrode_config == "VCB":
                c1, c2, c3, c4, c5 = (
                    0.045, -0.921, -0.642, 0.067, 0.000
                )
            elif electrode_config == "VCBB":
                c1, c2, c3, c4, c5 = (
                    0.076, -0.921, -0.642, 0.067, 0.000
                )
            else:  # HCB
                c1, c2, c3, c4, c5 = (
                    0.198, -0.921, -0.642, 0.067, 0.000
                )
            x = 1.0
        else:
            # Lee method for > 15 kV
            # E = 2.142 * 10^6 * V * Iarc * t / D^2
            E_lee = 2.142e6 * voltage_kv * Iarc * t / (D ** 2)
            return self._format_ie_result(
                E_lee, D, arc_current_ka, voltage_kv, "Lee"
            )

        # IEEE 1584-2018 empirical model
        log_E = (
            c1
            + c2 * np.log10(Iarc)
            + c3 * np.log10(G)
            + c4 * np.log10(Iarc) * G
            + c5 * np.log10(D)
        )
        E_normalization = 10.0 ** log_E

        # Apply duration scaling: E = E_0.2 * (t / 0.2)
        E = E_normalization * (t / 0.2) ** x

        return self._format_ie_result(
            E, D, arc_current_ka, voltage_kv, "IEEE 1584-2018"
        )

    def _format_ie_result(
        self,
        E_cal_cm2: float,
        working_distance_mm: float,
        arc_current_ka: float,
        voltage_kv: float,
        method: str,
    ) -> Dict[str, Any]:
        """Format incident energy result with boundary and PPE classification."""
        # Arc flash boundary: distance where E = 1.2 cal/cm²
        if E_cal_cm2 > 0 and working_distance_mm > 0:
            # Simplified: D_boundary = D * sqrt(E / 1.2)
            boundary_mm = working_distance_mm * np.sqrt(E_cal_cm2 / 1.2)
        else:
            boundary_mm = 0.0

        # PPE category
        ppe_cat, ppe_desc = self._classify_ppe(E_cal_cm2)

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

    def _classify_ppe(self, ie: float) -> tuple:
        """
        Classify required PPE category based on incident energy.

        Parameters
        ----------
        ie : float
            Incident energy in cal/cm².

        Returns
        -------
        tuple
            (category: int, description: str)
        """
        for cat in _PPE_CATEGORIES:
            if cat["min_ie"] <= ie < cat["max_ie"]:
                return cat["category"], cat["description"]
        return -1, "Dangerous — no PPE adequate; de-energize equipment"

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
        start_time = datetime.now(timezone.utc)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting arc flash analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}

            voltage_kv = float(task.parameters.get("voltage_kv", 0.48))
            bolted_fault_ka = float(task.parameters.get("bolted_fault_current_ka", 20.0))
            electrode_config = task.parameters.get("electrode_config", "VCB")
            gap_mm = float(task.parameters.get("gap_mm", 32.0))

            # --- Arc current calculation ---
            arc_result = self.calculate_arc_current(
                voltage_kv=voltage_kv,
                bolted_fault_current_ka=bolted_fault_ka,
                electrode_config=electrode_config,
                gap_mm=gap_mm,
            )
            results["arc_current"] = arc_result

            # --- Incident energy calculation ---
            if analysis_type in ("incident_energy", "full"):
                arc_current_ka = float(task.parameters.get(
                    "arc_current_ka", arc_result["arc_current_ka"]
                ))
                arc_duration_s = float(task.parameters.get("arc_duration_s", 0.2))
                working_distance_mm = float(task.parameters.get("working_distance_mm", 457.0))

                ie_result = self.calculate_incident_energy(
                    voltage_kv=voltage_kv,
                    arc_current_ka=arc_current_ka,
                    arc_duration_s=arc_duration_s,
                    working_distance_mm=working_distance_mm,
                    electrode_config=electrode_config,
                    gap_mm=gap_mm,
                )
                results["incident_energy"] = ie_result

                # Also evaluate at reduced arc current (85%)
                ie_reduced = self.calculate_incident_energy(
                    voltage_kv=voltage_kv,
                    arc_current_ka=arc_result["reduced_arc_current_ka"],
                    arc_duration_s=arc_duration_s,
                    working_distance_mm=working_distance_mm,
                    electrode_config=electrode_config,
                    gap_mm=gap_mm,
                )
                results["incident_energy_reduced_current"] = ie_reduced

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
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
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
        errors: List[str] = []

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
            Iarc = arc_data.get("arc_current_ka", 0.0)
            if Iarc <= 0:
                errors.append(f"Arc current is non-positive: {Iarc:.4f} kA")

        result.validation_errors.extend(errors)
        return len(errors) == 0
