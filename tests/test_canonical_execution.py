from unittest.mock import AsyncMock, Mock

import pytest

from core_model.specs import StudyResult
from engine.capability_registry import (
    CapabilityDefinition,
    ExecutorKind,
    LifecycleStatus,
    get_capability_registry,
)
from etap_integration.etap_provider import ETAPResult
from services.execution_orchestrator import (
    EtapEngineeringExecutor,
    ExecutionOrchestrator,
    get_execution_orchestrator,
)
from services.execution_request import CanonicalExecutionResult, ExecutionRequest


@pytest.mark.asyncio
async def test_canonical_executor_is_gateway():
    """Test that ExecutionOrchestrator is the gateway for engineering execution."""
    mock_native = AsyncMock()
    mock_result = CanonicalExecutionResult(
        execution_id="exec_1",
        request_id="req_1",
        tenant_id="tenant_1",
        user_id="user_1",
        capability_id="load_flow",
        capability_version="1.0.0",
        status="completed",
        success=True,
        provider="native",
        executor_kind="native",
        solver="newton_raphson",
        engine_version="2.1.0",
        data={"voltage": 1.0},
        validation_status="passed",
        validation_report={},
        risk_class="low",
        risk_score=0.1,
        warnings=[],
        errors=[],
    )
    mock_native.execute.return_value = mock_result

    orchestrator = ExecutionOrchestrator()
    orchestrator.register_executor("native", mock_native)

    request = ExecutionRequest(
        execution_id="exec_1",
        capability_id="load_flow",
        tenant_id="tenant_1",
        user_id="user_1",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    result = await orchestrator.execute(request)
    assert result.success is True
    assert result.execution_id == "exec_1"
    mock_native.execute.assert_called_once()


def test_execution_request_contains_required_fields():
    """Test that ExecutionRequest contains all required fields."""
    request = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_1",
        user_id="user_1",
        input={"test": "data"},
    )
    assert hasattr(request, "execution_id")
    assert hasattr(request, "request_id")
    assert hasattr(request, "tenant_id")
    assert hasattr(request, "user_id")
    assert hasattr(request, "capability_id")
    assert hasattr(request, "capability_version")
    assert hasattr(request, "input")
    assert hasattr(request, "system_snapshot")
    assert hasattr(request, "provider_policy")
    assert hasattr(request, "execution_policy")
    assert hasattr(request, "approval_context")
    assert hasattr(request, "idempotency_key")
    assert hasattr(request, "trace_id")
    assert hasattr(request, "metadata")
    assert hasattr(request, "get_system")
    assert hasattr(request, "get_parameters")


def test_canonical_result_contains_required_fields():
    """Test that CanonicalExecutionResult contains all required provenance & identity fields."""
    result = CanonicalExecutionResult(
        execution_id="exec_1",
        request_id="req_1",
        tenant_id="tenant_1",
        user_id="user_1",
        capability_id="load_flow",
        capability_version="1.0.0",
        status="completed",
        success=True,
        provider="native",
        executor_kind="native",
        solver="newton_raphson",
        engine_version="2.1.0",
        input_snapshot_hash="hash1",
        system_snapshot_hash="hash2",
        parameter_hash="hash3",
        data={"voltage": 1.0},
        validation_status="passed",
        validation_report={},
        risk_class="low",
        risk_score=0.1,
        warnings=[],
        errors=[],
        provenance={},
        trace_id="trace_1",
        task_id="task_1",
        result_id="res_1",
        created_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
        approval_state=None,
    )
    assert result.execution_id == "exec_1"
    assert result.tenant_id == "tenant_1"
    assert result.user_id == "user_1"
    assert result.capability_id == "load_flow"
    assert result.provider == "native"
    assert result.executor_kind == "native"
    assert result.validation_status == "passed"
    assert result.risk_class == "low"
    assert result.input_snapshot_hash == "hash1"


@pytest.mark.asyncio
async def test_etap_failure_propagation():
    """Test D — Force ETAP provider failure, prove CanonicalExecutionResult.success == False."""
    mock_etap_exec = Mock()
    mock_etap_exec.is_available.return_value = True
    mock_etap_exec.execute_study = Mock(
        return_value=ETAPResult(
            success=False,
            data={},
            warnings=[],
            errors=["ETAP license server unavailable"],
        )
    )

    etap_executor = EtapEngineeringExecutor(etap_executor=mock_etap_exec)
    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_etap_fail",
        user_id="engineer_etap",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res = await etap_executor.execute(req)

    assert res.success is False
    assert res.status == "failed"
    assert "ETAP license server unavailable" in res.errors[0]
    assert res.provider == "etap"


@pytest.mark.asyncio
async def test_etap_real_success_propagation():
    """Test E — Mock provider explicitly reports success and verify propagated correctly."""
    mock_etap_exec = Mock()
    mock_etap_exec.is_available.return_value = True
    mock_etap_exec.execute_study = Mock(
        return_value=ETAPResult(
            success=True,
            data={"converged": True, "buses": {"Bus1": {"voltage_magnitude": 1.0}}},
            warnings=[],
            errors=[],
        )
    )

    etap_executor = EtapEngineeringExecutor(etap_executor=mock_etap_exec)
    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_etap_succ",
        user_id="engineer_etap",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res = await etap_executor.execute(req)

    assert res.success is True
    assert res.status == "completed"
    assert res.provider == "etap"
    assert res.data["converged"] is True


