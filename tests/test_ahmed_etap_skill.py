"""
tests/test_ahmed_etap_skill.py — Runtime verification of the
``ahmed-etap`` orchestration skill.

These tests confirm the skill is ACTUALLY ACTIVE in the runtime, not just
present as files.  Each test asserts that the four core principles
(SharedContext, TokenBudget, MathGuard, PeerReview) behave exactly as the
skill specification requires.

Run:  pytest tests/test_ahmed_etap_skill.py -v
"""

from __future__ import annotations

import asyncio
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# Ensure project root is on sys.path so `agents.*` imports work even when
# pytest is invoked from a subdirectory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.ahmed_etap_orchestrator import (  # noqa: E402
    AhmedETAPOrchestrator,
    AhmedETAPSkillAgent,
    MathGuard,
    MathGuardResult,
    OrchestrationResult,
    OrchestrationVerdict,
    PEER_REVIEW_MATRIX,
    PeerReview,
    PeerReviewResult,
    ProjectRef,
    SharedContext,
    TaskRecord,
    TokenBudget,
    canonicalize_study_type,
    load_skill_text,
)
from agents.orchestrator import (  # noqa: E402
    AgentResult,
    AgentStatus,
    BaseAgent,
    EngineeringTask,
    StudyType,
    get_orchestrator,
)


# ---------------------------------------------------------------------------
# 1. Skill files exist & are loaded
# ---------------------------------------------------------------------------


def test_skill_files_exist():
    """SKILL.md and REFERENCE.md must be present in skills/ahmed-etap/."""
    skill_dir = PROJECT_ROOT / "skills" / "ahmed-etap"
    assert (skill_dir / "SKILL.md").exists(), "SKILL.md missing"
    assert (skill_dir / "REFERENCE.md").exists(), "REFERENCE.md missing"


def test_skill_text_loads():
    """The runtime loader must return non-empty SKILL.md content."""
    text = load_skill_text()
    assert isinstance(text, str)
    assert len(text) > 200, "SKILL.md content too short"
    assert "AhmedETAP" in text or "ahmed-etap" in text.lower()


def test_skill_text_cached_on_second_call():
    """Second call to load_skill_text returns the same object (cached)."""
    a = load_skill_text()
    b = load_skill_text()
    assert a is b, "Skill loader should cache the text after first call"


# ---------------------------------------------------------------------------
# 2. Canonicalisation — aliases are normalised
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("load_flow", "load_flow"),
        ("Load_Flow", "load_flow"),
        ("LOAD_FLOW", "load_flow"),
        ("fault", "short_circuit"),  # alias
        ("coordination", "protection_coordination"),  # alias
        ("harmonic", "harmonic_analysis"),  # alias
        ("stability", "transient_stability"),  # alias
        ("opf", "optimal_power_flow"),  # alias
        ("arc_flash", "arc_flash"),
        ("", ""),
    ],
)
def test_canonicalize_study_type(raw, expected):
    assert canonicalize_study_type(raw) == expected


# ---------------------------------------------------------------------------
# 3. TokenBudget — tracking + 70 % compression threshold
# ---------------------------------------------------------------------------


def test_token_budget_defaults():
    """REFERENCE.md mandates specific defaults per workflow type."""
    assert TokenBudget.DEFAULTS["single"] == 8_000
    assert TokenBudget.DEFAULTS["multi"] == 16_000
    assert TokenBudget.DEFAULTS["etap_expert"] == 24_000


def test_token_budget_tracking():
    """Spend and remaining are tracked correctly."""
    tb = TokenBudget(max_tokens=10_000)
    assert tb.spent == 0
    assert tb.remaining == 10_000
    assert tb.fraction_spent == 0.0

    tb.record_spend(3_000)
    assert tb.spent == 3_000
    assert tb.remaining == 7_000
    assert abs(tb.fraction_spent - 0.30) < 1e-9


