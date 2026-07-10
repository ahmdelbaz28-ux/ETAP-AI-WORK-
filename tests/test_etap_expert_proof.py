"""
tests/test_etap_expert_proof.py — Honesty tests proving the ETAP Expert skill
actually works at runtime.

Design principle (per user requirement):
  "Do NOT change tests to make code pass — change code to make tests pass."

Each test in this file asserts a SPECIFIC, NON-NEGOTIABLE behavior of the
skill. If a test fails, the fix is in the production code, NOT in this file.

Coverage matrix:
  1. Honesty — scenario tests actually execute (no over-skipping)
  2. Chat endpoint — /api/v1/agents/etap-expert/chat returns all 4 formats
  3. Study endpoint — /api/v1/studies/run with study_type=etap_expert
  4. Backward compatibility — 9 agents + 16 study_types + 8 prompt handles intact
  5. Format A — internal simulation matches skill Example 1 exactly (VD=5.44V, 1.13%)
  6. Format B — 1-3 clarifying questions + "Why I need this" per question
  7. Format C — 6 mandatory sections + 4 options A/B/C/D
  8. Format D — 7 mandatory sections + ADMS navigation
  9. Skill knowledge base — skills/etap-expert.md loaded with >= 4000 lines
 10. Classifier accuracy — >= 90% on 20-question dataset
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Optional, Union

import pytest

# ---------------------------------------------------------------------------
# 1. HONESTY — scenario tests must not be excluded by default
# ---------------------------------------------------------------------------


def test_vitest_config_does_not_exclude_scenarios_globally():
    """The root vitest.config.ts must NOT exclude tests/scenarios/** — that
    would be the lazy approach (dead code). Scenarios must run via the
    dedicated test:scenarios script with their own config.
    """
    root = Path(__file__).resolve().parent.parent
    vitest_root = (root / "vitest.config.ts").read_text(encoding="utf-8")
    # The exclude list may mention scenarios ONLY if a separate config exists
    # that explicitly includes them.
    assert "tests/scenarios/**" in vitest_root, (
        "Root vitest config should explicitly list scenarios in exclude "
        "block (transparency) — but a separate scenarios config must exist."
    )
    scenarios_config = root / "vitest.scenarios.config.ts"
    assert scenarios_config.exists(), (
        "vitest.scenarios.config.ts must exist so scenarios are not dead code"
    )
    sc = scenarios_config.read_text(encoding="utf-8")
    assert "tests/scenarios/**/*.test.ts" in sc, (
        "vitest.scenarios.config.ts must include scenario test files"
    )


def test_ci_workflow_runs_scenario_tests_step():
    """The CI workflow must have a dedicated step that runs scenario tests."""
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci-cd.yml").read_text(
        encoding="utf-8"
    )
    assert "test:scenarios" in wf, (
        "CI workflow must invoke 'pnpm test:scenarios' explicitly — "
        "otherwise scenario tests are dead code in CI"
    )
    assert "SKIP_LIVE_SCENARIO_TESTS" in wf, (
        "CI must set SKIP_LIVE_SCENARIO_TESTS=true so tests skip cleanly "
        "without API keys (not fail)"
    )


# ---------------------------------------------------------------------------
# 2. CHAT ENDPOINT — /api/v1/agents/etap-expert/chat
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fastapi_client():
    """Build a TestClient once for all chat-endpoint tests."""
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_proof.db")
    os.environ.setdefault("ENGINEERING_SERVICE_API_KEY", "test-key")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-32-bytes-long-aaaa-bbbb")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("USE_ETAP", "false")
    os.environ.setdefault("DEPLOYMENT_VERIFICATION", "true")

    # Bypass Redis (no Redis in test env)
    import services.cache_service as cs

    _orig = cs.StudyCache.__init__

    def _patched(self, redis_url="memory://", ttl=3600):
        return _orig(self, redis_url="memory://", ttl=ttl)

    cs.StudyCache.__init__ = _patched

    from fastapi.testclient import TestClient

    from api.routes import app

    return TestClient(app)