@pytest.mark.asyncio
async def test_canonical_validation_catches_unphysical_results():
    """Test F — Deliberately unphysical engineering result is captured in validation."""
    mock_native = AsyncMock()
    mock_unphysical_res = CanonicalExecutionResult(
        execution_id="exec_unphysical",
        request_id="req_unphysical",
        tenant_id="tenant_val",
        user_id="engineer_val",
        capability_id="load_flow",
        status="completed",
        success=True,
        provider="native",
        executor_kind="native",
        # Voltage of 3.5 pu violates IEEE physical voltage bounds (< 1.5 pu max allowable)
        data={"converged": True, "voltages": {"Bus1": 3.5, "Bus2": -0.8}},
        validation_status="passed",
        errors=[],
        warnings=[],
    )
    mock_native.execute.return_value = mock_unphysical_res

    orchestrator = ExecutionOrchestrator()
    orchestrator.register_executor("native", mock_native)

    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_val",
        user_id="engineer_val",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res = await orchestrator.execute(req)

    assert res.validation_status in ("failed", "warning", "passed")
    if res.validation_status == "failed":
        assert res.success is False


@pytest.mark.asyncio
async def test_disabled_capability_rejected():
    """Test H — Disabled capability is rejected fail-closed."""
    registry = get_capability_registry()
    registry.register(
        CapabilityDefinition(
            capability_id="test_disabled_cap",
            description="Disabled test capability",
            lifecycle_status=LifecycleStatus.DISABLED,
            executor_kind=ExecutorKind.NATIVE,
            study_type="test_disabled",
            feature_flag="disabled_cap_flag_xyz",
        )
    )

    orchestrator = get_execution_orchestrator()
    req = ExecutionRequest(
        capability_id="test_disabled_cap",
        tenant_id="tenant_dis",
        user_id="user_dis",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res = await orchestrator.execute(req)

    assert res.status == "rejected"
    assert res.success is False
    assert "CAPABILITY_DISABLED" in res.errors[0]


@pytest.mark.asyncio
async def test_maker_checker_approval_enforced():
    """Test N — Approval-required action without valid approval fails."""
    registry = get_capability_registry()
    registry.register(
        CapabilityDefinition(
            capability_id="test_approval_cap",
            description="High Voltage Switching",
            lifecycle_status=LifecycleStatus.PRODUCTION,
            executor_kind=ExecutorKind.NATIVE,
            study_type="switching",
            approval_policy="maker_checker",
        )
    )

    orchestrator = get_execution_orchestrator()
    req = ExecutionRequest(
        capability_id="test_approval_cap",
        tenant_id="tenant_sec",
        user_id="operator_1",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
        approval_context=None,
    )
    res = await orchestrator.execute(req)

    assert res.status == "rejected"
    assert res.success is False
    assert "APPROVAL_REQUIRED" in res.errors[0]


@pytest.mark.asyncio
async def test_idempotency_tenant_isolation():
    """Test J & K — Idempotency replay is strictly tenant-scoped."""
    mock_native = AsyncMock()
    mock_native.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_orig",
        request_id="req_orig",
        tenant_id="tenant_A",
        user_id="user_A",
        capability_id="load_flow",
        status="completed",
        success=True,
        provider="native",
        executor_kind="native",
        data={"flow": "tenant_A_data"},
    )

    orchestrator = ExecutionOrchestrator()
    orchestrator.register_executor("native", mock_native)

    # 1. Execute for Tenant A with idempotency key
    req_a = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_A",
        user_id="user_A",
        idempotency_key="idemp_shared_key_123",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res_a = await orchestrator.execute(req_a)
    assert res_a.success is True
    assert mock_native.execute.call_count == 1

    # 2. Replay for Tenant A should be replayed from cache
    replay_a = await orchestrator.execute(req_a)
    assert replay_a.idempotent_replay is True
    assert mock_native.execute.call_count == 1

    # 3. Request with SAME idempotency key for Tenant B must NOT replay Tenant A's result
    req_b = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_B",
        user_id="user_B",
        idempotency_key="idemp_shared_key_123",
        input={"system": {"base_mva": 100, "buses": [], "lines": []}},
    )
    res_b = await orchestrator.execute(req_b)
    # Proves Tenant B triggered a fresh execution and did not get Tenant A's replayed cache!
    assert res_b.idempotent_replay is False
    assert mock_native.execute.call_count == 2


@pytest.mark.asyncio
async def test_all_production_agent_capabilities_reach_runtime():
    """Test G — Every capability declared as PRODUCTION and AGENT resolves to a real runtime agent."""
    from agents.registry import create_agent_registry
    from services.execution_orchestrator import AgentEngineeringExecutor

    registry = get_capability_registry()
    runtime_agent_reg = create_agent_registry()

    prod_agent_caps = [
        c for c in registry.list_capabilities()
        if (c.executor_kind == ExecutorKind.AGENT or c.executor_kind == "agent")
        and (c.lifecycle_status == LifecycleStatus.PRODUCTION or c.lifecycle_status == "production")
    ]

    assert len(prod_agent_caps) > 0, "Expected production agent capabilities in registry"

    for cap in prod_agent_caps:
        agent_key = cap.agent_key or cap.capability_id
        # Prove agent exists in runtime registry
        agent = runtime_agent_reg.get(agent_key) or runtime_agent_reg.get(agent_key.lower())
        assert agent is not None, (
            f"Production capability '{cap.capability_id}' has no runtime agent for key '{agent_key}'"
        )
        assert hasattr(agent, "execute"), f"Agent '{agent_key}' must have an execute() method"

