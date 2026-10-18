"""Regression tests for Defect 2: Fail-Closed Topology Validation.

Verifies that study_service._build_system_from_spec and study_executor._build_system_from_spec
strictly REJECT network models with missing/dangling bus references and NEVER synthesize
default PQ or PV buses.
"""

from __future__ import annotations

import pytest

from core_model.specs import (
    BusSpec,
    GeneratorSpec,
    LineSpec,
    LoadSpec,
    SystemSpec,
    TransformerSpec,
)
from services.study_executor import StudyExecutor
from services.study_service import _build_system_from_spec as service_build_system


@pytest.fixture
def valid_bus_spec() -> BusSpec:
    return BusSpec(bus_id=1, base_kv=132.0, bus_type="slack")


class TestFailClosedTopologyRejection:
    """Verifies that both builders reject dangling bus references and never synthesize default buses."""

    def test_line_dangling_from_bus_rejected_by_service_and_executor(self, valid_bus_spec):
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec],
            lines=[LineSpec(line_id=101, from_bus_id=999, to_bus_id=1, r1=0.01, x1=0.05)],
        )
        # Test study_service builder
        with pytest.raises(ValueError) as exc_service:
            service_build_system(spec)
        assert "Line 101 references unknown bus 999" in str(exc_service.value)

        # Test study_executor builder
        executor = StudyExecutor()
        with pytest.raises(ValueError) as exc_exec:
            executor._build_system_from_spec(spec)
        assert "Line 101 references unknown bus 999" in str(exc_exec.value)

    def test_line_dangling_to_bus_rejected_by_service_and_executor(self, valid_bus_spec):
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec],
            lines=[LineSpec(line_id=102, from_bus_id=1, to_bus_id=888, r1=0.01, x1=0.05)],
        )
        with pytest.raises(ValueError) as exc_service:
            service_build_system(spec)
        assert "Line 102 references unknown bus 888" in str(exc_service.value)

        executor = StudyExecutor()
        with pytest.raises(ValueError) as exc_exec:
            executor._build_system_from_spec(spec)
        assert "Line 102 references unknown bus 888" in str(exc_exec.value)

    def test_transformer_dangling_bus_rejected(self, valid_bus_spec):
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec],
            transformers=[
                TransformerSpec(
                    transformer_id=201, from_bus_id=1, to_bus_id=777, r1=0.01, x1=0.08
                )
            ],
        )
        with pytest.raises(ValueError) as exc_service:
            service_build_system(spec)
        assert "Transformer 201 references unknown bus 777" in str(exc_service.value)

        executor = StudyExecutor()
        with pytest.raises(ValueError) as exc_exec:
            executor._build_system_from_spec(spec)
        assert "Transformer 201 references unknown bus 777" in str(exc_exec.value)

    def test_generator_dangling_bus_rejected(self, valid_bus_spec):
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec],
            generators=[
                GeneratorSpec(
                    generator_id=301, bus_id=666, r1=0.02, x1=0.15, internal_voltage_mag=1.02
                )
            ],
        )
        with pytest.raises(ValueError) as exc_service:
            service_build_system(spec)
        assert "Generator 301 references unknown bus 666" in str(exc_service.value)

        executor = StudyExecutor()
        with pytest.raises(ValueError) as exc_exec:
            executor._build_system_from_spec(spec)
        assert "Generator 301 references unknown bus 666" in str(exc_exec.value)

    def test_load_dangling_bus_rejected(self, valid_bus_spec):
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec],
            loads=[LoadSpec(load_id=401, bus_id=555, p_mw=25.0, q_mvar=10.0)],
        )
        with pytest.raises(ValueError) as exc_service:
            service_build_system(spec)
        assert "Load 401 references unknown bus 555" in str(exc_service.value)

        executor = StudyExecutor()
        with pytest.raises(ValueError) as exc_exec:
            executor._build_system_from_spec(spec)
        assert "Load 401 references unknown bus 555" in str(exc_exec.value)

    def test_complete_valid_spec_builds_without_error(self, valid_bus_spec):
        b2 = BusSpec(bus_id=2, base_kv=132.0, bus_type="pq")
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec, b2],
            lines=[LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05)],
            generators=[GeneratorSpec(generator_id=1, bus_id=1, r1=0.01, x1=0.1)],
            loads=[LoadSpec(load_id=1, bus_id=2, p_mw=15.0, q_mvar=5.0)],
        )
        sys_svc = service_build_system(spec)
        assert len(sys_svc.buses) == 2
        assert len(sys_svc.lines) == 1
        assert len(sys_svc.generators) == 1
        assert len(sys_svc.loads) == 1

        executor = StudyExecutor()
        sys_exec = executor._build_system_from_spec(spec)
        assert len(sys_exec.buses) == 2
        assert len(sys_exec.lines) == 1
        assert len(sys_exec.generators) == 1
        assert len(sys_exec.loads) == 1
