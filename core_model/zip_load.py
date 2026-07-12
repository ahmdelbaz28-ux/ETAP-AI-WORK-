"""
ZIP Load Model for Power System Analysis

Implements the ZIP load model:
P = P0 * (aZ * V^2 + aI * V + aP)
Q = Q0 * (bZ * V^2 + bI * V + bP)

Where:
- aZ, aI, aP are the constant impedance, current, and power fractions for active power
- bZ, bI, bP are the constant impedance, current, and power fractions for reactive power
- aZ + aI + aP = 1.0
- bZ + bI + bP = 1.0
- V is the voltage magnitude in per-unit
- P0, Q0 are the nominal active and reactive power

Reference: IEEE Task Force on Load Representation, "Load Representation for
Dynamic Performance Analysis", IEEE Trans. Power Systems, 1993.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ZIPCoefficients:
    """ZIP load model coefficients."""

    aZ: float = 0.0  # Constant impedance fraction (active power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    aI: float = 0.0  # Constant current fraction (active power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    aP: float = 1.0  # Constant power fraction (active power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    bZ: float = 0.0  # Constant impedance fraction (reactive power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    bI: float = 0.0  # Constant current fraction (reactive power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    bP: float = 1.0  # Constant power fraction (reactive power)  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability

    def __post_init__(self):
        """Validate that coefficients sum to 1.0."""
        a_sum = self.aZ + self.aI + self.aP
        b_sum = self.bZ + self.bI + self.bP
        if abs(a_sum - 1.0) > 0.01:
            raise ValueError(f"Active power ZIP coefficients must sum to 1.0, got {a_sum:.4f}")
        if abs(b_sum - 1.0) > 0.01:
            raise ValueError(f"Reactive power ZIP coefficients must sum to 1.0, got {b_sum:.4f}")


# Common ZIP load model presets
ZIP_PRESETS = {
    "constant_power": ZIPCoefficients(aZ=0.0, aI=0.0, aP=1.0, bZ=0.0, bI=0.0, bP=1.0),
    "constant_impedance": ZIPCoefficients(aZ=1.0, aI=0.0, aP=0.0, bZ=1.0, bI=0.0, bP=0.0),
    "constant_current": ZIPCoefficients(aZ=0.0, aI=1.0, aP=0.0, bZ=0.0, bI=1.0, bP=0.0),
    # IEEE typical residential load
    "residential_ieee": ZIPCoefficients(aZ=0.25, aI=0.15, aP=0.60, bZ=0.25, bI=0.15, bP=0.60),
    # IEEE typical commercial load
    "commercial_ieee": ZIPCoefficients(aZ=0.10, aI=0.10, aP=0.80, bZ=0.10, bI=0.10, bP=0.80),
    # IEEE typical industrial load
    "industrial_ieee": ZIPCoefficients(aZ=0.15, aI=0.15, aP=0.70, bZ=0.15, bI=0.15, bP=0.70),
    # Mixed urban load
    "mixed_urban": ZIPCoefficients(aZ=0.20, aI=0.20, aP=0.60, bZ=0.20, bI=0.20, bP=0.60),
}


class ZIPLoadModel:
    """
    ZIP Load Model for voltage-dependent load representation.
    """

    def __init__(
        self, P0: float, Q0: float, coefficients: ZIPCoefficients = None, preset: str = None,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    ):
        """
        Initialize ZIP load model.

        Parameters:
        P0 (float): Nominal active power at rated voltage (per-unit).
        Q0 (float): Nominal reactive power at rated voltage (per-unit).
        coefficients (ZIPCoefficients): Custom ZIP coefficients.
        preset (str): Name of a preset ZIP model.
        """
        self.P0 = P0
        self.Q0 = Q0

        if preset is not None and preset in ZIP_PRESETS:
            self.coefficients = ZIP_PRESETS[preset]
        elif coefficients is not None:
            self.coefficients = coefficients
        else:
            self.coefficients = ZIP_PRESETS["constant_power"]

    def calculate_power(self, V: float) -> tuple[float, float]:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Calculate load power at a given voltage.

        P = P0 * (aZ * V^2 + aI * V + aP)
        Q = Q0 * (bZ * V^2 + bI * V + bP)

        Parameters:
        V (float): Voltage magnitude in per-unit.

        Returns:
        tuple: (P, Q) active and reactive power at voltage V.
        """
        c = self.coefficients
        P = self.P0 * (c.aZ * V**2 + c.aI * V + c.aP)
        Q = self.Q0 * (c.bZ * V**2 + c.bI * V + c.bP)
        return P, Q

    def calculate_admittance(self, V: float) -> complex:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Calculate the equivalent admittance of the ZIP load at voltage V.

        For constant impedance component: Y = S* Union[/, V|^2]
        For constant current component: Y = S* / V (complex)
        For constant power component: Y = S* Union[/, V|^2] (but varies with V)

        The total equivalent admittance is:
        Y_eq = (P - jQ) Union[/, V|^2]

        Parameters:
        V (float): Voltage magnitude in per-unit.

        Returns:
        complex: Equivalent admittance.
        """
        if V < 0.01:
            return complex(0, 0)
        P, Q = self.calculate_power(V)
        S = complex(P, Q)
        Y_eq = np.conj(S) / (V**2)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        return Y_eq

    def get_impedance_component(self, V: float) -> complex:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Get only the constant-impedance component admittance.

        Parameters:
        V (float): Voltage magnitude in per-unit.

        Returns:
        complex: Admittance of constant-impedance portion.
        """
        c = self.coefficients
        P_z = self.P0 * c.aZ  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Q_z = self.Q0 * c.bZ  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        if V < 0.01:
            return complex(0, 0)
        return complex(P_z, -Q_z)  # V² cancels: (P_z - jQ_z) / V² * V² = P_z - jQ_z

    def voltage_sensitivity(self, V: float) -> tuple[float, float]:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Calculate voltage sensitivity of load power.

        dP/dV = P0 * (2*aZ*V + aI)
        dQ/dV = Q0 * (2*bZ*V + bI)

        Parameters:
        V (float): Voltage magnitude in per-unit.

        Returns:
        tuple: (dP/dV, dQ/dV)
        """
        c = self.coefficients
        dPdV = self.P0 * (2 * c.aZ * V + c.aI)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        dQdV = self.Q0 * (2 * c.bZ * V + c.bI)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        return dPdV, dQdV

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "P0": self.P0,
            "Q0": self.Q0,
            "aZ": self.coefficients.aZ,
            "aI": self.coefficients.aI,
            "aP": self.coefficients.aP,
            "bZ": self.coefficients.bZ,
            "bI": self.coefficients.bI,
            "bP": self.coefficients.bP,
        }

    @staticmethod
    def from_dict(data: dict) -> ZIPLoadModel:
        """Create ZIPLoadModel from dictionary."""
        coeffs = ZIPCoefficients(
            aZ=data.get("aZ", 0.0),
            aI=data.get("aI", 0.0),
            aP=data.get("aP", 1.0),
            bZ=data.get("bZ", 0.0),
            bI=data.get("bI", 0.0),
            bP=data.get("bP", 1.0),
        )
        return ZIPLoadModel(P0=data["P0"], Q0=data["Q0"], coefficients=coeffs)
