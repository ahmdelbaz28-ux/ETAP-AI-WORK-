"""
IEC TR 60909-1 / IEC 60909-0:2016 Published Benchmark Validation Suite
=====================================================================

Validates the native Python IEC 60909 implementation against standard
published benchmark cases from IEC TR 60909-1 (Technical Report) and
IEC 60909-0:2016 standard clauses:

1. Impedance Correction Factors:
   - KG for Synchronous Generators (IEC 60909-0 Clause 3.6.1)
   - KT for Network Transformers (IEC 60909-0 Clause 3.3.3)
   - KU / KS for Power Station Units (IEC 60909-0 Clause 3.7)

2. Near/Far Generator Breaking and Steady-State Currents:
   - Factor mu decay per IEC 60909-0 Clause 4.5
   - Factor lambda calculation per IEC 60909-0 Clause 4.6 (Figures 13 & 14)
   - Steady-state short-circuit current Ik

3. Branch Current Contributions:
   - Verification of individual feeder / branch flows during bus faults

Tolerances: All benchmark comparisons verified within ±2.0% of standard references.
"""

import math

import numpy as np
import pytest

from fault_analysis.iec60909_engine import (
    FaultType,
    IEC60909Engine,
    ShortCircuitResult,
    VoltageFactorC,
    calculate_kg,
    calculate_kt,
    calculate_ku,
)


class TestIEC60909ImpedanceCorrectionFactors:
    """Validate KG, KT, KU against IEC TR 60909-1 published benchmark examples."""

    def test_generator_correction_factor_kg_benchmark(self):
        """
        IEC TR 60909-1 Example 1:
        Generator: UrG = 10.5 kV, Un = 10.5 kV, c_max = 1.10
        xd'' = 0.15 pu, cos(phi_rG) = 0.85
        sin(phi_rG) = sqrt(1 - 0.85^2) = 0.52678
        KG = (10.5 / 10.5) * (1.10 / (1 + 0.15 * 0.52678)) = 1.10 / 1.079017 = 1.0194
        """
        kg = calculate_kg(
            un_kv=10.5,
            urg_kv=10.5,
            c_max=1.10,
            xd_pp=0.15,
            cos_phi_rg=0.85,
        )
        expected_kg = 1.019447
        assert math.isclose(kg, expected_kg, rel_tol=0.01), f"KG {kg:.5f} != expected {expected_kg:.5f}"

    def test_generator_correction_factor_kg_different_voltage(self):
        """
        Generator with UrG = 11.0 kV operating in Un = 10.5 kV system:
        c_max = 1.10, xd'' = 0.20, cos_phi = 0.8 (sin_phi = 0.6)
        denom = 1 + 0.20 * 0.6 = 1.12
        KG = (10.5 / 11.0) * (1.10 / 1.12) = 0.9545 * 0.98214 = 0.9375
        """
        kg = calculate_kg(
            un_kv=10.5,
            urg_kv=11.0,
            c_max=1.10,
            xd_pp=0.20,
            cos_phi_rg=0.8,
        )
        expected_kg = (10.5 / 11.0) * (1.10 / 1.12)
        assert math.isclose(kg, expected_kg, rel_tol=0.01)

    def test_transformer_correction_factor_kt_benchmark(self):
        """
        IEC TR 60909-1 Example 2:
        Network transformer: uk = 12% (xT = 0.12 pu), c_max = 1.10
        KT = 0.95 * (1.10 / (1 + 0.6 * 0.12)) = 0.95 * (1.10 / 1.072) = 0.9748
        """
        kt = calculate_kt(
            c_max=1.10,
            xt=0.12,
        )
        expected_kt = 0.974813
        assert math.isclose(kt, expected_kt, rel_tol=0.01), f"KT {kt:.5f} != expected {expected_kt:.5f}"

    def test_unit_block_correction_factor_ku_without_oltc(self):
        """
        IEC 60909-0 Clause 3.7.1 unit block without OLTC:
        Un = 110 kV, UrTHV = 115 kV, UrTLV = 10.5 kV, UrG = 10.5 kV
        c_max = 1.10, xd'' = 0.18, xT = 0.12, cos_phi = 0.85
        |xd'' - xT| = 0.06
        denom = 1 + 0.06 * sqrt(1 - 0.85^2) = 1 + 0.06 * 0.52678 = 1.0316
        KU = (110 / 115) * (10.5 / 10.5) * (1.10 / 1.0316) = 0.9565 * 1.0663 = 1.020
        """
        ku = calculate_ku(
            un_kv=110.0,
            urthv_kv=115.0,
            urtlv_kv=10.5,
            urg_kv=10.5,
            c_max=1.10,
            xd_pp=0.18,
            xt=0.12,
            cos_phi_rg=0.85,
            has_oltc=False,
        )
        expected_ku = (110.0 / 115.0) * (1.10 / (1.0 + 0.06 * math.sqrt(1 - 0.85**2)))
        assert math.isclose(ku, expected_ku, rel_tol=0.01)

    def test_unit_block_correction_factor_ku_with_oltc(self):
        """
        IEC 60909-0 Clause 3.7.2 unit block with OLTC (KSAT):
        Un = 110 kV, UrTHV = 115 kV, c_max = 1.10, xd'' = 0.18, cos_phi = 0.85
        denom = 1 + 0.18 * 0.52678 = 1.0948
        KU = (110 / 115)^2 * (1.10 / 1.0948) = 0.9149 * 1.0047 = 0.9192
        """
        ku = calculate_ku(
            un_kv=110.0,
            urthv_kv=115.0,
            urtlv_kv=10.5,
            urg_kv=10.5,
            c_max=1.10,
            xd_pp=0.18,
            xt=0.12,
            cos_phi_rg=0.85,
            has_oltc=True,
        )
        expected_ku = ((110.0 / 115.0) ** 2) * (1.10 / (1.0 + 0.18 * math.sqrt(1 - 0.85**2)))
        assert math.isclose(ku, expected_ku, rel_tol=0.01)


