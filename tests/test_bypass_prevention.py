from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.dependencies import CurrentUser
from api.studies import run_study
from services.execution_request import CanonicalExecutionResult, ExecutionRequest


@pytest.mark.asyncio
async def test_api_studies_runs_via_orchestrator():
    """Test that POST /api/v1/studies/run goes through ExecutionOrchestrator (Test A)."""
    with patch("api.studies.get_execution_orchestrator") as mock_get_orchestrator:
        mock_orchestrator = Mock()
        mock_get_orchestrator.return_value = mock_orchestrator
        mock_canonical_res = CanonicalExecutionResult(
            execution_id="exec_1",
            request_id="req_1",
            tenant_id="tenant_1",
            user_id="user_1",
            capability_id="LOAD_FLOW",
            status="completed",
            success=True,
            provider="native",
            executor_kind="native",
            solver="newton_raphson",
            result={"converged": True, "voltages": {}},
            validation_status="passed",
            errors=[],
            warnings=[],
        )
        mock_orchestrator.execute = AsyncMock(return_value=mock_canonical_res)

        payload = {
            "study_type": "LOAD_FLOW",
            "parameters": {},
            "system": {"base_mva": 100, "buses": [], "lines": []},
        }
        result = await run_study(payload, user_id="user_1", tenant_id="tenant_1")

        mock_get_orchestrator.assert_called()
        mock_orchestrator.execute.assert_called_once()
        args, kwargs = mock_orchestrator.execute.call_args
        req = args[0]
        assert isinstance(req, ExecutionRequest)
        assert req.capability_id.upper() == "LOAD_FLOW"
        assert req.tenant_id == "tenant_1"
        assert req.user_id == "user_1"
        assert result.success is True
        assert result.provider == "native"


@pytest.mark.asyncio
async def test_no_api_direct_power_system_engine_execution():
    """Test that the API layer does not directly call PowerSystemEngine (Test B)."""
    with patch("engine.engine.PowerSystemEngine") as mock_engine_cls, \
         patch("api.studies.get_execution_orchestrator") as mock_get_orchestrator:

        mock_orchestrator = Mock()
        mock_get_orchestrator.return_value = mock_orchestrator
        mock_canonical_res = CanonicalExecutionResult(
            execution_id="exec_2",
            request_id="req_2",
            tenant_id="tenant_2",
            user_id="user_2",
            capability_id="LOAD_FLOW",
            status="completed",
            success=True,
            provider="native",
            executor_kind="native",
            result={"converged": True},
            validation_status="passed",
            errors=[],
            warnings=[],
        )
        mock_orchestrator.execute = AsyncMock(return_value=mock_canonical_res)

        payload = {
            "study_type": "LOAD_FLOW",
            "parameters": {},
            "system": {"base_mva": 100, "buses": [], "lines": []},
        }
        await run_study(payload, user_id="user_2", tenant_id="tenant_2")

        # Prove the API layer did NOT instantiate PowerSystemEngine directly
        mock_engine_cls.assert_not_called()


@pytest.mark.asyncio
async def test_study_execution_service_re_run_uses_canonical_orchestrator():
    """Test that execute_study_re_run traverses the canonical orchestrator."""
    from api.services.study_execution_service import execute_study_re_run

    mock_db = AsyncMock()
    mock_project = Mock()
    mock_project.id = "proj_1"
    mock_project.tenant_id = "tenant_alpha"
    mock_project.created_by = "user_rerun"
    mock_project.system_config = {"base_mva": 100, "buses": [], "lines": []}
    mock_scalar = Mock()
    mock_scalar.scalar_one_or_none.return_value = mock_project
    mock_scalar.scalar.return_value = 1
    mock_db.execute = AsyncMock(return_value=mock_scalar)

    with patch("api.services.study_execution_service.save_solver_params", new=AsyncMock()), \
         patch("services.execution_orchestrator.get_execution_orchestrator") as mock_get_orch:
        mock_orch = Mock()
        mock_get_orch.return_value = mock_orch
        mock_res = CanonicalExecutionResult(
            execution_id="exec_rerun",
            request_id="req_rerun",
            tenant_id="tenant_alpha",
            user_id="user_rerun",
            capability_id="SHORT_CIRCUIT",
            status="completed",
            success=True,
            provider="native",
            executor_kind="native",
            result={"ik_ss": 10.0},
            validation_status="passed",
            errors=[],
            warnings=[],
        )
        mock_orch.execute = AsyncMock(return_value=mock_res)

        user = CurrentUser(
            user_id="user_rerun",
            username="rerunner",
            email="rerunner@example.com",
            tenant_id="tenant_alpha",
            role="engineer",
        )
        output = await execute_study_re_run(
            project_id="proj_1",
            tool="short_circuit",
            params={"system": {"base_mva": 100, "buses": [], "lines": []}},
            user=user,
            db=mock_db,
        )

        mock_get_orch.assert_called()
        mock_orch.execute.assert_called_once()
        exec_req = mock_orch.execute.call_args[0][0]
        assert isinstance(exec_req, ExecutionRequest)
        assert exec_req.tenant_id == "tenant_alpha"
        assert exec_req.user_id == "user_rerun"
        assert output["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_executor_canonical_tool_uses_canonical_orchestrator():
    """Test that _canonical_orchestrator_executor traverses the canonical orchestrator (Test C)."""
    from api.agent_executor import _canonical_orchestrator_executor

    with patch("services.execution_orchestrator.get_execution_orchestrator") as mock_get_orch:
        mock_orch = Mock()
        mock_get_orch.return_value = mock_orch
        mock_res = CanonicalExecutionResult(
            execution_id="exec_agent_tool",
            request_id="req_agent_tool",
            tenant_id="tenant_tool",
            user_id="engineer_1",
            capability_id="SHORT_CIRCUIT",
            status="completed",
            success=True,
            provider="native",
            executor_kind="native",
            result={"ik_ss": 12.5},
            validation_status="passed",
            errors=[],
            warnings=[],
        )
        mock_orch.execute = AsyncMock(return_value=mock_res)

        args = {
            "capability_id": "SHORT_CIRCUIT",
            "goal": "Fault analysis",
            "parameters": {"fault_type": "3phase"},
            "system": {"base_mva": 100, "buses": [], "lines": []},
        }
        ctx = {
            "tenant_id": "tenant_tool",
            "user_id": "engineer_1",
            "execution_id": "exec_ctx_1",
        }
        tool_res = await _canonical_orchestrator_executor(args, ctx)

        assert tool_res["status"] == "completed"
        assert tool_res["authoritative"] is True
        assert tool_res["execution_mode"] == "canonical_orchestrator"
        mock_orch.execute.assert_called_once()
        exec_req = mock_orch.execute.call_args[0][0]
        assert isinstance(exec_req, ExecutionRequest)
        assert exec_req.tenant_id == "tenant_tool"
        assert exec_req.capability_id == "SHORT_CIRCUIT"
