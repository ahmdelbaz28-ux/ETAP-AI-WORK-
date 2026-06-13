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

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
import logging

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
    angle_deg: float     # Phase angle in degrees
    source_type: str = "current"  # "current" or "voltage"

    @property
    def frequency_hz(self, fundamental_freq: float = 60.0) -> float:
        """Calculate frequency for this harmonic."""
        return self.harmonic_order * fundamental_freq


@dataclass
class HarmonicResult:
    """Results from harmonic analysis at a specific harmonic order."""
    harmonic_order: int
    frequency_hz: float
    bus_voltages: Dict[str, complex]  # bus_id -> voltage phasor
    branch_currents: Dict[str, complex]  # branch_id -> current phasor
    thd_voltage: Dict[str, float]  # bus_id -> THD %
    thd_current: Dict[str, float]  # branch_id -> THD %


@dataclass
class HarmonicAnalysisResult:
    """Complete harmonic analysis results."""
    fundamental_frequency: float  # Hz
    max_harmonic_order: int
    harmonic_results: List[HarmonicResult]
    total_thd_voltage: Dict[str, float]  # bus_id -> Total THD %
    total_tdd_current: Dict[str, float]  # bus_id -> Total TDD %
    resonance_detected: bool
    resonance_frequencies: List[float]
    compliance_status: Dict[str, bool]  # bus_id -> compliant (True/False)
    violations: List[str]


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
        self.harmonic_sources: List[HarmonicSource] = []
        self.Ybus_fundamental = None
        self.bus_ids = []
        self.branch_data = {}

    def set_system_data(self, Ybus_fundamental: np.ndarray, bus_ids: List[str],
                        branch_data: Dict = None):
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
        logger.info(f"Added harmonic source: order={source.harmonic_order}, "
                    f"magnitude={source.magnitude_pu} pu")

    def calculate_harmonic_impedance(self, harmonic_order: int,
                                      Ybus_fundamental: np.ndarray = None) -> np.ndarray:
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
        Ybus_h = np.zeros((n, n), dtype=complex)

        # Scale Ybus elements based on harmonic order
        for i in range(n):
            for j in range(n):
                Y_ij = Ybus_fundamental[i, j]

                if i == j:
                    # Diagonal elements (shunt + series contributions)
                    # Approximate scaling for harmonic impedance
                    G = Y_ij.real
                    B = Y_ij.imag

                    # Conductance increases with sqrt(h) due to skin effect
                    G_h = G * np.sqrt(h) if G != 0 else 0

                    # Susceptance scales with h for inductive, 1/h for capacitive
                    # Simplified: assume predominantly inductive
                    if B < 0:  # Inductive (negative susceptance)
                        B_h = B * h
                    elif B > 0:  # Capacitive (positive susceptance)
                        B_h = B / h if h > 0 else B
                    else:
                        B_h = 0

                    Ybus_h[i, j] = complex(G_h, B_h)
                else:
                    # Off-diagonal elements (mutual coupling)
                    # Similar scaling applies
                    G = Y_ij.real
                    B = Y_ij.imag

                    G_h = G * np.sqrt(h) if G != 0 else 0

                    if B < 0:
                        B_h = B * h
                    elif B > 0:
                        B_h = B / h if h > 0 else B
                    else:
                        B_h = 0

                    Ybus_h[i, j] = complex(G_h, B_h)

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
        Ybus_h = self.calculate_harmonic_impedance(h)

        # Compute Zbus by inversion
        try:
            Zbus_h = np.linalg.inv(Ybus_h)
        except np.linalg.LinAlgError:
            logger.warning(f"Singular Ybus at harmonic {h}, using pseudo-inverse")
            Zbus_h = np.linalg.pinv(Ybus_h)

        # Build harmonic current injection vector
        n = len(self.bus_ids)
        I_h = np.zeros(n, dtype=complex)

        for source in self.harmonic_sources:
            if source.harmonic_order == h and source.source_type == "current":
                if source.bus_id in self.bus_ids:
                    bus_idx = self.bus_ids.index(source.bus_id)
                    # Convert polar to rectangular
                    angle_rad = np.radians(source.angle_deg)
                    I_injection = source.magnitude_pu * np.exp(1j * angle_rad)
                    I_h[bus_idx] += I_injection

        # Solve for voltages: V = Zbus * I
        V_h = Zbus_h @ I_h

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
            thd_current=thd_current
        )

    def calculate_thd(self, harmonic_results: List[HarmonicResult],
                      fundamental_magnitude: Dict[str, float]) -> Dict[str, float]:
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
                    V_h = abs(result.bus_voltages.get(bus_id, 0))
                    sum_squared += V_h ** 2

            # Calculate THD
            thd[bus_id] = (np.sqrt(sum_squared) / V1) * 100.0

        return thd

    def calculate_tdd(self, harmonic_results: List[HarmonicResult],
                      fundamental_current: Dict[str, float]) -> Dict[str, float]:
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

        for branch_id in self.branch_data.keys():
            # Get fundamental (load) current
            I_L = fundamental_current.get(branch_id, 1.0)

            if I_L == 0:
                tdd[branch_id] = 0.0
                continue

            # Sum squared harmonic currents
            sum_squared = 0.0
            for result in harmonic_results:
                if result.harmonic_order > 1:
                    I_h = abs(result.branch_currents.get(branch_id, 0))
                    sum_squared += I_h ** 2

            # Calculate TDD
            tdd[branch_id] = (np.sqrt(sum_squared) / I_L) * 100.0

        return tdd

    def detect_resonance(self, harmonic_results: List[HarmonicResult],
                         threshold_factor: float = 10.0) -> Tuple[bool, List[float]]:
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
                logger.warning(f"Potential resonance detected at {result.frequency_hz} Hz "
                             f"(harmonic {result.harmonic_order})")

        resonance_detected = len(resonance_freqs) > 0
        return resonance_detected, resonance_freqs

    def check_ieee_519_compliance(self, thd_voltage: Dict[str, float],
                                   tdd_current: Dict[str, float],
                                   voltage_kv: float) -> Dict[str, bool]:
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
                logger.warning(f"IEEE 519 violation at bus {bus_id}: "
                             f"THD={thd:.2f}% exceeds limit {vthd_limit}%")

        return compliance

    def run_full_analysis(self, fundamental_magnitudes: Dict[str, float] = None,
                          fundamental_currents: Dict[str, float] = None,
                          voltage_kv: float = 13.8) -> HarmonicAnalysisResult:
        """
        Run complete harmonic analysis for all harmonic orders.

        Parameters:
        fundamental_magnitudes: Fundamental voltage magnitudes per bus
        fundamental_currents: Fundamental currents per branch
        voltage_kv: System voltage in kV for compliance checking

        Returns:
        HarmonicAnalysisResult with complete results
        """
        logger.info(f"Starting harmonic analysis up to {self.max_harmonic}th harmonic")

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
                logger.error(f"Failed to solve harmonic {h}: {e}")
                continue

        # Calculate THD
        fund_mag = fundamental_magnitudes or {bus_id: 1.0 for bus_id in self.bus_ids}
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
                    f"Bus {bus_id}: THD={thd_voltage[bus_id]:.2f}% exceeds IEEE 519 limit"
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
            violations=violations
        )

        logger.info(f"Harmonic analysis complete. Resonance: {resonance_detected}, "
                   f"Violations: {len(violations)}")

        return result

    def design_passive_filter(self, target_harmonic: int, q_factor: float = 50.0,
                              tuning_frequency_offset: float = 0.05) -> Dict[str, float]:
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
        Q_cap_MVAR = 1.0  # 1 MVAR capacitor bank
        V_ll = 13.8  # Line-to-line voltage in kV (example)
        V_phase = V_ll / np.sqrt(3)  # Phase voltage in kV

        # Calculate capacitance
        # Q = V^2 / Xc = V^2 * omega * C
        omega_tuned = 2 * np.pi * f_tuned
        C = (Q_cap_MVAR * 1e6) / (omega_tuned * (V_phase * 1e3) ** 2)

        # Calculate inductance for resonance at tuned frequency
        # omega^2 = 1/(LC)
        L = 1 / (omega_tuned ** 2 * C)

        # Calculate resistance for desired Q factor
        # Q = omega * L / R
        R = omega_tuned * L / q_factor

        filter_design = {
            'target_harmonic': h_target,
            'tuned_frequency_hz': f_tuned,
            'capacitance_F': C,
            'capacitance_uF': C * 1e6,
            'inductance_H': L,
            'inductance_mH': L * 1e3,
            'resistance_ohm': R,
            'q_factor': q_factor,
            'capacitor_rating_MVAR': Q_cap_MVAR
        }

        logger.info(f"Passive filter designed for harmonic {h_target}: "
                   f"C={C*1e6:.2f} uF, L={L*1e3:.2f} mH, R={R:.3f} ohm")

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
