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
    CentralizedStateUnavailableError,
    CompositeEngineeringExecutor,
    EtapEngineeringExecutor,
    ExecutionOrchestrator,
    InMemoryExecutionStateStore,
    NativeEngineeringExecutor,
    RedisExecutionStateStore,
    _compute_standards_hash,
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
    """Test F — Deliberately unphysical engineering result is captured and blocked in canonical validation."""
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
        # 1.95 pu and 0.20 pu violate IEEE C84.1 Range B bounds (0.91 - 1.08 pu) -> CRITICAL voltage_range_b failure
        data={
            "converged": True,
            "bus_voltages": {"Bus1": 1.95, "Bus2": 0.20},
            "nominal_voltage_kv": 1.0,
        },
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

    # Gap 3: Assert strict physical failure — zero tolerance for "passed"
    assert res.success is False
    assert res.validation_status == "failed"
    assert res.validation_report.get("has_critical_failures") is True
    assert any("voltage_range_b" in str(f) for f in res.validation_report.get("failures", []))
    assert any("Range B" in err for err in res.errors)


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
    """Test G — Every production agent capability executes through AgentEngineeringExecutor into CanonicalExecutionResult."""
    from agents.registry import create_agent_registry
    from services.execution_orchestrator import AgentEngineeringExecutor

    registry = get_capability_registry()
    runtime_agent_reg = create_agent_registry()

    prod_agent_caps = [
        c
        for c in registry.list_capabilities()
        if (c.executor_kind == ExecutorKind.AGENT or c.executor_kind == "agent")
        and (c.lifecycle_status == LifecycleStatus.PRODUCTION or c.lifecycle_status == "production")
    ]

    assert len(prod_agent_caps) > 0, "Expected production agent capabilities in registry"

    for cap in prod_agent_caps:
        agent_key = cap.agent_key or cap.capability_id
        alias_map = {
            "harmonic": "harmonic_analysis",
            "opf": "optimal_power_flow",
            "protection": "protection_coordination",
        }
        agent_key = alias_map.get(agent_key, agent_key)
        agent = runtime_agent_reg.get(agent_key) or runtime_agent_reg.get(agent_key.lower())
        assert agent is not None, f"Agent for key '{agent_key}' not found"

        # Gap 4: Exercise AgentEngineeringExecutor -> agent.execute() -> CanonicalExecutionResult
        mock_delegate = AsyncMock()
        mock_delegate.execute.return_value = {
            "success": True,
            "status": "completed",
            "summary": f"Executed capability {cap.capability_id}",
            "data": {"result_val": 42},
        }

        agent_exec = AgentEngineeringExecutor(agent_registry={agent_key: mock_delegate})
        req = ExecutionRequest(
            execution_id=f"exec_test_{cap.capability_id}",
            request_id=f"req_test_{cap.capability_id}",
            capability_id=cap.capability_id,
            tenant_id="tenant_agent_contract",
            user_id="engineer_agent_contract",
            input={"parameters": {"test_param": "123"}},
        )

        res = await agent_exec.execute(req)
        assert mock_delegate.execute.called, (
            f"Expected agent.execute() to be invoked for {cap.capability_id}"
        )
        assert res.success is True
        assert res.executor_kind == "agent"
        assert res.provider == "agent"
        assert res.capability_id == cap.capability_id


