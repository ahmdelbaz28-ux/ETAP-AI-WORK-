"""Physical units and dimensions registry for electrical power engineering.

Provides Pint-based UnitRegistry and dimensionality verification for
engineering study parameters (IEC 60909, IEEE 1584, IEEE 3002, etc.).
Includes deterministic unit conversions, per-unit normalization,
angle conversions, and cable sizing bridges (AWG <-> mm2, ft <-> m).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional, Tuple

try:
    import numpy as _np

    # NumPy 2.0+ compatibility: Pint < 0.24 binds legacy NumPy 1.x aliases removed in NumPy 2.0
    _np_compat_aliases = {
        "cumproduct": "cumprod",
        "product": "prod",
        "alltrue": "all",
        "sometrue": "any",
        "trapz": "trapezoid",
        "round_": "round",
    }
    for _alias, _target in _np_compat_aliases.items():
        if not hasattr(_np, _alias) and hasattr(_np, _target):
            setattr(_np, _alias, getattr(_np, _target))
except ImportError:
    pass

import sys

# Python 3.13+ compatibility: Pint < 0.24 uses @dataclass(frozen=True) inheriting from non-frozen classes
if sys.version_info >= (3, 13):
    try:
        import dataclasses as _dc

        if hasattr(_dc, "_process_class"):
            _orig_process_class = _dc._process_class

            def _compat_process_class(*args, **kwargs):
                try:
                    return _orig_process_class(*args, **kwargs)
                except TypeError as err:
                    if "cannot inherit frozen dataclass from a non-frozen one" in str(err):
                        if len(args) > 6:
                            args_list = list(args)
                            args_list[6] = False
                            return _orig_process_class(*args_list, **kwargs)
                        elif "frozen" in kwargs:
                            kwargs_copy = dict(kwargs)
                            kwargs_copy["frozen"] = False
                            return _orig_process_class(*args, **kwargs_copy)
                    raise

            _dc._process_class = _compat_process_class
    except Exception:
        pass

import pint

# Initialize central unit registry
ureg = pint.UnitRegistry()
# Define domain-specific electrical engineering units in Pint
ureg.define("pu = [] = per_unit = p_u")
ureg.define("var = volt * ampere = VAR = Var = VAr")
ureg.define("cal_cm2 = cal / (centimeter ** 2) = cal_per_sq_cm")

# Dimensionality constants
DIM_CURRENT = ureg.ampere.dimensionality
DIM_VOLTAGE = ureg.volt.dimensionality
DIM_POWER = ureg.watt.dimensionality
DIM_APPARENT_POWER = ureg.volt_ampere.dimensionality
DIM_REACTIVE_POWER = ureg.var.dimensionality
DIM_IMPEDANCE = ureg.ohm.dimensionality
DIM_TIME = ureg.second.dimensionality
DIM_LENGTH = ureg.meter.dimensionality
DIM_AREA = (ureg.meter**2).dimensionality
DIM_RESISTIVITY = (ureg.ohm * ureg.meter).dimensionality
DIM_INCIDENT_ENERGY = (ureg.joule / (ureg.meter**2)).dimensionality
DIM_DIMENSIONLESS = ureg.dimensionless.dimensionality
DIM_ANGLE = ureg.radian.dimensionality
DIM_FREQUENCY = ureg.hertz.dimensionality
DIM_ADMITTANCE = ureg.siemens.dimensionality

# Comprehensive mapping covering all parameters in core_model/specs.py and api/tool_policy.py
EXPECTED_DIMENSIONS: dict[str, tuple[pint.util.UnitsContainer, ...]] = {
    # Current
    "bolted_fault_current": (DIM_CURRENT,),
    "bolted_fault_ka": (DIM_CURRENT,),
    "ik_double_prime": (DIM_CURRENT,),
    "current_ka": (DIM_CURRENT,),
    "current_a": (DIM_CURRENT,),
    "rated_current": (DIM_CURRENT,),
    "rated_current_a": (DIM_CURRENT,),
    "load_current": (DIM_CURRENT,),
    "load_current_a": (DIM_CURRENT,),
    "cable_ampacity": (DIM_CURRENT,),

    # Voltage & Operating Setpoints
    "voltage_setpoint": (DIM_VOLTAGE, DIM_DIMENSIONLESS),
    "base_kv": (DIM_VOLTAGE,),
    "voltage_kv": (DIM_VOLTAGE,),
    "voltage_v": (DIM_VOLTAGE,),
    "nominal_voltage": (DIM_VOLTAGE,),
    "rated_voltage": (DIM_VOLTAGE,),
    "primary_kv": (DIM_VOLTAGE,),
    "secondary_kv": (DIM_VOLTAGE,),
    "voltage_magnitude": (DIM_VOLTAGE, DIM_DIMENSIONLESS),
    "min_voltage_pu": (DIM_DIMENSIONLESS,),
    "max_voltage_pu": (DIM_DIMENSIONLESS,),

    # Angle
    "voltage_angle": (DIM_ANGLE, DIM_DIMENSIONLESS),
    "angle_deg": (DIM_ANGLE, DIM_DIMENSIONLESS),
    "phase_shift_deg": (DIM_ANGLE, DIM_DIMENSIONLESS),
    "phase_shift": (DIM_ANGLE, DIM_DIMENSIONLESS),

    # Power & Injections
    "base_mva": (DIM_APPARENT_POWER, DIM_POWER),
    "rating_mva": (DIM_APPARENT_POWER, DIM_POWER),
    "rated_mva": (DIM_APPARENT_POWER, DIM_POWER),
    "mva_rating": (DIM_APPARENT_POWER, DIM_POWER),
    "p_mw": (DIM_POWER, DIM_APPARENT_POWER),
    "q_mvar": (DIM_POWER, DIM_APPARENT_POWER, DIM_REACTIVE_POWER),
    "load_power_real": (DIM_POWER, DIM_APPARENT_POWER),
    "load_power_imag": (DIM_POWER, DIM_APPARENT_POWER, DIM_REACTIVE_POWER),
    "active_power": (DIM_POWER, DIM_APPARENT_POWER),
    "reactive_power": (DIM_POWER, DIM_APPARENT_POWER, DIM_REACTIVE_POWER),
    "generation_real": (DIM_POWER, DIM_APPARENT_POWER),
    "generation_imag": (DIM_POWER, DIM_APPARENT_POWER, DIM_REACTIVE_POWER),
    "short_circuit_level": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT),
    "fault_level": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT),
    "load_flow_limit": (DIM_POWER, DIM_APPARENT_POWER, DIM_CURRENT, DIM_DIMENSIONLESS),

    # Impedance & Admittance
    "r1": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "x1": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "r0": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "x0": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "line_impedance": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "transformer_impedance": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "internal_impedance": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "ra": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "xd_prime": (DIM_IMPEDANCE, DIM_DIMENSIONLESS),
    "bshunt1": (DIM_ADMITTANCE, DIM_DIMENSIONLESS),
    "bshunt0": (DIM_ADMITTANCE, DIM_DIMENSIONLESS),

    # Dimensionless
    "tap_ratio": (DIM_DIMENSIONLESS,),
    "power_factor": (DIM_DIMENSIONLESS,),
    "conductor_size": (DIM_AREA, DIM_DIMENSIONLESS),

    # Frequency
    "frequency_hz": (DIM_FREQUENCY,),
    "frequency": (DIM_FREQUENCY,),

    # Protection & Grounding & Arc Flash
    "soil_resistivity": (DIM_RESISTIVITY,),
    "fault_clearing_time": (DIM_TIME,),
    "working_distance": (DIM_LENGTH,),
    "length_km": (DIM_LENGTH,),
    "length_ft": (DIM_LENGTH,),
    "length_m": (DIM_LENGTH,),
    "incident_energy": (DIM_INCIDENT_ENERGY,),
    "earth_fault_setting": (DIM_CURRENT, DIM_TIME, DIM_DIMENSIONLESS),
}

# Regex to detect strings that specify units (e.g., "25 kA", "10V", "5.2 cal/cm²", "10 deg")
_UNIT_STR_PATTERN = re.compile(
    r"^\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z_/%²°]+(?:\s*[*/^0-9\-_a-zA-Z²]+)*)\s*$"
)

# Standard NEC / AWG to metric mm² cross-section table
AWG_TO_MM2: Dict[str, float] = {
    "14 AWG": 2.08,
    "12 AWG": 3.31,
    "10 AWG": 5.26,
    "8 AWG": 8.37,
    "6 AWG": 13.3,
    "4 AWG": 21.2,
    "3 AWG": 26.7,
    "2 AWG": 33.6,
    "1 AWG": 42.4,
    "1/0 AWG": 53.5,
    "2/0 AWG": 67.4,
    "3/0 AWG": 85.0,
    "4/0 AWG": 107.2,
    "250 kcmil": 126.7,
    "300 kcmil": 152.0,
    "350 kcmil": 177.3,
    "400 kcmil": 202.7,
    "500 kcmil": 253.4,
    "600 kcmil": 304.0,
    "750 kcmil": 380.0,
    "1000 kcmil": 506.7,
}


def parse_quantity(value: Any) -> Optional[pint.Quantity]:
    """Attempt to parse a value into a pint.Quantity.

    Supports:
      - Pint Quantity objects directly
      - Strings like '25.0 kA', '120 V', '5.2 cal/cm²', '100 MVA', '10 deg', '1.05 pu'
      - Dicts like {'value': 25.0, 'unit': 'kA'}
    Returns None if value has no explicit unit or cannot be parsed.
    """
    if isinstance(value, pint.Quantity):
        return value

    if isinstance(value, dict) and "value" in value and "unit" in value:
        try:
            num = float(value["value"])
            unit_str = str(value["unit"]).strip()
            clean = unit_str.replace("²", "**2").replace("cal/cm2", "cal / (cm**2)")
            u_low = clean.lower()
            if u_low in ("deg", "degree", "degrees", "°"):
                clean = "degree"
            elif u_low in ("pu", "p.u.", "per_unit"):
                clean = "pu"
            elif u_low in ("mvar", "mvar_reactive"):
                clean = "megavar"
            elif u_low in ("kvar", "kvar_reactive"):
                clean = "kilovar"
            return ureg.Quantity(num, clean)
        except Exception:
            return None

    if isinstance(value, str):
        match = _UNIT_STR_PATTERN.match(value.strip())
        if match:
            num_str, unit_str = match.groups()
            clean_unit = unit_str.replace("²", "**2").replace("cal/cm2", "cal / (cm**2)")
            u_low = clean_unit.lower()
            if u_low in ("deg", "degree", "degrees", "°"):
                clean_unit = "degree"
            elif u_low in ("pu", "p.u.", "per_unit"):
                clean_unit = "pu"
            elif u_low in ("mvar",):
                clean_unit = "megavar"
            elif u_low in ("kvar",):
                clean_unit = "kilovar"
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


def validate_parameter_dimension(param_name: str, value: Any) -> Tuple[bool, Optional[str]]:
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


def normalize_quantity(
    value: Any,
    quantity_kind: str,
    base_val: Optional[float] = None,
) -> Tuple[float, Optional[float]]:
    """Normalize a physical quantity to canonical SI/platform unit and per-unit value.

    Parameters
    ----------
    value : Any
        Numeric value, string with units (e.g. '120 V', '25 kA', '1.05 pu'),
        or dict {'value': 120, 'unit': 'V'}.
    quantity_kind : str
        One of 'voltage', 'current', 'power', 'apparent_power', 'reactive_power',
        'impedance', 'angle', 'length', 'time', 'frequency'.
    base_val : float | None
        Base value for per-unit calculations (e.g. base_kv for voltage, base_mva for power).

    Returns
    -------
    tuple[float, float | None]
        (canonical_value, pu_value)
        - canonical_value: in standard platform unit (kV for voltage, kA for current,
          MW/MVA for power, ohm for impedance, rad for angle, m for length, s for time).
        - pu_value: per-unit value if base_val provided or if input was already in pu.
    """
    kind = quantity_kind.lower().strip()
    qty = parse_quantity(value)

    if qty is None:
        try:
            num = float(value)
            if base_val and base_val > 0:
                return num, num / base_val
            return num, None
        except (ValueError, TypeError):
            raise ValueError(f"Cannot parse numeric quantity from: {value!r}")

    unit_str = str(qty.units).lower()
    is_pu = unit_str in ("pu", "per_unit", "dimensionless") and ("degree" not in unit_str and "rad" not in unit_str)

    if is_pu:
        pu_val = float(qty.magnitude)
        canonical_val = (pu_val * base_val) if (base_val and base_val > 0) else pu_val
        return canonical_val, pu_val

    if kind == "voltage":
        # Canonical is kV
        val_kv = float(qty.to("kV").magnitude)
        pu_val = (val_kv / base_val) if (base_val and base_val > 0) else None
        return val_kv, pu_val

    if kind in ("power", "apparent_power", "active_power"):
        # Canonical is MW / MVA
        val_mw = float(qty.to("MW").magnitude)
        pu_val = (val_mw / base_val) if (base_val and base_val > 0) else None
        return val_mw, pu_val

    if kind in ("reactive_power",):
        # Canonical is MVAr
        val_mvar = float(qty.to("megavar").magnitude)
        pu_val = (val_mvar / base_val) if (base_val and base_val > 0) else None
        return val_mvar, pu_val

    if kind == "current":
        # Canonical is kA
        val_ka = float(qty.to("kA").magnitude)
        pu_val = (val_ka / base_val) if (base_val and base_val > 0) else None
        return val_ka, pu_val

    if kind == "impedance":
        # Canonical is ohm
        val_ohm = float(qty.to("ohm").magnitude)
        pu_val = (val_ohm / base_val) if (base_val and base_val > 0) else None
        return val_ohm, pu_val

    if kind == "angle":
        # Canonical internal is rad
        if "deg" in unit_str or "arcdeg" in unit_str:
            val_deg = float(qty.magnitude)
            val_rad = math.radians(val_deg)
        else:
            val_rad = float(qty.to("radian").magnitude)
        return val_rad, None

    if kind == "length":
        val_m = float(qty.to("m").magnitude)
        return val_m, None

    if kind == "time":
        val_s = float(qty.to("s").magnitude)
        return val_s, None

    if kind == "frequency":
        val_hz = float(qty.to("Hz").magnitude)
        return val_hz, None

    return float(qty.magnitude), None


# ─── Angle conversion utilities ─────────────────────────────────────────────
def deg_to_rad(deg: float) -> float:
    """Convert angle from degrees to radians."""
    return math.radians(deg)


def rad_to_deg(rad: float) -> float:
    """Convert angle from radians to degrees."""
    return math.degrees(rad)


def normalize_angle(value: Any, target_unit: str = "rad") -> float:
    """Normalize angle value to target unit ('rad' or 'deg')."""
    qty = parse_quantity(value)
    if qty is None:
        num = float(value)
        # Plain numeric assumed to be in target_unit
        return num

    unit_name = str(qty.units).lower()
    if "deg" in unit_name or "arcdeg" in unit_name:
        deg_val = float(qty.magnitude)
        return deg_val if target_unit == "deg" else math.radians(deg_val)

    rad_val = float(qty.to("radian").magnitude)
    return math.degrees(rad_val) if target_unit == "deg" else rad_val


# ─── Cable sizing bridge: AWG <-> mm² and ft <-> m ──────────────────────────
def awg_to_mm2(awg_str: str) -> Optional[float]:
    """Convert AWG/kcmil designation string to cross-sectional area in mm²."""
    clean = awg_str.strip()
    return AWG_TO_MM2.get(clean)


def mm2_to_nearest_awg(mm2: float) -> str:
    """Find the smallest standard AWG/kcmil cable whose cross section is >= mm²."""
    candidates = sorted(AWG_TO_MM2.items(), key=lambda x: x[1])
    for name, area in candidates:
        if area >= mm2:
            return name
    return "1000 kcmil+"


def ft_to_m(ft: float) -> float:
    """Convert feet to meters."""
    return ft * 0.3048


def m_to_ft(m: float) -> float:
    """Convert meters to feet."""
    return m / 0.3048
