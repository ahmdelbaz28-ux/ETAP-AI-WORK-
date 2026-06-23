def to_per_unit(value, base_value):
    """
    Convert a value to per-unit.

    Parameters:
    value (float): Actual value.
    base_value (float): Base value for conversion.

    Returns:
    float: Per-unit value.
    """
    return value / base_value


def from_per_unit(pu_value, base_value):
    """
    Convert a per-unit value to actual value.

    Parameters:
    pu_value (float): Per-unit value.
    base_value (float): Base value for conversion.

    Returns:
    float: Actual value.
    """
    return pu_value * base_value


def power_to_per_unit(power_watts, base_mva):
    """
    Convert power in watts to per-unit on base MVA.

    Parameters:
    power_watts (float): Power in watts.
    base_mva (float): Base MVA.

    Returns:
    float: Per-unit power.
    """
    return power_watts / (base_mva * 1e6)


def impedance_to_per_unit(impact_ohms, base_voltage_kv, base_mva):
    """
    Convert impedance in ohms to per-unit.

    Parameters:
    impact_ohms (float or complex): Impedance in ohms.
    base_voltage_kv (float): Base voltage in kV (line-to-line).
    base_mva (float): Base MVA.

    Returns:
    complex: Per-unit impedance.
    """
    base_ohms = (base_voltage_kv**2) / base_mva
    return impact_ohms / base_ohms


def admittance_to_per_unit(admit_siemens, base_voltage_kv, base_mva):
    """
    Convert admittance in siemens to per-unit.

    Parameters:
    admit_siemens (float or complex): Admittance in siemens.
    base_voltage_kv (float): Base voltage in kV (line-to-line).
    base_mva (float): Base MVA.

    Returns:
    complex: Per-unit admittance.
    """
    base_siemens = base_mva / (base_voltage_kv**2)
    return admit_siemens / base_siemens