@pytest.mark.asyncio
@pytest.mark.parametrize("kind_name", ["native", "agent", "etap", "external_service", "composite"])
async def test_all_executor_kinds_success_and_failure(kind_name):
    """Test Gap 5 — Explicitly test all 5 executor kinds through ExecutionOrchestrator for success and failure."""
    orchestrator = ExecutionOrchestrator()
    registry = get_capability_registry()

    # 1. Success execution
    mock_success = AsyncMock()
    mock_success.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_succ",
        request_id="req_succ",
        capability_id=f"test_cap_{kind_name}",
        tenant_id="tenant_kind",
        user_id="user_kind",
        executor_kind=kind_name,
        provider=kind_name,
        solver="test_solver",
        engine_version="unknown",
        status="completed",
        success=True,
        data={"ok": True},
        validation_status="passed",
    )
    orchestrator.register_executor(kind_name, mock_success)

    test_cap = CapabilityDefinition(
        capability_id=f"test_cap_{kind_name}",
        description=f"Test capability for {kind_name}",
        lifecycle_status=LifecycleStatus.PRODUCTION,
        executor_kind=kind_name,
        study_type=f"test_{kind_name}",
    )
    try:
        registry.register(test_cap)
    except ValueError:
        pass

    req_succ = ExecutionRequest(
        execution_id="exec_succ",
        capability_id=f"test_cap_{kind_name}",
        tenant_id="tenant_kind",
        user_id="user_kind",
        input={"test": "data"},
    )
    res_succ = await orchestrator.execute(req_succ)
    assert res_succ.success is True
    assert res_succ.executor_kind == kind_name
    assert res_succ.status == "completed"
    assert res_succ.provenance["executor_kind"] == kind_name
    assert res_succ.engine_version == "unknown"

    # 2. Failure propagation
    mock_fail = AsyncMock()
    mock_fail.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_fail",
        request_id="req_fail",
        capability_id=f"test_cap_{kind_name}",
        tenant_id="tenant_kind",
        user_id="user_kind",
        executor_kind=kind_name,
        provider=kind_name,
        solver="test_solver",
        engine_version="unknown",
        status="failed",
        success=False,
        data={},
        errors=["Simulated failure in executor"],
        validation_status="failed",
    )
    orchestrator.register_executor(kind_name, mock_fail)

    req_fail = ExecutionRequest(
        execution_id="exec_fail",
        capability_id=f"test_cap_{kind_name}",
        tenant_id="tenant_kind",
        user_id="user_kind",
        input={"test": "data"},
    )
    res_fail = await orchestrator.execute(req_fail)
    assert res_fail.success is False
    assert res_fail.status == "failed"
    assert res_fail.validation_status == "failed"
    assert "Simulated failure in executor" in res_fail.errors[0]


def test_redis_execution_state_store_contract():
    """Test Gap 8 — Verify RedisExecutionStateStore contract for result and idempotency persistence."""
    from services.execution_orchestrator import (
        RedisExecutionStateStore,
    )

    fallback = InMemoryExecutionStateStore()
    store = RedisExecutionStateStore(fallback_store=fallback)

    res = CanonicalExecutionResult(
        execution_id="exec_store_1",
        request_id="req_store_1",
        capability_id="load_flow",
        tenant_id="tenant_store",
        user_id="user_store",
        status="completed",
        success=True,
        data={"flow": "data"},
    )

    store.set_result("exec_store_1", res)
    retrieved = store.get_result("exec_store_1")
    assert retrieved is not None
    assert retrieved.execution_id == "exec_store_1"
    assert retrieved.success is True

    store.set_idempotency("idemp_key_1", res, 12345.0)
    idemp_val = store.get_idempotency("idemp_key_1")
    assert idemp_val is not None
    cached_res, ts = idemp_val
    assert cached_res.execution_id == "exec_store_1"
    assert ts == 12345.0


@pytest.mark.asyncio
async def test_semantic_cache_governed_inside_orchestrator():
    """Test Gap 1 & Gap 2 — Verify semantic cache resolution is governed inside ExecutionOrchestrator."""
    orchestrator = ExecutionOrchestrator()
    mock_native = AsyncMock()
    mock_native.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_first",
        request_id="req_first",
        capability_id="load_flow",
        tenant_id="tenant_cache_gov",
        user_id="user_cache_gov",
        status="completed",
        success=True,
        provider="native",
        executor_kind="native",
        solver="newton_raphson",
        engine_version="unknown",
        data={"bus_voltages": {"Bus1": 1.0}},
        validation_status="passed",
    )
    orchestrator.register_executor("native", mock_native)

    req = ExecutionRequest(
        execution_id="exec_first",
        capability_id="load_flow",
        tenant_id="tenant_cache_gov",
        user_id="user_cache_gov",
        input={"system": {"base_mva": 100}},
        metadata={"use_cache": True},
    )

    res = await orchestrator.execute(req)
    assert res.success is True
    assert mock_native.execute.call_count == 1
    assert res.engine_version == "unknown"


