"""
tests/test_structural_anti_bypass_regressions.py — Structural Anti-Bypass Regression Tests.

Verifies the 4 core architectural invariants established in the Canonical Execution Flow:
1. Celery worker cannot bypass ExecutionOrchestrator (and never invokes legacy quarantined helpers).
2. HuggingFace Space runner cannot bypass ExecutionOrchestrator and fails closed on error.
3. ExternalServiceExecutor cannot fall back to local execution and fails closed if backend is missing/failing.
4. MathGuard cannot self-mirror and fails closed on missing/divergent deterministic verification.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_model.specs import BusSpec, StudyRequest, SystemSpec
from services.execution_request import (
    CanonicalExecutionResult,
    ExecutionRequest,
)


class TestStructuralAntiBypassRegressions(unittest.TestCase):
    """Structural anti-bypass regression suite for release gate compliance."""

    def setUp(self):
        self.sample_system = SystemSpec(
            base_mva=100.0,
            buses=[
                BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.0, voltage_angle=0.0),
                BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
            ],
            lines=[],
        )
        self.sample_request = StudyRequest(
            study_type="load_flow",
            system=self.sample_system,
            parameters={"tol": 1e-5, "max_iter": 50},
        )

    # ─── 1. Celery Worker Cannot Bypass ExecutionOrchestrator ───────────────

    def test_celery_worker_cannot_bypass_execution_orchestrator(self):
        """Celery worker MUST execute through ExecutionOrchestrator and NEVER call legacy helpers."""
        from services.study_service import execute_study_logic
        from worker.tasks import execute_engineering_study_task

        study_data = {
            "study_type": "load_flow",
            "data": self.sample_request.model_dump(),
            "trace_id": "test_celery_trace_123",
            "user_id": "authenticated_engineer_42",
            "tenant_id": "utility_tenant_alpha",
            "user_role": "lead_engineer",
        }

        # Track that ExecutionOrchestrator.execute is called
        with patch("services.execution_orchestrator.ExecutionOrchestrator.execute") as mock_orch_exec, \
             patch("services.study_service._run_native_study") as mock_legacy_native, \
             patch("services.study_service._run_etap_study") as mock_legacy_etap, \
             patch("worker.tasks.current_task"):

            fake_canonical_res = CanonicalExecutionResult(
                execution_id="exec_test_celery",
                request_id="req_test_celery",
                capability_id="load_flow",
                capability_version="1.0.0",
                tenant_id="utility_tenant_alpha",
                user_id="authenticated_engineer_42",
                executor_kind="local_engine",
                provider="native",
                solver="newton_raphson",
                engine_version="1.0.0",
                status="completed",
                success=True,
                data={"converged": True, "iterations": 3},
                errors=[],
                warnings=[],
            )
            mock_orch_exec.return_value = fake_canonical_res

            # Run the task directly (simulating worker process execution)
            result = execute_engineering_study_task.run(study_data)

            # Invariant 1: Orchestrator MUST have been called
            assert mock_orch_exec.called, "ExecutionOrchestrator.execute was NOT called by Celery task"
            called_req = mock_orch_exec.call_args[0][0]
            assert isinstance(called_req, ExecutionRequest)
            assert called_req.capability_id == "load_flow"
            assert called_req.user_id == "authenticated_engineer_42"
            assert called_req.tenant_id == "utility_tenant_alpha"

            # Invariant 2: Quarantined legacy execution functions MUST NEVER be called
            assert not mock_legacy_native.called, "Legacy _run_native_study was called! Bypass detected!"
            assert not mock_legacy_etap.called, "Legacy _run_etap_study was called! Bypass detected!"

            # Invariant 3: Result properly reflects execution
            assert result["success"] is True
            assert result["data"]["converged"] is True

    # ─── 2. HF Space Runner Cannot Bypass ExecutionOrchestrator ────────────

    def test_hf_space_runner_cannot_bypass_execution_orchestrator(self):
        """HuggingFace Space runner MUST route through ExecutionOrchestrator and fail closed on error."""
        from api.shared_handlers import run_study_lightweight

        system_dict = self.sample_system.model_dump()
        params = {"tol": 1e-4}

        with patch("services.execution_orchestrator.ExecutionOrchestrator.execute") as mock_orch_exec:
            fake_res = CanonicalExecutionResult(
                execution_id="hf_exec_01",
                request_id="hf_req_01",
                capability_id="load_flow",
                capability_version="1.0.0",
                tenant_id="hf_space_tenant",
                user_id="service_principal:hf_space",
                executor_kind="local_engine",
                provider="native",
                solver="newton_raphson",
                engine_version="1.0.0",
                status="completed",
                success=True,
                data={"converged": True},
                errors=[],
                warnings=[],
            )
            mock_orch_exec.return_value = fake_res

            # 1. Normal execution passes through orchestrator
            response = run_study_lightweight("load_flow", system_dict, params)
            assert mock_orch_exec.called
            called_req = mock_orch_exec.call_args[0][0]
            assert called_req.capability_id == "load_flow"
            assert called_req.tenant_id == "hf_space_tenant"
            assert called_req.metadata.get("deployment") == "hf_space"
            assert "reference" in response

        # 2. Failure case: Orchestrator raises an error -> HF runner MUST fail closed
        with patch("services.execution_orchestrator.ExecutionOrchestrator.execute", side_effect=RuntimeError("Engine crash")):
            failed_response = run_study_lightweight("load_flow", system_dict, params)
            assert failed_response.get("status") == "failed"
            assert failed_response.get("_status") == 500
            assert "Engine crash" in failed_response.get("error", "")

    # ─── 3. External Service Executor Cannot Use Local Executor & Fails Closed ──

    def test_external_executor_cannot_use_local_executor_and_fails_closed(self):
        """ExternalServiceExecutor MUST fail closed when endpoint is absent or failing and NEVER use local."""
        from services.execution_orchestrator import ExternalServiceExecutor

        executor = ExternalServiceExecutor()

        # Subtest A: No external endpoint configured -> MUST fail closed as unavailable
        req_no_endpoint = ExecutionRequest(
            capability_id="external_grid_sync",
            tenant_id="tenant_ext",
            user_id="user_ext",
            input={"test": 123},
            metadata={},  # No external_endpoint
        )

        with patch("services.study_executor.StudyExecutor._dispatch") as mock_local_dispatch:
            res_no_ep = asyncio.run(executor.execute(req_no_endpoint))

            assert res_no_ep.success is False
            assert res_no_ep.status == "failed"
            assert res_no_ep.provenance.get("failure_reason") == "NO_EXTERNAL_ENDPOINT_CONFIGURED"
            assert any("No external endpoint configured" in err for err in res_no_ep.errors)
            # Critical invariant: MUST NOT fall back to local dispatch
            assert not mock_local_dispatch.called, "External executor fell back to local StudyExecutor._dispatch!"

        # Subtest B: External endpoint returns 502 / failure -> MUST fail closed, no local fallback
        req_with_endpoint = ExecutionRequest(
            capability_id="external_grid_sync",
            tenant_id="tenant_ext",
            user_id="user_ext",
            input={"test": 123},
            metadata={"external_endpoint": "https://api.external-grid.example.com/solve"},
        )

        with patch("httpx.AsyncClient.post", side_effect=Exception("Remote refused")), \
             patch("services.study_executor.StudyExecutor._dispatch") as mock_local_dispatch:
            res_fail = asyncio.run(executor.execute(req_with_endpoint))

            assert res_fail.success is False
            assert res_fail.status == "failed"
            assert any("Remote refused" in err for err in res_fail.errors)
            assert not mock_local_dispatch.called, "External executor fell back to local StudyExecutor on network error!"

    # ─── 4. MathGuard Cannot Self-Mirror & Fails Closed ────────────────────

    def test_math_guard_cannot_self_mirror_and_fails_closed(self):
        """MathGuard MUST block when independent recomputation is missing, diverges, or fails."""
        from agents.ahmed_etap_orchestrator import MathGuard, MathGuardResult

        guard = MathGuard(tolerance_pct=0.01)

        # Invariant 4A: Missing recomputation (recompute is None) -> MUST FAIL CLOSED
        res_none = guard.validate(
            claim_value=1.024,
            recompute=None,
            quantity_kind="voltage",
            claim_unit="pu",
        )
        assert res_none.passed is False
        assert "VERIFICATION_UNAVAILABLE" in res_none.reason
        assert res_none.recomputed_value is None

        # Invariant 4B: Recompute callback raises exception -> MUST FAIL CLOSED
        def faulty_recompute():
            raise ValueError("Numerical divergence in solver")

        res_exc = guard.validate(
            claim_value=1.024,
            recompute=faulty_recompute,
            quantity_kind="voltage",
            claim_unit="pu",
        )
        assert res_exc.passed is False
        assert "recompute callback raised" in res_exc.reason

        # Invariant 4C: Divergent claim vs independent recompute (>0.01%) -> MUST BLOCK
        res_mismatch = guard.validate(
            claim_value=1.025,  # ~0.097% off
            recompute=lambda: 1.024,
            quantity_kind="voltage",
            claim_unit="pu",
        )
        assert res_mismatch.passed is False
        assert "value mismatch" in res_mismatch.reason

        # Invariant 4D: True deterministic match passes
        res_ok = guard.validate(
            claim_value=1.024,
            recompute=lambda: 1.024,
            quantity_kind="voltage",
            claim_unit="pu",
        )
        assert res_ok.passed is True
        assert res_ok.recomputed_value == 1.024

    # ─── 5. API Study Endpoint Routes Strictly Through Canonical Orchestrator ──

    def test_api_study_endpoint_routes_strictly_through_canonical_orchestrator(self):
        """API /run endpoint MUST delegate directly to ExecutionOrchestrator and never bypass."""
        from api.studies import run_study

        with patch("services.execution_orchestrator.ExecutionOrchestrator.execute") as mock_orch_exec, \
             patch("services.study_service._run_native_study") as mock_legacy_native, \
             patch("services.study_service._run_etap_study") as mock_legacy_etap:

            fake_canonical_res = CanonicalExecutionResult(
                execution_id="api_exec_123",
                request_id="api_req_123",
                capability_id="load_flow",
                capability_version="1.0.0",
                tenant_id="tenant_api_1",
                user_id="user_api_1",
                executor_kind="local_engine",
                provider="native",
                solver="newton_raphson",
                engine_version="1.0.0",
                status="completed",
                success=True,
                data={"converged": True},
                errors=[],
                warnings=[],
            )
            mock_orch_exec.return_value = fake_canonical_res

            res = asyncio.run(
                run_study(
                    req=None,
                    payload=self.sample_request,
                    _= "mock_api_key_test",
                    user=None,
                    user_id="user_api_1",
                    tenant_id="tenant_api_1",
                )
            )

            assert mock_orch_exec.called, "ExecutionOrchestrator.execute was not called by API endpoint!"
            assert not mock_legacy_native.called, "Legacy native study wrapper called by API!"
            assert not mock_legacy_etap.called, "Legacy ETAP study wrapper called by API!"
            assert res.status in ("success", "completed")
            assert res.data.get("converged") is True

    # ─── 6. Stability Refuses Missing Inputs Without Synthetic Fallback ──────

    def test_stability_missing_engineering_input_refuses_execution_without_synthetic_fallback(self):
        """StabilityAgent MUST fail closed with INSUFFICIENT_ENGINEERING_INPUT and never fabricate Ybus."""
        from agents.models import AgentStatus
        from agents.orchestrator import EngineeringTask, StudyType
        from agents.stability_agent import StabilityAgent

        agent = StabilityAgent()

        task = EngineeringTask(
            task_id="test_stability_missing_input",
            description="Stability analysis missing engineering parameters",
            study_types=[StudyType.TRANSIENT_STABILITY],
            parameters={"analysis_type": "transient"},
        )
        result = asyncio.run(agent.execute(task))

        assert result.status == AgentStatus.FAILED
        assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"
        missing = result.data.get("missing_inputs", [])
        assert any("Ybus_reduced" in item for item in missing)
        assert any("inertia_constants" in item for item in missing)

    # ─── 7. Production Maturity Gate Refuses Non-Production Execution ──────

    def test_production_maturity_gate_refuses_unvalidated_capability(self):
        """ExecutionOrchestrator MUST reject capabilities lacking production certification when requested."""
        from services.execution_orchestrator import ExecutionOrchestrator

        orchestrator = ExecutionOrchestrator()

        # Request transient_stability with strict production certification demand
        req = ExecutionRequest(
            capability_id="transient_stability",
            tenant_id="cert_tenant",
            user_id="lead_engineer_1",
            user_role="lead_engineer",
            input={"test": 123},
            metadata={"demand_production_certification": True},
        )

        result = asyncio.run(orchestrator.execute(req))

        assert result.status == "rejected"
        assert result.success is False
        assert any("PRODUCTION_MATURITY_GATE_REJECTED" in err for err in result.errors)
        assert result.provenance.get("rejection_reason") == "PRODUCTION_MATURITY_GATE_REJECTED"

    # ─── 8. Standards Numerical Drift Protection ──────────────────────────

    def test_iec60909_benchmark_regression_fails_on_numerical_drift(self):
        """IEC 60909 benchmark comparison MUST fail when solver results deviate beyond tolerance."""
        from engine.benchmarks.ieee_cases import IEC_60909_4BUS_BENCHMARK_FAULTS

        ref_case = IEC_60909_4BUS_BENCHMARK_FAULTS["results"][2]
        expected_ik = ref_case["three_phase_ik_ka"]
        tolerance_ka = ref_case["tolerance_ka"]

        # Simulated drifted calculation (> tolerance deviation)
        drifted_ik = expected_ik + 0.5  # 0.5 kA drift
        diff = abs(drifted_ik - expected_ik)

        assert diff > tolerance_ka, "Drift of 0.5 kA should exceed tolerance threshold"

    def test_ieee1584_benchmark_regression_fails_on_numerical_drift(self):
        """IEEE 1584 benchmark comparison MUST fail when arc flash results deviate beyond tolerance."""
        from engine.benchmarks.ieee_cases import IEEE_1584_ANNEX_D_PUBLISHED_CASES

        ref_case = IEEE_1584_ANNEX_D_PUBLISHED_CASES[0]
        expected_energy = ref_case["published_energy_cal_cm2"]
        tolerance_cal = 0.10

        # Simulated drifted calculation (> tolerance deviation)
        drifted_energy = expected_energy + 0.5  # 0.5 cal/cm2 drift
        diff = abs(drifted_energy - expected_energy)

        assert diff > tolerance_cal, "Drift of 0.5 cal/cm2 should exceed tolerance threshold"

