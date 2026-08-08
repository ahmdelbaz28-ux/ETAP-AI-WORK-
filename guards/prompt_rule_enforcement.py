"""
Prompt Rule Enforcement — Code-Gated Mandatory Rules (F-03 Fix)
================================================================

ARCHITECTURE AUDIT FIX (F-03): 14/27+ prompt YAML files contain
"mandatory" rules expressed only in prompt text (e.g. "MUST use
Python tool for ALL numerical computations"). Per the agent-architecture-audit
skill's Fix Strategy #1: "Code-gate tool requirements — enforce in code,
not just prompt text."

This module provides:
1. ``MANDATORY_TOOL_RULES`` — maps each agent to its required tool calls.
   If an agent's response is missing a required tool invocation, it is
   flagged as a Tool Discipline Failure (L6/L7 in the 12-layer stack).
2. ``MANDATORY_FORMAT_RULES`` — maps each agent to required output format
   fields that MUST appear in the response.
3. ``validate_agent_response()`` — runtime validator that checks if an
   agent's response satisfies its mandatory rules.
4. ``enforce_prompt_rules()`` — decorator/wrapper that blocks responses
   violating MUST_FIX rules and logs violations.

Usage in agent execution pipeline::

    from guards.prompt_rule_enforcement import enforce_prompt_rules

    @enforce_prompt_rules(agent_id="arcflash-agent")
    async def run_arcflash_agent(query: str) -> dict:
        ...  # actual agent execution

Or as a post-execution check::

    from guards.prompt_rule_enforcement import validate_agent_response

    result = validate_agent_response(
        agent_id="arcflash-agent",
        response_text=response.content,
        tool_calls_made=response.tool_calls,
        study_type="ARC_FLASH",
    )
    if not result.passed:
        logger.error("Agent response violates mandatory rules: %s", result.violations)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

from guards.base import GuardMode, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


# ─── Mandatory Tool Call Rules (per agent) ───────────────────────────────
# Maps agent_id → list of required tool names that MUST be called during
# execution. These are code-gated versions of "MUST use tool X" rules
# currently only expressed in prompt text.

MANDATORY_TOOL_RULES: dict[str, list[str]] = {
    # Life-safety agents: MUST use run_python for all numerical computations
    "arcflash-agent": ["run_python"],
    "short-circuit-agent": ["run_python"],
    "protection-agent": ["run_python"],
    "motorstarting-agent": ["run_python"],
    "load-flow-agent": ["run_python"],
    "harmonic-agent": ["run_python"],
    "opf-agent": ["run_python"],
    "cable-sizing-agent": ["run_python"],
    "earth-grid-agent": ["run_python"],
    "battery-storage-agent": ["run_python"],
    "stability-agent": ["run_python"],
    # ETAP operations agents
    "etap-engineer-agent": ["run_python"],
    "etap-expert-agent": ["run_python"],
    # Code quality
    "code-guard-agent": ["run_python"],
    # Weather — uses weather_tool, not run_python
    "weather-agent": ["weatherTool"],
}

# Study types that are life-safety critical and MUST go through validation_agent
LIFE_SAFETY_STUDY_TYPES = frozenset({
    "ARC_FLASH",
    "SHORT_CIRCUIT",
    "EARTH_GRID",
    "PROTECTION_COORDINATION",
    "CABLE_SIZING",
    "BATTERY_SIZING",
})

# ─── Mandatory Format Rules (per agent) ─────────────────────────────────
# Maps agent_id → list of (field_name, regex_pattern) tuples.
# The regex is searched in the response text. If not found, the response
# is missing a mandatory format field.

MANDATORY_FORMAT_RULES: dict[str, list[tuple[str, str]]] = {
    "arcflash-agent": [
        ("incident_energy", r"incident\s*energy|INCIDENT\s*ENERGY"),
        ("ppe_category", r"PPE\s*(CATEGORY|Level)|ppe"),
        ("arc_flash_boundary", r"arc\s*flash\s*boundary|AFB|ARC\s*FLASH\s*BOUNDARY"),
        ("standard", r"IEEE\s*1584"),
        ("assumptions", r"ASSUMPTIONS|assumptions"),
    ],
    "short-circuit-agent": [
        ("fault_current", r"fault\s*current|kA"),
        ("standard", r"IEC\s*60909|IEEE"),
        ("assumptions", r"ASSUMPTIONS|assumptions"),
    ],
    "load-flow-agent": [
        ("voltage", r"voltage|pu|kV"),
        ("convergence", r"converg|Convergence"),
        ("assumptions", r"ASSUMPTIONS|assumptions"),
    ],
    "protection-agent": [
        ("relay_settings", r"relay|pickup|time\s*dial|TCC"),
        ("standard", r"IEC\s*60255|IEEE\s*C37|IEEE\s*242"),
        ("assumptions", r"ASSUMPTIONS|assumptions"),
    ],
}


# ─── Validation Result ───────────────────────────────────────────────────

@dataclass
class PromptRuleViolation:
    """A single prompt rule violation."""
    rule_id: str
    agent_id: str
    rule_type: str  # "tool_call" or "format_field" or "validation_gate"
    description: str
    severity: GuardSeverity
    evidence: str = ""


@dataclass
class PromptRuleResult:
    """Aggregate result of prompt rule validation."""
    agent_id: str
    violations: list[PromptRuleViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when no MUST_FIX violations exist."""
        return not any(v.severity == GuardSeverity.MUST_FIX for v in self.violations)

    @property
    def must_fix_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == GuardSeverity.MUST_FIX)

    def to_guard_result(self) -> GuardResult:
        """Convert to base GuardResult for compatibility with guard framework."""
        return GuardResult(
            guard_name="prompt_rule_enforcement",
            mode=GuardMode.GUARD_PASS,
            violations=[
                GuardViolation(
                    rule_id=v.rule_id,
                    rule_name=f"F-03: {v.rule_type}",
                    severity=v.severity,
                    description=v.description,
                    location=f"agent:{v.agent_id}",
                    evidence=v.evidence[:200],
                )
                for v in self.violations
            ],
            metadata={"agent_id": self.agent_id},
        )