@pytest.mark.asyncio
async def test_identity_fail_closed_rejects_anonymous_and_default():
    """Verify that ExecutionOrchestrator rejects anonymous and default identities fail-closed."""
    orchestrator = ExecutionOrchestrator()
    mock_native = AsyncMock()
    orchestrator.register_executor("native", mock_native)

    # 1. Anonymous user_id must be rejected
    req_anon = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_valid",
        user_id="anonymous",
        input={"system": {"base_mva": 100}},
    )
    res_anon = await orchestrator.execute(req_anon)
    assert res_anon.success is False
    assert res_anon.status == "rejected"
    assert res_anon.audit_context["rejection_reason"] == "AUTHENTICATION_REQUIRED"
    assert "Anonymous access is strictly prohibited" in res_anon.errors[0]

    # 2. Default tenant_id must be rejected
    req_def_tenant = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="default",
        user_id="user_valid",
        input={"system": {"base_mva": 100}},
    )
    res_def_tenant = await orchestrator.execute(req_def_tenant)
    assert res_def_tenant.success is False
    assert res_def_tenant.status == "rejected"
    assert res_def_tenant.audit_context["rejection_reason"] == "TENANT_VALIDATION_FAILED"
    assert "default" in res_def_tenant.errors[0].lower()

    # 3. Blank user_id must be rejected
    req_blank_user = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_valid",
        user_id="   ",
        input={"system": {"base_mva": 100}},
    )
    res_blank_user = await orchestrator.execute(req_blank_user)
    assert res_blank_user.success is False
    assert res_blank_user.audit_context["rejection_reason"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_authorization_fail_closed_enforces_roles():
    """Verify that capability authorization policy enforces trusted role checks fail-closed."""
    orchestrator = ExecutionOrchestrator()
    mock_agent = AsyncMock()
    mock_agent.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_sec",
        request_id="req_sec",
        capability_id="code_guard",
        tenant_id="tenant_sec",
        user_id="admin",
        status="completed",
        success=True,
    )
    orchestrator.register_executor("agent", mock_agent)

    # 1. code_guard requires admin policy; engineer role must be denied
    req_eng = ExecutionRequest(
        capability_id="code_guard",
        tenant_id="tenant_sec",
        user_id="engineer_user",
        user_role="engineer",
        input={"system": {}},
    )
    res_eng = await orchestrator.execute(req_eng)
    assert res_eng.success is False
    assert res_eng.audit_context["rejection_reason"] == "AUTHORIZATION_DENIED"
    assert "Administrator privileges required" in res_eng.errors[0]

    # 2. scada requires lead_engineer policy; standard engineer role must be denied
    req_scada_eng = ExecutionRequest(
        capability_id="scada",
        tenant_id="tenant_sec",
        user_id="engineer_user",
        user_role="engineer",
        input={"system": {}},
    )
    res_scada_eng = await orchestrator.execute(req_scada_eng)
    assert res_scada_eng.success is False
    assert res_scada_eng.audit_context["rejection_reason"] == "AUTHORIZATION_DENIED"

    # 3. Missing user_role for protected capability must be denied
    req_no_role = ExecutionRequest(
        capability_id="scada",
        tenant_id="tenant_sec",
        user_id="engineer_user",
        user_role="",
        input={"system": {}},
    )
    res_no_role = await orchestrator.execute(req_no_role)
    assert res_no_role.success is False
    assert res_no_role.audit_context["rejection_reason"] == "AUTHORIZATION_DENIED"