def test_token_budget_estimation_heuristic():
    """estimate_and_record uses chars/4 heuristic."""
    tb = TokenBudget(max_tokens=10_000)
    n = tb.estimate_and_record("a" * 400)  # 400 chars → ~100 tokens
    assert n == 100
    assert tb.spent == 100


def test_token_budget_negative_spend_ignored():
    """Negative spend is silently ignored (defensive)."""
    tb = TokenBudget(max_tokens=1000)
    tb.record_spend(-500)
    assert tb.spent == 0


def test_token_budget_does_not_overshoot_remaining():
    """remaining never goes negative."""
    tb = TokenBudget(max_tokens=1000)
    tb.record_spend(10_000)
    assert tb.remaining == 0


# ---------------------------------------------------------------------------
# 4. SharedContext — schema, lifecycle, compression
# ---------------------------------------------------------------------------


def test_shared_context_schema():
    """SharedContext must expose project, budget, tasks, standards, glossary, errors, review."""
    ctx = SharedContext(max_tokens=8000)
    assert hasattr(ctx, "project")
    assert hasattr(ctx, "budget")
    assert hasattr(ctx, "tasks")
    assert hasattr(ctx, "standards")
    assert hasattr(ctx, "glossary")
    assert hasattr(ctx, "errors")
    assert hasattr(ctx, "review")
    assert isinstance(ctx.budget, TokenBudget)
    assert isinstance(ctx.project, ProjectRef)
    assert ctx.tasks == []
    assert ctx.errors == []


def test_shared_context_default_glossary_loaded():
    """Default glossary terms from CONTEXT.md are pre-populated."""
    ctx = SharedContext()
    for term in ("study", "task", "agent", "result", "report", "workflow"):
        assert term in ctx.glossary


def test_shared_context_default_standards_loaded():
    """Default standards list is pre-populated."""
    ctx = SharedContext()
    assert "IEEE 3002.7" in ctx.standards
    assert "IEC 60909" in ctx.standards
    assert "IEEE 1584" in ctx.standards


def test_shared_context_to_dict_serialisable():
    """to_dict must produce a JSON-serialisable snapshot."""
    ctx = SharedContext(max_tokens=1000)
    ctx.budget.record_spend(200)
    snap = ctx.to_dict()
    assert isinstance(snap, dict)
    assert snap["budget"]["max_tokens"] == 1000
    assert snap["budget"]["spent"] == 200
    assert "tasks" in snap
    assert "standards" in snap
    assert "review" in snap


@pytest.mark.asyncio
async def test_shared_context_task_lifecycle():
    """add_task → mark_running → mark_completed → mark_reviewed transitions."""
    ctx = SharedContext(max_tokens=1000)
    record = await ctx.add_task(agent="LoadFlowAgent", study_type="load_flow")
    assert record.status == "pending"
    assert record.agent == "LoadFlowAgent"
    assert record.study_type == "load_flow"

    await ctx.mark_running(record)
    assert record.status == "running"
    assert record.started_at is not None

    await ctx.mark_completed(record, {"voltage": 1.02}, math_guard_passed=True)
    assert record.status == "completed"
    assert record.result == {"voltage": 1.02}
    assert record.math_guard_passed is True
    assert record.completed_at is not None

    await ctx.mark_reviewed(record, passed=True, reviewer_notes="plausible")
    assert record.peer_review_passed is True
    assert record.status == "reviewed"


@pytest.mark.asyncio
async def test_shared_context_compression_triggers_at_70_pct():
    """When spend > 70 %, compression must drop intermediate fields."""
    ctx = SharedContext(max_tokens=1000)
    record = await ctx.add_task(agent="LoadFlowAgent", study_type="load_flow")
    await ctx.mark_completed(record, {
        "voltage": 1.02,
        "simulation_steps": ["a", "b", "c"],
        "intermediate_reasoning": "because physics",
        "debug_log": ["x", "y"],
    }, math_guard_passed=True)

    # Push budget past 70 %
    ctx.budget.record_spend(750)  # 75 % spent

    triggered = await ctx.compress_if_needed()
    assert triggered is True
    assert "simulation_steps" not in record.result
    assert "intermediate_reasoning" not in record.result
    assert "debug_log" not in record.result
    assert record.result.get("_compressed") is True
    # Inputs and final results kept
    assert record.result.get("voltage") == 1.02
    assert ctx.budget.compression_count == 1


