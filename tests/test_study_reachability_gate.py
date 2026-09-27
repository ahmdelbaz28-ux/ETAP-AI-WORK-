"""
tests/test_study_reachability_gate.py — Behavioral Safety and Reachability Gate Tests (Package P2).

Acceptance Gates Covered:
1. All 20 entries in STUDY_DISPATCH: either execute successfully or raise
   SpecializedExecutionUnavailableError with code == "SPECIALIZED_EXECUTION_UNAVAILABLE".
   Zero generic or unhandled ValueError exceptions allowed.
2. Dual-port parity: study_executor and study_service (and engine shim) behave
   consistently and deterministically on non-native studies by raising the unified error.
3. Native study preservation: the 4 native studies (load_flow, short_circuit,
   arc_flash, protection_coordination) execute cleanly without regressions.
4. Unregistered/bogus study types raise generic ValueError (preserving distinction
   between registered unreachable vs unrecognized types).
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import (
    BusSpec,
    GeneratorSpec,
    LineSpec,
    LoadSpec,
    StudyRequest,
    StudyResult,
    SystemSpec,
    TransformerSpec,
)
from engine.dispatch import STUDY_DISPATCH
from engine.engine import PowerSystemEngine
from services.study_executor import StudyExecutor
from services.study_service import _run_native_study


@pytest.fixture(name="sample_system_spec")
def fixture_sample_system_spec() -> SystemSpec:
    return SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(
                bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack", base_kv=11.0
            ),
            BusSpec(
                bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0
            ),
            BusSpec(
                bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0
            ),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.08, bshunt1=0.0),
        ],
        transformers=[
            TransformerSpec(
                transformer_id=1,
                from_bus_id=1,
                to_bus_id=2,
                r1=0.02,
                x1=0.1,
                tap_ratio=1.0,
                phase_shift_deg=0.0,
            ),
        ],
        generators=[
            GeneratorSpec(generator_id=1, bus_id=1, r1=0.01, x1=0.1, internal_voltage_mag=1.05),
        ],
        loads=[
            LoadSpec(load_id=1, bus_id=3, p_mw=20.0, q_mvar=10.0, constant_impedance=False),
        ],
    )


@pytest.fixture(name="built_system")
def fixture_built_system(sample_system_spec: SystemSpec):
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(sample_system_spec)


DEFAULT_PARAMS: dict[str, dict] = {
    "load_flow": {},
    "short_circuit": {"bus_id": 2, "fault_type": "three_phase"},
    "arc_flash": {
        "voltage_kv": 0.48,
        "bolted_fault_current_ka": 20.0,
        "arc_duration_sec": 0.1,
        "working_distance_mm": 457.0,
    },
    "protection_coordination": {
        "upstream_relay_id": 1,
        "downstream_relay_id": 2,
        "fault_currents": [2.0, 5.0, 10.0, 20.0],
    },
    "etap_expert": {"question": "What is IEEE 1584 standard for arc flash?"},
    "etap_gui": {"question": "How to create a bus in ETAP?"},
}


class TestStudyReachabilityGate:
    """Gate 1: Verify all 20 entries in STUDY_DISPATCH either execute or raise unified error."""

    def test_study_dispatch_has_exactly_20_entries(self):
        assert len(STUDY_DISPATCH) == 20, f"Expected 20 entries in STUDY_DISPATCH, found {len(STUDY_DISPATCH)}"

    @pytest.mark.asyncio
    async def test_all_20_study_dispatch_entries_reachability_in_study_executor(self, built_system):
        executor = StudyExecutor(cache=None)
        executed_count = 0
        specialized_unavailable_count = 0

        for study_type, reg in STUDY_DISPATCH.items():
            params = DEFAULT_PARAMS.get(study_type, {})
            try:
                res = executor._dispatch(study_type, built_system, params)
                assert isinstance(res, dict), f"Study {study_type} must return dict on execution"
                executed_count += 1
            except SpecializedExecutionUnavailableError as exc:
                assert exc.code == "SPECIALIZED_EXECUTION_UNAVAILABLE", (
                    f"Study {study_type} raised error with invalid code: {exc.code}"
                )
                assert exc.study_type == study_type
                assert isinstance(exc, ValueError), "SpecializedExecutionUnavailableError must inherit from ValueError"
                specialized_unavailable_count += 1
            except Exception as exc:
                pytest.fail(
                    f"Study '{study_type}' raised unhandled exception {type(exc).__name__}: {exc}. "
                    "Expected either successful execution or SpecializedExecutionUnavailableError."
                )

        assert executed_count + specialized_unavailable_count == 20
        # 4 native + 2 expert/gui agents = at least 6 executed
        assert executed_count >= 6
        assert specialized_unavailable_count <= 14

    @pytest.mark.asyncio
    async def test_full_pipeline_execute_for_all_registered_studies(self, sample_system_spec):
        """Test public execute() method for reachability."""
        executor = StudyExecutor(cache=None)

        for study_type in STUDY_DISPATCH:
            params = DEFAULT_PARAMS.get(study_type, {})
            try:
                req = StudyRequest(
                    study_type=study_type,
                    system=sample_system_spec if STUDY_DISPATCH[study_type].requires_system else None,
                    parameters=params,
                )
            except Exception:
                # StudyRequest schema restricts study_type enum to a subset; tested via _dispatch
                continue
            try:
                result = await executor.execute(req)
                assert isinstance(result, StudyResult)
                assert result.success is True
            except SpecializedExecutionUnavailableError as exc:
                assert exc.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
                assert exc.study_type == study_type
            except Exception as exc:
                pytest.fail(
                    f"Full pipeline execute for study '{study_type}' raised unexpected {type(exc).__name__}: {exc}"
                )


class TestDualPortParity:
    """Gate 2: Verify parity between study_executor and study_service (and engine shim)."""

    @pytest.mark.parametrize(
        "study_type",
        [
            "harmonic_analysis",
            "optimal_power_flow",
            "motor_starting",
            "transient_stability",
            "cable_sizing",
            "earth_grid",
            "renewable_integration",
            "battery_storage",
            "scada",
            "digital_twin",
            "generative_design",
            "optimization",
        ],
    )
    def test_non_native_studies_parity_across_ports(self, built_system, study_type: str):
        executor = StudyExecutor(cache=None)

        # Port 1: study_executor._dispatch
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_info_executor:
            executor._dispatch(study_type, built_system, {})
        assert exc_info_executor.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_info_executor.value.study_type == study_type

        # Port 2: study_service._run_native_study
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_info_service:
            _run_native_study(study_type, built_system, {})
        assert exc_info_service.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_info_service.value.study_type == study_type

        # Engine shim: PowerSystemEngine.run_study
        engine = PowerSystemEngine(built_system)
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_info_engine:
            engine.run_study(study_type)
        assert exc_info_engine.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_info_engine.value.study_type == study_type


class TestNativeFourStudiesPreservation:
    """Gate 3: Ensure the 4 native studies remain fully functional across all layers."""

    @pytest.mark.asyncio
    async def test_native_load_flow(self, built_system, sample_system_spec):
        executor = StudyExecutor(cache=None)
        res_executor = executor._dispatch("load_flow", built_system, {})
        assert res_executor.get("converged") is True

        res_service = _run_native_study("load_flow", built_system, {})
        assert res_service.get("converged") is True

        engine = PowerSystemEngine(built_system)
        res_engine = engine.run_study("load_flow")
        assert res_engine.get("converged") is True

    @pytest.mark.asyncio
    async def test_native_short_circuit(self, built_system):
        executor = StudyExecutor(cache=None)
        params = {"bus_id": 2, "fault_type": "three_phase"}
        res_executor = executor._dispatch("short_circuit", built_system, params)
        assert "fault_current_ka" in res_executor or "fault_current_magnitude" in res_executor

        res_service = _run_native_study("short_circuit", built_system, params)
        assert "fault_current_ka" in res_service or "fault_current_magnitude" in res_service

        engine = PowerSystemEngine(built_system)
        res_engine = engine.run_study("short_circuit", bus_id=2, fault_type="three_phase")
        assert "fault_current_ka" in res_engine or "fault_current_magnitude" in res_engine

    @pytest.mark.asyncio
    async def test_native_arc_flash(self, built_system):
        params = {
            "voltage_kv": 0.48,
            "bolted_fault_current_ka": 20.0,
            "arc_duration_sec": 0.1,
            "working_distance_mm": 457.0,
        }
        executor = StudyExecutor(cache=None)
        res_executor = executor._dispatch("arc_flash", built_system, params)
        assert "incident_energy_cal_per_cm2" in res_executor

        res_service = _run_native_study("arc_flash", built_system, params)
        assert "incident_energy_cal_per_cm2" in res_service

        engine = PowerSystemEngine(built_system)
        res_engine = engine.run_study("arc_flash", **params)
        assert "incident_energy_cal_per_cm2" in res_engine

    @pytest.mark.asyncio
    async def test_native_protection_coordination(self, built_system):
        params = {
            "upstream_relay_id": 1,
            "downstream_relay_id": 2,
            "fault_currents": [2.0, 5.0, 10.0, 20.0],
        }
        executor = StudyExecutor(cache=None)
        res_executor = executor._dispatch("protection_coordination", built_system, params)
        assert isinstance(res_executor, dict)

        res_service = _run_native_study("protection_coordination", built_system, params)
        assert isinstance(res_service, dict)

        engine = PowerSystemEngine(built_system)
        res_engine = engine.run_study("protection_coordination", **params)
        assert isinstance(res_engine, dict)


class TestUnregisteredAndSpecialStudies:
    """Gate 4: Unregistered study types and special feature flags behavior."""

    def test_unregistered_study_raises_generic_value_error(self, built_system):
        """Unregistered study types must raise generic ValueError, not SpecializedExecutionUnavailableError."""
        executor = StudyExecutor(cache=None)
        with pytest.raises(ValueError) as exc:
            executor._dispatch("bogus_unregistered_study", built_system, {})
        assert not isinstance(exc.value, SpecializedExecutionUnavailableError)
        assert "Unsupported native study type" in str(exc.value)

        engine = PowerSystemEngine(built_system)
        with pytest.raises(ValueError) as exc_engine:
            engine.run_study("bogus_unregistered_study")
        assert not isinstance(exc_engine.value, SpecializedExecutionUnavailableError)
        assert str(exc_engine.value) == "Unsupported study type: bogus_unregistered_study"

    def test_breaker_duty_flag_disabled_raises_unified_error(self, built_system, monkeypatch):
        monkeypatch.setenv("FEATURE_FLAG_BREAKER_DUTY", "false")
        executor = StudyExecutor(cache=None)
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
            executor._dispatch("breaker_duty", built_system, {})
        assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_info.value.study_type == "breaker_duty"
        assert "disabled by feature flag" in str(exc_info.value)
