"""
AhmedETAP - Router Completeness Gate Test Suite (Package P4)
============================================================
Comprehensive gate tests verifying 100% completeness of goal routing,
dependency scheduling, keyword rules, and registry mappings across
all 17 canonical StudyType members per AGENTS.md and ADR-0001.

Acceptance Gates:
1. 100% coverage of all 17 StudyType members in STUDY_PRIORITY (ranks 1..17).
2. 100% coverage of all 17 StudyType members as targets in KEYWORD_RULES.
3. 100% coverage of all 17 StudyType string values in STUDY_TYPE_MAPPING.
4. Precision routing for newly added types (DIGITAL_TWIN, ETAP_EXPERT, ETAP_GUI, GENERATIVE_DESIGN).
5. Immutable default baseline fallback (LOAD_FLOW, SHORT_CIRCUIT, HARMONIC_ANALYSIS).
6. Dependency-safe execution ordering for mixed traditional and new study workflows.
"""

from __future__ import annotations

import random

import pytest

from agents.models import StudyType
from agents.orchestrator import ChiefEngineeringOrchestrator, get_orchestrator
from agents.registry import STUDY_TYPE_MAPPING, get_agent_for_study, get_study_type_mapping
from agents.router import (
    DEFAULT_STUDIES,
    KEYWORD_RULES,
    STUDY_PRIORITY,
    GoalRouter,
    determine_execution_order,
    parse_user_goal,
    route_user_goal,
)

EXPECTED_PRIORITY_ORDER: list[tuple[StudyType, int]] = [
    (StudyType.LOAD_FLOW, 1),
    (StudyType.SHORT_CIRCUIT, 2),
    (StudyType.HARMONIC_ANALYSIS, 3),
    (StudyType.OPTIMAL_POWER_FLOW, 4),
    (StudyType.PROTECTION_COORDINATION, 5),
    (StudyType.MOTOR_STARTING, 6),
    (StudyType.ARC_FLASH, 7),
    (StudyType.TRANSIENT_STABILITY, 8),
    (StudyType.CABLE_SIZING, 9),
    (StudyType.EARTH_GRID, 10),
    (StudyType.RENEWABLE_INTEGRATION, 11),
    (StudyType.BATTERY_STORAGE, 12),
    (StudyType.SCADA, 13),
    (StudyType.DIGITAL_TWIN, 14),
    (StudyType.GENERATIVE_DESIGN, 15),
    (StudyType.ETAP_EXPERT, 16),
    (StudyType.ETAP_GUI, 17),
]


@pytest.fixture
def orchestrator() -> ChiefEngineeringOrchestrator:
    return get_orchestrator()


# ==============================================================================
# Gate 1: 100% Coverage of StudyType Members in STUDY_PRIORITY
# ==============================================================================

def test_all_17_study_types_in_study_priority() -> None:
    """Verify that every member of StudyType is present in STUDY_PRIORITY with valid ranks."""
    all_study_types = list(StudyType)
    assert len(all_study_types) == 17, f"Expected 17 StudyType members, found {len(all_study_types)}"
    assert len(STUDY_PRIORITY) == 17, f"Expected 17 entries in STUDY_PRIORITY, found {len(STUDY_PRIORITY)}"

    for st in all_study_types:
        assert st in STUDY_PRIORITY, f"StudyType.{st.name} ({st.value}) missing from STUDY_PRIORITY"

    # Verify priorities are unique integers strictly from 1 to 17
    ranks = list(STUDY_PRIORITY.values())
    assert sorted(ranks) == list(range(1, 18)), f"Priorities must span exactly 1..17, got {sorted(ranks)}"

    # Verify exact canonical priority mapping
    for st, expected_rank in EXPECTED_PRIORITY_ORDER:
        assert STUDY_PRIORITY[st] == expected_rank, (
            f"Expected {st.name} to have priority {expected_rank}, got {STUDY_PRIORITY[st]}"
        )


# ==============================================================================
# Gate 2: 100% Coverage of StudyType Members in KEYWORD_RULES
# ==============================================================================

def test_all_17_study_types_covered_in_keyword_rules() -> None:
    """Verify that every member of StudyType has at least one rule in KEYWORD_RULES."""
    all_study_types = set(StudyType)
    covered_study_types = {target for _, target in KEYWORD_RULES}

    missing_types = all_study_types - covered_study_types
    assert not missing_types, f"StudyType members missing from KEYWORD_RULES: {missing_types}"
    assert len(covered_study_types) == 17, f"Expected 17 covered types, got {len(covered_study_types)}"

    # Validate rule keywords integrity
    for keywords, target in KEYWORD_RULES:
        assert isinstance(target, StudyType), f"Rule target {target} must be an instance of StudyType"
        assert len(keywords) > 0, f"Keyword list for {target} must not be empty"
        for kw in keywords:
            assert isinstance(kw, str), f"Keyword '{kw}' for {target} must be a string"
            assert kw.strip(), f"Keyword '{kw}' for {target} must be a non-empty string"
            assert kw == kw.lower(), f"Keyword '{kw}' must be lower-case for case-insensitive matching"


