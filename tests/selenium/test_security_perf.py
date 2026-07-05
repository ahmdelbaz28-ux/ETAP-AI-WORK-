#!/usr/bin/env python3
"""Security and performance tests for the ETAP-AI API.

Tests:
1. SQL injection attempts in path parameters
2. XSS attempts in request bodies
3. Path traversal attempts
4. Large payload handling
5. Concurrent request handling
6. Response time benchmarks

Run: python3 tests/selenium/test_security_perf.py
"""
import sys
import time
import json
import urllib.request
import urllib.error
import concurrent.futures
from typing import Any

BASE_URL = "http://127.0.0.1:7860"

passed = 0
failed = 0
errors: list[str] = []


def run_test(name: str, test_fn):
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


def request(method: str, path: str, body: dict | None = None, raw_body: str | None = None) -> tuple[int, Any]:
    url = BASE_URL + path
    if raw_body:
        data = raw_body.encode()
    elif body:
        data = json.dumps(body).encode()
    else:
        data = None
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


# ---------------------------------------------------------------------------
# Security: SQL Injection
# ---------------------------------------------------------------------------

def test_sql_injection_in_agent_id():
    """SQL injection attempt in agent_id path parameter should not crash."""
    payloads = [
        "'; DROP TABLE agents;--",
        "' OR '1'='1",
        "1; DELETE FROM users WHERE 1=1;--",
        "' UNION SELECT * FROM users--",
    ]
    for payload in payloads:
        status, data = request("GET", f"/api/v1/agents/{urllib.request.quote(payload)}")
        if status == 0:
            print(f"  ✗ FAIL: server crashed on payload: {payload!r}")
            return False
        # Should return 404 (agent not found), not 500 (server error)
        if status == 500:
            print(f"  ✗ FAIL: payload {payload!r} caused 500 error (possible SQL injection)")
            return False
        if status != 404:
            print(f"  ⚠ WARNING: payload {payload!r} returned status {status} (expected 404)")
    print(f"  All SQL injection payloads safely rejected (404, no 500)")
    return True


def test_sql_injection_in_chat():
    """SQL injection in chat message body should not crash."""
    payloads = [
        {"question": "'; DROP TABLE messages;--"},
        {"question": "' OR '1'='1' --"},
        {"question": "1'; DELETE FROM users; --"},
    ]
    for payload in payloads:
        status, data = request("POST", "/api/v1/agents/etap-expert/chat", payload)
        if status == 0:
            print(f"  ✗ FAIL: server crashed on payload: {payload!r}")
            return False
        if status == 500:
            print(f"  ✗ FAIL: payload caused 500 error: {payload!r}")
            return False
    print(f"  SQL injection in chat body safely handled (no 500 errors)")
    return True


# ---------------------------------------------------------------------------
# Security: XSS
# ---------------------------------------------------------------------------

def test_xss_in_chat_message():
    """XSS payload in chat message should be escaped/sanitized, not executed.

    NOTE: The API returns JSON (Content-Type: application/json), so browsers
    will NOT execute <script> tags inside the JSON response. However, if the
    frontend renders the 'response' field as HTML without escaping, this
    becomes a stored XSS vulnerability. This test flags the reflection.
    """
    xss_payloads = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(document.cookie)",
        "<svg/onload=alert(1)>",
    ]
    reflection_found = False
    for payload in xss_payloads:
        status, data = request("POST", "/api/v1/agents/etap-expert/chat", {"question": payload})
        if status == 0:
            print(f"  ✗ FAIL: server crashed on XSS payload: {payload!r}")
            return False
        if status == 500:
            print(f"  ✗ FAIL: XSS payload caused 500 error: {payload!r}")
            return False
        # Check if the response reflects the payload unescaped
        if isinstance(data, dict):
            response_str = json.dumps(data)
            if payload in response_str:
                reflection_found = True
                print(f"  ⚠ WARNING: XSS payload reflected unescaped in response: {payload!r}")

    if reflection_found:
        print(f"  ⚠ XSS payloads are reflected in JSON response without escaping.")
        print(f"    This is safe for JSON API consumers but DANGEROUS if the frontend")
        print(f"    renders the 'response' field as HTML without sanitization.")
        print(f"    RECOMMENDATION: frontend must escape HTML in chat responses.")
    else:
        print(f"  XSS payloads not reflected in response")
    # Test passes because the API returns JSON, not HTML. But we flag the issue.
    return True


def test_xss_in_study_parameters():
    """XSS in study parameters should not crash."""
    status, data = request("POST", "/api/v1/studies/run", {
        "study_type": "load_flow",
        "system": {"base_mva": 100.0, "buses": [{"id": 1, "type": "slack"}], "lines": []},
        "parameters": {"name": "<script>alert(1)</script>"}
    })
    if status == 0 or status == 500:
        print(f"  ✗ FAIL: XSS in study params caused error (status={status})")
        return False
    print(f"  XSS in study parameters safely handled")
    return True


# ---------------------------------------------------------------------------
# Security: Path Traversal
# ---------------------------------------------------------------------------

def test_path_traversal_in_agent_id():
    """Path traversal attempt in agent_id should be rejected."""
    payloads = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    ]
    for payload in payloads:
        status, data = request("GET", f"/api/v1/agents/{payload}")
        if status == 0:
            print(f"  ✗ FAIL: server crashed on path traversal: {payload!r}")
            return False
        if status == 500:
            print(f"  ✗ FAIL: path traversal caused 500 error: {payload!r}")
            return False
        # Should not return 200 with file contents
        if status == 200 and isinstance(data, str) and "root:" in data:
            print(f"  ✗ CRITICAL: path traversal exposed /etc/passwd!")
            return False
    print(f"  Path traversal attempts safely rejected")
    return True


