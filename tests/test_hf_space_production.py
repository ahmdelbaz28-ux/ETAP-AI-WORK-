"""
tests/test_hf_space_production.py — Production smoke tests against the
live HF Space deployment at https://ahmdelbaz28-ahmedetap-platform.hf.space

These tests verify the ETAP Expert skill is reachable and returns the
correct Format A/B/C/D signatures in PRODUCTION — not just locally.

Skipped automatically when:
  - HF_SPACE_PRODUCTION_TESTS != 'true' (default: skip in CI, run on demand)
  - Network unavailable

NOTE on authentication: several endpoints (/api/v1/studies/types, /api/v1/agents,
/api/v1/studies/run, /api/v1/agents/etap-expert/chat) were secured during the
security audit and now require an API key via X-API-Key header. The E2E test
runs unauthenticated from the GitHub Actions runner. When a secured endpoint
returns HTTP 401/403, individual tests treat it as "endpoint is up and enforcing
security" and skip the body assertions (rather than failing). The /health
endpoint (test #1) remains the authoritative health probe.

To run the full assertion suite locally, set HF_SPACE_API_KEY in your env
and the tests will include it in the X-API-Key header for all requests.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

PRODUCTION_URL = "https://ahmdelbaz28-ahmedetap-platform.hf.space"
SKIP_REASON = f"Set HF_SPACE_PRODUCTION_TESTS=true to run production tests against {PRODUCTION_URL}"

# Optional API key — when set, requests will include X-API-Key header so the
# full assertion suite runs against secured endpoints. When unset (as in the
# GitHub Actions E2E job), secured endpoints return 401 and tests skip.
_API_KEY = os.environ.get("HF_SPACE_API_KEY", "")


def _skip_if_not_enabled():
    if os.environ.get("HF_SPACE_PRODUCTION_TESTS") != "true":
        pytest.skip(SKIP_REASON, allow_module_level=True)


_skip_if_not_enabled()


def _auth_headers() -> dict:
    """Return request headers, including X-API-Key if HF_SPACE_API_KEY is set."""
    headers = {"Content-Type": "application/json"}
    if _API_KEY:
        headers["X-API-Key"] = _API_KEY
    return headers


def _skip_if_secured(d: dict) -> None:
    """Skip the current test when the endpoint returned 401/403 (secured).

    Secured endpoints correctly reject unauthenticated probes. When the E2E
    test runs without HF_SPACE_API_KEY, those endpoints return 401/403, which
    confirms they are up and enforcing security. The test skips rather than
    failing — the /health endpoint (test #1) is the authoritative health probe.
    """
    if d.get("_http_error") in (401, 403):
        pytest.skip(
            f"Endpoint returned HTTP {d['_http_error']} (secured — set HF_SPACE_API_KEY to run full assertions)"
        )


def _post(path: str, payload: dict, timeout: int = 30) -> dict:
    """POST JSON to the production HF Space and return parsed response."""
    url = PRODUCTION_URL + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"_error": str(e)}


def _get(path: str, timeout: int = 15) -> dict:
    url = PRODUCTION_URL + path
    req = urllib.request.Request(url, headers=_auth_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"_error": str(e)}


# ---------------------------------------------------------------------------
# 1. Health endpoints
# ---------------------------------------------------------------------------


def test_production_root_returns_200():
    """The HF Space root endpoint must be reachable."""
    try:  # NOSONAR HTTPError → pytest.fail conversion
        with urllib.request.urlopen(PRODUCTION_URL + "/", timeout=15) as resp:
            assert resp.status == 200
    except urllib.error.HTTPError as e:
        pytest.fail(f"Root returned HTTP {e.code}")


def test_production_health_endpoint():
    """The /health endpoint must return 200."""
    try:  # NOSONAR HTTPError → pytest.fail conversion
        with urllib.request.urlopen(PRODUCTION_URL + "/health", timeout=15) as resp:
            assert resp.status == 200
    except urllib.error.HTTPError as e:
        pytest.fail(f"/health returned HTTP {e.code}")


# ---------------------------------------------------------------------------
# 2. Skill registered in production
# ---------------------------------------------------------------------------


def test_production_study_types_include_etap_expert():
    """/api/v1/studies/types must include 'etap_expert' (or return 401 if secured).

    The endpoint was secured during the security audit and now requires an API
    key via X-API-Key header. The E2E test runs unauthenticated from the GitHub
    Actions runner, so HTTP 401 is an expected and acceptable result — it
    confirms the endpoint is up and enforcing security. The /health endpoint
    (test #1) remains the authoritative health probe.
    """
    d = _get("/api/v1/studies/types")
    _skip_if_secured(d)
    assert "_error" not in d, f"Request failed: {d}"
    types = d.get("study_types", [])
    assert "etap_expert" in types, f"etap_expert missing from production study types: {types}"


def test_production_agents_include_etap_expert_agent():
    """/api/v1/agents must include 'etap-expert-agent' (or return 401 if secured).

    Same secured-endpoint pattern as test_production_study_types_include_etap_expert:
    the /api/v1/agents endpoint was secured during the security audit and now
    requires an API key. HTTP 401/403 from an unauthenticated probe is an
    acceptable result.
    """
    d = _get("/api/v1/agents")
    _skip_if_secured(d)
    assert "_error" not in d, f"Request failed: {d}"
    ids = [a["id"] for a in d.get("agents", [])]
    assert "etap-expert-agent" in ids, f"etap-expert-agent missing from production agents: {ids}"


# ---------------------------------------------------------------------------
# 3. Skill returns Format A/B/C/D in production
# ---------------------------------------------------------------------------


def test_production_format_a_complete_request():
    """Format A must be returned for a complete cable-sizing question."""
    d = _post(
        "/api/v1/studies/run",
        {
            "study_type": "etap_expert",
            "parameters": {"question": "What cable size for 200A load, 300ft, 480V?"},
            "use_etap": False,
        },
    )
    _skip_if_secured(d)
    assert "_http_error" not in d, f"HTTP error: {d}"
    assert "_error" not in d, f"Request error: {d}"
    assert d.get("success") is True, f"Expected success=True, got: {d}"
    inner = d.get("data", {})
    assert inner.get("classification") == "complete"
    assert inner.get("format") == "A"
    assert inner.get("skill_loaded") is True
    resp = inner.get("response", "")
    assert resp.startswith("✅ REQUEST ANALYSIS: COMPLETE"), f"Bad signature: {resp[:80]}"
    # Skill Example 1 numerical accuracy
    assert "5.44" in resp, "Voltage drop must be 5.44V (skill Example 1)"
    assert "1.13" in resp, "%VD must be 1.13% (skill Example 1)"
    assert "3/0 AWG" in resp or "4/0 AWG" in resp


def test_production_format_b_incomplete_request():
    """Format B must be returned for an incomplete transformer-sizing question."""
    d = _post(
        "/api/v1/studies/run",
        {
            "study_type": "etap_expert",
            "parameters": {"question": "Size transformer for 500kW"},
            "use_etap": False,
        },
    )
    _skip_if_secured(d)
    inner = d.get("data", {})
    assert inner.get("format") == "B"
    assert inner.get("response", "").startswith("⚠️ REQUEST ANALYSIS: INCOMPLETE")


def test_production_format_c_wrong_request():
    """Format C must be returned for a wrong-study-type question."""
    d = _post(
        "/api/v1/studies/run",
        {
            "study_type": "etap_expert",
            "parameters": {"question": "Run Load Flow to find fault current"},
            "use_etap": False,
        },
    )
    _skip_if_secured(d)
    inner = d.get("data", {})
    assert inner.get("format") == "C"
    assert inner.get("response", "").startswith("❌ REQUEST ANALYSIS: INCORRECT APPROACH")


def test_production_format_d_adms_request():
    """Format D must be returned for an ADMS/FLISR question."""
    d = _post(
        "/api/v1/studies/run",
        {
            "study_type": "etap_expert",
            "parameters": {"question": "How does FLISR work for fault on Feeder 1?"},
            "use_etap": False,
        },
    )
    _skip_if_secured(d)
    inner = d.get("data", {})
    assert inner.get("format") == "D"
    assert inner.get("response", "").startswith("🔷 ADMS REQUEST ANALYSIS")


# ---------------------------------------------------------------------------
# 4. Chat endpoint
# ---------------------------------------------------------------------------


def test_production_chat_endpoint():
    """POST /api/v1/agents/etap-expert/chat must return Format A."""
    d = _post(
        "/api/v1/agents/etap-expert/chat",
        {"question": "What cable size for 200A load, 300ft, 480V?"},
    )
    _skip_if_secured(d)
    assert d.get("success") is True
    inner = d.get("data", {})
    assert inner.get("format") == "A"
    assert inner.get("response", "").startswith("✅ REQUEST ANALYSIS: COMPLETE")


def test_production_chat_endpoint_rejects_empty_question():
    """POST /api/v1/agents/etap-expert/chat must reject empty question."""
    d = _post(
        "/api/v1/agents/etap-expert/chat",
        {"question": ""},
    )
    _skip_if_secured(d)
    # Should be HTTP 400 or error response
    assert d.get("_http_error") == 400 or "error" in d, f"Expected 400 or error, got: {d}"


# ---------------------------------------------------------------------------
# 5. Backward compatibility — old study types still work
# ---------------------------------------------------------------------------


def test_production_old_study_types_still_listed():
    """All 13 original study types must still be listed (etap_expert is the 14th)."""
    d = _get("/api/v1/studies/types")
    _skip_if_secured(d)
    types = d.get("study_types", [])
    expected_old = [
        "load_flow",
        "short_circuit",
        "arc_flash",
        "protection_coordination",
        "motor_starting",
        "transient_stability",
        "harmonic_analysis",
        "optimal_power_flow",
        "cable_sizing",
        "earth_grid",
        "renewable_integration",
        "battery_storage",
        "scada",
    ]
    for t in expected_old:
        assert t in types, f"Old study type '{t}' missing from production"


def test_production_unknown_study_type_rejected():
    """Unknown study types must return HTTP 400."""
    d = _post(
        "/api/v1/studies/run",
        {"study_type": "nonexistent_study", "parameters": {}, "use_etap": False},
    )
    _skip_if_secured(d)
    assert d.get("_http_error") == 400 or "error" in d or "Unknown" in str(d), (
        f"Expected 400 or error for unknown study type, got: {d}"
    )
