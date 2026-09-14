"""
AhmedETAP - Power System Goal Router
====================================
Typed goal router and dependency-aware study planner for multi-agent workflows.
Replaces unstructured keyword matching with typed intent resolution while
preserving 100% regression compatibility with existing goal phrases and fallback defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agents.models import StudyType

logger = logging.getLogger(__name__)

# Canonical priority order for execution dependencies
STUDY_PRIORITY: dict[StudyType, int] = {
    StudyType.LOAD_FLOW: 1,
    StudyType.SHORT_CIRCUIT: 2,
    StudyType.HARMONIC_ANALYSIS: 3,
    StudyType.OPTIMAL_POWER_FLOW: 4,
    StudyType.PROTECTION_COORDINATION: 5,
    StudyType.MOTOR_STARTING: 6,
    StudyType.ARC_FLASH: 7,
    StudyType.TRANSIENT_STABILITY: 8,
    StudyType.CABLE_SIZING: 9,
    StudyType.EARTH_GRID: 10,
    StudyType.RENEWABLE_INTEGRATION: 11,
    StudyType.BATTERY_STORAGE: 12,
    StudyType.SCADA: 13,
}

# Canonical keyword dictionary for heuristic goal analysis
KEYWORD_RULES: list[tuple[list[str], StudyType]] = [
    (["load flow", "power flow", "voltage"], StudyType.LOAD_FLOW),
    (["fault", "short circuit", "sc"], StudyType.SHORT_CIRCUIT),
    (["harmonic", "distortion", "thd"], StudyType.HARMONIC_ANALYSIS),
    (["optimize", "optimization", "opf", "economic"], StudyType.OPTIMAL_POWER_FLOW),
    (["protect", "coordination", "relay"], StudyType.PROTECTION_COORDINATION),
    (["arc flash", "incident energy", "ppe"], StudyType.ARC_FLASH),
    (["motor", "starting", "inrush"], StudyType.MOTOR_STARTING),
    (["stability", "transient", "swing"], StudyType.TRANSIENT_STABILITY),
    (["cable", "ampacity"], StudyType.CABLE_SIZING),
    (["earth", "ground", "grounding", "grid"], StudyType.EARTH_GRID),
    (["solar", "wind", "renewable", "pv"], StudyType.RENEWABLE_INTEGRATION),
    (["battery", "bess", "storage"], StudyType.BATTERY_STORAGE),
    (["scada", "telemetry", "61850"], StudyType.SCADA),
]

DEFAULT_STUDIES: list[StudyType] = [
    StudyType.LOAD_FLOW,
    StudyType.SHORT_CIRCUIT,
    StudyType.HARMONIC_ANALYSIS,
]


@dataclass
class RouterDecision:
    """Typed decision returned by the goal router containing study types, confidence, and reasoning."""

    study_types: list[StudyType]
    confidence: float
    reason: str


class GoalRouter:
    """Typed router that analyzes user goals and maps them to executable StudyTypes."""

    def __init__(self, custom_rules: list[tuple[list[str], StudyType]] | None = None) -> None:
        self.rules = custom_rules or KEYWORD_RULES

    def route(self, goal: Any) -> RouterDecision:
        """Route a user goal into a typed RouterDecision with confidence and reasoning.

        Supports:
        1. Empty / whitespace -> baseline default fallback.
        2. Sequence of StudyType enums or string study identifiers.
        3. Dict structure with 'study_types' or 'intent' fields.
        4. String input with keyword pattern extraction.
        Fallback returns [LOAD_FLOW, SHORT_CIRCUIT, HARMONIC_ANALYSIS].
        """
        if not goal or (isinstance(goal, str) and not goal.strip()):
            return RouterDecision(
                study_types=list(DEFAULT_STUDIES),
                confidence=0.5,
                reason="Default baseline studies for empty/unspecified goal",
            )

        if isinstance(goal, (list, tuple)):
            return self._resolve_list_goal(goal)

        if isinstance(goal, dict):
            return self._resolve_dict_goal(goal)

        return self._resolve_string_goal(str(goal))

    def _resolve_list_goal(self, goal: list | tuple) -> RouterDecision:
        """Resolve a list or tuple of StudyTypes or string identifiers."""
        resolved: list[StudyType] = []
        for item in goal:
            if isinstance(item, StudyType):
                resolved.append(item)
            elif isinstance(item, str):
                for st in StudyType:
                    if st.value == item:
                        resolved.append(st)
                        break
        if resolved:
            return RouterDecision(
                study_types=resolved,
                confidence=1.0,
                reason="Explicit study types provided directly",
            )
        return RouterDecision(
            study_types=list(DEFAULT_STUDIES),
            confidence=0.5,
            reason="Unrecognized sequence elements; default baseline fallback",
        )

    def _resolve_dict_goal(self, goal: dict) -> RouterDecision:
        """Resolve a dict goal by extracting study types or a nested goal string."""
        studies = goal.get("study_types") or goal.get("studies")
        if studies:
            return self.route(studies)
        goal_str = goal.get("goal") or goal.get("description") or ""
        return self.route(goal_str)

    def _resolve_string_goal(self, goal: str) -> RouterDecision:
        """Resolve a string goal by matching against keyword rules."""
        goal_lower = goal.lower()
        studies: list[StudyType] = []
        matched_reasons: list[str] = []

        for keywords, study_type in self.rules:
            matched_kws = [kw for kw in keywords if kw in goal_lower]
            if matched_kws:
                if study_type not in studies:
                    studies.append(study_type)
                    matched_reasons.append(f"{study_type.value} ('{matched_kws[0]}')")

        if studies:
            confidence = 0.95 if len(studies) > 1 else 0.90
            return RouterDecision(
                study_types=studies,
                confidence=confidence,
                reason=f"Matched keywords: {', '.join(matched_reasons)}",
            )

        return RouterDecision(
            study_types=list(DEFAULT_STUDIES),
            confidence=0.3,
            reason="Unrecognized goal intent; safe fallback to baseline load flow, short circuit, harmonic analysis",
        )

    def parse_user_goal(self, goal: Any) -> list[StudyType]:
        """Parse a user goal into an ordered list of StudyType enums.

        Backward-compatible shim returning study_types from RouterDecision.
        """
        return self.route(goal).study_types

    def determine_execution_order(self, study_types: list[StudyType]) -> list[StudyType]:
        """Sort study types into dependency-safe execution order (e.g. Load Flow first)."""
        return sorted(study_types, key=lambda x: STUDY_PRIORITY.get(x, 99))


# Module-level singletons / conveniences
_default_router = GoalRouter()


def route_user_goal(goal: Any) -> RouterDecision:
    """Module convenience function for typed goal routing."""
    return _default_router.route(goal)


def parse_user_goal(goal: Any) -> list[StudyType]:
    """Module convenience function for parsing user goals."""
    return _default_router.parse_user_goal(goal)


def determine_execution_order(study_types: list[StudyType]) -> list[StudyType]:
    """Module convenience function for determining dependency execution order."""
    return _default_router.determine_execution_order(study_types)
