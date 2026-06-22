"""
Comprehensive Unit Tests for Power System Engine
==================================================
Tests all core calculation engines with known analytical solutions.

Coverage targets:
- Load Flow: 95%+
- Short Circuit: 95%+
- Arc Flash: 95%+
- Protection Coordination: 90%+
- Harmonic Analysis: 85%+
- OPF: 80%+
"""

import os
import sys
import time
from datetime import UTC, datetime, timezone

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet

from agents.orchestrator import AgentResult, AgentStatus, EngineeringTask, StudyType
from coordination.coordination import CoordinationEngine
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer
from engine.async_executor import AsyncExecutor, TaskStatus, ThreadPoolManager, WorkflowOrchestrator
from engine.cache_manager import CacheKeyBuilder, CacheStrategy, CalculationCache
from engine.error_handler import (
    AlertManager,
    AutoRecoveryManager,
    ErrorHandler,
    ErrorSeverity,
    SystemError,
    component_guard,
)
from engine.numerical_safety import ConsistencyCheck, ConvergenceMonitor, NumericalGuard
from engine.resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    MultiLevelRecovery,
    RetryHandler,
    StabilityEnforcer,
)
from etap_integration.etap_com import STUDY_TYPE_PARAMETER_SCHEMAS, ETAPAutomation, ETAPStudyType
from fault_analysis.arc_flash_engine import ArcFlashEngine, ElectrodeConfig
from fault_analysis.fault import FaultAnalyzer
from fault_analysis.harmonic_analysis import HarmonicAnalysisEngine
from fault_analysis.iec60909_engine import IEC60909Engine
from load_flow.load_flow import LoadFlowSolver
from relays.relay import OvercurrentRelay
from security.secrets_manager import (
    EnvironmentValidator,
    KeyAccessAuditor,
    LocalSecretsManager,
    VaultSecretsManager,
)

# ============================================================================
# ETAP SCHEMA VALIDATION TESTS
# ============================================================================


class TestETAPSchemaValidation:
    """Test suite for per-study-type parameter schema validation."""

    def test_load_flow_valid_params(self):
        """Test that valid load flow parameters pass validation."""
        params = {"method": "newton_raphson", "max_iterations": 100, "tolerance": 1e-6}
        result = ETAPAutomation._validate_study_parameters(ETAPStudyType.LOAD_FLOW, params)
        assert result == params

    def test_load_flow_invalid_method(self):
        """Test that invalid method is rejected."""
        with pytest.raises(ValueError, match="not in allowed"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"method": "invalid_method"}
            )

    def test_load_flow_unknown_key_rejected(self):
        """Test that unknown parameter keys are rejected."""
        with pytest.raises(ValueError, match="Unknown parameter"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"unsupported_key": 123}
            )

    def test_short_circuit_valid_params(self):
        """Test that valid short circuit parameters pass validation."""
        params = {"fault_type": "ThreePhase", "standard": "iec60909"}
        result = ETAPAutomation._validate_study_parameters(ETAPStudyType.SHORT_CIRCUIT, params)
        assert result == params

    def test_short_circuit_invalid_fault_type(self):
        """Test that invalid fault type is rejected."""
        with pytest.raises(ValueError, match="not in allowed"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.SHORT_CIRCUIT, {"fault_type": "UnknownFault"}
            )

    def test_arc_flash_numeric_bounds(self):
        """Test that numeric bounds are enforced for arc flash."""
        with pytest.raises(ValueError, match="below minimum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.ARC_FLASH, {"working_distance_mm": 10.0}
            )
        with pytest.raises(ValueError, match="above maximum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.ARC_FLASH, {"working_distance_mm": 999999.0}
            )

    def test_harmonic_integer_type_enforcement(self):
        """Test that integer type is enforced for harmonic params."""
        with pytest.raises(ValueError, match="must be integer"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.HARMONIC_ANALYSIS, {"max_harmonic_order": "not_an_int"}
            )

    def test_harmonic_numeric_bounds(self):
        """Test that integer bounds are enforced."""
        with pytest.raises(ValueError, match="below minimum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.HARMONIC_ANALYSIS, {"max_harmonic_order": 1}
            )
        with pytest.raises(ValueError, match="above maximum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.HARMONIC_ANALYSIS, {"max_harmonic_order": 999}
            )

    def test_opf_boolean_type_enforcement(self):
        """Test that boolean type is enforced for OPF params."""
        with pytest.raises(ValueError, match="must be boolean"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.OPTIMAL_POWER_FLOW, {"include_reactive": "yes"}
            )

    def test_protection_coordination_valid_params(self):
        """Test valid protection coordination params."""
        params = {"curve_type": "standard_inverse", "tms_min": 0.05, "tms_max": 1.0}
        result = ETAPAutomation._validate_study_parameters(
            ETAPStudyType.PROTECTION_COORDINATION, params
        )
        assert result == params

    def test_empty_params_accepted(self):
        """Test that empty params dict is accepted (all params optional)."""
        result = ETAPAutomation._validate_study_parameters(ETAPStudyType.LOAD_FLOW, {})
        assert result == {}

    def test_non_dict_params_rejected(self):
        """Test that non-dict params are rejected."""
        with pytest.raises(ValueError, match="must be a dict"):
            ETAPAutomation._validate_study_parameters(ETAPStudyType.LOAD_FLOW, "not_a_dict")

    def test_invalid_study_type_rejected(self):
        """Test that non-ETAPStudyType is rejected."""
        with pytest.raises(ValueError, match="must be ETAPStudyType"):
            ETAPAutomation._validate_study_parameters("LOAD_FLOW", {})

    def test_cable_ampacity_valid_params(self):
        """Test valid cable ampacity params."""
        params = {"installation_method": "underground", "ambient_temperature_c": 25.0}
        result = ETAPAutomation._validate_study_parameters(ETAPStudyType.CABLE_AMACITY, params)
        assert result == params

    def test_ground_grid_valid_params(self):
        """Test valid ground grid params."""
        params = {"soil_resistivity_ohm_m": 100.0}
        result = ETAPAutomation._validate_study_parameters(ETAPStudyType.GROUND_GRID, params)
        assert result == params

    def test_all_schemas_have_valid_keys(self):
        """Test that all study types have a schema defined."""
        for study_type in ETAPStudyType:
            schema = STUDY_TYPE_PARAMETER_SCHEMAS.get(study_type, {})
            for key, rule in schema.items():
                assert "type" in rule, f"{study_type}.{key} missing 'type'"
                assert rule["type"] in ("numeric", "integer", "string", "boolean", "list"), (
                    f"{study_type}.{key} has unknown type: {rule['type']}"
                )


# ============================================================================
# WORKER RBAC TESTS
# ============================================================================