@pytest.mark.asyncio
async def test_shared_context_no_compression_below_70_pct():
    """Below 70 % spend, compression must NOT fire."""
    ctx = SharedContext(max_tokens=1000)
    record = await ctx.add_task(agent="LoadFlowAgent", study_type="load_flow")
    await ctx.mark_completed(record, {
        "voltage": 1.02,
        "simulation_steps": ["a"],
    }, math_guard_passed=True)
    ctx.budget.record_spend(500)  # 50 % spent

    triggered = await ctx.compress_if_needed()
    assert triggered is False
    assert "simulation_steps" in record.result
    assert ctx.budget.compression_count == 0


@pytest.mark.asyncio
async def test_shared_context_concurrent_writes_safe():
    """Multiple agents writing concurrently must not corrupt state."""
    ctx = SharedContext(max_tokens=10_000)

    async def add_one(i: int) -> TaskRecord:
        return await ctx.add_task(agent=f"Agent{i}", study_type="load_flow")

    records = await asyncio.gather(*[add_one(i) for i in range(20)])
    assert len(records) == 20
    assert len(ctx.tasks) == 20
    agents = {t.agent for t in ctx.tasks}
    assert len(agents) == 20


# ---------------------------------------------------------------------------
# 5. MathGuard — deterministic Python validation
# ---------------------------------------------------------------------------


def test_math_guard_passes_when_values_match():
    """A correct claim within tolerance passes."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=1.024,
        recompute=lambda: 1.024,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is True
    assert result.recomputed_value == 1.024
    assert result.units_ok is True


def test_math_guard_blocks_on_value_mismatch():
    """A claim that deviates > 0.01 % is blocked."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=1.05,        # 2.6 % off
        recompute=lambda: 1.024,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is False
    assert "value mismatch" in result.reason
    assert result.recomputed_value == 1.024


def test_math_guard_blocks_on_unit_mismatch():
    """kV ≠ V: a wrong unit blocks even if the number is right."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=115.0,
        recompute=lambda: 115.0,
        quantity_kind="voltage",
        claim_unit="V",  # should be kV
        expected_unit="kV",
    )
    assert result.passed is False
    assert "expected 'kV'" in result.reason
    assert result.units_ok is False


def test_math_guard_rejects_invalid_unit_for_kind():
    """A unit not in the allowed set for the quantity kind is blocked."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=20.0,
        recompute=lambda: 20.0,
        quantity_kind="current",
        claim_unit="kg",  # nonsense
    )
    assert result.passed is False
    assert "not valid for kind 'current'" in result.reason


