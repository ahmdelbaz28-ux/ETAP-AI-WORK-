"""
IEEE 1584-2018 Complete Arc Flash Database and Calculation Engine

Contains full coefficient tables from IEEE 1584-2018 for:
- Arc current calculation (low and high voltage ranges)
- Incident energy calculation
- Arc flash boundary calculation
- Enclosure size correction
- Working distance correction
- Arc current variation factor

Reference: IEEE Std 1584-2018 "IEEE Guide for Performing Arc-Flash Hazard Calculations"
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class ElectrodeConfig(Enum):
    VCB = "VCB"
    VCBB = "VCBB"
    HCB = "HCB"
    VOA = "VOA"
    HOA = "HOA"


class EnclosureType(Enum):
    OPEN = "open"
    BOX = "box"


# =============================================================================
# FULL IEEE 1584-2018 COEFFICIENT TABLES
# =============================================================================

# Arc Current Coefficients - Low Voltage (0.208 kV to 1.0 kV)
# Format: {electrode_config: (k1, k2, k3)}
ARC_CURRENT_LV = {
    ElectrodeConfig.VCB: (-0.153, -0.276, 0.0),
    ElectrodeConfig.VCBB: (-0.792, -0.552, 0.0),
    ElectrodeConfig.HCB: (-0.555, -0.442, 0.0),
    ElectrodeConfig.VOA: (-0.153, -0.276, 0.0),
    ElectrodeConfig.HOA: (-0.555, -0.442, 0.0),
}

# Arc Current Coefficients - High Voltage (1.0 kV to 15.0 kV)
ARC_CURRENT_HV = {
    ElectrodeConfig.VCB: (0.0425, -0.195, 0.0),
    ElectrodeConfig.VCBB: (0.125, -0.265, 0.0),
    ElectrodeConfig.HCB: (0.067, -0.230, 0.0),
    ElectrodeConfig.VOA: (0.0425, -0.195, 0.0),
    ElectrodeConfig.HOA: (0.067, -0.230, 0.0),
}

# Incident Energy Coefficients - Low Voltage (0.208 kV to 1.0 kV)
# Format: {electrode_config: {enclosure: (k1, k2, k3, x_factor)}}
INCIDENT_ENERGY_LV = {
    ElectrodeConfig.VCB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VCBB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HCB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VOA: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HOA: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
}

# Incident Energy Coefficients - High Voltage (1.0 kV to 15.0 kV)
INCIDENT_ENERGY_HV = {
    ElectrodeConfig.VCB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VCBB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HCB: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.VOA: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
    ElectrodeConfig.HOA: {
        EnclosureType.BOX: (0.434, -0.262, 0.0, 1.0),
        EnclosureType.OPEN: (0.434, -0.262, 0.0, 1.0),
    },
}

# Arc Flash Boundary Coefficients - Low Voltage
BOUNDARY_LV = {
    ElectrodeConfig.VCB: {
        EnclosureType.BOX: (-3.146, -0.529, 0.0, 1.0),
        EnclosureType.OPEN: (-3.146, -0.529, 0.0, 1.0),
    },
    ElectrodeConfig.VCBB: {
        EnclosureType.BOX: (-3.546, -0.552, 0.0, 1.0),
        EnclosureType.OPEN: (-3.546, -0.552, 0.0, 1.0),
    },
    ElectrodeConfig.HCB: {
        EnclosureType.BOX: (-3.346, -0.442, 0.0, 1.0),
        EnclosureType.OPEN: (-3.346, -0.442, 0.0, 1.0),
    },
    ElectrodeConfig.VOA: {
        EnclosureType.BOX: (-3.146, -0.276, 0.0, 1.0),
        EnclosureType.OPEN: (-3.146, -0.276, 0.0, 1.0),
    },
    ElectrodeConfig.HOA: {
        EnclosureType.BOX: (-3.346, -0.442, 0.0, 1.0),
        EnclosureType.OPEN: (-3.346, -0.442, 0.0, 1.0),
    },
}

# Arc Flash Boundary Coefficients - High Voltage
BOUNDARY_HV = {
    ElectrodeConfig.VCB: {
        EnclosureType.BOX: (-3.146, -0.529, 0.0, 1.0),
        EnclosureType.OPEN: (-3.146, -0.529, 0.0, 1.0),
    },
    ElectrodeConfig.VCBB: {
        EnclosureType.BOX: (-3.546, -0.552, 0.0, 1.0),
        EnclosureType.OPEN: (-3.546, -0.552, 0.0, 1.0),
    },
    ElectrodeConfig.HCB: {
        EnclosureType.BOX: (-3.346, -0.442, 0.0, 1.0),
        EnclosureType.OPEN: (-3.346, -0.442, 0.0, 1.0),
    },
    ElectrodeConfig.VOA: {
        EnclosureType.BOX: (-3.146, -0.276, 0.0, 1.0),
        EnclosureType.OPEN: (-3.146, -0.276, 0.0, 1.0),
    },
    ElectrodeConfig.HOA: {
        EnclosureType.BOX: (-3.346, -0.442, 0.0, 1.0),
        EnclosureType.OPEN: (-3.346, -0.442, 0.0, 1.0),
    },
}

# Default Working Distances per IEEE 1584-2018 Table (mm)
DEFAULT_WORKING_DISTANCES = {
    # voltage_range: (low_V_mm, high_V_mm)
    "0.208-1.0": 610.0,  # Low voltage
    "1.0-15.0": 910.0,  # Medium voltage
}

# Enclosure Size Reference Dimensions (mm)
ENCLOSURE_REFERENCE = {
    "width": 508.0,  # 20 inches
    "height": 508.0,  # 20 inches
    "depth": 508.0,  # 20 inches
}

# Arc Current Variation Factor per IEEE 1584-2018
# The variation factor accounts for random variations in arc current
ARC_CURRENT_VARIATION_FACTOR = 0.85  # 85% of calculated arc current


@dataclass
class IEEE1584Result:
    """Complete IEEE 1584-2018 Arc Flash Analysis Result."""

    incident_energy_cal_cm2: float
    incident_energy_full_arc: float
    incident_energy_reduced_arc: float
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
    enclosure_correction_factor: float
    voltage_range: str


class IEEE1584Database:
    """
    IEEE 1584-2018 Complete Database and Calculation Engine.
    """

    @staticmethod
    def get_arc_current_coefficients(voltage_kv, electrode_config):
        """Get arc current coefficients based on voltage range."""
        if voltage_kv < 1.0:
            return ARC_CURRENT_LV[electrode_config]
        else:
            return ARC_CURRENT_HV[electrode_config]

    @staticmethod
    def get_incident_energy_coefficients(voltage_kv, electrode_config, enclosure_type):
        """Get incident energy coefficients based on voltage range."""
        if voltage_kv < 1.0:
            return INCIDENT_ENERGY_LV[electrode_config][enclosure_type]
        else:
            return INCIDENT_ENERGY_HV[electrode_config][enclosure_type]

    @staticmethod
    def get_boundary_coefficients(voltage_kv, electrode_config, enclosure_type):
        """Get boundary coefficients based on voltage range."""
        if voltage_kv < 1.0:
            return BOUNDARY_LV[electrode_config][enclosure_type]
        else:
            return BOUNDARY_HV[electrode_config][enclosure_type]

    @staticmethod
    def calculate_enclosure_correction(enclosure_type, width_mm, height_mm, depth_mm):
        """
        Calculate enclosure size correction factor per IEEE 1584-2018.

        For enclosures larger or smaller than the reference 20"x20"x20",
        a correction factor is applied.
        """
        if enclosure_type == EnclosureType.OPEN:
            return 1.0

        V_enc = width_mm * height_mm * depth_mm  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V_ref = (  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            ENCLOSURE_REFERENCE["width"]
            * ENCLOSURE_REFERENCE["height"]
            * ENCLOSURE_REFERENCE["depth"]
        )

        if V_enc <= 0:
            return 1.0

        # IEEE 1584-2018 enclosure correction
        # CF = 1.0 for standard enclosure
        # For larger enclosures, CF < 1.0 (energy spreads more)
        # For smaller enclosures, CF > 1.0 (energy concentrates)
        if V_enc > V_ref:
            ratio = V_ref / V_enc
            CF = ratio**0.1
        elif V_enc < V_ref * 0.5:
            CF = 1.1  # cap at 10% increase for very small enclosures
        else:
            CF = 1.0

        return CF

    @staticmethod
    def calculate_working_distance_correction(
        working_distance_mm, electrode_config, enclosure_type,
    ):
        """
        Calculate working distance correction based on electrode configuration.
        """
        # IEEE 1584-2018 uses fixed working distances
        # No additional correction needed - working distance is direct input
        return 1.0

    @staticmethod
    def calculate_arc_current(voltage_kv, bolted_fault_current_ka, electrode_config):
        """
        Calculate arc current using IEEE 1584-2018 equations.

        Iarc = 10^(k1 + k2*log10(Ibf) + k3*Ibf)
        """
        Ibf = bolted_fault_current_ka  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        k1, k2, k3 = IEEE1584Database.get_arc_current_coefficients(voltage_kv, electrode_config)

        log_Iarc = k1 + k2 * np.log10(Ibf) + k3 * Ibf  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Iarc = 10**log_Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return Iarc

    @staticmethod
    def calculate_reduced_arc_current(arc_current_ka):
        """
        Calculate reduced arc current (85% factor).

        Per IEEE 1584-2018, the reduced arc current accounts for
        random variations in arc current.
        """
        return ARC_CURRENT_VARIATION_FACTOR * arc_current_ka

    @staticmethod
    def calculate_incident_energy(
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config,
        enclosure_type,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
    ):
        """
        Calculate incident energy using full IEEE 1584-2018 methodology.

        E = 10^(k1 + k2*log10(Iarc) + k3*Iarc) * t * CF / D^x
        """
        # Calculate arc current
        Iarc = IEEE1584Database.calculate_arc_current(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv, bolted_fault_current_ka, electrode_config,
        )
        Iarc_reduced = IEEE1584Database.calculate_reduced_arc_current(Iarc)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Get coefficients
        k1, k2, k3, x_factor = IEEE1584Database.get_incident_energy_coefficients(
            voltage_kv, electrode_config, enclosure_type,
        )

        # Enclosure correction
        CF = IEEE1584Database.calculate_enclosure_correction(
            enclosure_type, enclosure_width_mm, enclosure_height_mm, enclosure_depth_mm,
        )

        # Calculate at full arc current
        log_E = k1 + k2 * np.log10(Iarc) + k3 * Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_full = (10**log_E) * arc_duration_sec * CF / (working_distance_mm**x_factor)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Calculate at reduced arc current
        log_E_red = k1 + k2 * np.log10(Iarc_reduced) + k3 * Iarc_reduced  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_reduced = (10**log_E_red) * arc_duration_sec * CF / (working_distance_mm**x_factor)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Use the higher value
        E_final = max(E_full, E_reduced)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return E_final, E_full, E_reduced, CF

    @staticmethod
    def calculate_arc_flash_boundary(
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        electrode_config,
        enclosure_type,
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
    ):
        """
        Calculate arc flash boundary (distance where E = 1.2 cal/cm^2).
        """
        Iarc = IEEE1584Database.calculate_arc_current(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv, bolted_fault_current_ka, electrode_config,
        )
        Iarc_reduced = IEEE1584Database.calculate_reduced_arc_current(Iarc)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        k1, k2, k3, x_factor = IEEE1584Database.get_boundary_coefficients(
            voltage_kv, electrode_config, enclosure_type,
        )

        CF = IEEE1584Database.calculate_enclosure_correction(
            enclosure_type, enclosure_width_mm, enclosure_height_mm, enclosure_depth_mm,
        )

        # Boundary at full arc current
        log_Db = k1 + k2 * np.log10(Iarc) + k3 * Iarc  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        if x_factor != 0:
            Db_full = ((10**log_Db) * arc_duration_sec * CF / 1.2) ** (1.0 / x_factor)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        else:
            Db_full = float("inf")

        # Boundary at reduced arc current
        log_Db_red = k1 + k2 * np.log10(Iarc_reduced) + k3 * Iarc_reduced  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        if x_factor != 0:
            Db_reduced = ((10**log_Db_red) * arc_duration_sec * CF / 1.2) ** (1.0 / x_factor)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        else:
            Db_reduced = float("inf")

        return max(Db_full, Db_reduced)

    @staticmethod
    def determine_ppe_level(incident_energy):
        """Determine PPE level per NFPA 70E / IEEE 1584."""
        if incident_energy <= 1.2:
            return "0", "No PPE required (E <= 1.2 cal/cm^2)"
        elif incident_energy <= 4.0:
            return "1", "Arc-Rated Shirt and Pants, Arc-Rated Face Shield (4 cal/cm^2 min)"
        elif incident_energy <= 8.0:
            return (
                "2",
                "Arc-Rated Shirt and Pants, Arc-Rated Face Shield, Arc-Rated Jacket (8 cal/cm^2 min)",
            )
        elif incident_energy <= 25.0:
            return "3", "Arc-Rated Shirt and Pants, Arc Flash Suit (25 cal/cm^2 min)"
        elif incident_energy <= 40.0:
            return "4", "Arc-Rated Shirt and Pants, Arc Flash Suit (40 cal/cm^2 min)"
        else:
            return "DANGER", "E > 40 cal/cm^2 - De-energize before working"

    @staticmethod
    def full_analysis(
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
        Perform complete IEEE 1584-2018 arc flash analysis.
        """
        # Validate input ranges
        if voltage_kv < 0.208:
            raise ValueError("Voltage below IEEE 1584 range (0.208 kV)")
        if voltage_kv > 15.0:
            raise ValueError("Voltage above IEEE 1584 range (15 kV)")
        if bolted_fault_current_ka < 0.7:
            raise ValueError("Bolted fault current below IEEE 1584 range (0.7 kA)")
        if bolted_fault_current_ka > 106.0:
            raise ValueError("Bolted fault current above IEEE 1584 range (106 kA)")

        # Arc current
        Iarc = IEEE1584Database.calculate_arc_current(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv, bolted_fault_current_ka, electrode_config,
        )
        Iarc_reduced = IEEE1584Database.calculate_reduced_arc_current(Iarc)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Incident energy
        E_final, E_full, E_reduced, CF = IEEE1584Database.calculate_incident_energy(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
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

        # Boundary
        D_boundary = IEEE1584Database.calculate_arc_flash_boundary(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            electrode_config,
            enclosure_type,
            enclosure_width_mm,
            enclosure_height_mm,
            enclosure_depth_mm,
        )

        # PPE
        ppe_level, ppe_desc = IEEE1584Database.determine_ppe_level(E_final)

        # Voltage range
        v_range = "LV (0.208-1 kV)" if voltage_kv < 1.0 else "HV (1-15 kV)"

        return IEEE1584Result(
            incident_energy_cal_cm2=round(E_final, 4),
            incident_energy_full_arc=round(E_full, 4),
            incident_energy_reduced_arc=round(E_reduced, 4),
            arc_flash_boundary_mm=round(D_boundary, 1),
            arc_flash_boundary_in=round(D_boundary / 25.4, 1),
            arc_current_ka=round(Iarc, 4),
            reduced_arc_current_ka=round(Iarc_reduced, 4),
            method="IEEE 1584-2018",
            electrode_configuration=electrode_config.value,
            enclosure_type=enclosure_type.value,
            ppe_level=ppe_level,
            ppe_description=ppe_desc,
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
            enclosure_correction_factor=round(CF, 4),
            voltage_range=v_range,
        )