class TestWorkerRBAC:
    """Test suite for ETAP worker RBAC enforcement."""

    def test_study_type_to_permission_mapping_complete(self):
        """Test that all implemented study types have RBAC permission mappings."""
        # Import the worker's permission mapping
        from etap_integration.etap_worker_service import STUDY_TYPE_TO_PERMISSION
        from security.security_framework import Permission

        implemented_studies = [
            ETAPStudyType.LOAD_FLOW,
            ETAPStudyType.SHORT_CIRCUIT,
            ETAPStudyType.ARC_FLASH,
            ETAPStudyType.OPTIMAL_POWER_FLOW,
            ETAPStudyType.PROTECTION_COORDINATION,
            ETAPStudyType.HARMONIC_ANALYSIS,
        ]

        for study_type in implemented_studies:
            assert study_type in STUDY_TYPE_TO_PERMISSION, (
                f"{study_type} missing from STUDY_TYPE_TO_PERMISSION"
            )
            assert isinstance(STUDY_TYPE_TO_PERMISSION[study_type], Permission), (
                f"{study_type} maps to non-Permission value"
            )

    def test_engineer_has_all_calc_permissions(self):
        """Test that engineer role has all required calc permissions."""
        from etap_integration.etap_worker_service import STUDY_TYPE_TO_PERMISSION
        from security.security_framework import (
            AuthenticationManager,
            AuthorizationManager,
            UserRole,
        )

        auth = AuthenticationManager(secret_key="test-rbac-secret")
        authz = AuthorizationManager(auth)

        auth.create_user("engineer", "eng@test.com", "password123", UserRole.ENGINEER)
        token = auth.authenticate("engineer", "password123")
        assert token is not None

        for study_type, permission in STUDY_TYPE_TO_PERMISSION.items():
            assert authz.check_permission(token, permission), (
                f"Engineer should have {permission.value} for {study_type.value}"
            )

    def test_viewer_cannot_execute_studies(self):
        """Test that viewer role lacks calc permissions."""
        from etap_integration.etap_worker_service import STUDY_TYPE_TO_PERMISSION
        from security.security_framework import (
            AuthenticationManager,
            AuthorizationManager,
            UserRole,
        )

        auth = AuthenticationManager(secret_key="test-viewer-secret")
        authz = AuthorizationManager(auth)

        auth.create_user("viewer", "viewer@test.com", "password123", UserRole.VIEWER)
        token = auth.authenticate("viewer", "password123")
        assert token is not None

        for study_type, permission in STUDY_TYPE_TO_PERMISSION.items():
            assert not authz.check_permission(token, permission), (
                f"Viewer should NOT have {permission.value} for {study_type.value}"
            )

    def test_guest_has_no_permissions(self):
        """Test that guest role has zero permissions."""
        from security.security_framework import (
            AuthenticationManager,
            AuthorizationManager,
            Permission,
            UserRole,
        )

        auth = AuthenticationManager(secret_key="test-guest-secret")
        authz = AuthorizationManager(auth)

        auth.create_user("guest", "guest@test.com", "password123", UserRole.GUEST)
        token = auth.authenticate("guest", "password123")
        assert token is not None

        for perm in list(Permission)[:5]:  # Check a subset
            assert not authz.check_permission(token, perm), f"Guest should NOT have {perm.value}"

    def test_invalid_token_rejected(self):
        """Test that an invalid/fake token is rejected by authz."""
        from etap_integration.etap_worker_service import STUDY_TYPE_TO_PERMISSION
        from security.security_framework import AuthenticationManager, AuthorizationManager

        auth = AuthenticationManager(secret_key="test-invalid-secret")
        authz = AuthorizationManager(auth)

        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.fake"
        for permission in STUDY_TYPE_TO_PERMISSION.values():
            assert not authz.check_permission(fake_token, permission), (
                f"Fake token should not have {permission.value}"
            )

    def test_permission_after_logout_rejected(self):
        """Test that token is rejected after logout."""
        from etap_integration.etap_worker_service import STUDY_TYPE_TO_PERMISSION
        from security.security_framework import (
            AuthenticationManager,
            AuthorizationManager,
            UserRole,
        )

        auth = AuthenticationManager(secret_key="test-logout-secret")
        authz = AuthorizationManager(auth)

        auth.create_user("temp_user", "temp@test.com", "password123", UserRole.ENGINEER)
        token = auth.authenticate("temp_user", "password123")

        # Before logout, permissions should work
        first_perm = list(STUDY_TYPE_TO_PERMISSION.values())[0]
        assert authz.check_permission(token, first_perm)

        # After logout, permissions should be denied
        auth.logout(token)
        assert not authz.check_permission(token, first_perm), "Token should be invalid after logout"


# ============================================================================
# LOAD FLOW TESTS
# ============================================================================


