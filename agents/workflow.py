"""
AhmedETAP - Multi-Agent Workflow Engine
=======================================
Orchestrates autonomous study execution pipelines, parallel dispatch,
job progress telemetry, engineering assertions, and validation gates.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent
from agents.models import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)
from agents.registry import get_study_type_mapping
from agents.router import determine_execution_order
from core.tracing import trace_operation

UTC = timezone.utc  # noqa: UP017
logger = logging.getLogger(__name__)


def _emit_session_progress(
    task: EngineeringTask,
    phase: str,
    pct: float,
    message: str | None = None,
) -> None:
    """Emit a ``job_progress`` event for the task's session (best effort)."""
    try:
        params = getattr(task, "parameters", None) or {}
        session_id = params.get("session_id")
        if not session_id:
            return
        from api.session_stream import get_hub

        get_hub().publish(
            str(session_id),
            "job_progress",
            {
                "task_id": getattr(task, "task_id", None),
                "phase": phase,
                "pct": max(0.0, min(100.0, float(pct))),
                "message": message,
            },
        )
    except Exception:  # noqa: BLE001 - streaming is strictly additive
        logger.debug("job_progress emit skipped", exc_info=True)


def _emit_session_event(
    task: EngineeringTask,
    event_type: str,
    payload: dict | None = None,
) -> None:
    """Emit an arbitrary stream event (e.g. ``result_ready``) best effort."""
    try:
        params = getattr(task, "parameters", None) or {}
        session_id = params.get("session_id")
        if not session_id:
            return
        from api.session_stream import get_hub

        get_hub().publish(str(session_id), event_type, payload)
    except Exception:  # noqa: BLE001 - streaming is strictly additive
        logger.debug("%s emit skipped", event_type, exc_info=True)


