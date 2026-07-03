"""
Code Guard Agent — AI-Powered Code Quality Review
====================================================
Integrates the guard-skills quality gates into the ETAP agent system.
This agent reviews AI-generated code, test code, and documentation
against the 14 AI failure modes, 23 clean-code imperatives, 9 testing
rules, and 10 documentation accuracy rules.

Adapted from: github.com/amElnagdy/guard-skills
Integration point: agents/orchestrator.py → ChiefEngineeringOrchestrator
"""

import logging
import time
from typing import Any

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class CodeGuardAgent(BaseAgent):
    """Reviews code quality using guard-skills validators.

    This agent is invoked by the ChiefEngineeringOrchestrator after code
    generation to catch systematic AI failure modes before code is committed
    or executed.  It delegates to the guards module for actual scanning.

    Capabilities:
    - Production code review (CodeGuard: 23 rules + 14 AI failure modes)
    - Test code review (TestGuard: 9 rules + 3 LLM-specific rules)
    - Documentation review (DocsGuard: 10 rules)
    - AI failure mode detection (AIFailureModeDetector: 14 patterns)
    """

    prompt_handle = "code_guard_agent"

    def __init__(self):
        super().__init__("Code Guard Agent")
        self._code_guard = None
        self._test_guard = None
        self._docs_guard = None
        self._ai_detector = None
        self._initialize_guards()

    def _initialize_guards(self) -> None:
        """Lazily initialize guard instances."""
        try:
            from guards import AIFailureModeDetector, CodeGuard, DocsGuard, TestGuard
            from guards.base import GuardMode

            self._code_guard = CodeGuard(mode=GuardMode.GUARD_PASS)
            self._test_guard = TestGuard(mode=GuardMode.GUARD_PASS)
            self._docs_guard = DocsGuard(mode=GuardMode.GUARD_PASS)
            self._ai_detector = AIFailureModeDetector(mode=GuardMode.GUARD_PASS)
            self.logger.info("Guard skills initialized successfully")
        except ImportError as e:
            self.logger.warning(
                "Guards module not available: %s. Agent will operate in fallback mode.", e,
            )

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute a code guard review task.

        The task parameters should include:
          - 'source': The source code/text to review
          - 'guard_type': One of 'code', 'test', 'docs', 'ai_failure_modes', or 'all'
          - 'language': Optional language hint (default: 'python')
        """
        start_time = time.time()
        self.status = AgentStatus.RUNNING

        try:
            source = task.parameters.get("source", "")
            guard_type = task.parameters.get("guard_type", "all")
            language = task.parameters.get("language", "python")

            if not source:
                return AgentResult(
                    agent_name=self.agent_name,
                    study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                    status=AgentStatus.FAILED,
                    data={"error": "No source code provided for guard review"},
                    execution_time=time.time() - start_time,
                )

            results: dict[str, Any] = {}

            if guard_type in ("all", "code") and self._code_guard:
                code_result = self._code_guard.scan(source, language)
                results["code_guard"] = code_result.to_dict()

            if guard_type in ("all", "test") and self._test_guard:
                test_result = self._test_guard.scan(source, language)
                results["test_guard"] = test_result.to_dict()

            if guard_type in ("all", "docs") and self._docs_guard:
                docs_result = self._docs_guard.scan(source, "markdown", task.parameters)
                results["docs_guard"] = docs_result.to_dict()

            if guard_type in ("all", "ai_failure_modes") and self._ai_detector:
                ai_result = self._ai_detector.detect(source)
                results["ai_failure_modes"] = ai_result.to_dict()

            # Aggregate pass/fail
            all_passed = all(r.get("passed", True) for r in results.values() if isinstance(r, dict))

            # Count total violations by severity
            must_fix_total = sum(
                r.get("must_fix", 0) for r in results.values() if isinstance(r, dict)
            )
            should_fix_total = sum(
                r.get("should_fix", 0) for r in results.values() if isinstance(r, dict)
            )

            self.status = AgentStatus.COMPLETED
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    "guard_results": results,
                    "all_passed": all_passed,
                    "must_fix_total": must_fix_total,
                    "should_fix_total": should_fix_total,
                    "guard_type": guard_type,
                    "source_length": len(source),
                },
                validation_status=all_passed,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            self.status = AgentStatus.FAILED
            self.logger.error.exception("Code guard review failed: ")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={"error": str(e)},
                execution_time=time.time() - start_time,
            )

    async def review_code(self, source: str, language: str = "python") -> dict[str, Any]:
        """Convenience method for quick code reviews without a full EngineeringTask.

        Returns a dict with guard results suitable for API responses.
        """
        if not self._code_guard:
            return {"error": "Code guard not initialized", "passed": False}

        result = self._code_guard.scan(source, language)
        return result.to_dict()

    async def detect_ai_failure_modes(self, source: str) -> dict[str, Any]:
        """Run only the AI failure mode detector on the given source."""
        if not self._ai_detector:
            return {"error": "AI failure mode detector not initialized", "passed": False}

        result = self._ai_detector.detect(source)
        return result.to_dict()