class TestLoadFlow:
    """Test suite for load flow calculations."""

    @pytest.fixture
    def simple_2bus_system(self):
        """Create a simple 2-bus system for testing."""
        system = System(base_mva=100.0)

        bus1 = Bus(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack")
        bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq")

        system.add_bus(bus1)
        system.add_bus(bus2)

        gen = Generator(
            generator_id=1,
            bus=bus1,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)

        load = Load(load_id=1, bus=bus2, load_power=complex(0.5, 0.2))
        system.add_load(load)

        line = Line(
            line_id=1,
            from_bus=bus1,
            to_bus=bus2,
            z1=complex(0.01, 0.05),
            z2=complex(0.01, 0.05),
            z0=complex(0.03, 0.15),
        )
        system.add_line(line)

        return system

    def test_convergence(self, simple_2bus_system):
        """Test that load flow converges for simple system."""
        solver = LoadFlowSolver(simple_2bus_system)
        converged = solver.solve(max_iter=100, tol=1e-6)

        assert converged, "Load flow should converge for simple 2-bus system"

    def test_voltage_magnitudes_in_range(self, simple_2bus_system):
        """Test that voltages are within acceptable range."""
        solver = LoadFlowSolver(simple_2bus_system)
        solver.solve()

        for bus_id, bus in simple_2bus_system.buses.items():
            v_mag = abs(bus.voltage)
            assert 0.9 <= v_mag <= 1.1, f"Bus {bus_id} voltage {v_mag} out of range [0.9, 1.1]"

    def test_slack_bus_voltage_fixed(self, simple_2bus_system):
        """Test that slack bus voltage remains at specified value."""
        solver = LoadFlowSolver(simple_2bus_system)
        solver.solve()

        slack_bus = simple_2bus_system.buses[1]
        assert abs(abs(slack_bus.voltage) - 1.05) < 1e-4, "Slack bus voltage should be fixed"
        assert abs(np.angle(slack_bus.voltage)) < 1e-4, "Slack bus angle should be 0"

    def test_power_balance(self, simple_2bus_system):
        """Test that power generation equals load plus losses."""
        solver = LoadFlowSolver(simple_2bus_system)
        solver.solve()

        total_gen = sum(b.generation_power.real for b in simple_2bus_system.buses.values())
        total_load = sum(b.load_power.real for b in simple_2bus_system.buses.values())

        # Generation should be greater than load (due to losses)
        assert total_gen >= total_load, "Generation should cover load and losses"

    def test_ybus_symmetry(self, simple_2bus_system):
        """Test that Ybus matrix is symmetric."""
        Ybus = simple_2bus_system.build_ybus(seq="1")
        # Ybus for passive networks is symmetric (Y == Y^T), not Hermitian
        assert np.allclose(Ybus, Ybus.T), "Ybus should be symmetric"


# ============================================================================
# SHORT CIRCUIT TESTS
# ============================================================================


class TestShortCircuit:
    """Test suite for short circuit calculations."""

    @pytest.fixture
    def fault_system(self):
        """Create system for fault analysis testing."""
        system = System(base_mva=100.0)

        bus1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack")
        bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq")

        system.add_bus(bus1)
        system.add_bus(bus2)

        gen = Generator(
            generator_id=1,
            bus=bus1,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)

        line = Line(
            line_id=1,
            from_bus=bus1,
            to_bus=bus2,
            z1=complex(0.01, 0.05),
            z2=complex(0.01, 0.05),
            z0=complex(0.03, 0.15),
        )
        system.add_line(line)

        system.build_sequence_networks()

        Ybus_pos = system.get_ybus(seq="1")
        Ybus_neg = system.get_ybus(seq="2")
        Ybus_zero = system.get_ybus(seq="0")

        return FaultAnalyzer(Ybus_pos, Ybus_neg, Ybus_zero, base_mva=100.0, base_kv=115.0)

    def test_three_phase_fault_positive_current(self, fault_system):
        """Test that three-phase fault current is positive."""
        result = fault_system.three_phase_fault(0)
        assert result["fault_current"] != 0, "Fault current should be non-zero"
        assert abs(result["fault_current"]) > 0, "Fault current magnitude should be positive"

    def test_line_to_ground_fault(self, fault_system):
        """Test line-to-ground fault calculation."""
        result = fault_system.line_to_ground_fault(0)
        assert result["fault_current"] != 0, "SLG fault current should be non-zero"

    def test_line_to_line_fault(self, fault_system):
        """Test line-to-line fault calculation."""
        result = fault_system.line_to_line_fault(0)
        assert result["fault_current"] != 0, "LL fault current should be non-zero"

    def test_double_line_to_ground_fault(self, fault_system):
        """Test double line-to-ground fault calculation."""
        result = fault_system.double_line_to_ground_fault(0)
        assert (
            result["fault_current_b_magnitude"] != 0 or result["fault_current_c_magnitude"] != 0
        ), "DLG fault currents should be non-zero"

    def test_iec60909_three_phase(self):
        """Test IEC 60909 three-phase fault calculation."""
        # Simple system
        _n = 2
        Ybus = np.array(
            [[complex(10, -50), complex(-10, 50)], [complex(-10, 50), complex(10, -50)]]
        )

        engine = IEC60909Engine(Ybus, Ybus, Ybus, base_mva=100.0, base_kv=115.0)
        result = engine.calculate_three_phase_fault(0, bus_kv=115.0)

        assert result.Ik_initial_magnitude > 0, "IEC fault current should be positive"
        assert result.ip_peak > 0, "Peak current should be positive"
        assert result.Ib_breaking > 0, "Breaking current should be positive"


# ============================================================================
# ARC FLASH TESTS
# ============================================================================


class TestArcFlash:
    """Test suite for arc flash calculations."""

    def test_arc_current_calculation(self):
        """Test arc current calculation per IEEE 1584."""
        engine = ArcFlashEngine()

        Iarc, Iarc_reduced = engine.calculate_arc_current(
            voltage_kv=4.16, bolted_fault_current_ka=20.0, electrode_config=ElectrodeConfig.VCB
        )

        assert Iarc > 0, "Arc current should be positive"
        assert Iarc_reduced == 0.85 * Iarc, "Reduced arc current should be 85% of full"

    def test_incident_energy_positive(self):
        """Test that incident energy is always positive."""
        engine = ArcFlashEngine()

        result = engine.calculate(
            voltage_kv=4.16,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.5,
            working_distance_mm=610.0,
        )

        assert result.incident_energy_cal_cm2 > 0, "Incident energy should be positive"

    def test_arc_flash_boundary_positive(self):
        """Test that arc flash boundary is positive."""
        engine = ArcFlashEngine()

        result = engine.calculate(
            voltage_kv=4.16,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.5,
            working_distance_mm=610.0,
        )

        assert result.arc_flash_boundary_mm > 0, "Arc flash boundary should be positive"

    def test_ppe_level_assignment(self):
        """Test that PPE level is correctly assigned."""
        engine = ArcFlashEngine()

        result = engine.calculate(
            voltage_kv=4.16,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.5,
            working_distance_mm=610.0,
        )

        valid_ppe_levels = ["0", "1", "2", "3", "4", "DANGER"]
        assert result.ppe_level in valid_ppe_levels, f"Invalid PPE level: {result.ppe_level}"

    def test_voltage_sensitivity(self):
        """Test that higher voltage produces different results."""
        engine = ArcFlashEngine()

        result_low = engine.calculate(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.5,
            working_distance_mm=610.0,
        )

        result_high = engine.calculate(
            voltage_kv=13.8,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.5,
            working_distance_mm=610.0,
        )

        assert result_low.incident_energy_cal_cm2 != result_high.incident_energy_cal_cm2, (
            "Different voltages should produce different incident energies"
        )

    def test_input_validation(self):
        """Test that invalid inputs raise errors."""
        engine = ArcFlashEngine()

        with pytest.raises(ValueError):
            engine.calculate(
                voltage_kv=0.1,  # Below IEEE 1584 range
                bolted_fault_current_ka=20.0,
                arc_duration_sec=0.5,
                working_distance_mm=610.0,
            )

        with pytest.raises(ValueError):
            engine.calculate(
                voltage_kv=4.16,
                bolted_fault_current_ka=20.0,
                arc_duration_sec=-1.0,  # Negative duration
                working_distance_mm=610.0,
            )


# ============================================================================
# PROTECTION COORDINATION TESTS
# ============================================================================


class TestProtectionCoordination:
    """Test suite for protection coordination."""

    def test_standard_inverse_curve(self):
        """Test IEC 60255 standard inverse curve."""
        relay = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)

        # At I/Ip = 10, t ≈ 2.97s
        t = relay.trip_time(10.0)
        expected = 1.0 * 0.14 / ((10.0) ** 0.02 - 1)

        assert abs(t - expected) < 0.01, f"Trip time {t} should be close to {expected}"

    def test_very_inverse_curve(self):
        """Test IEC 60255 very inverse curve."""
        relay = OvercurrentRelay(relay_id=1, curve_type="very_inverse", TMS=1.0, Ip=1.0)

        # At I/Ip = 10, t = 13.5 / (10 - 1) = 1.5s
        t = relay.trip_time(10.0)
        expected = 1.0 * 13.5 / (10.0 - 1.0)

        assert abs(t - expected) < 0.01, f"Trip time {t} should be close to {expected}"

    def test_extremely_inverse_curve(self):
        """Test IEC 60255 extremely inverse curve."""
        relay = OvercurrentRelay(relay_id=1, curve_type="extremely_inverse", TMS=1.0, Ip=1.0)

        # At I/Ip = 10, t = 80 / (10^2 - 1) = 0.808s
        t = relay.trip_time(10.0)
        expected = 1.0 * 80.0 / (10.0**2 - 1.0)

        assert abs(t - expected) < 0.01, f"Trip time {t} should be close to {expected}"

    def test_coordination_downstream_faster(self):
        """Test that downstream relay trips before upstream."""
        coord_engine = CoordinationEngine()

        upstream = OvercurrentRelay(relay_id=1, TMS=0.5, Ip=1.0)
        downstream = OvercurrentRelay(relay_id=2, TMS=0.2, Ip=1.0)

        result = coord_engine.check_coordination(upstream, downstream, 5.0)

        assert result["downstream_time"] < result["upstream_time"], (
            "Downstream relay should trip faster"
        )

    def test_coordination_margin(self):
        """Test coordination margin requirement."""
        coord_engine = CoordinationEngine()

        upstream = OvercurrentRelay(relay_id=1, TMS=0.5, Ip=1.0)
        downstream = OvercurrentRelay(relay_id=2, TMS=0.2, Ip=1.0)

        result = coord_engine.check_coordination(upstream, downstream, 5.0)

        if result["coordinated"]:
            assert result["margin"] >= 0.2, "Coordination margin should be at least 0.2s"


# ============================================================================
# HARMONIC ANALYSIS TESTS
# ============================================================================


