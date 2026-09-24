"""
Deep Tests for StudyExecutor - services/study_executor.py

Covers:
- System building from SystemSpec, dict, or System instance
- Spec validation errors (unknown bus references)
- Pre-flight and feature flag validation
- End-to-end execute() for arc_flash, load_flow, short_circuit, etap_expert
- Aliases mapping (_NATIVE_ALIASES)
- Serialization helpers (_to_jsonable)
- Post-execution checks (risk scoring)
"""

from __future__ import annotations

import numpy as np
import pytest

from core_model.bus import Bus
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
from core_model.system import System
from services.study_executor import _NATIVE_ALIASES, _TYPES_REQUIRING_SYSTEM, StudyExecutor


@pytest.fixture(name="executor")
def fixture_executor():
    return StudyExecutor(cache=None)


@pytest.fixture(name="sample_spec")
def fixture_sample_spec():
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


class TestSystemBuilding:
    def test_build_system_from_spec(self, executor, sample_spec):
        system = executor._build_system_from_spec(sample_spec)
        assert isinstance(system, System)
        assert len(system.buses) == 3
        assert len(system.lines) == 2
        assert len(system.transformers) == 1
        assert len(system.generators) == 1
        assert len(system.loads) == 1

    def test_build_system_from_system_instance_returns_self(self, executor):
        sys = System()
        assert executor._build_system_from_spec(sys) is sys

    def test_build_system_from_dict(self, executor, sample_spec):
        spec_dict = sample_spec.model_dump()
        system = executor._build_system_from_spec(spec_dict)
        assert isinstance(system, System)
        assert len(system.buses) == 3

    def test_line_unknown_bus_raises(self, executor):
        bad_spec = SystemSpec(
            base_mva=100.0,
            buses=[BusSpec(bus_id=1, base_kv=11.0)],
            lines=[LineSpec(line_id=1, from_bus_id=1, to_bus_id=99, r1=0.01, x1=0.05)],
        )
        with pytest.raises(ValueError, match="Line 1 references unknown bus"):
            executor._build_system_from_spec(bad_spec)

    def test_transformer_unknown_bus_raises(self, executor):
        bad_spec = SystemSpec(
            base_mva=100.0,
            buses=[BusSpec(bus_id=1, base_kv=11.0)],
            transformers=[
                TransformerSpec(transformer_id=1, from_bus_id=1, to_bus_id=99, r1=0.01, x1=0.05)
            ],
        )
        with pytest.raises(ValueError, match="Transformer 1 references unknown bus"):
            executor._build_system_from_spec(bad_spec)

    def test_generator_unknown_bus_raises(self, executor):
        bad_spec = SystemSpec(
            base_mva=100.0,
            buses=[BusSpec(bus_id=1, base_kv=11.0)],
            generators=[GeneratorSpec(generator_id=1, bus_id=99, r1=0.01, x1=0.05)],
        )
        with pytest.raises(ValueError, match="Generator 1 references unknown bus"):
            executor._build_system_from_spec(bad_spec)

    def test_load_unknown_bus_raises(self, executor):
        bad_spec = SystemSpec(
            base_mva=100.0,
            buses=[BusSpec(bus_id=1, base_kv=11.0)],
            loads=[LoadSpec(load_id=1, bus_id=99, p_mw=10.0, q_mvar=5.0)],
        )
        with pytest.raises(ValueError, match="Load 1 references unknown bus"):
            executor._build_system_from_spec(bad_spec)


class TestRequestValidation:
    def test_system_required_for_load_flow(self, executor):
        req = StudyRequest(study_type="load_flow", system=None)
        with pytest.raises(ValueError, match="System configuration is required"):
            executor._validate_request(req)

    def test_arc_flash_does_not_require_system(self, executor):
        req = StudyRequest(
            study_type="arc_flash",
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_sec": 0.1,
                "working_distance_mm": 457.0,
            },
        )
        executor._validate_request(req)  # Should not raise


