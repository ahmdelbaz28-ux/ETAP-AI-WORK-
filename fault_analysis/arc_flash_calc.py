"""
IEEE 1584-2018 Arc Flash Calculation Utility
=============================================
Thin convenience wrapper around ``ArcFlashEngine`` from
``fault_analysis.arc_flash_engine``.  Delegates all IEEE 1584-2018
computations to the single authoritative engine in that module so that
coefficients are never duplicated across files.

Callers that need richer result objects (ArcFlashResult dataclass with
PPE descriptions, enclosure details, etc.) should import and use
``ArcFlashEngine`` directly.
"""
from __future__ import annotations

import json
from typing import Optional

from fault_analysis.arc_flash_engine import (
    ArcFlashEngine,
    ElectrodeConfig,
    EnclosureType,
)

# Lazy singleton — avoids repeated object creation overhead since the
# engine is stateless (all computation lives in static methods).
_engine: Optional[ArcFlashEngine] = None


def _get_engine() -> ArcFlashEngine:
    global _engine
    if _engine is None:
        _engine = ArcFlashEngine()
    return _engine


def calculate_arc_flash(
    voltage_kv: float,
    bolted_fault_current_ka: float,
    arc_duration_sec: float,
    working_distance_mm: float,
    enclosure_type: str = "box",
    electrode_config: str = "VCB",
) -> dict:
    """
    IEEE 1584-2018 Arc Flash calculation (convenience wrapper).

    Delegates to :class:`ArcFlashEngine` for the actual computation
    so that coefficient tables live in exactly one place.

    Returns a plain dict (backward-compatible with existing callers).
    """
    # Normalize string parameters to Enum values for ArcFlashEngine
    enc_map = {"box": EnclosureType.BOX, "open": EnclosureType.OPEN}
    elec_map = {
        "VCB": ElectrodeConfig.VCB,
        "VCBB": ElectrodeConfig.VCBB,
        "HCB": ElectrodeConfig.HCB,
        "VOA": ElectrodeConfig.VOA,
        "HOA": ElectrodeConfig.HOA,
    }

    enc = enc_map.get(enclosure_type.lower(), EnclosureType.BOX)
    elec = elec_map.get(electrode_config.upper(), ElectrodeConfig.VCB)

    engine = _get_engine()

    # For voltages below IEEE 1584 range, use Ralph Lee directly
    if voltage_kv < 0.208:
        result = engine.ralph_lee_method(
            voltage_kv,
            bolted_fault_current_ka,
            arc_duration_sec,
            working_distance_mm,
        )
        return {
            "incident_energy_cal_per_cm2": result.incident_energy_cal_cm2,
            "arc_flash_boundary_mm": result.arc_flash_boundary_mm,
            "arc_flash_boundary_in": result.arc_flash_boundary_in,
            "arc_current_ka": result.arc_current_ka,
            "method": result.method,
            "ppe_level": result.ppe_level,
        }

    # Standard IEEE 1584-2018 path
    result = engine.calculate(
        voltage_kv=voltage_kv,
        bolted_fault_current_ka=bolted_fault_current_ka,
        arc_duration_sec=arc_duration_sec,
        working_distance_mm=working_distance_mm,
        electrode_config=elec,
        enclosure_type=enc,
    )

    return {
        "incident_energy_cal_per_cm2": result.incident_energy_cal_cm2,
        "arc_flash_boundary_mm": result.arc_flash_boundary_mm,
        "arc_current_ka": result.arc_current_ka,
        "method": result.method,
        "ppe_level": result.ppe_level,
    }


def _validate_arc_flash_input(
    voltage_kv, bolted_fault_ka, duration_sec, distance_mm, enclosure, electrode,
):
    """Validate arc flash CLI inputs against IEEE 1584-2018 bounds."""
    import math

    errors = []
    if (
        not isinstance(voltage_kv, (int, float))
        or math.isnan(voltage_kv)
        or math.isinf(voltage_kv)
        or voltage_kv < 0
    ):
        errors.append(f"voltage_kv must be a non-negative number, got {voltage_kv!r}")
    if (
        not isinstance(bolted_fault_ka, (int, float))
        or math.isnan(bolted_fault_ka)
        or math.isinf(bolted_fault_ka)
        or bolted_fault_ka < 0
    ):
        errors.append(
            f"bolted_fault_current_ka must be a non-negative number, got {bolted_fault_ka!r}",
        )
    if (
        not isinstance(duration_sec, (int, float))
        or math.isnan(duration_sec)
        or math.isinf(duration_sec)
        or duration_sec <= 0
    ):
        errors.append(f"arc_duration_sec must be positive, got {duration_sec!r}")
    if (
        not isinstance(distance_mm, (int, float))
        or math.isnan(distance_mm)
        or math.isinf(distance_mm)
        or distance_mm <= 0
    ):
        errors.append(f"working_distance_mm must be positive, got {distance_mm!r}")
    valid_enclosures = {"box", "open"}
    if enclosure.lower() not in valid_enclosures:
        errors.append(f"enclosure_type must be one of {valid_enclosures}, got {enclosure!r}")
    valid_electrodes = {"VCB", "VCBB", "HCB", "VOA", "HOA"}
    if electrode.upper() not in valid_electrodes:
        errors.append(f"electrode_config must be one of {valid_electrodes}, got {electrode!r}")
    return errors


if __name__ == "__main__":
    import sys

    try:
        args = sys.argv[1:]
        if len(args) != 6:
            print(
                json.dumps(
                    {
                        "error": f"Expected 6 arguments (voltage_kv, bolted_fault_ka, duration_sec, distance_mm, enclosure, electrode), got {len(args)}",
                    },
                ),
            )
            sys.exit(1)
        # Parse and validate inputs before computation
        voltage_kv = float(args[0])
        bolted_fault_ka = float(args[1])
        duration_sec = float(args[2])
        distance_mm = float(args[3])
        enclosure = args[4]
        electrode = args[5]

        validation_errors = _validate_arc_flash_input(
            voltage_kv, bolted_fault_ka, duration_sec, distance_mm, enclosure, electrode,
        )
        if validation_errors:
            print(
                json.dumps(
                    {"error": "Input validation failed", "validation_errors": validation_errors},
                ),
            )
            sys.exit(1)

        res = calculate_arc_flash(
            voltage_kv, bolted_fault_ka, duration_sec, distance_mm, enclosure, electrode,
        )
        print(json.dumps(res))
    except ValueError as e:
        print(json.dumps({"error": f"Invalid numeric input: {e}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