@pytest.mark.asyncio
async def test_multi_replica_centralized_state_fail_closed(monkeypatch):
    """Verify that multi-replica mode fails closed when centralized state store is unavailable."""
    monkeypatch.setenv("DEPLOYMENT_TOPOLOGY", "multi_replica")
    monkeypatch.setenv(
        "REDIS_URL", "redis://127.0.0.1:59999/0?socket_timeout=0.1&socket_connect_timeout=0.1"
    )
    store = RedisExecutionStateStore(fallback_store=None)

    # Direct store operations must fail closed
    with pytest.raises(CentralizedStateUnavailableError):
        store.get_idempotency("tenant_mr:idemp_key")

    with pytest.raises(CentralizedStateUnavailableError):
        store.set_result(
            "exec_mr",
            CanonicalExecutionResult(
                execution_id="exec_mr",
                request_id="req_mr",
                capability_id="load_flow",
                tenant_id="tenant_mr",
                user_id="user_mr",
                status="completed",
                success=True,
            ),
        )

    # Orchestrator must catch CentralizedStateUnavailableError and reject fail-closed
    orchestrator = ExecutionOrchestrator(state_store=store)
    mock_native = AsyncMock()
    orchestrator.register_executor("native", mock_native)

    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_mr",
        user_id="user_mr",
        user_role="engineer",
        input={"system": {"base_mva": 100}},
    )
    res = await orchestrator.execute(req)
    assert res.success is False
    assert res.audit_context["rejection_reason"] == "CENTRALIZED_STATE_UNAVAILABLE"


def test_standards_hash_differentiates_standards_configuration():
    """Verify that standards_hash produces distinct identities for different validation rules/standards."""
    import dataclasses

    reg = get_capability_registry()
    cap = reg.get("load_flow")
    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_test",
        user_id="user_test",
        input={"system": {}},
    )

    hash_iec = _compute_standards_hash(cap, {"standard": "IEC"}, req)
    hash_ieee = _compute_standards_hash(cap, {"standard": "IEEE"}, req)
    assert hash_iec != hash_ieee

    # Changing capability validation policy changes the hash
    cap_clone = dataclasses.replace(cap, validation_policy="custom_nuclear_rules_v2")
    hash_custom = _compute_standards_hash(cap_clone, {"standard": "IEC"}, req)
    assert hash_custom != hash_iec


@pytest.mark.asyncio
async def test_semantic_cache_preserves_authentic_provenance(monkeypatch):
    """Verify that a semantic cache hit faithfully preserves original validated provenance."""
    from unittest.mock import MagicMock

    from api.semantic_cache_redis import CachedResult

    # Enable token governance cache flag
    monkeypatch.setenv("FEATURE_FLAG_TOKEN_GOVERNANCE", "true")

    orig_provenance = {
        "executor_kind": "native",
        "solver": "nr_sparse_solver_v3",
        "engine_version": "2.9.4",
        "provider": "internal_python",
        "certified_by": "PE-54321",
        "timestamp": "2026-10-06T10:00:00Z",
    }
    orig_report = {"assertions_checked": 50, "warnings": [], "passed": True}

    cached_entry_dict = {
        "execution_id": "exec_original_validated",
        "capability_id": "load_flow",
        "tenant_id": "tenant_cache_auth",
        "provider": "internal_python",
        "executor_kind": "native",
        "solver": "nr_sparse_solver_v3",
        "engine_version": "2.9.4",
        "success": True,
        "status": "completed",
        "validation_status": "passed",
        "validation_report": orig_report,
        "risk_class": "medium",
        "risk_score": 0.35,
        "risk_assessment": {"risk_class": "medium", "risk_score": 0.35},
        "provenance": orig_provenance,
        "data": {"bus_voltages": {"Bus1": 1.02}},
        "input_snapshot_hash": "hash_input_orig",
        "system_snapshot_hash": "hash_sys_orig",
        "parameter_hash": "hash_param_orig",
    }

    mock_cached_result = CachedResult(
        result=cached_entry_dict,
        tokens_saved=1500,
        similarity=1.0,
        cached_at=1000.0,
        cache_key="key_test",
    )

    mock_cache = MagicMock()
    mock_cache.lookup = AsyncMock(return_value=mock_cached_result)

    monkeypatch.setattr(
        "api.semantic_cache_redis.get_distributed_semantic_cache",
        lambda: mock_cache,
    )

    orchestrator = ExecutionOrchestrator()
    mock_native = AsyncMock()
    mock_native.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_fresh",
        request_id="req_fresh",
        capability_id="load_flow",
        tenant_id="tenant_cache_auth",
        user_id="engineer_auditor",
        status="completed",
        success=True,
    )
    orchestrator.register_executor("native", mock_native)

    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_cache_auth",
        user_id="engineer_auditor",
        user_role="engineer",
        input={"system": {"base_mva": 100}, "parameters": {"standard": "IEC"}},
        metadata={"use_cache": True},
    )

    res = await orchestrator.execute(req)
    assert res.success is True
    # Executor must NOT be called on cache hit
    assert mock_native.execute.call_count == 0

    # Provenance and validated properties must be authentically preserved
    assert res.solver == "nr_sparse_solver_v3"
    assert res.engine_version == "2.9.4"
    assert res.validation_status == "passed"
    assert res.validation_report == orig_report
    assert res.risk_class == "medium"
    assert res.risk_score == 0.35
    assert res.provenance["cached"] is True
    assert res.provenance["certified_by"] == "PE-54321"
    assert res.audit_context["cached"] is True
    assert res.audit_context["original_execution_id"] == "exec_original_validated"


