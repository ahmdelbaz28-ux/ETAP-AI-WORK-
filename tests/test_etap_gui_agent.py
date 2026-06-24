"""
tests/test_etap_gui_agent.py — Honesty tests for the ETAP GUI Agent skill.

These tests verify the GUI Agent skill is correctly integrated:
  1. Skill knowledge base loaded
  2. Dependency detection (graceful fallback)
  3. Classification — all 4 modes (analyze/monitor/control/solve)
  4. Format A/B/C/D/U signatures
  5. Safety rules in responses
  6. Endpoint registration (chat + study)
  7. Backward compatibility (etap_expert still works)

Design principle: tests verify behavior, not implementation details.
If a test fails, the fix is in production code, not in the test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. Skill knowledge base
# ---------------------------------------------------------------------------


def test_gui_skill_file_exists():
    """skills/etap-gui-agent.md must exist."""
    p = Path(__file__).resolve().parent.parent / "skills" / "etap-gui-agent.md"
    assert p.exists(), f"GUI skill file missing: {p}"
    content = p.read_text()
    assert len(content) > 5000, "GUI skill file too small"
    assert "GUI Agent" in content or "GUI AGENT" in content


def test_gui_skill_contains_required_sections():
    """The skill md must contain the key sections from the spec."""
    p = Path(__file__).resolve().parent.parent / "skills" / "etap-gui-agent.md"
    content = p.read_text()
    required = [
        "Architecture",
        "CUA Loop",
        "Safety Rules",
        "ETAP Controller",
        "Fallback",
        "Audit Log",
    ]
    missing = [s for s in required if s not in content]
    assert not missing, f"GUI skill missing sections: {missing}"


def test_agent_reports_skill_loaded():
    """Agent.get_agent_info() must report skill_loaded=True."""
    from agents.etap_gui_agent import ETAPGUIAgent
    agent = ETAPGUIAgent()
    info = agent.get_agent_info()
    assert info["skill_loaded"] is True
    assert info["skill_chars"] > 5000
    assert info["knowledge_base"] == "skills/etap-gui-agent.md"


# ---------------------------------------------------------------------------
# 2. Dependency detection
# ---------------------------------------------------------------------------


def test_check_gui_deps_returns_tuple():
    """_check_gui_deps must return (bool, list)."""
    from agents.etap_gui_agent import _check_gui_deps
    ok, missing = _check_gui_deps()
    assert isinstance(ok, bool)
    assert isinstance(missing, list)


def test_fallback_when_deps_unavailable():
    """When GUI deps are missing, agent returns Format U (unavailable).
    This is the CRITICAL safety guarantee — the agent never crashes."""
    from agents.etap_gui_agent import ETAPGUIAgent, _check_gui_deps
    ok, missing = _check_gui_deps()
    agent = ETAPGUIAgent()
    result = agent.answer("Open ETAP and run Load Flow")
    if not ok:
        # Headless environment (CI, HF Space) — must return Format U
        assert result["classification"] == "unavailable"
        assert result["format"] == "U"
        assert "GUI AGENT UNAVAILABLE" in result["response"]
        assert result["deps_available"] is False
        assert len(result["missing_deps"]) > 0
    else:
        # Desktop environment — must return one of A/B/C/D
        assert result["classification"] in ("analyze", "monitor", "control", "solve")
        assert result["format"] in ("A", "B", "C", "D")
        assert result["deps_available"] is True


# ---------------------------------------------------------------------------
# 3. Classification — all 4 modes
# ---------------------------------------------------------------------------


def test_classify_analyze_request():
    """Analyze questions (read-only inspection) must classify as 'analyze'."""
    from agents.etap_gui_agent import classify
    assert classify("Take a screenshot of ETAP") == "analyze"
    assert classify("What is shown on the screen?") == "analyze"
    assert classify("Analyze the ETAP one-line diagram") == "analyze"


def test_classify_monitor_request():
    """Monitor questions must classify as 'monitor'."""
    from agents.etap_gui_agent import classify
    assert classify("Monitor the running Load Flow study") == "monitor"
    assert classify("Watch the SCADA screen for alarms") == "monitor"
    assert classify("Observe the study convergence status") == "monitor"


def test_classify_control_request():
    """Control questions (modify state) must classify as 'control'."""
    from agents.etap_gui_agent import classify
    assert classify("Open ETAP and run Load Flow") == "control"
    assert classify("Click the Run button") == "control"
    assert classify("Set the transformer MVA to 1500") == "control"
    assert classify("Close ETAP") == "control"


def test_classify_solve_request():
    """Solve questions (multi-step) must classify as 'solve'."""
    from agents.etap_gui_agent import classify
    assert classify("Solve the voltage drop problem") == "solve"
    assert classify("Fix the convergence issue step by step") == "solve"
    assert classify("Troubleshoot the arc flash study") == "solve"


def test_classify_solve_takes_precedence_over_control():
    """SOLVE must take precedence over CONTROL (multi-step workflows
    often contain control actions)."""
    from agents.etap_gui_agent import classify
    # "solve" + "run" (control keyword) → should be 'solve'
    assert classify("Solve by running Load Flow") == "solve"
    # "fix" + "click" → should be 'solve'
    assert classify("Fix the issue by clicking the button") == "solve"


# ---------------------------------------------------------------------------
# 4. Target app detection
# ---------------------------------------------------------------------------


def test_detect_target_app_etap():
    from agents.etap_gui_agent import detect_target_app
    assert detect_target_app("Open ETAP") == "ETAP"
    assert detect_target_app("Launch etap.exe") == "ETAP"


def test_detect_target_app_revit():
    from agents.etap_gui_agent import detect_target_app
    assert detect_target_app("Open Revit") == "Revit"


def test_detect_target_app_unknown():
    from agents.etap_gui_agent import detect_target_app
    assert detect_target_app("Open notepad") == "unknown"


# ---------------------------------------------------------------------------
# 5. Format signatures (when deps available)
# ---------------------------------------------------------------------------


@pytest.fixture
def gui_agent():
    from agents.etap_gui_agent import ETAPGUIAgent
    return ETAPGUIAgent()


def _maybe_skip_if_unavailable(agent):
    """Skip format tests if GUI deps unavailable (Format U is tested elsewhere)."""
    from agents.etap_gui_agent import _check_gui_deps
    ok, _ = _check_gui_deps()
    if not ok:
        pytest.skip("GUI deps unavailable — Format U tested in test_fallback_when_deps_unavailable")


def test_format_a_analyze_signature(gui_agent):
    """Format A must start with 👁️ GUI AGENT — ANALYZE MODE."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Take a screenshot of ETAP")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    assert result["format"] == "A"
    assert "👁️ GUI AGENT — ANALYZE MODE" in result["response"]
    assert "read-only" in result["response"].lower()