# ─── Core Validation Function ───────────────────────────────────────────

def validate_agent_response(
    agent_id: str,
    response_text: str,
    tool_calls_made: Optional[list[str]] = None,
    study_type: Optional[str] = None,
    validation_agent_called: bool = False,
) -> PromptRuleResult:
    """Validate that an agent's response satisfies its mandatory prompt rules.

    Parameters
    ----------
    agent_id : str
        The agent identifier (e.g. "arcflash-agent").
    response_text : str
        The full text of the agent's response.
    tool_calls_made : list[str], optional
        List of tool names that were actually called during execution.
    study_type : str, optional
        The study type (e.g. "ARC_FLASH"), used for life-safety checks.
    validation_agent_called : bool
        Whether the validation_agent was invoked (required for life-safety).

    Returns
    -------
    PromptRuleResult
        Validation result with any violations.
    """
    violations: list[PromptRuleViolation] = []
    tool_calls = set(tool_calls_made or [])

    # ── Check 1: Mandatory tool calls ─────────────────────────────────
    required_tools = MANDATORY_TOOL_RULES.get(agent_id, [])
    for tool_name in required_tools:
        if tool_name not in tool_calls:
            is_life_safety = agent_id in {
                "arcflash-agent", "short-circuit-agent", "protection-agent",
            }
            violations.append(PromptRuleViolation(
                rule_id=f"F03-TOOL-{tool_name}",
                agent_id=agent_id,
                rule_type="tool_call",
                description=(
                    f"Agent '{agent_id}' did not call required tool '{tool_name}'. "
                    f"This violates the MANDATORY RULE in the agent's prompt that "
                    f"requires using {tool_name} for all numerical computations. "
                    f"Per SKILL.md Fix Strategy #1: 'Code-gate tool requirements — "
                    f"enforce in code, not just prompt text.'"
                ),
                severity=GuardSeverity.MUST_FIX if is_life_safety else GuardSeverity.SHOULD_FIX,
                evidence=f"tool_calls_made={sorted(tool_calls)}, required={sorted(required_tools)}",
            ))

    # ── Check 2: Mandatory format fields ──────────────────────────────
    format_rules = MANDATORY_FORMAT_RULES.get(agent_id, [])
    for field_name, pattern in format_rules:
        if not re.search(pattern, response_text, re.IGNORECASE):
            is_life_safety = agent_id in {"arcflash-agent", "short-circuit-agent"}
            violations.append(PromptRuleViolation(
                rule_id=f"F03-FMT-{field_name}",
                agent_id=agent_id,
                rule_type="format_field",
                description=(
                    f"Agent '{agent_id}' response is missing mandatory format field "
                    f"'{field_name}' (pattern: /{pattern}/). The prompt declares this "
                    f"field as 'mandatory' but the response does not contain it."
                ),
                severity=GuardSeverity.MUST_FIX if is_life_safety else GuardSeverity.SHOULD_FIX,
                evidence=f"response_length={len(response_text)}, pattern=/{pattern}/",
            ))

    # ── Check 3: Life-safety validation gate ──────────────────────────
    # The coordinator prompt states: "validation_agent MUST review the
    # specialist's result before the response is returned to the user"
    # for any life-safety calculation.
    if study_type and study_type.upper() in LIFE_SAFETY_STUDY_TYPES:
        if not validation_agent_called:
            violations.append(PromptRuleViolation(
                rule_id="F03-VAL-life_safety",
                agent_id=agent_id,
                rule_type="validation_gate",
                description=(
                    f"Life-safety study type '{study_type}' was executed but "
                    f"validation_agent was NOT called to review the result. "
                    f"The coordinator prompt mandates: 'validation_agent MUST review "
                    f"the specialist's result before the response is returned to the user' "
                    f"for any life-safety calculation. This is a Tool Discipline Failure "
                    f"(L6 in the 12-layer stack)."
                ),
                severity=GuardSeverity.MUST_FIX,
                evidence=f"study_type={study_type}, validation_agent_called={validation_agent_called}",
            ))

    # ── Check 4: Fallback agent numerical refusal ─────────────────────
    # The fallback_agent prompt states: "You MUST REFUSE to give numerical
    # answers for any life-safety calculation." Check that fallback responses
    # don't contain bare numerical answers.
    if agent_id == "fallback-agent":
        # Look for patterns like "X = 123.45 kA" or "result: 8.5 cal/cm²"
        # without a "REFUSE" or "cannot" disclaimer
        numerical_pattern = r'\d+\.?\d*\s*(kA|MW|MVAr|cal/cm|pu|kV|mm|V|A|Ω|Hz)'
        has_numerical = bool(re.search(numerical_pattern, response_text))
        has_refusal = bool(re.search(r'refuse|cannot|unable|not available|do not', response_text, re.IGNORECASE))
        if has_numerical and not has_refusal:
            violations.append(PromptRuleViolation(
                rule_id="F03-FALL-numerical",
                agent_id=agent_id,
                rule_type="format_field",
                description=(
                    "Fallback agent returned numerical answers for what may be a "
                    "life-safety calculation without a refusal disclaimer. The prompt "
                    "states: 'You MUST REFUSE to give numerical answers for any "
                    "life-safety calculation.'"
                ),
                severity=GuardSeverity.MUST_FIX,
                evidence="response contains numerical values without refusal disclaimer",
            ))

    return PromptRuleResult(agent_id=agent_id, violations=violations)


