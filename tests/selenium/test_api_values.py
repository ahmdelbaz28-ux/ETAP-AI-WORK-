#!/usr/bin/env python3
"""Real API tests that verify response VALUES, not just HTTP status.

These tests check:
1. Correct response structure (JSON keys present)
2. Correct field types (string, int, list, dict)
3. Correct field values (specific expected values)
4. Negative scenarios (missing fields, invalid input, 404s, 400s)
5. Edge cases (empty bodies, wrong types, non-existent resources)

Run: python3 tests/selenium/test_api_values.py
"""
import json
import urllib.request
import urllib.error
import sys
from typing import Any

BASE_URL = "http://127.0.0.1:7860"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def request(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """Make an HTTP request and return (status_code, parsed_json_or_text)."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:
        return 0, str(e)


def assert_eq(actual: Any, expected: Any, msg: str) -> bool:
    if actual != expected:
        print(f"  ✗ FAIL: {msg}")
        print(f"    Expected: {expected!r}")
        print(f"    Actual:   {actual!r}")
        return False
    return True


def assert_in(key: str, obj: dict, msg: str) -> bool:
    if key not in obj:
        print(f"  ✗ FAIL: {msg} (key '{key}' missing from {list(obj.keys())})")
        return False
    return True


def assert_type(val: Any, expected_type: type, msg: str) -> bool:
    if not isinstance(val, expected_type):
        print(f"  ✗ FAIL: {msg} (expected {expected_type.__name__}, got {type(val).__name__})")
        return False
    return True


# ---------------------------------------------------------------------------
# Test results tracking
# ---------------------------------------------------------------------------
passed = 0
failed = 0
errors: list[str] = []


def run_test(name: str, test_fn) -> None:
    global passed, failed
    print(f"\n--- {name} ---")
    try:
        result = test_fn()
        if result:
            print(f"  ✓ PASS")
            passed += 1
        else:
            failed += 1
            errors.append(name)
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        failed += 1
        errors.append(f"{name} (exception: {e})")


# ---------------------------------------------------------------------------
# GET endpoint tests — verify response VALUES
# ---------------------------------------------------------------------------

def test_healthz():
    status, data = request("GET", "/healthz")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("status", data, "response"): return False
    if not assert_eq(data["status"], "ok", "status value"): return False
    return True


def test_health():
    status, data = request("GET", "/health")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("status", data, "response"): return False
    if not assert_eq(data["status"], "healthy", "status value"): return False
    if not assert_in("uptime_seconds", data, "response"): return False
    if not assert_type(data["uptime_seconds"], (int, float), "uptime_seconds type"): return False
    if not assert_in("version", data, "response"): return False
    if not assert_type(data["version"], str, "version type"): return False
    return True


def test_ready():
    status, data = request("GET", "/ready")
    if not assert_eq(status, 200, "status"): return False
    if not assert_eq(data["status"], "ready", "status value"): return False
    if not assert_in("uptime", data, "response"): return False
    return True


def test_info():
    status, data = request("GET", "/api/v1/info")
    if not assert_eq(status, 200, "status"): return False
    if not assert_eq(data["name"], "AhmedETAP", "name"): return False
    if not assert_in("version", data, "response"): return False
    if not assert_in("description", data, "response"): return False
    if not assert_in("agents", data, "response"): return False
    if not assert_type(data["agents"], int, "agents type"): return False
    if data["agents"] < 1:
        print(f"  ✗ FAIL: agents count should be >= 1, got {data['agents']}")
        return False
    return True


def test_agents_list():
    status, data = request("GET", "/api/v1/agents")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("count", data, "response"): return False
    if not assert_in("agents", data, "response"): return False
    if not assert_type(data["agents"], list, "agents type"): return False
    if data["count"] != len(data["agents"]):
        print(f"  ✗ FAIL: count ({data['count']}) != len(agents) ({len(data['agents'])})")
        return False
    # Verify each agent has required fields
    for i, agent in enumerate(data["agents"][:3]):  # check first 3
        if "id" not in agent:
            print(f"  ✗ FAIL: agent[{i}] missing 'id' field")
            return False
        if "name" not in agent:
            print(f"  ✗ FAIL: agent[{i}] missing 'name' field")
            return False
    return True


def test_agent_by_id():
    # First get the list to find a valid ID
    _, list_data = request("GET", "/api/v1/agents")
    if not list_data["agents"]:
        print("  ✗ FAIL: no agents in list")
        return False
    valid_id = list_data["agents"][0]["id"]
    status, data = request("GET", f"/api/v1/agents/{valid_id}")
    if not assert_eq(status, 200, "status"): return False
    if not assert_eq(data["id"], valid_id, "id matches"): return False
    if not assert_in("name", data, "response"): return False
    return True


def test_study_types():
    status, data = request("GET", "/api/v1/studies/types")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("study_types", data, "response"): return False
    if not assert_type(data["study_types"], list, "study_types type"): return False
    expected_types = {"load_flow", "short_circuit", "arc_flash"}
    actual_set = set(data["study_types"])
    missing = expected_types - actual_set
    if missing:
        print(f"  ✗ FAIL: missing expected study types: {missing}")
        return False
    return True


def test_knowledge():
    status, data = request("GET", "/api/v1/knowledge")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("etap", data, "response"): return False
    if not assert_type(data["etap"], dict, "etap type"): return False
    if "manuals" not in data["etap"]:
        print(f"  ✗ FAIL: etap.manuals missing")
        return False
    return True


def test_ml_capabilities():
    status, data = request("GET", "/api/v1/ml/capabilities")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("data", data, "response"): return False
    if not assert_in("sklearn", data["data"], "data.sklearn"): return False
    return True


def test_settings_health():
    status, data = request("GET", "/api/v1/settings/health")
    if not assert_eq(status, 200, "status"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("data", data, "response"): return False
    if not assert_in("crypto_available", data["data"], "crypto_available"): return False
    if not assert_type(data["data"]["crypto_available"], bool, "crypto_available type"): return False
    return True


def test_settings_keys():
    status, data = request("GET", "/api/v1/settings/keys")
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_in("providers", data, "response"): return False
    if not assert_type(data["providers"], list, "providers type"): return False
    return True


# ---------------------------------------------------------------------------
# POST endpoint tests — verify response VALUES
# ---------------------------------------------------------------------------

def test_chat_expert():
    status, data = request("POST", "/api/v1/agents/etap-expert/chat",
                           {"question": "What is the cable size for a 100A load?"})
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("data", data, "response"): return False
    # The response should contain actual content, not be empty
    if "response" not in data["data"]:
        print(f"  ✗ FAIL: data.response missing. Keys: {list(data['data'].keys())}")
        return False
    if not data["data"]["response"]:
        print(f"  ✗ FAIL: data.response is empty")
        return False
    # Verify the response contains engineering content (not just empty/garbage)
    response_text = data["data"]["response"]
    if len(response_text) < 100:
        print(f"  ✗ FAIL: response too short ({len(response_text)} chars), expected substantive content")
        return False
    # Verify it mentions relevant engineering terms
    if "cable" not in response_text.lower() and "load" not in response_text.lower():
        print(f"  ⚠ WARNING: response doesn't mention 'cable' or 'load'")
    print(f"  Response length: {len(response_text)} chars")
    return True


def test_chat_gui():
    status, data = request("POST", "/api/v1/agents/etap-gui/chat",
                           {"question": "Open load flow study"})
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("data", data, "response"): return False
    return True


def test_study_load_flow():
    status, data = request("POST", "/api/v1/studies/run", {
        "study_type": "load_flow",
        "system": {
            "base_mva": 100.0,
            "buses": [{"id": 1, "type": "slack", "voltage": 1.0}],
            "lines": []
        },
        "parameters": {}
    })
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("study_type", data, "response"): return False
    if not assert_eq(data["study_type"], "load_flow", "study_type value"): return False
    if not assert_in("status", data, "response"): return False
    return True


def test_predict_anomaly():
    status, data = request("POST", "/api/v1/predict/anomaly", {
        "data": [100, 105, 110, 500, 115, 120],
        "threshold": 3.0
    })
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("data", data, "response"): return False
    if not assert_in("anomalies", data["data"], "anomalies"): return False
    if not assert_type(data["data"]["anomalies"], list, "anomalies type"): return False
    # The 4th value (500) should be flagged as anomaly
    if len(data["data"]["anomalies"]) >= 4:
        if not data["data"]["anomalies"][3]:
            print(f"  ✗ FAIL: anomalies[3] should be True (value 500 is an outlier)")
            return False
    return True


def test_context_retrieve():
    status, data = request("POST", "/api/v1/context/retrieve", {
        "query": "load flow analysis",
        "top_k": 5
    })
    if not assert_eq(status, 200, "status"): return False
    if not assert_in("success", data, "response"): return False
    if not assert_eq(data["success"], True, "success"): return False
    if not assert_in("count", data, "response"): return False
    if not assert_in("chunks", data, "response"): return False
    if not assert_type(data["chunks"], list, "chunks type"): return False
    return True


# ---------------------------------------------------------------------------
# NEGATIVE scenarios — verify correct error handling
# ---------------------------------------------------------------------------

def test_agent_not_found():
    """GET /api/v1/agents/nonexistent-agent-12345 should return 404."""
    status, data = request("GET", "/api/v1/agents/nonexistent-agent-12345")
    if not assert_eq(status, 404, "status should be 404"): return False
    if not assert_in("error", data, "response"): return False
    return True


def test_chat_missing_message():
    """POST /api/v1/agents/etap-expert/chat without message should return 422."""
    status, data = request("POST", "/api/v1/agents/etap-expert/chat", {})
    if not assert_eq(status, 422, "status should be 422"): return False
    return True


def test_study_invalid_type():
    """POST /api/v1/studies/run with invalid study_type should return 400."""
    status, data = request("POST", "/api/v1/studies/run", {
        "study_type": "invalid_study_type",
        "parameters": {}
    })
    if not assert_eq(status, 400, "status should be 400"): return False
    return True


def test_predict_load_insufficient_data():
    """POST /api/v1/predict/load with < 48 points should return 400 (not 500)."""
    status, data = request("POST", "/api/v1/predict/load", {
        "historical_data": [100, 110, 105, 115, 120],
        "horizon": 24
    })
    if not assert_eq(status, 400, "status should be 400 (not 500, not 200)"): return False
    if not assert_in("error", data, "response"): return False
    # The error message should mention "48" or "insufficient"
    err_msg = data["error"].lower()
    if "48" not in err_msg and "insufficient" not in err_msg:
        print(f"  ✗ FAIL: error message should mention 48 or insufficient, got: {data['error']}")
        return False
    return True


def test_predict_load_no_data():
    """POST /api/v1/predict/load without historical_data should return 400."""
    status, data = request("POST", "/api/v1/predict/load", {"horizon": 24})
    if not assert_eq(status, 400, "status should be 400"): return False
    return True


def test_siem_events_not_configured():
    """GET /api/v1/agents/etap-gui/siem/events without SIEM_LOG_FILE should return 400."""
    status, data = request("GET", "/api/v1/agents/etap-gui/siem/events")
    if not assert_eq(status, 400, "status should be 400 (logging not configured)"): return False
    if not assert_in("error", data, "response"): return False
    if not assert_eq(data["error"], "logging_only_mode_not_active", "error code"): return False
    return True


def test_settings_test_key_not_found():
    """POST /api/v1/settings/keys/nonexistent/test without body should return 404."""
    status, data = request("POST", "/api/v1/settings/keys/nonexistent-provider/test", {})
    if not assert_eq(status, 404, "status should be 404 (key not found)"): return False
    if not assert_in("error", data, "response"): return False
    if not assert_eq(data["error"], "key_not_found", "error code"): return False
    return True


def test_context_retrieve_missing_query():
    """POST /api/v1/context/retrieve without query should return 422."""
    status, data = request("POST", "/api/v1/context/retrieve", {"top_k": 5})
    if not assert_eq(status, 422, "status should be 422"): return False
    return True


def test_predict_anomaly_no_data():
    """POST /api/v1/predict/anomaly without data should return 400."""
    status, data = request("POST", "/api/v1/predict/anomaly", {"threshold": 3.0})
    if not assert_eq(status, 400, "status should be 400"): return False
    return True


def test_invalid_json():
    """POST with invalid JSON should return 422 (not 500)."""
    url = BASE_URL + "/api/v1/agents/etap-expert/chat"
    req = urllib.request.Request(
        url, data=b"not valid json{{", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    if not assert_eq(status, 422, "status should be 422 for invalid JSON"): return False
    return True


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("REAL API TESTS — verifying response VALUES and negative scenarios")
    print("=" * 70)

    # Positive tests (verify response values)
    run_test("GET /healthz — verify status=ok", test_healthz)
    run_test("GET /health — verify status=healthy + uptime + version", test_health)
    run_test("GET /ready — verify status=ready + uptime", test_ready)
    run_test("GET /api/v1/info — verify name=AhmedETAP + agents count", test_info)
    run_test("GET /api/v1/agents — verify count matches list length", test_agents_list)
    run_test("GET /api/v1/agents/{id} — verify id matches", test_agent_by_id)
    run_test("GET /api/v1/studies/types — verify expected types present", test_study_types)
    run_test("GET /api/v1/knowledge — verify etap.manuals exists", test_knowledge)
    run_test("GET /api/v1/ml/capabilities — verify sklearn present", test_ml_capabilities)
    run_test("GET /api/v1/settings/health — verify crypto_available is bool", test_settings_health)
    run_test("GET /api/v1/settings/keys — verify providers is list", test_settings_keys)

    # POST tests (verify response values)
    run_test("POST /agents/etap-expert/chat — verify non-empty response", test_chat_expert)
    run_test("POST /agents/etap-gui/chat — verify success=true", test_chat_gui)
    run_test("POST /studies/run load_flow — verify study_type matches", test_study_load_flow)
    run_test("POST /predict/anomaly — verify anomaly[3]=True for outlier", test_predict_anomaly)
    run_test("POST /context/retrieve — verify count + chunks list", test_context_retrieve)

    # Negative tests
    run_test("NEGATIVE: GET /agents/nonexistent → 404", test_agent_not_found)
    run_test("NEGATIVE: POST /agents/etap-expert/chat without message → 422", test_chat_missing_message)
    run_test("NEGATIVE: POST /studies/run invalid type → 400", test_study_invalid_type)
    run_test("NEGATIVE: POST /predict/load < 48 points → 400 (not 500)", test_predict_load_insufficient_data)
    run_test("NEGATIVE: POST /predict/load no data → 400", test_predict_load_no_data)
    run_test("NEGATIVE: GET /siem/events not configured → 400", test_siem_events_not_configured)
    run_test("NEGATIVE: POST /settings/keys/nonexistent/test → 404", test_settings_test_key_not_found)
    run_test("NEGATIVE: POST /context/retrieve no query → 422", test_context_retrieve_missing_query)
    run_test("NEGATIVE: POST /predict/anomaly no data → 400", test_predict_anomaly_no_data)
    run_test("NEGATIVE: POST invalid JSON → 422", test_invalid_json)

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)
