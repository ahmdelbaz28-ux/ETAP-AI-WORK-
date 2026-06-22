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

from dataclasses import dataclass
from enum import Enum

import numpy as np


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
    Ik_initial: complex  # Initial symmetrical current (kA)
    Ik_initial_magnitude: float  # |Ik"| (kA)
    ip_peak: float  # Peak current (kA)
    Ib_breaking: float  # Breaking current (kA)
    Ik_steady: float  # Steady-state current (kA)
    Ith_thermal: float  # Thermal equivalent current (kA)
    voltage_factor_c: float  # Voltage factor used
    fault_location: str = ""
    # Sequence currents
    I_positive: complex = complex(0, 0)
    I_negative: complex = complex(0, 0)
    I_zero: complex = complex(0, 0)
    # Phase currents
    Ia: complex = complex(0, 0)
    Ib: complex = complex(0, 0)
    Ic: complex = complex(0, 0)


class IEC60909Engine:
    """
    IEC 60909 Short Circuit Calculation Engine.
    """

    def __init__(
        self,
        Ybus_pos,
        Ybus_neg,
        Ybus_zero,
        base_mva=100.0,
        base_kv=115.0,
        generators=None,
        r_override=None,
    ):
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
        self.Ybus_pos = Ybus_pos
        self.Ybus_neg = Ybus_neg
        self.Ybus_zero = Ybus_zero
        self.n_buses = Ybus_pos.shape[0]
        self.base_mva = base_mva
        self.base_kv = base_kv
        self.generators = generators or []
        self.r_override = r_override or {}

        # Base impedance and current
        self.base_z = (base_kv**2) / base_mva  # ohms
        self.base_i = (base_mva * 1000) / (base_kv * np.sqrt(3))  # amps

        # Compute Zbus matrices (inverse of Ybus)
        self._compute_zbus()

    def _compute_zbus(self):
        """Compute Zbus matrices from Ybus."""
        try:
            self.Zbus_pos = np.linalg.inv(self.Ybus_pos)
        except np.linalg.LinAlgError:
            self.Zbus_pos = np.linalg.pinv(self.Ybus_pos)
        try:
            self.Zbus_neg = np.linalg.inv(self.Ybus_neg)
        except np.linalg.LinAlgError:
            self.Zbus_neg = np.linalg.pinv(self.Ybus_neg)
        try:
            self.Zbus_zero = np.linalg.inv(self.Ybus_zero)
        except np.linalg.LinAlgError:
            self.Zbus_zero = np.linalg.pinv(self.Ybus_zero)

    def _get_voltage_factor(self, bus_kv, maximum=True):
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

    def _get_rx_ratio(self, bus_index):
        """
        Get the R/X ratio at a bus for peak current calculation.

        Per IEC 60909, the R/X ratio determines the peak factor kappa.
        """
        z_pos = self.Zbus_pos[bus_index, bus_index]
        if z_pos.imag != 0:
            rx_ratio = z_pos.real / abs(z_pos.imag)
        else:
            rx_ratio = 10.0  # default high R/X for pure resistance
        return rx_ratio

    def _calculate_kappa(self, bus_index):
        """
        Calculate the peak factor kappa per IEC 60909.

        kappa = 1.02 + 0.98 * exp(-3 * R/X)

        Returns:
        float: Peak factor kappa (1.0 to 2.0).
        """
        rx = self._get_rx_ratio(bus_index)
        kappa = 1.02 + 0.98 * np.exp(-3.0 * rx)
        return min(kappa, 2.0)  # kappa max is 2.0

    def _calculate_mu(self, Ik_initial_pu, t_min=0.02):
        """
        Calculate the factor mu for breaking current per IEC 60909.

        mu depends on the minimum delay time and the ratio Ik/Ib.

        Parameters:
        Ik_initial_pu (float): Initial symmetrical current in per-unit.
        t_min (float): Minimum delay time in seconds (0.02 for 50Hz, 0.0167 for 60Hz).

        Returns:
        float: Factor mu.
        """
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

    def _calculate_thermal_factor(self, Ik_initial, ip, t_k=1.0, m_factor=1.0):
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
            f_50 = 50.0  # assume 50 Hz
            n = 2.0 * (1.0 / (4.0 * f_50 * t_k)) * (1.0 - np.exp(-2.0 * f_50 * t_k))
            # Simplified: n ≈ (ip/Ik" - 1)^2 for short durations
            if Ik_initial > 0:
                n_simplified = (ip / Ik_initial - 1.0) ** 2
                n = min(n, n_simplified)
        else:
            n = 0.0

        # Factor m
        m = m_factor

        Ith = Ik_initial * np.sqrt(m + n)
        return Ith

    def calculate_three_phase_fault(
        self, bus_index, c_factor=None, bus_kv=115.0, maximum=True, t_min=0.02, t_k=1.0
    ):
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
        V_pre = c_factor * 1.0  # c * Un/Un = c in per-unit

        # Positive sequence driving point impedance
        Z1 = self.Zbus_pos[bus_index, bus_index]

        # Initial symmetrical short-circuit current (per-unit)
        Ik_pu = V_pre / Z1

        # Convert to kA
        Ik_kA = abs(Ik_pu) * self.base_i / 1000.0

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(Ik_pu), t_min)
        Ib = mu * Ik_kA

        # Steady-state current (simplified: Ik = Ik" for far-from-generator faults)
        Ik_steady = Ik_kA

        # Thermal current
        Ith = self._calculate_thermal_factor(Ik_kA, ip, t_k)

        # Phase currents (balanced three-phase fault)
        Ia = Ik_pu
        Ib_phase = Ik_pu * np.exp(1j * (-2 * np.pi / 3))
        Ic_phase = Ik_pu * np.exp(1j * (2 * np.pi / 3))

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
        self, bus_index, c_factor=None, bus_kv=115.0, maximum=True, t_min=0.02, t_k=1.0
    ):
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

        V_pre = c_factor * 1.0

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents for SLG fault: I0 = I1 = I2 (series connection)
        I1 = V_pre / (Z1 + Z2 + Z0)
        I2 = I1
        I0 = I1

        # Phase A current = 3 * I1 (for SLG fault)
        Ia = 3 * I1

        # Convert to kA
        Ik_kA = abs(Ia) * self.base_i / 1000.0

        # Peak current (use positive sequence impedance for kappa)
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = mu * Ik_kA

        # Steady-state
        Ik_steady = Ik_kA

        # Thermal
        Ith = self._calculate_thermal_factor(Ik_kA, ip, t_k)

        # Phase currents
        Ib_phase = complex(0, 0)
        Ic_phase = complex(0, 0)

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
        self, bus_index, c_factor=None, bus_kv=115.0, maximum=True, t_min=0.02, t_k=1.0
    ):
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

        V_pre = c_factor * 1.0

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]

        # Sequence currents
        I1 = V_pre / (Z1 + Z2)
        I2 = -I1
        I0 = complex(0, 0)

        # Phase currents for LL fault (B-C fault)
        # I2 = -I1, I0 = 0 for line-to-line fault
        Ia = complex(0, 0)
        a_op = np.exp(1j * 2 * np.pi / 3)
        a2_op = np.exp(-1j * 2 * np.pi / 3)
        Ib_phase = a2_op * I1 + a_op * I2 + I0
        Ic_phase = a_op * I1 + a2_op * I2 + I0

        # Magnitude of fault current
        Ik_pu = abs(Ib_phase)
        Ik_kA = Ik_pu * self.base_i / 1000.0

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = mu * Ik_kA

        # Steady-state
        Ik_steady = Ik_kA

        # Thermal
        Ith = self._calculate_thermal_factor(Ik_kA, ip, t_k)

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
        self, bus_index, c_factor=None, bus_kv=115.0, maximum=True, t_min=0.02, t_k=1.0
    ):
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

        V_pre = c_factor * 1.0

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents
        Z2_Z0_parallel = (Z2 * Z0) / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        I1 = V_pre / (Z1 + Z2_Z0_parallel)
        I2 = -I1 * Z0 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        I0 = -I1 * Z2 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)

        # Phase currents using symmetrical component transformation
        a = np.exp(1j * 2 * np.pi / 3)
        a2 = np.exp(-1j * 2 * np.pi / 3)
        Ia = I1 + I2 + I0
        Ib_phase = a2 * I1 + a * I2 + I0
        Ic_phase = a * I1 + a2 * I2 + I0

        # Use the larger of Ib and Ic for magnitude
        Ik_kA = max(abs(Ib_phase), abs(Ic_phase)) * self.base_i / 1000.0

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * Ik_kA

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        Ib = mu * Ik_kA

        # Steady-state
        Ik_steady = Ik_kA

        # Thermal
        Ith = self._calculate_thermal_factor(Ik_kA, ip, t_k)

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

    def calculate(self, fault_type, bus_index, **kwargs):
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
            raise ValueError("Unsupported fault type: {}".format(fault_type))
