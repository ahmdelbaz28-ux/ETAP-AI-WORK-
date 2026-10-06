from unittest.mock import AsyncMock, Mock, patch

import pytest

from core_model.specs import StudyResult
from services.execution_orchestrator import ExecutionOrchestrator
from services.execution_request import ExecutionRequest


@pytest.mark.asyncio
async def test_canonical_executor_is_gateway():
    """Test that ExecutionOrchestrator is the sole gateway for engineering execution."""
    mock_native = AsyncMock()
    mock_result = StudyResult(
        execution_id="exec_1",
        request_id="req_1",
        tenant_id="tenant_1",
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
        result={"voltage": 1.0},
        validation_status=True,
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
        approval_state=None
    )
    mock_native.execute.return_value = mock_result
    mock_native.execute_native = mock_native.execute

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
    # Verify that the native executor was called
    mock_native.execute_native.assert_called_once()

def test_execution_request_contains_required_fields():
    """Test that ExecutionRequest contains all required fields."""
    request = ExecutionRequest(
        capability_id="load_flow",
        tenant_id="tenant_1",
        user_id="user_1",
        input={"test": "data"},
    )
    assert hasattr(request, 'execution_id')
    assert hasattr(request, 'request_id')
    assert hasattr(request, 'tenant_id')
    assert hasattr(request, 'user_id')
    assert hasattr(request, 'capability_id')
    assert hasattr(request, 'capability_version')
    assert hasattr(request, 'input')
    assert hasattr(request, 'system_snapshot')
    assert hasattr(request, 'provider_policy')
    assert hasattr(request, 'execution_policy')
    assert hasattr(request, 'approval_context')
    assert hasattr(request, 'idempotency_key')
    assert hasattr(request, 'trace_id')
    assert hasattr(request, 'metadata')

def test_canonical_result_contains_required_fields():
    """Test that StudyResult (CanonicalExecutionResult) contains all required fields."""
    result = StudyResult(
        execution_id="exec_1",
        request_id="req_1",
        tenant_id="tenant_1",
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
        result={"voltage": 1.0},
        validation_status=True,
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
        approval_state=None
    )
    assert result.execution_id == "exec_1"
    assert result.tenant_id == "tenant_1"
    assert result.capability_id == "load_flow"
    assert result.provider == "native"
    assert result.executor_kind == "native"
    assert result.validation_status is True
    assert result.risk_class == "low"