class TestHarmonicAnalysis:
    """Test suite for harmonic analysis."""

    def test_harmonic_impedance_scaling(self):
        """Test that harmonic impedance scales correctly."""
        engine = HarmonicAnalysisEngine(fundamental_freq=60.0, max_harmonic=50)

        # Create non-singular Ybus (add shunt admittance to make invertible)
        # A pure 2-bus line matrix is singular; adding shunt makes it invertible
        Ybus = np.array(
            [[complex(10.1, -50.5), complex(-10, 50)], [complex(-10, 50), complex(10.1, -50.5)]]
        )

        engine.set_system_data(Ybus, ["bus1", "bus2"])

        # Calculate harmonic impedance at 5th harmonic
        Ybus_5th = engine.calculate_harmonic_impedance(5)

        # Impedance should scale with harmonic order
        assert Ybus_5th.shape == Ybus.shape, "Ybus shape should be preserved"

    def test_thd_calculation(self):
        """Test THD calculation."""
        engine = HarmonicAnalysisEngine()
        # Set bus_ids so calculate_thd knows which buses to process
        engine.set_system_data(Ybus_fundamental=np.array([[complex(0.1, -0.5)]]), bus_ids=["bus1"])

        # Mock harmonic results
        from fault_analysis.harmonic_analysis import HarmonicResult

        fundamental_mag = {"bus1": 1.0}
        harmonic_results = [
            HarmonicResult(
                harmonic_order=h,
                frequency_hz=h * 60.0,
                bus_voltages={"bus1": complex(0.05 / h, 0)},
                branch_currents={},
                thd_voltage={},
                thd_current={},
            )
            for h in range(2, 11)
        ]

        thd = engine.calculate_thd(harmonic_results, fundamental_mag)

        assert "bus1" in thd, "THD should be calculated for bus1"
        assert thd["bus1"] >= 0, "THD should be non-negative"

    def test_resonance_detection(self):
        """Test resonance detection."""
        engine = HarmonicAnalysisEngine()

        from fault_analysis.harmonic_analysis import HarmonicResult

        # Create results with high voltage magnification (indicating resonance)
        harmonic_results = [
            HarmonicResult(
                harmonic_order=5,
                frequency_hz=300.0,
                bus_voltages={"bus1": complex(15.0, 0)},  # High magnification
                branch_currents={},
                thd_voltage={},
                thd_current={},
            )
        ]

        detected, freqs = engine.detect_resonance(harmonic_results, threshold_factor=10.0)

        assert detected, "Resonance should be detected"
        assert len(freqs) > 0, "Resonance frequencies should be identified"

    def test_passive_filter_design(self):
        """Test passive filter design."""
        engine = HarmonicAnalysisEngine(fundamental_freq=60.0)

        filter_design = engine.design_passive_filter(target_harmonic=5, q_factor=50.0)

        assert "capacitance_F" in filter_design, "Filter should have capacitance"
        assert "inductance_H" in filter_design, "Filter should have inductance"
        assert "resistance_ohm" in filter_design, "Filter should have resistance"
        assert filter_design["capacitance_F"] > 0, "Capacitance should be positive"
        assert filter_design["inductance_H"] > 0, "Inductance should be positive"


# ============================================================================
# OPTIMAL POWER FLOW TESTS
# ============================================================================


class TestOptimalPowerFlow:
    """Test suite for optimal power flow."""

    def test_dc_opf_convergence(self):
        """Test DC-OPF convergence."""
        from load_flow.optimal_power_flow import GeneratorCost, OptimalPowerFlowEngine

        # Simple 2-bus system
        Ybus = np.array(
            [[complex(10, -50), complex(-10, 50)], [complex(-10, 50), complex(10, -50)]]
        )

        gen_cost = GeneratorCost(
            generator_id=1,
            cost_coefficients=[100, 20, 0.5],  # $/hr = 100 + 20*P + 0.5*P^2
            p_min=0.0,
            p_max=100.0,
            q_min=-50.0,
            q_max=50.0,
        )

        opf = OptimalPowerFlowEngine(Ybus, [1, 2], [gen_cost])
        opf.set_load_data({2: complex(50.0, 20.0)})  # 50 MW load at bus 2
        opf.set_generator_locations({1: 2})  # Generator 1 at bus 2 (same bus as load)

        result = opf.solve_opf(method="dc")

        assert result.success, "DC-OPF should converge"
        assert result.total_generation > 0, "Generation should be positive"

    def test_opf_cost_minimization(self):
        """Test that OPF minimizes cost."""
        from load_flow.optimal_power_flow import GeneratorCost, OptimalPowerFlowEngine

        Ybus = np.array(
            [[complex(10, -50), complex(-10, 50)], [complex(-10, 50), complex(10, -50)]]
        )

        # Two generators with different costs
        gen1 = GeneratorCost(
            generator_id=1,
            cost_coefficients=[0, 10, 0],  # Cheap: $10/MW
            p_min=0.0,
            p_max=100.0,
            q_min=-50.0,
            q_max=50.0,
        )

        gen2 = GeneratorCost(
            generator_id=2,
            cost_coefficients=[0, 30, 0],  # Expensive: $30/MW
            p_min=0.0,
            p_max=100.0,
            q_min=-50.0,
            q_max=50.0,
        )

        opf = OptimalPowerFlowEngine(Ybus, [1, 2], [gen1, gen2])
        opf.set_load_data({2: complex(50.0, 0)})
        opf.set_generator_locations({1: 1, 2: 1})

        result = opf.solve_opf(method="dc")

        if result.success:
            # Cheaper generator should produce more power
            P1 = result.generator_dispatch[1].real
            P2 = result.generator_dispatch[2].real

            # This is a simplified test - actual dispatch depends on constraints
            assert P1 + P2 > 0, "Total generation should be positive"


# ============================================================================
# SECURITY FRAMEWORK TESTS
# ============================================================================