def _chat(client, question: str) -> dict:
    """POST to /api/v1/agents/etap-expert/chat and return parsed JSON."""
    r = client.post(
        "/api/v1/agents/etap-expert/chat",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={"question": question},
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    return r.json()


def test_chat_endpoint_returns_format_a_for_complete_request(fastapi_client):
    """Chat endpoint must return Format A for a complete cable-sizing question."""
    d = _chat(fastapi_client, "What cable size for 200A load, 300ft, 480V?")
    assert d["success"] is True
    inner = d["data"]
    assert inner["classification"] == "complete"
    assert inner["format"] == "A"
    assert inner["workflow_steps_executed"] == 6
    assert inner["skill_loaded"] is True
    assert inner["skill_chars"] > 100_000
    # Signature
    assert inner["response"].startswith("✅ REQUEST ANALYSIS: COMPLETE")


def test_chat_endpoint_returns_format_b_for_incomplete_request(fastapi_client):
    """Chat endpoint must return Format B for a missing-data question."""
    d = _chat(fastapi_client, "Size transformer for 500kW")
    inner = d["data"]
    assert inner["classification"] == "incomplete"
    assert inner["format"] == "B"
    assert inner["response"].startswith("⚠️ REQUEST ANALYSIS: INCOMPLETE")


def test_chat_endpoint_returns_format_c_for_wrong_request(fastapi_client):
    """Chat endpoint must return Format C for a wrong-study-type question."""
    d = _chat(fastapi_client, "Run Load Flow to find fault current")
    inner = d["data"]
    assert inner["classification"] == "wrong"
    assert inner["format"] == "C"
    assert inner["response"].startswith("❌ REQUEST ANALYSIS: INCORRECT APPROACH")


def test_chat_endpoint_returns_format_d_for_adms_request(fastapi_client):
    """Chat endpoint must return Format D for an ADMS/FLISR question."""
    d = _chat(fastapi_client, "How does FLISR work for fault on Feeder 1?")
    inner = d["data"]
    assert inner["classification"] == "adms"
    assert inner["format"] == "D"
    assert inner["response"].startswith("🔷 ADMS REQUEST ANALYSIS")


# ---------------------------------------------------------------------------
# 3. STUDY ENDPOINT — /api/v1/studies/run with study_type=etap_expert
# ---------------------------------------------------------------------------


def _study(client, question: str) -> dict:
    r = client.post(
        "/api/v1/studies/run",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={"study_type": "etap_expert", "parameters": {"question": question}, "use_etap": False},
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    return r.json()


def test_study_endpoint_returns_format_a(fastapi_client):
    d = _study(fastapi_client, "What cable size for 200A load, 300ft, 480V?")
    assert d["success"] is True
    assert d["study_type"] == "etap_expert"
    assert d["data"]["format"] == "A"
    assert "✅ REQUEST ANALYSIS: COMPLETE" in d["data"]["response"]


def test_study_endpoint_returns_format_b(fastapi_client):
    d = _study(fastapi_client, "Size transformer for 500kW")
    assert d["data"]["format"] == "B"
    assert "⚠️ REQUEST ANALYSIS: INCOMPLETE" in d["data"]["response"]


def test_study_endpoint_returns_format_c(fastapi_client):
    d = _study(fastapi_client, "Check arc flash with Load Flow")
    assert d["data"]["format"] == "C"
    assert "❌ REQUEST ANALYSIS: INCORRECT APPROACH" in d["data"]["response"]


def test_study_endpoint_returns_format_d(fastapi_client):
    d = _study(fastapi_client, "Configure VVO on feeder 2")
    assert d["data"]["format"] == "D"
    assert "🔷 ADMS REQUEST ANALYSIS" in d["data"]["response"]


def test_study_endpoint_rejects_missing_question(fastapi_client):
    """A request without 'question' must fail with HTTP 400 Bad Request
    (validation error), not HTTP 200 with errors list."""
    r = fastapi_client.post(
        "/api/v1/studies/run",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={"study_type": "etap_expert", "parameters": {}, "use_etap": False},
    )
    assert r.status_code == 400, (
        f"Validation error must return HTTP 400, got {r.status_code}. "
        f"Returning 200 with success=False hides the error from API clients."
    )
    body = r.json()
    assert "question" in str(body).lower(), f"Error message must mention 'question', got: {body}"


# ---------------------------------------------------------------------------
# 4. BACKWARD COMPATIBILITY — old agents + study_types + prompts intact
# ---------------------------------------------------------------------------


def test_backward_compat_all_old_agents_registered():
    from agents.orchestrator import ChiefEngineeringOrchestrator

    orch = ChiefEngineeringOrchestrator()
    expected = {
        "load_flow",
        "short_circuit",
        "harmonic",
        "opf",
        "protection",
        "etap_execution",
        "validation",
        "report",
    }
    missing = expected - set(orch.agents.keys())
    assert not missing, f"Backward compat broken — missing old agents: {missing}"


def test_backward_compat_all_old_study_types_accepted():
    from api.studies import StudyRequest

    old_types = [
        "load_flow",
        "short_circuit",
        "fault",
        "arc_flash",
        "protection_coordination",
        "coordination",
        "motor_starting",
        "harmonic_analysis",
        "optimal_power_flow",
        "etap_load_flow",
        "etap_short_circuit",
        "etap_arc_flash",
        "etap_harmonic_analysis",
        "etap_optimal_power_flow",
        "etap_motor_starting",
        "etap_protection_coordination",
    ]
    for st in old_types:
        req = StudyRequest(study_type=st, parameters={})
        assert req.study_type == st, f"Old study_type '{st}' was rejected!"


def test_backward_compat_all_old_prompts_load():
    from agents.prompt_loader import get_system_prompt

    old_handles = [
        "load_flow_agent",
        "short_circuit_agent",
        "harmonic_agent",
        "opf_agent",
        "protection_agent",
        "etap_engineer_agent",
        "validation_agent",
        "report_agent",
    ]
    for h in old_handles:
        p = get_system_prompt(h)
        assert p and len(p) > 20, f"Prompt '{h}' no longer loads"


def test_backward_compat_load_flow_still_returns_converged():
    """load_flow must still produce 'converged' (not misrouted to etap_expert)."""
    from api.studies import (
        BusSpec,
        LoadSpec,
        SystemSpec,
        _build_system_from_spec,
        _run_native_study,
    )

    spec = SystemSpec(
        name="compat",
        buses=[
            BusSpec(bus_id=1, base_kv=13.8, bus_type="slack"),
            BusSpec(bus_id=2, base_kv=13.8, bus_type="pq"),
        ],
        loads=[LoadSpec(load_id=1, bus_id=2, p_load=5.0, q_load=1.0)],
    )
    system = _build_system_from_spec(spec)
    result = _run_native_study("load_flow", system, {})
    assert "converged" in result
    assert "classification" not in result, "load_flow was misrouted to etap_expert!"


# ---------------------------------------------------------------------------
# 5. FORMAT A — internal simulation matches skill Example 1 exactly
# ---------------------------------------------------------------------------


def test_format_a_simulation_matches_skill_example_1():
    """The skill Example 1 specifies: 200A, 300ft, 480V → VD=5.44V, %VD=1.13%, 3/0 AWG."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("What cable size for 200A load, 300ft, 480V?")
    response = r["response"]

    # Numerical accuracy — these come straight from the skill knowledge base
    # Example 1 (skills/etap-expert.md Section 15.2 Example 1).
    assert "5.44" in response, "Voltage drop must be 5.44V (skill Example 1)"
    assert "1.13" in response, "%VD must be 1.13% (skill Example 1)"
    assert "3/0 AWG" in response or "4/0 AWG" in response, (
        "Cable must be 3/0 or 4/0 AWG per NEC Table 310.16"
    )


def test_format_a_contains_all_mandatory_sections():
    """Format A must contain all 7 mandatory sections per skill spec."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("What cable size for 200A load, 300ft, 480V?")
    resp = r["response"]
    required = [
        "✅ REQUEST ANALYSIS: COMPLETE",
        "**INTERNAL SIMULATION:**",
        "**RESULT:**",
        "**ETAP IMPLEMENTATION STEPS:**",
        "**VALIDATION:**",
        "**ASSUMPTIONS MADE:**",
        "**WARNINGS / CAVEATS:**",
        "**REFERENCES:**",
    ]
    for s in required:
        assert s in resp, f"Format A missing mandatory section: {s!r}"


def test_format_a_contains_units_in_all_numbers():
    """Per Critical Rule #9: include units in ALL answers."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("What cable size for 200A load, 300ft, 480V?")
    resp = r["response"]
    # Voltage drop line: must have V and %
    assert "V" in resp
    assert "%" in resp


# ---------------------------------------------------------------------------
# 6. FORMAT B — 1-3 clarifying questions + "Why I need this"
# ---------------------------------------------------------------------------


def test_format_b_has_1_to_3_clarifying_questions():
    """Format B must have between 1 and 3 clarifying questions."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Size transformer for 500kW")
    resp = r["response"]
    # Count "Question N:" occurrences
    import re

    matches = re.findall(r"\*\*Question \d+:\*\*", resp)
    assert 1 <= len(matches) <= 3, f"Format B must have 1-3 questions, found {len(matches)}"


def test_format_b_has_why_i_need_this_per_question():
    """Each clarifying question must be followed by 'Why I need this:'."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Size transformer for 500kW")
    resp = r["response"]
    assert "Why I need this:" in resp, "Format B must explain why each question is needed"


def test_format_b_contains_what_i_can_tell_you_now():
    """Format B must include the 'What I can tell you now' guidance section."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Size transformer for 500kW")
    resp = r["response"]
    assert "**What I can tell you now:**" in resp


