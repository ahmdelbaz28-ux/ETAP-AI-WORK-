"""
Arc Flash Analysis Engine - IEEE 1584-2018 Implementation

This module implements arc flash calculations according to IEEE 1584-2018
"IEEE Guide for Performing Arc-Flash Hazard Calculations".

Supports:
- Arc current calculation
- Reduced arc current calculation
- Incident energy calculation
- Arc flash boundary calculation
- PPE level determination
- Enclosure size correction
- Electrode configuration (VCB, VCBB, HCB, VOA, HOA)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class ElectrodeConfig(Enum):
    """Electrode configuration types per IEEE 1584-2018."""

    VCB = "VCB"  # Vertical conductors/electrodes inside a metal box/enclosure
    VCBB = "VCBB"  # Vertical conductors/electrodes terminated in an insulating barrier inside a metal box/enclosure
    HCB = "HCB"  # Horizontal conductors/electrodes inside a metal box/enclosure
    VOA = "VOA"  # Vertical conductors/electrodes in open air
    HOA = "HOA"  # Horizontal conductors/electrodes in open air


class EnclosureType(Enum):
    """Enclosure type."""

    OPEN = "open"
    BOX = "box"


@dataclass
class ArcFlashResult:
    """Result of an arc flash analysis."""

    incident_energy_cal_cm2: float
    incident_energy_at_full_arc_current: float
    incident_energy_at_reduced_arc_current: float
    arc_flash_boundary_mm: float
    arc_flash_boundary_in: float
    arc_current_ka: float
    reduced_arc_current_ka: float
    method: str
    electrode_configuration: str
    enclosure_type: str
    ppe_level: str
    ppe_description: str
    voltage_kv: float
    bolted_fault_current_ka: float
    arc_duration_sec: float
    working_distance_mm: float


# IEEE 1584-2018 Coefficients for arc current calculation
# NOTE: use plain string keys to avoid Enum identity mismatches across reloads.
# Format: {electrode_config_str: {voltage_range: (k1, k2, k3)}}
# Voltage range: 'low' = 0.208-1 kV, 'high' = 1-15 kV
ARC_CURRENT_COEFFICIENTS = {
    ElectrodeConfig.VCB.value: {
        "low": (-0.153, -0.276, 0.0),
        "high": (0.0425, -0.195, 0.0),
    },
    ElectrodeConfig.VCBB.value: {
        "low": (-0.792, -0.552, 0.0),
        "high": (0.125, -0.265, 0.0),
    },
    ElectrodeConfig.HCB.value: {
        "low": (-0.555, -0.442, 0.0),
        "high": (0.067, -0.230, 0.0),
    },
    ElectrodeConfig.VOA.value: {
        "low": (-0.153, -0.276, 0.0),
        "high": (0.0425, -0.195, 0.0),
    },
    ElectrodeConfig.HOA.value: {
        "low": (-0.555, -0.442, 0.0),
        "high": (0.067, -0.230, 0.0),
    },
}

# IEEE 1584-2018 Coefficients for incident energy calculation
# NOTE: use plain string keys to avoid Enum identity mismatches across reloads.
# Format: {electrode_config_str: {enclosure_type_str: (k1, k2, k3, k4, x_factor)}}
#
# IEEE 1584-2018 Table 4 defines distinct coefficients for each electrode configuration
# in the full formula: log10(En) = K1 + K2×log10(Iarc) + K3×log10(G) + K4×log10(Iarc)×log10(G)
# where G = gap between electrodes. The simplified form used here omits the gap term (G)
# and the K4 interaction term, using a single log10-linear model per config.
# For production engineering, use ETAP or certified software with full gap correction.
# The relative differences between configurations follow the standard's pattern.
# IEEE 1584-2018 Table 3/4 coefficients for incident energy.
# SECURITY AUDIT 2026-07-25 — Fix E-01: Full equation implementation.
# Format: (k1, k2, k3, k4, x_factor)
# Unified canonical incident energy coefficients per IEEE 1584-2018 (single source in ieee1584_database.py)
from fault_analysis.ieee1584_database import INCIDENT_ENERGY_COEFFICIENTS

# IEEE 1584-2018 Coefficients for arc flash boundary calculation
# Kept for completeness; boundary is computed via incident-energy inversion in this file.
BOUNDARY_COEFFICIENTS = {}

# Flag indicating this engine uses a simplified model (no gap correction, no K4 term)
# Production-grade arc flash studies require certified software (ETAP, SKM, EasyPower)
# SECURITY AUDIT 2026-07-25 — Fix E-01: Simplified model flagged.
# The incident energy formula omits: gap distance G, K4 interaction term, and
# uses t as linear multiplier instead of log10(t). Results are NOT compliant
# with IEEE 1584-2018. Do NOT use for PPE selection or arc flash labeling.
ENGINE_IS_SIMPLIFIED = True


def classify_nfpa70e_ppe(incident_energy: float) -> tuple[int, str]:
    """
    Classify required PPE category and description per NFPA 70E boundaries:
    - E <= 1.2 cal/cm²: Category 0 (No PPE required)
    - 1.2 < E <= 4.0 cal/cm²: Category 1 (4 cal/cm² minimum)
    - 4.0 < E <= 8.0 cal/cm²: Category 2 (8 cal/cm² minimum)
    - 8.0 < E <= 25.0 cal/cm²: Category 3 (25 cal/cm² minimum)
    - 25.0 < E <= 40.0 cal/cm²: Category 4 (40 cal/cm² minimum)
    - E > 40.0 cal/cm²: Category -1 (Dangerous — no PPE adequate)
    """
    ie = float(incident_energy)
    if ie <= 1.2:
        return 0, "No PPE required (E <= 1.2 cal/cm^2)"
    elif ie <= 4.0:
        return 1, "Arc-Rated Shirt and Pants, Arc-Rated Face Shield (4 cal/cm^2 minimum)"
    elif ie <= 8.0:
        return 2, "Arc-Rated Shirt and Pants, Arc-Rated Face Shield, Arc-Rated Jacket (8 cal/cm^2 minimum)"
    elif ie <= 25.0:
        return 3, "Arc-Rated Shirt and Pants, Arc Flash Suit (25 cal/cm^2 minimum)"
    elif ie <= 40.0:
        return 4, "Arc-Rated Shirt and Pants, Arc Flash Suit (40 cal/cm^2 minimum)"
    else:
        return -1, "Dangerous — no PPE adequate (E > 40 cal/cm^2); de-energize before working"


class ArcFlashEngine:
    """
    Arc Flash Analysis Engine implementing IEEE 1584-2018 methodology.
    """

    def __init__(self):
        """Initialize the Arc Flash Engine with IEEE 1584-2018 defaults."""
        # All coefficients live in module-level constants; the engine is
        # stateless.  Reserved instance attributes allow subclasses or tests
        # to override per-config tolerances without touching module globals.
        self.working_distance_default_mm = 610.0  # 24 inches
        self.enclosure_reference_volume_mm3 = 508.0**3  # 20" cube
        self.tolerance = 1e-6

    @staticmethod
    def _validate_inputs(
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
    ):
        """
        Validate input parameters for arc flash calculations.

        Parameters:
        voltage_kv (float): System voltage in kV.
        bolted_fault_current_ka (float): Bolted fault current in kA.
        arc_duration_sec (float): Arc duration in seconds.
        working_distance_mm (float): Working distance in mm.

        Raises:
        ValueError: If any input is out of the valid range.
        """
        for param_name, param_val in [
            ("voltage_kv", voltage_kv),
            ("bolted_fault_current_ka", bolted_fault_current_ka),
            ("arc_duration_sec", arc_duration_sec),
            ("working_distance_mm", working_distance_mm),
        ]:
            if not isinstance(param_val, (int, float)) or not math.isfinite(param_val):
                raise ValueError(f"{param_name} must be a finite number.")

        if voltage_kv < 0.208:
            raise ValueError(
                f"Voltage {voltage_kv} kV is below the IEEE 1584-2018 minimum range (0.208 kV). Use Ralph Lee method instead.",
            )
        if voltage_kv > 15.0:
            raise ValueError(
                f"Voltage {voltage_kv} kV is above the IEEE 1584-2018 maximum range (15 kV).",
            )
        if bolted_fault_current_ka < 0.7:
            raise ValueError(
                f"Bolted fault current {bolted_fault_current_ka} kA is below the IEEE 1584-2018 minimum range (0.7 kA).",
            )
        if bolted_fault_current_ka > 106.0:
            raise ValueError(
                f"Bolted fault current {bolted_fault_current_ka} kA is above the IEEE 1584-2018 maximum range (106 kA).",
            )
        if arc_duration_sec <= 0:
            raise ValueError("Arc duration must be positive.")
        if working_distance_mm <= 0:
            raise ValueError("Working distance must be positive.")

    @staticmethod
    def calculate_arc_current(
        voltage_kv,
        bolted_fault_current_ka,
        electrode_config=ElectrodeConfig.VCB,
    ):
        """
        Calculate the arc current using IEEE 1584-2018 equations.

        Parameters:
        voltage_kv (float): System voltage in kV.
        bolted_fault_current_ka (float): Bolted fault current in kA.
        electrode_config (ElectrodeConfig): Electrode configuration.

        Returns:
        tuple: (arc_current_ka, reduced_arc_current_ka)
        """
        if voltage_kv is None or not math.isfinite(float(voltage_kv)) or float(voltage_kv) <= 0:
            raise ValueError(f"voltage_kv must be a positive finite number, got {voltage_kv}")
        if bolted_fault_current_ka is None or not math.isfinite(float(bolted_fault_current_ka)) or float(bolted_fault_current_ka) <= 0:
            raise ValueError(f"bolted_fault_current_ka must be a positive finite number, got {bolted_fault_current_ka}")

        raw_electrode = (
            electrode_config.value if isinstance(electrode_config, Enum) else str(electrode_config)
        )
        electrode_key = str(raw_electrode).strip().upper()
        if electrode_key not in ARC_CURRENT_COEFFICIENTS:
            valid_configs = list(ARC_CURRENT_COEFFICIENTS.keys())
            raise ValueError(
                f"Invalid electrode_config '{electrode_config}'. Allowed values: {valid_configs}"
            )

        from fault_analysis.ieee1584_database import calculate_arcing_current_ieee1584

        iarc, iarc_varcf = calculate_arcing_current_ieee1584(
            voltage_kv=float(voltage_kv),
            bolted_fault_current_ka=float(bolted_fault_current_ka),
            electrode_config=electrode_key,
        )
        iarc_reduced = iarc_varcf

        return iarc, iarc_reduced

    @staticmethod
    def calculate_incident_energy(  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config=ElectrodeConfig.VCB,
        enclosure_type=EnclosureType.BOX,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
        arc_gap_mm=None,
    ):
        """
        Calculate incident energy using IEEE 1584-2018 equations.

        Parameters:
        voltage_kv (float): System voltage in kV.
        bolted_fault_current_ka (float): Bolted fault current in kA.
        arc_duration_sec (float): Arc duration in seconds.
        working_distance_mm (float): Working distance in mm.
        electrode_config (ElectrodeConfig): Electrode configuration.
        enclosure_type (EnclosureType): Enclosure type (open or box).
        enclosure_width_mm (float): Enclosure width in mm (default 508).
        enclosure_height_mm (float): Enclosure height in mm (default 508).
        enclosure_depth_mm (float): Enclosure depth in mm (default 508).
        arc_gap_mm (float): Gap between conductors in mm. If None,
            defaults per IEEE 1584-2018: 25mm for LV (<=1kV), 13mm for HV (>1kV).

        Returns:
        tuple: (E_final, e_full, e_reduced) in cal/cm^2.
        """
        # Calculate arc current
        (
            iarc,
            iarc_reduced,
        ) = ArcFlashEngine.calculate_arc_current(  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            electrode_config,
        )

        # Normalize keys for coefficient lookup (case/enum-identity safe)
        # Validate primary electrical parameters
        if voltage_kv is None or not math.isfinite(float(voltage_kv)) or float(voltage_kv) <= 0:
            raise ValueError(f"voltage_kv must be a positive finite number, got {voltage_kv}")
        if bolted_fault_current_ka is None or not math.isfinite(float(bolted_fault_current_ka)) or float(bolted_fault_current_ka) <= 0:
            raise ValueError(f"bolted_fault_current_ka must be a positive finite number, got {bolted_fault_current_ka}")
        if arc_duration_sec is None or not math.isfinite(float(arc_duration_sec)) or float(arc_duration_sec) <= 0:
            raise ValueError(f"arc_duration_sec must be a positive finite number, got {arc_duration_sec}")
        if working_distance_mm is None or not math.isfinite(float(working_distance_mm)) or float(working_distance_mm) <= 0:
            raise ValueError(f"working_distance_mm must be a positive finite number, got {working_distance_mm}")

        # Normalize keys for coefficient lookup (case/enum-identity safe)
        raw_electrode = (
            electrode_config.value if isinstance(electrode_config, Enum) else str(electrode_config)
        )
        e = str(raw_electrode).strip().upper()
        valid_electrode_configs = {cfg.value: cfg.value for cfg in ElectrodeConfig}
        if e not in valid_electrode_configs:
            raise ValueError(
                f"Invalid electrode_config '{electrode_config}'. Allowed values: {list(valid_electrode_configs.keys())}"
            )
        electrode_key = valid_electrode_configs[e]

        raw_enclosure = (
            enclosure_type.value if isinstance(enclosure_type, Enum) else str(enclosure_type)
        )
        enc = str(raw_enclosure).strip().upper()
        if enc in (EnclosureType.BOX.value, "BOX"):
            enclosure_key = EnclosureType.BOX.value
        elif enc in (EnclosureType.OPEN.value, "OPEN"):
            enclosure_key = EnclosureType.OPEN.value
        else:
            raise ValueError(f"Invalid enclosure_type '{enclosure_type}'. Allowed values: ['box', 'open']")

        k1, k2, k3, k4, x_factor = INCIDENT_ENERGY_COEFFICIENTS[electrode_key][enclosure_key]

        # Calculate enclosure correction factor for box configurations
        if enclosure_key == EnclosureType.BOX.value:
            for dim_name, dim_val in [
                ("enclosure_width_mm", enclosure_width_mm),
                ("enclosure_height_mm", enclosure_height_mm),
                ("enclosure_depth_mm", enclosure_depth_mm),
            ]:
                if dim_val is None:
                    raise ValueError(f"{dim_name} is required for box enclosure (no silent defaults).")
                try:
                    d_v = float(dim_val)
                except (TypeError, ValueError):
                    raise ValueError(f"{dim_name} must be a valid number, got {dim_val}")
                if not math.isfinite(d_v) or d_v <= 0:
                    raise ValueError(f"{dim_name} must be a positive finite number, got {d_v}")

            v_enc = float(enclosure_width_mm) * float(enclosure_height_mm) * float(enclosure_depth_mm)  # NOSONAR
            v_ref = 508.0**3
            if v_enc > 0 and v_enc != v_ref:
                CF = (v_ref / v_enc) ** 0.1 if v_enc > v_ref else 1.0
            else:
                CF = 1.0
        else:
            CF = 1.0

        # Determine gap distance G
        if arc_gap_mm is None:
            raise ValueError(
                "arc_gap_mm is required (fail-closed: missing gap distance). "
                "IEEE 1584-2018 requires an explicit conductor gap."
            )
        try:
            G = float(arc_gap_mm)
        except (TypeError, ValueError):
            raise ValueError(f"arc_gap_mm must be a valid number, got {arc_gap_mm}")
        if not math.isfinite(G) or G <= 0:
            raise ValueError(f"arc_gap_mm must be a positive finite number, got {G}")

        if float(voltage_kv) <= 1.0:
            if G < 6.35 or G > 76.2:
                raise ValueError(
                    f"arc_gap_mm={G} mm is outside IEEE 1584-2018 valid range [6.35, 76.2] mm "
                    f"for low-voltage systems ({voltage_kv} kV)."
                )
        else:
            if G < 19.05 or G > 254.0:
                raise ValueError(
                    f"arc_gap_mm={G} mm is outside IEEE 1584-2018 valid range [19.05, 254.0] mm "
                    f"for medium-voltage systems ({voltage_kv} kV)."
                )

        log10_g = np.log10(G)
        t = float(arc_duration_sec)
        log10_t = np.log10(t / 0.2)  # Normalized to 0.2s (200 ms) IEEE reference duration

        x_power = max(0.5, min(2.5, float(x_factor)))
        D = float(working_distance_mm)

        # Full IEEE 1584-2018 equation
        log_e = (
            k1 + k2 * np.log10(iarc) + k3 * log10_g + k4 * np.log10(iarc) * log10_g + log10_t
        )  # time term: log10(t), not linear t

        # Distance scaling per IEEE 1584: (D_ref / D)^x where D_ref = 457.0 mm (18 in)
        dist_factor = math.pow(457.0 / D, x_power)
        e_full = (10**log_e) * CF * dist_factor

        # Calculate incident energy at reduced arc current
        log_e_reduced = (
            k1
            + k2 * np.log10(iarc_reduced)
            + k3 * log10_g
            + k4 * np.log10(iarc_reduced) * log10_g
            + log10_t
        )

        e_reduced = (10**log_e_reduced) * CF * dist_factor

        # Use the higher of the two values
        e_final = max(e_full, e_reduced)

        return e_final, e_full, e_reduced

    @staticmethod
    def calculate_arc_flash_boundary(  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config=ElectrodeConfig.VCB,
        enclosure_type=EnclosureType.BOX,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
        arc_gap_mm=None,
    ):
        """
        Calculate the arc flash boundary distance using IEEE 1584-2018.

        Fix: compute boundary by inverting the incident-energy scaling so that
        it stays consistent with calculate_incident_energy().
        The boundary is the distance where incident energy equals 1.2 cal/cm^2.
        """
        if working_distance_mm is None or not math.isfinite(float(working_distance_mm)) or float(working_distance_mm) <= 0:
            raise ValueError(f"working_distance_mm must be a positive finite number, got {working_distance_mm}")

        # Incident energy exponent x (normalize to string keys)
        raw_electrode = (
            electrode_config.value if isinstance(electrode_config, Enum) else str(electrode_config)
        )
        electrode_key = str(raw_electrode).strip().upper()
        if electrode_key not in INCIDENT_ENERGY_COEFFICIENTS:
            valid_configs = list(INCIDENT_ENERGY_COEFFICIENTS.keys())
            raise ValueError(f"Invalid electrode_config '{electrode_config}'. Allowed values: {valid_configs}")

        enc_up = (
            enclosure_type.value if isinstance(enclosure_type, Enum) else str(enclosure_type)
        ).strip().upper()
        if enc_up in (EnclosureType.BOX.value, "BOX"):
            enclosure_key = EnclosureType.BOX.value
        elif enc_up in (EnclosureType.OPEN.value, "OPEN"):
            enclosure_key = EnclosureType.OPEN.value
        else:
            raise ValueError(f"Invalid enclosure_type '{enclosure_type}'. Allowed values: ['box', 'open']")

        # Use numeric x exponent (IEEE 1584-2018 coefficients expected to be numeric)
        _, _, _, _, x_factor = INCIDENT_ENERGY_COEFFICIENTS[electrode_key][enclosure_key]
        x_factor_num = float(x_factor)

        # Compute incident energy at the given working distance
        (
            e_final,
            _,
            _,
        ) = ArcFlashEngine.calculate_incident_energy(  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
            electrode_config=electrode_config,
            enclosure_type=enclosure_type,
            enclosure_width_mm=enclosure_width_mm,
            enclosure_height_mm=enclosure_height_mm,
            enclosure_depth_mm=enclosure_depth_mm,
            arc_gap_mm=arc_gap_mm,
        )

        if e_final <= 0 or x_factor_num == 0:
            return 0.0

        # E scales as 1 / D^x => D_boundary = D_work * (E_work / 1.2)^(1/x)
        d_boundary = (
            working_distance_mm * math.pow(e_final / 1.2, 1.0 / x_factor_num)
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Numerical safety + rounding expectations in validation suite
        return max(d_boundary, 0.1)

    @staticmethod
    def determine_ppe_level(incident_energy, allow_simplified=False):
        """
        Determine the PPE level based on incident energy per NFPA 70E / IEEE 1584.

        Parameters:
        incident_energy (float): Incident energy in cal/cm^2.
        allow_simplified (bool): If True, permit mapping even when ENGINE_IS_SIMPLIFIED is True.

        Returns:
        tuple: (ppe_level, ppe_description)
        """
        if ENGINE_IS_SIMPLIFIED and not allow_simplified:
            raise ValueError(
                "ENGINE_IS_SIMPLIFIED is True: ArcFlashEngine uses a simplified model "
                "not compliant with IEEE 1584-2018. Cannot determine PPE level. "
                "Production PPE selection requires certified software (ETAP, SKM, EasyPower)."
            )
        cat_int, desc = classify_nfpa70e_ppe(incident_energy)
        return ("DANGER" if cat_int == -1 else str(cat_int)), desc

    def calculate(
        self,
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config=ElectrodeConfig.VCB,
        enclosure_type=EnclosureType.BOX,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
        arc_gap_mm=None,
    ) -> ArcFlashResult:
        """
        Perform a complete arc flash analysis per IEEE 1584-2018.

        Parameters:
        voltage_kv (float): System voltage in kV.
        bolted_fault_current_ka (float): Bolted fault current in kA.
        arc_duration_sec (float): Arc duration in seconds.
        working_distance_mm (float): Working distance in mm.
        electrode_config (ElectrodeConfig): Electrode configuration.
        enclosure_type (EnclosureType): Enclosure type.
        enclosure_width_mm (float): Enclosure width in mm.
        enclosure_height_mm (float): Enclosure height in mm.
        enclosure_depth_mm (float): Enclosure depth in mm.
        arc_gap_mm (float): Conductor gap distance in mm (required).

        Returns:
        ArcFlashResult: Complete arc flash analysis result.
        """
        # Validate inputs
        self._validate_inputs(
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
        )

        # Calculate arc current
        (
            iarc,
            iarc_reduced,
        ) = self.calculate_arc_current(  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            electrode_config,
        )

        # Calculate incident energy
        e_final, e_full, e_reduced = self.calculate_incident_energy(
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
            electrode_config,
            enclosure_type,
            enclosure_width_mm,
            enclosure_height_mm,
            enclosure_depth_mm,
            arc_gap_mm=arc_gap_mm,
        )

        # Calculate arc flash boundary
        d_boundary = self.calculate_arc_flash_boundary(  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
            electrode_config,
            enclosure_type,
            enclosure_width_mm,
            enclosure_height_mm,
            enclosure_depth_mm,
            arc_gap_mm=arc_gap_mm,
        )

        # Determine PPE level
        try:
            ppe_level, ppe_description = self.determine_ppe_level(e_final)
        except ValueError as err:
            ppe_level = "REJECTED"
            ppe_description = str(err)

        return ArcFlashResult(
            incident_energy_cal_cm2=round(e_final, 4),
            incident_energy_at_full_arc_current=round(e_full, 4),
            incident_energy_at_reduced_arc_current=round(e_reduced, 4),
            arc_flash_boundary_mm=round(d_boundary, 1),
            arc_flash_boundary_in=round(d_boundary / 25.4, 1),
            arc_current_ka=round(iarc, 4),
            reduced_arc_current_ka=round(iarc_reduced, 4),
            method="IEEE 1584-2018",
            electrode_configuration=electrode_config.value if hasattr(electrode_config, "value") else str(electrode_config),
            enclosure_type=enclosure_type.value if hasattr(enclosure_type, "value") else str(enclosure_type),
            ppe_level=ppe_level,
            ppe_description=ppe_description,
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
        )

    @staticmethod
    def ralph_lee_method(
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
    ):
        """
        Calculate arc flash using Ralph Lee method for voltages outside IEEE 1584 range.

        This method is used for voltages above 15 kV or below 0.208 kV.

        Parameters:
        voltage_kv (float): System voltage in kV.
        bolted_fault_current_ka (float): Bolted fault current in kA.
        arc_duration_sec (float): Arc duration in seconds.
        working_distance_mm (float): Working distance in mm.

        Returns:
        ArcFlashResult: Arc flash analysis result using Ralph Lee method.
        """
        V = voltage_kv
        Ibf = bolted_fault_current_ka  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        t = arc_duration_sec
        D = working_distance_mm

        # Ralph Lee method for incident energy (cal/cm^2) per IEEE 1584 Annex D
        E = (2.142e6 * V * Ibf * t) / (D**2)

        # Arc flash boundary (mm) where incident energy = 1.2 cal/cm^2
        d_boundary = (
            ((2.142e6 * V * Ibf * t) / 1.2) ** 0.5
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        try:
            ppe_level, ppe_description = ArcFlashEngine.determine_ppe_level(E)
        except ValueError as err:
            ppe_level = "REJECTED"
            ppe_description = str(err)

        # Ralph Lee method applies outside IEEE 1584 range (V > 15 kV or V < 0.208 kV).
        # Arcing current is taken conservatively as bolted fault current per Lee (1982).
        iarc = float(bolted_fault_current_ka)
        iarc_reduced = float(bolted_fault_current_ka)

        return ArcFlashResult(
            incident_energy_cal_cm2=round(E, 4),
            incident_energy_at_full_arc_current=round(E, 4),
            incident_energy_at_reduced_arc_current=round(E, 4),
            arc_flash_boundary_mm=round(d_boundary, 1),
            arc_flash_boundary_in=round(d_boundary / 25.4, 1),
            arc_current_ka=round(iarc, 4),
            reduced_arc_current_ka=round(iarc_reduced, 4),
            method="Ralph Lee (outside IEEE 1584 range)",
            electrode_configuration="N/A",
            enclosure_type="N/A",
            ppe_level=ppe_level,
            ppe_description=ppe_description,
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
        )


def validate_and_extract_arc_flash_params(
    parameters: dict[str, Any],
    voltage_kv: float | None = None,
) -> dict[str, Any]:
    """Canonical IEEE 1584 arc flash parameter extraction and validation.

    Validates that all life-safety parameters are present and finite without
    any silent default injection or clamps. Returns normalized parameters dict:
    - voltage_kv: float
    - bolted_fault_current_ka: float
    - arc_duration_sec: float
    - working_distance_mm: float
    - arc_gap_mm: float
    - electrode_config: str
    - enclosure_type: str
    - enclosure_width_mm: float | None
    - enclosure_height_mm: float | None
    - enclosure_depth_mm: float | None
    """
    missing_af: list[str] = []

    # 1. Voltage
    v_raw = voltage_kv if voltage_kv is not None else parameters.get("voltage_kv", parameters.get("base_kv"))
    if v_raw is None:
        missing_af.append("voltage_kv")

    # 2. Fault current
    if "bolted_fault_current_ka" not in parameters and "fault_current_ka" not in parameters:
        missing_af.append("bolted_fault_current_ka")

    # 3. Arc duration / clearing time
    if "arc_duration_sec" not in parameters and "clearing_time_s" not in parameters:
        missing_af.append("arc_duration_sec")

    # 4. Working distance
    if "working_distance_mm" not in parameters:
        missing_af.append("working_distance_mm")

    # 5. Gap
    if "arc_gap_mm" not in parameters and "conductor_gap_mm" not in parameters and "gap_mm" not in parameters:
        missing_af.append("arc_gap_mm")

    # 6. Electrode config
    if "electrode_config" not in parameters:
        missing_af.append("electrode_config")

    # 7. Enclosure type
    if "enclosure_type" not in parameters:
        missing_af.append("enclosure_type")

    raw_enc = str(parameters.get("enclosure_type", "")).strip().lower()
    if raw_enc == "box":
        for dim in ("enclosure_width_mm", "enclosure_height_mm", "enclosure_depth_mm"):
            if dim not in parameters:
                missing_af.append(dim)

    if missing_af:
        raise ValueError(
            f"Missing required arc flash parameter(s): {', '.join(missing_af)}. "
            "Silent default parameter injection (VCB/box/508mm/etc) is prohibited per life safety rules (fail-closed)."
        )

    bf_ka = float(parameters.get("bolted_fault_current_ka", parameters.get("fault_current_ka")))
    arc_dur = float(parameters.get("arc_duration_sec", parameters.get("clearing_time_s")))
    w_dist = float(parameters["working_distance_mm"])
    gap = float(parameters.get("arc_gap_mm", parameters.get("conductor_gap_mm", parameters.get("gap_mm"))))
    v_val = float(v_raw)

    for name, val in [
        ("voltage_kv", v_val),
        ("bolted_fault_current_ka", bf_ka),
        ("arc_duration_sec", arc_dur),
        ("working_distance_mm", w_dist),
        ("arc_gap_mm", gap),
    ]:
        if not math.isfinite(val) or val <= 0:
            raise ValueError(f"Arc flash parameter '{name}' must be finite and > 0, got {val}")

    enc_w = float(parameters["enclosure_width_mm"]) if raw_enc == "box" else None
    enc_h = float(parameters["enclosure_height_mm"]) if raw_enc == "box" else None
    enc_d = float(parameters["enclosure_depth_mm"]) if raw_enc == "box" else None

    if raw_enc == "box":
        for dim_name, dim_val in [
            ("enclosure_width_mm", enc_w),
            ("enclosure_height_mm", enc_h),
            ("enclosure_depth_mm", enc_d),
        ]:
            if dim_val is None or not math.isfinite(dim_val) or dim_val <= 0:
                raise ValueError(f"Enclosure dimension '{dim_name}' must be finite and > 0, got {dim_val}")

    return {
        "voltage_kv": v_val,
        "bolted_fault_current_ka": bf_ka,
        "arc_duration_sec": arc_dur,
        "working_distance_mm": w_dist,
        "arc_gap_mm": gap,
        "electrode_config": str(parameters["electrode_config"]),
        "enclosure_type": str(parameters["enclosure_type"]),
        "enclosure_width_mm": enc_w,
        "enclosure_height_mm": enc_h,
        "enclosure_depth_mm": enc_d,
    }