def test_format_b_monitor_signature(gui_agent):
    """Format B must start with 📊 GUI AGENT — MONITOR MODE."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Monitor the running study")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    assert result["format"] == "B"
    assert "📊 GUI AGENT — MONITOR MODE" in result["response"]


def test_format_c_control_signature(gui_agent):
    """Format C must start with 🖱️ GUI AGENT — CONTROL MODE + require confirmation."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Click the Run button in ETAP")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    assert result["format"] == "C"
    assert "🖱️ GUI AGENT — CONTROL MODE" in result["response"]
    assert "CONFIRMATION REQUIRED" in result["response"]
    assert "CONFIRM" in result["response"]


def test_format_d_solve_signature(gui_agent):
    """Format D must start with ⚡ GUI AGENT — SOLVE MODE + mention confirmation."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Solve the convergence problem step by step")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    assert result["format"] == "D"
    assert "⚡ GUI AGENT — SOLVE MODE" in result["response"]
    assert "confirmation" in result["response"].lower()


# ---------------------------------------------------------------------------
# 6. Safety rules in responses
# ---------------------------------------------------------------------------


def test_control_response_mentions_failsafe(gui_agent):
    """Format C (control) must mention failsafe safety rule."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Open ETAP and run Load Flow")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    if result["format"] == "C":
        assert "failsafe" in result["response"].lower() or "FAILSAFE" in result["response"]
        assert "timeout" in result["response"].lower()
        assert "audit" in result["response"].lower()