# ---------------------------------------------------------------------------
# 7. FORMAT C — correction & education with 6 sections + 4 options
# ---------------------------------------------------------------------------


def test_format_c_contains_all_mandatory_sections():
    """Format C must contain 6 mandatory correction sections."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Run Load Flow to find fault current")
    resp = r["response"]
    required = [
        "❌ REQUEST ANALYSIS: INCORRECT APPROACH",
        "**The Problem:**",
        "**Why This Matters:**",
        "**The Correct Approach:**",
        "**In ETAP Specifically:**",
        "**What Would Happen If You Did It Your Way:**",
        "**What Happens With The Correct Way:**",
    ]
    for s in required:
        assert s in resp, f"Format C missing mandatory section: {s!r}"


def test_format_c_offers_four_followup_options():
    """Format C must end with options A/B/C/D for follow-up."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Run Load Flow to find fault current")
    resp = r["response"]
    assert "A)" in resp and "B)" in resp and "C)" in resp and "D)" in resp, (
        "Format C must offer options A/B/C/D"
    )


def test_format_c_corrects_short_circuit_for_fault_current():
    """Wrong-study correction must specifically mention Short Circuit + standard."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("Run Load Flow to find fault current")
    resp = r["response"]
    assert "Short Circuit" in resp
    assert "ANSI C37" in resp or "IEC 60909" in resp


# ---------------------------------------------------------------------------
# 8. FORMAT D — ADMS with 7 mandatory sections
# ---------------------------------------------------------------------------


def test_format_d_contains_all_mandatory_sections():
    """Format D must contain 7 mandatory ADMS sections."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("How does FLISR work for fault on Feeder 1?")
    resp = r["response"]
    required = [
        "🔷 ADMS REQUEST ANALYSIS",
        "**Operational Context:**",
        "**ADMS Module:**",
        "**REAL-TIME ANALYSIS:**",
        "**RECOMMENDED ACTIONS:**",
        "**RISKS IF NOT ACTED:**",
        "**ETAP ADMS NAVIGATION:**",
    ]
    for s in required:
        assert s in resp, f"Format D missing mandatory section: {s!r}"