# ==============================================================================
# Gate 3: 100% Coverage of StudyType Members in Registry Mapping
# ==============================================================================

def test_all_17_study_types_mapped_in_registry() -> None:
    """Verify that every member of StudyType has a string mapping in STUDY_TYPE_MAPPING."""
    all_study_types = list(StudyType)
    mapping = get_study_type_mapping()

    assert mapping == STUDY_TYPE_MAPPING, "get_study_type_mapping() must return a copy of STUDY_TYPE_MAPPING"

    for st in all_study_types:
        assert st.value in STUDY_TYPE_MAPPING, f"StudyType.{st.name} value '{st.value}' missing from STUDY_TYPE_MAPPING"
        target_agent_key = STUDY_TYPE_MAPPING[st.value]
        assert isinstance(target_agent_key, str), f"Mapped agent key for {st.value} must be a string"
        assert target_agent_key.strip(), f"Mapped agent key for {st.value} must be a non-empty string"


def test_registry_get_agent_for_study(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Verify get_agent_for_study resolves agents for traditional and newly mapped types."""
    for st in StudyType:
        agent = get_agent_for_study(orchestrator.agents, st)
        # Agent might be None if optional external dependency is absent, but registry lookup must not throw
        if agent is not None:
            assert hasattr(agent, "execute"), f"Agent for {st} must have an execute method"


# ==============================================================================
# Gate 4: Precision Routing for Newly Added Study Types
# ==============================================================================

@pytest.mark.parametrize(
    ("phrase", "expected_study"),
    [
        # DIGITAL_TWIN keywords
        ("build a digital twin for real-time monitoring", StudyType.DIGITAL_TWIN),
        ("twin model calibration with field telemetry", StudyType.DIGITAL_TWIN),
        ("real-time twin synchronization", StudyType.DIGITAL_TWIN),
        ("state estimation twin telemetry update", StudyType.DIGITAL_TWIN),
        # ETAP_EXPERT keywords
        ("need etap expert assistance for design review", StudyType.ETAP_EXPERT),
        ("provide expert advice for substation rating", StudyType.ETAP_EXPERT),
        ("etap rule compliance verification", StudyType.ETAP_EXPERT),
        ("output the results in format a", StudyType.ETAP_EXPERT),
        ("generate recommendation in format b", StudyType.ETAP_EXPERT),
        # ETAP_GUI keywords
        ("etap gui navigation instructions", StudyType.ETAP_GUI),
        ("gui guide for adding bus and transformer", StudyType.ETAP_GUI),
        ("follow one-line diagram step by step", StudyType.ETAP_GUI),
        ("user interface guide for one-line editor", StudyType.ETAP_GUI),
        # GENERATIVE_DESIGN keywords
        ("generative design for 115kv substation", StudyType.GENERATIVE_DESIGN),
        ("substation design parameter estimation", StudyType.GENERATIVE_DESIGN),
        ("sld synthesis for industrial plant", StudyType.GENERATIVE_DESIGN),
        ("topology synthesis based on load requirements", StudyType.GENERATIVE_DESIGN),
    ],
)
def test_precision_keyword_routing_new_study_types(
    orchestrator: ChiefEngineeringOrchestrator,
    phrase: str,
    expected_study: StudyType,
) -> None:
    """Newly added study types must route precisely without falling back to defaults."""
    # Test via parse_user_goal
    studies = parse_user_goal(phrase)
    assert expected_study in studies, f"Expected {expected_study} in parsed studies for '{phrase}', got {studies}"

    # Test via route_user_goal
    decision = route_user_goal(phrase)
    assert expected_study in decision.study_types
    assert decision.confidence >= 0.90, f"Expected high confidence (>=0.90), got {decision.confidence}"
    assert expected_study.value in decision.reason

    # Test via ChiefEngineeringOrchestrator shim
    orch_studies = orchestrator._parse_user_goal(phrase)
    assert expected_study in orch_studies


def test_composite_goals_with_new_and_traditional_studies() -> None:
    """Composite queries combining new and traditional studies must route all required types."""
    goal = "Perform generative design for substation, then run load flow and setup digital twin"
    decision = route_user_goal(goal)

    assert StudyType.GENERATIVE_DESIGN in decision.study_types
    assert StudyType.LOAD_FLOW in decision.study_types
    assert StudyType.DIGITAL_TWIN in decision.study_types
    assert decision.confidence == 0.95
    assert len(decision.study_types) == 3


# ==============================================================================
# Gate 5: Default Baseline Fallback Immutability
# ==============================================================================

def test_default_baseline_fallback_immutability(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Empty or unrecognized goals must fall back strictly to [LOAD_FLOW, SHORT_CIRCUIT, HARMONIC_ANALYSIS]."""
    test_cases = [
        "",
        "    ",
        None,
        "completely unknown arbitrary text 12345",
        "xyz abc 987654",
        [],
        ["unrecognized_study_type_here"],
        {"goal": ""},
        {"goal": "unrecognized goal text"},
    ]

    for case in test_cases:
        decision = route_user_goal(case)
        assert decision.study_types == DEFAULT_STUDIES, (
            f"Case {case!r} failed to produce DEFAULT_STUDIES, got {decision.study_types}"
        )
        assert decision.confidence in (0.3, 0.5), (
            f"Expected fallback confidence (0.3 or 0.5), got {decision.confidence}"
        )
        assert parse_user_goal(case) == DEFAULT_STUDIES
        assert orchestrator._parse_user_goal(case) == DEFAULT_STUDIES


# ==============================================================================
# Gate 6: Dependency-Safe Execution Ordering
# ==============================================================================

def test_determine_execution_order_sorting_all_17() -> None:
    """Sorting all 17 study types in reverse or random order must yield canonical 1..17 order."""
    all_studies = [st for st, _ in EXPECTED_PRIORITY_ORDER]

    # Test reverse order
    reversed_studies = list(reversed(all_studies))
    sorted_studies = determine_execution_order(reversed_studies)
    assert sorted_studies == all_studies, "Reversed studies did not sort to canonical order"

    # Test random permutations
    rng = random.Random(42)
    for _ in range(10):
        shuffled = list(all_studies)
        rng.shuffle(shuffled)
        assert determine_execution_order(shuffled) == all_studies


def test_determine_execution_order_mixed_subsets(orchestrator: ChiefEngineeringOrchestrator) -> None:
    """Mixed subsets of traditional and newly integrated studies must respect dependency ranks."""
    mixed_input = [
        StudyType.ETAP_GUI,            # priority 17
        StudyType.LOAD_FLOW,           # priority 1
        StudyType.GENERATIVE_DESIGN,   # priority 15
        StudyType.SHORT_CIRCUIT,       # priority 2
        StudyType.DIGITAL_TWIN,        # priority 14
        StudyType.ARC_FLASH,           # priority 7
        StudyType.ETAP_EXPERT,         # priority 16
    ]

    expected_output = [
        StudyType.LOAD_FLOW,           # 1
        StudyType.SHORT_CIRCUIT,       # 2
        StudyType.ARC_FLASH,           # 7
        StudyType.DIGITAL_TWIN,        # 14
        StudyType.GENERATIVE_DESIGN,   # 15
        StudyType.ETAP_EXPERT,         # 16
        StudyType.ETAP_GUI,            # 17
    ]

    result = determine_execution_order(mixed_input)
    assert result == expected_output, f"Expected {expected_output}, got {result}"

    # Verify orchestrator integration produces identical order
    assert orchestrator._determine_execution_order(mixed_input) == expected_output


# ==============================================================================
# Gate 7: Typed Sequence and Dictionary Input Handling
# ==============================================================================

def test_typed_sequence_and_dict_support_for_new_types() -> None:
    """Direct sequence of enums, strings, and dicts containing new study types must resolve cleanly."""
    router = GoalRouter()

    # 1. Direct enum sequence
    enum_seq = [StudyType.DIGITAL_TWIN, StudyType.GENERATIVE_DESIGN]
    dec = router.route(enum_seq)
    assert dec.study_types == enum_seq
    assert dec.confidence == 1.0

    # 2. String identifier sequence
    str_seq = ["etap_expert", "etap_gui"]
    dec = router.route(str_seq)
    assert dec.study_types == [StudyType.ETAP_EXPERT, StudyType.ETAP_GUI]
    assert dec.confidence == 1.0

    # 3. Dict specification with study_types
    dict_input = {"study_types": ["digital_twin", "generative_design", "etap_expert"]}
    dec = router.route(dict_input)
    assert dec.study_types == [
        StudyType.DIGITAL_TWIN,
        StudyType.GENERATIVE_DESIGN,
        StudyType.ETAP_EXPERT,
    ]
    assert dec.confidence == 1.0