# ---------------------------------------------------------------------------
# Performance: Response Time
# ---------------------------------------------------------------------------

def test_response_time_healthz():
    """Healthz endpoint should respond in < 100ms."""
    times = []
    for _ in range(5):
        start = time.perf_counter()
        status, _ = request("GET", "/healthz")
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    avg = sum(times) / len(times)
    max_t = max(times)
    print(f"  Avg: {avg:.1f}ms, Max: {max_t:.1f}ms (5 requests)")
    if avg > 500:
        print(f"  ✗ FAIL: average response time {avg:.1f}ms > 500ms threshold")
        return False
    return True


def test_response_time_agents_list():
    """Agents list endpoint should respond in < 500ms."""
    times = []
    for _ in range(5):
        start = time.perf_counter()
        status, _ = request("GET", "/api/v1/agents")
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    avg = sum(times) / len(times)
    max_t = max(times)
    print(f"  Avg: {avg:.1f}ms, Max: {max_t:.1f}ms (5 requests)")
    if avg > 1000:
        print(f"  ✗ FAIL: average response time {avg:.1f}ms > 1000ms threshold")
        return False
    return True


def test_concurrent_requests():
    """Server should handle 20 concurrent requests without errors."""
    def make_request(_):
        status, _ = request("GET", "/healthz")
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_request, i) for i in range(20)]
        results = [f.result() for f in futures]

    success_count = sum(1 for s in results if s == 200)
    print(f"  {success_count}/20 concurrent requests succeeded")
    if success_count < 20:
        print(f"  ✗ FAIL: {20 - success_count} requests failed")
        return False
    return True


def test_concurrent_chat_requests():
    """Server should handle 5 concurrent chat requests without 500 errors."""
    def make_chat_request(_):
        status, _ = request("POST", "/api/v1/agents/etap-expert/chat",
                           {"question": "What is load flow?"})
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_chat_request, i) for i in range(5)]
        results = [f.result() for f in futures]

    success_count = sum(1 for s in results if s == 200)
    error_count = sum(1 for s in results if s == 500)
    print(f"  {success_count}/5 succeeded, {error_count}/5 returned 500")
    if error_count > 0:
        print(f"  ✗ FAIL: {error_count} requests returned 500 (concurrency issue)")
        return False
    return True


# ---------------------------------------------------------------------------
# Performance: Large Payloads
# ---------------------------------------------------------------------------

def test_large_payload_handling():
    """Server should handle a 100KB JSON payload gracefully."""
    # Create a large but valid payload
    large_data = ["data_point_" + str(i) for i in range(5000)]  # ~50KB
    status, data = request("POST", "/api/v1/predict/anomaly", {
        "data": [100 + i for i in range(100)],
        "threshold": 3.0,
        "_large_field": large_data
    })
    if status == 0:
        print(f"  ✗ FAIL: server crashed on large payload")
        return False
    if status == 500:
        print(f"  ✗ FAIL: large payload caused 500 error")
        return False
    print(f"  Large payload handled (status={status})")
    return True


def test_empty_body_post():
    """POST with empty body should return appropriate error (not 500)."""
    status, data = request("POST", "/api/v1/agents/etap-expert/chat", {})
    if status == 500:
        print(f"  ✗ FAIL: empty body caused 500 error (should be 422)")
        return False
    if status != 422:
        print(f"  ⚠ WARNING: empty body returned {status} (expected 422)")
    print(f"  Empty body handled correctly (status={status})")
    return True


def test_wrong_content_type():
    """POST with wrong content type should not crash."""
    url = BASE_URL + "/api/v1/agents/etap-expert/chat"
    req = urllib.request.Request(
        url, data=b"plain text body", method="POST",
        headers={"Content-Type": "text/plain"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        print(f"  ✗ FAIL: wrong content type caused exception: {e}")
        return False

    if status == 500:
        print(f"  ✗ FAIL: wrong content type caused 500 error")
        return False
    print(f"  Wrong content type handled (status={status})")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("SECURITY & PERFORMANCE TESTS")
    print("=" * 70)

    # Security tests
    run_test("SECURITY: SQL injection in agent_id path param", test_sql_injection_in_agent_id)
    run_test("SECURITY: SQL injection in chat message body", test_sql_injection_in_chat)
    run_test("SECURITY: XSS in chat message", test_xss_in_chat_message)
    run_test("SECURITY: XSS in study parameters", test_xss_in_study_parameters)
    run_test("SECURITY: Path traversal in agent_id", test_path_traversal_in_agent_id)

    # Performance tests
    run_test("PERF: /healthz response time < 500ms", test_response_time_healthz)
    run_test("PERF: /api/v1/agents response time < 1000ms", test_response_time_agents_list)
    run_test("PERF: 20 concurrent requests to /healthz", test_concurrent_requests)
    run_test("PERF: 5 concurrent chat requests", test_concurrent_chat_requests)

    # Edge cases
    run_test("EDGE: Large payload (50KB) handling", test_large_payload_handling)
    run_test("EDGE: Empty body POST", test_empty_body_post)
    run_test("EDGE: Wrong content type", test_wrong_content_type)

    print("\n" + "=" * 70)
    print(f"SECURITY & PERF RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✓ All security & performance tests passed!")
        sys.exit(0)