def test_math_guard_blocks_on_callback_exception():
    """If the recompute callback raises, the guard blocks (never silently passes)."""
    guard = MathGuard()

    def boom() -> float:
        raise ZeroDivisionError("simulated engine failure")

    result = guard.validate(
        claim_value=1.0,
        recompute=boom,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is False
    assert "recompute callback raised" in result.reason


def test_math_guard_blocks_nan():
    """NaN claims are blocked."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=float("nan"),
        recompute=lambda: 1.0,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is False
    assert "NaN" in result.reason


def test_math_guard_blocks_infinity():
    """Infinite claims are blocked."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=float("inf"),
        recompute=lambda: 1.0,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is False
    assert "infinite" in result.reason


def test_math_guard_handles_zero_recomputed():
    """When the recomputed value is 0, use absolute tolerance (avoid div by 0)."""
    guard = MathGuard()
    result_ok = guard.validate(
        claim_value=0.0,
        recompute=lambda: 0.0,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result_ok.passed is True

    result_bad = guard.validate(
        claim_value=0.5,
        recompute=lambda: 0.0,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result_bad.passed is False


def test_math_guard_tolerance_within_0_01_pct():
    """A 0.005 % deviation is within tolerance and passes."""
    guard = MathGuard()
    result = guard.validate(
        claim_value=1.00005,
        recompute=lambda: 1.00000,
        quantity_kind="voltage",
        claim_unit="pu",
    )
    assert result.passed is True


def test_math_guard_never_calls_llm():
    """The guard is deterministic — it must not import any LLM client.

    This is a static check: importing the guard module must not pull in
    openai, anthropic, langchain, or similar.
    """
    import agents.ahmed_etap_orchestrator as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    # The module must not import any LLM SDK
    forbidden = ["import openai", "import anthropic", "from openai",
                 "from anthropic", "import langchain", "from langchain"]
    for token in forbidden:
        assert token not in src, f"MathGuard module must not contain '{token}'"


# ---------------------------------------------------------------------------
# 6. PeerReview — matrix + default sanity checks
# ---------------------------------------------------------------------------


def test_peer_review_matrix_has_entries_for_all_critical_studies():
    """Every safety-critical study type must have a peer reviewer."""
    required = {
        "load_flow", "short_circuit", "arc_flash",
        "protection_coordination", "harmonic_analysis", "optimal_power_flow",
        "motor_starting", "transient_stability", "cable_sizing",
        "earth_grid", "renewable_integration", "battery_storage",
        "scada", "digital_twin", "etap_expert",
    }
    for study in required:
        assert study in PEER_REVIEW_MATRIX, f"missing peer reviewer for {study}"


def test_peer_review_matrix_specific_pairs():
    """Spot-check the matrix from REFERENCE.md."""
    assert PEER_REVIEW_MATRIX["load_flow"] == "short_circuit"
    assert PEER_REVIEW_MATRIX["short_circuit"] == "load_flow"
    assert PEER_REVIEW_MATRIX["arc_flash"] == "protection_coordination"
    assert PEER_REVIEW_MATRIX["protection_coordination"] == "arc_flash"
    assert PEER_REVIEW_MATRIX["etap_expert"] == "validation"


def test_peer_review_reviewer_for_alias():
    """Aliases resolve to the canonical study before looking up the reviewer."""
    pr = PeerReview()
    assert pr.reviewer_for("fault") == "load_flow"  # alias → short_circuit → load_flow
    assert pr.reviewer_for("coordination") == "arc_flash"  # alias → protection_coordination → arc_flash


def test_peer_review_unknown_study_auto_approves():
    """An unknown study type has no reviewer and auto-approves with a note."""
    pr = PeerReview()
    result = pr.review("totally_unknown_study", result={"x": 1})
    assert result.passed is True
    assert result.reviewer == "none"
    assert "auto-approved" in result.notes


def test_peer_review_default_check_load_flow_implausible_voltage():
    """Default sanity check rejects a 5.0 pu voltage."""
    pr = PeerReview()
    result = pr.review(
        "load_flow",
        result={"buses": {"B1": {"voltage_magnitude_pu": 5.0}}},
    )
    assert result.passed is False
    assert "physically implausible" in result.notes


def test_peer_review_default_check_short_circuit_zero_current():
    """Default sanity check rejects a zero fault current."""
    pr = PeerReview()
    result = pr.review(
        "short_circuit",
        result={"fault_results": {"B1": {"three_phase": {"fault_current": 0}}}},
    )
    assert result.passed is False
    assert "non-positive fault current" in result.notes


def test_peer_review_default_check_arc_flash_too_high():
    """Default sanity check rejects a 200 cal/cm² incident energy."""
    pr = PeerReview()
    result = pr.review(
        "arc_flash",
        result={"incident_energy": 200.0},
    )
    assert result.passed is False
    assert "implausibly high" in result.notes


def test_peer_review_custom_reviewer_fn():
    """A caller-supplied reviewer_fn overrides the default check."""
    pr = PeerReview()

    def custom(result: dict[str, Any]) -> tuple[bool, str]:
        return (False, "custom rejection")

    result = pr.review("load_flow", result={"v": 1.0}, reviewer_fn=custom)
    assert result.passed is False
    assert result.notes == "custom rejection"


def test_peer_review_empty_result_rejected():
    """An empty result dict is rejected."""
    pr = PeerReview()
    result = pr.review("load_flow", result={})
    assert result.passed is False


# ---------------------------------------------------------------------------
# 7. AhmedETAPOrchestrator — full pipeline
# ---------------------------------------------------------------------------


def _fake_lead_factory(status: AgentStatus = AgentStatus.COMPLETED, data: dict | None = None):
    """Build a fake lead-agent callable that returns a fixed AgentResult."""
    async def fake_lead(task: EngineeringTask) -> AgentResult:
        return AgentResult(
            agent_name="FakeLead",
            study_type=StudyType.LOAD_FLOW,
            status=status,
            data=data or {"voltage": 1.024},
        )
    return fake_lead


@pytest.mark.asyncio
async def test_orchestrator_approves_when_all_checks_pass():
    """Happy path: MathGuard passes, PeerReview passes → verdict APPROVED."""
    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=lambda: 1.024,  # matches the agent's data
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    assert result.verdict == OrchestrationVerdict.APPROVED
    assert result.iterations == 1
    assert result.math_guard is not None
    assert result.math_guard.passed is True
    assert result.peer_review is not None
    assert result.peer_review.passed is True
    assert result.peer_review.reviewer == "short_circuit"
    assert "voltage" in result.response


@pytest.mark.asyncio
async def test_orchestrator_blocks_on_math_guard_mismatch():
    """MathGuard mismatch → blocked after exhausting retries."""
    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=lambda: 1.000,  # 2.4 % off from claim
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    assert result.verdict == OrchestrationVerdict.BLOCKED_MATH_GUARD
    assert result.iterations == 3  # 1 initial + 2 retries
    assert result.math_guard is not None
    assert result.math_guard.passed is False
    assert "value mismatch" in result.math_guard.reason


@pytest.mark.asyncio
async def test_orchestrator_blocks_on_peer_review_rejection():
    """PeerReview rejection → blocked after exhausting retries.

    We use a custom reviewer_fn that always rejects.
    """
    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=lambda: 1.024,
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
        reviewer_fn=lambda r: (False, "custom reviewer rejected"),
    )
    assert result.verdict == OrchestrationVerdict.BLOCKED_PEER_REVIEW
    assert result.iterations == 3
    assert result.peer_review is not None
    assert result.peer_review.passed is False


@pytest.mark.asyncio
async def test_orchestrator_recovers_after_one_failure():
    """If the first MathGuard fails but the second passes, the orchestrator recovers.

    We use a recompute_fn that returns the wrong value on the first call
    and the correct value on subsequent calls.
    """
    call_count = {"n": 0}

    def recompute() -> float:
        call_count["n"] += 1
        return 1.000 if call_count["n"] == 1 else 1.024

    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=recompute,
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    assert result.verdict == OrchestrationVerdict.APPROVED
    assert result.iterations == 2  # failed once, succeeded on retry


@pytest.mark.asyncio
async def test_orchestrator_unknown_study_type_fails_cleanly():
    """An uncanonicalisable study_type returns FAILED, not a crash."""
    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=lambda: 1.0,
        claim_value=1.0,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    assert result.verdict == OrchestrationVerdict.FAILED
    assert "cannot canonicalize" in result.response.get("error", "")


@pytest.mark.asyncio
async def test_orchestrator_handles_lead_agent_exception():
    """If the Lead Agent raises, the orchestrator returns FAILED, not a crash."""
    async def raising_lead(task: EngineeringTask) -> AgentResult:
        raise RuntimeError("engine offline")

    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TestProj"),
        parameters={},
        lead_agent_fn=raising_lead,
        recompute_fn=lambda: 1.0,
        claim_value=1.0,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    assert result.verdict == OrchestrationVerdict.FAILED
    assert "engine offline" in result.response.get("error", "")


@pytest.mark.asyncio
async def test_orchestrator_records_shared_context_snapshot():
    """The result must include a shared-context snapshot for auditability."""
    orch = AhmedETAPOrchestrator()
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="AuditProj", base_mva=200, base_kv=138),
        parameters={},
        lead_agent_fn=_fake_lead_factory(),
        recompute_fn=lambda: 1.024,
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=8000,
    )
    snap = result.shared_context_snapshot
    assert snap["project"]["name"] == "AuditProj"
    assert snap["project"]["base_mva"] == 200
    assert snap["budget"]["max_tokens"] == 8000
    assert len(snap["tasks"]) >= 1
    assert snap["tasks"][0]["study_type"] == "load_flow"
    assert snap["tasks"][0]["math_guard_passed"] is True


