"""
Regression tests for goal router and dependency execution ordering.
Ensures 100% backward compatibility with all historical goal phrases and default fallbacks.
"""

from __future__ import annotations

import pytest

from agents.models import StudyType
from agents.optimizers.bandit_router import ContextualBanditRouter
from agents.orchestrator import ChiefEngineeringOrchestrator, get_orchestrator
from agents.router import (
    DEFAULT_STUDIES,
    GoalRouter,
    RouterDecision,
    determine_execution_order,
    parse_user_goal,
)
from core.exceptions import RoutingResolutionError


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


def test_router_decision_confidence_threshold_evaluation() -> None:
    """M3.1 Gating: RouterDecision.is_confident(0.65) boundary evaluation (0.64 => False, 0.65 => True)."""
    # 0.64 -> Below 0.65 threshold
    decision_low = RouterDecision(
        study_types=[StudyType.LOAD_FLOW],
        confidence=0.64,
        reason="Marginal confidence",
    )
    assert decision_low.is_confident(0.65) is False
    assert decision_low.is_confident() is False  # Default threshold 0.65

    # 0.65 -> Exactly at threshold
    decision_exact = RouterDecision(
        study_types=[StudyType.LOAD_FLOW],
        confidence=0.65,
        reason="Threshold boundary",
    )
    assert decision_exact.is_confident(0.65) is True
    assert decision_exact.is_confident() is True  # Default threshold 0.65

    # 0.66 -> Above threshold
    decision_high = RouterDecision(
        study_types=[StudyType.LOAD_FLOW],
        confidence=0.66,
        reason="High confidence",
    )
    assert decision_high.is_confident(0.65) is True
    assert decision_high.is_confident() is True

    # Custom threshold verification (e.g. 0.80)
    decision_mid = RouterDecision(
        study_types=[StudyType.LOAD_FLOW],
        confidence=0.75,
        reason="Mid confidence",
    )
    assert decision_mid.is_confident(0.80) is False
    assert decision_mid.is_confident(0.70) is True


def test_goal_router_resolution_error_and_safe_fallback() -> None:
    """M3.1 Gating: GoalRouter raises RoutingResolutionError on unreachable intents or falls back safely."""
    router = GoalRouter()
    unreachable_goal = "completely_unrecognized_system_intent_xyz_9999"

    # 1. Safe fail-closed fallback when raise_on_unreachable=False (default behavior)
    fallback_decision = router.route(unreachable_goal, min_confidence=0.65, raise_on_unreachable=False)
    assert fallback_decision.confidence < 0.65
    assert fallback_decision.is_confident(0.65) is False
    assert fallback_decision.study_types == DEFAULT_STUDIES
    assert "safe fallback" in fallback_decision.reason.lower()

    # 2. Precise RoutingResolutionError when raise_on_unreachable=True
    with pytest.raises(RoutingResolutionError) as exc_info:
        router.route(unreachable_goal, min_confidence=0.65, raise_on_unreachable=True)

    err = exc_info.value
    assert err.code == "ROUTING_RESOLUTION_FAILED"
    assert unreachable_goal in err.goal
    assert err.confidence == fallback_decision.confidence
    assert err.threshold == 0.65
    assert err.confidence < err.threshold

    # 3. resolve_intent propagates raise_on_unreachable=True
    with pytest.raises(RoutingResolutionError):
        router.resolve_intent(unreachable_goal, min_confidence=0.65, raise_on_unreachable=True)


def test_contextual_bandit_router_resolution_error_and_safe_fallback() -> None:
    """M3.1 Gating: ContextualBanditRouter raises RoutingResolutionError or delegates to fallback safely."""
    # 1. Fallback delegation when confidence < confidence_threshold
    bandit_router = ContextualBanditRouter(confidence_threshold=0.75)
    unreachable_goal = "completely_unrecognized_system_intent_xyz_8888"

    # Safe fallback when raise_on_unreachable=False (delegates to fallback router)
    fallback_decision = bandit_router.route(unreachable_goal, min_confidence=0.65, raise_on_unreachable=False)
    assert fallback_decision.confidence < 0.65
    assert fallback_decision.is_confident(0.65) is False
    assert fallback_decision.study_types == DEFAULT_STUDIES

    # Precise RoutingResolutionError when raise_on_unreachable=True via fallback
    with pytest.raises(RoutingResolutionError) as exc_info:
        bandit_router.route(unreachable_goal, min_confidence=0.65, raise_on_unreachable=True)

    err = exc_info.value
    assert err.code == "ROUTING_RESOLUTION_FAILED"
    assert unreachable_goal in err.goal
    assert err.confidence < err.threshold
    assert err.threshold == 0.65

    # 2. Direct bandit RoutingResolutionError when decision.confidence < min_confidence
    direct_bandit = ContextualBanditRouter(confidence_threshold=0.5)
    with pytest.raises(RoutingResolutionError) as exc_direct:
        direct_bandit.route(unreachable_goal, min_confidence=0.85, raise_on_unreachable=True)

    err_direct = exc_direct.value
    assert err_direct.code == "ROUTING_RESOLUTION_FAILED"
    assert unreachable_goal in err_direct.goal
    assert err_direct.threshold == 0.85
    assert err_direct.confidence < 0.85

    # 3. resolve_intent propagates raise_on_unreachable=True
    with pytest.raises(RoutingResolutionError):
        bandit_router.resolve_intent(unreachable_goal, min_confidence=0.65, raise_on_unreachable=True)
