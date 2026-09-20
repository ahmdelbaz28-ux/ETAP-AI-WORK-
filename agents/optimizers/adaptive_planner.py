"""
agents/optimizers/adaptive_planner.py — Adaptive Critical Path Task Scheduling Optimizer.

Replaces static 0.4/0.4/0.2 weight scoring in GoalPlannerAgent with an adaptive
CPM (Critical Path Method) and local topological search optimizer that minimizes
total study execution makespan and schedules dependent engineering agents dynamically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A task with computed earliest start, finish, slack, and critical path status."""

    name: str
    estimated_hours: float
    importance: float
    urgency: float
    dependencies: List[str]
    earliest_start: float = 0.0
    earliest_finish: float = 0.0
    latest_start: float = 0.0
    latest_finish: float = 0.0
    slack: float = 0.0
    is_critical: bool = False


@dataclass
class ScheduleResult:
    """Optimized multi-agent execution schedule."""

    tasks: List[ScheduledTask]
    critical_path: List[str]
    total_duration_hours: float
    total_slack_hours: float
    recommended_execution_order: List[str]
    parallel_execution_batches: List[List[str]]


class AdaptiveTaskScheduler:
    """Adaptive scheduler optimizing multi-agent engineering workflows."""

    def __init__(self, historical_agent_latencies: Optional[Dict[str, float]] = None) -> None:
        self.latencies = historical_agent_latencies or {}

    def schedule(self, raw_tasks: List[Dict[str, Any]]) -> ScheduleResult:
        """Compute optimal topological schedule, critical path, and parallel batches."""
        if not raw_tasks:
            return ScheduleResult(
                tasks=[],
                critical_path=[],
                total_duration_hours=0.0,
                total_slack_hours=0.0,
                recommended_execution_order=[],
                parallel_execution_batches=[],
            )

        task_dict: Dict[str, ScheduledTask] = {}
        for t in raw_tasks:
            name = t.get("name", "Unnamed Task")
            dur = float(t.get("estimated_hours", self.latencies.get(name, 2.0)))
            imp = float(t.get("importance", 3.0)) / 5.0
            urg = float(t.get("urgency", 3.0)) / 5.0
            deps = list(t.get("dependencies", []))
            task_dict[name] = ScheduledTask(
                name=name,
                estimated_hours=max(0.1, dur),
                importance=imp,
                urgency=urg,
                dependencies=deps,
            )

        # 1. Forward Pass (Compute Earliest Start and Finish)
        visited: Set[str] = set()

        def forward_pass(t_name: str) -> None:
            if t_name in visited:
                return
            task = task_dict[t_name]
            max_dep_finish = 0.0
            for dep in task.dependencies:
                if dep in task_dict:
                    forward_pass(dep)
                    max_dep_finish = max(max_dep_finish, task_dict[dep].earliest_finish)
            task.earliest_start = max_dep_finish
            task.earliest_finish = max_dep_finish + task.estimated_hours
            visited.add(t_name)

        for name in task_dict:
            forward_pass(name)

        total_makespan = max((t.earliest_finish for t in task_dict.values()), default=0.0)

        # 2. Backward Pass (Compute Latest Start, Finish, and Slack)
        for t in task_dict.values():
            t.latest_finish = total_makespan
            t.latest_start = total_makespan - t.estimated_hours

        # Reverse topological order
        sorted_tasks = sorted(task_dict.values(), key=lambda x: x.earliest_finish, reverse=True)
        for t in sorted_tasks:
            # Look at tasks that depend on this task
            successors = [s for s in task_dict.values() if t.name in s.dependencies]
            if successors:
                min_succ_start = min(s.latest_start for s in successors)
                t.latest_finish = min_succ_start
                t.latest_start = t.latest_finish - t.estimated_hours

            t.slack = max(0.0, round(t.latest_start - t.earliest_start, 4))
            t.is_critical = (t.slack < 1e-4)

        # 3. Identify Critical Path
        critical_tasks = [t for t in sorted(task_dict.values(), key=lambda x: x.earliest_start) if t.is_critical]
        critical_path = [t.name for t in critical_tasks]

        # 4. Determine Parallel Execution Batches
        # Group tasks that can run concurrently (no direct or indirect dependencies)
        remaining = set(task_dict.keys())
        completed: Set[str] = set()
        batches: List[List[str]] = []

        while remaining:
            # Available tasks are those whose dependencies are all completed
            ready = [
                name for name in remaining
                if all(d in completed for d in task_dict[name].dependencies)
            ]
            if not ready:
                # Cycle or unresolved dependency break
                ready = list(remaining)

            # Sort ready tasks by criticality and urgency
            ready.sort(key=lambda n: (task_dict[n].is_critical, task_dict[n].urgency), reverse=True)
            batches.append(ready)
            for r in ready:
                completed.add(r)
                remaining.remove(r)

        recommended_order = [t_name for batch in batches for t_name in batch]
        total_slack = sum(t.slack for t in task_dict.values())

        return ScheduleResult(
            tasks=list(task_dict.values()),
            critical_path=critical_path,
            total_duration_hours=round(total_makespan, 2),
            total_slack_hours=round(total_slack, 2),
            recommended_execution_order=recommended_order,
            parallel_execution_batches=batches,
        )
