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

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Dict, Optional

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
    ik_initial: complex  # Initial symmetrical short-circuit current (pu)
    Ik_initial_magnitude: float  # Initial symmetrical current magnitude (kA)
    ip_peak: float  # Peak current (kA)
    Ib_breaking: float  # Breaking current (kA)
    Ik_steady: float  # Steady-state current (kA)
    Ith_thermal: float  # Thermal equivalent current (kA)
    voltage_factor_c: float  # Voltage factor used
    fault_location: str = ""
    # Sequence currents (pu)
    i_positive: complex = complex(0, 0)
    i_negative: complex = complex(0, 0)
    i_zero: complex = complex(0, 0)
    # Phase currents (pu)
    ia: complex = complex(0, 0)
    ib: complex = complex(0, 0)
    ic: complex = complex(0, 0)
    # Near-generator factors and branch contributions
    is_near_generator: bool = False
    mu_factor: float = 1.0
    lambda_factor: float = 1.0
    kappa_factor: float = 1.0
    branch_contributions: List[Dict[str, Any]] = field(default_factory=list)


def calculate_kg(
    un_kv: float,
    urg_kv: float,
    c_max: float,
    xd_pp: float,
    cos_phi_rg: float = 0.8,
) -> float:
    """
    Calculate generator impedance correction factor KG per IEC 60909-0:2016 Clause 3.6.1.

    KG = (Un / UrG) * (c_max / (1 + xd'' * sin(phi_rG)))

    Parameters
    ----------
    un_kv : float
        Nominal system voltage (kV).
    urg_kv : float
        Rated generator voltage (kV).
    c_max : float
        Voltage factor c_max (e.g. 1.10 for HV/MV).
    xd_pp : float
        Subtransient reactance of generator in per unit.
    cos_phi_rg : float
        Rated generator power factor (default 0.8).

    Returns
    -------
    float
        Correction factor KG.
    """
    sin_phi = float(np.sqrt(max(0.0, 1.0 - cos_phi_rg**2)))
    denom = 1.0 + xd_pp * sin_phi
    if denom <= 0:
        return 1.0
    return float((un_kv / urg_kv) * (c_max / denom))


def calculate_kt(
    c_max: float,
    xt: float,
    ut_lv_kv: float | None = None,
    un_kv: float | None = None,
) -> float:
    """
    Calculate network transformer impedance correction factor KT per IEC 60909-0:2016 Clause 3.3.3.

    KT = 0.95 * (c_max / (1 + 0.6 * xT))

    Parameters
    ----------
    c_max : float
        Voltage factor c_max.
    xt : float
        Transformer reactance in per unit (xT = uk / 100).
    ut_lv_kv, un_kv : float, optional
        Voltage ratio adjustment if applicable.

    Returns
    -------
    float
        Correction factor KT.
    """
    denom = 1.0 + 0.6 * xt
    if denom <= 0:
        return 1.0
    kt = 0.95 * (c_max / denom)
    if ut_lv_kv is not None and un_kv is not None and un_kv > 0:
        kt *= un_kv / ut_lv_kv
    return float(kt)