class TestIEC60909NearFarDecayAndSteadyState:
    """Validate mu decay and lambda steady-state current factor calculations."""

    @pytest.fixture
    def engine(self):
        # 2-bus system: bus 0 connected to bus 1 by line
        z = complex(0.01, 0.05)
        y = 1.0 / z
        Y = np.array([[y, -y], [-y, y]], dtype=complex)
        return IEC60909Engine(
            ybus_pos=Y,
            ybus_neg=Y,
            ybus_zero=Y,
            base_mva=100.0,
            base_kv=11.0,
            slack_bus_index=0,
            generator_type="salient",
            irg_pu=1.0,
        )

    def test_far_from_generator_steady_state(self, engine):
        """When Ik'' / IrG < 2.0, fault is far-from-generator: Ik = Ik''."""
        # Low current ratio (e.g. 1.5 pu)
        assert engine.is_near_generator(1.5, irg_pu=1.0) is False
        lam = engine._calculate_lambda(1.5, irg_pu=1.0)
        assert math.isclose(lam, 1.5, rel_tol=0.01)

    def test_near_generator_steady_state_salient(self, engine):
        """When Ik'' / IrG >= 2.0 on salient pole machine, lambda follows IEC curve."""
        assert engine.is_near_generator(4.0, irg_pu=1.0) is True
        lam = engine._calculate_lambda(4.0, irg_pu=1.0, generator_type="salient", maximum=True)
        # For ratio=4.0, salient-pole lambda should be between 1.5 and 2.5
        assert 1.5 <= lam <= 2.5

    def test_near_generator_steady_state_turbo(self, engine):
        """When Ik'' / IrG >= 2.0 on turbo generator, lambda follows Figure 13."""
        lam = engine._calculate_lambda(5.0, irg_pu=1.0, generator_type="turbo", maximum=True)
        # For turbo generator, lambda is bounded by 2.0
        assert 1.2 <= lam <= 2.0

    def test_minimum_steady_state_underexcited(self, engine):
        """Minimum steady-state short circuit uses reciprocal of unsaturated reactance."""
        lam_min = engine._calculate_lambda(5.0, irg_pu=1.0, maximum=False, xd_pu=1.5)
        expected = 1.0 / 1.5
        assert math.isclose(lam_min, expected, rel_tol=0.05)

    def test_breaking_current_decay_mu(self, engine):
        """Test breaking current decay factor mu decreases with delay time."""
        mu_fast = engine._calculate_mu(ik_initial_pu=5.0, t_min=0.02)
        mu_delayed = engine._calculate_mu(ik_initial_pu=5.0, t_min=0.10)
        assert mu_delayed < mu_fast
        assert 0.4 <= mu_delayed <= 1.0


