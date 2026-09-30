"""
AhmedETAP - Multi-Agent Orchestrator
====================================
Chief Engineering Orchestrator that coordinates all specialized agents
for autonomous power system analysis and ETAP automation.

Architecture:
- Chief Orchestrator: Task decomposition & agent coordination
- Load Flow Agent: Newton-Raphson / Fast Decoupled methods
- Short Circuit Agent: IEC 60909 fault analysis
- Harmonic Agent: IEEE 519 compliance analysis
- OPF Agent: AC/DC optimal power flow
- Protection Agent: Relay coordination per IEC 60255
- ETAP Execution Agent: COM automation interface
- Validation Agent: Results verification & compliance checking
- Report Agent: Automated report generation (PDF/DOCX/XLSX)

NOTE (Modularization Refactor):
The orchestrator has been decomposed into modular components:
- ``agents/models.py``: Domain models (StudyType, AgentResult, EngineeringTask, etc.)
- ``agents/base.py``: BaseAgent abstraction
- ``agents/registry.py``: Agent definitions and 24-agent registry
- ``agents/router.py``: Typed goal parsing and execution ordering
- ``agents/workflow.py``: Workflow engine and parallel execution dispatch
All public symbols and classes are re-exported from this module so that existing
call sites continue to work without breaking changes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent  # noqa: F401
from agents.models import (  # noqa: F401
    _ANALYSIS_RESULTS_TITLE,
    _ENGINEERING_REPORT_TITLE,
    _SYSTEM_DATA_NOT_PROVIDED_MSG,
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)
from agents.registry import (  # noqa: F401
    ETAPExecutionAgent,
    HarmonicAnalysisAgent,
    LoadFlowAgent,
    OptimalPowerFlowAgent,
    ProtectionCoordinationAgent,
    ReportGenerationAgent,
    ShortCircuitAgent,
    ValidationAgent,
    create_agent_registry,
    get_agent_for_study,
    get_study_type_mapping,
)
from agents.router import (  # noqa: F401
    GoalRouter,
    RouterDecision,
    determine_execution_order,
    parse_user_goal,
)
from agents.workflow import (  # noqa: F401
    WorkflowEngine,
    _emit_session_event,
    _emit_session_progress,
)
from core.tracing import trace_operation

UTC = timezone.utc  # noqa: UP017
logger = logging.getLogger(__name__)


class ChiefEngineeringOrchestrator:
    """Chief Engineering Orchestrator Agent.

    Prompt Handle: power_system_coordinator_agent

    Coordinates all specialized agents to execute complete engineering workflows.

    Workflow Example:
    User Goal: "Optimize this industrial power network"

    Orchestrator executes:
    1. Load Flow Analysis -> Validate
    2. Loss Calculation
    3. OPF Optimization
    4. Capacitor Placement Suggestion
    5. Fault Analysis -> Validate
    6. Harmonic Analysis -> Validate
    7. Report Generation

    All without additional user intervention.
    """

    prompt_handle = "power_system_coordinator_agent"

    def __init__(
        self,
        router: Any | None = None,
        enable_bandit_router: bool | None = None,
        agents: dict[str, BaseAgent] | None = None,
    ) -> None:
        self.agents = agents if agents is not None else create_agent_registry(orchestrator_instance=self)
        self._code_guard_agent = self.agents.get("code_guard")
        # S-19: If CodeGuardAgent is not available, safety code review is DISABLED (logged as warning in agents.registry).
        self._etap_expert_agent = self.agents.get("etap_expert")
        self._etap_gui_agent = self.agents.get("etap_gui")
        self._ahmed_etap_skill_agent = self.agents.get("ahmed_etap")

        self.task_queue: list[EngineeringTask] = []
        self.completed_tasks: dict[str, EngineeringTask] = {}
        self.logger = logging.getLogger("orchestrator")

        if router is not None:
            self.router = router
        else:
            if enable_bandit_router is None:
                try:
                    from api.feature_flags import is_strict_feature_enabled

                    enable_bandit_router = is_strict_feature_enabled(
                        "use_bandit_router", default=False
                    )
                except Exception:
                    enable_bandit_router = False
            from agents.router import create_router

            self.router = create_router(use_bandit=bool(enable_bandit_router))

        self.workflow_engine = WorkflowEngine(
            agents=self.agents,
            code_guard_agent=self._code_guard_agent,
            custom_logger=self.logger,
        )

        # Load orchestrator's own prompt for coordination guidance
        self._system_prompt: str | None = None
        self._load_prompt()

    def _load_prompt(self) -> None:
        """Load the orchestrator's prompt for coordination guidance."""
        try:
            from agents.prompt_loader import get_system_prompt

            self._system_prompt = get_system_prompt(self.prompt_handle)
            self.logger.info(
                "Orchestrator prompt loaded from handle '%s' (%d chars)",
                self.prompt_handle,
                len(self._system_prompt) if self._system_prompt else 0,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to load orchestrator prompt: %s. Using default coordination logic.",
                exc,
            )

    def get_agents_info(self) -> dict[str, Any]:
        """Return metadata for all registered agents including prompt info."""
        return {
            "orchestrator": {
                "prompt_handle": self.prompt_handle,
                "prompt_loaded": self._system_prompt is not None,  # NOSONAR S7503
            },
            "agents": {key: agent.get_agent_info() for key, agent in self.agents.items()},
        }

    async def submit_task(self, task: EngineeringTask) -> None:  # NOSONAR
        """Submit engineering task for execution."""
        self.task_queue.append(task)
        self.logger.info("Task submitted: %s - %s", task.task_id, task.description)

    @trace_operation("execute_autonomous_workflow", attributes={"component": "orchestrator"})
    async def execute_autonomous_workflow(
        self,
        user_goal: str,
        system_data: Any,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        """Execute complete autonomous engineering workflow based on user goal."""
        self.logger.info("Starting autonomous workflow for goal: %s", user_goal)

        # Parse user goal and determine required studies via typed router
        decision = self.router.route(user_goal)
        required_studies = decision.study_types

        # Create task
        task = EngineeringTask(
            task_id=f"workflow_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            description=user_goal,
            study_types=required_studies,
            parameters={"system": system_data, **(parameters or {})},
        )

        # P3 JobProgress bridge: announce the parsing phase
        _emit_session_progress(task, "parsing", 5, "Parsed goal into study plan")

        # Execute workflow
        results = await self._execute_workflow(task)

        # Store completed task
        task.results = results
        task.status = AgentStatus.COMPLETED
        self.completed_tasks[task.task_id] = task

        self.logger.info("Workflow completed: %s", task.task_id)

        # P3 JobProgress bridge: completion + result_ready
        # M4.4 — `all_validated` is NO LONGER a self-acknowledgement.
        # It requires BOTH:
        #   (a) every producer agent's own flag (self-report), AND
        #   (b) an independent pass by the ValidationAgent (external check),
        # and it is fail-closed: zero results ⇒ False, missing validator ⇒ False.
        self_validated = bool(results) and all(r.validation_status for r in results)
        external_valid, external_summary = await self._run_independent_validation(
            task, results
        )
        all_validated = bool(self_validated and external_valid)
        _emit_session_progress(task, "validating", 100, "Workflow completed")
        _emit_session_event(
            task,
            "result_ready",
            {
                "task_id": task.task_id,
                "studies_performed": [
                    r.study_type.value if hasattr(r.study_type, "value") else str(r.study_type)
                    for r in results
                ],
                "all_validated": all_validated,
                "external_validation": external_summary,
            },
        )

        # Feedback loop: telemetry & reward update for learning routers (e.g. LinUCB Bandit)
        if hasattr(self.router, "update_reward"):
            try:
                reward = 1.0 if (all_validated and results) else (0.5 if results and any(r.status == AgentStatus.COMPLETED for r in results) else 0.0)
                for r in results:
                    if hasattr(r, "study_type") and r.study_type:
                        self.router.update_reward(r.study_type, user_goal, reward)
            except Exception as exc:
                self.logger.debug("Router reward update ignored: %s", exc)

        return {
            "task_id": task.task_id,
            "run_id": getattr(task, "run_id", None),
            "plan_id": getattr(task, "plan_id", None),
            "goal": user_goal,
            "studies_performed": [
                r.study_type.value if hasattr(r.study_type, "value") else str(r.study_type)
                for r in results
            ],
            "results": results,
            "all_validated": all_validated,
            "external_validation": external_summary,
            "self_reported_valid": self_validated,
            "execution_plan": getattr(self.workflow_engine, "last_execution_plan", None),
            "execution_trace": getattr(self.workflow_engine, "last_execution_trace", None),
        }

    async def _run_independent_validation(
        self, task: EngineeringTask, results: list[AgentResult]
    ) -> tuple[bool, dict[str, Any]]:
        """Run an independent ValidationAgent pass over workflow results (M4.4).

        ``all_validated`` previously asserted only that each producer agent
        marked its own work as valid — a self-acknowledgement. This helper adds
        the external check required by the M4 gate: the separately-registered
        ``validation`` agent re-examines the results with its own checks.

        Fail-closed semantics:
          * no results                     → ``(False, ...)``
          * ValidationAgent not registered → ``(False, ...)``
          * validator raised / not COMPLETED → ``(False, ...)``

        Returns ``(externally_valid, summary)`` where ``summary`` is safe to
        embed in the workflow payload (no raw result data).
        """
        if not results:
            return False, {"performed": False, "reason": "no_results"}

        validator = self.agents.get("validation")
        if validator is None:
            self.logger.error(
                "ValidationAgent not registered — independent validation impossible; "
                "all_validated fails closed"
            )
            return False, {"performed": False, "reason": "validation_agent_missing"}

        try:
            validation_task = EngineeringTask(
                task_id=f"{task.task_id}__independent_validation",
                description=(
                    "Independent (external) validation of workflow results — M4.4 gate"
                ),
                study_types=list(task.study_types),
                parameters={
                    "results": list(results),
                    "system": (task.parameters or {}).get("system"),
                },
            )
            validation_result = await validator.execute(validation_task)
        except Exception as exc:
            self.logger.error("Independent validation raised: %s", exc)
            return False, {
                "performed": True,
                "passed": False,
                "reason": "validation_error",
                "error": str(exc),
            }

        passed = bool(
            validation_result.status == AgentStatus.COMPLETED
            and validation_result.validation_status
        )
        summary = validation_result.data.get("validation_summary", {}) if validation_result.data else {}
        return passed, {
            "performed": True,
            "passed": passed,
            "validator": validation_result.agent_name,
            "summary": summary,
        }

    async def execute_execution_plan(
        self,
        plan: Any,
        context_parameters: dict[str, Any] | None = None,
    ) -> Any:
        """M4.2 — boundary adapter: *Mastra plans, Python executes*.

        Consumes an ``ExecutionPlanContract`` (produced by the planning side)
        and returns the ``ExecutionTraceContract`` produced by the
        deterministic workflow engine. The M3 scheduling machinery
        (``WorkflowEngine.build_execution_plan`` / topological batching) is
        reused, not re-implemented.

        Fail-closed contract:
          * the payload must be a valid ``ExecutionPlanContract``
            (a plain dict is pydantic-validated; anything invalid raises);
          * at least one node must be present;
          * every ``node.study_type`` must resolve to a real ``StudyType`` —
            unknown keys raise instead of silently degrading to ``LOAD_FLOW``;
          * the trace export must succeed — no "partial trace" returns;
          * the M4.4 independent validation pass is folded into
            ``trace.overall_success`` (self-reported flags alone are not
            enough).
        """
        try:
            from contracts.ai.models import ExecutionPlanContract, ValidationResultContract
        except Exception as exc:  # pragma: no cover - contracts layer disabled
            raise RuntimeError(
                "ExecutionPlanContract unavailable — contract layer disabled; "
                "refusing to execute an unverifiable plan"
            ) from exc

        if ExecutionPlanContract is None:  # pragma: no cover - defensive
            raise RuntimeError("ExecutionPlanContract is None; refusing to execute")

        if not isinstance(plan, ExecutionPlanContract):
            try:
                plan = ExecutionPlanContract.model_validate(plan)
            except Exception as exc:
                raise ValueError(f"invalid ExecutionPlanContract: {exc}") from exc

        if not plan.nodes:
            raise ValueError("ExecutionPlanContract contains no nodes — nothing to execute")

        study_types: list[StudyType] = []
        unknown: list[str] = []
        for node in plan.nodes:
            try:
                study_types.append(StudyType(node.study_type))
            except ValueError:
                unknown.append(str(node.study_type))
        if unknown:
            raise ValueError(
                "plan references unknown study type(s) "
                f"{sorted(set(unknown))} — refusing to guess a study"
            )

        parameters: dict[str, Any] = dict(context_parameters or {})
        # Feed the plan's own DAG back through the engine so M3 scheduling
        # executes exactly what the planner ordered.
        parameters["custom_nodes"] = [
            {
                "node_id": n.node_id,
                "study_type": n.study_type,
                "agent_id": n.agent_id,
                "depends_on": list(n.depends_on),
                "parameters": dict(n.parameters),
                "input_mapping": dict(n.input_mapping),
                "output_mapping": dict(n.output_mapping),
            }
            for n in plan.nodes
        ]

        task = EngineeringTask(
            task_id=f"plan_{plan.plan_id}",
            description=plan.description or f"Execution of plan {plan.plan_id}",
            study_types=study_types,
            parameters=parameters,
            plan_id=plan.plan_id,
            run_id=plan.run_id,
        )

        started_at = datetime.now(UTC)
        results = await self._execute_workflow(task)
        completed_at = datetime.now(UTC)

        task.results = results
        if any(r.status == AgentStatus.REJECTED for r in results):
            task.status = AgentStatus.REJECTED
        elif any(r.status in (AgentStatus.FAILED, AgentStatus.SKIPPED_WITH_REASON) for r in results):
            task.status = AgentStatus.FAILED
        else:
            task.status = AgentStatus.COMPLETED
        self.completed_tasks[task.task_id] = task

        # M4.4 honesty: an independent ValidationAgent pass must agree before
        # the trace may claim overall success.
        external_ok, external_summary = await self._run_independent_validation(task, results)

        trace = self.workflow_engine.export_execution_trace(
            task,
            results,
            plan=plan,
            started_at=started_at,
            completed_at=completed_at,
        )
        if trace is None:
            raise RuntimeError(
                "ExecutionTraceContract export failed — refusing to return a partial trace"
            )

        trace.overall_success = bool(trace.overall_success and external_ok)
        try:
            trace.validations.append(
                ValidationResultContract(
                    check_name="independent_validation",
                    passed=bool(external_ok),
                    severity="info" if external_ok else "error",
                    message=(
                        "Independent ValidationAgent pass"
                        if external_ok
                        else "Independent ValidationAgent did not confirm the results"
                    ),
                    details=dict(external_summary),
                    checked_at=completed_at,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning("Could not append independent validation: %s", exc)

        self.logger.info(
            "Execution plan %s finished: success=%s nodes=%d",
            plan.plan_id,
            trace.overall_success,
            len(plan.nodes),
        )
        return trace

    def route_user_goal(self, goal: Any) -> RouterDecision:
        """Route user goal into a typed RouterDecision with confidence and reasoning."""
        return self.router.route(goal)

    def _parse_user_goal(self, goal: str) -> list[StudyType]:
        """Parse user goal to determine required studies (backward compatible shim)."""
        return self.router.parse_user_goal(goal)

    def _determine_execution_order(self, study_types: list[StudyType]) -> list[StudyType]:
        """Determine optimal execution order based on dependencies."""
        return self.router.determine_execution_order(study_types)

    def _get_agent_for_study(self, study_type: StudyType) -> BaseAgent | None:
        """Get appropriate agent for study type from the canonical mapping."""
        return get_agent_for_study(self.agents, study_type)

    def get_study_type_mapping(self) -> dict[str, str]:
        """Return mapping of study type strings to agent keys."""
        return get_study_type_mapping()

    @trace_operation("_execute_workflow", attributes={"component": "orchestrator"})
    async def _execute_workflow(self, task: EngineeringTask) -> list[AgentResult]:
        """Execute workflow by coordinating agents with parallel execution."""
        return await self.workflow_engine.execute_workflow(task)

    @trace_operation("execute_parallel_studies", attributes={"component": "orchestrator"})
    async def execute_parallel_studies(
        self,
        study_types: list[str],
        system_data: Any,
        parameters: dict[str, Any] | None = None,
        max_workers: int = 4,
        benchmark: bool = False,
    ) -> dict[str, Any]:
        """Execute multiple independent studies in parallel."""
        return await self.workflow_engine.execute_parallel_studies(
            study_types=study_types,
            system_data=system_data,
            parameters=parameters,
            max_workers=max_workers,
            benchmark=benchmark,
        )

    async def get_task_status(self, task_id: str) -> EngineeringTask | None:  # NOSONAR
        """Get status of a task."""
        return self.completed_tasks.get(task_id)


# Singleton instance
_orchestrator: ChiefEngineeringOrchestrator | None = None


def get_orchestrator() -> ChiefEngineeringOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChiefEngineeringOrchestrator()
    return _orchestrator
