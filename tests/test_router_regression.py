"""
Regression tests for goal router and dependency execution ordering.
Ensures 100% backward compatibility with all historical goal phrases and default fallbacks.
"""

from __future__ import annotations

import pytest

from agents.models import StudyType
from agents.orchestrator import ChiefEngineeringOrchestrator, get_orchestrator
from agents.router import GoalRouter, determine_execution_order, parse_user_goal


@pytest.fixture
def orchestrator() -> ChiefEngineeringOrchestrator:
    return get_orchestrator()


def test_default_fallback_on_empty_and_unknown(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Empty or unrecognized goals must fall back to LOAD_FLOW + SHORT_CIRCUIT + HARMONIC_ANALYSIS."""
    expected_default = [
        StudyType.LOAD_FLOW,
        StudyType.SHORT_CIRCUIT,
        StudyType.HARMONIC_ANALYSIS,
    ]

    for goal in ["", "   ", "general overview", "random query 12345", None]:
        assert orchestrator._parse_user_goal(goal) == expected_default
        assert parse_user_goal(goal) == expected_default


@pytest.mark.parametrize(
    ("phrase", "expected_study"),
    [
        ("run a load flow simulation", StudyType.LOAD_FLOW),
        ("calculate power flow on line 1", StudyType.LOAD_FLOW),
        ("check voltage profile", StudyType.LOAD_FLOW),
        ("fault analysis on bus 3", StudyType.SHORT_CIRCUIT),
        ("short circuit 3-phase calculation", StudyType.SHORT_CIRCUIT),
        ("calculate sc capacity", StudyType.SHORT_CIRCUIT),
        ("analyze harmonic distortion", StudyType.HARMONIC_ANALYSIS),
        ("thd exceeds 5 percent", StudyType.HARMONIC_ANALYSIS),
        ("voltage distortion check", StudyType.LOAD_FLOW),  # "voltage" triggers LOAD_FLOW
        ("optimize generation costs", StudyType.OPTIMAL_POWER_FLOW),
        ("run opf analysis", StudyType.OPTIMAL_POWER_FLOW),
        ("economic dispatch optimization", StudyType.OPTIMAL_POWER_FLOW),
        ("relay coordination check", StudyType.PROTECTION_COORDINATION),
        ("protect transformer feeder", StudyType.PROTECTION_COORDINATION),
        ("overcurrent coordination curves", StudyType.PROTECTION_COORDINATION),
        ("calculate incident energy and ppe category", StudyType.ARC_FLASH),
        ("arc flash boundary calculation", StudyType.ARC_FLASH),
        ("large motor starting voltage dip", StudyType.MOTOR_STARTING),
        ("motor inrush current analysis", StudyType.MOTOR_STARTING),
        ("transient stability critical clearing time", StudyType.TRANSIENT_STABILITY),
        ("generator swing equation", StudyType.TRANSIENT_STABILITY),
        ("cable sizing for 200A feeder", StudyType.CABLE_SIZING),
        ("conductor ampacity calculation", StudyType.CABLE_SIZING),
        ("substation earth grid mesh voltage", StudyType.EARTH_GRID),
        ("grounding resistance check", StudyType.EARTH_GRID),
        ("solar pv plant integration", StudyType.RENEWABLE_INTEGRATION),
        ("wind farm interconnection study", StudyType.RENEWABLE_INTEGRATION),
        ("battery energy storage system sizing", StudyType.BATTERY_STORAGE),
        ("bess state of charge optimization", StudyType.BATTERY_STORAGE),
        ("scada telemetry mapping", StudyType.SCADA),
        ("iec 61850 substation automation", StudyType.SCADA),
    ],
)
def test_keyword_mapping_single_study(
    orchestrator: ChiefEngineeringOrchestrator,
    phrase: str,
    expected_study: StudyType,
) -> None:
    """Each historical keyword phrase maps to the expected StudyType."""
    studies = orchestrator._parse_user_goal(phrase)
    assert expected_study in studies
    assert expected_study in parse_user_goal(phrase)


def test_multi_study_composite_goal(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Composite goal queries parse into multiple studies without duplicates."""
    goal = "Perform load flow, calculate short circuit faults, and check harmonic distortion"
    studies = orchestrator._parse_user_goal(goal)

    assert StudyType.LOAD_FLOW in studies
    assert StudyType.SHORT_CIRCUIT in studies
    assert StudyType.HARMONIC_ANALYSIS in studies
    assert len(studies) == 3


def test_determine_execution_order_dependencies(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Execution order must always prioritize LOAD_FLOW first as the foundational base case."""
    unordered = [
        StudyType.ARC_FLASH,
        StudyType.SHORT_CIRCUIT,
        StudyType.LOAD_FLOW,
        StudyType.HARMONIC_ANALYSIS,
    ]

    ordered = orchestrator._determine_execution_order(unordered)
    assert ordered[0] == StudyType.LOAD_FLOW
    assert ordered[1] == StudyType.SHORT_CIRCUIT
    assert ordered[2] == StudyType.HARMONIC_ANALYSIS
    assert ordered[3] == StudyType.ARC_FLASH

    # Verify module convenience function gives same result
    assert determine_execution_order(unordered) == ordered


def test_typed_router_direct_enum_and_dict_support() -> None:
    """GoalRouter directly accepts typed lists and dictionary specifications."""
    router = GoalRouter()

    # Direct list of StudyTypes
    typed_input = [StudyType.LOAD_FLOW, StudyType.OPTIMAL_POWER_FLOW]
    assert router.parse_user_goal(typed_input) == typed_input

    # Dict input with study_types key
    dict_input = {"study_types": ["load_flow", "short_circuit"]}
    assert router.parse_user_goal(dict_input) == [
        StudyType.LOAD_FLOW,
        StudyType.SHORT_CIRCUIT,
    ]
