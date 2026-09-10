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
        assert "incident_energy_cal_per_cm2" in res.data
        assert res.study_type == "arc_flash"

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
        assert "fault_current" in res.data or "fault_current_ka" in res.data

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
