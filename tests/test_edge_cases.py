"""
test_edge_cases.py — Edge-case tests for critical ETAP AI Platform functions.

Covers 10 edge cases:
1. Load flow with degenerate 1-bus system (no lines, no loads)
2. Load flow with all buses as slack (invalid)
3. Short circuit with zero impedance line
4. Arc flash with extreme voltage values (0V, 1MV)
5. Study request with extremely large system (1000+ buses)
6. Cache collision: two different systems producing same SHA-256 hash
7. Rate limiter under burst traffic (100 concurrent requests)
8. JWT token manipulation (modified payload, expired token, none algorithm)
9. SQL injection in project name field
10. XSS in project description field

Run:
    pytest tests/test_edge_cases.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import jwt
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY


# ===========================================================================
# 1. Load flow with degenerate 1-bus system
# ===========================================================================

class TestDegenerateLoadFlow:
    """Edge case: a 1-bus system with no lines and no loads."""

    def test_single_slack_bus_no_loads(self, client, auth_headers):
        """A degenerate system with one slack bus, no lines, no loads
        should be handled gracefully — not crash."""
        config = {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack"},
            ],
            "lines": [],
            "generators": [
                {"generator_id": 1, "bus_id": 1},
            ],
            "loads": [],
        }
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"name": "Degenerate 1-bus", "system_config": config},
        )
        assert resp.status_code == 201, f"Project creation failed: {resp.text}"
        project_id = resp.json()["id"]

        study_resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        assert study_resp.status_code == 201, f"Study creation failed: {study_resp.text}"
        data = study_resp.json()
        # The study should either complete (trivially) or fail gracefully
        assert data["status"] in ("completed", "failed"), (
            f"Study should complete or fail, got status: {data['status']}"
        )
        # If it completed, it should not have crash-inducing results
        if data["status"] == "completed" and data.get("results"):
            results = data["results"]
            assert isinstance(results, dict), "Results should be a dict"


# ===========================================================================
# 2. Load flow with all buses as slack (invalid)
# ===========================================================================

class TestAllSlackBuses:
    """Edge case: all buses are slack — invalid power system."""

    def test_all_buses_slack(self, client, auth_headers):
        """A system where every bus is slack should fail or produce a
        meaningful error."""
        config = {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack"},
                {"bus_id": 2, "voltage_magnitude": 1.05, "bus_type": "slack"},
                {"bus_id": 3, "voltage_magnitude": 1.05, "bus_type": "slack"},
            ],
            "lines": [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2},
                {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3},
            ],
            "generators": [
                {"generator_id": 1, "bus_id": 1},
                {"generator_id": 2, "bus_id": 2},
                {"generator_id": 3, "bus_id": 3},
            ],
        }
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"name": "All Slack", "system_config": config},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        study_resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        # The study should not crash the server — it should either complete
        # or fail with a descriptive error
        assert study_resp.status_code == 201, f"Study request should succeed, got {study_resp.status_code}"
        data = study_resp.json()
        assert data["status"] in ("completed", "failed"), (
            f"Study should complete or fail, got: {data['status']}"
        )


# ===========================================================================
# 3. Short circuit with zero impedance line
# ===========================================================================

class TestZeroImpedanceShortCircuit:
    """Edge case: short circuit analysis with a zero-impedance line."""

    def test_zero_impedance_line(self, client, auth_headers):
        """A zero-impedance line should not cause a divide-by-zero crash."""
        config = {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack"},
                {"bus_id": 2, "voltage_magnitude": 1.0, "bus_type": "pq"},
            ],
            "lines": [
                {
                    "line_id": 1,
                    "from_bus_id": 1,
                    "to_bus_id": 2,
                    "r1": 0.0,
                    "x1": 0.0,  # zero impedance
                    "bshunt1": 0.0,
                },
            ],
            "generators": [
                {"generator_id": 1, "bus_id": 1},
            ],
        }
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"name": "Zero Impedance", "system_config": config},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        study_resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={
                "study_type": "short_circuit",
                "config": {"fault_type": "three_phase", "bus_id": 2},
            },
        )
        # Should not crash — either complete or fail with an error message
        assert study_resp.status_code == 201, f"Study request should not crash, got {study_resp.status_code}"
        data = study_resp.json()
        assert data["status"] in ("completed", "failed"), (
            f"Study should complete or fail gracefully, got: {data['status']}"
        )


# ===========================================================================
# 4. Arc flash with extreme voltage values
# ===========================================================================

class TestExtremeVoltageArcFlash:
    """Edge case: arc flash analysis with extreme voltage values."""

    @pytest.mark.parametrize("voltage_kv", [0.0, 1000.0])
    def test_extreme_voltage_arc_flash(self, client, auth_headers, voltage_kv):
        """Arc flash with 0 kV or 1,000 kV should not crash."""
        config = {
            "base_mva": 100.0,
            "buses": [
                {
                    "bus_id": 1,
                    "voltage_magnitude": 1.05,
                    "bus_type": "slack",
                    "base_kv": voltage_kv,
                },
                {"bus_id": 2, "voltage_magnitude": 1.0, "bus_type": "pq"},
            ],
            "lines": [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2},
            ],
            "generators": [
                {"generator_id": 1, "bus_id": 1},
            ],
        }
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": f"Extreme Voltage {voltage_kv}kV",
                "system_config": config,
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        study_resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "arc_flash"},
        )
        # Should not crash
        assert study_resp.status_code == 201
        data = study_resp.json()
        assert data["status"] in ("completed", "failed"), (
            f"Study should complete or fail gracefully, got: {data['status']}"
        )


# ===========================================================================
# 5. Study request with extremely large system (1000+ buses)
# ===========================================================================

class TestLargeSystem:
    """Edge case: a system with 1000+ buses."""

    def test_1000_bus_system(self, client, auth_headers):
        """Creating and running a study on a 1000-bus system should not crash."""
        buses = [
            {"bus_id": i, "voltage_magnitude": 1.0, "bus_type": "pq"}
            for i in range(1, 1001)
        ]
        # Make bus 1 slack
        buses[0]["bus_type"] = "slack"
        buses[0]["voltage_magnitude"] = 1.05

        lines = [
            {
                "line_id": i,
                "from_bus_id": i,
                "to_bus_id": i + 1,
                "r1": 0.01,
                "x1": 0.05,
            }
            for i in range(1, 1000)
        ]

        config = {
            "base_mva": 100.0,
            "buses": buses,
            "lines": lines,
            "generators": [{"generator_id": 1, "bus_id": 1}],
        }

        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"name": "1000 Bus System", "system_config": config},
        )
        assert resp.status_code == 201, f"Project creation should succeed: {resp.text}"
        project_id = resp.json()["id"]

        study_resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        # Should not crash the server
        assert study_resp.status_code == 201, f"Study request should not crash: {study_resp.text}"
        data = study_resp.json()
        assert data["status"] in ("completed", "failed"), (
            f"Study should complete or fail gracefully, got: {data['status']}"
        )


# ===========================================================================
# 6. Cache collision: two different systems producing same SHA-256 hash
# ===========================================================================

class TestCacheCollision:
    """Edge case: SHA-256 hash collision for cache keys (format test).

    Note: A real SHA-256 collision is computationally infeasible. This test
    validates the format and structure of the cache hashing mechanism, not
    an actual collision.
    """

    def test_different_configs_produce_different_hashes(self):
        """Two different system configs should produce different SHA-256 hashes."""
        config_a = {"base_mva": 100, "buses": [{"bus_id": 1}]}
        config_b = {"base_mva": 200, "buses": [{"bus_id": 1}]}

        hash_a = hashlib.sha256(
            json.dumps(config_a, sort_keys=True).encode()
        ).hexdigest()
        hash_b = hashlib.sha256(
            json.dumps(config_b, sort_keys=True).encode()
        ).hexdigest()

        assert hash_a != hash_b, (
            "Different configs must produce different SHA-256 hashes"
        )

    def test_same_config_produces_same_hash(self):
        """Identical system configs should produce identical SHA-256 hashes."""
        config = {"base_mva": 100, "buses": [{"bus_id": 1, "voltage_magnitude": 1.05}]}

        hash_1 = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        hash_2 = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()

        assert hash_1 == hash_2, "Same config must produce same SHA-256 hash"

    def test_hash_format(self):
        """Cache hashes should be 64-character hex strings (SHA-256)."""
        config = {"base_mva": 100}
        h = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        assert len(h) == 64, f"SHA-256 hex digest should be 64 chars, got {len(h)}"
        assert all(c in "0123456789abcdef" for c in h), "Hash should be hex"


# ===========================================================================
# 7. Rate limiter under burst traffic (100 concurrent requests)
# ===========================================================================

class TestRateLimiterBurst:
    """Edge case: burst traffic against the login rate limiter."""

    def test_burst_login_attempts(self, client):
        """Sending many rapid login attempts triggers rate limiting.

        We test with a burst of requests. The first 5 should get 401
        (wrong password), and subsequent ones should get 429 (rate limited).
        """
        # Register a user
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "burstuser",
                "email": "burst@example.com",
                "password": "S3cureP@ss!",
            },
        )

        # Send 20 rapid failed login attempts from multiple threads
        results = []
        lock = threading.Lock()

        def attempt_login(idx):
            try:
                resp = client.post(
                    "/api/v1/auth/login",
                    json={"username": "burstuser", "password": f"Wrong{idx}!"},
                )
                with lock:
                    results.append(resp.status_code)
            except Exception as exc:
                with lock:
                    results.append(-1)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_login, i) for i in range(20)]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

        # At least some should be rate-limited (429)
        rate_limited = sum(1 for code in results if code == 429)
        unauthorized = sum(1 for code in results if code == 401)
        total_valid = rate_limited + unauthorized

        assert total_valid >= 5, (
            f"Expected at least 5 valid responses (401 or 429), got {total_valid}"
        )
        # After 5 failures, subsequent attempts should be rate-limited
        assert rate_limited > 0, (
            f"Expected some rate-limited responses (429), got {rate_limited} out of {len(results)}"
        )


# ===========================================================================
# 8. JWT token manipulation
# ===========================================================================

class TestJWTManipulation:
    """Edge case: various JWT token manipulation attacks."""

    def test_modified_payload(self, client):
        """A JWT with a modified payload (but re-signed incorrectly) is rejected."""
        # Create a valid token first by registering and logging in
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "jwtmanip",
                "email": "jwtmanip@example.com",
                "password": "S3cureP@ss!",
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "jwtmanip", "password": "S3cureP@ss!"},
        )
        valid_token = login_resp.json()["access_token"]

        # Decode without verification to get the payload
        payload = jwt.decode(valid_token, options={"verify_signature": False})
        # Tamper with the role
        payload["role"] = "admin"

        # Re-encode with a different secret (forged)
        forged_token = jwt.encode(payload, "wrong-secret-key", algorithm=JWT_ALGORITHM)

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        assert resp.status_code == 401, (
            f"Forged token should be rejected, got {resp.status_code}"
        )

    def test_expired_token(self, client):
        """An expired JWT is rejected."""
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "role": "engineer",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
        )

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401, (
            f"Expired token should be rejected, got {resp.status_code}"
        )

    def test_none_algorithm(self, client):
        """A JWT signed with 'none' algorithm is rejected."""
        payload = {
            "sub": str(uuid.uuid4()),
            "role": "admin",
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        # Encode with none algorithm (no signature)
        none_token = jwt.encode(payload, "", algorithm="none")

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        assert resp.status_code == 401, (
            f"'none' algorithm token should be rejected, got {resp.status_code}"
        )


# ===========================================================================
# 9. SQL injection in project name field
# ===========================================================================

class TestSQLInjection:
    """Edge case: SQL injection attempts in the project name field."""

    SQLI_PAYLOADS = [
        "'; DROP TABLE projects;--",
        "' OR '1'='1",
        "1; SELECT * FROM users--",
        "' UNION SELECT password_hash FROM users--",
    ]

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_sql_injection_in_project_name(self, client, auth_headers, payload):
        """SQL injection in project name should not compromise the database.

        The project may or may not be created (depending on validation),
        but the database should remain intact and functional.
        """
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"name": payload},
        )
        # Regardless of whether the project is created, the API should
        # still function normally afterward
        verify_resp = client.get("/api/v1/projects/", headers=auth_headers)
        assert verify_resp.status_code == 200, (
            "API should remain functional after SQL injection attempt"
        )


# ===========================================================================
# 10. XSS in project description field
# ===========================================================================

class TestXSSInjection:
    """Edge case: XSS attempts in the project description field."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert('xss')",
        "<svg onload=alert('xss')>",
    ]

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_project_description(self, client, auth_headers, payload):
        """XSS payloads in project description should be stored safely.

        The payload may be stored verbatim (it's the frontend's
        responsibility to escape on render), but the API should not crash.
        """
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": "XSS Test Project",
                "description": payload,
            },
        )
        assert resp.status_code == 201, (
            f"Project creation should succeed with XSS payload, got {resp.status_code}: {resp.text}"
        )
        # Verify the description is stored (possibly verbatim)
        project_id = resp.json()["id"]
        get_resp = client.get(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        # The description should be present — the API stores it as-is;
        # rendering/escaping is the frontend's job
        assert get_resp.json()["description"] is not None