class WorkflowEngine:
    """Coordinates autonomous multi-study execution pipelines and parallel dispatch."""

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        code_guard_agent: Any = None,
        custom_logger: logging.Logger | None = None,
    ) -> None:
        self.agents = agents
        self.code_guard_agent = code_guard_agent
        self.logger = custom_logger or logging.getLogger("orchestrator.workflow")

    def _get_agent_for_study(self, study_type: StudyType) -> BaseAgent | None:
        """Get appropriate agent for study type from the canonical mapping."""
        mapping = get_study_type_mapping()
        val = study_type.value if hasattr(study_type, "value") else str(study_type)
        agent_key = mapping.get(val, val)
        return self.agents.get(agent_key)

    @trace_operation("_execute_workflow", attributes={"component": "orchestrator"})
    async def execute_workflow(self, task: EngineeringTask) -> list[AgentResult]:
        """Execute workflow by coordinating agents with parallel execution."""
        results: list[AgentResult] = []

        # Determine execution order based on dependencies
        execution_order = determine_execution_order(task.study_types)

        # Separate load flow (must run first) from independent studies
        dependent_studies = [s for s in execution_order if s == StudyType.LOAD_FLOW]
        independent_studies = [s for s in execution_order if s != StudyType.LOAD_FLOW]

        # P3 JobProgress bridge: entering the solving phase
        _emit_session_progress(
            task,
            "solving",
            10,
            f"Executing {len(dependent_studies + independent_studies)} studies",
        )

        # Phase 1: Run load flow first (dependency for others)
        await self._run_dependent_studies(task, dependent_studies, results)

        # Phase 2: Run independent studies in parallel
        await self._run_independent_studies(task, independent_studies, results)

        # Phase 2.5: Engineering Assertion Gate (F-07 Fix)
        self._run_engineering_assertions(task, results)

        # Phase 3: Final validation pass
        _emit_session_progress(task, "validating", 85, "Final validation pass")
        validation_result = await self._run_final_validation(task, results)
        results.append(validation_result)

        # Phase 3.5: Guard-skills code quality review (if enabled)
        await self._run_guard_review(task, results)

        # Phase 4: Generate report if all validations pass
        if validation_result.validation_status:
            await self._run_report_phase(task, results)

        return results

    async def _run_dependent_studies(
        self,
        task: EngineeringTask,
        study_types: list[StudyType],
        results: list[AgentResult],
    ) -> None:
        """Phase 1: run load flow studies sequentially (dependency for others)."""
        total = len(study_types)
        for idx, study_type in enumerate(study_types):
            agent = self._get_agent_for_study(study_type)
            if not agent:
                continue
            _emit_session_progress(
                task,
                "solving",
                10 + 60.0 * idx / max(total, 1),
                f"Solving {study_type.value}",
            )
            self.logger.info("Executing %s via %s", study_type.value, agent.agent_name)
            result = await agent.execute(task)
            results.append(result)
            if not result.validation_status:
                self.logger.warning(
                    "Validation failed for %s: %s",
                    study_type.value,
                    result.validation_errors,
                )

    async def _run_independent_studies(
        self,
        task: EngineeringTask,
        study_types: list[StudyType],
        results: list[AgentResult],
    ) -> None:
        """Phase 2: run independent studies in parallel."""
        if not study_types:
            return

        total = len(study_types)
        parallel_tasks = []
        for idx, study_type in enumerate(study_types):
            agent = self._get_agent_for_study(study_type)
            if not agent:
                continue
            _emit_session_progress(
                task,
                "solving",
                40 + 30.0 * idx / max(total, 1),
                f"Solving {study_type.value}",
            )
            self.logger.info("Executing %s via %s", study_type.value, agent.agent_name)
            parallel_tasks.append(agent.execute(task))

        if not parallel_tasks:
            return

        parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        for pr in parallel_results:
            if isinstance(pr, BaseException):
                self.logger.exception("Parallel agent failed: %s", pr)
                continue
            results.append(pr)
            if not pr.validation_status:
                self.logger.warning("Validation failed: %s", pr.validation_errors)

    async def _run_final_validation(
        self, task: EngineeringTask, results: list[AgentResult]
    ) -> AgentResult:
        """Phase 3: final validation pass over all collected results."""
        validation_task = EngineeringTask(
            task_id=f"validation_{task.task_id}",
            description="Final validation of all results",
            study_types=[],
            parameters={"results": results},
        )
        return await self.agents["validation"].execute(validation_task)

    async def _run_guard_review(self, task: EngineeringTask, results: list[AgentResult]) -> None:
        """Phase 3.5: guard-skills code quality review of AI-generated code."""
        if not self.code_guard_agent:
            return
        try:
            code_to_review = task.parameters.get("source", "")
            if not code_to_review:
                return
            guard_task = EngineeringTask(
                task_id=f"guard_{task.task_id}",
                description="AI code quality guard review",
                study_types=[],
                parameters={
                    "source": code_to_review,
                    "guard_type": "all",
                    "language": "python",
                },
            )
            guard_result = await self.code_guard_agent.execute(guard_task)
            results.append(guard_result)
            if not guard_result.validation_status:
                self.logger.warning(
                    "Guard-skills review found MUST_FIX violations: %s",
                    guard_result.data.get("must_fix_total", 0),
                )
        except Exception as guard_err:
            self.logger.warning("Guard review failed (non-blocking): %s", guard_err)

    def _run_engineering_assertions(
        self, _task: EngineeringTask, results: list[AgentResult]
    ) -> None:
        """Phase 2.5: Run deterministic engineering assertions on all results."""
        try:
            from copilot.ai.engineering_assertions import EngineeringAssertionLayer

            assertion_layer = EngineeringAssertionLayer()
        except ImportError:
            self.logger.info(
                "EngineeringAssertionLayer not available — skipping F-07 assertion gate."
            )
            return

        for result in results:
            if result.status != AgentStatus.COMPLETED:
                continue
            if not result.data:
                continue
            self._apply_assertion_to_result(result, assertion_layer)

    def _apply_assertion_to_result(self, result: AgentResult, assertion_layer) -> None:
        """Apply engineering assertions to a single result."""
        study_type = result.study_type
        try:
            assertion_results = assertion_layer.validate(
                data=result.data,
                study_type=study_type.value if hasattr(study_type, "value") else str(study_type),
            )

            if assertion_results and hasattr(assertion_results, "failures"):
                failures = [ar for ar in assertion_results.failures if not ar.passed]
                if failures:
                    result.validation_status = False
                    self._record_assertion_failures(result, failures)

        except Exception as assertion_err:
            self.logger.warning(
                "Engineering assertion gate failed for %s (non-blocking): %s",
                study_type.value if hasattr(study_type, "value") else str(study_type),
                assertion_err,
            )

    def _record_assertion_failures(self, result: AgentResult, failures: list) -> None:
        """Record assertion failures on the result and log them."""
        for failure in failures:
            _msg = (
                f"Engineering assertion FAILED: {failure.check_name} — "
                f"{failure.message if hasattr(failure, 'message') else failure}"
            )
            result.validation_errors.append(_msg)
            severity = failure.severity if hasattr(failure, "severity") else "WARNING"
            if str(severity).upper() in ("CRITICAL", "FATAL"):
                self.logger.critical("F-07: %s", _msg)
            else:
                self.logger.warning("F-07: %s", _msg)

    async def _run_report_phase(self, task: EngineeringTask, results: list[AgentResult]) -> None:
        """Phase 4: generate the final report when validations pass."""
        report_task = EngineeringTask(
            task_id=f"report_{task.task_id}",
            description="Generate final report",
            study_types=[],
            parameters={"results": results, "format": "pdf", "output_path": "./reports"},
        )
        report_result = await self.agents["report"].execute(report_task)
        results.append(report_result)

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
        parameters = parameters or {}

        resolved = self._resolve_parallel_studies(study_types)

        if not resolved:
            self.logger.error("No valid study types resolved – nothing to execute")
            return {
                "task_id": None,
                "study_types": [],
                "parallel_results": {},
                "parallel_time_seconds": 0.0,
                "benchmark": benchmark,
            }

        task_id = f"parallel_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        def _make_task(study_str: str, agent_key: str) -> EngineeringTask:
            return self._build_parallel_task(task_id, study_str, agent_key, system_data, parameters)

        semaphore = asyncio.Semaphore(max_workers)

        self.logger.info(
            "Starting parallel execution of %d studies (max_workers=%d)",
            len(resolved),
            max_workers,
        )
        parallel_start = time.perf_counter()

        parallel_coros = [
            self._run_parallel_with_semaphore(
                semaphore, study_str, agent, _make_task(study_str, agent_key)
            )
            for study_str, agent_key, agent in resolved
        ]
        parallel_raw = await asyncio.gather(*parallel_coros, return_exceptions=True)

        parallel_time = time.perf_counter() - parallel_start
        parallel_results = self._collect_parallel_results(parallel_raw)

        result: dict[str, Any] = {
            "task_id": task_id,
            "study_types": [s for s, _, _ in resolved],
            "parallel_results": parallel_results,
            "parallel_time_seconds": round(parallel_time, 4),
            "benchmark": benchmark,
        }

        if benchmark:
            result.update(await self._run_sequential_benchmark(resolved, _make_task, parallel_time))

        self.logger.info(
            "Parallel studies completed: task_id=%s, studies=%d, parallel_time=%.4fs",
            task_id,
            len(parallel_results),
            parallel_time,
        )

        return result

    def _resolve_parallel_studies(self, study_types: list[str]) -> list[tuple]:
        """Resolve study type strings to (study_str, agent_key, agent) triples."""
        study_type_map = get_study_type_mapping()
        resolved: list[tuple] = []
        for study_str in study_types:
            agent_key = study_type_map.get(study_str)
            if agent_key is None:
                self.logger.warning("Unknown study type '%s' – skipping", study_str)
                continue
            agent = self.agents.get(agent_key)
            if agent is None:
                self.logger.warning(
                    "No agent registered for key '%s' (study '%s') – skipping",
                    agent_key,
                    study_str,
                )
                continue
            resolved.append((study_str, agent_key, agent))
        return resolved

    def _build_parallel_task(
        self,
        task_id: str,
        study_str: str,
        agent_key: str,
        system_data: Any,
        parameters: dict[str, Any],
    ) -> EngineeringTask:
        """Create an EngineeringTask for a single parallel study."""
        study_type_match = [s for s in StudyType if s.value == study_str or s.value == agent_key]
        return EngineeringTask(
            task_id=f"{task_id}_{study_str}",
            description=f"Parallel study: {study_str}",
            study_types=study_type_match[:1],
            parameters={"system": system_data, **parameters},
        )

    async def _run_parallel_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        study_str: str,
        agent: BaseAgent,
        task: EngineeringTask,
    ) -> tuple:
        """Run a single agent.execute, bounded by the semaphore."""
        async with semaphore:
            self.logger.info("[parallel] Starting %s via %s", study_str, agent.agent_name)
            try:
                result = await agent.execute(task)
                self.logger.info(
                    "[parallel] Completed %s (status=%s)",
                    study_str,
                    result.status.value,
                )
                return (study_str, result)
            except Exception as exc:
                self.logger.exception("[parallel] Failed %s: %s", study_str, exc)
                return (study_str, self._failed_parallel_result(agent, task, exc))

    def _failed_parallel_result(
        self, agent: BaseAgent, task: EngineeringTask, exc: Exception
    ) -> AgentResult:
        """Build a failure AgentResult instead of propagating the exception."""
        return AgentResult(
            agent_name=agent.agent_name,
            study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
            status=AgentStatus.FAILED,
            data={},
            validation_status=False,
            validation_errors=[str(exc)],
        )

    def _collect_parallel_results(self, parallel_raw: list) -> dict[str, AgentResult]:
        """Filter gather output into a study_str → AgentResult mapping."""
        parallel_results: dict[str, AgentResult] = {}
        for item in parallel_raw:
            if isinstance(item, BaseException):
                self.logger.exception("[parallel] Unexpected exception: %s", item)
                continue
            study_str, result = item
            if not isinstance(result, AgentResult):
                raise TypeError(f"Expected AgentResult, got {type(result).__name__}")
            parallel_results[study_str] = result
        return parallel_results

    async def _run_sequential_benchmark(
        self,
        resolved: list[tuple],
        make_task: Any,
        parallel_time: float,
    ) -> dict[str, Any]:
        """Run studies sequentially and return the timing comparison."""
        self.logger.info("Benchmark: running studies sequentially for comparison")
        sequential_start = time.perf_counter()

        sequential_results: dict[str, AgentResult] = {}
        for study_str, agent_key, agent in resolved:
            task = make_task(study_str, agent_key)
            self.logger.info("[sequential] Starting %s via %s", study_str, agent.agent_name)
            try:
                seq_result = await agent.execute(task)
                sequential_results[study_str] = seq_result
            except Exception as exc:
                self.logger.exception("[sequential] Failed %s: %s", study_str, exc)
                sequential_results[study_str] = self._failed_parallel_result(agent, task, exc)

        sequential_time = time.perf_counter() - sequential_start
        speedup = sequential_time / parallel_time if parallel_time > 0 else float("inf")

        self.logger.info(
            "Benchmark complete – parallel: %.4fs, sequential: %.4fs, speedup: %.2fx",
            parallel_time,
            sequential_time,
            speedup,
        )

        return {
            "sequential_results": sequential_results,  # NOSONAR S7503
            "sequential_time_seconds": round(sequential_time, 4),
            "speedup_factor": round(speedup, 2),
        }
