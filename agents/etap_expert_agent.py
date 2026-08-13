"""
agents/etap_expert_agent.py — ETAP Expert Skill Agent

Implements the ETAP Expert skill as a runtime-active agent that:
  1. Loads its knowledge base from skills/etap-expert.md (4,400+ lines)
  2. Classifies each user question via rule-based pattern matching into
     one of four modes: COMPLETE / INCOMPLETE / WRONG / ADMS
  3. Runs an internal simulation when applicable (cable sizing, transformer
     sizing, arc flash, relay coordination, FLISR, etc.)
  4. Formats the response using the mandatory Format A/B/C/D templates
     defined by the skill

C6 REFACTOR: The classification patterns, simulation engine, and
response formatters have been extracted into the
``agents.etap_expert`` sub-package (classifier.py, simulator.py,
formatter.py). This file is now a thin orchestrator that imports
from those sub-modules. All public functions are re-exported from
the package for backward compatibility:

    from agents.etap_expert import classify, simulate_cable_sizing

Registered as study_type="etap_expert" in api/studies.py and callable
via POST /api/v1/studies/run.

References:
  - skills/etap-expert.md            (knowledge base)
  - skills/etap-ai-agent-system-prompt.md  (system prompt)
  - prompts/etap_expert_agent.prompt.yaml  (LLM prompt for Mastra side)
  - api/studies.py:_run_native_study       (dispatch entry point)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.etap_expert.classifier import (
    classify,
    find_incomplete_pattern,
    find_wrong_pattern,
)
from agents.etap_expert.formatter import (
    format_adms,
    format_complete,
    format_incomplete,
    format_wrong,
)
from agents.etap_expert.simulator import (
    generic_complete_response,
    try_cable_sizing_simulation,
)
from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger("agent.etap_expert")

# ---------------------------------------------------------------------------
# Skill knowledge loader — single source of truth, loaded once
# ---------------------------------------------------------------------------

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "etap-expert.md"
_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "skills" / "etap-ai-agent-system-prompt.md"

_skill_cache: str | None = None
_system_prompt_cache: str | None = None


def _load_skill() -> str:
    """Load the skill knowledge base (cached after first call)."""
    global _skill_cache
    if _skill_cache is None:
        if not _SKILL_PATH.exists():
            logger.warning("Skill knowledge file missing: %s", _SKILL_PATH)
            _skill_cache = ""
        else:
            _skill_cache = _SKILL_PATH.read_text(encoding="utf-8")
            logger.info("ETAP Expert skill loaded: %d chars", len(_skill_cache))
    return _skill_cache


def _load_system_prompt() -> str:
    """Load the skill system prompt (cached)."""
    global _system_prompt_cache
    if _system_prompt_cache is None:
        if not _SYSTEM_PROMPT_PATH.exists():
            _system_prompt_cache = ""
        else:
            _system_prompt_cache = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _system_prompt_cache


# ---------------------------------------------------------------------------
# Backward-compat aliases for the old private functions (tests may call these).
# ---------------------------------------------------------------------------

def _try_cable_sizing_simulation(question: str) -> dict[str, Any] | None:
    return try_cable_sizing_simulation(question)


def _generic_complete_response(question: str) -> dict[str, Any]:
    return generic_complete_response(question)


def _format_a_complete(question: str, simulation: dict[str, Any]) -> str:
    return format_complete(question, simulation)


def _format_b_incomplete(question: str, missing: str, clarifying_q: str) -> str:
    return format_incomplete(question, missing, clarifying_q)


def _format_c_wrong(question: str, problem: str, correct: str) -> str:
    return format_wrong(question, problem, correct)


def _format_d_adms(question: str) -> str:
    return format_adms(question)


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ETAPExpertAgent(BaseAgent):
    """ETAP Expert Agent — implements the 6-step workflow with Format A/B/C/D.

    Registered as study_type="etap_expert" in api/studies.py.
    Loads its knowledge base from skills/etap-expert.md.

    Classification, simulation, and formatting are delegated to the
    ``agents.etap_expert`` sub-package modules.
    """

    prompt_handle = "etap_expert_agent"

    def __init__(self) -> None:
        super().__init__("etap_expert")
        skill_text = _load_skill()
        if not skill_text:
            logger.warning(
                "ETAP Expert skill knowledge base is empty — agent will operate in degraded mode",
            )
        _load_system_prompt()

    # ----- Public API -----

    def answer(self, question: str) -> dict[str, Any]:
        """Answer a question using the 6-step workflow.

        Returns a dict with keys: classification, response (Format A/B/C/D text),
        skill_loaded (bool), skill_chars (int).
        """
        cls = classify(question)

        if cls == "adms":
            response = format_adms(question)
        elif cls == "wrong":
            problem, correct = find_wrong_pattern(question)
            response = format_wrong(question, problem, correct)
        elif cls == "incomplete":
            missing, clarifying = find_incomplete_pattern(question)
            response = format_incomplete(question, missing, clarifying)
        else:  # complete
            sim = try_cable_sizing_simulation(question) or generic_complete_response(question)
            response = format_complete(question, sim)

        return {
            "classification": cls,
            "format": {"complete": "A", "incomplete": "B", "wrong": "C", "adms": "D"}[cls],
            "response": response,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "workflow_steps_executed": 6,
        }

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Async wrapper for orchestrator compatibility."""
        question = str(task.parameters.get("question", "")).strip()
        if not question:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=["Missing 'question' parameter"],
            )
        try:
            data = self.answer(question)
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data=data,
            )
        except Exception as exc:
            logger.exception("ETAPExpertAgent failed")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(exc)],
            )

    # ----- Backward-compat helper methods -----

    @staticmethod
    def _find_wrong_pattern(question: str) -> tuple[str, str]:
        return find_wrong_pattern(question)

    @staticmethod
    def _find_incomplete_pattern(question: str) -> tuple[str, str]:
        return find_incomplete_pattern(question)

    def get_agent_info(self) -> dict[str, Any]:
        return {
            "name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "knowledge_base": "skills/etap-expert.md",
            "study_type": "etap_expert",
            "supported_formats": ["A (complete)", "B (incomplete)", "C (wrong)", "D (ADMS)"],
        }


# ---------------------------------------------------------------------------
# Module-level convenience — allows `python -m agents.etap_expert_agent` smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agents.etap_expert_agent 'your ETAP question'")
        sys.exit(1)

    agent = ETAPExpertAgent()
    result = agent.answer(" ".join(sys.argv[1:]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