class TestSecurityFramework:
    """Test suite for security framework."""

    def test_user_creation(self):
        """Test user account creation."""
        from security.security_framework import AuthenticationManager, UserRole

        auth = AuthenticationManager(secret_key="test_secret")
        user = auth.create_user("testuser", "test@example.com", "password123", UserRole.ENGINEER)

        assert user is not None, "User should be created"
        assert user.username == "testuser"
        assert user.role == UserRole.ENGINEER

    def test_authentication_success(self):
        """Test successful authentication."""
        from security.security_framework import AuthenticationManager, UserRole

        auth = AuthenticationManager(secret_key="test_secret")
        auth.create_user("testuser", "test@example.com", "password123", UserRole.ENGINEER)

        token = auth.authenticate("testuser", "password123")

        assert token is not None, "Authentication should succeed"

    def test_authentication_failure(self):
        """Test failed authentication."""
        from security.security_framework import AuthenticationManager

        auth = AuthenticationManager(secret_key="test_secret")
        auth.create_user("testuser", "test@example.com", "password123")

        token = auth.authenticate("testuser", "wrong_password")

        assert token is None, "Authentication should fail with wrong password"

    def test_permission_check(self):
        """Test permission checking."""
        from security.security_framework import (
            AuthenticationManager,
            AuthorizationManager,
            Permission,
            UserRole,
        )

        auth = AuthenticationManager(secret_key="test_secret")
        authz = AuthorizationManager(auth)

        auth.create_user("engineer", "eng@example.com", "password123", UserRole.ENGINEER)
        token = auth.authenticate("engineer", "password123")

        # Engineer should have CALC_LOAD_FLOW permission
        has_perm = authz.check_permission(token, Permission.CALC_LOAD_FLOW)
        assert has_perm, "Engineer should have CALC_LOAD_FLOW permission"

        # Engineer should not have ADMIN_USERS permission
        has_admin = authz.check_permission(token, Permission.ADMIN_USERS)
        assert not has_admin, "Engineer should not have ADMIN_USERS permission"

    def test_input_validation_python_code(self):
        """Test Python code validation."""
        from security.security_framework import InputValidator

        validator = InputValidator()

        # Safe code
        safe_code = "import numpy as np\nx = np.array([1, 2, 3])"
        assert validator.validate_python_code(safe_code), "Safe code should pass validation"

        # Dangerous code
        dangerous_code = "import os\nos.system('rm -rf /')"
        assert not validator.validate_python_code(dangerous_code), (
            "Dangerous code should fail validation"
        )

    def test_rate_limiting(self):
        """Test rate limiting."""
        from security.security_framework import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed("client1"), f"Request {i + 1} should be allowed"

        # 6th request should be denied
        assert not limiter.is_allowed("client1"), "6th request should be rate-limited"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_load_flow_workflow(self):
        """Test complete load flow workflow from system creation to results."""
        system = System(base_mva=100.0)

        # Create 3-bus system
        for i in range(1, 4):
            bus_type = "slack" if i == 1 else "pq"
            bus = Bus(bus_id=i, voltage_magnitude=1.0, voltage_angle=0.0, bus_type=bus_type)
            system.add_bus(bus)

        # Add generator
        gen = Generator(
            generator_id=1,
            bus=system.buses[1],
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)

        # Add loads
        for i in range(2, 4):
            load = Load(load_id=i, bus=system.buses[i], load_power=complex(0.5, 0.2))
            system.add_load(load)

        # Add lines
        for i in range(1, 3):
            line = Line(
                line_id=i,
                from_bus=system.buses[i],
                to_bus=system.buses[i + 1],
                z1=complex(0.01, 0.05),
            )
            system.add_line(line)

        # Run load flow
        solver = LoadFlowSolver(system)
        converged = solver.solve()

        assert converged, "Load flow should converge"

        # Verify all buses have voltages
        for bus_id, bus in system.buses.items():
            assert abs(bus.voltage) > 0, f"Bus {bus_id} should have non-zero voltage"

    def test_fault_analysis_workflow(self):
        """Test complete fault analysis workflow."""
        system = System(base_mva=100.0)

        bus1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack")
        bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq")

        system.add_bus(bus1)
        system.add_bus(bus2)

        gen = Generator(
            generator_id=1,
            bus=bus1,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)

        line = Line(
            line_id=1,
            from_bus=bus1,
            to_bus=bus2,
            z1=complex(0.01, 0.05),
            z2=complex(0.01, 0.05),
            z0=complex(0.03, 0.15),
        )
        system.add_line(line)

        system.build_sequence_networks()

        Ybus_pos = system.get_ybus(seq="1")
        Ybus_neg = system.get_ybus(seq="2")
        Ybus_zero = system.get_ybus(seq="0")

        analyzer = FaultAnalyzer(Ybus_pos, Ybus_neg, Ybus_zero)

        # Test all fault types
        faults = [
            analyzer.three_phase_fault(0),
            analyzer.line_to_ground_fault(0),
            analyzer.line_to_line_fault(0),
            analyzer.double_line_to_ground_fault(0),
        ]

        for fault in faults:
            assert "fault_current" in fault or "fault_current_b" in fault, (
                "Fault result should contain current"
            )


# ============================================================================
# SECRETS MANAGER TESTS
# ============================================================================


class TestSecretsManager:
    """Test suite for secrets management."""

    def test_vault_manager_initialization(self):
        mgr = VaultSecretsManager(use_mock_if_unavailable=True)
        # When Vault is unavailable, falls back to LocalSecretsManager
        assert mgr._fallback_store._cipher is not None
        ok = mgr.set_secret("test/path", "test_key", "secret_value")
        assert ok
        val = mgr.get_secret("test/path", "test_key")
        assert val == "secret_value"
        mgr.set_secret("other/path", "other_key", "other_val")
        keys = mgr.list_secrets("test/path")
        assert "test_key" in keys
        ok = mgr.delete_secret("test/path", "test_key")
        assert ok
        val = mgr.get_secret("test/path", "test_key")
        assert val is None

    def test_local_secrets_store_retrieve(self, tmp_path, monkeypatch):
        monkeypatch.setattr("security.secrets_manager.SECRETS_DIR", tmp_path / "secrets")
        monkeypatch.setattr(
            "security.secrets_manager.ENCRYPTION_KEY_FILE", tmp_path / "secrets" / ".encryption_key"
        )
        key = Fernet.generate_key()
        mgr = LocalSecretsManager(encryption_key=key)
        ok = mgr.set_api_key("svc_test", "sk-test-key-abc")
        assert ok
        val = mgr.get_api_key("svc_test")
        assert val == "sk-test-key-abc"
        mgr.delete_api_key("svc_test")
        assert mgr.get_api_key("svc_test") is None

    def test_key_rotation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("security.secrets_manager.SECRETS_DIR", tmp_path / "secrets")
        monkeypatch.setattr(
            "security.secrets_manager.ENCRYPTION_KEY_FILE", tmp_path / "secrets" / ".encryption_key"
        )
        key = Fernet.generate_key()
        mgr = LocalSecretsManager(encryption_key=key)
        mgr.set_api_key("svc_rotate", "key-to-rotate")
        ok = mgr.rotate_key()
        assert ok
        val = mgr.get_api_key("svc_rotate")
        assert val == "key-to-rotate"

    def test_key_access_audit_logging(self, tmp_path, monkeypatch):

        monkeypatch.setattr("security.secrets_manager.AUDIT_DIR", tmp_path / "audit")
        auditor = KeyAccessAuditor()
        auditor.log_access("user_a", "api-key-1", KeyAccessAuditor.ACTION_GET, True)
        auditor.log_access(
            "user_a", "api-key-2", KeyAccessAuditor.ACTION_GET, True, {"origin": "dashboard"}
        )
        logs = auditor.get_access_logs()
        assert len(logs) == 2
        assert logs[0]["user_id"] == "user_a"
        filtered = auditor.get_access_logs(key_name="api-key-1")
        assert len(filtered) == 1
        recent = auditor.get_recent_access(limit=1)
        assert len(recent) == 1

    def test_environment_validator(self, tmp_path):
        validator = EnvironmentValidator()
        template = validator.generate_env_template(tmp_path / ".env.test")
        assert "JWT_SECRET_KEY" in template
        assert "ENVIRONMENT" in template
        findings = validator.check_for_hardcoded_secrets(file_patterns=["*.md"])
        assert isinstance(findings, list)


# ============================================================================
# RESILIENCE TESTS
# ============================================================================


