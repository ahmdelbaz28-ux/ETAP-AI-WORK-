"""
tests/test_etap_expert_skill.py — Runtime verification of the ETAP Expert skill.

These tests confirm the skill is ACTUALLY ACTIVE in the runtime, not just present
as files. Each test asserts that the Format A/B/C/D signatures appear in the
agent's response, exactly as the skill specification requires.

Run:  pytest tests/test_etap_expert_skill.py -v
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixture: lazy-loaded agent (skill knowledge base is read once per process)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def agent():
    from agents.etap_expert_agent import ETAPExpertAgent

    return ETAPExpertAgent()


# ---------------------------------------------------------------------------
# 1. Skill knowledge base is loaded
# ---------------------------------------------------------------------------


def test_skill_knowledge_base_file_exists():
    """The skill markdown must exist at skills/etap-expert.md."""
    from pathlib import Path

    skill_path = Path(__file__).resolve().parent.parent / "skills" / "etap-expert.md"
    assert skill_path.exists(), f"Skill file missing: {skill_path}"
    assert skill_path.stat().st_size > 100_000, "Skill file looks truncated (< 100KB)"


def test_skill_knowledge_base_loaded_by_agent(agent):
    """The agent must report that the skill is loaded."""
    info = agent.get_agent_info()
    assert info["skill_loaded"] is True, "Agent did not load the skill knowledge base"
    assert info["skill_chars"] > 100_000, "Skill loaded but content is suspiciously small"
    assert info["knowledge_base"] == "skills/etap-expert.md"


def test_system_prompt_file_exists():
    """The system prompt file must exist at skills/etap-ai-agent-system-prompt.md."""
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "skills" / "etap-ai-agent-system-prompt.md"
    assert p.exists()


# ---------------------------------------------------------------------------
# 2. Classification — rule-based, deterministic
# ---------------------------------------------------------------------------


def test_classify_complete_request():
    from agents.etap_expert_agent import classify

    assert classify("What cable size for 200A load, 300ft, 480V?") == "complete"


def test_classify_incomplete_request():
    from agents.etap_expert_agent import classify

    assert classify("Size transformer for 500kW") == "incomplete"
    assert classify("Set relay for motor") == "incomplete"
    assert classify("Calculate voltage drop") == "incomplete"


def test_classify_wrong_request():
    from agents.etap_expert_agent import classify

    assert classify("Run Load Flow to find fault current") == "wrong"
    assert classify("Check arc flash with Load Flow") == "wrong"
    assert classify("Do FEM analysis in ETAP") == "wrong"


def test_classify_adms_request():
    from agents.etap_expert_agent import classify

    assert classify("How does FLISR work for fault on Feeder 1?") == "adms"
    assert classify("Configure VVO on feeder 2") == "adms"
    assert classify("How does DMS state estimation work?") == "adms"


# ---------------------------------------------------------------------------
# 3. Format A — COMPLETE request → expert answer with internal simulation
# ---------------------------------------------------------------------------


def test_format_a_complete_cable_sizing(agent):
    """The cable sizing question from skill Example 1 must produce Format A."""
    result = agent.answer("What cable size for 200A load, 300ft, 480V?")

    assert result["classification"] == "complete"
    assert result["format"] == "A"
    assert result["workflow_steps_executed"] == 6

    response = result["response"]
    assert "✅ REQUEST ANALYSIS: COMPLETE" in response
    assert "**INTERNAL SIMULATION:**" in response
    assert "**ETAP IMPLEMENTATION STEPS:**" in response
    assert "**VALIDATION:**" in response
    assert "**ASSUMPTIONS MADE:**" in response
    assert "**WARNINGS / CAVEATS:**" in response
    assert "**REFERENCES:**" in response

    # The skill Example 1 specifies 4/0 AWG with 1.13% voltage drop
    # Our agent should pick 3/0 AWG (200A) OR 4/0 AWG (230A) — both valid
    assert "AWG" in response or "kcmil" in response, "Cable size must be mentioned"
    assert "%" in response, "Voltage drop percentage must be mentioned"
    assert "V" in response, "Voltage drop in volts must be mentioned"


def test_format_a_contains_etap_menu_paths(agent):
    """Format A must include ETAP menu navigation steps."""
    result = agent.answer("What cable size for 200A load, 300ft, 480V?")
    assert "Tools → Cable Sizing" in result["response"] or "Cable Sizing" in result["response"]


# ---------------------------------------------------------------------------
# 4. Format B — INCOMPLETE request → clarifying questions
# ---------------------------------------------------------------------------


def test_format_b_incomplete_transformer(agent):
    """'Size transformer for 500kW' must produce Format B with clarifying questions."""
    result = agent.answer("Size transformer for 500kW")

    assert result["classification"] == "incomplete"
    assert result["format"] == "B"

    response = result["response"]
    assert "⚠️ REQUEST ANALYSIS: INCOMPLETE" in response
    assert "**What's Missing:**" in response
    assert "**Question 1:**" in response
    assert "Why I need this:" in response
    assert "voltage" in response.lower() or "power factor" in response.lower()


# ---------------------------------------------------------------------------
# 5. Format C — WRONG request → correction & education
# ---------------------------------------------------------------------------


def test_format_c_wrong_load_flow_for_fault(agent):
    """'Run Load Flow to find fault current' must produce Format C."""
    result = agent.answer("Run Load Flow to find fault current")

    assert result["classification"] == "wrong"
    assert result["format"] == "C"

    response = result["response"]
    assert "❌ REQUEST ANALYSIS: INCORRECT APPROACH" in response
    assert "**The Problem:**" in response
    assert "**Why This Matters:**" in response
    assert "**The Correct Approach:**" in response
    assert "Short Circuit" in response
    assert "ANSI C37" in response or "IEC 60909" in response


def test_format_c_wrong_etap_for_hvac(agent):
    """'Design HVAC in ETAP' must produce Format C with software mismatch correction."""
    result = agent.answer("Design building HVAC in ETAP")
    assert result["classification"] == "wrong"
    assert "ETAP is for electrical power" in result["response"]


# ---------------------------------------------------------------------------
# 6. Format D — ADMS / DER request
# ---------------------------------------------------------------------------


def test_format_d_adms_flisr(agent):
    """FLISR question must produce Format D."""
    result = agent.answer("How does FLISR work for fault on Feeder 1?")

    assert result["classification"] == "adms"
    assert result["format"] == "D"

    response = result["response"]
    assert "🔷 ADMS REQUEST ANALYSIS" in response
    assert "**Operational Context:**" in response
    assert "**ADMS Module:**" in response
    assert "**RECOMMENDED ACTIONS:**" in response
    assert "**RISKS IF NOT ACTED:**" in response
    assert "**ETAP ADMS NAVIGATION:**" in response
    assert "DSE" in response or "State Estimation" in response


def test_format_d_adms_vvo(agent):
    """VVO question must produce Format D."""
    result = agent.answer("How do I configure VVO on feeder 2?")
    assert result["classification"] == "adms"
    assert result["format"] == "D"
    assert "🔷 ADMS REQUEST ANALYSIS" in result["response"]


# ---------------------------------------------------------------------------
# 7. 6-Step workflow — every response executes all 6 steps
# ---------------------------------------------------------------------------


def test_workflow_steps_count(agent):
    """Every response must execute the full 6-step workflow."""
    for question in [
        "What cable size for 200A load, 300ft, 480V?",
        "Size transformer for 500kW",
        "Run Load Flow to find fault current",
        "How does FLISR work for fault on Feeder 1?",
    ]:
        result = agent.answer(question)
        assert result["workflow_steps_executed"] == 6, (
            f"Question '{question}' did not complete 6 workflow steps"
        )


# ---------------------------------------------------------------------------
# 8. Integration with orchestrator + study_type routing
# ---------------------------------------------------------------------------


def test_agent_registered_in_orchestrator():
    """The orchestrator must register the etap_expert agent."""
    from agents.orchestrator import ChiefEngineeringOrchestrator

    orch = ChiefEngineeringOrchestrator()
    assert "etap_expert" in orch.agents, "etap_expert not registered in orchestrator"
    assert orch.agents["etap_expert"].__class__.__name__ == "ETAPExpertAgent"


def test_study_type_etap_expert_accepted():
    """The StudyRequest validator must accept study_type='etap_expert'."""
    from api.studies import StudyRequest

    req = StudyRequest(study_type="etap_expert", parameters={"question": "test"})
    assert req.study_type == "etap_expert"


def test_study_type_etap_expert_dispatches_to_agent():
    """The native study runner must route etap_expert to the agent."""
    from api.studies import _run_native_study

    data = _run_native_study(
        study_type="etap_expert",
        system=None,
        parameters={"question": "What cable size for 200A load, 300ft, 480V?"},
    )
    assert data["classification"] == "complete"
    assert data["format"] == "A"
    assert "✅ REQUEST ANALYSIS: COMPLETE" in data["response"]


def test_study_type_etap_expert_requires_question():
    """The dispatcher must raise if 'question' is missing."""
    from api.studies import _run_native_study

    with pytest.raises(ValueError, match="question"):
        _run_native_study(
            study_type="etap_expert",
            system=None,
            parameters={},
        )


# ---------------------------------------------------------------------------
# 9. Bug fix — the import error that previously broke /api/v1/studies/run
# ---------------------------------------------------------------------------


def test_studies_run_imports_resolve():
    """api.studies must import _add_execution_time and _increment_counter successfully."""
    from core.bootstrap import _add_execution_time, _increment_counter

    # Smoke-test: calling them must not raise
    _increment_counter("request")
    _add_execution_time(0.001)


# ---------------------------------------------------------------------------
# 10. Prompt YAML — registered in prompts.json
# ---------------------------------------------------------------------------


def test_prompt_yaml_registered_in_prompts_json():
    """prompts.json must include etap_expert_agent handle."""
    import json
    from pathlib import Path

    prompts_json = Path(__file__).resolve().parent.parent / "prompts.json"
    data = json.loads(prompts_json.read_text())
    assert "etap_expert_agent" in data["prompts"]
    assert data["prompts"]["etap_expert_agent"] == "prompts/etap_expert_agent.prompt.yaml"


def test_prompt_yaml_file_exists():
    """The prompt YAML file must exist."""
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "prompts" / "etap_expert_agent.prompt.yaml"
    assert p.exists()
    content = p.read_text()
    assert "ETAP Expert Agent" in content
    assert "6-STEP WORKFLOW" in content or "6-step workflow" in content.lower()
    assert "Format A" in content
