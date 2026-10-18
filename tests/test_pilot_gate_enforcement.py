"""Regression tests for Defect 3: Authoritative Server-Side PILOT Capability Gating.

Verifies that client inputs (metadata.pilot_opt_in, metadata.allow_pilot,
input.pilot_opt_in, execution_policy="pilot", provider_policy="pilot")
CANNOT bypass server-side feature flags or dual-control approval policies.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.feature_flags import is_strict_feature_enabled
from core_model.specs import BusSpec, SystemSpec
from engine.capability_registry import CapabilityRegistry, LifecycleStatus
from services.execution_orchestrator import (
    ExecutionOrchestrator,
    SpecializedExecutionUnavailableError,
)
from services.execution_request import ExecutionRequest

_MOCK_SYSTEM = SystemSpec(
    base_mva=100.0,
    buses=[BusSpec(bus_id=1, base_kv=132.0, bus_type="slack")],
)


@pytest.mark.asyncio
class TestPilotCapabilityGating:
    """Verifies fail-closed server-side gating for PILOT status."""

    async def test_client_pilot_opt_in_cannot_bypass_disabled_feature_flag(self):
        """Client sending pilot_opt_in=True must still be rejected when server flag is OFF."""
        orchestrator = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="digital_twin",
            tenant_id="tenant_pilot_test",
            user_id="user_attacker",
            metadata={"pilot_opt_in": True, "allow_pilot": True},
            input={"system": _MOCK_SYSTEM, "pilot_opt_in": True},
            execution_policy="pilot",
            provider_policy="pilot",
        )

        with patch("api.feature_flags.is_strict_feature_enabled", return_value=False):
            res = await orchestrator.execute(req)
            assert res.success is False
            assert res.status == "rejected"
            assert (
                "PILOT_FEATURE_FLAG_DISABLED" in res.errors[0]
                or "pilot" in res.errors[0].lower()
            )

    async def test_client_allow_pilot_cannot_bypass_disabled_feature_flag(self):
        """Client sending allow_pilot in metadata must be rejected when server flag is OFF."""
        orchestrator = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="digital_twin",
            tenant_id="tenant_pilot_test",
            user_id="user_attacker",
            metadata={"allow_pilot": True},
            input={"system": _MOCK_SYSTEM},
        )

        with patch("api.feature_flags.is_strict_feature_enabled", return_value=False):
            res = await orchestrator.execute(req)
            assert res.success is False
            assert res.status == "rejected"
            assert "PILOT_FEATURE_FLAG_DISABLED" in res.errors[0] or "pilot" in res.errors[0].lower()

    async def test_client_execution_policy_pilot_cannot_bypass_disabled_flag(self):
        """Client setting execution_policy='pilot' must not enable pilot without server flag."""
        orchestrator = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="digital_twin",
            tenant_id="tenant_pilot_test",
            user_id="user_attacker",
            execution_policy="pilot",
            input={"system": _MOCK_SYSTEM},
        )

        with patch("api.feature_flags.is_strict_feature_enabled", return_value=False):
            res = await orchestrator.execute(req)
            assert res.success is False
            assert res.status == "rejected"

    async def test_server_flag_enabled_allows_pilot_capability(self):
        """When server feature flag is ON, PILOT capability is admitted."""
        from services.execution_orchestrator import CanonicalExecutionResult

        orchestrator = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="digital_twin",
            tenant_id="tenant_pilot_test",
            user_id="user_eng",
            input={"system": _MOCK_SYSTEM, "telemetry": {"v": 1.0}},
        )

        mock_res = CanonicalExecutionResult(
            execution_id=req.execution_id,
            request_id=req.request_id,
            capability_id=req.capability_id,
            capability_version="1.0.0",
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            executor_kind="agent",
            provider="agent",
            solver="DigitalTwinAgent",
            status="completed",
            success=True,
            data={"synced": True},
        )

        with patch("api.feature_flags.is_strict_feature_enabled", return_value=True):
            with patch.object(orchestrator.get_executor("agent"), "execute", return_value=mock_res):
                res = await orchestrator.execute(req)
                assert res.success is True
                assert res.status == "completed"

    async def test_dual_control_pilot_requires_both_flag_and_approval(self):
        """SCADA capability (PILOT with dual_control): must require flag AND verified approval."""
        orchestrator = ExecutionOrchestrator()

        # 1. Flag ON but NO approval context -> rejected
        req_no_approval = ExecutionRequest(
            capability_id="scada",
            tenant_id="tenant_pilot_test",
            user_id="user_eng",
            input={"system": _MOCK_SYSTEM},
        )
        with patch("api.feature_flags.is_strict_feature_enabled", return_value=True):
            res1 = await orchestrator.execute(req_no_approval)
            assert res1.success is False
            assert res1.status == "rejected"

        # 2. Flag OFF even with approval context -> rejected
        req_with_approval = ExecutionRequest(
            capability_id="scada",
            tenant_id="tenant_pilot_test",
            user_id="user_eng",
            approval_context={"approved": True, "approver": "lead_admin"},
            input={"system": _MOCK_SYSTEM},
        )
        with patch("api.feature_flags.is_strict_feature_enabled", return_value=False):
            res2 = await orchestrator.execute(req_with_approval)
            assert res2.success is False
            assert res2.status == "rejected"

    async def test_disabled_capability_fails_closed_regardless_of_client_inputs(self):
        """DISABLED capability (e.g. generative_design) cannot be enabled by client input or flags."""
        orchestrator = ExecutionOrchestrator()
        req = ExecutionRequest(
            capability_id="generative_design",
            tenant_id="tenant_pilot_test",
            user_id="user_attacker",
            metadata={"pilot_opt_in": True, "allow_pilot": True},
            execution_policy="pilot",
            input={"system": _MOCK_SYSTEM},
        )

        with patch("api.feature_flags.is_strict_feature_enabled", return_value=True):
            res = await orchestrator.execute(req)
            assert res.success is False
            assert res.status == "rejected"
            assert "CAPABILITY_DISABLED" in res.errors[0] or "disabled" in res.errors[0].lower()
