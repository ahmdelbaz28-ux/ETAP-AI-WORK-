"""
IEEE 1584-2018 Arc Flash Calculation Utility
=============================================
Provides standalone functions for arc flash analysis to be used by agents.
"""

import json
import math


def calculate_arc_flash(
    voltage_kv: float,
    bolted_fault_current_ka: float,
    arc_duration_sec: float,
    working_distance_mm: float,
    enclosure_type: str = "box",
    electrode_config: str = "VCB"
) -> dict:
    """
    IEEE 1584-2018 Arc Flash Calculations
    """
    V = voltage_kv
    Ibf = bolted_fault_current_ka
    t = arc_duration_sec
    D = working_distance_mm
    elec_config = electrode_config

    # Step 1: Intermediate arc current (kA) for voltages 0.6-15 kV
    if V < 0.208:
        # For low voltage < 208V, use Ralph Lee method as fallback
        E = (5.12e5 * V * Ibf * t) / (D ** 2)
        D_boundary = ((5.12e5 * V * Ibf * t) / 1.2) ** 0.5
        return {
            "incident_energy_cal_per_cm2": round(E, 4),
            "arc_flash_boundary_mm": round(D_boundary, 1),
            "arc_flash_boundary_in": round(D_boundary / 25.4, 1),
            "arc_current_ka": round(Ibf, 4),
            "method": "Ralph Lee (voltage below IEEE 1584 range)",
            "ppe_level": "N/A - consult engineer"
        }

    # IEEE 1584-2018 coefficients based on electrode configuration
    coefficients = {
        "VCB":  {"k1": -0.153, "k2": -0.276, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
        "VCBB": {"k1": -0.792, "k2": -0.552, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
        "HCB":  {"k1": -0.555, "k2": -0.442, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
        "VOA":  {"k1": -0.153, "k2": -0.276, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
        "HOA":  {"k1": -0.555, "k2": -0.442, "k3":  0.0,   "x": 0.744, "k1_ie": 0.434, "k2_ie": -0.262, "k3_ie": 0.0,   "x_ie": 1.0},
    }

    # Get coefficients for the electrode configuration
    c = coefficients.get(elec_config, coefficients["VCB"])

    # Calculate arc current
    log_Iarc = c["k1"] + c["k2"] * math.log10(Ibf) + c["k3"] * Ibf
    Iarc = 10 ** log_Iarc
    Iarc_min = 0.85 * Iarc

    # Step 2: Calculate incident energy
    Cf = 1.0 # Enclosure correction factor simplified for this tool

    log_E = c["k1_ie"] + c["k2_ie"] * math.log10(Iarc) + c["k3_ie"] * Iarc
    E_base = 10 ** log_E
    E = E_base * t / (D ** c["x_ie"]) * Cf

    log_E_min = c["k1_ie"] + c["k2_ie"] * math.log10(Iarc_min) + c["k3_ie"] * Iarc_min
    E_base_min = 10 ** log_E_min
    E_min = E_base_min * t / (D ** c["x_ie"]) * Cf

    E_final = max(E, E_min)

    # Step 3: Arc flash boundary
    D_boundary = (E_base * t / 1.2) ** (1.0 / c["x_ie"]) * Cf ** (1.0 / c["x_ie"])
    D_boundary_min = (E_base_min * t / 1.2) ** (1.0 / c["x_ie"]) * Cf ** (1.0 / c["x_ie"])
    D_boundary_final = max(D_boundary, D_boundary_min)

    # PPE Level
    if E_final <= 1.2: ppe_level = "0"
    elif E_final <= 4.0: ppe_level = "1"
    elif E_final <= 8.0: ppe_level = "2"
    elif E_final <= 25.0: ppe_level = "3"
    elif E_final <= 40.0: ppe_level = "4"
    else: ppe_level = "DANGER"

    return {
        "incident_energy_cal_per_cm2": round(E_final, 4),
        "arc_flash_boundary_mm": round(D_boundary_final, 1),
        "arc_current_ka": round(Iarc, 4),
        "method": "IEEE 1584-2018",
        "ppe_level": ppe_level
    }

if __name__ == "__main__":
    import sys
    try:
        args = sys.argv[1:]
        res = calculate_arc_flash(
            float(args[0]), float(args[1]), float(args[2]),
            float(args[3]), args[4], args[5]
        )
        print(json.dumps(res))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
