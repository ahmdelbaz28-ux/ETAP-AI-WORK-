"""
tests/test_optimization_agent_construct.py — Verification of OptimizationAgent and StudyExecutor imports.

Windows-safe, completely offline, zero network access.
Verifies:
1. OptimizationAgent.execute() with unsupported type returns AgentStatus.FAILED without AttributeError / TypeError.
2. OptimizationAgent.execute() on success returns AgentStatus.COMPLETED with valid data and zero errors.
3. OptimizationAgent.execute() on exception handles errors gracefully with AgentStatus.FAILED.
4. services/study_executor.py:464 imports get_orchestrator from agents.orchestrator without ImportError.
"""

from __future__ import annotations

import pytest

from agents.models import AgentStatus, EngineeringTask, StudyType
from agents.optimizers.optimization_agent import OptimizationAgent


@pytest.mark.asyncio
async def test_optimization_agent_unsupported_type():
    """Verify that calling execute() with an unsupported optimization type

    returns AgentStatus.FAILED cleanly without raising AttributeError (e.g. task.id or AgentStatus.SUCCESS).
    """
    agent = OptimizationAgent()
    task = EngineeringTask(
        task_id="opt_task_001",
        description="Test unsupported optimization type",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={"optimization_type": "non_existent_type"},
    )

    result = await agent.execute(task)

    assert result.status == AgentStatus.FAILED
    assert result.agent_name == "OptimizationAgent"
    assert result.study_type == StudyType.OPTIMAL_POWER_FLOW
    assert "error" in result.data
    assert "Unsupported optimization type: non_existent_type" in result.data["error"]
    assert len(result.validation_errors) == 1
    assert "Unsupported optimization type" in result.validation_errors[0]


@pytest.mark.asyncio
async def test_optimization_agent_successful_execution(monkeypatch):
    """Verify that a successful optimization execution returns AgentStatus.COMPLETED

    and valid payload data conforming to AgentResult schema.
    """
    agent = OptimizationAgent()
    mock_payload = {
        "optimal_allocations_mvar": [5.0, 10.0],
        "initial_losses_mw": 1.25,
        "optimized_losses_mw": 0.85,
        "loss_reduction_pct": 32.0,
    }
    monkeypatch.setattr(agent, "_run_placement", lambda params: mock_payload)

    task = EngineeringTask(
        task_id="opt_task_002",
        description="Test successful placement optimization",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={"optimization_type": "placement"},
    )

    result = await agent.execute(task)

    assert result.status == AgentStatus.COMPLETED
    assert result.agent_name == "OptimizationAgent"
    assert result.study_type == StudyType.OPTIMAL_POWER_FLOW
    assert result.data == mock_payload
    assert result.validation_errors == []


@pytest.mark.asyncio
async def test_optimization_agent_exception_handling(monkeypatch):
    """Verify that unexpected exceptions during execution return AgentStatus.FAILED

    with error captured in data and validation_errors.
    """
    agent = OptimizationAgent()

    def _failing_placement(params):
        raise RuntimeError("Convergence timeout in PSO solver")

    monkeypatch.setattr(agent, "_run_placement", _failing_placement)

    task = EngineeringTask(
        task_id="opt_task_003",
        description="Test exception handling",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={"optimization_type": "placement"},
    )

    result = await agent.execute(task)

    assert result.status == AgentStatus.FAILED
    assert result.agent_name == "OptimizationAgent"
    assert result.study_type == StudyType.OPTIMAL_POWER_FLOW
    assert "Convergence timeout in PSO solver" in result.data.get("error", "")
    assert any("Convergence timeout in PSO solver" in err for err in result.validation_errors)


def test_study_executor_import_block():
    """Verify the corrected import block in services/study_executor.py:464.

    Ensures get_orchestrator is correctly imported from agents.orchestrator,
    and EngineeringTask, StudyType from agents.models without ImportError.
    """
    # Test importing from agents.models
    from agents.models import EngineeringTask, StudyType

    assert EngineeringTask is not None
    assert StudyType is not None

    # Test importing get_orchestrator from agents.orchestrator
    from agents.orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    assert orchestrator is not None
    assert hasattr(orchestrator, "agents")


# ---------------------------------------------------------------------------
# M3.5 Option A: StudyExecutor Local Dispatch Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_study_executor_dispatches_optimization_locally(monkeypatch):
    """M3.5 Option A: StudyExecutor dispatches 'optimization' locally to OptimizationAgent."""
    from core_model.specs import StudyRequest
    from services.study_executor import StudyExecutor

    executor = StudyExecutor()
    mock_payload = {
        "optimal_allocations_mvar": [5.0, 10.0],
        "initial_losses_mw": 1.25,
        "optimized_losses_mw": 0.85,
    }
    monkeypatch.setattr(
        OptimizationAgent,
        "_run_placement",
        lambda self, params: mock_payload,
    )

    req = StudyRequest(
        study_type="optimization",
        parameters={"optimization_type": "placement"},
    )
    result = await executor.execute(req)
    assert result.success is True
    for k, v in mock_payload.items():
        assert result.data[k] == v
    assert "risk_score" in result.data


def test_study_executor_optimization_failure_raises_specialized_execution_unavailable():
    """M3.5: Failed optimization raises SpecializedExecutionUnavailableError in _dispatch."""
    from core.exceptions import SpecializedExecutionUnavailableError
    from services.study_executor import StudyExecutor

    executor = StudyExecutor()
    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch(
            study_type="optimization",
            system=None,
            parameters={"optimization_type": "unsupported_xyz"},
        )

    assert "optimization" in str(exc_info.value).lower()

