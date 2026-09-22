"""Physical units and dimensions registry for electrical power engineering.

Provides Pint-based UnitRegistry and dimensionality verification for
engineering study parameters (IEC 60909, IEEE 1584, IEEE 3002, etc.).
"""

from __future__ import annotations

import re
from typing import Any, Tuple

import pint

# Initialize central unit registry
ureg = pint.UnitRegistry()
ureg.define("cal_cm2 = cal / (centimeter ** 2) = cal_per_sq_cm")

# Dimensionality constants
DIM_CURRENT = ureg.ampere.dimensionality
DIM_VOLTAGE = ureg.volt.dimensionality
DIM_POWER = ureg.watt.dimensionality
DIM_APPARENT_POWER = ureg.volt_ampere.dimensionality
DIM_IMPEDANCE = ureg.ohm.dimensionality
DIM_TIME = ureg.second.dimensionality
DIM_LENGTH = ureg.meter.dimensionality
DIM_AREA = (ureg.meter**2).dimensionality
DIM_RESISTIVITY = (ureg.ohm * ureg.meter).dimensionality
DIM_INCIDENT_ENERGY = (ureg.joule / (ureg.meter**2)).dimensionality
DIM_DIMENSIONLESS = ureg.dimensionless.dimensionality

# Parameter name to allowed dimensions mapping
EXPECTED_DIMENSIONS: dict[str, tuple[pint.util.UnitsContainer, ...]] = {
    "bolted_fault_current": (DIM_CURRENT,),
    "bolted_fault_ka": (DIM_CURRENT,),
    "ik_double_prime": (DIM_CURRENT,),
    "short_circuit_level": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT),
    "fault_level": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT),
    "voltage_setpoint": (DIM_VOLTAGE,),
    "cable_ampacity": (DIM_CURRENT,),
    "conductor_size": (DIM_AREA, DIM_LENGTH, DIM_DIMENSIONLESS),
    "transformer_impedance": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "earth_fault_setting": (DIM_CURRENT, DIM_TIME, DIM_DIMENSIONLESS),
    "soil_resistivity": (DIM_RESISTIVITY,),
    "fault_clearing_time": (DIM_TIME,),
    "working_distance": (DIM_LENGTH,),
    "incident_energy": (DIM_INCIDENT_ENERGY,),
    "load_flow_limit": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT, DIM_DIMENSIONLESS),
}

# Regex to detect strings that specify units (e.g., "25 kA", "10V", "5.2 cal/cm²")
_UNIT_STR_PATTERN = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z_/%²°]+(?:\s*[*/^0-9\-_a-zA-Z²]+)*)\s*$")


def parse_quantity(value: Any) -> pint.Quantity | None:
    """Attempt to parse a value into a pint.Quantity.

    Supports:
      - Pint Quantity objects directly
      - Strings like '25.0 kA', '120 V', '5.2 cal/cm²', '100 MVA'
      - Dicts like {'value': 25.0, 'unit': 'kA'}
    Returns None if value has no explicit unit or cannot be parsed.
    """
    if isinstance(value, pint.Quantity):
        return value

    if isinstance(value, dict) and "value" in value and "unit" in value:
        try:
            num = float(value["value"])
            unit_str = str(value["unit"]).strip()
            return ureg.Quantity(num, unit_str)
        except Exception:
            return None

    if isinstance(value, str):
        match = _UNIT_STR_PATTERN.match(value.strip())
        if match:
            num_str, unit_str = match.groups()
            # Clean common unicode characters
            clean_unit = unit_str.replace("²", "**2").replace("cal/cm2", "cal / (cm**2)")
            try:
                num = float(num_str)
                return ureg.Quantity(num, clean_unit)
            except Exception:
                pass
        # Try full string parse as fallback
        try:
            qty = ureg(value)
            if isinstance(qty, pint.Quantity):
                return qty
        except Exception:
            pass

    return None


def validate_parameter_dimension(param_name: str, value: Any) -> Tuple[bool, str | None]:
    """Validate that value's dimension matches expected dimension for param_name.

    If value has no explicit unit (e.g. pure float/int), returns (True, None).
    If value has an explicit unit whose dimension does NOT match, returns
    (False, error_reason).
    """
    qty = parse_quantity(value)
    if qty is None:
        # No explicit unit given; pure numeric values pass dimension check
        return True, None

    # Check if param_name has known dimension restrictions
    param_key = param_name.lower().strip()
    allowed_dims = EXPECTED_DIMENSIONS.get(param_key)
    if not allowed_dims:
        return True, None

    qty_dim = qty.dimensionality
    for allowed in allowed_dims:
        if qty_dim == allowed:
            return True, None

    # Mismatch found
    return (
        False,
        f"Dimension mismatch for parameter '{param_name}': got {qty_dim} ({qty.units}), "
        f"expected one of {[str(d) for d in allowed_dims]}",
    )
