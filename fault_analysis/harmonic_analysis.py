"""
Harmonic Analysis Engine
=========================
Implements harmonic power flow analysis per IEEE 519-2022.

Supports:
- Harmonic impedance calculation
- Total Harmonic Distortion (THD) analysis
- Total Demand Distortion (TDD) calculation
- Frequency scan analysis
- Harmonic filter design
- Resonance detection
- Individual harmonic limits checking

Reference: IEEE 519-2022 "IEEE Standard for Harmonic Control in Electric Power Systems"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class HarmonicStandard(Enum):
    """Harmonic standards for limit checking."""

    IEEE_519_2022 = "IEEE 519-2022"
    IEC_61000 = "IEC 61000"
    EN_50160 = "EN 50160"


@dataclass
class HarmonicSource:
    """Represents a harmonic current/voltage source."""

    source_id: str
    bus_id: str
    harmonic_order: int
    magnitude_pu: float  # Per-unit magnitude
    angle_deg: float  # Phase angle in degrees
    source_type: str = "current"  # "current" or "voltage"
    fundamental_freq: float = 60.0  # System fundamental frequency (Hz)

    @property
    def frequency_hz(self) -> float:
        """Calculate frequency for this harmonic."""
        return self.harmonic_order * self.fundamental_freq


@dataclass
class HarmonicResult:
    """Results from harmonic analysis at a specific harmonic order."""

    harmonic_order: int
    frequency_hz: float
    bus_voltages: dict[str, complex]  # bus_id -> voltage phasor
    branch_currents: dict[str, complex]  # branch_id -> current phasor
    thd_voltage: dict[str, float]  # bus_id -> THD %
    thd_current: dict[str, float]  # branch_id -> THD %


@dataclass
class HarmonicAnalysisResult:
    """Complete harmonic analysis results."""

    fundamental_frequency: float  # Hz
    max_harmonic_order: int
    harmonic_results: list[HarmonicResult]
    total_thd_voltage: dict[str, float]  # bus_id -> Total THD %
    total_tdd_current: dict[str, float]  # bus_id -> Total TDD %
    resonance_detected: bool
    resonance_frequencies: list[float]
    compliance_status: dict[str, bool]  # bus_id -> compliant (True/False)
    violations: list[str]


class HarmonicAnalysisEngine:
    """
    Harmonic Analysis Engine implementing IEEE 519 methodology.

    Performs frequency-domain harmonic power flow analysis using
    superposition principle for each harmonic order.
    """

    def __init__(self, fundamental_freq: float = 60.0, max_harmonic: int = 50):
        """
        Initialize harmonic analysis engine.

        Parameters:
        fundamental_freq: Fundamental frequency in Hz (default 60 Hz)
        max_harmonic: Maximum harmonic order to analyze (default 50th)
        """
        self.fundamental_freq = fundamental_freq
        self.max_harmonic = max_harmonic
        self.harmonic_sources: list[HarmonicSource] = []
        self.Ybus_fundamental = None  # NOSONAR standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.bus_ids = []
        self.branch_data = {}

    def set_system_data(
        self,
        Ybus_fundamental: np.ndarray,
        bus_ids: list[str],
        branch_data: dict = None,  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    ):
        """
        Set system admittance matrix and topology.

        Parameters:
        Ybus_fundamental: Fundamental frequency Ybus matrix
        bus_ids: List of bus IDs
        branch_data: Optional branch impedance data
        """
        self.Ybus_fundamental = Ybus_fundamental
        self.bus_ids = bus_ids
        self.branch_data = branch_data or {}

    def add_harmonic_source(self, source: HarmonicSource):
        """Add a harmonic current/voltage source."""
        self.harmonic_sources.append(source)
        logger.info(
            "Added harmonic source: order=%d, magnitude=%s pu",
            source.harmonic_order,
            source.magnitude_pu,
        )

    def set_system(self, system: Any) -> None:
        """
        Configure engine directly from a System object.

        Parameters:
        system: System instance containing buses, lines, transformers, and generators.
        """
        self.Ybus_fundamental = system.get_ybus(seq="1")
        self.bus_ids = [str(bid) for bid in sorted(system.buses.keys())]
        self.branch_data = {}
        if hasattr(system, "lines"):
            for line in system.lines:
                b_name = f"line_{line.line_id}"
                self.branch_data[b_name] = {
                    "from_bus": str(line.from_bus.bus_id),
                    "to_bus": str(line.to_bus.bus_id),
                    "r": float(line.z1.real),
                    "x": float(line.z1.imag),
                    "b": float(line.yshunt1.imag) if hasattr(line, "yshunt1") else 0.0,
                }
        if hasattr(system, "transformers"):
            for tx in system.transformers:
                b_name = f"xfmr_{tx.transformer_id}"
                self.branch_data[b_name] = {
                    "from_bus": str(tx.from_bus.bus_id),
                    "to_bus": str(tx.to_bus.bus_id),
                    "r": float(tx.z1.real),
                    "x": float(tx.z1.imag),
                    "b": 0.0,
                }

    def calculate_harmonic_impedance(
        self,
        harmonic_order: int,
        ybus_fundamental: np.ndarray = None,
    ) -> np.ndarray:
        """
        Calculate system admittance matrix at a specific harmonic order per IEEE 519-2022.

        Directly reconstructs frequency-dependent network parameters:
        - Series resistance scales with skin effect: R(h) = R(1) * sqrt(h)
        - Series inductance scales with frequency: X_L(h) = h * X_L(1)
        - Shunt capacitive susceptance scales with frequency: B_C(h) = h * B_C(1)
        - Shunt inductive susceptance: B_L(h) = B_L(1) / h

        Parameters:
        harmonic_order: Harmonic order (h)
        ybus_fundamental: Fundamental Ybus (optional, uses stored if not provided)

        Returns:
        Harmonic order Ybus matrix
        """
        if ybus_fundamental is None:
            ybus_fundamental = self.Ybus_fundamental

        if ybus_fundamental is None:
            raise ValueError("Ybus matrix not set. Call set_system_data() first.")

        h = float(harmonic_order)
        if h <= 0:
            raise ValueError("Harmonic order must be positive")

        n = ybus_fundamental.shape[0]
        ybus_h = np.zeros((n, n), dtype=complex)

        # 1. If explicit branch data is provided, assemble Ybus(h) directly from branches
        if self.branch_data and len(self.branch_data) > 0 and self.bus_ids:
            bus_idx_map = {str(bid): idx for idx, bid in enumerate(self.bus_ids)}
            shunt_admittance = np.zeros(n, dtype=complex)

            for i in range(n):
                row_offdiag_sum = sum(
                    abs(ybus_fundamental[i, j]) for j in range(n) if j != i
                )
                if row_offdiag_sum > 0:
                    y_shunt_fund = ybus_fundamental[i, i] + sum(
                        ybus_fundamental[i, j] for j in range(n) if j != i
                    )
                    g_sh = y_shunt_fund.real
                    b_sh = y_shunt_fund.imag
                    b_sh_h = b_sh * h if b_sh > 0 else (b_sh / h if b_sh < 0 else 0.0)
                    shunt_admittance[i] = complex(g_sh, b_sh_h)

            for branch_id, b_info in self.branch_data.items():
                u_str = str(b_info.get("from_bus"))
                v_str = str(b_info.get("to_bus"))
                if u_str in bus_idx_map and v_str in bus_idx_map:
                    u = bus_idx_map[u_str]
                    v = bus_idx_map[v_str]
                    r1 = float(b_info.get("r", b_info.get("r1", 0.0)))
                    x1 = float(b_info.get("x", b_info.get("x1", 0.0)))
                    b_sh = float(b_info.get("b", b_info.get("b1", b_info.get("yshunt1", 0.0))))

                    r_h = r1 * np.sqrt(h)
                    x_h = x1 * h
                    z_h = complex(r_h, x_h)
                    y_ser = 1.0 / z_h if abs(z_h) > 1e-12 else 0.0

                    y_cap_half = complex(0.0, 0.5 * h * b_sh)

                    ybus_h[u, v] -= y_ser
                    ybus_h[v, u] -= y_ser
                    ybus_h[u, u] += y_ser + y_cap_half
                    ybus_h[v, v] += y_ser + y_cap_half

            for i in range(n):
                ybus_h[i, i] += shunt_admittance[i]

            return ybus_h

        # 2. Physics-based branch decomposition from fundamental Ybus matrix
        offdiag_y_h = np.zeros((n, n), dtype=complex)
        for i in range(n):
            for j in range(i + 1, n):
                y_fund = -ybus_fundamental[i, j]
                if abs(y_fund) > 1e-12:
                    z_fund = 1.0 / y_fund
                    r1 = max(float(z_fund.real), 0.0)
                    x1 = float(z_fund.imag)
                    r_h = r1 * np.sqrt(h)
                    x_h = x1 * h
                    z_h = complex(r_h, x_h)
                    y_h = 1.0 / z_h if abs(z_h) > 1e-12 else 0.0
                    offdiag_y_h[i, j] = y_h
                    offdiag_y_h[j, i] = y_h

        if not self.branch_data and self.bus_ids and len(self.bus_ids) == n:
            for i in range(n):
                for j in range(i + 1, n):
                    if abs(ybus_fundamental[i, j]) > 1e-12:
                        b_name = f"{self.bus_ids[i]}-{self.bus_ids[j]}"
                        z_fund = -1.0 / ybus_fundamental[i, j]
                        self.branch_data[b_name] = {
                            "from_bus": self.bus_ids[i],
                            "to_bus": self.bus_ids[j],
                            "r": max(float(z_fund.real), 0.0),
                            "x": float(z_fund.imag),
                            "b": 0.0,
                        }

        for i in range(n):
            sum_y_connected_1 = sum(-ybus_fundamental[i, j] for j in range(n) if j != i)
            y_shunt_1 = ybus_fundamental[i, i] - sum_y_connected_1
            g_shunt = y_shunt_1.real
            b_shunt = y_shunt_1.imag

            if b_shunt > 0:
                b_shunt_h = b_shunt * h
            elif b_shunt < 0:
                b_shunt_h = b_shunt / h
            else:
                b_shunt_h = 0.0

            y_shunt_h = complex(g_shunt, b_shunt_h)

            sum_connected_h = 0.0
            for j in range(n):
                if i != j:
                    y_branch_h = offdiag_y_h[i, j]
                    ybus_h[i, j] = -y_branch_h
                    sum_connected_h += y_branch_h

            ybus_h[i, i] = sum_connected_h + y_shunt_h

        return ybus_h

    def solve_harmonic_power_flow(self, harmonic_order: int) -> HarmonicResult:
        """
        Solve harmonic power flow for a specific harmonic order.

        Uses nodal analysis: V(h) = Zbus(h) * I(h)

        Parameters:
        harmonic_order: Harmonic order to solve

        Returns:
        HarmonicResult with voltages and currents
        """
        h = harmonic_order
        freq = h * self.fundamental_freq

        # Build harmonic Ybus
        ybus_h = self.calculate_harmonic_impedance(h)

        # Compute Zbus by inversion with pseudo-inverse fallback
        try:
            zbus_h = np.linalg.inv(ybus_h)
        except np.linalg.LinAlgError:
            logger.warning("Singular Ybus at harmonic %s, using pseudo-inverse", h)
            zbus_h = np.linalg.pinv(ybus_h)

        # Build harmonic current injection vector
        n = len(self.bus_ids)
        i_h = np.zeros(n, dtype=complex)

        for source in self.harmonic_sources:
            if source.harmonic_order == h and source.source_type == "current":
                if source.bus_id in self.bus_ids:
                    bus_idx = self.bus_ids.index(source.bus_id)
                    angle_rad = np.radians(source.angle_deg)
                    i_injection = source.magnitude_pu * np.exp(1j * angle_rad)
                    i_h[bus_idx] += i_injection

        # Solve for voltages: V = Zbus * I
        v_h = zbus_h @ i_h

        # Create result dictionaries
        bus_voltages = {}
        for i, bus_id in enumerate(self.bus_ids):
            bus_voltages[bus_id] = v_h[i]

        # Calculate branch currents per branch
        branch_currents = {}
        for b_name, b_info in self.branch_data.items():
            u_id = b_info.get("from_bus")
            v_id = b_info.get("to_bus")
            if u_id in self.bus_ids and v_id in self.bus_ids:
                u_idx = self.bus_ids.index(u_id)
                v_idx = self.bus_ids.index(v_id)
                r = float(b_info.get("r", 0.0))
                x = float(b_info.get("x", 0.0))
                b = float(b_info.get("b", 0.0))
                z_h = complex(r * np.sqrt(h), x * h)
                y_h = 1.0 / z_h if abs(z_h) > 1e-12 else 0.0
                i_series = (v_h[u_idx] - v_h[v_idx]) * y_h
                i_shunt = v_h[u_idx] * complex(0.0, 0.5 * h * b)
                branch_currents[str(b_name)] = i_series + i_shunt

        thd_voltage = {}
        thd_current = {}

        return HarmonicResult(
            harmonic_order=h,
            frequency_hz=freq,
            bus_voltages=bus_voltages,
            branch_currents=branch_currents,
            thd_voltage=thd_voltage,
            thd_current=thd_current,
        )

    def calculate_thd(
        self,
        harmonic_results: list[HarmonicResult],
        fundamental_magnitude: dict[str, float],
    ) -> dict[str, float]:
        """
        Calculate Total Harmonic Distortion (THD).

        THD = sqrt(sum(V_h^2)) / V_1 * 100%

        Parameters:
        harmonic_results: Results for all harmonic orders
        fundamental_magnitude: Fundamental voltage magnitude per bus

        Returns:
        Dictionary of bus_id -> THD percentage
        """
        thd = {}

        for bus_id in self.bus_ids:
            # Get fundamental magnitude
            V1 = fundamental_magnitude.get(bus_id, 1.0)

            if V1 == 0:
                thd[bus_id] = 0.0
                continue

            # Sum squared harmonic magnitudes
            sum_squared = 0.0
            for result in harmonic_results:
                if result.harmonic_order > 1:  # Exclude fundamental
                    v_h = abs(
                        result.bus_voltages.get(bus_id, 0)
                    )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    sum_squared += v_h**2

            # Calculate THD
            thd[bus_id] = (np.sqrt(sum_squared) / V1) * 100.0

        return thd

    def calculate_tdd(
        self,
        harmonic_results: list[HarmonicResult],
        fundamental_current: dict[str, float],
    ) -> dict[str, float]:
        """
        Calculate Total Demand Distortion (TDD).

        TDD = sqrt(sum(I_h^2)) / I_L * 100%
        where I_L is maximum demand load current

        Parameters:
        harmonic_results: Results for all harmonic orders
        fundamental_current: Fundamental current per branch

        Returns:
        Dictionary of branch_id -> TDD percentage
        """
        tdd = {}

        for branch_id in self.branch_data:
            # Get fundamental (load) current
            I_L = fundamental_current.get(branch_id, 1.0)

            if I_L == 0:
                tdd[branch_id] = 0.0
                continue

            # Sum squared harmonic currents
            sum_squared = 0.0
            for result in harmonic_results:
                if result.harmonic_order > 1:
                    i_h = abs(
                        result.branch_currents.get(branch_id, 0)
                    )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    sum_squared += i_h**2

            # Calculate TDD
            tdd[branch_id] = (np.sqrt(sum_squared) / I_L) * 100.0

        return tdd

    def detect_resonance(
        self,
        harmonic_results: list[HarmonicResult],
        threshold_factor: float = 10.0,
    ) -> tuple[bool, list[float]]:
        """
        Detect potential resonance conditions.

        Resonance is indicated by unusually high voltage/current magnification
        at specific harmonic frequencies.

        Parameters:
        harmonic_results: Results for all harmonic orders
        threshold_factor: Magnification factor indicating resonance (default 10x)

        Returns:
        Tuple of (resonance_detected, resonance_frequencies)
        """
        resonance_freqs = []

        for result in harmonic_results:
            # Check for voltage magnification
            max_voltage = max(abs(v) for v in result.bus_voltages.values())

            # If voltage is significantly higher than typical, flag as resonance
            if max_voltage > threshold_factor:
                resonance_freqs.append(result.frequency_hz)
                logger.warning(
                    "Potential resonance detected at %s Hz (harmonic %d)",
                    result.frequency_hz,
                    result.harmonic_order,
                )

        resonance_detected = len(resonance_freqs) > 0
        return resonance_detected, resonance_freqs

    def check_ieee_519_compliance(
        self,
        thd_voltage: dict[str, float],
        tdd_current: dict[str, float] = None,
        voltage_kv: float = 13.8,
        isc_il_ratio: float = 50.0,
    ) -> dict[str, bool]:
        """
        Check compliance with IEEE 519-2022 limits for both voltage and current.

        Voltage THD limits (Table 1 in IEEE 519-2022):
        - V <= 1.0 kV: 8.0%
        - 1.0 < V <= 69 kV: 5.0%
        - 69 < V <= 161 kV: 2.5%
        - V > 161 kV: 1.5%

        Current TDD limits (Table 2 in IEEE 519-2022, 120V through 69kV):
        - Isc/IL < 20: TDD <= 5.0%
        - 20 <= Isc/IL < 50: TDD <= 8.0%
        - 50 <= Isc/IL < 100: TDD <= 12.0%
        - 100 <= Isc/IL < 1000: TDD <= 15.0%
        - Isc/IL >= 1000: TDD <= 20.0%
        (For 69-161 kV: 50% of values; for >161 kV: 25% of values).

        Parameters:
        thd_voltage: Bus THD percentages
        tdd_current: Branch TDD percentages (optional)
        voltage_kv: System voltage in kV
        isc_il_ratio: Ratio of short-circuit current to maximum demand load current

        Returns:
        Dictionary of element_id -> compliant (True/False)
        """
        # 1. Voltage THD limit per IEEE 519-2022 Table 1
        if voltage_kv <= 1.0:
            vthd_limit = 8.0
        elif voltage_kv <= 69.0:
            vthd_limit = 5.0
        elif voltage_kv <= 161.0:
            vthd_limit = 2.5
        else:
            vthd_limit = 1.5

        # 2. Current TDD limit per IEEE 519-2022 Table 2
        if isc_il_ratio < 20.0:
            itdd_base = 5.0
        elif isc_il_ratio < 50.0:
            itdd_base = 8.0
        elif isc_il_ratio < 100.0:
            itdd_base = 12.0
        elif isc_il_ratio < 1000.0:
            itdd_base = 15.0
        else:
            itdd_base = 20.0

        if voltage_kv <= 69.0:
            itdd_limit = itdd_base
        elif voltage_kv <= 161.0:
            itdd_limit = itdd_base * 0.5
        else:
            itdd_limit = itdd_base * 0.25

        compliance = {}
        for bus_id, thd in thd_voltage.items():
            compliant = thd <= vthd_limit
            compliance[str(bus_id)] = compliant
            if not compliant:
                logger.warning(
                    "IEEE 519 voltage THD violation at bus %s: THD=%.2f%% exceeds limit %.1f%%",
                    bus_id,
                    thd,
                    vthd_limit,
                )

        if tdd_current:
            for branch_id, tdd in tdd_current.items():
                compliant = tdd <= itdd_limit
                compliance[f"branch_{branch_id}"] = compliant
                if not compliant:
                    logger.warning(
                        "IEEE 519 current TDD violation on branch %s: TDD=%.2f%% exceeds limit %.1f%% (Isc/IL=%.1f)",
                        branch_id,
                        tdd,
                        itdd_limit,
                        isc_il_ratio,
                    )

        return compliance

    def run_full_analysis(
        self,
        fundamental_magnitudes: dict[str, float] = None,
        fundamental_currents: dict[str, float] = None,
        voltage_kv: float = 13.8,
        isc_il_ratio: float = 50.0,
    ) -> HarmonicAnalysisResult:
        """
        Run complete harmonic analysis for all harmonic orders.

        Parameters:
        fundamental_magnitudes: Fundamental voltage magnitudes per bus
        fundamental_currents: Fundamental currents per branch
        voltage_kv: System voltage in kV for compliance checking
        isc_il_ratio: Short circuit to load current ratio for IEEE 519 Table 2

        Returns:
        HarmonicAnalysisResult with complete results
        """
        logger.info("Starting harmonic analysis up to %sth harmonic", self.max_harmonic)

        harmonic_results = []

        # Analyze each harmonic order (odd harmonics typically most significant)
        for h in range(2, self.max_harmonic + 1):
            if h % 2 == 0 and h > 2:
                continue

            try:
                result = self.solve_harmonic_power_flow(h)
                harmonic_results.append(result)
            except Exception as e:
                logger.exception("Failed to solve harmonic %s: %s", h, e)
                continue

        # Calculate THD
        fund_mag = fundamental_magnitudes or dict.fromkeys(self.bus_ids, 1.0)
        thd_voltage = self.calculate_thd(harmonic_results, fund_mag)

        # Calculate TDD
        fund_curr = fundamental_currents or {}
        tdd_current = self.calculate_tdd(harmonic_results, fund_curr)

        # Detect resonance
        resonance_detected, resonance_freqs = self.detect_resonance(harmonic_results)

        # Check IEEE 519 compliance
        compliance = self.check_ieee_519_compliance(
            thd_voltage, tdd_current, voltage_kv=voltage_kv, isc_il_ratio=isc_il_ratio
        )

        # Collect violations
        violations = []
        for bus_id, thd in thd_voltage.items():
            if not compliance.get(str(bus_id), True):
                violations.append(
                    f"Bus {bus_id}: Voltage THD={thd:.2f}% exceeds IEEE 519 limit",
                )
        if tdd_current:
            for branch_id, tdd in tdd_current.items():
                if not compliance.get(f"branch_{branch_id}", True):
                    violations.append(
                        f"Branch {branch_id}: Current TDD={tdd:.2f}% exceeds IEEE 519 limit",
                    )

        result = HarmonicAnalysisResult(
            fundamental_frequency=self.fundamental_freq,
            max_harmonic_order=self.max_harmonic,
            harmonic_results=harmonic_results,
            total_thd_voltage=thd_voltage,
            total_tdd_current=tdd_current,
            resonance_detected=resonance_detected,
            resonance_frequencies=resonance_freqs,
            compliance_status=compliance,
            violations=violations,
        )

        logger.info(
            "Harmonic analysis complete. Resonance: %s, Violations: %d",
            resonance_detected,
            len(violations),
        )

        return result

    def design_passive_filter(
        self,
        target_harmonic: int,
        q_factor: float = 50.0,
        tuning_frequency_offset: float = 0.05,
    ) -> dict[str, float]:
        """
        Design a passive harmonic filter (single-tuned).

        Parameters:
        target_harmonic: Harmonic order to filter
        q_factor: Quality factor of the filter
        tuning_frequency_offset: Tuning offset as fraction (default 5% below target)

        Returns:
        Filter component values (R, L, C)
        """
        h_target = target_harmonic
        f_target = h_target * self.fundamental_freq

        # Tune slightly below target to account for component tolerances
        f_tuned = f_target * (1 - tuning_frequency_offset)

        # For a given system impedance, calculate filter components
        # This is simplified - real design requires iterative optimization
        # Assume we want to provide low impedance path at tuned frequency

        # Choose capacitor rating (typical values)
        Q_cap_MVAR = 1.0  # NOSONAR
        V_ll = 13.8  # NOSONAR
        v_phase = V_ll / np.sqrt(3)  # NOSONAR

        # Calculate capacitance
        # Q = V^2 / Xc = V^2 * omega * C
        omega_tuned = 2 * np.pi * f_tuned
        C = (Q_cap_MVAR * 1e6) / (omega_tuned * (v_phase * 1e3) ** 2)

        # Calculate inductance for resonance at tuned frequency
        # omega^2 = 1/(LC)
        L = 1 / (omega_tuned**2 * C)

        # Calculate resistance for desired Q factor
        # Q = omega * L / R
        R = omega_tuned * L / q_factor

        filter_design = {
            "target_harmonic": h_target,
            "tuned_frequency_hz": f_tuned,
            "capacitance_F": C,
            "capacitance_uF": C * 1e6,
            "inductance_H": L,
            "inductance_mH": L * 1e3,
            "resistance_ohm": R,
            "q_factor": q_factor,
            "capacitor_rating_MVAR": Q_cap_MVAR,
        }

        logger.info(
            "Passive filter designed for harmonic %d: C=%.2f uF, L=%.2f mH, R=%.3f ohm",
            h_target,
            C * 1e6,
            L * 1e3,
            R,
        )

        return filter_design

    def generate_report(self, result: HarmonicAnalysisResult) -> str:
        """Generate a text report of harmonic analysis results."""
        lines = []
        lines.append("=" * 70)
        lines.append("HARMONIC ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Fundamental Frequency: {result.fundamental_frequency} Hz")
        lines.append(f"Maximum Harmonic Order: {result.max_harmonic_order}")
        lines.append("")

        lines.append("TOTAL HARMONIC DISTORTION (THD) - VOLTAGE")
        lines.append("-" * 70)
        for bus_id, thd in sorted(result.total_thd_voltage.items()):
            status = "✓ PASS" if result.compliance_status.get(bus_id, False) else "✗ FAIL"
            lines.append(f"  Bus {bus_id:10s}: THD = {thd:6.2f}%  {status}")
        lines.append("")

        lines.append("TOTAL DEMAND DISTORTION (TDD) - CURRENT")
        lines.append("-" * 70)
        for branch_id, tdd in sorted(result.total_tdd_current.items()):
            lines.append(f"  Branch {branch_id:10s}: TDD = {tdd:6.2f}%")
        lines.append("")

        if result.resonance_detected:
            lines.append("⚠ WARNING: RESONANCE DETECTED")
            lines.append("-" * 70)
            for freq in result.resonance_frequencies:
                lines.append(f"  Resonance frequency: {freq:.1f} Hz")
            lines.append("")

        if result.violations:
            lines.append("❌ IEEE 519 COMPLIANCE VIOLATIONS")
            lines.append("-" * 70)
            for violation in result.violations:
                lines.append(f"  {violation}")
            lines.append("")
        else:
            lines.append("✓ All buses comply with IEEE 519-2022 limits")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)
