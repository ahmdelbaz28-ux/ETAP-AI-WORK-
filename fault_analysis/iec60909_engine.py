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
from typing import Any, Dict, List

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
    generator_contributions: List[Dict[str, Any]] = field(default_factory=list)


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
    Calculate power station unit (generator + unit transformer block) correction factor.

    Standard Normative References (IEC 60909-0:2016):
    - IEC 60909-0:2016 Clause 3.6.1: Generator correction factor K_G (calculated in calculate_kg).
    - IEC 60909-0:2016 Clause 3.3.3: Network transformer correction factor K_T (calculated in calculate_kt).
    - IEC 60909-0:2016 Clause 3.7: Power station unit blocks (generator + unit transformer) correction factor K_S.
      * Unit blocks WITHOUT on-load tap-changer (Clause 3.7):
          K_S (or K_SO / K_U) = (Un / UrTHV) * (UrTLV / UrG) * (c_max / (1 + |xd'' - xT| * sin(phi_rG)))
      * Unit blocks WITH on-load tap-changer (Clause 3.7):
          K_SAT = (Un^2 / UrTHV^2) * (c_max / (1 + xd'' * sin(phi_rG)))

    Naming Rationale:
    The function is named `calculate_ku` where 'U' designates the combined 'Unit block'
    (Kraftwerksbloecke) impedance correction factor, matching the ETAP convention K_U.
    In the standard text of IEC 60909-0 Clause 3.7, this factor is denoted K_S (or K_SO / K_SAT).
    This function specifically evaluates the combined unit block factor and must NOT be confused
    with individual generator correction factor K_G (Clause 3.6.1) or individual network transformer
    correction factor K_T (Clause 3.3.3).

    Parameters:
        un_kv: Nominal system voltage at connection point Q (kV).
        urthv_kv: Rated voltage of transformer HV winding (kV).
        urtlv_kv: Rated voltage of transformer LV winding (kV).
        urg_kv: Rated voltage of generator (kV).
        c_max: Voltage factor c_max per Table 1.
        xd_pp: Subtransient reactance of generator in pu.
        xt: Transformer reactance in pu.
        cos_phi_rg: Generator rated power factor (default 0.8).
        has_oltc: True if transformer has on-load tap-changer.

    Returns:
        float: Unit block correction factor K_U (equivalent to K_S / K_SO / K_SAT).
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




