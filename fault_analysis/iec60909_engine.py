"""
IEC 60909 Short Circuit Calculation Engine

Implements IEC 60909-0:2016 "Short-circuit currents in three-phase AC systems"
Supports:
- Three-phase short circuit
- Line-to-ground (single-phase) short circuit
- Line-to-line short circuit
- Double line-to-ground short circuit

Calculates:
- Initial symmetrical short-circuit current Ik"
- Peak short-circuit current ip
- Symmetrical short-circuit breaking current Ib
- Steady-state short-circuit current Ik
- Thermal equivalent short-circuit current Ith
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import numpy as np
import numpy.typing as npt


class FaultType(Enum):
    THREE_PHASE = "three_phase"
    LINE_TO_GROUND = "line_to_ground"
    LINE_TO_LINE = "line_to_line"
    DOUBLE_LINE_TO_GROUND = "double_line_to_ground"


class VoltageFactorC(Enum):
    """IEC 60909 voltage factor c for maximum and minimum short-circuit currents."""

    C_MAX_HV = 1.10  # c_max for HV (>= 35 kV)
    C_MAX_MV = 1.10  # c_max for MV (1-35 kV)
    C_MAX_LV = 1.05  # c_max for LV with +6% tolerance
    C_MIN_HV = 1.00  # c_min for HV
    C_MIN_MV = 1.00  # c_min for MV
    C_MIN_LV = 0.95  # c_min for LV


@dataclass
class ShortCircuitResult:
    """Result of a short circuit calculation."""

    fault_type: str
    fault_bus_index: int
    Ik_initial: complex  # Initial symmetrical current (kA)  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    Ik_initial_magnitude: float  # magnitude of initial symmetrical current (kA)  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    ip_peak: float  # Peak current (kA)
    Ib_breaking: float  # Breaking current (kA)  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    Ik_steady: float  # Steady-state current (kA)  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    Ith_thermal: float  # Thermal equivalent current (kA)  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    voltage_factor_c: float  # Voltage factor used
    fault_location: str = ""
    # Sequence currents
    I_positive: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    I_negative: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    I_zero: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    # Phase currents
    Ia: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    Ib: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
    Ic: complex = complex(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
        0, 0
    )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability


# Default R/X ratio when the bus impedance is purely resistive (imaginary
# part near zero). IEC 60909-0:2016 Section 4.3.1.2 recommends a high R/X
# value (typically 10.0) for this edge case to avoid division by zero.
_DEFAULT_RX_RATIO = 10.0


class IEC60909Engine:
    """
    IEC 60909 Short Circuit Calculation Engine.
    """

    def __init__(
        self,
        Ybus_pos: npt.NDArray[  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ybus_neg: npt.NDArray[  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ybus_zero: npt.NDArray[  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        base_mva: float = 100.0,
        base_kv: float = 115.0,
        generators: list[Any] | None = None,
        r_override: dict[int, float] | None = None,
        frequency_hz: float = 50.0,
    ) -> None:
        """
        Initialize the IEC 60909 engine.

        Parameters:
        Ybus_pos (numpy.ndarray): Positive sequence Ybus.
        Ybus_neg (numpy.ndarray): Negative sequence Ybus.
        Ybus_zero (numpy.ndarray): Zero sequence Ybus.
        base_mva (float): Base MVA.
        base_kv (float): Base kV (line-to-line).
        generators (list): List of generator objects with impedance info.
        r_override (dict): Override R/X ratios for specific buses.
        """
        self.Ybus_pos = Ybus_pos  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.Ybus_neg = Ybus_neg  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.Ybus_zero = Ybus_zero  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.n_buses = Ybus_pos.shape[0]
        self.base_mva = base_mva
        self.base_kv = base_kv
        self.generators = generators or []
        self.r_override = r_override or {}
        self.frequency_hz = max(1.0, float(frequency_hz))  # SECURITY: S-20 — was hardcoded 50.0

        # Base impedance and current
        self.base_z = (base_kv**2) / base_mva  # ohms
        self.base_i = (base_mva * 1000) / (base_kv * np.sqrt(3))  # amps

        # Compute Zbus matrices (inverse of Ybus)
        self._compute_zbus()

    def _compute_zbus(self) -> None:
        """Compute Zbus matrices from Ybus."""
        try:
            self.Zbus_pos = np.linalg.inv(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
                self.Ybus_pos
            )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        except np.linalg.LinAlgError:
            self.Zbus_pos = np.linalg.pinv(self.Ybus_pos)
        try:
            self.Zbus_neg = np.linalg.inv(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
                self.Ybus_neg
            )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        except np.linalg.LinAlgError:
            self.Zbus_neg = np.linalg.pinv(self.Ybus_neg)
        try:
            self.Zbus_zero = np.linalg.inv(  # S116 field names use engineering notation; snake_case would harm domain readability  # NOSONAR: IEEE/IEC engineering notation — domain-standard names (S116)
                self.Ybus_zero
            )  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        except np.linalg.LinAlgError:
            self.Zbus_zero = np.linalg.pinv(self.Ybus_zero)

    def _get_voltage_factor(self, bus_kv: float, maximum: bool = True) -> float:
        """
        Get IEC 60909 voltage factor c.

        Parameters:
        bus_kv (float): Nominal voltage at bus in kV.
        maximum (bool): True for maximum, False for minimum short-circuit current.

        Returns:
        float: Voltage factor c.
        """
        if maximum:
            if bus_kv >= 35.0:
                return VoltageFactorC.C_MAX_HV.value
            elif bus_kv > 1.0:
                return VoltageFactorC.C_MAX_MV.value
            else:
                return VoltageFactorC.C_MAX_LV.value
        else:
            if bus_kv >= 35.0:
                return VoltageFactorC.C_MIN_HV.value
            elif bus_kv > 1.0:
                return VoltageFactorC.C_MIN_MV.value
            else:
                return VoltageFactorC.C_MIN_LV.value

    def _get_rx_ratio(self, bus_index: int) -> float:
        """
        Get the R/X ratio at a bus for peak current calculation.

        Per IEC 60909, the R/X ratio determines the peak factor kappa.
        """
        z_pos = self.Zbus_pos[bus_index, bus_index]
        # SECURITY AUDIT 2026-07-25 — Fix S-21: Use z_pos.imag (not abs).
        # Per IEC 60909 Clause 4.3.3.1, R/X ratio uses the actual (signed) imaginary
        # component. Using abs() incorrectly makes inductive/capacitive X equivalent.
        rx_ratio = z_pos.real / z_pos.imag if z_pos.imag != 0 else _DEFAULT_RX_RATIO
        return rx_ratio

    def _calculate_kappa(self, bus_index: int) -> float:
        """
        Calculate the peak factor kappa per IEC 60909.

        kappa = 1.02 + 0.98 * exp(-3 * R/X)

        Returns:
        float: Peak factor kappa (1.0 to 2.0).
        """
        rx = self._get_rx_ratio(bus_index)
        kappa = 1.02 + 0.98 * np.exp(-3.0 * rx)
        return min(kappa, 2.0)  # kappa max is 2.0

    def _calculate_mu(
        self, Ik_initial_pu: float, t_min: float | None = None  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
    ) -> float:  # NOSONAR physics/engineering notation
        """
        Calculate the factor mu for breaking current per IEC 60909.

        mu depends on the minimum delay time and the ratio Ik/Ib.

        Parameters:
        Ik_initial_pu (float): Initial symmetrical current in per-unit.
        t_min (float | None): Minimum delay time in seconds. If None,
            derived from self.frequency_hz (one cycle: 1/freq).

        Returns:
        float: Factor mu.
        """
        # SECURITY (S-IEC-1): Derive t_min from frequency if not provided.
        # 50Hz → 0.02s, 60Hz → 0.01667s per IEC 60909.
        if t_min is None:
            t_min = 1.0 / self.frequency_hz

        # Simplified mu calculation
        # For t_min = 0.02s (50Hz): mu = 0.84 + 0.26 * exp(-0.26 * Ikg/IrG)
        # For t_min = 0.05s: mu = 0.71 + 0.51 * exp(-0.3 * Ikg/IrG)
        if t_min <= 0.02:
            mu = 0.84 + 0.26 * np.exp(-0.26 * min(Ik_initial_pu, 20.0))
        elif t_min <= 0.05:
            mu = 0.71 + 0.51 * np.exp(-0.30 * min(Ik_initial_pu, 20.0))
        else:
            mu = 0.62 + 0.72 * np.exp(-0.32 * min(Ik_initial_pu, 20.0))
        return min(mu, 1.0)

    def _calculate_thermal_factor(
        self,
        Ik_initial: float,  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
        ip: float,
        t_k: float = 1.0,
        m_factor: float = 1.0,  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    ) -> float:
        """
        Calculate thermal equivalent current Ith per IEC 60909.

        Ith = Ik" * sqrt(m + n)

        Where:
        m = factor for heat dissipation (depends on Ik"/Ik ratio)
        n = factor for aperiodic component

        Parameters:
        Ik_initial (float): Initial symmetrical current magnitude (kA).
        ip (float): Peak current (kA).
        t_k (float): Short-circuit duration (seconds).
        m_factor (float): Factor m for heat dissipation.

        Returns:
        float: Thermal equivalent current Ith (kA).
        """
        # Factor n (aperiodic component)
        if t_k > 0:
            f = self.frequency_hz  # SECURITY AUDIT 2026-07-25 — Fix S-20: was hardcoded 50 Hz
            n = 2.0 * (1.0 / (4.0 * f * t_k)) * (1.0 - np.exp(-2.0 * f * t_k))
            # Simplified: n ≈ (ip/Ik" - 1)^2 for short durations
            if Ik_initial > 0:
                n_simplified = (ip / Ik_initial - 1.0) ** 2
                n = min(n, n_simplified)
        else:
            n = 0.0

        # Factor m
        m = m_factor

        Ith = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_initial * np.sqrt(m + n)
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        return Ith

    def calculate_three_phase_fault(
        self,
        bus_index: int,
        c_factor: Optional[float] = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
    ) -> ShortCircuitResult:
        """
        Calculate three-phase short-circuit current per IEC 60909.

        Ik" = c * Un / (sqrt(3) * Z1)

        Parameters:
        bus_index (int): Index of the faulted bus.
        c_factor (float): Voltage factor (if None, calculated from bus_kv).
        bus_kv (float): Nominal voltage at bus (kV).
        maximum (bool): Maximum or minimum short-circuit current.
        t_min (float): Minimum delay time for breaking current (seconds).
        t_k (float): Short-circuit duration for thermal current (seconds).

        Returns:
        ShortCircuitResult
        """
        if c_factor is None:
            c_factor = self._get_voltage_factor(bus_kv, maximum)

        # Pre-fault voltage (per-unit)
        V_pre = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            c_factor * 1.0
        )  # c * Un/Un = c in per-unit  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Positive sequence driving point impedance
        Z1 = self.Zbus_pos[bus_index, bus_index]

        # Initial symmetrical short-circuit current (per-unit)
        Ik_pu = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            V_pre / Z1
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Convert to kA
        Ik_kA = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            abs(Ik_pu) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(Ik_pu), t_min)
        Ib = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            mu * Ik_kA
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state current (simplified: Ik = Ik" for far-from-generator faults)
        Ik_steady = Ik_kA  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Thermal current
        Ith = self._calculate_thermal_factor(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_kA, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Phase currents (balanced three-phase fault)
        Ia = Ik_pu  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ib_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_pu * np.exp(1j * (-2 * np.pi / 3))
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ic_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_pu * np.exp(1j * (2 * np.pi / 3))
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.THREE_PHASE.value,
            fault_bus_index=bus_index,
            Ik_initial=Ik_pu,
            Ik_initial_magnitude=Ik_kA,
            ip_peak=ip,
            Ib_breaking=Ib,
            Ik_steady=Ik_steady,
            Ith_thermal=Ith,
            voltage_factor_c=c_factor,
            I_positive=Ik_pu,
            I_negative=complex(0, 0),
            I_zero=complex(0, 0),
            Ia=Ia,
            Ib=Ib_phase,
            Ic=Ic_phase,
        )

    def calculate_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: Optional[float] = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
    ) -> ShortCircuitResult:
        """
        Calculate single line-to-ground short-circuit current per IEC 60909.

        I1 = c * Un / (Z1 + Z2 + Z0)

        Parameters:
        bus_index (int): Index of the faulted bus.
        c_factor (float): Voltage factor.
        bus_kv (float): Nominal voltage at bus (kV).
        maximum (bool): Maximum or minimum short-circuit current.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        if c_factor is None:
            c_factor = self._get_voltage_factor(bus_kv, maximum)

        V_pre = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents for SLG fault: I0 = I1 = I2 (series connection)
        I1 = V_pre / (Z1 + Z2 + Z0)
        I2 = I1
        I0 = I1

        # Phase A current = 3 * I1 (for SLG fault)
        Ia = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            3 * I1
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Convert to kA
        Ik_kA = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            abs(Ia) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current (use positive sequence impedance for kappa)
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            mu * Ik_kA
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        Ik_steady = Ik_kA  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Thermal
        Ith = self._calculate_thermal_factor(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_kA, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Phase currents
        Ib_phase = complex(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ic_phase = complex(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.LINE_TO_GROUND.value,
            fault_bus_index=bus_index,
            Ik_initial=Ia,
            Ik_initial_magnitude=Ik_kA,
            ip_peak=ip,
            Ib_breaking=Ib,
            Ik_steady=Ik_steady,
            Ith_thermal=Ith,
            voltage_factor_c=c_factor,
            I_positive=I1,
            I_negative=I2,
            I_zero=I0,
            Ia=Ia,
            Ib=Ib_phase,
            Ic=Ic_phase,
        )

    def calculate_line_to_line_fault(
        self,
        bus_index: int,
        c_factor: Optional[float] = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
    ) -> ShortCircuitResult:
        """
        Calculate line-to-line short-circuit current per IEC 60909.

        I1 = c * Un / (Z1 + Z2)

        Parameters:
        bus_index (int): Index of the faulted bus.
        c_factor (float): Voltage factor.
        bus_kv (float): Nominal voltage at bus (kV).
        maximum (bool): Maximum or minimum.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        if c_factor is None:
            c_factor = self._get_voltage_factor(bus_kv, maximum)

        V_pre = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]

        # Sequence currents
        I1 = V_pre / (Z1 + Z2)
        I2 = -I1
        I0 = complex(0, 0)

        # Phase currents for LL fault (B-C fault)
        # I2 = -I1, I0 = 0 for line-to-line fault
        Ia = complex(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        a_op = np.exp(1j * 2 * np.pi / 3)
        a2_op = np.exp(-1j * 2 * np.pi / 3)
        Ib_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            a2_op * I1 + a_op * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ic_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            a_op * I1 + a2_op * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Magnitude of fault current
        Ik_pu = abs(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ib_phase
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ik_kA = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_pu * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            mu * Ik_kA
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        Ik_steady = Ik_kA  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Thermal
        Ith = self._calculate_thermal_factor(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_kA, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.LINE_TO_LINE.value,
            fault_bus_index=bus_index,
            Ik_initial=Ib_phase,
            Ik_initial_magnitude=Ik_kA,
            ip_peak=ip,
            Ib_breaking=Ib,
            Ik_steady=Ik_steady,
            Ith_thermal=Ith,
            voltage_factor_c=c_factor,
            I_positive=I1,
            I_negative=I2,
            I_zero=I0,
            Ia=Ia,
            Ib=Ib_phase,
            Ic=Ic_phase,
        )

    def calculate_double_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: Optional[float] = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
    ) -> ShortCircuitResult:
        """
        Calculate double line-to-ground short-circuit current per IEC 60909.

        I1 = c * Un / (Z1 + Z2*Z0/(Z2+Z0))

        Parameters:
        bus_index (int): Index of the faulted bus.
        c_factor (float): Voltage factor.
        bus_kv (float): Nominal voltage at bus (kV).
        maximum (bool): Maximum or minimum.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        if c_factor is None:
            c_factor = self._get_voltage_factor(bus_kv, maximum)

        V_pre = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents
        Z2_Z0_parallel = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            (Z2 * Z0) / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        I1 = V_pre / (Z1 + Z2_Z0_parallel)
        I2 = -I1 * Z0 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        I0 = -I1 * Z2 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)

        # Phase currents using symmetrical component transformation
        a = np.exp(1j * 2 * np.pi / 3)
        a2 = np.exp(-1j * 2 * np.pi / 3)
        Ia = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            I1 + I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ib_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            a2 * I1 + a * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ic_phase = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            a * I1 + a2 * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Use the larger of Ib and Ic for magnitude
        Ik_kA = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            max(abs(Ib_phase), abs(Ic_phase)) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = (  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            mu * Ik_kA
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        Ik_steady = Ik_kA  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Thermal
        Ith = self._calculate_thermal_factor(  # S117 engineering-notation variable names (e.g. Iarc, delta_V); snake_case would harm domain readability NOSONAR
            Ik_kA, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.DOUBLE_LINE_TO_GROUND.value,
            fault_bus_index=bus_index,
            Ik_initial=max(Ib_phase, Ic_phase, key=abs),
            Ik_initial_magnitude=Ik_kA,
            ip_peak=ip,
            Ib_breaking=Ib,
            Ik_steady=Ik_steady,
            Ith_thermal=Ith,
            voltage_factor_c=c_factor,
            I_positive=I1,
            I_negative=I2,
            I_zero=I0,
            Ia=Ia,
            Ib=Ib_phase,
            Ic=Ic_phase,
        )

    def calculate(
        self, fault_type: str | FaultType, bus_index: int, **kwargs: Any
    ) -> ShortCircuitResult:
        """
        Calculate short-circuit current for a given fault type.

        Parameters:
        fault_type (str or FaultType): Type of fault.
        bus_index (int): Index of the faulted bus.
        **kwargs: Additional parameters.

        Returns:
        ShortCircuitResult
        """
        if isinstance(fault_type, str):
            fault_type = FaultType(fault_type)

        if fault_type == FaultType.THREE_PHASE:
            return self.calculate_three_phase_fault(bus_index, **kwargs)
        elif fault_type == FaultType.LINE_TO_GROUND:
            return self.calculate_line_to_ground_fault(bus_index, **kwargs)
        elif fault_type == FaultType.LINE_TO_LINE:
            return self.calculate_line_to_line_fault(bus_index, **kwargs)
        elif fault_type == FaultType.DOUBLE_LINE_TO_GROUND:
            return self.calculate_double_line_to_ground_fault(bus_index, **kwargs)
        else:
            raise ValueError(f"Unsupported fault type: {fault_type}")