def calculate_ku(
    un_kv: float,
    urthv_kv: float,
    urtlv_kv: float,
    urg_kv: float,
    c_max: float,
    xd_pp: float,
    xt: float,
    cos_phi_rg: float = 0.8,
    has_oltc: bool = False,
) -> float:
    """
    Calculate power station unit (generator + transformer block) correction factor KU (or KS)
    per IEC 60909-0:2016 Clause 3.7.

    Without on-load tap-changer:
    KU = (Un / UrTHV) * (UrTLV / UrG) * (c_max / (1 + |xd'' - xT| * sin(phi_rG)))

    With on-load tap-changer (KSAT):
    KU = (Un^2 / UrTHV^2) * (c_max / (1 + xd'' * sin(phi_rG)))
    """
    sin_phi = float(np.sqrt(max(0.0, 1.0 - cos_phi_rg**2)))
    if has_oltc:
        denom = 1.0 + xd_pp * sin_phi
        if denom <= 0:
            return 1.0
        return float(((un_kv / urthv_kv) ** 2) * (c_max / denom))
    else:
        denom = 1.0 + abs(xd_pp - xt) * sin_phi
        if denom <= 0:
            return 1.0
        return float((un_kv / urthv_kv) * (urtlv_kv / urg_kv) * (c_max / denom))


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
        ybus_pos: npt.NDArray[
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ybus_neg: npt.NDArray[
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ybus_zero: npt.NDArray[
            np.complexfloating
        ],  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        base_mva: float = 100.0,
        base_kv: float = 115.0,
        generators: list[Any] | None = None,
        r_override: dict[int, float] | None = None,
        frequency_hz: float = 50.0,
        slack_bus_index: int | None = None,
        branches: list[dict[str, Any]] | None = None,
        generator_type: str = "salient",
        irg_pu: float = 1.0,
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
        slack_bus_index (int): Optional index of slack/reference bus to resolve singularity.
        branches (list): Optional branch models for calculating branch current contributions.
        generator_type (str): 'salient' or 'turbo' for steady-state current factor lambda.
        irg_pu (float): Rated generator current in per unit.
        """
        self.Ybus_pos = ybus_pos  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.Ybus_neg = ybus_neg  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.Ybus_zero = ybus_zero  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.n_buses = ybus_pos.shape[0]
        self.base_mva = base_mva
        self.base_kv = base_kv
        self.generators = generators or []
        self.r_override = r_override or {}
        self.frequency_hz = max(1.0, float(frequency_hz))  # SECURITY: S-20 — was hardcoded 50.0
        self.slack_bus_index = slack_bus_index
        self.branches = branches or []
        self.generator_type = generator_type
        self.irg_pu = irg_pu

        # Base impedance and current
        self.base_z = (base_kv**2) / base_mva  # ohms
        self.base_i = (base_mva * 1000) / (base_kv * np.sqrt(3))  # amps

        # Compute Zbus matrices (inverse of Ybus)
        self._compute_zbus()

    def _invert_matrix(self, ybus: npt.NDArray[np.complexfloating]) -> npt.NDArray[np.complexfloating]:
        """Invert Ybus to Zbus, resolving singularity via slack removal or pseudo-inverse."""
        if ybus is None:
            return None
        n = ybus.shape[0]
        is_singular = False
        try:
            cond = np.linalg.cond(ybus)
            if cond > 1e12 or np.isnan(cond) or np.isinf(cond):
                is_singular = True
        except Exception:
            is_singular = True

        if is_singular:
            s = self.slack_bus_index
            if s is not None and 0 <= s < n:
                rem_idx = [i for i in range(n) if i != s]
                y_rem = ybus[np.ix_(rem_idx, rem_idx)]
                try:
                    z_rem = np.linalg.inv(y_rem)
                except Exception:
                    z_rem = np.linalg.pinv(y_rem)
                zbus = np.zeros((n, n), dtype=complex)
                for i_new, i_orig in enumerate(rem_idx):
                    for j_new, j_orig in enumerate(rem_idx):
                        zbus[i_orig, j_orig] = z_rem[i_new, j_new]
                return zbus
            return np.linalg.pinv(ybus)

        try:
            return np.linalg.inv(ybus)
        except np.linalg.LinAlgError:
            return np.linalg.pinv(ybus)

    def _compute_zbus(self) -> None:
        """Compute Zbus matrices from Ybus."""
        self.Zbus_pos = self._invert_matrix(self.Ybus_pos)
        self.Zbus_neg = self._invert_matrix(self.Ybus_neg)
        self.Zbus_zero = self._invert_matrix(self.Ybus_zero)

    def is_near_generator(self, ik_initial_pu: float, irg_pu: float = 1.0) -> bool:
        """
        Determine if fault is near-to-generator per IEC 60909-0 Clause 4.5.
        Near-to-generator: Ik'' / IrG >= 2.0 (decay occurs in ac component).
        Far-from-generator: Ik'' / IrG < 2.0 (negligible ac decay, Ib = Ik'').
        """
        ratio = ik_initial_pu / max(1e-6, irg_pu)
        return ratio >= 2.0

    def _calculate_lambda(
        self,
        ik_initial_pu: float,
        irg_pu: float = 1.0,
        generator_type: str = "salient",
        maximum: bool = True,
        xd_pu: float = 1.2,
    ) -> float:
        """
        Calculate factor lambda for steady-state short-circuit current Ik per IEC 60909-0 Clause 4.6.

        Ik = lambda * IrG (for near-generator faults)
        Ik = Ik'' (for far-from-generator faults, lambda = Ik''/IrG)
        """
        ratio = ik_initial_pu / max(1e-6, irg_pu)
        if ratio < 2.0:
            # Far from generator: Ik = Ik"
            return ratio

        if not maximum:
            # Minimum steady-state current (underexcited / constant excitation)
            return float(min(ratio, max(0.5, 1.0 / max(0.1, xd_pu))))

        # Maximum steady-state current (ceiling excitation, IEC 60909-0 Figures 13 & 14)
        if generator_type.lower() in ("salient", "salient_pole", "hydro"):
            # Salient-pole machine curve
            lam = 0.88 + 0.46 * np.exp(-0.27 * min(ratio, 10.0)) + 0.15 * min(ratio, 5.0)
            return float(min(lam, 2.5))
        else:
            # Cylindrical rotor / turbo-generator
            lam = 0.75 + 0.55 * np.exp(-0.30 * min(ratio, 10.0)) + 0.12 * min(ratio, 5.0)
            return float(min(lam, 2.0))

    def calculate_branch_contributions(
        self,
        fault_bus_index: int,
        if_pu: complex,
        branches: list[dict[str, Any]] | None = None,
        c_factor: float = 1.10,
    ) -> list[dict[str, Any]]:
        """
        Calculate individual branch current contributions during a fault at fault_bus_index.

        Parameters
        ----------
        fault_bus_index : int
            Index of faulted bus.
        if_pu : complex
            Fault current injection in per-unit.
        branches : list[dict], optional
            Branch configurations with from_bus, to_bus, r, x (or z1).
        c_factor : float
            Pre-fault voltage factor.

        Returns
        -------
        list[dict]
            Branch contribution entries.
        """
        contributions: list[dict[str, Any]] = []
        br_list = branches if branches is not None else self.branches
        if not br_list:
            return contributions

        # Compute fault voltages at all buses: V_fault = V_pre - Zbus[:, fault_bus] * If
        v_pre = complex(c_factor, 0.0)
        z_col = self.Zbus_pos[:, fault_bus_index]
        v_fault = np.full(self.n_buses, v_pre, dtype=complex) - z_col * if_pu

        for br in br_list:
            fb = br.get("from_bus", br.get("from_bus_id", 0))
            tb = br.get("to_bus", br.get("to_bus_id", 0))
            if isinstance(fb, int) and isinstance(tb, int) and fb < self.n_buses and tb < self.n_buses:
                z = br.get("z1", complex(br.get("r", br.get("r1", 0.0)), br.get("x", br.get("x1", 0.01))))
                if abs(z) > 1e-12:
                    i_branch = (v_fault[fb] - v_fault[tb]) / z
                    i_ka = abs(i_branch) * self.base_i / 1000.0
                    contributions.append({
                        "from_bus": fb,
                        "to_bus": tb,
                        "current_pu": complex(i_branch),
                        "current_magnitude_pu": float(abs(i_branch)),
                        "current_ka": float(i_ka),
                        "angle_deg": float(np.angle(i_branch, deg=True)),
                    })
        return contributions

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
        self,
        ik_initial_pu: float,
        t_min: float | None = None,
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
            mu = 0.84 + 0.26 * np.exp(-0.26 * min(ik_initial_pu, 20.0))
        elif t_min <= 0.05:
            mu = 0.71 + 0.51 * np.exp(-0.30 * min(ik_initial_pu, 20.0))
        else:
            mu = 0.62 + 0.72 * np.exp(-0.32 * min(ik_initial_pu, 20.0))
        return min(mu, 1.0)

    def _calculate_thermal_factor(
        self,
        ik_initial: float,
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
            if ik_initial > 0:
                n_simplified = (ip / ik_initial - 1.0) ** 2
                n = min(n, n_simplified)
        else:
            n = 0.0

        # Factor m
        m = m_factor

        ith = (
            ik_initial * np.sqrt(m + n)
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        return ith

    def calculate_three_phase_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
        **kwargs: Any,
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
        v_pre = c_factor * 1.0  # NOSONAR

        # Positive sequence driving point impedance
        Z1 = self.Zbus_pos[bus_index, bus_index]

        # Initial symmetrical short-circuit current (per-unit)
        ik_pu = (
            v_pre / Z1
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Convert to kA
        ik_ka = (
            abs(ik_pu) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Breaking current
        mu = self._calculate_mu(abs(ik_pu), t_min)
        ib = (
            mu * ik_ka
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state current: near vs far generator
        is_near = self.is_near_generator(abs(ik_pu), self.irg_pu)
        if is_near:
            lambda_factor = self._calculate_lambda(
                abs(ik_pu), self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * self.base_i / 1000.0)
        else:
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal current
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch contributions
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ik_pu, branches=branch_list, c_factor=c_factor
        )

        # Phase currents (balanced three-phase fault)
        ia = ik_pu  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ib_phase = (
            ik_pu * np.exp(1j * (-2 * np.pi / 3))
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ic_phase = (
            ik_pu * np.exp(1j * (2 * np.pi / 3))
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.THREE_PHASE.value,
            fault_bus_index=bus_index,
            ik_initial=ik_pu,
            Ik_initial_magnitude=ik_ka,
            ip_peak=ip,
            Ib_breaking=ib,
            Ik_steady=Ik_steady,
            Ith_thermal=ith,
            voltage_factor_c=c_factor,
            i_positive=ik_pu,
            i_negative=complex(0, 0),
            i_zero=complex(0, 0),
            ia=ia,
            ib=ib_phase,
            ic=ic_phase,
            is_near_generator=is_near,
            mu_factor=mu,
            lambda_factor=lambda_factor,
            kappa_factor=kappa,
            branch_contributions=branch_contribs,
        )

    def calculate_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
        **kwargs: Any,
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

        v_pre = (
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents for SLG fault: I0 = I1 = I2 (series connection)
        I1 = v_pre / (Z1 + Z2 + Z0)
        I2 = I1
        I0 = I1

        # Phase A current = 3 * I1 (for SLG fault)
        ia = (
            3 * I1
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Convert to kA
        ik_ka = (
            abs(ia) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current (use positive sequence impedance for kappa)
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        ib = (
            mu * ik_ka
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        is_near = self.is_near_generator(abs(ia), self.irg_pu)
        if is_near:
            lambda_factor = self._calculate_lambda(
                abs(ia), self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * self.base_i / 1000.0)
        else:
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch contributions
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ia, branches=branch_list, c_factor=c_factor
        )

        # Phase currents
        ib_phase = complex(
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ic_phase = complex(
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        return ShortCircuitResult(
            fault_type=FaultType.LINE_TO_GROUND.value,
            fault_bus_index=bus_index,
            ik_initial=ia,
            Ik_initial_magnitude=ik_ka,
            ip_peak=ip,
            Ib_breaking=ib,
            Ik_steady=Ik_steady,
            Ith_thermal=ith,
            voltage_factor_c=c_factor,
            i_positive=I1,
            i_negative=I2,
            i_zero=I0,
            ia=ia,
            ib=ib_phase,
            ic=ic_phase,
            is_near_generator=is_near,
            mu_factor=mu,
            lambda_factor=lambda_factor,
            kappa_factor=kappa,
            branch_contributions=branch_contribs,
        )

    def calculate_line_to_line_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
        **kwargs: Any,
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

        v_pre = (
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]

        # Sequence currents
        I1 = v_pre / (Z1 + Z2)
        I2 = -I1
        I0 = complex(0, 0)

        # Phase currents for LL fault (B-C fault)
        # I2 = -I1, I0 = 0 for line-to-line fault
        ia = complex(
            0, 0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        a_op = np.exp(1j * 2 * np.pi / 3)
        a2_op = np.exp(-1j * 2 * np.pi / 3)
        ib_phase = (
            a2_op * I1 + a_op * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ic_phase = (
            a_op * I1 + a2_op * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Magnitude of fault current
        ik_pu = abs(
            ib_phase
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ik_ka = (
            ik_pu * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        ib = (
            mu * ik_ka
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        is_near = self.is_near_generator(ik_pu, self.irg_pu)
        if is_near:
            lambda_factor = self._calculate_lambda(
                ik_pu, self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * self.base_i / 1000.0)
        else:
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch contributions
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ib_phase, branches=branch_list, c_factor=c_factor
        )

        return ShortCircuitResult(
            fault_type=FaultType.LINE_TO_LINE.value,
            fault_bus_index=bus_index,
            ik_initial=ib_phase,
            Ik_initial_magnitude=ik_ka,
            ip_peak=ip,
            Ib_breaking=ib,
            Ik_steady=Ik_steady,
            Ith_thermal=ith,
            voltage_factor_c=c_factor,
            i_positive=I1,
            i_negative=I2,
            i_zero=I0,
            ia=ia,
            ib=ib_phase,
            ic=ic_phase,
            is_near_generator=is_near,
            mu_factor=mu,
            lambda_factor=lambda_factor,
            kappa_factor=kappa,
            branch_contributions=branch_contribs,
        )

    def calculate_double_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float = 115.0,
        maximum: bool = True,
        t_min: float | None = None,
        t_k: float = 1.0,
        **kwargs: Any,
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

        v_pre = (
            c_factor * 1.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]

        # Sequence currents
        z2_z0_parallel = (
            (Z2 * Z0) / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        I1 = v_pre / (Z1 + z2_z0_parallel)
        I2 = -I1 * Z0 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)
        I0 = -I1 * Z2 / (Z2 + Z0) if (Z2 + Z0) != 0 else complex(0, 0)

        # Phase currents using symmetrical component transformation
        a = np.exp(1j * 2 * np.pi / 3)
        a2 = np.exp(-1j * 2 * np.pi / 3)
        ia = (
            I1 + I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ib_phase = (
            a2 * I1 + a * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ic_phase = (
            a * I1 + a2 * I2 + I0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Use the larger of Ib and Ic for magnitude
        ik_ka = (
            max(abs(ib_phase), abs(ic_phase)) * self.base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Breaking current
        mu = self._calculate_mu(abs(I1), t_min)
        ib = (
            mu * ik_ka
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Steady-state
        ik_max_pu = max(abs(ib_phase), abs(ic_phase))
        is_near = self.is_near_generator(ik_max_pu, self.irg_pu)
        if is_near:
            lambda_factor = self._calculate_lambda(
                ik_max_pu, self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * self.base_i / 1000.0)
        else:
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch contributions
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, max(ib_phase, ic_phase, key=abs), branches=branch_list, c_factor=c_factor
        )

        return ShortCircuitResult(
            fault_type=FaultType.DOUBLE_LINE_TO_GROUND.value,
            fault_bus_index=bus_index,
            ik_initial=max(ib_phase, ic_phase, key=abs),
            Ik_initial_magnitude=ik_ka,
            ip_peak=ip,
            Ib_breaking=ib,
            Ik_steady=Ik_steady,
            Ith_thermal=ith,
            voltage_factor_c=c_factor,
            i_positive=I1,
            i_negative=I2,
            i_zero=I0,
            ia=ia,
            ib=ib_phase,
            ic=ic_phase,
            is_near_generator=is_near,
            mu_factor=mu,
            lambda_factor=lambda_factor,
            kappa_factor=kappa,
            branch_contributions=branch_contribs,
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
