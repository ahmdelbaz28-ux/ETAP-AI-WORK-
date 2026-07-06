"""
Regression tests for the v2.1.0 hardening fixes.

Each test in this file guards against a specific bug that was fixed in the
hardening pass. If any of these tests fail, it means someone reverted one of
the fixes — the build must fail until the fix is restored.

Fixes covered:
1. AGENT_COUNT must equal len(AGENTS) — no hardcoded drift
2. Security headers must be present on every response
3. HSTS must only be sent over HTTPS (not HTTP localhost dev)
4. ML capabilities must return a clear error (not cryptic ImportError)
5. RAG retrieve must return a `note` explaining why 0 chunks
6. Homepage must NOT contain the stale hardcoded "548" test count
7. SUPPORTED_STANDARDS must be the single source of truth for standards
8. AnomalyDetector._build_available_methods() must work (regression for
   the AVAILABLE_METHODS AttributeError bug)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so `import api.shared_handlers` works
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hf_app_client():
    """Load hf-space/app.py as a module and return a TestClient.

    This avoids importing the heavy api/routes.py (which needs bcrypt, structlog,
    opentelemetry, etc.) — we only test the HF Space entry point here.
    """
    from fastapi.testclient import TestClient

    app_path = REPO_ROOT / "hf-space" / "app.py"
    spec = importlib.util.spec_from_file_location("hf_app_regression_test", app_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return TestClient(mod.app)


# ---------------------------------------------------------------------------
# Fix 1: AGENT_COUNT == len(AGENTS)
# ---------------------------------------------------------------------------


class TestAgentCountConsistency:
    """AGENT_COUNT must always equal len(AGENTS). Never hardcode it."""

    def test_agent_count_equals_len_agents(self):
        from api.shared_handlers import AGENT_COUNT, AGENTS

        assert len(AGENTS) == AGENT_COUNT, (
            f"AGENT_COUNT ({AGENT_COUNT}) != len(AGENTS) ({len(AGENTS)}). "
            "Do not hardcode AGENT_COUNT — it is derived from len(AGENTS)."
        )

    def test_agent_count_is_25(self):
        """As of v2.1.0 the AGENTS list has 25 entries. If you add or remove
        an agent, update this test accordingly — do NOT change AGENT_COUNT."""
        from api.shared_handlers import AGENT_COUNT

        assert AGENT_COUNT == 25, (
            f"Expected 25 agents, got {AGENT_COUNT}. If you intentionally "
            "added/removed an agent, update this test."
        )

    def test_health_endpoint_reports_correct_count(self, hf_app_client):
        r = hf_app_client.get("/health")
        assert r.status_code == 200
        from api.shared_handlers import AGENT_COUNT

        assert r.json()["agents"] == AGENT_COUNT

    def test_info_endpoint_reports_correct_count(self, hf_app_client):
        r = hf_app_client.get("/api/v1/info")
        assert r.status_code == 200
        from api.shared_handlers import AGENT_COUNT

        assert r.json()["agents"] == AGENT_COUNT

    def test_agents_list_endpoint_count_matches(self, hf_app_client):
        r = hf_app_client.get("/api/v1/agents")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == len(data["agents"])


# ---------------------------------------------------------------------------
# Fix 2: Security headers on every response
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """All 5 security headers must be present on every HTTP response."""

    @pytest.mark.parametrize(
        "path",
        ["/", "/healthz", "/readyz", "/health", "/api/v1/agents", "/api/v1/info"],
    )
    def test_security_headers_present(self, hf_app_client, path):
        r = hf_app_client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in r.headers

    def test_csp_allows_swagger_cdn(self, hf_app_client):
        """CSP must allow cdn.jsdelivr.net so Swagger UI loads."""
        r = hf_app_client.get("/docs")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "cdn.jsdelivr.net" in csp, "CSP must allow Swagger CDN"


# ---------------------------------------------------------------------------
# Fix 3: HSTS only over HTTPS
# ---------------------------------------------------------------------------


class TestHstsHttpsOnly:
    """HSTS must NOT be sent over HTTP (localhost dev), only over HTTPS."""

    def test_no_hsts_on_http(self, hf_app_client):
        r = hf_app_client.get("/")
        # TestClient uses http:// — HSTS must not be present
        assert "Strict-Transport-Security" not in r.headers, (
            "HSTS should not be sent over HTTP — it pollutes dev logs and "
            "can pin HSTS on localhost for a year."
        )

    def test_hsts_present_on_https_via_forwarded_proto(self, hf_app_client):
        r = hf_app_client.get("/", headers={"x-forwarded-proto": "https"})
        assert "Strict-Transport-Security" in r.headers
        assert "max-age=31536000" in r.headers["Strict-Transport-Security"]


# ---------------------------------------------------------------------------
# Fix 4: ML capabilities clear error message
# ---------------------------------------------------------------------------


class TestMlCapabilitiesErrorHandling:
    """ML endpoints must return a clear error, not a cryptic ImportError."""

    def test_ml_capabilities_returns_success_or_clear_error(self):
        from api.shared_handlers import handle_ml_capabilities

        result = handle_ml_capabilities()
        # Either it works (sklearn installed) or it fails with a clear message
        if result.get("success"):
            assert "data" in result
            assert "sklearn" in result["data"]
        else:
            # On failure, must have a deployment_note explaining why
            assert "errors" in result
            assert "deployment_note" in result, (
                "ML failure must include deployment_note explaining how to "
                "enable ML on self-hosted deployment."
            )
            # Status should be 503 (service unavailable), not 500 (server error)
            assert result.get("_status") == 503

    def test_ml_capabilities_no_cryptic_module_error(self):
        """The error must NOT be the raw 'No module named ml' string."""
        from api.shared_handlers import handle_ml_capabilities

        result = handle_ml_capabilities()
        if not result.get("success"):
            errors_str = str(result.get("errors", ""))
            # The improved handler wraps the error with context
            assert "deployment_note" in result or "ml/" in errors_str or "numpy" in errors_str, (
                f"Error message too cryptic: {errors_str[:200]}"
            )


# ---------------------------------------------------------------------------
# Fix 5: RAG retrieve note field
# ---------------------------------------------------------------------------


class TestRagRetrieveNote:
    """When RAG returns 0 chunks, it must explain WHY via a `note` field."""

    def test_note_present_when_no_chroma(self, monkeypatch):
        """When ChromaDB is not available, response must include a note."""
        from api.shared_handlers import handle_context_retrieval

        # Point to a nonexistent directory so no collection is found
        monkeypatch.setenv("CODE_CONTEXT_INDEX_DIR", "/nonexistent_dir_regression_test_xyz")
        result = handle_context_retrieval(query="anything")

        assert result["success"] is True
        assert result["count"] == 0
        assert result["chunks"] == []
        # The note field must explain why 0 chunks
        assert "note" in result, (
            "RAG retrieve must include `note` field when 0 chunks returned — "
            "otherwise callers can't tell 'no match' from 'RAG not configured'."
        )
        assert len(result["note"]) > 20, "Note must be a meaningful message"


# ---------------------------------------------------------------------------
# Fix 6: No stale "548" hardcoded in homepage
# ---------------------------------------------------------------------------


class TestHomepageNoStaleNumbers:
    """Homepage must not contain the stale hardcoded '548' test count."""

    def test_no_548_in_homepage(self, hf_app_client):
        r = hf_app_client.get("/")
        assert r.status_code == 200
        # The number 548 must not appear as a stat (it's stale — actual test
        # count is ~1681 as of v2.1.0 and changes over time)
        assert "548" not in r.text, (
            "Homepage still contains the stale '548' test count. "
            "Use len(SUPPORTED_STANDARDS) or another live metric instead."
        )

    def test_homepage_shows_standards_count(self, hf_app_client):
        r = hf_app_client.get("/")
        assert "Standards" in r.text, "Homepage must show the Standards stat card"
        from api.shared_handlers import SUPPORTED_STANDARDS

        assert f">{len(SUPPORTED_STANDARDS)}<" in r.text

    def test_homepage_shows_correct_agent_count(self, hf_app_client):
        r = hf_app_client.get("/")
        from api.shared_handlers import AGENT_COUNT

        assert f">{AGENT_COUNT}<" in r.text


# ---------------------------------------------------------------------------
# Fix 7: SUPPORTED_STANDARDS single source of truth
# ---------------------------------------------------------------------------


class TestSupportedStandardsConsistency:
    """SUPPORTED_STANDARDS must be the single source of truth everywhere."""

    def test_supported_standards_length(self):
        from api.shared_handlers import SUPPORTED_STANDARDS

        assert len(SUPPORTED_STANDARDS) == 10, (
            f"Expected 10 standards, got {len(SUPPORTED_STANDARDS)}. "
            "Update this test if you add a new standard."
        )

    def test_platform_info_uses_supported_standards(self):
        from api.shared_handlers import SUPPORTED_STANDARDS, build_platform_info

        info = build_platform_info()
        assert info["standards"] == SUPPORTED_STANDARDS, (
            "build_platform_info() must use SUPPORTED_STANDARDS, not an inline list."
        )

    def test_supported_standards_contains_expected_entries(self):
        from api.shared_handlers import SUPPORTED_STANDARDS

        expected = {"IEEE 3002.7", "IEC 60909", "IEEE 1584", "IEC 60255", "IEEE 519"}
        actual = set(SUPPORTED_STANDARDS)
        missing = expected - actual
        assert not missing, f"Missing standards: {missing}"


# ---------------------------------------------------------------------------
# Fix 8: AnomalyDetector._build_available_methods() works
# ---------------------------------------------------------------------------


class TestAnomalyDetectorMethods:
    """Regression: AnomalyDetector.AVAILABLE_METHODS was referenced but didn't
    exist. The fix uses _build_available_methods() classmethod instead."""

    def test_build_available_methods_returns_list(self):
        from ml.predictive import AnomalyDetector

        methods = AnomalyDetector._build_available_methods()
        assert isinstance(methods, list)
        # 'statistical' is always available (pure Python, no deps)
        assert "statistical" in methods, "statistical method must always be available as a fallback"

    def test_get_ml_capabilities_does_not_raise(self):
        """get_ml_capabilities() must not raise AttributeError on
        AnomalyDetector.AVAILABLE_METHODS."""
        from ml.predictive import get_ml_capabilities

        caps = get_ml_capabilities()
        assert "anomaly_detection_methods" in caps
        assert "available" in caps["anomaly_detection_methods"]
        assert isinstance(caps["anomaly_detection_methods"]["available"], list)


# ---------------------------------------------------------------------------
# Cross-cutting: Documentation files must not have stale counts
# ---------------------------------------------------------------------------


class TestDocsNoStaleCounts:
    """Markdown docs must not contain stale hardcoded agent/test counts.

    These counts drift over time, so we use the live API values instead.
    If a doc must mention a count, it should be a range (e.g. '25+ agents')
    or be auto-generated.
    """

    @pytest.mark.parametrize(
        "filename",
        [
            "README.md",
            "README.hf.md",
            "hf-space/README.md",
            "docs/index.md",
        ],
    )
    def test_no_hardcoded_548_in_docs(self, filename):
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} not found")
        content = path.read_text(encoding="utf-8")
        # "548 passing" or "548 tests" is stale — actual count is ~1681
        assert "548 passing" not in content, (
            f"{filename} contains stale '548 passing' — update to actual count"
        )
        assert "548 Tests" not in content, f"{filename} contains stale '548 Tests'"

    def test_no_wrong_hf_url_in_readme(self):
        """README files must use the correct HF Space URL."""
        correct_url = "ahmdelbaz28-ahmedetap-platform.hf.space"
        wrong_url = "ahmdelbaz28-etap-ai-platform.hf.space"

        for filename in ["README.md", "README.hf.md", "hf-space/README.md"]:
            path = REPO_ROOT / filename
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            assert wrong_url not in content, (
                f"{filename} contains wrong HF URL '{wrong_url}'. Use '{correct_url}' instead."
            )