@pytest.mark.asyncio
async def test_orchestrator_compression_fires_under_tight_budget():
    """A tight budget triggers compression during the workflow."""
    orch = AhmedETAPOrchestrator()

    # Tiny budget (50 tokens) so any prompt-load + data record pushes us
    # past 70 % (= 35 tokens). The initial shared-context load alone is
    # ~25 tokens, and the agent's data record adds another ~22 — so by
    # the time MathGuard runs, we are well past 70 %.
    result = await orch.run_study(
        study_type="load_flow",
        project=ProjectRef(name="TightBudget"),
        parameters={},
        lead_agent_fn=_fake_lead_factory(
            data={
                "voltage": 1.024,
                "simulation_steps": ["a", "b"],
                "intermediate_reasoning": "scratch",
            },
        ),
        recompute_fn=lambda: 1.024,
        claim_value=1.024,
        claim_unit="pu",
        quantity_kind="voltage",
        budget_tokens=50,  # very small — compression must fire
    )
    assert result.verdict == OrchestrationVerdict.APPROVED
    snap = result.shared_context_snapshot
    # Budget must show compression fired at least once during the workflow
    assert snap["budget"]["compressions"] >= 1, (
        f"expected compression_count>=1, got {snap['budget']['compressions']}; "
        f"fraction_spent={snap['budget']['fraction_spent']}"
    )