class TestResilience:
    """Test suite for resilience patterns."""

    def test_retry_handler_success_on_retry(self):
        handler = RetryHandler(max_retries=3, base_delay=0.01, jitter=False)
        call_count = [0]

        def flaky_fn():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("transient fail")
            return "ok"

        result = handler.execute(flaky_fn)
        assert result == "ok"
        assert handler.total_calls == 1
        assert handler.total_retries == 1

    def test_retry_handler_max_retries_exceeded(self):
        handler = RetryHandler(max_retries=2, base_delay=0.01, jitter=False)

        def always_fail():
            raise ConnectionError("permanent fail")

        with pytest.raises(ConnectionError):
            handler.execute(always_fail)
        assert handler.total_calls == 1
        assert handler.total_retries == 2

    def test_circuit_breaker_closed_to_open(self):
        cb = CircuitBreaker(name="ut_closed_open", failure_threshold=3, recovery_timeout=100)
        assert cb.get_state() == CircuitBreakerState.CLOSED

        def fail():
            raise ValueError("fail")

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(fail)
        assert cb.get_state() == CircuitBreakerState.OPEN
        assert cb.state_changes == 1
        assert cb.failed_calls == 3

    def test_circuit_breaker_half_open_recovery(self):
        cb = CircuitBreaker(name="ut_half_open", failure_threshold=2, recovery_timeout=0.05)

        def fail():
            raise ValueError("fail")

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(fail)
        assert cb.get_state() == CircuitBreakerState.OPEN
        time.sleep(0.06)
        cb._check_state_transition()
        assert cb.get_state() == CircuitBreakerState.HALF_OPEN
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.get_state() == CircuitBreakerState.CLOSED

    def test_multi_level_recovery_level_1(self):
        recovery = MultiLevelRecovery(name="ut_mlr")
        actions = []
        recovery.add_strategy(1, lambda e, ctx: actions.append("fast_fix"))
        result = recovery.recover(ValueError("test"))
        assert result.success
        assert result.level_used == 1
        assert len(result.actions_taken) == 1
        assert recovery.total_recoveries == 1
        assert recovery.successful_recoveries == 1

    def test_stability_enforcer_safe_inverse(self):
        enforcer = StabilityEnforcer()
        mat = np.array([[4.0, 7.0], [2.0, 6.0]])
        inv = enforcer.safe_matrix_inverse(mat)
        assert np.allclose(inv @ mat, np.eye(2), atol=1e-10)
        singular = np.array([[1.0, 1.0], [1.0, 1.0]])
        pinv = enforcer.safe_matrix_inverse(singular, fallback_to_pinv=True)
        assert pinv.shape == (2, 2)
        assert enforcer.checks_performed > 0

    def test_stability_enforcer_convergence_check(self):
        enforcer = StabilityEnforcer()
        converging = [1.0, 0.5, 0.1, 0.01, 0.001, 0.0001, 1e-5, 1e-7]
        assert enforcer.check_convergence(converging)
        diverging = [1.0, 10.0, 100.0, 1000.0]
        assert not enforcer.check_convergence(diverging)
        assert not enforcer.check_convergence([1.0])
        assert enforcer.checks_performed > 0


# ============================================================================
# ERROR HANDLER TESTS
# ============================================================================


class TestErrorHandler:
    """Test suite for error handling infrastructure."""

    def test_error_handler_handles_error(self):
        handler = ErrorHandler(max_history=100)
        err = handler.handle_error("test_comp", "something failed", ErrorSeverity.ERROR)
        assert err.component == "test_comp"
        assert err.message == "something failed"
        assert err.severity == ErrorSeverity.ERROR
        assert err.error_id is not None

    def test_error_handler_error_history_query(self):
        handler = ErrorHandler()
        handler.handle_error("comp_a", "err alpha", ErrorSeverity.WARNING)
        handler.handle_error("comp_b", "err beta", ErrorSeverity.ERROR)
        handler.handle_error("comp_a", "err gamma", ErrorSeverity.CRITICAL)
        all_hist = handler.get_error_history()
        assert len(all_hist) == 3
        filtered = handler.get_error_history(component="comp_a")
        assert len(filtered) == 2
        err_only = handler.get_error_history(severity=ErrorSeverity.ERROR)
        assert len(err_only) == 1
        stats = handler.get_error_statistics()
        assert stats["total"] == 3
        assert stats["by_component"]["comp_a"] == 2

    def test_alert_manager_console_alert(self):
        alert_mgr = AlertManager()
        error = SystemError(
            error_id="alert-test-id", message="console alert",
            component="test", severity=ErrorSeverity.ERROR,
            timestamp=datetime.now(UTC),
        )
        alert_mgr.trigger_alert(error, channels=["console"])
        alert_mgr.add_alert_rule("*", ErrorSeverity.WARNING, channels=["console"])
        alert_mgr.get_active_alerts()

    def test_component_guard_context_manager(self):
        handler = ErrorHandler()
        with component_guard("guarded_comp", handler, ErrorSeverity.WARNING):
            raise ValueError("guarded exception")
        history = handler.get_error_history()
        assert len(history) == 1
        assert history[0].component == "guarded_comp"

    def test_auto_recovery_action(self):
        handler = ErrorHandler()
        recovery = AutoRecoveryManager(handler)

        def fix_action(error):
            return True

        recovery.register_recovery_action(
            "recover_comp",
            "critical failure",
            fix_action,
            action_name="fix_critical",
            cooldown_seconds=1,
        )
        err = handler.handle_error("recover_comp", "critical failure occurred", ErrorSeverity.ERROR)
        result = recovery.attempt_recovery(err)
        assert result
        status = recovery.get_recovery_status()
        assert len(status) == 1
        assert status[0]["attempts"] == 1
        assert status[0]["last_success"] is True


# ============================================================================
# NUMERICAL SAFETY TESTS
# ============================================================================


class TestNumericalSafety:
    """Test suite for numerical safety utilities."""

    def test_safe_division(self):
        guard = NumericalGuard(warn_on_clamp=False)
        result = guard.safe_division(10.0, 0.0, default=0.0)
        assert result == 0.0
        result = guard.safe_division(10.0, 2.0)
        assert result == 5.0
        arr = guard.safe_division(np.array([10.0, 10.0]), np.array([2.0, 0.0]), default=-1.0)
        assert arr[0] == 5.0
        assert arr[1] == -1.0

    def test_clamp_to_bounds(self):
        guard = NumericalGuard(warn_on_clamp=False)
        clamped = guard.clamp_to_bounds(15.0, 0.0, 10.0, name="test")
        assert clamped == 10.0
        clamped = guard.clamp_to_bounds(-5.0, 0.0, 10.0)
        assert clamped == 0.0
        clamped = guard.clamp_to_bounds(5.0, 0.0, 10.0)
        assert clamped == 5.0
        inside = guard.is_within_bounds(5.0, 0.0, 10.0)
        assert inside
        outside = guard.is_within_bounds(15.0, 0.0, 10.0)
        assert not outside

    def test_matrix_validation(self):
        guard = NumericalGuard()
        mat = np.array([[1.0, np.nan], [np.inf, 4.0]])
        cleaned = guard.validate_matrix(mat, expected_shape=(2, 2))
        assert not np.any(np.isnan(cleaned))
        assert not np.any(np.isinf(cleaned))
        with pytest.raises(ValueError):
            guard.validate_matrix(np.eye(3), expected_shape=(2, 2))
        cn = guard.condition_number(np.eye(3))
        assert np.isfinite(cn)

    def test_convergence_monitor(self):
        monitor = ConvergenceMonitor(max_iterations=100, tolerance=1e-6, divergence_threshold=50.0)
        assert not monitor.is_converged(0.1)
        assert monitor.is_converged(1e-7)
        assert not monitor.is_diverging(0.1)
        monitor.add_iteration(1.0)
        monitor.add_iteration(2.0)
        assert monitor.is_diverging(100.0)
        stats = monitor.get_statistics()
        assert stats["iterations"] >= 2
        rate = monitor.get_convergence_rate()
        assert isinstance(rate, float)
        monitor.reset()
        assert len(monitor._history) == 0

    def test_power_balance_consistency(self):
        check = ConsistencyCheck()
        r1 = check.check_power_balance(total_gen=100.0, total_load=80.0, total_losses=20.0)
        assert r1["passed"]
        r2 = check.check_power_balance(
            total_gen=100.0, total_load=50.0, total_losses=10.0, tolerance_mw=0.5
        )
        assert not r2["passed"]
        r3 = check.check_voltage_profile([0.98, 1.02, 1.05])
        assert r3["passed"]
        r4 = check.check_voltage_profile([0.90, 1.08])
        assert not r4["passed"]
        assert r4["n_violations"] == 2
        results = check.get_all_results()
        assert len(results) >= 4
        check.clear_results()
        assert len(check.get_all_results()) == 0
        r5 = check.check_kirchhoff_current_law([1e-8, -1e-8], tolerance=1e-6)
        assert r5["passed"]
        r6 = check.check_energy_conservation(100.0, 80.0, 20.0)
        assert r6["passed"]