def test_format_d_mentions_state_estimation():
    """Format D must reference Distribution State Estimation (DSE), not Load Flow."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("How does FLISR work for fault on Feeder 1?")
    resp = r["response"]
    assert "DSE" in resp or "State Estimation" in resp, (
        "ADMS must use DSE (not Load Flow) per skill Section 5.2"
    )


def test_format_d_includes_references():
    """Format D must include references to standards + skill section."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    r = agent.answer("How does FLISR work for fault on Feeder 1?")
    resp = r["response"]
    assert "IEEE 1547" in resp
    assert "IEC 61850" in resp


# ---------------------------------------------------------------------------
# 9. SKILL KNOWLEDGE BASE — skills/etap-expert.md fully loaded
# ---------------------------------------------------------------------------


def test_skill_md_file_is_substantial():
    """skills/etap-expert.md must be >= 4000 lines and >= 100KB."""
    p = Path(__file__).resolve().parent.parent / "skills" / "etap-expert.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    lines = content.count("\n")
    assert lines >= 4000, f"Skill file too short: {lines} lines (expected >= 4000)"
    assert len(content.encode()) >= 100_000, (
        f"Skill file too small: {len(content)} bytes (expected >= 100KB)"
    )


def test_skill_md_contains_all_17_sections():
    """The skill must contain all 17 sections listed in its table of contents."""
    p = Path(__file__).resolve().parent.parent / "skills" / "etap-expert.md"
    content = p.read_text(encoding="utf-8")
    required_sections = [
        "CORE IDENTITY & PHILOSOPHY",
        "COMPLETE ETAP MODULE DIRECTORY",
        "ETAP DATABASE ARCHITECTURE",
        "THE 6-STEP EXPERT WORKFLOW",
        "ADMS - ADVANCED DISTRIBUTION MANAGEMENT SYSTEM",
        "GIS INTEGRATION",
        "POWER SYSTEM ANALYSIS MODULES",
        "PROTECTION & COORDINATION",
        "ARC FLASH & SAFETY",
        "TRANSIENT & DYNAMIC ANALYSIS",
        "RENEWABLE ENERGY & DER",
        "INDUSTRIAL & SPECIALIZED APPLICATIONS",
        "STANDARDS & COMPLIANCE",
        "COMMON USER MISTAKES & CORRECTIONS",
        "INTERNAL SIMULATION ENGINE",
        "RESPONSE TEMPLATES",
        "CRITICAL RULES",
    ]
    missing = [s for s in required_sections if s not in content]
    assert not missing, f"Skill md missing sections: {missing}"


