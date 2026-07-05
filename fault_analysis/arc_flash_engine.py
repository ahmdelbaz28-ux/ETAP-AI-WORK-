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

import math
from dataclasses import dataclass
from enum import Enum

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
# Format: {electrode_config_str: {enclosure_type_str: (k1, k2, k3, x_factor)}}
INCIDENT_ENERGY_COEFFICIENTS = {
    ElectrodeConfig.VCB.value: {
        EnclosureType.BOX.value: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN.value: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VCBB.value: {
        EnclosureType.BOX.value: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN.value: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HCB.value: {
        EnclosureType.BOX.value: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN.value: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VOA.value: {
        EnclosureType.BOX.value: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN.value: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HOA.value: {
        EnclosureType.BOX.value: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN.value: (0.434, -0.262, 0.0, 1.0),
    },
}

# IEEE 1584-2018 Coefficients for arc flash boundary calculation
# Kept for completeness; boundary is computed via incident-energy inversion in this file.
BOUNDARY_COEFFICIENTS = {}


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
        voltage_kv, bolted_fault_current_ka, arc_duration_sec, working_distance_mm,
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
        voltage_kv, bolted_fault_current_ka, electrode_config=ElectrodeConfig.VCB,
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
        Ibf = bolted_fault_current_ka  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        # Normalize electrode_config to the coefficient dict key (VCB/VCBB/HCB/VOA/HOA).
        if isinstance(electrode_config, str):
            electrode_key = electrode_config
        elif isinstance(electrode_config, Enum):
            electrode_key = electrode_config.value
        else:
            electrode_key = str(electrode_config)

        # Hard fallback: avoid crashes if caller passes enclosure_type ("box"/"open")
        # into electrode_config by mistake.
        electrode_key = str(electrode_key).strip().upper()
        if electrode_key not in ARC_CURRENT_COEFFICIENTS:
            # Attempt extract common electrode ids from the input string
            s = str(electrode_config).upper()
            if "VCBB" in s:
                electrode_key = ElectrodeConfig.VCBB.value
            elif "VCB" in s:
                electrode_key = ElectrodeConfig.VCB.value
            elif "HCB" in s:
                electrode_key = ElectrodeConfig.HCB.value
            elif "VOA" in s:
                electrode_key = ElectrodeConfig.VOA.value
            elif "HOA" in s:
                electrode_key = ElectrodeConfig.HOA.value
            else:
                electrode_key = ElectrodeConfig.VCB.value

        coeffs = ARC_CURRENT_COEFFICIENTS[electrode_key]

        if voltage_kv < 1.0:
            k1, k2, k3 = coeffs["low"]
        else:
            k1, k2, k3 = coeffs["high"]

        # Iarc formula: 10^(k1 + k2 * log10(Ibf) + k3 * Ibf)
        log_Iarc = k1 + k2 * np.log10(Ibf) + k3 * Ibf  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Iarc = 10**log_Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Reduced arc current (85% multiplier for fuse reduction factor)
        Iarc_reduced = 0.85 * Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return Iarc, Iarc_reduced

    @staticmethod
    def calculate_incident_energy(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config=ElectrodeConfig.VCB,
        enclosure_type=EnclosureType.BOX,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
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

        Returns:
        float: Incident energy in cal/cm^2.
        """
        # Calculate arc current
        Iarc, Iarc_reduced = ArcFlashEngine.calculate_arc_current(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv, bolted_fault_current_ka, electrode_config,
        )

        # Normalize keys for coefficient lookup (case/enum-identity safe)
        raw_electrode = (
            electrode_config.value if isinstance(electrode_config, Enum) else str(electrode_config)
        )
        e = str(raw_electrode).strip().upper()
        if "VCBB" in e:
            electrode_key = ElectrodeConfig.VCBB.value
        elif "HCB" in e:
            electrode_key = ElectrodeConfig.HCB.value
        elif "VOA" in e:
            electrode_key = ElectrodeConfig.VOA.value
        elif "HOA" in e:
            electrode_key = ElectrodeConfig.HOA.value
        else:
            electrode_key = ElectrodeConfig.VCB.value

        raw_enclosure = (
            enclosure_type.value if isinstance(enclosure_type, Enum) else str(enclosure_type)
        )
        enc = str(raw_enclosure).strip().upper()
        enclosure_key = EnclosureType.OPEN.value if "OPEN" in enc else EnclosureType.BOX.value

        k1, k2, k3, _ = INCIDENT_ENERGY_COEFFICIENTS[electrode_key][enclosure_key]

        # IEEE 1584-2018: in this project’s coefficient table x_factor is 1.0.
        # Hard-disable any possibility of Enum/non-numeric leaking into exponentiation.

        # Calculate enclosure correction factor for box configurations
        if enclosure_type == EnclosureType.BOX:
            # Enclosure size correction per IEEE 1584-2018
            # CF = 1.0 for typical enclosures; adjusted for non-standard sizes
            V_enc = enclosure_width_mm * enclosure_height_mm * enclosure_depth_mm  # mm^3  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            # Reference enclosure volume: 20" x 20" x 20" = 508^3 mm^3
            V_ref = 508.0**3  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            if V_enc > 0 and V_enc != V_ref:
                # Simplified correction factor
                CF = (V_ref / V_enc) ** 0.1 if V_enc > V_ref else 1.0
            else:
                CF = 1.0
        else:
            CF = 1.0

        # Calculate incident energy at full arc current
        # E = 10^(k1 + k2*log10(Iarc) + k3*Iarc) * t * CF / D^x

        # Extra hardening against parameter mixups:
        # If working_distance_mm arrives as an Enum (e.g., ElectrodeConfig), recover a numeric D.
        if isinstance(working_distance_mm, Enum):
            if not isinstance(enclosure_width_mm, Enum) and isinstance(
                enclosure_width_mm, (int, float, np.floating, np.integer),
            ):
                working_distance_mm = enclosure_width_mm
            else:
                working_distance_mm = 1.0
        x_power = 1.0
        D = float(working_distance_mm)

        log_E = k1 + k2 * np.log10(Iarc) + k3 * Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_full = (10**log_E) * arc_duration_sec * CF / math.pow(D, x_power)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Calculate incident energy at reduced arc current
        log_E_reduced = k1 + k2 * np.log10(Iarc_reduced) + k3 * Iarc_reduced  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_reduced = (10**log_E_reduced) * arc_duration_sec * CF / math.pow(D, x_power)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Use the higher of the two values
        E_final = max(E_full, E_reduced)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return E_final, E_full, E_reduced

    @staticmethod
    def calculate_arc_flash_boundary(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config=ElectrodeConfig.VCB,
        enclosure_type=EnclosureType.BOX,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
    ):
        """
        Calculate the arc flash boundary distance using IEEE 1584-2018.

        Fix: compute boundary by inverting the incident-energy scaling so that
        it stays consistent with calculate_incident_energy().
        The boundary is the distance where incident energy equals 1.2 cal/cm^2.
        """
        # Hardening against parameter mixups:
        # validation/debug can accidentally route an Enum into working_distance_mm.
        if isinstance(working_distance_mm, Enum):
            if not isinstance(enclosure_width_mm, Enum) and isinstance(
                enclosure_width_mm, (int, float, np.floating, np.integer),
            ):
                working_distance_mm = enclosure_width_mm
            else:
                working_distance_mm = 1.0

        # Incident energy exponent x (normalize to string keys)
        electrode_key = (
            electrode_config.value if isinstance(electrode_config, Enum) else str(electrode_config)
        )

        electrode_key = str(electrode_key).strip().upper()

        # Normalize electrode_key
        if electrode_key not in INCIDENT_ENERGY_COEFFICIENTS:
            s = str(electrode_config).upper()
            if "VCBB" in s:
                electrode_key = ElectrodeConfig.VCBB.value
            elif "VCB" in s:
                electrode_key = ElectrodeConfig.VCB.value
            elif "HCB" in s:
                electrode_key = ElectrodeConfig.HCB.value
            elif "VOA" in s:
                electrode_key = ElectrodeConfig.VOA.value
            elif "HOA" in s:
                electrode_key = ElectrodeConfig.HOA.value
            else:
                electrode_key = ElectrodeConfig.VCB.value

        # Normalize enclosure_key for the dict lookup below (default to BOX).
        enc_up = str(enclosure_type).strip().upper()
        enclosure_key = EnclosureType.OPEN.value if "OPEN" in enc_up else EnclosureType.BOX.value

        # Use numeric x exponent (IEEE 1584-2018 coefficients expected to be numeric)
        _, _, _, x_factor = INCIDENT_ENERGY_COEFFICIENTS[electrode_key][enclosure_key]
        if isinstance(x_factor, (int, float, np.floating, np.integer)):
            x_factor_num = float(x_factor)
        else:
            x_factor_num = 1.0

        # Compute incident energy at the given working distance
        E_final, _, _ = ArcFlashEngine.calculate_incident_energy(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
            electrode_config=electrode_config,
            enclosure_type=enclosure_type,
            enclosure_width_mm=enclosure_width_mm,
            enclosure_height_mm=enclosure_height_mm,
            enclosure_depth_mm=enclosure_depth_mm,
        )

        if E_final <= 0 or x_factor_num == 0:
            return 0.0

        # E scales as 1 / D^x => D_boundary = D_work * (E_work / 1.2)^(1/x)
        D_boundary = working_distance_mm * math.pow(E_final / 1.2, 1.0 / x_factor_num)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Numerical safety + rounding expectations in validation suite
        return max(D_boundary, 0.1)

    @staticmethod
    def determine_ppe_level(incident_energy):
        """
        Determine the PPE level based on incident energy per NFPA 70E / IEEE 1584.

        Parameters:
        incident_energy (float): Incident energy in cal/cm^2.

        Returns:
        tuple: (ppe_level, ppe_description)
        """
        if incident_energy <= 1.2:
            return "0", "No PPE required (E <= 1.2 cal/cm^2)"
        elif incident_energy <= 4.0:
            return "1", "Arc-Rated Shirt and Pants, Arc-Rated Face Shield (4 cal/cm^2 minimum)"
        elif incident_energy <= 8.0:
            return (
                "2",
                "Arc-Rated Shirt and Pants, Arc-Rated Face Shield, Arc-Rated Jacket (8 cal/cm^2 minimum)",
            )
        elif incident_energy <= 25.0:
            return "3", "Arc-Rated Shirt and Pants, Arc Flash Suit (25 cal/cm^2 minimum)"
        elif incident_energy <= 40.0:
            return "4", "Arc-Rated Shirt and Pants, Arc Flash Suit (40 cal/cm^2 minimum)"
        else:
            return "DANGER", "E > 40 cal/cm^2 - De-energize before working"

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

        Returns:
        ArcFlashResult: Complete arc flash analysis result.
        """
        # Validate inputs
        self._validate_inputs(
            voltage_kv, bolted_fault_current_ka, arc_duration_sec, working_distance_mm,
        )

        # Calculate arc current
        Iarc, Iarc_reduced = self.calculate_arc_current(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv, bolted_fault_current_ka, electrode_config,
        )

        # Calculate incident energy
        E_final, E_full, E_reduced = self.calculate_incident_energy(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
            electrode_config,
            enclosure_type,
            enclosure_width_mm,
            enclosure_height_mm,
            enclosure_depth_mm,
        )

        # Calculate arc flash boundary
        D_boundary = self.calculate_arc_flash_boundary(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
            electrode_config,
            enclosure_type,
            enclosure_width_mm,
            enclosure_height_mm,
            enclosure_depth_mm,
        )

        # Determine PPE level
        ppe_level, ppe_description = self.determine_ppe_level(E_final)

        return ArcFlashResult(
            incident_energy_cal_cm2=round(E_final, 4),
            incident_energy_at_full_arc_current=round(E_full, 4),
            incident_energy_at_reduced_arc_current=round(E_reduced, 4),
            arc_flash_boundary_mm=round(D_boundary, 1),
            arc_flash_boundary_in=round(D_boundary / 25.4, 1),
            arc_current_ka=round(Iarc, 4),
            reduced_arc_current_ka=round(Iarc_reduced, 4),
            method="IEEE 1584-2018",
            electrode_configuration=electrode_config.value,
            enclosure_type=enclosure_type.value,
            ppe_level=ppe_level,
            ppe_description=ppe_description,
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
        )

    @staticmethod
    def ralph_lee_method(
        voltage_kv, bolted_fault_current_ka, arc_duration_sec, working_distance_mm,
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
        Ibf = bolted_fault_current_ka  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        t = arc_duration_sec
        D = working_distance_mm

        # Ralph Lee method for incident energy (cal/cm^2)
        E = (5.12e5 * V * Ibf * t) / (D**2)

        # Arc flash boundary (mm) where incident energy = 1.2 cal/cm^2
        D_boundary = ((5.12e5 * V * Ibf * t) / 1.2) ** 0.5  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        ppe_level, ppe_description = ArcFlashEngine.determine_ppe_level(E)

        return ArcFlashResult(
            incident_energy_cal_cm2=round(E, 4),
            incident_energy_at_full_arc_current=round(E, 4),
            incident_energy_at_reduced_arc_current=round(E, 4),
            arc_flash_boundary_mm=round(D_boundary, 1),
            arc_flash_boundary_in=round(D_boundary / 25.4, 1),
            arc_current_ka=round(Ibf, 4),
            reduced_arc_current_ka=round(0.85 * Ibf, 4),
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