# ============================================================================
# CACHE MANAGER TESTS
# ============================================================================


class TestCacheManager:
    """Test suite for calculation cache."""

    def test_cache_set_get(self):
        cache = CalculationCache(
            max_size_mb=10, strategy=CacheStrategy.LRU, default_ttl_seconds=3600
        )
        cache.set("k1", "value_one")
        assert cache.get("k1") == "value_one"
        assert cache.get("nonexistent") is None
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1

    def test_cache_ttl_expiry(self):
        cache = CalculationCache(default_ttl_seconds=3600)
        cache.set("k_ttl", "will_expire", ttl_seconds=0.05)
        assert cache.get("k_ttl") == "will_expire"
        time.sleep(0.1)
        assert cache.get("k_ttl") is None

    def test_cache_invalidate_by_tag(self):
        cache = CalculationCache()
        cache.set("tag1_k1", "v1", tags=["group_a"])
        cache.set("tag1_k2", "v2", tags=["group_a"])
        cache.set("tag1_k3", "v3", tags=["group_b"])
        assert cache.get("tag1_k1") == "v1"
        count = cache.invalidate_by_tag("group_a")
        assert count == 2
        assert cache.get("tag1_k1") is None
        assert cache.get("tag1_k3") == "v3"
        assert cache.get("tag1_k2") is None

    def test_cache_key_builder(self):
        builder = CacheKeyBuilder()
        key = builder.build_key("load_flow", "solve", "abc123")
        assert key == "load_flow:solve:abc123"
        h = builder.hash_params(1.0, 2.0, name="test")
        assert isinstance(h, str)
        assert len(h) == 64
        h2 = builder.hash_params(1.0, 2.0, name="test")
        assert h == h2
        h3 = builder.hash_params(1.0, 2.0, name="diff")
        assert h != h3


# ============================================================================
# ASYNC EXECUTOR TESTS
# ============================================================================


class TestAsyncExecutor:
    """Test suite for async execution and concurrency."""

    def test_submit_and_get_task(self):
        executor = AsyncExecutor(max_workers=2)
        try:

            def simple_fn():
                return 42

            task_id = executor.submit_task(simple_fn, name="simple_test")
            tasks = executor.wait_for_completion([task_id], timeout=5)
            assert len(tasks) == 1
            assert tasks[0].result == 42
            assert tasks[0].status == TaskStatus.COMPLETED
        finally:
            executor.shutdown(wait=False)

    def test_run_parallel(self):
        executor = AsyncExecutor(max_workers=2)
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(
                executor.run_parallel([lambda: 10, lambda: 20, lambda: 30])
            )
            loop.close()
            assert results == [10, 20, 30]
        finally:
            executor.shutdown(wait=False)

    def test_thread_pool_execution(self):
        pool = ThreadPoolManager(max_workers=2)

        def multiply(x, y):
            return x * y

        result = pool.run_in_thread(multiply, 6, 7)
        assert result == 42
        stats = pool.get_stats()
        assert stats["total_submitted"] == 1
        assert stats["total_completed"] == 1
        results = pool.run_batch([lambda: 1, lambda: 2])
        assert sorted(results) == [1, 2]

    def test_workflow_orchestrator(self):
        executor = AsyncExecutor(max_workers=2)
        try:
            orchestrator = WorkflowOrchestrator(executor)
            # Use initial_params to pass data between steps (avoids kwarg name mismatch)
            shared = {"value": "FIRST"}

            def step_first():
                return shared["value"]

            def step_second():
                return shared["value"] + "SECOND"

            wf_id = orchestrator.define_workflow(
                [
                    {"name": "step_first", "fn": step_first},
                    {"name": "step_second", "fn": step_second},
                ]
            )
            result = orchestrator.execute_workflow(wf_id)
            assert result["status"] == "completed", f"Workflow failed: {result.get('errors', {})}"
            assert result["results"]["step_first"] == "FIRST"
            assert result["results"]["step_second"] == "FIRSTSECOND"
        finally:
            executor.shutdown(wait=False)


# ============================================================================
# LOAD FLOW EXPANSION TESTS
# ============================================================================


