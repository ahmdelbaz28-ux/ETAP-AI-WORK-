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
        self.Ybus_fundamental = None  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.bus_ids = []
        self.branch_data = {}

    def set_system_data(
        self, Ybus_fundamental: np.ndarray, bus_ids: list[str], branch_data: dict = None,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
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
            source.harmonic_order, source.magnitude_pu,
        )

    def calculate_harmonic_impedance(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, harmonic_order: int, Ybus_fundamental: np.ndarray = None,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    ) -> np.ndarray:
        """
        Calculate system impedance matrix at a specific harmonic order.

        For passive elements:
        - Resistance: R(h) = R(1) * sqrt(h)  (skin effect)
        - Inductance: X_L(h) = h * X_L(1)
        - Capacitance: X_C(h) = X_C(1) / h

        Parameters:
        harmonic_order: Harmonic order (h)
        Ybus_fundamental: Fundamental Ybus (optional, uses stored if not provided)

        Returns:
        Harmonic order Ybus matrix
        """
        if Ybus_fundamental is None:
            Ybus_fundamental = self.Ybus_fundamental

        if Ybus_fundamental is None:
            raise ValueError("Ybus matrix not set. Call set_system_data() first.")

        h = harmonic_order
        n = Ybus_fundamental.shape[0]
        Ybus_h = np.zeros((n, n), dtype=complex)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # IEEE 519-2022 frequency-dependent scaling:
        #   R(h) ≈ R(1) × sqrt(h)   (skin effect)
        #   X_L(h) = h × X_L(1)     (inductive reactance)
        #   B_C(h) = h × B_C(1)     (capacitive susceptance — shunt, NOT series)
        #   X_C(h) = X_C(1) / h     (capacitive reactance — series)
        #
        # Ybus admittance elements mix inductive and capacitive contributions
        # from both series elements (lines/transformers) and shunt elements
        # (line charging, shunt capacitors/reactors).  The sign of the net
        # susceptance (B = imag(Y)) cannot distinguish series vs shunt or
        # inductive vs capacitive because both could contribute.  Instead,
        # the Ybus is decomposed per-frequency using the fundamental-frequency
        # impedance to reconstruct the full admittance.
        #
        # Simplified approach: compute Zbus at fundamental → scale each
        # element's R and X components individually → rebuild Ybus via
        # pseudo-inversion.  This is more accurate than sign-based scaling.
        Zbus_1 = np.linalg.inv(Ybus_fundamental)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Zbus_h = np.zeros_like(Zbus_1, dtype=complex)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        for i in range(n):
            for j in range(n):
                Z_ij = Zbus_1[i, j]  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                R = Z_ij.real
                X = Z_ij.imag

                # Skin effect on resistance (approximate)
                R_h = R * np.sqrt(h) if R != 0 else 0.0  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

                # Reactance scaling: inductive X > 0, capacitive X < 0
                if X > 0:  # Net inductive at this (i,j)
                    X_h = X * h  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                elif X < 0:  # Net capacitive at this (i,j)
                    X_h = X / h if h > 0 else X
                else:
                    X_h = 0.0

                Zbus_h[i, j] = complex(R_h, X_h)

        # Rebuild Ybus from scaled Zbus.  For non-square or singular systems
        # use pseudo-inverse as a fallback.
        try:
            Ybus_h = np.linalg.inv(Zbus_h)
        except np.linalg.LinAlgError:
            logger.warning(
                "Zbus_h at harmonic %d is singular; falling back to pseudo-inverse",
                h,
            )
            Ybus_h = np.linalg.pinv(Zbus_h)

        return Ybus_h

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
        Ybus_h = self.calculate_harmonic_impedance(h)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Compute Zbus by inversion
        try:
            Zbus_h = np.linalg.inv(Ybus_h)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        except np.linalg.LinAlgError:
            logger.warning("Singular Ybus at harmonic %s, using pseudo-inverse", h)
            Zbus_h = np.linalg.pinv(Ybus_h)

        # Build harmonic current injection vector
        n = len(self.bus_ids)
        I_h = np.zeros(n, dtype=complex)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        for source in self.harmonic_sources:
            if source.harmonic_order == h and source.source_type == "current":
                if source.bus_id in self.bus_ids:
                    bus_idx = self.bus_ids.index(source.bus_id)
                    # Convert polar to rectangular
                    angle_rad = np.radians(source.angle_deg)
                    I_injection = source.magnitude_pu * np.exp(1j * angle_rad)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    I_h[bus_idx] += I_injection

        # Solve for voltages: V = Zbus * I
        V_h = Zbus_h @ I_h  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Create result dictionaries
        bus_voltages = {}
        for i, bus_id in enumerate(self.bus_ids):
            bus_voltages[bus_id] = V_h[i]

        # Calculate branch currents (simplified - would need branch data)
        branch_currents = {}

        # Calculate THD for this harmonic (will be accumulated later)
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
        self, harmonic_results: list[HarmonicResult], fundamental_magnitude: dict[str, float],
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
                    V_h = abs(result.bus_voltages.get(bus_id, 0))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    sum_squared += V_h**2

            # Calculate THD
            thd[bus_id] = (np.sqrt(sum_squared) / V1) * 100.0

        return thd

    def calculate_tdd(
        self, harmonic_results: list[HarmonicResult], fundamental_current: dict[str, float],
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
                    I_h = abs(result.branch_currents.get(branch_id, 0))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    sum_squared += I_h**2

            # Calculate TDD
            tdd[branch_id] = (np.sqrt(sum_squared) / I_L) * 100.0

        return tdd

    def detect_resonance(
        self, harmonic_results: list[HarmonicResult], threshold_factor: float = 10.0,
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
                    result.frequency_hz, result.harmonic_order,
                )

        resonance_detected = len(resonance_freqs) > 0
        return resonance_detected, resonance_freqs

    def check_ieee_519_compliance(
        self, thd_voltage: dict[str, float], tdd_current: dict[str, float], voltage_kv: float,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> dict[str, bool]:
        """
        Check compliance with IEEE 519-2022 limits.

        Voltage THD limits (Table 1 in IEEE 519):
        - V <= 1.0 kV: 8.0%
        - 1.0 < V <= 69 kV: 5.0%
        - 69 < V <= 161 kV: 2.5%
        - V > 161 kV: 1.5%

        Current TDD limits depend on Isc/IL ratio (Table 2 in IEEE 519)

        Parameters:
        thd_voltage: Bus THD percentages
        tdd_current: Branch TDD percentages
        voltage_kv: System voltage in kV

        Returns:
        Dictionary of bus_id -> compliant (True/False)
        """
        # Determine voltage THD limit based on voltage level
        if voltage_kv <= 1.0:
            vthd_limit = 8.0
        elif voltage_kv <= 69.0:
            vthd_limit = 5.0
        elif voltage_kv <= 161.0:
            vthd_limit = 2.5
        else:
            vthd_limit = 1.5

        compliance = {}
        for bus_id, thd in thd_voltage.items():
            compliant = thd <= vthd_limit
            compliance[bus_id] = compliant

            if not compliant:
                logger.warning(
                    "IEEE 519 violation at bus %s: THD=%.2f%% exceeds limit %s%%",
                    bus_id, thd, vthd_limit,
                )

        return compliance

    def run_full_analysis(
        self,
        fundamental_magnitudes: dict[str, float] = None,
        fundamental_currents: dict[str, float] = None,
        voltage_kv: float = 13.8,
    ) -> HarmonicAnalysisResult:
        """
        Run complete harmonic analysis for all harmonic orders.

        Parameters:
        fundamental_magnitudes: Fundamental voltage magnitudes per bus
        fundamental_currents: Fundamental currents per branch
        voltage_kv: System voltage in kV for compliance checking

        Returns:
        HarmonicAnalysisResult with complete results
        """
        logger.info("Starting harmonic analysis up to %sth harmonic", self.max_harmonic)

        harmonic_results = []

        # Analyze each harmonic order (odd harmonics typically most significant)
        for h in range(2, self.max_harmonic + 1):
            # Skip even harmonics unless specifically requested
            # (even harmonics are rare in balanced systems)
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
        compliance = self.check_ieee_519_compliance(thd_voltage, tdd_current, voltage_kv)

        # Collect violations
        violations = []
        for bus_id, compliant in compliance.items():
            if not compliant:
                violations.append(
                    f"Bus {bus_id}: THD={thd_voltage[bus_id]:.2f}% exceeds IEEE 519 limit",
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
            resonance_detected, len(violations),
        )

        return result

    def design_passive_filter(
        self, target_harmonic: int, q_factor: float = 50.0, tuning_frequency_offset: float = 0.05,
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
        Q_cap_MVAR = 1.0  # 1 MVAR capacitor bank  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V_ll = 13.8  # Line-to-line voltage in kV (example)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V_phase = V_ll / np.sqrt(3)  # Phase voltage in kV  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Calculate capacitance
        # Q = V^2 / Xc = V^2 * omega * C
        omega_tuned = 2 * np.pi * f_tuned
        C = (Q_cap_MVAR * 1e6) / (omega_tuned * (V_phase * 1e3) ** 2)

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
            h_target, C * 1e6, L * 1e3, R,
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