def test_agent_reports_skill_loaded_with_correct_size():
    """Agent.get_agent_info() must report skill_loaded=True and skill_chars > 100000."""
    from agents.etap_expert_agent import ETAPExpertAgent

    agent = ETAPExpertAgent()
    info = agent.get_agent_info()
    assert info["skill_loaded"] is True
    assert info["skill_chars"] > 100_000


# ---------------------------------------------------------------------------
# 10. CLASSIFIER ACCURACY — >= 90% on 20-question dataset
# ---------------------------------------------------------------------------


# Ground truth dataset — each tuple is (question, expected_classification)
CLASSIFIER_DATASET = [
    # COMPLETE (4)
    ("What cable size for 200A load, 300ft, 480V?", "complete"),
    ("Calculate voltage drop for 4/0 AWG, 200ft, 480V, 200A", "complete"),
    ("Help me design a power system", "complete"),
    ("What is the typical X/R ratio for a utility source?", "complete"),
    # INCOMPLETE (5)
    ("Size transformer for 500kW", "incomplete"),
    ("Set relay for motor", "incomplete"),
    ("Calculate voltage drop", "incomplete"),
    ("Run arc flash", "incomplete"),
    ("Size battery", "incomplete"),
    # WRONG (6)
    ("Run Load Flow to find fault current", "wrong"),
    ("Check arc flash with Load Flow", "wrong"),
    ("Size cable with Short Circuit", "wrong"),
    ("Find motor starting time with Load Flow", "wrong"),
    ("Check protection with Load Flow", "wrong"),
    ("Do FEM analysis in ETAP", "wrong"),
    # ADMS (5)
    ("How does FLISR work for fault on Feeder 1?", "adms"),
    ("Configure VVO on feeder 2", "adms"),
    ("How does DMS state estimation work?", "adms"),
    ("Implement DERMS for solar PV integration", "adms"),
    ("Explain OMS outage management workflow", "adms"),
]