class TestIEC60909BranchContributions:
    """Validate branch current calculations during bus faults."""

    def test_branch_current_conservation(self):
        """
        In a radial 3-bus network: Bus 0 (slack) -> Bus 1 -> Bus 2.
        A 3-phase fault at Bus 1 should draw current from Bus 0 (line 0-1)
        and zero current from unloaded downstream Bus 2 (line 1-2).
        """
        # Line 0-1: z = 0.01 + 0.05j
        # Line 1-2: z = 0.02 + 0.08j
        z01 = complex(0.01, 0.05)
        z12 = complex(0.02, 0.08)
        y01 = 1.0 / z01
        y12 = 1.0 / z12

        Y = np.zeros((3, 3), dtype=complex)
        Y[0, 0] += y01
        Y[1, 1] += y01 + y12
        Y[2, 2] += y12
        Y[0, 1] -= y01
        Y[1, 0] -= y01
        Y[1, 2] -= y12
        Y[2, 1] -= y12

        branches = [
            {"from_bus": 0, "to_bus": 1, "z1": z01},
            {"from_bus": 1, "to_bus": 2, "z1": z12},
        ]

        engine = IEC60909Engine(
            ybus_pos=Y,
            ybus_neg=Y,
            ybus_zero=Y,
            base_mva=100.0,
            base_kv=12.47,
            slack_bus_index=0,
            branches=branches,
        )

        res = engine.calculate_three_phase_fault(bus_index=1, bus_kv=12.47)
        assert len(res.branch_contributions) == 2

        # Branch 0-1 feeds the fault: current magnitude should equal total fault current
        br01 = [b for b in res.branch_contributions if b["from_bus"] == 0 and b["to_bus"] == 1][0]
        assert math.isclose(br01["current_ka"], res.Ik_initial_magnitude, rel_tol=0.01)

        # Branch 1-2 is unloaded downstream: current should be near zero
        br12 = [b for b in res.branch_contributions if b["from_bus"] == 1 and b["to_bus"] == 2][0]
        assert br12["current_ka"] < 1e-4


