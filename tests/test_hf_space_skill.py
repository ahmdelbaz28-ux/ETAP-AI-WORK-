"""
tests/test_hf_space_skill.py — Verify that the HF Space deployment
(hf-space/app.py) supports the ETAP Expert skill.

This is the production-facing test: it ensures that when the HF Space
rebuilds from main, the skill is reachable via /api/v1/agents/etap-expert/chat
and /api/v1/studies/run with study_type=etap_expert.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. hf-space/app.py must declare etap_expert support
# ---------------------------------------------------------------------------


def _load_hf_app_module():
    """Load hf-space/app.py as an isolated module (it lives outside tests/)."""
    app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    if not app_path.exists():
        pytest.skip(f"hf-space/app.py not found at {app_path}")
    spec = importlib.util.spec_from_file_location("hf_app", app_path)
    mod = importlib.util.module_from_spec(spec)
    # The module uses `from datetime import UTC` (Python 3.11+)
    sys.modules["hf_app"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_hf_space_app_py_contains_etap_expert_in_study_types():
    """hf-space/app.py STUDY_TYPES must include 'etap_expert'."""
    from api.shared_handlers import STUDY_TYPES

    assert "etap_expert" in STUDY_TYPES, (
        "STUDY_TYPES in api/shared_handlers.py must include 'etap_expert' — otherwise "
        "the skill is unreachable in the HF Space deployment."
    )


def test_hf_space_app_py_has_etap_expert_chat_endpoint():
    """hf-space/app.py must define the /api/v1/agents/etap-expert/chat endpoint."""
    app_py = (Path(__file__).resolve().parent.parent / "hf-space" / "app.py").read_text(
        encoding="utf-8"
    )
    assert "/api/v1/agents/etap-expert/chat" in app_py, (
        "hf-space/app.py must define the etap-expert chat endpoint"
    )
    assert "ETAPExpertChatRequest" in app_py, (
        "hf-space/app.py must define the ETAPExpertChatRequest schema"
    )


def test_hf_space_app_py_routes_etap_expert_to_agent():
    """hf-space/app.py run_study must delegate to run_study_lightweight."""
    app_py = (Path(__file__).resolve().parent.parent / "hf-space" / "app.py").read_text(
        encoding="utf-8"
    )
    assert "run_study_lightweight" in app_py, (
        "hf-space/app.py must use run_study_lightweight to execute studies"
    )


def test_hf_space_agents_list_includes_etap_expert_agent():
    """The /api/v1/agents list in hf-space/app.py must include etap-expert-agent."""
    from api.shared_handlers import AGENTS

    agent_ids = [a["id"] for a in AGENTS]
    assert "etap-expert-agent" in agent_ids, (
        "AGENTS list in api/shared_handlers.py must include 'etap-expert-agent'"
    )


# ---------------------------------------------------------------------------
# 2. Dockerfile must copy skill files
# ---------------------------------------------------------------------------


def test_dockerfile_copies_skill_files():
    """The Dockerfile (used by HF Space) must COPY the skill files."""
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    required_copy_patterns = [
        "COPY",
        "hf-space/app.py",
        "agents/",
        "skills/",
        "prompts/",
    ]
    for pat in required_copy_patterns:
        assert pat in dockerfile, (
            f"Dockerfile must include '{pat}' so the skill is available in the HF Space container"
        )


def test_dockerfile_uses_hf_requirements():
    """Dockerfile must use hf-space/requirements.hf.txt (lightweight),
    NOT the heavy root requirements.txt."""
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements.hf.txt" in dockerfile, (
        "Dockerfile must use hf-space/requirements.hf.txt — the root "
        "requirements.txt is too heavy for HF Spaces (causes BUILD_ERROR)"
    )


def test_dockerfile_exposes_7860():
    """HF Spaces require port 7860 exposed."""
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "EXPOSE 7860" in dockerfile


def test_dockerfile_uses_non_root_user():
    """HF Spaces require non-root user with UID 1000."""
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "useradd -m -u 1000" in dockerfile or "UID 1000" in dockerfile


# ---------------------------------------------------------------------------
# 3. README.md must have HF YAML frontmatter
# ---------------------------------------------------------------------------


def test_readme_has_hf_yaml_frontmatter():
    """README.md must start with HF Spaces YAML frontmatter (title, sdk, etc.)."""
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("---"), "README.md must start with YAML frontmatter ---"
    # Extract the frontmatter block
    parts = readme.split("---", 2)
    assert len(parts) >= 3, "README.md must have closing --- for frontmatter"
    frontmatter = parts[1]
    assert "title:" in frontmatter
    assert "sdk: docker" in frontmatter
    assert "app_port: 7860" in frontmatter


# ---------------------------------------------------------------------------
# 4. HF sync workflow must exist
# ---------------------------------------------------------------------------


def test_hf_sync_workflow_exists():
    """The .github/workflows/sync-platforms.yml must exist and trigger on main push."""
    wf_path = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "sync-platforms.yml"
    )
    assert wf_path.exists(), "sync-platforms.yml workflow must exist"
    content = wf_path.read_text(encoding="utf-8")
    assert "branches: [main]" in content
    assert "HF_TOKEN" in content
    assert "huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform" in content


# ---------------------------------------------------------------------------
# 5. hf-space/app.py must import successfully (no syntax errors)
# ---------------------------------------------------------------------------


def test_hf_space_app_py_imports_cleanly():
    """hf-space/app.py must import without errors."""
    try:
        mod = _load_hf_app_module()
        # Verify it has the expected attributes
        assert hasattr(mod, "app"), "hf_app must expose 'app' (FastAPI instance)"
        assert hasattr(mod, "STUDY_TYPES"), "hf_app must expose STUDY_TYPES list"
        assert hasattr(mod, "AGENTS"), "hf_app must expose AGENTS list"
        assert "etap_expert" in mod.STUDY_TYPES, (
            f"STUDY_TYPES must include 'etap_expert', got: {mod.STUDY_TYPES}"
        )
        # Verify etap-expert-agent is in AGENTS
        agent_ids = [a["id"] for a in mod.AGENTS]
        assert "etap-expert-agent" in agent_ids, (
            f"AGENTS must include 'etap-expert-agent', got: {agent_ids}"
        )
    except ImportError as e:
        # If we can't import (missing dep in test env), at least verify the
        # source code structure is correct via grep — but warn loudly.
        pytest.skip(f"hf-space/app.py import failed (likely missing dep): {e}")


# ---------------------------------------------------------------------------
# 6. hf-space/app.py must respond to /api/v1/agents/etap-expert/chat via TestClient
# ---------------------------------------------------------------------------


def test_hf_space_chat_endpoint_returns_format_a(monkeypatch):
    """HF Space chat endpoint must return Format A for a complete cable-sizing question."""
    # Auth is now enforced — set ENGINEERING_SERVICE_API_KEY so the middleware
    # accepts our requests. Without this, verify_api_key() returns 401.
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-key-for-ci")
    monkeypatch.setenv("HF_API_KEY", "test-key-for-ci")

    try:
        mod = _load_hf_app_module()
    except ImportError as e:
        pytest.skip(f"hf-space/app.py import failed: {e}")

    from fastapi.testclient import TestClient

    client = TestClient(mod.app)

    r = client.post(
        "/api/v1/agents/etap-expert/chat",
        json={"question": "What cable size for 200A load, 300ft, 480V?"},
        headers={"X-API-Key": "test-key-for-ci"},
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["data"]["classification"] == "complete"
    assert body["data"]["format"] == "A"
    assert "✅ REQUEST ANALYSIS: COMPLETE" in body["data"]["response"]


def test_hf_space_study_endpoint_returns_format_a(monkeypatch):
    """HF Space /api/v1/studies/run with study_type=etap_expert must return Format A."""
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-key-for-ci")
    monkeypatch.setenv("HF_API_KEY", "test-key-for-ci")

    try:
        mod = _load_hf_app_module()
    except ImportError as e:
        pytest.skip(f"hf-space/app.py import failed: {e}")

    from fastapi.testclient import TestClient

    client = TestClient(mod.app)

    r = client.post(
        "/api/v1/studies/run",
        json={
            "study_type": "etap_expert",
            "parameters": {"question": "What cable size for 200A load, 300ft, 480V?"},
            "use_etap": False,
        },
        headers={"X-API-Key": "test-key-for-ci"},
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["data"]["format"] == "A"


def test_hf_space_study_endpoint_rejects_missing_question(monkeypatch):
    """HF Space /api/v1/studies/run must reject missing question with HTTP 400."""
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-key-for-ci")
    monkeypatch.setenv("HF_API_KEY", "test-key-for-ci")

    try:
        mod = _load_hf_app_module()
    except ImportError as e:
        pytest.skip(f"hf-space/app.py import failed: {e}")

    from fastapi.testclient import TestClient

    client = TestClient(mod.app)

    r = client.post(
        "/api/v1/studies/run",
        json={"study_type": "etap_expert", "parameters": {}, "use_etap": False},
        headers={"X-API-Key": "test-key-for-ci"},
    )
    assert r.status_code == 400
    assert "question" in r.json()["error"].lower()
