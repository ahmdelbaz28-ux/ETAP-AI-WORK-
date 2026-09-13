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

    def __init__(self) -> None:
        self.agents = create_agent_registry(orchestrator_instance=self)
        self._code_guard_agent = self.agents.get("code_guard")
        self._etap_expert_agent = self.agents.get("etap_expert")
        self._etap_gui_agent = self.agents.get("etap_gui")
        self._ahmed_etap_skill_agent = self.agents.get("ahmed_etap")

        self.task_queue: list[EngineeringTask] = []
        self.completed_tasks: dict[str, EngineeringTask] = {}
        self.logger = logging.getLogger("orchestrator")

        self.router = GoalRouter()
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

        # Parse user goal and determine required studies
        required_studies = self._parse_user_goal(user_goal)

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
        all_validated = all(r.validation_status for r in results)
        _emit_session_progress(task, "validating", 100, "Workflow completed")
        _emit_session_event(
            task,
            "result_ready",
            {
                "task_id": task.task_id,
                "studies_performed": [r.study_type.value for r in results],
                "all_validated": all_validated,
            },
        )

        return {
            "task_id": task.task_id,
            "goal": user_goal,
            "studies_performed": [r.study_type.value for r in results],
            "results": results,
            "all_validated": all(r.validation_status for r in results),
        }

    def _parse_user_goal(self, goal: str) -> list[StudyType]:
        """Parse user goal to determine required studies."""
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
