"""
tests/test_multi_objective_and_planner.py — Unit Tests for MOPSO, Adaptive Scheduler, and Tuner.
"""

from __future__ import annotations

import numpy as np
import pytest

from agents.optimizers.adaptive_planner import AdaptiveTaskScheduler
from engine.optimizers.multi_objective import MultiObjectivePSO, ParetoPoint
from engine.optimizers.solver_tuner import NetworkCategory, SolverParameterTuner


def test_mopso_pareto_frontier_discovery():
    def simple_bi_objective(x):
        # Convex front: f1 = x[0]^2, f2 = (x[0] - 2)^2
        f1 = float(x[0] ** 2)
        f2 = float((x[0] - 2.0) ** 2)
        return np.array([f1, f2])

    mopso = MultiObjectivePSO(
        n_objectives=2,
        objective_names=["F1", "F2"],
        archive_size=20,
        swarm_size=25,
        max_iter=30,
        seed=42,
    )

    result = mopso.optimize(simple_bi_objective, lb=[0.0], ub=[2.0])

    assert result.n_points >= 10
    matrix = result.get_objective_matrix()
    assert matrix.shape[1] == 2
    # Check that as F1 increases, F2 decreases along the front (trade-off)
    assert matrix[0, 0] < matrix[-1, 0]
    assert matrix[0, 1] > matrix[-1, 1]


def test_adaptive_cpm_scheduler():
    scheduler = AdaptiveTaskScheduler()

    tasks = [
        {"name": "Task A", "estimated_hours": 2.0, "dependencies": []},
        {"name": "Task B", "estimated_hours": 3.0, "dependencies": ["Task A"]},
        {"name": "Task C", "estimated_hours": 1.5, "dependencies": ["Task A"]},
        {"name": "Task D", "estimated_hours": 2.0, "dependencies": ["Task B", "Task C"]},
    ]

    res = scheduler.schedule(tasks)

    # Path A(2) -> B(3) -> D(2) = 7.0 hours
    # Path A(2) -> C(1.5) -> D(2) = 5.5 hours
    assert res.total_duration_hours == 7.0
    assert "Task A" in res.critical_path
    assert "Task B" in res.critical_path
    assert "Task D" in res.critical_path
    assert "Task C" not in res.critical_path  # Task C has 1.5h slack

    # Check parallel batches
    assert len(res.parallel_execution_batches) == 3
    # Batch 2 must run Task B and Task C concurrently
    assert set(res.parallel_execution_batches[1]) == {"Task B", "Task C"}


def test_solver_parameter_tuner():
    tuner = SolverParameterTuner()

    class MockSystem:
        def __init__(self, n_buses):
            self.buses = dict.fromkeys(range(n_buses))
            self.branches = {}

    small_sys = MockSystem(14)
    med_sys = MockSystem(100)
    large_sys = MockSystem(500)

    params_small = tuner.get_optimal_parameters(small_sys)
    assert params_small.max_iterations == 35
    assert params_small.damping_factor == 1.0

    params_med = tuner.get_optimal_parameters(med_sys)
    assert params_med.use_sparse_solver is True
    assert params_med.damping_factor == 0.95

    params_large = tuner.get_optimal_parameters(large_sys)
    assert params_large.use_sparse_solver is True
    assert params_large.max_iterations == 80


def test_optimizers_init_exports():
    import agents.optimizers as opt

    assert hasattr(opt, "AdaptiveTaskScheduler")
    assert hasattr(opt, "ScheduledTask")
    assert hasattr(opt, "ScheduleResult")
    assert hasattr(opt, "ContextualBanditRouter")
    assert hasattr(opt, "OptimizationAgent")


def test_goal_planner_agent_default_static_behavior():
    from agents.goal_planner_agent import GoalPlannerAgent

    agent = GoalPlannerAgent()
    assert agent.enable_adaptive_cpm is False

    tasks = [
        {"name": "Study A", "estimated_hours": 2.0, "importance": "high", "urgency": "today"},
        {"name": "Study B", "estimated_hours": 4.0, "importance": "critical", "urgency": "immediate", "dependencies": ["Study A"]},
    ]

    out = agent.prioritize_tasks(tasks, available_hours=8.0)
    assert "adaptive_schedule" not in out
    assert "parallel_execution_batches" not in out
    assert len(out["prioritized_tasks"]) == 2
    assert out["fits_in_period"] is True
    assert out["prioritization_criteria"]["w_importance"] == 0.4


def test_goal_planner_agent_adaptive_cpm_integration():
    from agents.goal_planner_agent import GoalPlannerAgent

    agent = GoalPlannerAgent()
    tasks = [
        {"name": "Task A", "estimated_hours": 2.0, "dependencies": []},
        {"name": "Task B", "estimated_hours": 3.0, "dependencies": ["Task A"]},
        {"name": "Task C", "estimated_hours": 1.5, "dependencies": ["Task A"]},
        {"name": "Task D", "estimated_hours": 2.0, "dependencies": ["Task B", "Task C"]},
    ]

    out = agent.prioritize_tasks(tasks, available_hours=10.0, use_adaptive_cpm=True)
    assert "adaptive_schedule" in out
    assert "parallel_execution_batches" in out

    adaptive = out["adaptive_schedule"]
    assert adaptive["total_duration_hours"] == 7.0
    assert "Task A" in adaptive["critical_path"]
    assert "Task B" in adaptive["critical_path"]
    assert "Task D" in adaptive["critical_path"]
    assert "Task C" not in adaptive["critical_path"]

    # Scored tasks have CPM metadata
    for t in out["prioritized_tasks"]:
        assert "earliest_start" in t
        assert "earliest_finish" in t
        assert "slack" in t
        assert "is_critical" in t


def test_goal_planner_agent_adaptive_fallback_on_corrupt_input():
    from agents.goal_planner_agent import GoalPlannerAgent

    agent = GoalPlannerAgent()

    class FaultyScheduler:
        def schedule(self, raw_tasks):
            raise RuntimeError("CPM solver simulation failure")

    agent._adaptive_scheduler = FaultyScheduler()

    tasks = [
        {"name": "Task A", "estimated_hours": 2.0, "dependencies": []},
        {"name": "Task B", "estimated_hours": 3.0, "dependencies": ["Task A"]},
    ]

    # Should not crash; gracefully falls back to static prioritization
    out = agent.prioritize_tasks(tasks, available_hours=8.0, use_adaptive_cpm=True)
    assert "adaptive_schedule" not in out
    assert len(out["prioritized_tasks"]) == 2
    assert "Task A" in out["critical_path"]


@pytest.mark.asyncio
async def test_goal_planner_agent_async_execute_with_adaptive_flag():
    from agents.goal_planner_agent import GoalPlannerAgent
    from agents.orchestrator import EngineeringTask, StudyType

    agent = GoalPlannerAgent()
    task = EngineeringTask(
        task_id="task_m3_1",
        description="Goal planning task for substation study",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "raw_input": "Run full substation study workflow",
            "tasks": [
                {"name": "Load Flow", "estimated_hours": 2.0, "importance": "high", "urgency": "today"},
                {"name": "Short Circuit", "estimated_hours": 3.0, "importance": "critical", "urgency": "immediate", "dependencies": ["Load Flow"]},
            ],
            "use_adaptive_cpm": True,
        },
    )

    result = await agent.execute(task)
    assert result.status.value == "completed"
    assert result.validation_status is True
    assert "adaptive_schedule" in result.data["prioritization"]
    assert result.data["prioritization"]["adaptive_schedule"]["total_duration_hours"] == 5.0