class TestExecutionPipeline:
    @pytest.mark.asyncio
    async def test_execute_arc_flash(self, executor):
        req = StudyRequest(
            study_type="arc_flash",
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_sec": 0.1,
                "working_distance_mm": 457.0,
            },
        )
        res = await executor.execute(req)
        assert isinstance(res, StudyResult)
        assert res.success is True
        assert res.study_type == "arc_flash"
        # IEEE 1584-2018 Clause 4.11 & 4.12: Physical incident energy and boundary limits
        energy = res.data.get("incident_energy_cal_per_cm2", 0)
        afb = res.data.get("arc_flash_boundary_mm", 0)
        assert 0.0005 <= energy <= 100.0, f"Incident energy {energy} out of IEEE 1584 bounds"
        assert 0.1 <= afb <= 10000.0, f"Arc flash boundary {afb} mm out of physical bounds"

    @pytest.mark.asyncio
    async def test_execute_load_flow(self, executor, sample_spec):
        req = StudyRequest(
            study_type="load_flow",
            system=sample_spec,
        )
        res = await executor.execute(req)
        assert isinstance(res, StudyResult)
        assert res.success is True
        assert res.data.get("converged") is True
        # IEEE 3002.7 & ANSI C84.1: Bus voltage magnitudes must lie in 0.90 - 1.10 pu range
        voltages = res.data.get("voltages", {})
        for bus_id, v in voltages.items():
            vmag = abs(complex(v["re"], v["im"])) if isinstance(v, dict) else abs(v)
            assert 0.90 <= vmag <= 1.10, f"Bus {bus_id} voltage {vmag} outside IEEE 3002.7 limits"

    @pytest.mark.asyncio
    async def test_execute_short_circuit(self, executor, sample_spec):
        req = StudyRequest(
            study_type="short_circuit",
            system=sample_spec,
            parameters={"bus_id": 2, "fault_type": "three_phase"},
        )
        res = await executor.execute(req)
        assert isinstance(res, StudyResult)
        assert res.success is True
        ik = res.data.get("fault_current_ka") or res.data.get("fault_current_magnitude")
        assert ik >= 0.1, f"Fault current {ik} outside IEC 60909 prospective range"
        assert ik <= 500.0, f"Fault current {ik} outside IEC 60909 prospective range"

    @pytest.mark.asyncio
    async def test_execute_etap_expert(self, executor):
        req = StudyRequest(
            study_type="etap_expert",
            parameters={"question": "What is IEEE 1584 standard for arc flash?"},
        )
        res = await executor.execute(req)
        assert isinstance(res, StudyResult)
        assert res.success is True
        assert len(res.data) > 0

    @pytest.mark.asyncio
    async def test_execute_etap_expert_missing_question_raises(self, executor):
        req = StudyRequest(
            study_type="etap_expert",
            parameters={"question": ""},
        )
        with pytest.raises(ValueError, match="'question' field is required"):
            await executor.execute(req)


class TestJsonSerialization:
    def test_to_jsonable_complex(self, executor):
        val = complex(3.0, 4.0)
        res = executor._to_jsonable(val)
        assert res == {"re": 3.0, "im": 4.0}

    def test_to_jsonable_numpy(self, executor):
        arr = np.array([1.0, 2.0, 3.0])
        res = executor._to_jsonable(arr)
        assert res == [1.0, 2.0, 3.0]

    def test_to_jsonable_nested(self, executor):
        data = {"v": complex(1.0, -2.0), "arr": np.array([5])}
        res = executor._to_jsonable(data)
        assert res == {"v": {"re": 1.0, "im": -2.0}, "arr": [5]}