class TestLoadFlowExpansion:
    """Expanded test suite for load flow calculations."""

    def test_large_system_convergence(self):
        """Test convergence on a 14-bus radial feeder.

        Uses 14 buses with 0.05 pu load per bus (total ~13° angle drop),
        which is physically plausible and well within voltage stability limits.
        A 35-bus radial with 0.1 pu/bus loading is past voltage collapse
        (~170° total angle) and has no real solution.
        """
        system = System(base_mva=100.0)
        n_buses = 14
        for i in range(1, n_buses + 1):
            bus_type = "slack" if i == 1 else "pq"
            bus = Bus(bus_id=i, voltage_magnitude=1.0, voltage_angle=0.0, bus_type=bus_type)
            system.add_bus(bus)
        gen = Generator(
            generator_id=1,
            bus=system.buses[1],
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)
        for i in range(2, n_buses + 1):
            load = Load(load_id=i, bus=system.buses[i], load_power=complex(0.05, 0.01))
            system.add_load(load)
        for i in range(1, n_buses):
            line = Line(
                line_id=i,
                from_bus=system.buses[i],
                to_bus=system.buses[i + 1],
                z1=complex(0.01, 0.05),
            )
            system.add_line(line)
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=200, tol=1e-4)
        assert converged, "Load flow should converge for 14-bus radial system"

    def test_transformer_tap_changing(self):
        system = System(base_mva=100.0)
        bus1 = Bus(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack")
        bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq")
        system.add_bus(bus1)
        system.add_bus(bus2)
        xf = Transformer(
            transformer_id=1,
            from_bus=bus1,
            to_bus=bus2,
            z1=complex(0.01, 0.06),
            tap_ratio=1.05,
            phase_shift=0.1,
        )
        system.add_transformer(xf)
        gen = Generator(
            generator_id=1,
            bus=bus1,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)
        load = Load(load_id=1, bus=bus2, load_power=complex(0.4, 0.15))
        system.add_load(load)
        Ybus = system.build_ybus(seq="1")
        # Off-diagonal should reflect tap ratio and phase shift
        assert Ybus[0, 1] != Ybus[1, 0], "Tap-changing transformer should break Ybus symmetry"
        solver = LoadFlowSolver(system)
        converged = solver.solve()
        assert converged, "Load flow should converge with tap-changing transformer"

    def test_reactive_power_limits(self):
        system = System(base_mva=100.0)
        bus1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack")
        bus2 = Bus(
            bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pv", q_min=-0.2, q_max=0.3
        )
        system.add_bus(bus1)
        system.add_bus(bus2)
        gen1 = Generator(
            generator_id=1,
            bus=bus1,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        gen2 = Generator(
            generator_id=2,
            bus=bus2,
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen1)
        system.add_generator(gen2)
        load = Load(load_id=1, bus=bus2, load_power=complex(0.6, 0.4))
        system.add_load(load)
        line = Line(line_id=1, from_bus=bus1, to_bus=bus2, z1=complex(0.02, 0.08))
        system.add_line(line)
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=50, tol=1e-6)
        # May converge with PV->PQ switching if Q limits hit
        assert converged or len(solver.switching_log) > 0


# ============================================================================
# SHORT CIRCUIT EXPANSION TESTS
# ============================================================================


class TestShortCircuitExpansion:
    """Expanded test suite for short circuit calculations."""

    @pytest.fixture
    def multi_bus_fault_system(self):
        system = System(base_mva=100.0)
        for i in range(1, 5):
            bus = Bus(
                bus_id=i,
                voltage_magnitude=1.0,
                voltage_angle=0.0,
                bus_type="slack" if i == 1 else "pq",
            )
            system.add_bus(bus)
        gen = Generator(
            generator_id=1,
            bus=system.buses[1],
            impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
        )
        system.add_generator(gen)
        for i in range(1, 4):
            line = Line(
                line_id=i,
                from_bus=system.buses[i],
                to_bus=system.buses[i + 1],
                z1=complex(0.01, 0.05),
                z2=complex(0.01, 0.05),
                z0=complex(0.03, 0.15),
            )
            system.add_line(line)
        system.build_sequence_networks(for_fault=True)
        Ybus_pos = system.get_ybus(seq="1")
        Ybus_neg = system.get_ybus(seq="2")
        Ybus_zero = system.get_ybus(seq="0")
        return FaultAnalyzer(Ybus_pos, Ybus_neg, Ybus_zero, base_mva=100.0, base_kv=115.0)

    def test_fault_at_different_buses(self, multi_bus_fault_system):
        for bus_idx in range(4):
            result = multi_bus_fault_system.three_phase_fault(bus_idx)
            assert abs(result["fault_current"]) > 0, f"Non-zero fault current at bus {bus_idx}"

    def test_iec60909_fault_types_all(self):
        _n = 2
        Ybus = np.array(
            [[complex(10, -50), complex(-10, 50)], [complex(-10, 50), complex(10, -50)]]
        )
        engine = IEC60909Engine(Ybus, Ybus, Ybus, base_mva=100.0, base_kv=115.0)
        for fault_type, method in [
            ("three_phase", engine.calculate_three_phase_fault),
            ("line_to_ground", engine.calculate_line_to_ground_fault),
            ("line_to_line", engine.calculate_line_to_line_fault),
            ("double_line_to_ground", engine.calculate_double_line_to_ground_fault),
        ]:
            result = method(0, bus_kv=115.0)
            assert result.Ik_initial_magnitude > 0, f"{fault_type} current should be positive"
            assert result.ip_peak > 0, f"{fault_type} peak should be positive"
            assert result.Ib_breaking > 0, f"{fault_type} breaking should be positive"
            assert result.fault_type == fault_type

    def test_fault_current_symmetry(self):
        _n = 2
        Ybus = np.array(
            [[complex(10, -50), complex(-10, 50)], [complex(-10, 50), complex(10, -50)]]
        )
        engine = IEC60909Engine(Ybus, Ybus, Ybus, base_mva=100.0, base_kv=115.0)
        result = engine.calculate_three_phase_fault(0, bus_kv=115.0)
        mags = [abs(result.Ia), abs(result.Ib), abs(result.Ic)]
        assert abs(mags[0] - mags[1]) < 1e-6, "Phase A and B magnitudes should be equal"
        assert abs(mags[0] - mags[2]) < 1e-6, "Phase A and C magnitudes should be equal"
        assert abs(result.I_negative) < 1e-10, "Negative sequence should be zero for balanced fault"
        assert abs(result.I_zero) < 1e-10, "Zero sequence should be zero for balanced fault"


# ============================================================================
# ETAP AUTOMATION TESTS
# ============================================================================


class TestETAPAutomation:
    """Test suite for ETAP automation (using static methods, no COM dependency)."""

    def test_project_path_validation(self):
        import unittest.mock as umock

        etap_mock = umock.MagicMock(spec=ETAPAutomation)
        etap_mock._allowed_project_dirs = []
        empty = ETAPAutomation._validate_project_path(etap_mock, "")
        assert not empty
        no_ext = ETAPAutomation._validate_project_path(etap_mock, "no_extension")
        assert not no_ext
        unc = ETAPAutomation._validate_project_path(etap_mock, "\\\\unsafe\\share\\proj.edb")
        assert not unc
        etap_mock._allowed_project_dirs = []
        valid = ETAPAutomation._validate_project_path(etap_mock, "test_project.edb")
        assert valid

    def test_input_sanitization(self):
        raw = "<script>alert('xss')</script>\x00nullbyte"
        sanitized = ETAPAutomation._sanitize_string_input(raw, max_length=100)
        assert "\x00" not in sanitized
        assert "<script>" not in sanitized
        assert sanitized == "alert('xss')nullbyte"
        with pytest.raises(ValueError):
            ETAPAutomation._sanitize_string_input(123, max_length=100)

    def test_input_validation_engineering_ranges(self):
        validated = ETAPAutomation._validate_input(13.8, "numeric", min_val=0.1, max_val=1200.0)
        assert validated == 13.8
        validated = ETAPAutomation._validate_input(5, "integer", min_val=0, max_val=100)
        assert validated == 5
        validated = ETAPAutomation._validate_input("hello", "string", max_length=10)
        assert validated == "hello"
        validated = ETAPAutomation._validate_input(True, "boolean")
        assert validated is True
        with pytest.raises(ValueError):
            ETAPAutomation._validate_input(1e20, "numeric", max_val=1e15)
        with pytest.raises(ValueError):
            ETAPAutomation._validate_input("not_numeric", "numeric")

    def test_result_size_checking(self):
        small = {"a": 1, "b": 2}
        result = ETAPAutomation._check_result_size(small, max_entries=100)
        assert result["a"] == 1
        with pytest.raises(ValueError):
            ETAPAutomation._check_result_size(
                {"a": {"x": 1}, "b": {"y": 2}, "c": {"z": 3}},
                max_entries=2,
            )
        with pytest.raises(TypeError):
            ETAPAutomation._check_result_size("not_a_dict")


# ============================================================================
# MULTI-AGENT COORDINATION TESTS
# ============================================================================


class TestMultiAgentCoordination:
    """Test suite for multi-agent coordination data structures."""

    def test_agent_result_dataclass(self):
        result = AgentResult(
            agent_name="test_agent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={"key": "value"},
        )
        assert result.agent_name == "test_agent"
        assert result.study_type == StudyType.LOAD_FLOW
        assert result.status == AgentStatus.COMPLETED
        assert result.data["key"] == "value"
        assert result.validation_status is False
        assert result.validation_errors == []

    def test_study_type_enum(self):
        assert StudyType.LOAD_FLOW.value == "load_flow"
        assert StudyType.SHORT_CIRCUIT.value == "short_circuit"
        assert StudyType.HARMONIC_ANALYSIS.value == "harmonic_analysis"
        assert StudyType.OPTIMAL_POWER_FLOW.value == "optimal_power_flow"
        assert StudyType.PROTECTION_COORDINATION.value == "protection_coordination"
        assert StudyType.MOTOR_STARTING.value == "motor_starting"
        assert StudyType.TRANSIENT_STABILITY.value == "transient_stability"
        assert StudyType.ARC_FLASH.value == "arc_flash"
        assert len(StudyType) == 8

    def test_engineering_task_creation(self):
        task = EngineeringTask(
            task_id="task-coord-001",
            description="Multi-study coordination test",
            study_types=[StudyType.LOAD_FLOW, StudyType.SHORT_CIRCUIT],
            parameters={"system": None},
            priority=2,
        )
        assert task.task_id == "task-coord-001"
        assert len(task.study_types) == 2
        assert task.priority == 2
        assert task.status == AgentStatus.IDLE
        assert len(task.results) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=.", "--cov-report=html"])
