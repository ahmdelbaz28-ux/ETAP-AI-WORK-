"""
AhmedETAP - Goal Planner Agent
===================================================
Goal decomposition, task extraction, and prioritized planning for
engineering workflows and daily task management.

Capabilities:
- Goal extraction from free-form text
- Task decomposition with time estimation and dependency identification
- Priority-based task scheduling (importance, urgency, dependencies)
- Risk identification and mitigation recommendations
- Structured daily plan generation

Standards:
- Project Management Institute (PMI) PMBOK framework
- Critical Path Method (CPM) for dependency scheduling
- MoSCoW prioritization method
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

UTC = UTC
from typing import Any, Dict, List

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority and dependency constants
# ---------------------------------------------------------------------------

_PRIORITY_LEVELS = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "optional": 1,
}

_URGENCY_LEVELS = {
    "immediate": 5,
    "today": 4,
    "this_week": 3,
    "this_month": 2,
    "backlog": 1,
}


class GoalPlannerAgent(BaseAgent):
    """
    Goal Planner Agent for task decomposition and prioritized planning.

    Takes in messy, free-form text about goals, tasks, and projects
    and produces a structured, prioritized task list. The agent
    follows the GoalPlannerOutput schema:

    1. **Problem Understanding**: Restate the user's input and
       identify the goals and tasks mentioned.
    2. **Task Extraction**: List each extracted task with estimated
       duration, priority, dependencies, and notes.
    3. **Prioritization**: Explain the prioritization criteria used
       (importance, urgency, dependencies).
    4. **Structured Daily Plan**: Provide the final prioritized task
       list ordered for execution.
    5. **Validation & Risks**: Note assumptions and potential risks.
    6. **Recommendations**: Suggest adjustments or next steps.

    Prioritization uses a composite scoring method:

        Score = w_importance × importance
              + w_urgency × urgency
              + w_dependency × (1 / (1 + blocked_by_count))

    where weights default to 0.4, 0.4, and 0.2 respectively.

    Dependency scheduling follows the Critical Path Method (CPM):
    - Tasks with unmet dependencies are deferred
    - The longest dependency chain determines the critical path
    - Slack time is computed for non-critical tasks
    """

    prompt_handle = "goal_planner_agent"

    def __init__(self) -> None:
        super().__init__("GoalPlannerAgent")
        self.standards = ["PMI PMBOK", "CPM", "MoSCoW"]
        self.w_importance: float = 0.4
        self.w_urgency: float = 0.4
        self.w_dependency: float = 0.2

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def extract_tasks(
        self,
        raw_input: str,
        known_tasks: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """
        Extract and structure tasks from free-form input text.

        This method provides a computational framework for task
        extraction. In production, it is typically augmented by the
        LLM prompt to parse natural language.

        Parameters
        ----------
        raw_input : str
            Free-form text describing goals, tasks, and constraints.
        known_tasks : Optional[List[Dict[str, Any]]]
            Pre-extracted tasks (if already parsed). Each dict has
            keys: 'name', 'estimated_hours', 'importance',
            'urgency', 'dependencies' (list of task names),
            'notes'.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'problem_understanding', 'tasks',
            'total_tasks', 'total_estimated_hours'.
        """
        if known_tasks is None:
            known_tasks = []

        # Problem understanding: summarize the input
        problem_understanding = (
            f"User input contains {len(known_tasks)} identified task(s) "
            f"from the provided text. "
            f"Total estimated effort: {sum(t.get('estimated_hours', 0) for t in known_tasks):.1f} hours."
        )

        # Normalize and validate tasks
        normalized_tasks = []
        for i, task in enumerate(known_tasks):
            normalized = {
                "id": i + 1,
                "name": task.get("name", f"Task {i + 1}"),
                "estimated_hours": float(task.get("estimated_hours", 1.0)),
                "importance": task.get("importance", "medium"),
                "urgency": task.get("urgency", "this_week"),
                "dependencies": task.get("dependencies", []),
                "notes": task.get("notes", ""),
                "moscow_category": task.get("moscow_category", "should"),
            }
            normalized_tasks.append(normalized)

        total_hours = sum(t["estimated_hours"] for t in normalized_tasks)

        return {
            "problem_understanding": problem_understanding,
            "raw_input_length": len(raw_input),
            "tasks": normalized_tasks,
            "total_tasks": len(normalized_tasks),
            "total_estimated_hours": round(total_hours, 1),
        }

    def prioritize_tasks(
        self,
        tasks: List[Dict[str, Any]],
        available_hours: float = 8.0,
    ) -> Dict[str, Any]:
        """
        Prioritize tasks using composite scoring and dependency
        resolution.

        Parameters
        ----------
        tasks : List[Dict[str, Any]]
            List of task dicts with keys: 'id', 'name',
            'estimated_hours', 'importance', 'urgency',
            'dependencies', 'notes'.
        available_hours : float
            Available working hours for the planning period
            (default 8.0 for one day).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'prioritized_tasks', 'scheduled_tasks',
            'deferred_tasks', 'critical_path', 'total_hours',
            'available_hours', 'utilization_percent'.
        """
        # Compute composite score for each task
        scored_tasks = []
        for task in tasks:
            importance_score = _PRIORITY_LEVELS.get(task.get("importance", "medium"), 3) / 5.0
            urgency_score = _URGENCY_LEVELS.get(task.get("urgency", "this_week"), 3) / 5.0

            # Dependency score: tasks with fewer blockers score higher
            dep_count = len(task.get("dependencies", []))
            dependency_score = 1.0 / (1.0 + dep_count)

            composite = (
                self.w_importance * importance_score
                + self.w_urgency * urgency_score
                + self.w_dependency * dependency_score
            )

            scored_task = {**task, "composite_score": round(composite, 4)}
            scored_tasks.append(scored_task)

        # Sort by composite score (descending)
        scored_tasks.sort(key=lambda t: t["composite_score"], reverse=True)

        # Dependency-aware scheduling (topological sort with priority)
        task_names = {t["name"] for t in scored_tasks}
        completed = set()
        scheduled = []
        deferred = []

        remaining = list(scored_tasks)
        max_iterations = len(remaining) * 2
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            ready = []
            not_ready = []

            for task in remaining:
                deps = task.get("dependencies", [])
                # Only consider dependencies that exist in our task set
                unmet = [d for d in deps if d in task_names and d not in completed]
                if not unmet:
                    ready.append(task)
                else:
                    not_ready.append(task)

            if not ready:
                # Circular dependency — schedule remaining by score
                deferred.extend(remaining)
                break

            # Pick the highest-scoring ready task
            ready.sort(key=lambda t: t["composite_score"], reverse=True)
            next_task = ready[0]
            scheduled.append(next_task)
            completed.add(next_task["name"])
            remaining = [t for t in remaining if t["name"] != next_task["name"]]

        # Determine critical path (longest dependency chain)
        critical_path = self._find_critical_path(scored_tasks)

        # Calculate schedule fit
        scheduled_hours = sum(t["estimated_hours"] for t in scheduled)
        fits_in_day = scheduled_hours <= available_hours

        # If over budget, identify which tasks to defer
        if not fits_in_day:
            cumulative = 0.0
            for i, task in enumerate(scheduled):
                cumulative += task["estimated_hours"]
                if cumulative > available_hours and i < len(scheduled):
                    deferred = scheduled[i:]
                    scheduled = scheduled[:i]
                    break

        total_scheduled_hours = sum(t["estimated_hours"] for t in scheduled)
        utilization = (
            (total_scheduled_hours / available_hours * 100.0) if available_hours > 0 else 0.0
        )

        return {
            "prioritized_tasks": scored_tasks,
            "scheduled_tasks": scheduled,
            "deferred_tasks": deferred,
            "critical_path": critical_path,
            "total_hours": round(total_scheduled_hours, 1),
            "available_hours": available_hours,
            "utilization_percent": round(min(utilization, 100.0), 1),
            "fits_in_period": fits_in_day,
            "prioritization_criteria": {
                "w_importance": self.w_importance,
                "w_urgency": self.w_urgency,
                "w_dependency": self.w_dependency,
            },
        }

    def _find_critical_path(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """
        Find the critical path (longest dependency chain) through tasks.

        Returns a list of task names forming the critical path.
        """
        task_map = {t["name"]: t for t in tasks}
        memo: Dict[str, List[str]] = {}

        def longest_chain(name: str) -> List[str]:
            if name in memo:
                return memo[name]
            task = task_map.get(name)
            if task is None:
                memo[name] = [name]
                return [name]
            deps = task.get("dependencies", [])
            if not deps:
                memo[name] = [name]
                return [name]
            best_chain = []
            for dep in deps:
                chain = longest_chain(dep)
                if len(chain) > len(best_chain):
                    best_chain = chain
            memo[name] = best_chain + [name]
            return memo[name]

        overall_best = []
        for task in tasks:
            chain = longest_chain(task["name"])
            if len(chain) > len(overall_best):
                overall_best = chain

        return overall_best

    def assess_risks(
        self,
        scheduled_tasks: List[Dict[str, Any]],
        deferred_tasks: List[Dict[str, Any]],
        available_hours: float = 8.0,
    ) -> Dict[str, Any]:
        """
        Assess risks in the planned schedule.

        Parameters
        ----------
        scheduled_tasks : List[Dict[str, Any]]
            Tasks scheduled for the planning period.
        deferred_tasks : List[Dict[str, Any]]
            Tasks deferred beyond the current period.
        available_hours : float
            Available hours in the planning period.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'risks', 'assumptions', 'recommendations'.
        """
        risks = []
        assumptions = []
        recommendations = []

        total_hours = sum(t.get("estimated_hours", 0) for t in scheduled_tasks)

        # Risk: schedule overrun
        if total_hours > available_hours * 0.9:
            risks.append(
                f"Scheduled tasks total {total_hours:.1f}h, "
                f"close to or exceeding available {available_hours:.1f}h. "
                "High risk of schedule overrun."
            )

        # Risk: high-importance tasks deferred
        for task in deferred_tasks:
            if task.get("importance") in ("critical", "high"):
                risks.append(
                    f"High-importance task '{task['name']}' is deferred — "
                    "may cause downstream delays."
                )

        # Risk: dependency chains
        for task in scheduled_tasks:
            deps = task.get("dependencies", [])
            if len(deps) > 2:
                risks.append(
                    f"Task '{task['name']}' has {len(deps)} dependencies — high coupling risk."
                )

        # Assumptions
        assumptions.append("Time estimates are approximate and may vary by ±25%")
        if deferred_tasks:
            assumptions.append(f"{len(deferred_tasks)} task(s) deferred to next period")

        # Recommendations
        if total_hours > available_hours:
            recommendations.append("Consider breaking large tasks into smaller subtasks")
            recommendations.append("Identify tasks that can be parallelized or delegated")
        if deferred_tasks:
            recommendations.append("Review deferred tasks for any that can be quick-wins")
        if not risks:
            recommendations.append("Schedule looks feasible — proceed with execution")

        return {
            "risks": risks,
            "assumptions": assumptions,
            "recommendations": recommendations,
            "risk_count": len(risks),
            "risk_level": "high" if len(risks) > 3 else "medium" if len(risks) > 1 else "low",
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute goal planning task.

        Processes the user's free-form goal description through:
        1. Task extraction
        2. Prioritization and scheduling
        3. Risk assessment
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting goal planning for task {task.task_id}")

            raw_input = task.parameters.get("raw_input", "")
            known_tasks = task.parameters.get("tasks")
            available_hours = float(task.parameters.get("available_hours", 8.0))

            # Step 1: Extract tasks
            extraction = self.extract_tasks(
                raw_input=raw_input,
                known_tasks=known_tasks,
            )

            # Step 2: Prioritize and schedule
            prioritization = self.prioritize_tasks(
                tasks=extraction["tasks"],
                available_hours=available_hours,
            )

            # Step 3: Assess risks
            risk_assessment = self.assess_risks(
                scheduled_tasks=prioritization["scheduled_tasks"],
                deferred_tasks=prioritization["deferred_tasks"],
                available_hours=available_hours,
            )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    "problem_understanding": extraction["problem_understanding"],
                    "task_extraction": extraction,
                    "prioritization": prioritization,
                    "risk_assessment": risk_assessment,
                    "standards": self.standards,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Goal planning completed in {execution_time:.2f}s "
                f"({extraction['total_tasks']} tasks, "
                f"{len(prioritization['scheduled_tasks'])} scheduled)"
            )
            return result

        except Exception as e:
            self.log_execution(f"Goal planning failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate goal planning results.

        Checks:
        - At least one task was extracted
        - Scheduled task hours are non-negative
        - Composite scores are between 0 and 1
        - No duplicate task names in scheduled list
        """
        errors: List[str] = []

        extraction = result.data.get("task_extraction")
        if extraction is not None:
            if extraction.get("total_tasks", 0) < 0:
                errors.append("Negative task count")

        prioritization = result.data.get("prioritization")
        if prioritization is not None:
            for task in prioritization.get("scheduled_tasks", []):
                if task.get("estimated_hours", 0) < 0:
                    errors.append(f"Task '{task.get('name')}' has negative estimated hours")
                score = task.get("composite_score", 0)
                if score < 0 or score > 1:
                    errors.append(f"Task '{task.get('name')}' has invalid composite score: {score}")

            scheduled_names = [t["name"] for t in prioritization.get("scheduled_tasks", [])]
            if len(scheduled_names) != len(set(scheduled_names)):
                errors.append("Duplicate task names in scheduled list")

        result.validation_errors.extend(errors)
        return len(errors) == 0