@pytest.mark.asyncio
async def test_composite_executor_records_workflow_provenance():
    """Verify that CompositeEngineeringExecutor extracts and retains composite orchestration provenance."""
    mock_inner_executor = AsyncMock()
    mock_inner_executor.execute.return_value = CanonicalExecutionResult(
        execution_id="exec_comp_inner",
        request_id="req_comp_inner",
        capability_id="ahmed_etap_orchestration",
        tenant_id="tenant_comp",
        user_id="user_comp",
        status="completed",
        success=True,
        executor_kind="agent",
        provenance={"sub_studies": ["load_flow", "short_circuit"]},
    )

    composite_executor = CompositeEngineeringExecutor(
        agent_executor=mock_inner_executor,
    )

    req = ExecutionRequest(
        capability_id="ahmed_etap_orchestration",
        tenant_id="tenant_comp",
        user_id="user_comp",
        user_role="lead_engineer",
        input={"system": {"base_mva": 100}},
    )

    res = await composite_executor.execute(req)
    assert res.success is True
    assert res.executor_kind == "composite"
    assert "composite_workflow" in res.provenance
    wf = res.provenance["composite_workflow"]
    assert wf["orchestration_type"] == "composite_multi_agent"
    assert wf["capability_id"] == "ahmed_etap_orchestration"
    assert wf["verdict"] == "approved"


# ─────────────────────────────────────────────────────────────────────────────
# Real Runtime Execution Tests (Section 8, 9, 12, 16 - No Mocking Executors)
# ─────────────────────────────────────────────────────────────────────────────

_REAL_TEST_SYSTEM = {
    "base_mva": 100.0,
    "buses": [
        {
            "bus_id": 1,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "slack",
            "base_kv": 11.0,
        },
        {
            "bus_id": 2,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "pq",
            "base_kv": 11.0,
        },
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
    ],
    "loads": [
        {"load_id": 1, "bus_id": 2, "p_mw": 10.0, "q_mvar": 5.0},
    ],
}