# ─── Decorator for Enforcement ──────────────────────────────────────────

def enforce_prompt_rules(agent_id: str) -> Callable:
    """Decorator that validates agent response against mandatory prompt rules.

    Blocks the response (raises RuntimeError) if MUST_FIX violations are
    found. Logs SHOULD_FIX violations as warnings.

    Usage::

        @enforce_prompt_rules(agent_id="arcflash-agent")
        async def run_agent(query: str) -> AgentResponse:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            # Extract response text and tool calls from the result
            response_text = ""
            tool_calls_made: list[str] = []
            study_type = kwargs.get("study_type")

            if hasattr(result, "content"):
                response_text = str(result.content)
            elif isinstance(result, str):
                response_text = result
            elif isinstance(result, dict):
                response_text = str(result.get("content", result.get("response", "")))
                tool_calls_made = list(result.get("tool_calls", result.get("tools_used", [])))

            if hasattr(result, "tool_calls"):
                tool_calls_made = [tc.name if hasattr(tc, "name") else str(tc)
                                   for tc in result.tool_calls]

            # Validate
            validation = validate_agent_response(
                agent_id=agent_id,
                response_text=response_text,
                tool_calls_made=tool_calls_made,
                study_type=study_type,
            )

            if not validation.passed:
                must_fix = [v for v in validation.violations
                            if v.severity == GuardSeverity.MUST_FIX]
                should_fix = [v for v in validation.violations
                              if v.severity == GuardSeverity.SHOULD_FIX]

                for v in should_fix:
                    logger.warning(
                        "F-03 SHOULD_FIX: %s (agent=%s)", v.description, agent_id
                    )

                if must_fix:
                    _violation_summary = "; ".join(v.rule_id for v in must_fix)
                    logger.error(
                        "F-03 MUST_FIX VIOLATIONS: %s — blocking response from agent '%s'. "
                        "Violations: %s",
                        _violation_summary,
                        agent_id,
                        [v.description[:100] for v in must_fix],
                    )
                    raise RuntimeError(
                        f"Agent '{agent_id}' response blocked: violates mandatory prompt rules "
                        f"({_violation_summary}). See logs for details."
                    )

            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Sync version for non-async agent functions
            result = func(*args, **kwargs)

            response_text = ""
            tool_calls_made: list[str] = []
            study_type = kwargs.get("study_type")

            if hasattr(result, "content"):
                response_text = str(result.content)
            elif isinstance(result, str):
                response_text = result
            elif isinstance(result, dict):
                response_text = str(result.get("content", result.get("response", "")))
                tool_calls_made = list(result.get("tool_calls", result.get("tools_used", [])))

            validation = validate_agent_response(
                agent_id=agent_id,
                response_text=response_text,
                tool_calls_made=tool_calls_made,
                study_type=study_type,
            )

            if not validation.passed:
                must_fix = [v for v in validation.violations
                            if v.severity == GuardSeverity.MUST_FIX]
                if must_fix:
                    _violation_summary = "; ".join(v.rule_id for v in must_fix)
                    logger.error(
                        "F-03 MUST_FIX: %s — blocking response from '%s'",
                        _violation_summary, agent_id,
                    )
                    raise RuntimeError(
                        f"Agent '{agent_id}' response blocked: violates mandatory rules "
                        f"({_violation_summary})."
                    )

            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ─── API Boundary Enforcement ───────────────────────────────────────────

def enforce_at_api_boundary(
    agent_id: str,
    response: dict[str, Any],
    study_type: Optional[str] = None,
) -> dict[str, Any]:
    """Enforce prompt rules at the API boundary before returning to client.

    This is the last-chance enforcement point. If mandatory rules are
    violated, the response is annotated with violation metadata and
    the 'success' flag is set to False for MUST_FIX violations.

    Parameters
    ----------
    agent_id : str
        The agent identifier.
    response : dict
        The API response dict to validate and potentially modify.
    study_type : str, optional
        The study type for life-safety checks.

    Returns
    -------
    dict
        The response, possibly annotated with violation info.
    """
    response_text = str(response.get("content", response.get("result", "")))
    tool_calls = list(response.get("tool_calls", response.get("tools_used", [])))
    validation_called = response.get("validation_agent_called", False)

    validation = validate_agent_response(
        agent_id=agent_id,
        response_text=response_text,
        tool_calls_made=tool_calls,
        study_type=study_type,
        validation_agent_called=validation_called,
    )

    if validation.violations:
        response["prompt_rule_violations"] = [
            {
                "rule_id": v.rule_id,
                "rule_type": v.rule_type,
                "severity": v.severity.value,
                "description": v.description,
            }
            for v in validation.violations
        ]

        if not validation.passed:
            response["success"] = False
            response["error"] = (
                f"Response blocked by prompt rule enforcement (F-03): "
                f"{validation.must_fix_count} MUST_FIX violations."
            )
            logger.error(
                "F-03 API BOUNDARY BLOCK: agent=%s, violations=%s",
                agent_id,
                [v.rule_id for v in validation.violations if v.severity == GuardSeverity.MUST_FIX],
            )

    return response


__all__ = [
    "MANDATORY_TOOL_RULES",
    "MANDATORY_FORMAT_RULES",
    "LIFE_SAFETY_STUDY_TYPES",
    "validate_agent_response",
    "enforce_prompt_rules",
    "enforce_at_api_boundary",
    "PromptRuleViolation",
    "PromptRuleResult",
]
