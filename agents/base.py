"""
Base agent class for the multi-agent engineering orchestration system.

``BaseAgent`` provides the common infrastructure all concrete agent classes
inherit: prompt loading via the 3-tier fallback (ADR-0003), result validation,
execution logging, and distributed tracing.

Extracted from ``agents/orchestrator.py`` so data models (``agents/models``)
and the orchestrator are independently importable. Re-exported from
``agents/orchestrator.py`` for backward compatibility.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc  # noqa: UP017
from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
from core.tracing import trace_operation


class BaseAgent:
    """Base class for all engineering agents.

    Integrates with the prompt management system so every agent can
    access its prompt-driven description, standards references, and
    execution guidance from ``prompts/`` YAML files (or LangWatch).

    Subclasses must set ``prompt_handle`` to the handle that matches
    their YAML prompt file (e.g. ``"load_flow_agent"``).  If not set,
    a handle is derived from the class name by converting CamelCase
    to snake_case and stripping the "Agent" suffix.
    """

    # Subclasses should override this to match their prompt YAML handle.
    prompt_handle: str = ""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.execution_log: list[dict] = []

        # Derive prompt handle from class name if not explicitly set
        if not self.prompt_handle:
            self.prompt_handle = self._derive_prompt_handle()

        # Load prompt-driven metadata (description, standards, guidance)
        self._system_prompt: str | None = None
        self._prompt_metadata: dict[str, Any] = {}
        self._load_prompt()

    def _derive_prompt_handle(self) -> str:
        """Derive a prompt handle from the class name.

        Examples:
            LoadFlowAgent       → load_flow_agent
            ShortCircuitAgent   → short_circuit_agent
            StabilityAgent      → stability_agent
        """
        name = self.__class__.__name__
        # Remove 'Agent' suffix if present
        if name.endswith("Agent"):
            name = name[:-5]
        # Convert CamelCase to snake_case
        name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
        return name

    def _load_prompt(self) -> None:
        """Load the prompt for this agent from the prompt management system.

        Uses the 3-tier fallback:
        1. LangWatch API (if configured)
        2. Local YAML file in prompts/
        3. Hardcoded default

        Failures are non-fatal — the agent can still operate without
        a prompt, using its hardcoded computational logic.
        """
        try:
            from agents.prompt_loader import get_prompt_metadata, get_system_prompt

            self._system_prompt = get_system_prompt(self.prompt_handle)
            self._prompt_metadata = get_prompt_metadata(self.prompt_handle)
            self.logger.info(
                "Prompt loaded for handle '%s' (%d chars)",
                self.prompt_handle,
                len(self._system_prompt) if self._system_prompt else 0,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to load prompt for handle '%s': %s. Agent will use hardcoded logic.",
                self.prompt_handle,
                exc,
            )
            self._system_prompt = None
            self._prompt_metadata = {}

    @property
    def system_prompt(self) -> str:
        """Return the loaded system prompt, or a default if unavailable."""
        if self._system_prompt:
            return self._system_prompt
        return f"{self.agent_name}: Computational agent for power system analysis."

    @property
    def prompt_model(self) -> str:
        """Return the model name from the prompt metadata, if available."""
        return self._prompt_metadata.get("model", "unknown")

    @property
    def prompt_temperature(self) -> float:
        """Return the temperature from the prompt metadata, if available."""
        # SECURITY AUDIT 2026-07-25 — Fix S-18: Default temperature changed from 0.2 to 0.0.
        # Safety-critical engineering calculations require deterministic outputs.
        # Use higher temperature (0.1-0.3) ONLY for creative tasks, not engineering.
        return float(self._prompt_metadata.get("temperature", 0.0))

    def get_agent_info(self) -> dict[str, Any]:
        """Return agent metadata including prompt-derived information.

        This is useful for API responses, logging, and debugging.
        """
        return {
            "agent_name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "model": self.prompt_model,
            "temperature": self.prompt_temperature,
            "prompt_loaded": self._system_prompt is not None,
            "status": self.status.value,
        }

    @trace_operation("BaseAgent.execute", attributes={"component": "orchestrator"})
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute agent task. Override in subclasses.

        Default implementation returns a FAILED AgentResult so that any
        subclass that forgets to override ``execute`` is detected early
        via the agent's own validation pipeline (rather than crashing
        the workflow with a NotImplementedError at runtime).
        """
        self.status = AgentStatus.FAILED
        self.log_execution(
            f"BaseAgent.execute invoked on {self.agent_name} (no override). Task={task.task_id}",
            level="ERROR",
        )
        return AgentResult(
            agent_name=self.agent_name,
            study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
            status=AgentStatus.FAILED,
            data={},
            validation_errors=[
                f"Agent '{self.agent_name}' does not implement execute(); "
                "override BaseAgent.execute in the concrete subclass.",
            ],
        )

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate agent result. Override in subclasses.

        Default implementation performs the minimum sanity checks that
        apply to every result (status == COMPLETED, non-empty data,
        no pre-existing validation errors) and returns True if they
        all pass. Subclasses are expected to add domain-specific
        checks.
        """
        if result.status != AgentStatus.COMPLETED:
            result.validation_errors.append(
                f"Result status is {result.status.value}, expected completed",
            )
            return False
        if not result.data:
            result.validation_errors.append("Result data is empty")
            return False
        return not result.validation_errors

    def log_execution(self, message: str, level: str = "INFO") -> None:
        """Log execution details."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": self.agent_name,
            "level": level,
            "message": message,
        }
        self.execution_log.append(entry)
        getattr(self.logger, level.lower())(message)