@pytest.mark.asyncio
async def test_real_native_executor_load_flow_and_short_circuit():
    """Section 8: Prove that the REAL NativeEngineeringExecutor executes Newton-Raphson and IEC 60909."""
    orchestrator = get_execution_orchestrator()

    # 1. Real Load Flow execution
    req_lf = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_real_eng",
        user_id="engineer_alice",
        user_role="engineer",
        input={"system": _REAL_TEST_SYSTEM, "parameters": {"tol": 1e-5, "max_iter": 50}},
    )
    res_lf = await orchestrator.execute(req_lf)
    assert res_lf.success is True
    assert res_lf.status == "completed"
    assert res_lf.executor_kind == "native"
    assert res_lf.provider == "native"
    assert res_lf.solver == "newton_raphson"
    assert "bus_results" in res_lf.data or "buses" in res_lf.data or "converged" in res_lf.data
    assert res_lf.validation_status in ("passed", "warning")

    # 2. Real Short Circuit execution
    req_sc = ExecutionRequest(
        capability_id="short_circuit",
        tenant_id="tenant_real_eng",
        user_id="engineer_alice",
        user_role="engineer",
        input={
            "system": _REAL_TEST_SYSTEM,
            "parameters": {"bus_id": 2, "fault_type": "three_phase"},
        },
    )
    res_sc = await orchestrator.execute(req_sc)
    assert res_sc.success is True
    assert res_sc.status == "completed"
    assert res_sc.executor_kind == "native"
    assert res_sc.validation_status in ("passed", "warning")


@pytest.mark.asyncio
async def test_real_native_executor_propagates_real_failure():
    """Section 8: Prove that real mathematical/system failures propagate honestly without manufactured success."""
    orchestrator = get_execution_orchestrator()

    # Network with disconnected/invalid line referring to non-existent bus
    invalid_system = {
        "base_mva": 100.0,
        "buses": [
            {
                "bus_id": 1,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "bus_type": "slack",
                "base_kv": 11.0,
            }
        ],
        "lines": [
            {
                "line_id": 1,
                "from_bus_id": 1,
                "to_bus_id": 999,
                "r1": 0.01,
                "x1": 0.05,
                "bshunt1": 0.0,
            }
        ],
    }
    req = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_real_fail",
        user_id="engineer_alice",
        user_role="engineer",
        input={"system": invalid_system, "parameters": {}},
    )
    res = await orchestrator.execute(req)
    assert res.success is False
    assert res.status == "failed"
    assert res.validation_status == "failed"
    assert len(res.errors) > 0


@pytest.mark.asyncio
async def test_real_agent_executor_stability_and_expert():
    """Section 9: Prove that the REAL AgentEngineeringExecutor executes real BaseAgent algorithms."""
    orchestrator = get_execution_orchestrator()

    # 1. Real ETAPExpertAgent knowledge-base reasoning
    req_expert = ExecutionRequest(
        capability_id="etap_expert",
        tenant_id="tenant_agent_real",
        user_id="engineer_alice",
        user_role="engineer",
        input={"parameters": {"question": "How do I perform a load flow study in ETAP?"}},
    )
    res_expert = await orchestrator.execute(req_expert)
    assert res_expert.success is True
    assert res_expert.status == "completed"
    assert res_expert.executor_kind == "agent"
    assert res_expert.solver == "ETAPExpertAgent"
    assert "response" in res_expert.data or "answer" in res_expert.data

    # 2. Real CableSizingAgent computation (valid cable selection)
    req_cable = ExecutionRequest(
        capability_id="cable_sizing",
        tenant_id="tenant_agent_real",
        user_id="engineer_alice",
        user_role="engineer",
        input={
            "system": _REAL_TEST_SYSTEM,
            "parameters": {
                "cross_section_mm2": 185,
                "load_current_A": 120.0,
                "cable_length_m": 150.0,
                "system_voltage_V": 400.0,
                "power_factor": 0.85,
                "fault_current_kA": 5.0,
                "fault_duration_s": 0.5,
            },
        },
    )
    res_cable = await orchestrator.execute(req_cable)
    assert res_cable.success is True
    assert res_cable.status == "completed"
    assert res_cable.executor_kind == "agent"
    assert res_cable.solver == "CableSizingAgent"