# ---------------------------------------------------------------------------
# 8. AhmedETAPSkillAgent — BaseAgent wrapper
# ---------------------------------------------------------------------------


def test_skill_agent_info_reports_principles():
    """get_agent_info must list the four enforced principles."""
    agent = AhmedETAPSkillAgent()
    info = agent.get_agent_info()
    assert info["skill"] == "ahmed-etap"
    assert info["skill_path"] == "skills/ahmed-etap/SKILL.md"
    principles = info["principles_enforced"]
    for p in ("shared_context", "token_budget", "math_guard", "peer_review"):
        assert p in principles


@pytest.mark.asyncio
async def test_skill_agent_rejects_missing_study_type():
    """A skill task without 'study_type' returns FAILED with a clear error."""
    agent = AhmedETAPSkillAgent()
    task = EngineeringTask(
        task_id="t1",
        description="missing study_type",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert "'study_type' is required" in result.validation_errors[0]


@pytest.mark.asyncio
async def test_skill_agent_routes_to_load_flow_lead():
    """End-to-end: the skill agent routes a load_flow study through the pipeline."""
    # Build a minimal orchestrator with a stubbed load_flow agent so we don't
    # need the full engine.
    from agents.orchestrator import ChiefEngineeringOrchestrator

    class StubLoadFlowAgent(BaseAgent):
        prompt_handle = "load_flow_agent"

        def __init__(self):
            super().__init__("StubLoadFlowAgent")

        async def execute(self, task: EngineeringTask) -> AgentResult:
            return AgentResult(
                agent_name="StubLoadFlowAgent",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    "buses": {"B1": {"voltage_magnitude_pu": 1.024}},
                    "converged": True,
                    "iterations": 4,
                    "method": "Newton-Raphson",
                },
            )

    orch = ChiefEngineeringOrchestrator()
    orch.agents["load_flow"] = StubLoadFlowAgent()

    skill_agent = AhmedETAPSkillAgent(orchestrator=orch)
    task = EngineeringTask(
        task_id="e2e_load_flow",
        description="end-to-end load_flow via skill",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "study_type": "load_flow",
            "project": {"name": "E2E", "base_mva": 100, "base_kv": 115},
            "parameters": {},
            "claim_value": 1.024,
            "claim_unit": "pu",
            "quantity_kind": "voltage",
            "budget_tokens": 8000,
        },
    )
    result = await skill_agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.validation_status is True
    assert result.data["verdict"] == "approved"


