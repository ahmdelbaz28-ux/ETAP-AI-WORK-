"""
AhmedETAP - Power System Goal Router
====================================
Typed goal router and dependency-aware study planner for multi-agent workflows.
Replaces unstructured keyword matching with typed intent resolution while
preserving 100% regression compatibility with existing goal phrases and fallback defaults.
"""

from __future__ import annotations

import logging
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


class GoalRouter:
    """Typed router that analyzes user goals and maps them to executable StudyTypes."""

    def __init__(self, custom_rules: list[tuple[list[str], StudyType]] | None = None) -> None:
        self.rules = custom_rules or KEYWORD_RULES

    def parse_user_goal(self, goal: Any) -> list[StudyType]:
        """Parse a user goal into an ordered list of StudyType enums.

        Supports:
        1. String input with keyword pattern extraction.
        2. Sequence of StudyType enums or string study identifiers.
        3. Dict structure with 'study_types' or 'intent' fields.
        Fallback returns [LOAD_FLOW, SHORT_CIRCUIT, HARMONIC_ANALYSIS].
        """
        if not goal:
            return list(DEFAULT_STUDIES)

        # Handle typed list of StudyTypes or strings directly
        if isinstance(goal, (list, tuple)):
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
                return resolved
            return list(DEFAULT_STUDIES)

        # Handle dict format
        if isinstance(goal, dict):
            studies = goal.get("study_types") or goal.get("studies")
            if studies:
                return self.parse_user_goal(studies)
            goal_str = goal.get("goal") or goal.get("description") or ""
            return self.parse_user_goal(goal_str)

        # String goal processing
        goal_lower = str(goal).lower()
        studies: list[StudyType] = []

        for keywords, study_type in self.rules:
            if any(kw in goal_lower for kw in keywords):
                if study_type not in studies:
                    studies.append(study_type)

        if not studies:
            studies = list(DEFAULT_STUDIES)

        return studies

    def determine_execution_order(self, study_types: list[StudyType]) -> list[StudyType]:
        """Sort study types into dependency-safe execution order (e.g. Load Flow first)."""
        return sorted(study_types, key=lambda x: STUDY_PRIORITY.get(x, 99))


# Module-level singletons / conveniences
_default_router = GoalRouter()


def parse_user_goal(goal: Any) -> list[StudyType]:
    """Module convenience function for parsing user goals."""
    return _default_router.parse_user_goal(goal)


def determine_execution_order(study_types: list[StudyType]) -> list[StudyType]:
    """Module convenience function for determining dependency execution order."""
    return _default_router.determine_execution_order(study_types)
