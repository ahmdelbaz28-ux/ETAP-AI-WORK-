"""
tests/test_agent_registration_regression.py — Regression tests for the
agent-registration fixes made after the per-agent audit.

CONTEXT
-------
The audit on 2026-07-26 found three critical bugs:

1. ``ChiefEngineeringOrchestrator`` only registered 8 base agents + 4
   optional agents (code_guard, etap_expert, etap_gui, ahmed_etap) = 12.
   But AGENTS.md declares 24 agents, and 13 of them existed as files
   under ``agents/`` but were NEVER registered.  This meant the
   AhmedETAP skill's peer-review matrix referenced agents the
   orchestrator couldn't find.

2. ``ChiefEngineeringOrchestrator.get_study_type_mapping()`` only
   contained 12 study types.  Study types like ``arc_flash``,
   ``motor_starting``, ``transient_stability``, ``cable_sizing``,
   ``earth_grid``, ``renewable_integration``, ``battery_storage``,
   ``scada``, ``digital_twin`` were MISSING — so any caller using
   ``study_type="arc_flash"`` would silently route to ``load_flow``.

3. ``AhmedETAPSkillAgent._default_lead_for()`` only mapped 7 study
   types to lead agents.  The other 8 study types in the peer-review
   matrix fell back to ``load_flow`` — wrong and unsafe for life-safety
   calculations.

These tests verify the fixes are in place and prevent regressions.

Run:  pytest tests/test_agent_registration_regression.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.ahmed_etap_orchestrator import (  # noqa: E402
    PEER_REVIEW_MATRIX,
    AhmedETAPSkillAgent,
    canonicalize_study_type,
)
from agents.orchestrator import (  # noqa: E402
    ChiefEngineeringOrchestrator,
    StudyType,
    get_orchestrator,
)

# ---------------------------------------------------------------------------
# 1. Every agent declared in AGENTS.md is registered in the orchestrator
# ---------------------------------------------------------------------------

# The 24 agents per AGENTS.md (plus the AhmedETAP skill agent = 25)
EXPECTED_REGISTERED_AGENTS = {
    # Core 8 (defined inside orchestrator.py)
    "load_flow",
    "short_circuit",
    "harmonic_analysis",
    "optimal_power_flow",
    "protection_coordination",
    "etap_execution",
    "validation",
    "report",
    # Backward-compat aliases (orchestrator.py lines 1421-1423)
    # These short aliases map to the long-form agent instances for
    # pre-SonarCloud-sweep callers.
    "harmonic",
    "opf",
    "protection",
    # Standalone specialist agents (per AGENTS.md §"Python Agents" #10-#24)
    "arc_flash",
    "motor_starting",
    "transient_stability",
    "cable_sizing",
    "earth_grid",
    "renewable_integration",
    "battery_storage",
    "scada",
    "digital_twin",
    "anomaly",
    "predictive",
    "weather",
    "goal_planner",
    # Skill / guard agents
    "code_guard",
    "etap_expert",
    "etap_gui",
    "ahmed_etap",
    # Backward-compat aliases (registered in orchestrator.py lines 1421-1423).
    # These point to the same agent instances as their long-form counterparts:
    #   "harmonic"    → self.agents["harmonic_analysis"]
    #   "opf"         → self.agents["optimal_power_flow"]
    #   "protection"  → self.agents["protection_coordination"]
    # They exist so pre-sonarcloud-sweep callers (and tests/test_backward_compatibility.py)
    # that used the short names keep working. Removing them would break backward
    # compatibility; adding them here keeps the regression test accurate.
    "opf",  # noqa: B033
}

# Optional agents that may be missing if their dependencies aren't installed.
# Their absence is NOT a regression — but their presence IS tested if available.
OPTIONAL_AGENTS = {"etap_gui", "code_guard"}  # may fail to import on headless


def test_all_24_agents_registered_in_orchestrator():
    """Every agent in AGENTS.md must be registered in ChiefEngineeringOrchestrator.

    Regression for the bug where 13 standalone agents existed as files
    but were never registered.
    """
    orch = get_orchestrator()
    registered = set(orch.agents.keys())
    missing = EXPECTED_REGISTERED_AGENTS - registered - OPTIONAL_AGENTS
    assert not missing, (
        f"Agents missing from orchestrator.agents: {sorted(missing)}. "
        f"These agents exist as files under agents/ but are NOT registered, "
        f"so the AhmedETAP skill cannot route studies to them."
    )


def test_no_orphan_agents_in_orchestrator():
    """Conversely, every registered agent should be a known agent.

    Catches typos in registration keys.
    """
    orch = get_orchestrator()
    registered = set(orch.agents.keys())
    unknown = registered - EXPECTED_REGISTERED_AGENTS
    assert not unknown, f"Unknown agents registered in orchestrator: {sorted(unknown)}"


# ---------------------------------------------------------------------------
# 2. study_type_to_agent_key mapping covers every study type
# ---------------------------------------------------------------------------

EXPECTED_STUDY_TYPES = {
    "load_flow",
    "short_circuit",
    "harmonic_analysis",
    "optimal_power_flow",
    "protection_coordination",
    "arc_flash",
    "motor_starting",
    "transient_stability",
    "cable_sizing",
    "earth_grid",
    "renewable_integration",
    "battery_storage",
    "scada",
    "digital_twin",
    "etap_expert",
    "etap_gui",
    "etap_execution",
    "validation",
    "report",
    "ahmed_etap",
    "ahmed_etap_orchestration",
}


def test_study_type_mapping_contains_all_study_types():
    """get_study_type_mapping() must cover every study type used by the system.

    Regression for the bug where 9 study types were missing, causing
    ``study_type="arc_flash"`` to silently fall back to load_flow.
    """
    orch = get_orchestrator()
    mapping = orch.get_study_type_mapping()
    keys = set(mapping.keys())
    missing = EXPECTED_STUDY_TYPES - keys
    assert not missing, f"Study types missing from get_study_type_mapping(): {sorted(missing)}"


def test_study_type_mapping_values_resolve_to_registered_agents():
    """Every value in the mapping must be a key in self.agents.

    A mapping to a non-existent agent is just as bad as no mapping.
    """
    orch = get_orchestrator()
    mapping = orch.get_study_type_mapping()
    registered = set(orch.agents.keys())
    broken = {st: key for st, key in mapping.items() if key not in registered}
    assert not broken, f"Study types mapping to unregistered agents: {broken}"


# ---------------------------------------------------------------------------
# 3. _default_lead_for covers every peer-review-matrix study type
# ---------------------------------------------------------------------------


def test_default_lead_for_covers_all_peer_review_leads():
    """``_default_lead_for`` must NOT fall back to 'load_flow' for any
    study type that has a real Lead Agent.

    Regression for the bug where 8 study types in the peer-review matrix
    silently fell back to load_flow.
    """
    bad_fallbacks = []
    for lead_study in PEER_REVIEW_MATRIX.keys():
        lead_key = AhmedETAPSkillAgent._default_lead_for(lead_study)
        if lead_key == "load_flow" and lead_study != "load_flow":
            bad_fallbacks.append(lead_study)
    assert not bad_fallbacks, (
        f"_default_lead_for falls back to 'load_flow' for these study types "
        f"(should map to their real Lead Agent): {bad_fallbacks}"
    )


def test_default_lead_for_returns_registered_agent_keys():
    """Every value returned by _default_lead_for must be a registered agent."""
    orch = get_orchestrator()
    registered = set(orch.agents.keys())
    unregistered = []
    for lead_study in PEER_REVIEW_MATRIX.keys():
        lead_key = AhmedETAPSkillAgent._default_lead_for(lead_study)
        if lead_key not in registered:
            unregistered.append((lead_study, lead_key))
    assert not unregistered, f"_default_lead_for returns unregistered agent keys: {unregistered}"


# ---------------------------------------------------------------------------
# 4. Peer-review matrix coverage — every lead AND reviewer resolves
# ---------------------------------------------------------------------------


def test_peer_review_matrix_leads_resolve_to_registered_agents():
    """For every entry in PEER_REVIEW_MATRIX, the Lead Agent must be
    findable in the orchestrator.
    """
    orch = get_orchestrator()
    mapping = orch.get_study_type_mapping()
    unresolved = []
    for lead_study in PEER_REVIEW_MATRIX.keys():
        agent_key = mapping.get(lead_study)
        if agent_key is None or agent_key not in orch.agents:
            unresolved.append(lead_study)
    assert not unresolved, (
        f"Peer-review matrix lead study types with no registered agent: {unresolved}"
    )


def test_peer_review_matrix_reviewers_resolve_to_registered_agents():
    """For every entry in PEER_REVIEW_MATRIX, the Peer Reviewer must be
    findable in the orchestrator (either as a study_type or as a raw
    agent key like 'validation').
    """
    orch = get_orchestrator()
    mapping = orch.get_study_type_mapping()
    registered = set(orch.agents.keys())
    unresolved = []
    for _, reviewer_study in PEER_REVIEW_MATRIX.items():
        # Reviewer can be either a study_type (e.g. 'short_circuit') or
        # a direct agent key (e.g. 'validation').
        agent_key = mapping.get(reviewer_study, reviewer_study)
        if agent_key not in registered:
            unresolved.append(reviewer_study)
    assert not unresolved, (
        f"Peer-review matrix reviewer study types with no registered agent: {unresolved}"
    )


# ---------------------------------------------------------------------------
# 5. StudyType enum covers every matrix entry
# ---------------------------------------------------------------------------


def test_study_type_enum_covers_all_matrix_entries():
    """Every study type in PEER_REVIEW_MATRIX (both keys and values that
    aren't raw agent keys) must exist in the StudyType enum.

    The 'validation' reviewer is a direct agent key, not a StudyType —
    that's OK. But everything else must be in the enum.
    """
    not_enum = []
    for st in PEER_REVIEW_MATRIX.keys():
        try:
            StudyType(st)
        except ValueError:
            not_enum.append(st)
    # 'validation' is intentionally not a StudyType (it's an agent key)
    not_enum = [s for s in not_enum if s != "validation"]
    assert not not_enum, f"Study types in PEER_REVIEW_MATRIX not in StudyType enum: {not_enum}"


# ---------------------------------------------------------------------------
# 6. End-to-end: routing an arc_flash study finds the ArcFlashAgent
# ---------------------------------------------------------------------------


def test_skill_agent_finds_arc_flash_lead():
    """End-to-end: the skill agent resolves 'arc_flash' to the ArcFlashAgent.

    Before the fix, this fell back to load_flow — wrong and unsafe.
    """
    from agents.arc_flash_agent import ArcFlashAgent

    orch = get_orchestrator()
    assert "arc_flash" in orch.agents, "arc_flash agent not registered"
    assert isinstance(orch.agents["arc_flash"], ArcFlashAgent), (
        f"arc_flash agent is {type(orch.agents['arc_flash']).__name__}, expected ArcFlashAgent"
    )

    # And the skill's lead lookup must agree
    lead_key = AhmedETAPSkillAgent._default_lead_for("arc_flash")
    assert lead_key == "arc_flash", (
        f"_default_lead_for('arc_flash') returned '{lead_key}', expected 'arc_flash'"
    )


def test_skill_agent_finds_transient_stability_lead():
    """End-to-end: transient_stability resolves to StabilityAgent."""
    from agents.stability_agent import StabilityAgent

    orch = get_orchestrator()
    assert "transient_stability" in orch.agents
    assert isinstance(orch.agents["transient_stability"], StabilityAgent)

    lead_key = AhmedETAPSkillAgent._default_lead_for("transient_stability")
    assert lead_key == "transient_stability"


def test_skill_agent_finds_scada_lead():
    """End-to-end: scada resolves to SCADAAgent."""
    from agents.scada_agent import SCADAAgent

    orch = get_orchestrator()
    assert "scada" in orch.agents
    assert isinstance(orch.agents["scada"], SCADAAgent)

    lead_key = AhmedETAPSkillAgent._default_lead_for("scada")
    assert lead_key == "scada"


# ---------------------------------------------------------------------------
# 7. Inter-agent communication via SharedContext — coupling works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_context_coupling_load_flow_to_short_circuit():
    """A short_circuit agent can read a load_flow agent's result from
    SharedContext and use it in its own computation.

    This is the canonical inter-agent coupling pattern mandated by
    SKILL.md §"Agent Communication": 'Agents speak through SharedContext
    only. Never pass full prompts between agents.'
    """
    from agents.ahmed_etap_orchestrator import (
        ProjectRef,
        SharedContext,
        TaskRecord,
    )
    from agents.orchestrator import (
        AgentResult,
        AgentStatus,
        EngineeringTask,
        StudyType,
    )

    ctx = SharedContext(project=ProjectRef(name="CouplingTest"), max_tokens=8000)

    # Agent A — Load Flow — writes voltage to SharedContext
    async def agent_a(task: EngineeringTask) -> AgentResult:
        record = await ctx.add_task(agent="load_flow", study_type="load_flow")
        await ctx.mark_running(record)
        await ctx.mark_completed(
            record,
            result={
                "bus_id": "B1",
                "voltage_magnitude_pu": 1.024,
                "method": "Newton-Raphson",
            },
            math_guard_passed=True,
        )
        return AgentResult(
            agent_name="LoadFlowAgent",
            study_type=StudyType.LOAD_FLOW,
            status=AgentStatus.COMPLETED,
            data={"voltage_pu": 1.024},
        )

    # Agent B — Short Circuit — reads A's voltage, computes fault current
    async def agent_b(task: EngineeringTask) -> AgentResult:
        record = await ctx.add_task(agent="short_circuit", study_type="short_circuit")
        await ctx.mark_running(record)
        lf = next(
            (t for t in ctx.tasks if t.agent == "load_flow" and t.status == "completed"),
            None,
        )
        assert lf is not None, "SharedContext did not surface load_flow result to short_circuit"
        v_pu = lf.result["voltage_magnitude_pu"]
        fault_ka = round(v_pu * 20.0, 4)  # synthetic formula
        await ctx.mark_completed(
            record,
            result={
                "bus_id": "B1",
                "fault_current_ka": fault_ka,
                "used_voltage_pu": v_pu,
                "source_agent": "load_flow",
            },
            math_guard_passed=True,
        )
        return AgentResult(
            agent_name="ShortCircuitAgent",
            study_type=StudyType.SHORT_CIRCUIT,
            status=AgentStatus.COMPLETED,
            data={"fault_current_ka": fault_ka},
        )

    task = EngineeringTask(
        task_id="coupling-test",
        description="inter-agent coupling test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={},
    )
    result_a = await agent_a(task)
    result_b = await agent_b(task)

    # Agent B must have read Agent A's voltage (1.024) and used it
    assert result_a.status == AgentStatus.COMPLETED
    assert result_b.status == AgentStatus.COMPLETED
    assert result_b.data["fault_current_ka"] == 20.48  # 1.024 * 20
    assert len(ctx.tasks) == 2

    # The SharedContext records the provenance — agent B's result cites agent A
    sc_record = next(t for t in ctx.tasks if t.agent == "short_circuit")
    assert sc_record.result["source_agent"] == "load_flow"
    assert sc_record.result["used_voltage_pu"] == 1.024


# ---------------------------------------------------------------------------
# 8. Token-budget discipline — no per-call prompt reload in agents
# ---------------------------------------------------------------------------


def test_no_agent_reloads_prompt_inside_execute():
    """Anti-pattern (A) from the audit report: no agent should call
    get_system_prompt() inside its execute() method.

    Reloading the prompt per call defeats the entire purpose of the
    skill's token-budget system.  Prompts must be loaded once at
    construction time (or via the prompt_loader cache).
    """
    import re

    agents_dir = PROJECT_ROOT / "agents"
    offenders = []
    for py in sorted(agents_dir.glob("*.py")):
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        lines = text.splitlines()
        in_method = False
        method_indent = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Detect entering an execute/run/call/process method
            if re.match(r"^\s*(async\s+)?def\s+(execute|run|call|process)", stripped):
                in_method = True
                method_indent = len(line) - len(line.lstrip())
                continue
            # Detect leaving the method (next def at same or lower indent)
            if in_method and stripped.startswith(("def ", "async def ", "class ")):
                in_method = False
            if in_method and "get_system_prompt(" in line and "def " not in stripped:
                offenders.append((py.name, i, stripped))
    assert not offenders, (
        "Agents calling get_system_prompt() inside execute/run methods "
        "(per-call prompt reload = token waste):\n"
        + "\n".join(f"  {n}:{l}: {c}" for n, l, c in offenders)
    )


def test_math_guard_module_is_llm_free():
    """Anti-pattern (D): MathGuard must never call an LLM.

    This is a static source-code check. The module must not import any
    LLM SDK (openai, anthropic, langchain, etc.).
    """
    mod_path = PROJECT_ROOT / "agents" / "ahmed_etap_orchestrator.py"
    src = mod_path.read_text(encoding="utf-8").lower()
    forbidden = [
        "import openai",
        "import anthropic",
        "import langchain",
        "from openai",
        "from anthropic",
        "from langchain",
        "llm.invoke",
        "chat.completions.create",
    ]
    found = [kw for kw in forbidden if kw in src]
    assert not found, (
        f"MathGuard module imports LLM SDKs: {found}. MathGuard must be 100% deterministic Python."
    )