# ---------------------------------------------------------------------------
# 9. Integration with the global orchestrator singleton
# ---------------------------------------------------------------------------


def test_skill_agent_registered_in_chief_orchestrator():
    """The ChiefEngineeringOrchestrator must register the skill agent."""
    orch = get_orchestrator()
    assert "ahmed_etap" in orch.agents, "Skill agent not registered as 'ahmed_etap'"
    assert isinstance(orch.agents["ahmed_etap"], AhmedETAPSkillAgent)


def test_skill_agent_has_prompt_handle():
    """The skill agent must expose prompt_handle='ahmed_etap_agent'."""
    agent = AhmedETAPSkillAgent()
    assert agent.prompt_handle == "ahmed_etap_agent"


def test_prompt_files_resolve():
    """The prompt loader must resolve the 'ahmed_etap_agent' handle."""
    from agents.prompt_loader import clear_prompt_cache, get_system_prompt

    clear_prompt_cache()
    prompt = get_system_prompt("ahmed_etap_agent")
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    # Skill prompt should mention the four principles
    assert "SharedContext" in prompt or "shared context" in prompt.lower()
    assert "MathGuard" in prompt or "math guard" in prompt.lower()
    assert "Peer Review" in prompt or "peer review" in prompt.lower()
    assert "Token Budget" in prompt or "token budget" in prompt.lower()


def test_prompts_lock_contains_skill_handle():
    """prompts-lock.json must have an entry for ahmed_etap_agent."""
    import json
    lock = json.loads((PROJECT_ROOT / "prompts-lock.json").read_text())
    assert "ahmed_etap_agent" in lock["prompts"]
    assert lock["prompts"]["ahmed_etap_agent"]["materialized"] == "prompts/ahmed_etap_agent.prompt.yaml"


def test_skills_lock_contains_skill():
    """skills-lock.json must have an entry for ahmed-etap."""
    import json
    lock = json.loads((PROJECT_ROOT / "skills-lock.json").read_text())
    assert "ahmed-etap" in lock["skills"]
    skill = lock["skills"]["ahmed-etap"]
    assert skill["skillPath"] == "skills/ahmed-etap/SKILL.md"
    assert skill["runtimeModule"] == "agents/ahmed_etap_orchestrator.py"
    assert skill["promptHandle"] == "ahmed_etap_agent"
    assert skill["studyType"] == "ahmed_etap_orchestration"


def test_shared_handlers_lists_new_study_type():
    """api.shared_handlers.STUDY_TYPES must include ahmed_etap_orchestration."""
    from api.shared_handlers import STUDY_TYPES
    assert "ahmed_etap_orchestration" in STUDY_TYPES


# ---------------------------------------------------------------------------
# 10. Module-level smoke test — `python -m agents.ahmed_etap_orchestrator`
# ---------------------------------------------------------------------------


def test_module_smoke_test_runs_without_error():
    """Running the module as a script must produce valid JSON output."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "agents.ahmed_etap_orchestrator", "--info"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, f"smoke test failed: {result.stderr}"
    import json
    info = json.loads(result.stdout)
    assert info["skill"] == "ahmed-etap"
    assert "shared_context" in info["principles_enforced"]