def test_solve_response_mentions_integration(gui_agent):
    """Format D (solve) must mention integration with ETAP Expert Skill."""
    _maybe_skip_if_unavailable(gui_agent)
    result = gui_agent.answer("Fix the voltage drop problem")
    if result["format"] == "U":
        pytest.skip("GUI deps unavailable")
    if result["format"] == "D":
        assert "Expert Skill" in result["response"] or "etap-expert" in result["response"].lower()


def test_unavailable_response_mentions_alternative():
    """Format U must suggest the ETAP Expert Skill as alternative."""
    from agents.etap_gui_agent import ETAPGUIAgent, _check_gui_deps
    ok, _ = _check_gui_deps()
    if ok:
        pytest.skip("GUI deps available — Format U not triggered")
    agent = ETAPGUIAgent()
    result = agent.answer("Open ETAP")
    assert result["format"] == "U"
    assert "etap_expert" in result["response"].lower()
    assert "alternative" in result["response"].lower()


# ---------------------------------------------------------------------------
# 7. Agent registration + endpoint registration
# ---------------------------------------------------------------------------


def test_agent_registered_in_orchestrator():
    """The orchestrator must register the etap_gui agent."""
    from agents.orchestrator import ChiefEngineeringOrchestrator
    orch = ChiefEngineeringOrchestrator()
    assert "etap_gui" in orch.agents, "etap_gui not registered in orchestrator"
    assert orch.agents["etap_gui"].__class__.__name__ == "ETAPGUIAgent"


def test_study_type_etap_gui_accepted():
    """StudyRequest validator must accept study_type='etap_gui'."""
    from api.studies import StudyRequest
    req = StudyRequest(study_type="etap_gui", parameters={"question": "test"})
    assert req.study_type == "etap_gui"


def test_study_type_etap_gui_dispatches_to_agent():
    """_run_native_study must route etap_gui to the GUI agent."""
    from api.studies import _run_native_study
    data = _run_native_study(
        study_type="etap_gui",
        system=None,
        parameters={"question": "Open ETAP"},
    )
    assert "classification" in data
    assert "format" in data
    assert "response" in data
    assert data["format"] in ("A", "B", "C", "D", "U")


def test_study_type_etap_gui_requires_question():
    """Dispatcher must raise if 'question' is missing."""
    from api.studies import _run_native_study
    with pytest.raises(ValueError, match="question"):
        _run_native_study(
            study_type="etap_gui",
            system=None,
            parameters={},
        )


def test_chat_endpoint_in_api_agents():
    """api/agents.py must define /etap-gui/chat endpoint."""
    p = Path(__file__).resolve().parent.parent / "api" / "agents.py"
    content = p.read_text()
    assert "/etap-gui/chat" in content
    assert "ETAPGUIChatRequest" in content
    assert "etap_gui_chat" in content


def test_chat_endpoint_in_hf_space_app():
    """hf-space/app.py must define /etap-gui/chat endpoint."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    content = p.read_text()
    assert "/etap-gui/chat" in content
    assert "ETAPGUIChatRequest" in content
    assert "etap_gui_chat" in content


def test_etap_gui_in_hf_space_study_types():
    """hf-space/app.py STUDY_TYPES must include 'etap_gui'."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    content = p.read_text()
    assert '"etap_gui"' in content


