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


@pytest.mark.asyncio
class TestCanonicalExecutionOrchestratorTopologyRejection:
    """Verifies that ExecutionOrchestrator enforces fail-closed topology validation (P1-B)."""

    async def test_canonical_orchestrator_rejects_dict_with_dangling_line_bus(self):
        """Dict system input with dangling line bus must fail closed at canonical boundary."""
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={
                "system": {
                    "base_mva": 100.0,
                    "buses": [{"bus_id": 1, "base_kv": 132.0, "bus_type": "slack"}],
                    "lines": [{"line_id": 101, "from_bus_id": 999, "to_bus_id": 1, "r1": 0.01, "x1": 0.05}],
                }
            },
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("references unknown bus" in err for err in res.errors)

    async def test_canonical_orchestrator_rejects_spec_with_dangling_transformer_bus(self, valid_bus_spec):
        """SystemSpec with dangling transformer bus must fail closed at canonical boundary."""
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        orch = ExecutionOrchestrator()
        b2 = BusSpec(bus_id=2, base_kv=132.0, bus_type="pq")
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec, b2],
            lines=[LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05)],
            transformers=[
                TransformerSpec(transformer_id=201, from_bus_id=1, to_bus_id=777, r1=0.01, x1=0.08)
            ],
        )
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": spec},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("references unknown bus 777" in err for err in res.errors)

    async def test_canonical_orchestrator_rejects_spec_with_dangling_load_or_generator(self, valid_bus_spec):
        """SystemSpec with dangling generator/load must fail closed at canonical boundary."""
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        orch = ExecutionOrchestrator()
        b2 = BusSpec(bus_id=2, base_kv=132.0, bus_type="pq")
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec, b2],
            lines=[LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05)],
            generators=[GeneratorSpec(generator_id=301, bus_id=666, r1=0.02, x1=0.15)],
            loads=[LoadSpec(load_id=401, bus_id=555, p_mw=25.0, q_mvar=10.0)],
        )
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": spec},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("references unknown bus" in err for err in res.errors)

    async def test_canonical_orchestrator_valid_model_continues_normally(self, valid_bus_spec):
        """Valid SystemSpec model continues through normal canonical execution without rejection."""
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        orch = ExecutionOrchestrator()
        b2 = BusSpec(bus_id=2, base_kv=132.0, bus_type="pq")
        spec = SystemSpec(
            base_mva=100.0,
            buses=[valid_bus_spec, b2],
            lines=[LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05)],
            generators=[GeneratorSpec(generator_id=1, bus_id=1, r1=0.01, x1=0.1)],
            loads=[LoadSpec(load_id=1, bus_id=2, p_mw=15.0, q_mvar=5.0)],
        )
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": spec},
        )
        res = await orch.execute(req)
        assert res.success is True
        assert res.status == "completed"

    async def test_canonical_orchestrator_rejects_fake_object_with_buses_attribute(self):
        """An arbitrary mock or object with a 'buses' attribute cannot bypass validation."""
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        class FakeBusesObject:
            buses = {"b1": "something"}

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": FakeBusesObject()},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("Unsupported or unvalidated system model type" in err for err in res.errors)

    async def test_canonical_orchestrator_validates_domain_system_with_dangling_line(self):
        """A core_model.system.System instance with dangling line references is rejected."""
        from core_model.bus import Bus
        from core_model.line import Line
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=100.0, base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        sys_obj.buses = {"B1": b1}

        b_ghost = Bus(bus_id="B_GHOST", base_kv=132.0, bus_type="pq")
        line = Line(line_id="L1", from_bus=b1, to_bus=b_ghost, z1=complex(0.01, 0.05))
        sys_obj.lines = [line]

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("references unknown bus" in err for err in res.errors)

    async def test_canonical_orchestrator_rejects_domain_system_bus_key_mismatch(self):
        """DomainSystem where bus dict key does not match bus_id is rejected."""
        from core_model.bus import Bus
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=100.0, base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        sys_obj.buses = {"WRONG_KEY": b1}

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("does not match canonical bus_id" in err for err in res.errors)

    async def test_canonical_orchestrator_rejects_domain_system_nonfinite_base_mva(self):
        """DomainSystem with nonfinite base_mva fails closed."""
        from core_model.bus import Bus
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=float("nan"), base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        sys_obj.buses = {"B1": b1}

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert res.status in ("failed", "rejected")
        assert any("invalid base_mva" in err for err in res.errors)

    async def test_canonical_orchestrator_rejects_domain_system_dangling_transformer_and_generator(self):
        """DomainSystem with dangling transformer or generator fails closed."""
        from core_model.bus import Bus
        from core_model.generator import Generator
        from core_model.transformer import Transformer
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=100.0, base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        sys_obj.buses = {"B1": b1}

        b_ghost = Bus(bus_id="B_GHOST", base_kv=33.0, bus_type="pq")
        xf = Transformer(transformer_id="T1", from_bus=b1, to_bus=b_ghost, z1=complex(0.01, 0.08))
        sys_obj.transformers = [xf]

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert any("Transformer 'T1' references unknown bus" in err for err in res.errors)

        # Clear transformers, add dangling generator
        sys_obj.transformers = []
        gen = Generator(generator_id="G1", bus=b_ghost)
        sys_obj.generators = [gen]

        req2 = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res2 = await orch.execute(req2)
        assert res2.success is False
        assert any("Generator 'G1' references unknown bus" in err for err in res2.errors)

    async def test_canonical_orchestrator_rejects_domain_system_nonfinite_parameters(self):
        """DomainSystem with NaN or Inf in electrical parameters fails closed."""
        from core_model.bus import Bus
        from core_model.line import Line
        from core_model.load import Load
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=100.0, base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        b2 = Bus(bus_id="B2", base_kv=132.0, bus_type="pq")
        sys_obj.buses = {"B1": b1, "B2": b2}

        # Line with NaN impedance
        line = Line(line_id="L1", from_bus=b1, to_bus=b2, z1=complex(float("nan"), 0.05))
        sys_obj.lines = [line]

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res = await orch.execute(req)
        assert res.success is False
        assert any("nonfinite complex parameter z1" in err for err in res.errors)

        # Fix line, add load with infinite load_power
        sys_obj.lines = [Line(line_id="L1", from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05))]
        ld = Load(load_id="LD1", bus=b2, load_power=complex(float("inf"), 5.0))
        sys_obj.loads = [ld]

        req2 = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )
        res2 = await orch.execute(req2)
        assert res2.success is False
        assert any("nonfinite load_power" in err for err in res2.errors)

    async def test_canonical_orchestrator_prevents_engine_dispatch_on_validation_failure(self):
        """A topology validation failure aborts execution before the engine or study service is dispatched."""
        from unittest.mock import patch
        from core_model.bus import Bus
        from core_model.line import Line
        from core_model.system import System as DomainSystem
        from services.execution_orchestrator import ExecutionOrchestrator
        from services.execution_request import ExecutionRequest

        sys_obj = DomainSystem(base_mva=100.0, base_kv=132.0)
        b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
        sys_obj.buses = {"B1": b1}
        b_ghost = Bus(bus_id="B_GHOST", base_kv=132.0, bus_type="pq")
        line = Line(line_id="L1", from_bus=b1, to_bus=b_ghost, z1=complex(0.01, 0.05))
        sys_obj.lines = [line]

        orch = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="load_flow",
            tenant_id="tenant_topo_test",
            user_id="engineer_1",
            input={"system": sys_obj},
        )

        from services.execution_orchestrator import NativeEngineeringExecutor

        with patch.object(NativeEngineeringExecutor, "execute", autospec=True) as mock_executor:
            res = await orch.execute(req)
            assert res.success is False
            assert res.status in ("failed", "rejected")
            mock_executor.assert_not_called()
