"""
tests/test_bandit_and_cascade.py — Unit Tests for Contextual Bandit and LLM Cascade.
"""

from __future__ import annotations

import pytest

from agents.models import StudyType
from agents.optimizers.bandit_router import ContextualBanditRouter
from integrations.model_router import ModelCascadeRouter, ModelSelection, ModelTier


def test_contextual_bandit_bootstrap_routing():
    router = ContextualBanditRouter(alpha=0.2)

    # 1. Load flow
    d1 = router.route("Run Newton Raphson load flow analysis")
    assert StudyType.LOAD_FLOW in d1.study_types

    # 2. Short circuit
    d2 = router.route("Calculate 3-phase fault currents on main bus")
    assert StudyType.SHORT_CIRCUIT in d2.study_types

    # 3. Arc flash
    d3 = router.route("Estimate arc flash boundary and incident energy")
    assert StudyType.ARC_FLASH in d3.study_types


def test_contextual_bandit_reward_learning():
    router = ContextualBanditRouter(alpha=0.3)

    novel_intent = "check CT saturation and grading selectivity"
    # Provide repeated positive reinforcement for protection coordination
    for _ in range(3):
        router.update_reward(StudyType.PROTECTION_COORDINATION, novel_intent, reward=1.0)

    decision = router.route(novel_intent)
    assert StudyType.PROTECTION_COORDINATION in decision.study_types
    assert decision.confidence > 0.6


def test_model_cascade_tier_classification():
    cascade = ModelCascadeRouter()

    # Simple prompt -> Economy
    sel_eco = cascade.select_model("What is the frequency of the grid?")
    assert sel_eco.tier == ModelTier.ECONOMY

    # High complexity calculation prompt -> Reasoning
    sel_reas = cascade.select_model(
        "Calculate IEEE 1584 incident energy calculation and verify selective coordination margin with time current curve"
    )
    assert sel_reas.tier == ModelTier.REASONING


def test_model_cascade_validation_and_escalation():
    cascade = ModelCascadeRouter()

    sel = cascade.select_model("Compute line ampacity")
    assert sel.tier == ModelTier.ECONOMY

    # Acceptance test
    accepted, escalation = cascade.evaluate_and_escalate(
        "The cable ampacity for 500 kcmil copper is 430 A per NEC Table 310.16.",
        sel,
    )
    assert accepted is True
    assert escalation is None

    # Rejection and escalation test
    rejected, escalation_model = cascade.evaluate_and_escalate(
        "as an ai, i cannot compute the ampacity",
        sel,
    )
    assert rejected is False
    assert escalation_model == "gpt-4o"

    metrics = cascade.metrics
    assert metrics["total_requests"] == 1
    assert metrics["escalated_requests"] == 1