def test_etap_gui_agent_in_hf_space_agents_list():
    """hf-space/app.py AGENTS list must include 'etap-gui-agent'."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    content = p.read_text()
    assert '"etap-gui-agent"' in content


def test_prompt_yaml_exists():
    """prompts/etap_gui_agent.prompt.yaml must exist and contain key sections."""
    p = Path(__file__).resolve().parent.parent / "prompts" / "etap_gui_agent.prompt.yaml"
    assert p.exists()
    content = p.read_text()
    assert "GUI Agent" in content
    assert "CUA" in content
    assert "safety" in content.lower()
    assert "Format A" in content or "Analyze" in content


def test_prompt_registered_in_prompts_json():
    """prompts.json must include etap_gui_agent handle."""
    import json
    p = Path(__file__).resolve().parent.parent / "prompts.json"
    data = json.loads(p.read_text())
    assert "etap_gui_agent" in data["prompts"]
    assert data["prompts"]["etap_gui_agent"] == "prompts/etap_gui_agent.prompt.yaml"


# ---------------------------------------------------------------------------
# 8. Backward compatibility — etap_expert still works
# ---------------------------------------------------------------------------


def test_etap_expert_still_registered():
    """Adding etap_gui must NOT remove etap_expert."""
    from agents.orchestrator import ChiefEngineeringOrchestrator
    orch = ChiefEngineeringOrchestrator()
    assert "etap_expert" in orch.agents
    assert "etap_gui" in orch.agents


def test_etap_expert_study_type_still_accepted():
    """etap_expert study_type must still be accepted."""
    from api.studies import StudyRequest
    req = StudyRequest(study_type="etap_expert", parameters={"question": "test"})
    assert req.study_type == "etap_expert"


def test_etap_expert_chat_endpoint_still_exists():
    """etap-expert chat endpoint must still be in api/agents.py."""
    p = Path(__file__).resolve().parent.parent / "api" / "agents.py"
    content = p.read_text()
    assert "/etap-expert/chat" in content


# ---------------------------------------------------------------------------
# 9. HTTP endpoint smoke test (via TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fastapi_client():
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_gui.db")
    os.environ.setdefault("ENGINEERING_SERVICE_API_KEY", "test-key")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-32-bytes-long-aaaa-bbbb")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("USE_ETAP", "false")
    os.environ.setdefault("DEPLOYMENT_VERIFICATION", "true")

    import services.cache_service as cs
    _orig = cs.StudyCache.__init__
    def _patched(self, redis_url="memory://", ttl=3600):
        return _orig(self, redis_url="memory://", ttl=ttl)
    cs.StudyCache.__init__ = _patched

    from fastapi.testclient import TestClient

    from api.routes import app
    return TestClient(app)


def test_chat_endpoint_returns_response(fastapi_client):
    """POST /api/v1/agents/etap-gui/chat must return a valid response."""
    r = fastapi_client.post(
        "/api/v1/agents/etap-gui/chat",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={"question": "Open ETAP and run Load Flow"},
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    body = r.json()
    assert body["success"] is True
    inner = body["data"]
    assert inner["format"] in ("A", "B", "C", "D", "U")
    assert "response" in inner
    assert inner["workflow_steps_executed"] >= 1


def test_study_endpoint_returns_response(fastapi_client):
    """POST /api/v1/studies/run with study_type=etap_gui must return a valid response."""
    r = fastapi_client.post(
        "/api/v1/studies/run",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={
            "study_type": "etap_gui",
            "parameters": {"question": "Monitor the running study"},
            "use_etap": False,
        },
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["data"]["format"] in ("A", "B", "C", "D", "U")


def test_study_endpoint_rejects_missing_question(fastapi_client):
    """Missing 'question' must return HTTP 400."""
    r = fastapi_client.post(
        "/api/v1/studies/run",
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
        json={"study_type": "etap_gui", "parameters": {}, "use_etap": False},
    )
    assert r.status_code == 400
    assert "question" in r.text.lower()