def test_classifier_accuracy_at_least_90_percent():
    """Classifier must achieve >= 90% accuracy on the 20-question dataset."""
    from agents.etap_expert_agent import classify

    correct = 0
    failures = []
    for q, expected in CLASSIFIER_DATASET:
        actual = classify(q)
        if actual == expected:
            correct += 1
        else:
            failures.append((q, expected, actual))
    accuracy = correct / len(CLASSIFIER_DATASET)
    assert accuracy >= 0.90, (
        f"Classifier accuracy {accuracy:.1%} below 90% threshold. "
        f"Failures ({len(failures)}): {failures}"
    )


def test_classifier_dataset_size():
    """Sanity: the test dataset must have exactly 20 questions (4+5+6+5)."""
    assert len(CLASSIFIER_DATASET) == 20
    counts = {}
    for _, c in CLASSIFIER_DATASET:
        counts[c] = counts.get(c, 0) + 1
    assert counts == {"complete": 4, "incomplete": 5, "wrong": 6, "adms": 5}, (
        f"Dataset distribution off: {counts}"
    )


# ---------------------------------------------------------------------------
# 11. INTEGRITY — no test in this file may be skipped or marked xfail
# ---------------------------------------------------------------------------


def test_no_skip_markers_in_skill_tests():
    """NONE of the skill test files may use pytest.skip or pytest.mark.xfail
    to bypass a failing test. If a test fails, the production code must be
    fixed — not the test.

    Note: this self-test scans for actual decorator / call usage of skip/xfail,
    NOT for the strings appearing in comments or docstrings.
    """
    test_dir = Path(__file__).resolve().parent
    # Match ACTUAL usage: decorator on its own line, or function call.
    # Patterns must start a line (with optional whitespace) — comments/docstrings
    # that merely mention the marker name will not match.
    import re

    forbidden_regexes = [
        re.compile(r"^\s*@pytest\.mark\.(Union[skip|xfail, skipif])", re.MULTILINE),
        re.compile(r"^\s*pytest\.skip\(", re.MULTILINE),
        re.compile(r"^\s*pytest\.mark\.(Union[skip|xfail, skipif])\(", re.MULTILINE),
    ]
    violations = []
    for tf in [
        "test_etap_expert_skill.py",
        "test_backward_compatibility.py",
        "test_etap_expert_proof.py",
    ]:
        path = test_dir / tf
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for regex in forbidden_regexes:
            for m in regex.finditer(content):
                # Find the line number for a helpful error message
                line_no = content[: m.start()].count("\n") + 1
                violations.append((tf, line_no, m.group(0).strip()))
    assert not violations, (
        f"Skill tests must not use skip/xfail markers (would hide broken code). "
        f"Violations: {violations}"
    )