class TestPreFlightChecks:
    def test_pre_flight_basic_validations(self, executor):
        # Missing system
        assert "System configuration is required" in executor._pre_flight_basic({})["error"]
        # No buses
        assert "must have at least one bus" in executor._pre_flight_basic({"buses": []})["error"]
        # No lines
        assert (
            "must have at least one line"
            in executor._pre_flight_basic({"buses": [{"bus_id": 1}], "lines": []})["error"]
        )
        # Invalid base_mva
        assert (
            "base_mva must be > 0"
            in executor._pre_flight_basic(
                {"buses": [{"bus_id": 1}], "lines": [{"line_id": 1}], "base_mva": 0}
            )["error"]
        )

    def test_pre_flight_lines_impedance_and_bus_lookup(self, executor):
        # Zero / negative impedance
        lines = [{"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0, "x1": 0}]
        assert "zero/negative impedance" in executor._pre_flight_lines(lines, {1, 2})["error"]

        # Unknown from_bus
        lines = [{"line_id": 1, "from_bus_id": 99, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}]
        assert "references unknown from_bus" in executor._pre_flight_lines(lines, {1, 2})["error"]

        # Unknown to_bus
        lines = [{"line_id": 1, "from_bus_id": 1, "to_bus_id": 99, "r1": 0.01, "x1": 0.05}]
        assert "references unknown to_bus" in executor._pre_flight_lines(lines, {1, 2})["error"]

    def test_pre_flight_voltage_bounds(self, executor):
        # Out of bounds low voltage
        buses = [{"bus_id": 1, "voltage_magnitude": 0.005}]
        assert "out of realistic range" in executor._pre_flight_voltage_bounds(buses)["error"]

        # Out of bounds high voltage
        buses = [{"bus_id": 1, "voltage_magnitude": 1.6}]
        assert "out of realistic range" in executor._pre_flight_voltage_bounds(buses)["error"]

        # In bounds voltage
        buses = [{"bus_id": 1, "voltage_magnitude": 1.02}]
        assert executor._pre_flight_voltage_bounds(buses) is None


class TestETAPGUIAndFailureScan:
    @pytest.mark.asyncio
    async def test_execute_etap_gui(self, executor):
        req = StudyRequest(
            study_type="etap_gui",
            parameters={"question": "How do I run load flow in ETAP?"},
        )
        res = await executor.execute(req)
        assert isinstance(res, StudyResult)
        assert res.success is True

    @pytest.mark.asyncio
    async def test_execute_etap_gui_missing_question_raises(self, executor):
        req = StudyRequest(
            study_type="etap_gui",
            parameters={"question": "   "},
        )
        with pytest.raises(ValueError, match="'question' field is required"):
            await executor.execute(req)

    def test_scan_ai_failure_modes(self, executor):
        # Small payload should return empty list without error
        res = executor._scan_ai_failure_modes({"test": 123}, "load_flow")
        assert isinstance(res, list)


class TestDenyByDefaultValidationGate:
    """RC-1 regression tests — deny-by-default for unregistered study types.

    StudyRequest's Pydantic validator (_ALLOWED_STUDY_TYPES) already rejects
    completely unknown strings.  The RC-1 guard in _validate_request() provides a
    SECOND layer: it rejects study_types that pass Pydantic's allowed list but are
    NOT registered in STUDY_DISPATCH or _NATIVE_ALIASES.  This prevents types like
    'etap_load_flow' (which pass Pydantic) from silently passing validation in
    dev/test because is_feature_enabled() forces True for any key string.

    Ref: services/study_executor.py::StudyExecutor._validate_request (RC-1)
    """

    def test_unregistered_etap_type_raises_deny_by_default(self, executor):
        """'etap_load_flow' passes Pydantic (_ALLOWED_STUDY_TYPES) but is NOT in
        STUDY_DISPATCH or _NATIVE_ALIASES, so _validate_request must deny it.
        This validates the RC-1 guard fires before is_feature_enabled().
        """
        req = StudyRequest(study_type="etap_load_flow", parameters={})
        with pytest.raises(ValueError, match="deny-by-default"):
            executor._validate_request(req)

    def test_unregistered_etap_type_error_mentions_unknown(self, executor):
        """Error message must include 'Unknown study_type' for rejected types."""
        req = StudyRequest(study_type="etap_short_circuit", parameters={})
        with pytest.raises(ValueError, match="Unknown study_type"):
            executor._validate_request(req)

    def test_alias_fault_passes_deny_by_default_guard(self, executor):
        """'fault' is a valid alias for 'short_circuit' in _NATIVE_ALIASES.
        The RC-1 guard must NOT reject it — aliases are in _known_study_types.
        _validate_request passes it through cleanly; alias resolution to
        'short_circuit' happens later in _dispatch().  _TYPES_REQUIRING_SYSTEM
        also uses canonical names ('short_circuit'), not aliases ('fault'),
        so no system-required error fires here either.
        """
        req = StudyRequest(study_type="fault", parameters={})
        # Must NOT raise — fault is a registered alias, passes all _validate_request gates
        executor._validate_request(req)  # no exception expected

    def test_known_disabled_flag_harmonic_analysis_follows_feature_flag_path(self, executor):
        """harmonic_analysis is REGISTERED (in STUDY_DISPATCH) and DISABLED by flag.
        It should raise the 'disabled in production' error, NOT the deny-by-default error.
        This confirms the deny-by-default guard does not swallow known-disabled studies.
        """
        import os

        # Force production env so is_feature_enabled() reads flags (not dev bypass)
        original_env = os.environ.get("ENV")
        original_app_env = os.environ.get("APP_ENV")
        try:
            os.environ["ENV"] = "production"
            os.environ.pop("APP_ENV", None)
            req = StudyRequest(study_type="harmonic_analysis", system=None)
            with pytest.raises(ValueError, match="disabled in production"):
                executor._validate_request(req)
        finally:
            # Restore original env
            if original_env is not None:
                os.environ["ENV"] = original_env
            else:
                os.environ.pop("ENV", None)
            if original_app_env is not None:
                os.environ["APP_ENV"] = original_app_env