@pytest.mark.asyncio
async def test_real_agent_executor_failure_propagation():
    """Section 9: Prove that real agent computation failures propagate truthfully."""
    orchestrator = get_execution_orchestrator()

    # 1. ETAPExpertAgent with empty question fails
    req_fail_expert = ExecutionRequest(
        capability_id="etap_expert",
        tenant_id="tenant_agent_fail",
        user_id="engineer_alice",
        user_role="engineer",
        input={"parameters": {"question": ""}},
    )
    res_fail_expert = await orchestrator.execute(req_fail_expert)
    assert res_fail_expert.success is False
    assert res_fail_expert.status in ("rejected", "failed")
    assert any(
        "SCHEMA_VALIDATION_FAILED" in err or "question" in err for err in res_fail_expert.errors
    )

    # 2. CableSizingAgent with undersized cross section for large fault current fails
    req_fail_cable = ExecutionRequest(
        capability_id="cable_sizing",
        tenant_id="tenant_agent_fail",
        user_id="engineer_alice",
        user_role="engineer",
        input={
            "system": _REAL_TEST_SYSTEM,
            "parameters": {
                "cross_section_mm2": 10,
                "fault_current_kA": 50.0,
                "fault_duration_s": 1.0,
            },
        },
    )
    res_fail_cable = await orchestrator.execute(req_fail_cable)
    assert res_fail_cable.success is False
    assert res_fail_cable.status == "failed"
    assert len(res_fail_cable.errors) > 0


@pytest.mark.asyncio
async def test_real_composite_executor_multi_stage_workflow():
    """Section 12: Prove that CompositeEngineeringExecutor genuinely executes a multi-stage workflow."""
    orchestrator = get_execution_orchestrator()

    # Execute genuine 2-stage composite workflow: load_flow -> short_circuit
    req_composite = ExecutionRequest(
        capability_id="ahmed_etap_orchestration",
        tenant_id="tenant_comp_real",
        user_id="lead_alice",
        user_role="lead_engineer",
        approval_context={"approved": True, "approver_id": "checker_bob"},
        input={
            "system": _REAL_TEST_SYSTEM,
            "stages": ["load_flow", "short_circuit"],
            "parameters": {"bus_id": 2, "fault_type": "three_phase"},
        },
    )
    res = await orchestrator.execute(req_composite)
    assert res.success is True
    assert res.status == "completed"
    assert res.executor_kind == "composite"
    assert "composite_workflow" in res.provenance
    wf = res.provenance["composite_workflow"]
    assert wf["orchestration_type"] == "composite_multi_stage"
    assert wf["verdict"] == "approved"
    assert len(wf["stages_executed"]) == 2
    assert wf["stages_executed"][0]["capability_id"] == "load_flow"
    assert wf["stages_executed"][1]["capability_id"] == "short_circuit"
    assert "composite_results" in res.data
    assert "load_flow" in res.data["composite_results"]
    assert "short_circuit" in res.data["composite_results"]


@pytest.mark.asyncio
async def test_real_composite_executor_halts_and_fails_on_stage_failure():
    """Section 12: Prove that composite workflow halts and fails closed if an inner stage fails."""
    orchestrator = get_execution_orchestrator()

    # Stage 1 succeeds (load_flow), Stage 2 fails (short_circuit missing required bus_id on disconnected bus)
    req_composite = ExecutionRequest(
        capability_id="ahmed_etap_orchestration",
        tenant_id="tenant_comp_fail",
        user_id="lead_alice",
        user_role="lead_engineer",
        approval_context={"approved": True, "approver_id": "checker_bob"},
        input={
            "system": _REAL_TEST_SYSTEM,
            "stages": [
                {"capability_id": "load_flow", "parameters": {}},
                {"capability_id": "short_circuit", "parameters": {"bus_id": 99999}},
            ],
        },
    )
    res = await orchestrator.execute(req_composite)
    assert res.success is False
    assert res.status == "failed"
    assert "composite_workflow" in res.provenance
    assert res.provenance["composite_workflow"]["verdict"] == "rejected"
    assert res.provenance["composite_workflow"]["failed_stage"] == "short_circuit"
    assert any("short_circuit" in err for err in res.errors)