class TestIEC60909MethodEvidence:
    """Evidence tests for IEC 60909-0:2016 Clause 4.3.1.2 Method A peak factor kappa.

    Verifies mathematical and physical limits of Method A:
    1. R/X = 0.1 matches hand calculation (kappa = 1.7460).
    2. R/X -> 0 approaches theoretical upper bound (kappa = 2.0).
    3. Large R/X (10.0) approaches asymptotic lower bound (kappa ≈ 1.02).
    4. Published benchmark outputs remain invariant.
    """

    @staticmethod
    def _create_single_bus_engine(r: float, x: float) -> IEC60909Engine:
        """Helper to create a single-bus IEC 60909 engine with specified R and X impedance."""
        z = complex(r, x)
        y = 1.0 / z
        Y = np.array([[y]], dtype=complex)
        return IEC60909Engine(
            ybus_pos=Y,
            ybus_neg=Y,
            ybus_zero=Y,
            base_mva=100.0,
            base_kv=11.0,
            slack_bus_index=0,
        )

    def test_kappa_method_a_at_rx_0_point_1(self):
        """
        Verify peak factor kappa at R/X = 0.1 against hand calculation.

        Hand Calculation (IEC 60909-0:2016 Clause 4.3.1.2 Method A: Uniform ratio R/X):
        Formula:
            kappa = 1.02 + 0.98 * exp(-3.0 * (R/X))
        Step-by-step evaluation for R/X = 0.1:
            - Exponent: -3.0 * 0.1 = -0.3
            - exp(-0.3) = 0.7408182206817179
            - Product: 0.98 * 0.7408182206817179 = 0.7260018562680835
            - Sum: 1.02 + 0.7260018562680835 = 1.7460018562680837
        """
        engine = self._create_single_bus_engine(r=0.1, x=1.0)
        assert math.isclose(engine._get_rx_ratio(0), 0.1, rel_tol=1e-9)

        kappa = engine._calculate_kappa(0)
        expected_hand_calc = 1.02 + 0.98 * math.exp(-0.3)
        # Expected value is exactly 1.7460018562680837
        assert math.isclose(kappa, expected_hand_calc, rel_tol=1e-6)
        assert math.isclose(kappa, 1.746001856, rel_tol=1e-6)

    def test_kappa_method_a_upper_bound_rx_approaches_zero(self):
        """
        Verify that as R/X -> 0, kappa approaches the theoretical upper bound of 2.0.

        Hand Calculation (IEC 60909-0:2016 Clause 4.3.1.2 Upper Bound Limit):
        Formula:
            kappa = 1.02 + 0.98 * exp(-3.0 * (R/X))
        Physical boundary condition:
            In an ideal purely inductive network with negligible resistance (R/X -> 0):
            - Exponent: -3.0 * 0 = 0
            - exp(0) = 1.0
            - kappa = 1.02 + 0.98 * 1.0 = 2.0000
            The standard specifies kappa <= 2.0, representing the maximum possible
            asymmetrical peak current with 100% DC offset.
        """
        engine = self._create_single_bus_engine(r=1e-9, x=1.0)
        assert math.isclose(engine._get_rx_ratio(0), 0.0, abs_tol=1e-8)

        kappa = engine._calculate_kappa(0)
        expected_upper_bound = 2.0
        assert math.isclose(kappa, expected_upper_bound, rel_tol=1e-5)
        assert kappa <= 2.0, "Peak factor kappa must never exceed standard ceiling of 2.0"

    def test_kappa_method_a_lower_bound_large_rx(self):
        """
        Verify that for large R/X (e.g. R/X = 10.0), kappa approaches 1.02.

        Hand Calculation (IEC 60909-0:2016 Clause 4.3.1.2 Asymptotic Lower Bound):
        Formula:
            kappa = 1.02 + 0.98 * exp(-3.0 * (R/X))
        Step-by-step evaluation for R/X = 10.0 (high resistive damping):
            - Exponent: -3.0 * 10.0 = -30.0
            - exp(-30.0) = 9.357622968840175e-14 ≈ 0.0
            - Product: 0.98 * 9.3576e-14 ≈ 0.0
            - Sum: 1.02 + 0.0 = 1.0200000000000917 ≈ 1.02
        Physical meaning:
            With high resistance, the DC transient component decays almost instantaneously,
            so the peak current equals the AC peak (kappa ≈ 1.02).
        """
        engine = self._create_single_bus_engine(r=10.0, x=1.0)
        assert math.isclose(engine._get_rx_ratio(0), 10.0, rel_tol=1e-9)

        kappa = engine._calculate_kappa(0)
        expected_lower_bound = 1.02
        assert math.isclose(kappa, expected_lower_bound, rel_tol=1e-5)
        assert kappa >= 1.02, "Peak factor kappa must be >= 1.02"

    def test_published_benchmark_cases_numerical_invariance(self):
        """
        Prove that documentation updates and Method A evidence tests produce zero
        behavioral or numerical changes in published benchmark outputs.
        """
        # 1. Generator correction factor KG
        kg = calculate_kg(un_kv=10.5, urg_kv=10.5, c_max=1.10, xd_pp=0.15, cos_phi_rg=0.85)
        assert math.isclose(kg, 1.019447, rel_tol=1e-5)

        # 2. Transformer correction factor KT
        kt = calculate_kt(c_max=1.10, xt=0.12)
        assert math.isclose(kt, 0.974813, rel_tol=1e-5)

        # 3. Power station unit block KU without OLTC
        ku_no_oltc = calculate_ku(
            un_kv=110.0, urthv_kv=115.0, urtlv_kv=10.5, urg_kv=10.5,
            c_max=1.10, xd_pp=0.18, xt=0.12, cos_phi_rg=0.85, has_oltc=False,
        )
        assert math.isclose(ku_no_oltc, 1.019937, rel_tol=1e-5)

        # 4. Power station unit block KU with OLTC (KSAT)
        ku_oltc = calculate_ku(
            un_kv=110.0, urthv_kv=115.0, urtlv_kv=10.5, urg_kv=10.5,
            c_max=1.10, xd_pp=0.18, xt=0.12, cos_phi_rg=0.85, has_oltc=True,
        )
        assert math.isclose(ku_oltc, 0.919262, rel_tol=1e-5)