class IEC60909Engine:
    """
    IEC 60909 Short Circuit Calculation Engine.

    Implements IEC 60909-0:2016 calculations:
    - Initial symmetrical short-circuit current Ik"
    - Peak short-circuit current ip
    - Symmetrical short-circuit breaking current Ib
    - Steady-state short-circuit current Ik
    - Thermal equivalent short-circuit current Ith

    Impedance Correction Factors (KT, KG, KU/KS per IEC 60909-0 Clause 3.3.3, 3.6.1, 3.7):
    - Normative helper functions `calculate_kt`, `calculate_kg`, and `calculate_ku` provide exact standard factors.
    - Since pre-assembled admittance matrices (Ybus) are supplied at initialization, network-wide correction
      factors must be applied during network admittance assembly.
    - Detailed branch flows support `calculate_kt` via `calculate_branch_contributions(..., apply_kt=True)`.
    - Detailed generator flows support `calculate_kg` via `calculate_generator_contributions(..., apply_kg=True)`.
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
        base_kv: float | dict[Any, float] | None = None,
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
        base_kv (float or dict): Base kV (line-to-line), or dict mapping bus_id -> base_kv.
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
        self.bus_base_kv: dict[Any, float] = {}
        if isinstance(base_kv, dict):
            self.bus_base_kv = {k: float(v) for k, v in base_kv.items()}
            self.base_kv = base_kv
            self.base_z = None
            self.base_i = None
        elif base_kv is not None:
            kv_val = float(base_kv)
            self.base_kv = kv_val
            self.bus_base_kv = {i: kv_val for i in range(self.n_buses)}
            self.base_z = (kv_val**2) / base_mva  # ohms
            self.base_i = (base_mva * 1000) / (kv_val * np.sqrt(3))  # amps
        else:
            self.base_kv = None
            self.base_z = None
            self.base_i = None
        self.generators = generators or []
        self.r_override = r_override or {}
        self.frequency_hz = max(1.0, float(frequency_hz))  # SECURITY: S-20 — was hardcoded 50.0
        self.slack_bus_index = slack_bus_index
        self.branches = branches or []
        self.generator_type = generator_type
        self.irg_pu = irg_pu

        # Compute Zbus matrices (inverse of Ybus)
        self._compute_zbus()

    def get_bus_base_kv(self, bus_index: int | str, explicit_kv: float | None = None) -> float:
        """Get base_kv for a bus, failing closed if unavailable."""
        if explicit_kv is not None and float(explicit_kv) > 0:
            return float(explicit_kv)
        if bus_index in self.bus_base_kv:
            return float(self.bus_base_kv[bus_index])
        if isinstance(bus_index, int) and str(bus_index) in self.bus_base_kv:
            return float(self.bus_base_kv[str(bus_index)])
        if isinstance(bus_index, str) and bus_index.isdigit() and int(bus_index) in self.bus_base_kv:
            return float(self.bus_base_kv[int(bus_index)])
        raise ValueError(
            f"base_kv is missing for bus {bus_index} (fail-closed: no default base voltage permitted per IEC 60909)."
        )

    def get_bus_base_i(self, bus_index: int | str, explicit_kv: float | None = None) -> float:
        """Get base current (Amperes) for a bus."""
        kv = self.get_bus_base_kv(bus_index, explicit_kv)
        if kv <= 0:
            raise ValueError(f"Invalid base_kv={kv} for bus {bus_index}")
        return (self.base_mva * 1000.0) / (kv * np.sqrt(3))

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

        # Maximum steady-state current from IEC 60909-0:2016 Figures 13 & 14 (Series 1 excitation)
        gen_type = generator_type.lower()
        if gen_type in ("salient", "salient_pole", "hydro"):
            # IEC 60909-0:2016 Figure 14 (Salient-pole machine, Series 1)
            ratios = np.array([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0], dtype=float)
            lambdas = np.array([1.38, 1.55, 1.70, 1.83, 1.95, 2.05, 2.14, 2.28], dtype=float)
            lam = float(np.interp(min(ratio, 6.0), ratios, lambdas))
            return float(min(lam, 2.5))
        elif gen_type in ("turbo", "turbogenerator", "cylindrical"):
            # IEC 60909-0:2016 Figure 13 (Cylindrical rotor / turbo-generator, Series 1)
            ratios = np.array([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0], dtype=float)
            lambdas = np.array([1.14, 1.25, 1.36, 1.46, 1.55, 1.63, 1.70, 1.82], dtype=float)
            lam = float(np.interp(min(ratio, 6.0), ratios, lambdas))
            return float(min(lam, 2.0))
        else:
            raise ValueError(
                f"Unknown generator type '{generator_type}'; must be 'salient' or 'turbo' per IEC 60909 Clause 4.6."
            )

    def calculate_branch_contributions(
        self,
        fault_bus_index: int,
        if_pu: complex,
        branches: list[dict[str, Any]] | None = None,
        c_factor: float = 1.10,
        apply_kt: bool = True,
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
        apply_kt : bool
            Whether to apply transformer correction factor KT per IEC 60909-0 Clause 3.3.3.

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
                # Connect KT for transformer branches per IEC 60909-0:2016 Clause 3.3.3
                is_trafo = bool(
                    br.get("is_transformer", False)
                    or br.get("branch_type") == "transformer"
                    or br.get("type") == "transformer"
                )
                kt = 1.0
                kt_applied = False
                if is_trafo and br.get("apply_kt", apply_kt):
                    xt_val = float(br.get("xt", abs(z.imag)))
                    kt = calculate_kt(
                        c_max=c_factor,
                        xt=xt_val,
                        ut_lv_kv=br.get("ut_lv_kv"),
                        un_kv=br.get("un_kv"),
                    )
                    z = z * kt
                    kt_applied = True
                if abs(z) > 1e-12:
                    i_branch = (v_fault[fb] - v_fault[tb]) / z
                    i_ka = abs(i_branch) * self.base_i / 1000.0
                    entry: dict[str, Any] = {
                        "from_bus": fb,
                        "to_bus": tb,
                        "current_pu": complex(i_branch),
                        "current_magnitude_pu": float(abs(i_branch)),
                        "current_ka": float(i_ka),
                        "angle_deg": float(np.angle(i_branch, deg=True)),
                    }
                    if is_trafo:
                        entry["is_transformer"] = True
                        entry["kt_factor"] = float(kt) if kt_applied else 1.0
                    contributions.append(entry)
        return contributions

    def calculate_generator_contributions(
        self,
        fault_bus_index: int,
        c_factor: float = 1.10,
        apply_kg: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Calculate individual generator current contributions per IEC 60909-0 Clause 3.6 / 3.7.
        Applies generator impedance correction factor KG (via calculate_kg).
        """
        contributions: list[dict[str, Any]] = []
        if not self.generators:
            return contributions

        v_pre = complex(c_factor, 0.0)
        z_col = self.Zbus_pos[:, fault_bus_index]
        v_fault = np.full(self.n_buses, v_pre, dtype=complex) - z_col * 1.0

        for gen in self.generators:
            bus_idx = getattr(gen, "bus_index", getattr(gen, "bus_id", None))
            if bus_idx is None or not (0 <= bus_idx < self.n_buses):
                continue
            xd_pp = float(getattr(gen, "xd_pp", getattr(gen, "xd_subtransient", 0.15)))
            urg_kv = float(getattr(gen, "urg_kv", getattr(gen, "rated_kv", self.get_bus_base_kv(bus_idx))))
            un_kv = self.get_bus_base_kv(bus_idx)
            cos_phi = float(getattr(gen, "cos_phi", 0.8))
            z_gen = complex(float(getattr(gen, "rg", 0.0)), xd_pp)
            kg_val = 1.0
            if apply_kg:
                kg_val = calculate_kg(un_kv=un_kv, urg_kv=urg_kv, c_max=c_factor, xd_pp=xd_pp, cos_phi_rg=cos_phi)
                z_gen = z_gen * kg_val
            if abs(z_gen) > 1e-12:
                i_gen = v_fault[bus_idx] / z_gen
                i_ka = abs(i_gen) * self.get_bus_base_i(bus_idx) / 1000.0
                contributions.append({
                    "bus_index": bus_idx,
                    "generator_id": getattr(gen, "generator_id", getattr(gen, "id", f"gen_{bus_idx}")),
                    "current_pu": complex(i_gen),
                    "current_magnitude_pu": float(abs(i_gen)),
                    "current_ka": float(i_ka),
                    "kg_factor": float(kg_val),
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
        Get the equivalent R/X ratio at a bus for peak current calculation.

        Standard Normative Reference:
        IEC 60909-0:2016 Clause 4.3.3.1 (Short-circuit impedance and R/X ratio).

        Signed R/X Ratio Justification:
        Per IEC 60909 Clause 4.3.3.1, the ratio R/X is determined from the complex short-circuit
        impedance Z_k = R + jX using the actual signed imaginary component `z_pos.imag`
        (not abs). In physical AC power systems, inductive reactance (X > 0) governs the rate
        of DC decaying offset during faults. Retaining the signed value ensures physical
        correctness and prevents erroneously treating inductive and capacitive reactances as
        equivalent (Fix S-21).

        Parameters:
            bus_index (int): Index of the bus in the network admittance matrix.

        Returns:
            float: Signed R/X ratio at the short-circuit location, or _DEFAULT_RX_RATIO if X == 0.
        """
        z_pos = self.Zbus_pos[bus_index, bus_index]
        if -1e-12 < z_pos.imag < 1e-12:
            raise ValueError(
                f"Bus {bus_index} positive sequence reactance is zero (X=0); R/X ratio is undefined per IEC 60909 Clause 4.3.3.1."
            )
        rx_ratio = z_pos.real / z_pos.imag
        return rx_ratio

    def _calculate_kappa(self, bus_index: int) -> float:
        """
        Calculate peak factor kappa per IEC 60909-0:2016 Clause 4.3.1.2 (Method A: Uniform ratio R/X).

        Standard Normative Reference:
        IEC 60909-0:2016 Clause 4.3.1.2 defines Method A (Uniform ratio R/X):
            kappa = 1.02 + 0.98 * exp(-3.0 * (R/X))

        Mathematical & Physical Clamping Limits [1.0, 2.0]:
        - Upper bound (kappa = 2.0): As R/X -> 0 (purely inductive fault, zero resistance damping),
          exp(0) = 1.0, giving kappa = 1.02 + 0.98 = 2.00. This represents the theoretical
          maximum asymmetrical peak fault current with 100% DC offset.
        - Lower bound (kappa -> 1.02): For large R/X ratios (e.g. R/X >= 10, predominantly resistive
          or damped networks), exp(-3 * R/X) -> 0, asymptotically approaching 1.02 where the DC
          transient component decays almost instantaneously.
        - The standard clamps kappa to a maximum ceiling of 2.0: min(kappa, 2.0).

        Method Scope:
        This engine implements Method A (Uniform ratio R/X, Clause 4.3.1.2) only.
        Methods B and C are not implemented in this engine.

        Parameters:
            bus_index (int): Bus index for retrieving the R/X ratio.

        Returns:
            float: Peak factor kappa clamped to the standard range [1.0, 2.0].
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
        m_factor: float | None = None,
        is_near: bool = False,
        ik_steady: float | None = None,
    ) -> float:
        """
        Calculate thermal equivalent current Ith per IEC 60909-0 Clause 4.8.

        Ith = Ik" * sqrt(m + n)

        Parameters:
        ik_initial (float): Initial symmetrical current magnitude (kA).
        ip (float): Peak current (kA).
        t_k (float): Short-circuit duration (seconds).
        m_factor (float | None): Factor m for heat dissipation. If None and is_near=False, m=1.0.
        is_near (bool): Whether the fault is near to generator.
        ik_steady (float | None): Steady-state current magnitude (kA).

        Returns:
        float: Thermal equivalent current Ith (kA).
        """
        if t_k <= 0:
            raise ValueError("Short-circuit duration t_k must be positive.")

        # Factor n (aperiodic component)
        f = self.frequency_hz
        n = 2.0 * (1.0 / (4.0 * f * t_k)) * (1.0 - np.exp(-2.0 * f * t_k))
        if ik_initial > 0:
            n_simplified = (ip / ik_initial - 1.0) ** 2
            n = min(n, n_simplified)

        # Factor m (periodic component per IEC 60909-0 Clause 4.8)
        if m_factor is not None:
            if m_factor < 0:
                raise ValueError("m_factor must be non-negative.")
            m = m_factor
        elif not is_near:
            # Far from generator per Clause 4.8.1: negligible AC decay, m = 1.0
            m = 1.0
        else:
            # Near generator per Clause 4.8.2: calculate AC decay integral
            if ik_initial <= 0 or ik_steady is None:
                raise ValueError(
                    "Near-generator fault requires explicit m_factor or steady-state current to calculate thermal factor m per IEC 60909."
                )
            a = min(1.0, max(0.0, ik_steady / ik_initial))
            b = 1.0 - a
            tau = 0.1  # typical machine transient time constant (s)
            m = a**2 + (2.0 * a * b * tau / t_k) * (1.0 - np.exp(-t_k / tau)) + (b**2 * tau / (2.0 * t_k)) * (1.0 - np.exp(-2.0 * t_k / tau))
            m = float(min(1.0, max(0.0, m)))

        ith = ik_initial * np.sqrt(m + n)
        return ith

    def calculate_three_phase_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float | None = None,
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
        bus_kv (float): Nominal voltage at bus (kV). If None, looked up from base_kv map.
        maximum (bool): Maximum or minimum short-circuit current.
        t_min (float): Minimum delay time for breaking current (seconds).
        t_k (float): Short-circuit duration for thermal current (seconds).

        Returns:
        ShortCircuitResult
        """
        actual_kv = self.get_bus_base_kv(bus_index, bus_kv)
        if c_factor is None:
            c_factor = self._get_voltage_factor(actual_kv, maximum)

        # Pre-fault voltage (per-unit)
        v_pre = c_factor * 1.0  # NOSONAR

        # Positive sequence driving point impedance
        Z1 = self.Zbus_pos[bus_index, bus_index]

        # Initial symmetrical short-circuit current (per-unit)
        ik_pu = (
            v_pre / Z1
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Convert to kA using bus base current
        bus_base_i = self.get_bus_base_i(bus_index, actual_kv)
        ik_ka = (
            abs(ik_pu) * bus_base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Steady-state and breaking current: determine near vs far generator first (IEC 60909-0 Clause 4.5)
        is_near = self.is_near_generator(abs(ik_pu), self.irg_pu)
        if is_near:
            mu = self._calculate_mu(abs(ik_pu), t_min)
            ib = mu * ik_ka
            lambda_factor = self._calculate_lambda(
                abs(ik_pu), self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * bus_base_i / 1000.0)
        else:
            # Far from generator: negligible AC decay per IEC 60909-0 Clause 4.5 (Ib = Ik'', lambda = 1.0)
            mu = 1.0
            ib = ik_ka
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal current
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k, m_factor=kwargs.get("m_factor"), is_near=is_near, ik_steady=Ik_steady
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch and generator contributions
        apply_kt = kwargs.get("apply_kt", True)
        apply_kg = kwargs.get("apply_kg", True)
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ik_pu, branches=branch_list, c_factor=c_factor, apply_kt=apply_kt
        )
        generator_contribs = self.calculate_generator_contributions(
            bus_index, c_factor=c_factor, apply_kg=apply_kg
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
            generator_contributions=generator_contribs,
        )

    def calculate_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float | None = None,
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
        bus_kv (float): Nominal voltage at bus (kV). If None, looked up from base_kv map.
        maximum (bool): Maximum or minimum short-circuit current.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        actual_kv = self.get_bus_base_kv(bus_index, bus_kv)
        if c_factor is None:
            c_factor = self._get_voltage_factor(actual_kv, maximum)

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

        # Convert to kA using bus base current
        bus_base_i = self.get_bus_base_i(bus_index, actual_kv)
        ik_ka = (
            abs(ia) * bus_base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current (use positive sequence impedance for kappa)
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Steady-state and breaking current: determine near vs far generator first (IEC 60909-0 Clause 4.5)
        is_near = self.is_near_generator(abs(ia), self.irg_pu)
        if is_near:
            mu = self._calculate_mu(abs(I1), t_min)
            ib = mu * ik_ka
            lambda_factor = self._calculate_lambda(
                abs(ia), self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * bus_base_i / 1000.0)
        else:
            # Far from generator: negligible AC decay per IEC 60909-0 Clause 4.5 (Ib = Ik'', lambda = 1.0)
            mu = 1.0
            ib = ik_ka
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k, m_factor=kwargs.get("m_factor"), is_near=is_near, ik_steady=Ik_steady
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch and generator contributions
        apply_kt = kwargs.get("apply_kt", True)
        apply_kg = kwargs.get("apply_kg", True)
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ia, branches=branch_list, c_factor=c_factor, apply_kt=apply_kt
        )
        generator_contribs = self.calculate_generator_contributions(
            bus_index, c_factor=c_factor, apply_kg=apply_kg
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
            generator_contributions=generator_contribs,
        )

    def calculate_line_to_line_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float | None = None,
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
        bus_kv (float): Nominal voltage at bus (kV). If None, looked up from base_kv map.
        maximum (bool): Maximum or minimum.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        actual_kv = self.get_bus_base_kv(bus_index, bus_kv)
        if c_factor is None:
            c_factor = self._get_voltage_factor(actual_kv, maximum)

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
        bus_base_i = self.get_bus_base_i(bus_index, actual_kv)
        ik_ka = (
            ik_pu * bus_base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Steady-state and breaking current: determine near vs far generator first (IEC 60909-0 Clause 4.5)
        is_near = self.is_near_generator(ik_pu, self.irg_pu)
        if is_near:
            mu = self._calculate_mu(abs(I1), t_min)
            ib = mu * ik_ka
            lambda_factor = self._calculate_lambda(
                ik_pu, self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * bus_base_i / 1000.0)
        else:
            # Far from generator: negligible AC decay per IEC 60909-0 Clause 4.5 (Ib = Ik'', lambda = 1.0)
            mu = 1.0
            ib = ik_ka
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k, m_factor=kwargs.get("m_factor"), is_near=is_near, ik_steady=Ik_steady
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch and generator contributions
        apply_kt = kwargs.get("apply_kt", True)
        apply_kg = kwargs.get("apply_kg", True)
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, ib_phase, branches=branch_list, c_factor=c_factor, apply_kt=apply_kt
        )
        generator_contribs = self.calculate_generator_contributions(
            bus_index, c_factor=c_factor, apply_kg=apply_kg
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
            generator_contributions=generator_contribs,
        )

    def calculate_double_line_to_ground_fault(
        self,
        bus_index: int,
        c_factor: float | None = None,
        bus_kv: float | None = None,
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
        bus_kv (float): Nominal voltage at bus (kV). If None, looked up from base_kv map.
        maximum (bool): Maximum or minimum.
        t_min (float): Minimum delay time.
        t_k (float): Short-circuit duration.

        Returns:
        ShortCircuitResult
        """
        actual_kv = self.get_bus_base_kv(bus_index, bus_kv)
        if c_factor is None:
            c_factor = self._get_voltage_factor(actual_kv, maximum)

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

        # Use the larger of Ib and Ic for magnitude using bus base current
        bus_base_i = self.get_bus_base_i(bus_index, actual_kv)
        ik_ka = (
            max(abs(ib_phase), abs(ic_phase)) * bus_base_i / 1000.0
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Peak current
        kappa = self._calculate_kappa(bus_index)
        ip = np.sqrt(2) * kappa * ik_ka

        # Steady-state and breaking current: determine near vs far generator first (IEC 60909-0 Clause 4.5)
        ik_max_pu = max(abs(ib_phase), abs(ic_phase))
        is_near = self.is_near_generator(ik_max_pu, self.irg_pu)
        if is_near:
            mu = self._calculate_mu(abs(I1), t_min)
            ib = mu * ik_ka
            lambda_factor = self._calculate_lambda(
                ik_max_pu, self.irg_pu, generator_type=self.generator_type, maximum=maximum
            )
            Ik_steady = lambda_factor * (self.irg_pu * bus_base_i / 1000.0)
        else:
            # Far from generator: negligible AC decay per IEC 60909-0 Clause 4.5 (Ib = Ik'', lambda = 1.0)
            mu = 1.0
            ib = ik_ka
            lambda_factor = 1.0
            Ik_steady = ik_ka

        # Thermal
        ith = self._calculate_thermal_factor(
            ik_ka, ip, t_k, m_factor=kwargs.get("m_factor"), is_near=is_near, ik_steady=Ik_steady
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Branch and generator contributions
        apply_kt = kwargs.get("apply_kt", True)
        apply_kg = kwargs.get("apply_kg", True)
        branch_list = kwargs.get("branches", self.branches)
        branch_contribs = self.calculate_branch_contributions(
            bus_index, max(ib_phase, ic_phase, key=abs), branches=branch_list, c_factor=c_factor, apply_kt=apply_kt
        )
        generator_contribs = self.calculate_generator_contributions(
            bus_index, c_factor=c_factor, apply_kg=apply_kg
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
            generator_contributions=generator_contribs,
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
