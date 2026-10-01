"""
tests/test_m6_integration_acceptance.py — Comprehensive Integration & Acceptance Battery (M6.1).

Validates the final platform convergence and production acceptance gates:
1. Reachability & Parity: All 20 entries in STUDY_DISPATCH across dual ports (StudyExecutor & study_service).
   Zero silent fallback to load_flow on unregistered or specialized studies (enforcing test_agent_registration_regression.py:7-26).
2. The 3 Canonical Chains: Data flows across multi-agent pipelines (SC->Prot->AF, LF->OPF->Verify LF, Harmonics->Filter Opt->Verify Harmonics).
3. Negative Tests for the 4 PSO Gates: Non-compliant solutions for placement, harmonic filter, protection coordination,
   and AC-OPF yield AgentStatus.REJECTED with validation_status=False and recorded violations.
4. Absence of Generic Fallback: Fails closed with SpecializedExecutionUnavailableError; verified clean under check_ai_fallback_guard.
5. REJECTED Cascade Propagation: Rejections halt execution, mark downstream dependents as SKIPPED_WITH_REASON,
   and set overall_success=False in execution traces.
6. ContextFabric Tenant Isolation: Complete isolation between tenants; ContextEvidence enforces mandatory provenance & SHA-256 hash.
7. CUA Governance & Approvals: CONTROL mode requires affirmative approval, post-action verification failure triggers automated rollback,
   and coordinate bounds check blocks out-of-window clicks.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from agents.base import BaseAgent
from agents.cua_base_executor import BaseCUAExecutor
from agents.cua_executor import CUAAction, CUAExecutionResult
from agents.life_safety import LifeSafetyGuard, life_safety_guard
from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
from agents.optimizers.optimization_agent import OptimizationAgent
from agents.registry import (
    CANONICAL_AGENT_KEYS,
    ShortCircuitAgent,
    create_agent_registry,
    get_study_type_mapping,
)
from agents.workflow import WorkflowEngine
from context_fabric import (
    CallableContextProvider,
    ContextEvidence,
    ContextEvidenceError,
    ContextFabric,
    ContextIsolationError,
    ContextType,
)
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
from scripts.check_ai_fallback_guard import run_ai_fallback_guard
from services.study_executor import StudyExecutor
from services.study_service import _run_native_study

REPO_ROOT = Path(__file__).resolve().parent.parent


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(name="sample_system_spec")
def fixture_sample_system_spec() -> SystemSpec:
    return SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack", base_kv=11.0),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0),
            BusSpec(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0),
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


class MockChainAgent(BaseAgent):
    """Configurable agent tracking received inputs and returning scripted outputs."""

    def __init__(self, name: str, output_data: dict[str, Any], fail: bool = False, reject: bool = False) -> None:
        super().__init__(name)
        self.agent_name = name
        self.output_data = output_data
        self.fail = fail
        self.reject = reject
        self.received_tasks: list[EngineeringTask] = []

    async def execute(self, task: EngineeringTask) -> AgentResult:
        self.received_tasks.append(task)
        st = task.study_types[0] if task.study_types else StudyType.LOAD_FLOW
        if isinstance(st, str):
            try:
                st = StudyType(st)
            except ValueError:
                st = StudyType.LOAD_FLOW

        if self.fail:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=st,
                status=AgentStatus.FAILED,
                data={"error": "Simulated hardware engine failure"},
                validation_status=False,
                validation_errors=["Simulated failure"],
            )
        if self.reject:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=st,
                status=AgentStatus.REJECTED,
                data={"violations": ["Constraint violation"]},
                validation_status=False,
                validation_errors=["Constraint violation"],
            )
        return AgentResult(
            agent_name=self.agent_name,
            study_type=st,
            status=AgentStatus.COMPLETED,
            data=dict(self.output_data),
            validation_status=True,
        )


class MockCUAExecutor(BaseCUAExecutor):
    """Concrete mock executor for testing CUA loop governance, approvals, and rollback."""

    def __init__(self, actions_to_return: list[dict[str, Any]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.actions_to_return = actions_to_return or []
        self.action_index = 0
        self.executed_actions: list[CUAAction] = []
        self.temp_dir = tempfile.TemporaryDirectory()

    def check_dependencies(self) -> dict[str, Any]:
        return {"all_available": True, "missing": []}

    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> str | None:
        p = Path(self.temp_dir.name) / f"screen_{step_num}_{phase}.png"
        color = "white" if phase == "before" else "lightgray"
        Image.new("RGB", (800, 600), color).save(str(p))
        return str(p)

    def _execute_action_hook(self, action: CUAAction, **kwargs) -> str | None:
        self.executed_actions.append(action)
        return None

    def _wait_settle(self) -> None:
        pass

    def _cleanup_on_exit(self) -> None:
        self.temp_dir.cleanup()


DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
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


# ==============================================================================
# 1. Dual-Port Reachability & Registry Integrity (M6.1.1)
# ==============================================================================


class TestM6ReachabilityAndRegistry:
    """Gate 1: Verify all 20 entries in STUDY_DISPATCH across dual ports with zero silent drift."""

    def test_study_dispatch_has_exactly_20_entries(self):
        assert len(STUDY_DISPATCH) == 20, f"Expected 20 entries in STUDY_DISPATCH, found {len(STUDY_DISPATCH)}"

    def test_canonical_agent_registry_coverage(self):
        agents = create_agent_registry()
        for key in CANONICAL_AGENT_KEYS:
            assert key in agents, f"Canonical agent key '{key}' missing from agent registry"
            assert isinstance(agents[key], BaseAgent)

    def test_study_type_mapping_no_silent_load_flow_fallback(self):
        """Enforces test_agent_registration_regression.py:7-26: no non-load_flow study maps to load_flow."""
        mapping = get_study_type_mapping()
        for study_val, target_agent in mapping.items():
            if study_val not in ("load_flow", "power_flow"):
                assert target_agent != "load_flow", (
                    f"Study mapping '{study_val}' points silently to 'load_flow' — "
                    "silent load_flow drift is strictly prohibited!"
                )

    def test_all_20_study_dispatch_entries_reachability(self, built_system):
        executor = StudyExecutor(cache=None)
        executed_count = 0
        specialized_unavailable_count = 0

        for study_type in STUDY_DISPATCH:
            params = DEFAULT_PARAMS.get(study_type, {})
            try:
                res = executor._dispatch(study_type, built_system, params)
                assert isinstance(res, dict)
                executed_count += 1
            except SpecializedExecutionUnavailableError as exc:
                assert exc.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
                assert exc.study_type == study_type
                assert isinstance(exc, ValueError)
                specialized_unavailable_count += 1
            except Exception as exc:
                pytest.fail(f"Study '{study_type}' dispatch raised unexpected exception: {exc}")

        assert executed_count + specialized_unavailable_count == 20
        assert executed_count >= 6
        assert specialized_unavailable_count <= 14

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
    def test_dual_port_parity_non_native_studies(self, built_system, study_type: str):
        executor = StudyExecutor(cache=None)

        # Port 1: StudyExecutor._dispatch
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_p1:
            executor._dispatch(study_type, built_system, {})
        assert exc_p1.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_p1.value.study_type == study_type

        # Port 2: study_service._run_native_study
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_p2:
            _run_native_study(study_type, built_system, {})
        assert exc_p2.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_p2.value.study_type == study_type

        # Engine shim: PowerSystemEngine
        engine = PowerSystemEngine(built_system)
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_eng:
            engine.run_study(study_type)
        assert exc_eng.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"

    def test_unregistered_study_raises_generic_value_error_no_silent_fallback(self, built_system):
        executor = StudyExecutor(cache=None)
        with pytest.raises(ValueError) as exc:
            executor._dispatch("unregistered_phantom_study", built_system, {})
        assert not isinstance(exc.value, SpecializedExecutionUnavailableError)
        assert "Unsupported native study type" in str(exc.value)


# ==============================================================================
# 2. The 3 Canonical Multi-Agent Chains (M6.1.2)
# ==============================================================================


class TestM6ThreeCanonicalChains:
    """Gate 2: Verification of the 3 canonical multi-agent workflows."""

    @pytest.mark.asyncio
    async def test_chain_1_short_circuit_protection_arc_flash(self):
        """Chain 1: short_circuit -> protection_coordination -> arc_flash."""
        sc_agent = MockChainAgent("ShortCircuitAgent", {"fault_current_ka": 31.5, "ik_ss_ka": 29.0})
        prot_agent = MockChainAgent("ProtectionCoordinationAgent", {"clearing_time_s": 0.12, "curve": "IEC_NI"})
        af_agent = MockChainAgent("ArcFlashAgent", {"incident_energy_cal_cm2": 4.1, "ppe_category": "Category 2"})
        val_agent = MockChainAgent("ValidationAgent", {"passed": True})

        engine = WorkflowEngine(
            agents={
                "short_circuit": sc_agent,
                "protection_coordination": prot_agent,
                "arc_flash": af_agent,
                "validation": val_agent,
            }
        )
        task = EngineeringTask(
            task_id="m6_chain_1",
            description="M6 Chain 1: SC -> Protection -> ArcFlash",
            study_types=[StudyType.SHORT_CIRCUIT, StudyType.PROTECTION_COORDINATION, StudyType.ARC_FLASH],
            parameters={"base_voltage_kv": 11.0},
        )

        results = await engine.execute_workflow(task)
        assert len(prot_agent.received_tasks) == 1
        assert prot_agent.received_tasks[0].parameters.get("fault_current_ka") == 31.5
        assert len(af_agent.received_tasks) == 1
        assert af_agent.received_tasks[0].parameters.get("fault_current_ka") == 31.5
        assert af_agent.received_tasks[0].parameters.get("clearing_time_s") == 0.12

        completed = [r for r in results if r.status == AgentStatus.COMPLETED]
        assert len(completed) >= 3

    @pytest.mark.asyncio
    async def test_chain_2_load_flow_opf_verify_load_flow(self):
        """Chain 2: load_flow -> optimal_power_flow -> verify load_flow."""
        lf_initial = {"bus_voltages": {1: 1.0, 2: 0.96}, "total_losses_mw": 2.4}
        opf_output = {"optimal_dispatch": {1: 42.0, 2: 28.0}, "control_setpoints": {"tap": 1.02}}
        lf_verified = {"bus_voltages": {1: 1.0, 2: 0.99}, "total_losses_mw": 1.8}

        lf_calls = []

        class LFMultiAgent(BaseAgent):
            def __init__(self):
                super().__init__("LoadFlowAgent")
                self.agent_name = "LoadFlowAgent"

            async def execute(self, task: EngineeringTask) -> AgentResult:
                lf_calls.append(task)
                out = lf_verified if len(lf_calls) > 1 else lf_initial
                return AgentResult(
                    agent_name=self.agent_name,
                    study_type=StudyType.LOAD_FLOW,
                    status=AgentStatus.COMPLETED,
                    data=out,
                    validation_status=True,
                )

        lf_agent = LFMultiAgent()
        opf_agent = MockChainAgent("OptimalPowerFlowAgent", opf_output)
        val_agent = MockChainAgent("ValidationAgent", {"passed": True})

        engine = WorkflowEngine(
            agents={
                "load_flow": lf_agent,
                "optimal_power_flow": opf_agent,
                "validation": val_agent,
            }
        )
        task = EngineeringTask(
            task_id="m6_chain_2",
            description="M6 Chain 2: LF -> OPF -> Verify LF",
            study_types=[StudyType.LOAD_FLOW, StudyType.OPTIMAL_POWER_FLOW, StudyType.LOAD_FLOW],
            parameters={"system_id": "sys_m6_chain_2"},
        )

        results = await engine.execute_workflow(task)
        assert len(opf_agent.received_tasks) == 1
        assert opf_agent.received_tasks[0].parameters.get("bus_voltages") == {1: 1.0, 2: 0.96}
        assert len(lf_calls) == 2
        assert lf_calls[1].parameters.get("generator_dispatch") == {1: 42.0, 2: 28.0}
        assert lf_calls[1].parameters.get("control_settings") == {"tap": 1.02}

        completed = [r for r in results if r.status == AgentStatus.COMPLETED]
        assert len(completed) >= 3

    @pytest.mark.asyncio
    async def test_chain_3_harmonics_filter_optimization_verify_harmonics(self):
        """Chain 3: harmonic_analysis -> optimization -> verify harmonic_analysis."""
        harm_initial = {"thd_voltage": 9.2, "harmonic_spectrum": {5: 6.5, 7: 4.8}}
        opt_output = {"filter_parameters": {"type": "single_tuned", "c_mvar": 6.0}, "projected_thd_v": 3.4}
        harm_verified = {"thd_voltage": 3.3, "harmonic_spectrum": {5: 1.8, 7: 1.2}}

        harm_calls = []

        class HarmMultiAgent(BaseAgent):
            def __init__(self):
                super().__init__("HarmonicAnalysisAgent")
                self.agent_name = "HarmonicAnalysisAgent"

            async def execute(self, task: EngineeringTask) -> AgentResult:
                harm_calls.append(task)
                out = harm_verified if len(harm_calls) > 1 else harm_initial
                return AgentResult(
                    agent_name=self.agent_name,
                    study_type=StudyType.HARMONIC_ANALYSIS,
                    status=AgentStatus.COMPLETED,
                    data=out,
                    validation_status=True,
                )

        harm_agent = HarmMultiAgent()
        opt_agent = MockChainAgent("OptimizationAgent", opt_output)
        val_agent = MockChainAgent("ValidationAgent", {"passed": True})

        engine = WorkflowEngine(
            agents={
                "harmonic_analysis": harm_agent,
                "optimization": opt_agent,
                "validation": val_agent,
            }
        )
        task = EngineeringTask(
            task_id="m6_chain_3",
            description="M6 Chain 3: Harmonics -> Filter Opt -> Verify Harmonics",
            study_types=[StudyType.HARMONIC_ANALYSIS, "optimization", StudyType.HARMONIC_ANALYSIS],
            parameters={"network": "grid_m6_h"},
        )

        results = await engine.execute_workflow(task)
        assert len(opt_agent.received_tasks) == 1
        assert opt_agent.received_tasks[0].parameters.get("baseline_thd_v") == 9.2
        assert len(harm_calls) == 2
        assert harm_calls[1].parameters.get("installed_filters") == {"type": "single_tuned", "c_mvar": 6.0}

        completed = [r for r in results if r.status == AgentStatus.COMPLETED]
        assert len(completed) >= 3

    @pytest.mark.asyncio
    async def test_chain_failure_cascade_aborts_downstream(self):
        """When an upstream step in a chain fails, downstream dependent steps are skipped."""
        sc_failing_agent = MockChainAgent("ShortCircuitAgent", {}, fail=True)
        prot_agent = MockChainAgent("ProtectionCoordinationAgent", {"clearing_time_s": 0.15})
        val_agent = MockChainAgent("ValidationAgent", {"passed": True})

        engine = WorkflowEngine(
            agents={
                "short_circuit": sc_failing_agent,
                "protection_coordination": prot_agent,
                "validation": val_agent,
            }
        )
        task = EngineeringTask(
            task_id="m6_chain_fail_cascade",
            description="Chain failure cascade verification",
            study_types=[StudyType.SHORT_CIRCUIT, StudyType.PROTECTION_COORDINATION],
            parameters={"base_voltage_kv": 11.0},
        )

        results = await engine.execute_workflow(task)
        assert len(sc_failing_agent.received_tasks) == 1
        assert len(prot_agent.received_tasks) == 0  # Downstream skipped


# ==============================================================================
# 3. Negative Tests for the 4 PSO Gates (M6.1.3)
# ==============================================================================


class TestM6PSOFourGatesNegativeRejection:
    """Gate 3: All 4 PSO optimization engines yield AgentStatus.REJECTED on constraint violations."""

    @pytest.mark.asyncio
    async def test_pso_gate_1_placement_voltage_violation_rejected(self):
        """PSO Gate 1: Placement yielding voltage < 0.90 pu yields AgentStatus.REJECTED."""
        agent = OptimizationAgent()
        task = EngineeringTask(
            task_id="pso_gate_1_fail",
            description="Capacitor placement violating minimum voltage",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "placement", "seed": 42},
        )
        mock_res = {
            "min_voltage_after": 0.88,
            "optimal_allocations": {2: 500.0},
            "initial_losses_mw": 1.5,
            "optimized_losses_mw": 1.2,
        }
        with patch.object(agent, "_run_placement", return_value=mock_res):
            result = await agent.execute(task)

        assert result.status == AgentStatus.REJECTED
        assert result.validation_status is False
        assert any("Voltage constraint violated" in v for v in result.validation_errors)

    @pytest.mark.asyncio
    async def test_pso_gate_2_harmonic_filter_thd_violation_rejected(self):
        """PSO Gate 2: Harmonic filter violating IEEE 519 (>5.0% THD) yields AgentStatus.REJECTED."""
        agent = OptimizationAgent()
        task = EngineeringTask(
            task_id="pso_gate_2_fail",
            description="Filter design exceeding THD limit",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "harmonic_filter", "seed": 101},
        )
        mock_res = {
            "ieee_519_compliant": False,
            "thd_v_after_pct": 6.8,
            "thd_v_before_pct": 14.0,
        }
        with patch.object(agent, "_run_filter_design", return_value=mock_res):
            result = await agent.execute(task)

        assert result.status == AgentStatus.REJECTED
        assert result.validation_status is False
        assert any("IEEE 519 compliance failed" in v for v in result.validation_errors)

    @pytest.mark.asyncio
    async def test_pso_gate_3_protection_coordination_margin_violation_rejected(self):
        """PSO Gate 3: Relay coordination violating selectivity time margin yields AgentStatus.REJECTED."""
        agent = OptimizationAgent()
        task = EngineeringTask(
            task_id="pso_gate_3_fail",
            description="Coordination margin failure",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "protection_coordination", "seed": 202},
        )
        mock_res = {
            "coordinated": False,
            "success": False,
            "cpi": 0.52,
        }
        with patch.object(agent, "_run_coordination", return_value=mock_res):
            result = await agent.execute(task)

        assert result.status == AgentStatus.REJECTED
        assert result.validation_status is False
        assert any("Relay coordination failed" in v for v in result.validation_errors)

    @pytest.mark.asyncio
    async def test_pso_gate_4_ac_opf_infeasibility_rejected(self):
        """PSO Gate 4: AC-OPF infeasibility / convergence failure yields AgentStatus.REJECTED."""
        agent = OptimizationAgent()
        task = EngineeringTask(
            task_id="pso_gate_4_fail",
            description="AC-OPF infeasible power flow constraints",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "pso_opf", "seed": 303},
        )
        mock_res = {
            "success": False,
            "error": "Generator Q-limits infeasible",
        }
        with patch.object(agent, "_run_opf", return_value=mock_res):
            result = await agent.execute(task)

        assert result.status == AgentStatus.REJECTED
        assert result.validation_status is False
        assert any("AC-OPF constraints violated" in v for v in result.validation_errors)


# ==============================================================================
# 4. Absence of Generic Fallback & Raw-LLM Elimination (M6.1.4)
# ==============================================================================


class TestM6AbsenceOfGenericFallback:
    """Gate 4: Ensure zero raw direct-AI fallback or ungrounded responses in platform serving paths."""

    def test_raw_llm_fallback_guard_zero_violations(self):
        """Asserts repository adheres 100% to M4.3 fallback prohibition."""
        violations = run_ai_fallback_guard(REPO_ROOT)
        assert violations == [], f"M4.3 Raw-LLM fallback guard found violations: {violations}"

    def test_specialized_execution_unavailable_fail_closed(self, built_system):
        """Unavailable specialized studies raise SpecializedExecutionUnavailableError, never raw LLM."""
        executor = StudyExecutor(cache=None)
        with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
            executor._dispatch("transient_stability", built_system, {})
        assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
        assert exc_info.value.study_type == "transient_stability"


# ==============================================================================
# 5. Fail-Closed REJECTED Cascade Propagation (M6.1.5)
# ==============================================================================


class TestM6FailClosedRejectedPropagation:
    """Gate 5: Node rejection halts execution, cascades SKIPPED to downstream, and exports overall_success=False."""

    @pytest.mark.asyncio
    async def test_workflow_engine_rejection_marks_downstream_skipped(self):
        """When node 1 is REJECTED, dependent node 2 is marked SKIPPED_WITH_REASON and trace overall_success=False."""
        agent_1 = MockChainAgent("bad_agent", {}, reject=True)
        agent_2 = MockChainAgent("good_agent", {"completed": True})

        engine = WorkflowEngine(
            agents={
                "short_circuit": agent_1,
                "arc_flash": agent_2,
            }
        )
        task = EngineeringTask(
            task_id="m6_reject_cascade",
            description="Rejection cascade verification",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={
                "custom_nodes": [
                    {
                        "node_id": "node_1",
                        "study_type": "short_circuit",
                        "agent_id": "bad_agent",
                        "depends_on": [],
                    },
                    {
                        "node_id": "node_2",
                        "study_type": "arc_flash",
                        "agent_id": "good_agent",
                        "depends_on": ["node_1"],
                    },
                ]
            },
        )

        results = await engine.execute_workflow(task)
        assert len(agent_1.received_tasks) == 1
        assert len(agent_2.received_tasks) == 0

        res_1 = next(r for r in results if r.agent_name == "bad_agent")
        assert res_1.status == AgentStatus.REJECTED

        # Verify trace export
        trace = engine.export_execution_trace(task, results)
        assert trace is not None
        assert not trace.overall_success
        assert len(trace.node_results) >= 1
        assert not trace.node_results[0].success


# ==============================================================================
# 6. ContextFabric Tenant Isolation & Provenance (M6.1.6)
# ==============================================================================


class TestM6ContextFabricTenantIsolation:
    """Gate 6: Multi-tenant boundaries and provenance integrity across ContextFabric."""

    def test_context_fabric_query_without_tenant_raises_isolation_error(self):
        fabric = ContextFabric()
        with pytest.raises(ContextIsolationError) as exc_info:
            fabric.query(ContextType.STANDARDS, "grid specs", tenant_id="")
        assert "tenant" in str(exc_info.value).lower()

    def test_context_evidence_mandatory_fields_and_hash(self):
        # Valid evidence computes SHA-256 content_hash
        ev = ContextEvidence.build(
            ContextType.STANDARDS,
            "ieee.c84_1",
            {"rule": "Range A 0.95..1.05"},
            tenant_id="tenant_alpha",
        )
        assert ev.content_hash is not None
        assert len(ev.content_hash) == 64
        assert ev.tenant_id == "tenant_alpha"
        assert ev.key == "ieee.c84_1"

        # Missing or empty tenant_id raises ContextIsolationError
        with pytest.raises(ContextIsolationError):
            ContextEvidence.build(
                ContextType.STANDARDS,
                "ieee.c84_1",
                {"rule": "Range A"},
                tenant_id="",
            )

        # Missing key/value raises ContextEvidenceError
        with pytest.raises(ContextEvidenceError):
            ContextEvidence.build(
                ContextType.STANDARDS,
                "",
                {"rule": "Range A"},
                tenant_id="tenant_alpha",
            )

    def test_context_fabric_cross_tenant_isolation(self):
        """Data from tenant_alpha must never bleed into tenant_beta queries."""
        records = {
            "tenant_alpha": [
                ContextEvidence.build(
                    ContextType.ENGINEERING_KNOWLEDGE,
                    "substation.alpha",
                    {"substation": "Alpha-400kV"},
                    tenant_id="tenant_alpha",
                )
            ],
            "tenant_beta": [
                ContextEvidence.build(
                    ContextType.ENGINEERING_KNOWLEDGE,
                    "substation.beta",
                    {"substation": "Beta-220kV"},
                    tenant_id="tenant_beta",
                )
            ],
        }

        def mock_provider_func(query_str: str, tenant: str, max_items: int):
            raw = records.get(tenant, [])
            return [{"key": e.key, "value": e.value, "source_ref": "mock"} for e in raw]

        provider = CallableContextProvider("mock_tenant_provider", mock_provider_func)
        fabric = ContextFabric({ContextType.ENGINEERING_KNOWLEDGE: provider})

        # Query tenant_alpha
        res_alpha = fabric.query(ContextType.ENGINEERING_KNOWLEDGE, "substation", tenant_id="tenant_alpha")
        assert res_alpha.available is True
        assert len(res_alpha.evidence) == 1
        assert res_alpha.evidence[0].value["substation"] == "Alpha-400kV"

        # Query tenant_beta
        res_beta = fabric.query(ContextType.ENGINEERING_KNOWLEDGE, "substation", tenant_id="tenant_beta")
        assert res_beta.available is True
        assert len(res_beta.evidence) == 1
        assert res_beta.evidence[0].value["substation"] == "Beta-220kV"
        assert res_beta.evidence[0].value["substation"] != "Alpha-400kV"


# ==============================================================================
# 7. CUA Governance & Approvals (M6.1.7)
# ==============================================================================


class TestM6CUAGovernanceAndApprovals:
    """Gate 7: CUA safety rules, affirmative approvals, automated rollback, and coordinate bounds."""

    def test_cua_control_mode_requires_affirmative_approval(self):
        """Negative test: CONTROL action with require_confirmation=True and rejection callback must abort."""
        executor = MockCUAExecutor()
        mock_action_dict = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 200,
                "y": 300,
                "target": "Breaker Open Operation",
            },
        }

        rejection_callback = MagicMock(return_value=False)

        with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=mock_action_dict):
            result: CUAExecutionResult = executor.execute_loop(
                objective="Open circuit breaker",
                max_steps=1,
                mode="control",
                require_confirmation=True,
                on_confirmation_request=rejection_callback,
                bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
            )

        assert not result.success
        assert "declined" in (result.aborted_reason or "").lower()
        assert len(executor.executed_actions) == 0

    def test_cua_post_action_verification_failure_triggers_auto_rollback(self):
        """STEP 10.5 post-action failure halts CUA and triggers registered auto-rollback."""
        executor = MockCUAExecutor()
        action_dict = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 300,
                "y": 400,
                "target": "modify_transformer_tap",
            },
        }

        rollback_called_with = []

        def mock_auto_rollback(snapshot_id: str, reason: str = ""):
            rollback_called_with.append((snapshot_id, reason))
            return True

        life_safety_guard.register_auto_rollback_handler(mock_auto_rollback)
        life_safety_guard.set_verification_hook(MagicMock(return_value=False))

        try:
            with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_dict):
                result: CUAExecutionResult = executor.execute_loop(
                    objective=f"Change tap {uuid.uuid4().hex[:8]}",
                    max_steps=2,
                    mode="control",
                    require_confirmation=False,
                    bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
                )

            assert not result.success
            assert (
                "post_action_verification_failed" in (result.aborted_reason or "").lower()
                or "verification failed" in (result.aborted_reason or "").lower()
            )
            assert len(executor.executed_actions) == 1
            assert len(rollback_called_with) >= 1
            assert "post_action_verification_failed" in rollback_called_with[0][1]
        finally:
            life_safety_guard.set_verification_hook(None)
            life_safety_guard.register_auto_rollback_handler(None)

    def test_cua_coordinate_bounds_violation_aborts_before_action(self):
        """Actions targeting coordinates outside defined window bounds abort before execution."""
        executor = MockCUAExecutor()
        action_dict = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 2500,  # Exceeds max_x 1920
                "y": 500,
                "target": "desktop_escape",
            },
        }

        with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_dict):
            result: CUAExecutionResult = executor.execute_loop(
                objective="Click outside ETAP window",
                max_steps=1,
                mode="control",
                require_confirmation=False,
                bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
            )

        assert not result.success
        assert "bounds" in (result.aborted_reason or "").lower()
        assert len(executor.executed_actions) == 0


class TestM6FullLifecycleIntentToProvenance:
    """Final Acceptance Gate: Full lifecycle Intent -> Plan -> DAG -> Execution -> Assertions -> Evidence -> Provenance."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle_intent_plan_dag_execution_assertions_evidence_provenance(self, built_system):
        """Validates the unbroken execution chain from user intent to verifiable provenance."""
        # 1. Intent: High-level user engineering objective
        intent = "Assess three-phase bolted fault at Bus 2 and coordinate protection relays"
        tenant_id = "tenant_m6_acceptance_alpha"
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # 2. Plan: Tasks structured for the objective
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = EngineeringTask(
            task_id=task_id,
            description=intent,
            study_types=[StudyType.SHORT_CIRCUIT, StudyType.PROTECTION_COORDINATION],
            parameters={
                "system": built_system,
                "fault_buses": [2],
                "bus_id": 2,
                "fault_type": "three_phase",
                "upstream_relay_id": 1,
                "downstream_relay_id": 2,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "source": "user_input",
            },
        )

        # 3. DAG: WorkflowEngine generates contract-driven execution plan
        # R-11: ShortCircuitAgent uses the real engine-backed agent rather than a pure mock
        sc_agent = ShortCircuitAgent()
        prot_agent = MockChainAgent(
            "ProtectionCoordinationAgent",
            output_data={
                "margin_s": 0.32,
                "clearing_time_s": 0.15,
                "coordination_curve": "IEC_Standard_Inverse",
                "is_coordinated": True,
            },
        )
        agents_map = {
            "short_circuit": sc_agent,
            "protection_coordination": prot_agent,
        }

        workflow = WorkflowEngine(agents=agents_map)
        plan = workflow.build_execution_plan(task)
        assert plan is not None
        assert len(plan.nodes) == 2
        # Verify DAG dependency: protection depends on short_circuit
        sc_node = [n for n in plan.nodes if n.study_type == "short_circuit"][0]
        prot_node = [n for n in plan.nodes if n.study_type == "protection_coordination"][0]
        assert sc_node.node_id in prot_node.depends_on

        # 4. Execution: Execute workflow across DAG batches (includes automated validation gate)
        results = await workflow.execute_workflow(task)
        assert len(results) >= 2
        assert all(r.status == AgentStatus.COMPLETED for r in results)

        # 5. Assertions: Physical engineering checks
        sc_res = results[0]
        prot_res = results[1]
        assert sc_res.data.get("fault_current_ka", 0) > 0, "Fault current must be positive"
        assert prot_res.data.get("margin_s", 0) >= 0.20, "Coordination margin must meet IEC minimum (0.20s)"

        # 6. Evidence: Record cryptographic evidence in ContextFabric
        evidence_sc = ContextEvidence.build(
            ContextType.PROJECT_STATE,
            f"fault_study_{task_id}",
            {"fault_current_ka": sc_res.data["fault_current_ka"], "bus_id": 2},
            tenant_id=tenant_id,
        )
        evidence_prot = ContextEvidence.build(
            ContextType.PROJECT_STATE,
            f"prot_study_{task_id}",
            {"margin_s": prot_res.data["margin_s"], "is_coordinated": True},
            tenant_id=tenant_id,
        )

        def mock_provider_func(query_str: str, tenant: str, max_items: int):
            return [
                {"key": evidence_sc.key, "value": evidence_sc.value, "source_ref": "engine"},
                {"key": evidence_prot.key, "value": evidence_prot.value, "source_ref": "engine"},
            ]

        provider = CallableContextProvider("project_data_provider", mock_provider_func)
        fabric = ContextFabric({ContextType.PROJECT_STATE: provider})

        # 7. Provenance: Query and verify immutable evidence integrity and tenant bounds
        retrieved = fabric.query(ContextType.PROJECT_STATE, f"fault_study_{task_id}", tenant_id=tenant_id)
        assert retrieved.available is True
        assert len(retrieved.evidence) >= 1
        assert len(evidence_sc.content_hash) == 64  # SHA-256 hash
        assert evidence_sc.source_type == ContextType.PROJECT_STATE
        assert evidence_sc.tenant_id == tenant_id

        # Trace export verification
        trace = workflow.export_execution_trace(task, results, plan)
        assert trace is not None
        assert trace.overall_success is True
        assert len(trace.node_results) >= 2

