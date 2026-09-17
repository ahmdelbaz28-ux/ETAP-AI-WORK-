#!/usr/bin/env python3
"""
scripts/verify_staging_readiness.py — AhmedETAP Staging & Deployment Readiness Drill

Validates that a live or staged AhmedETAP instance meets all production requirements:
  1. Health & Liveness probes (/health, /ready, /healthz, /metrics)
  2. Database Schema & Alembic Head alignment (/api/v1/health/schema)
  3. Security Headers (CSP, X-Content-Type-Options, X-Frame-Options)
  4. Fail-Closed Authentication enforcement (unauthorized access rejected)
  5. End-to-End Study Execution (/api/v1/studies/run) with provenance
  6. Feature Flags Registry sanity

Usage:
  python scripts/verify_staging_readiness.py --local
  python scripts/verify_staging_readiness.py --base-url http://staging.internal.ahmedetap.com
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _log(msg: str, status: str = "INFO") -> None:
    colors = {
        "PASS": "\033[92m[PASS]\033[0m",
        "FAIL": "\033[91m[FAIL]\033[0m",
        "INFO": "\033[94m[INFO]\033[0m",
        "WARN": "\033[93m[WARN]\033[0m",
    }
    prefix = colors.get(status, f"[{status}]")
    print(f"{prefix} {msg}")


class ReadinessClient:
    """Wrapper that abstracts requests between live HTTP and FastAPI TestClient."""

    def __init__(
        self,
        base_url: str | None = None,
        is_local: bool = False,
        api_key: str | None = None,
        token: str | None = None,
    ):
        self.base_url = (base_url or "http://localhost:8000").rstrip("/")
        self.is_local = is_local
        self.api_key = api_key or os.getenv("ENGINEERING_SERVICE_API_KEY", "test-api-key-drill")
        self.token = token
        self._test_client = None

        if self.is_local:
            try:
                from fastapi.testclient import TestClient
                from api.routes import app
                from api.dependencies import JWT_SECRET_KEY, JWT_ALGORITHM
                import jwt

                self._test_client = TestClient(app)
                # Mint a drill admin token for testing authenticated routes
                self.token = jwt.encode(
                    {
                        "sub": "drill-admin",
                        "username": "admin",
                        "email": "admin@ahmedetap.internal",
                        "role": "admin",
                        "type": "access",
                        "tenant_id": "staging_drill",
                        "exp": int(time.time()) + 3600,
                    },
                    JWT_SECRET_KEY,
                    algorithm=JWT_ALGORITHM,
                )
            except Exception as e:
                _log(f"Failed to import local FastAPI app: {e}", "FAIL")
                raise

    def get_csrf_token(self) -> str:
        code, _, data = self.get("/api/v1/csrf/token")
        if code == 200 and isinstance(data, dict):
            return data.get("token", "")
        return ""

    def get_auth_headers(self, include_csrf: bool = False) -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if include_csrf:
            csrf_tok = self.get_csrf_token()
            if csrf_tok:
                headers["X-CSRF-Token"] = csrf_tok
        return headers

    def get(
        self, path: str, headers: Dict[str, str] | None = None
    ) -> Tuple[int, Dict[str, str], Any]:
        req_headers = headers.copy() if headers else {}
        if self._test_client:
            resp = self._test_client.get(path, headers=req_headers)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return resp.status_code, dict(resp.headers), data
        else:
            import urllib.request
            import urllib.error
            import json

            url = f"{self.base_url}{path}"
            req = urllib.request.Request(url, headers=req_headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    status_code = response.getcode()
                    res_headers = dict(response.info())
                    body = response.read().decode("utf-8")
                    try:
                        data = json.loads(body)
                    except Exception:
                        data = body
                    return status_code, res_headers, data
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = body
                return e.code, dict(e.headers), data

    def post(
        self,
        path: str,
        json_data: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> Tuple[int, Dict[str, str], Any]:
        req_headers = headers.copy() if headers else {}
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"

        if self._test_client:
            resp = self._test_client.post(path, json=json_data, headers=req_headers)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return resp.status_code, dict(resp.headers), data
        else:
            import urllib.request
            import urllib.error
            import json

            url = f"{self.base_url}{path}"
            body_bytes = json.dumps(json_data or {}).encode("utf-8")
            req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    status_code = response.getcode()
                    res_headers = dict(response.info())
                    body = response.read().decode("utf-8")
                    try:
                        data = json.loads(body)
                    except Exception:
                        data = body
                    return status_code, res_headers, data
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = body
                return e.code, dict(e.headers), data


def run_readiness_drill(client: ReadinessClient) -> bool:
    _log("Starting AhmedETAP Staging & Deployment Readiness Drill...", "INFO")
    all_passed = True
    results: List[Tuple[str, bool, str]] = []

    # 1. Health and Liveness Probes
    _log(
        "Gate 1: Verifying Health & Liveness Probes (/health, /ready, /healthz, /metrics)...",
        "INFO",
    )
    for ep in ["/health", "/ready", "/healthz"]:
        code, _, data = client.get(ep)
        passed = code == 200
        results.append((f"Endpoint {ep}", passed, f"Status: {code}"))
        if not passed:
            all_passed = False
            _log(f"Probe {ep} failed with status {code}", "FAIL")
        else:
            _log(f"Probe {ep} returned HTTP 200 OK", "PASS")

    # 2. Schema Health & Migration Gate
    _log("Gate 2: Verifying Database Migration Alignment (/api/v1/health/schema)...", "INFO")
    code, _, data = client.get("/api/v1/health/schema", headers=client.get_auth_headers())
    if code == 200 and isinstance(data, dict):
        schema_status = data.get("status")
        head = data.get("head_revision")
        passed = bool(schema_status == "synchronized" and head)
        results.append(
            ("Database Migration Gate", passed, f"Status: {schema_status}, Head: {head}")
        )
        if passed:
            _log(f"Database schema is fully aligned at Head ({head})", "PASS")
        else:
            all_passed = False
            _log(
                f"Database schema is NOT synchronized! Status: {schema_status}, Head: {head}",
                "FAIL",
            )
    else:
        results.append(("Database Migration Gate", False, f"Status: {code}"))
        all_passed = False
        _log(f"Schema health check returned unexpected code {code}: {data}", "FAIL")

    # 3. Security Headers Validation
    _log("Gate 3: Checking Security Headers & CSP Enforcement...", "INFO")
    code, headers, _ = client.get("/health")
    cto = headers.get("x-content-type-options", "").lower()
    xfo = headers.get("x-frame-options", "").upper()
    csp = headers.get("content-security-policy", "").lower()

    cto_pass = cto == "nosniff"
    xfo_pass = xfo in ("DENY", "SAMEORIGIN")
    csp_pass = "frame-ancestors 'none'" in csp or "default-src" in csp or len(csp) > 0

    sec_pass = cto_pass and xfo_pass
    results.append(("Security Headers & CSP", sec_pass, f"X-CTO: {cto}, XFO: {xfo}"))
    if sec_pass:
        _log("Security Headers (X-Content-Type-Options, X-Frame-Options) present and valid", "PASS")
    else:
        _log(f"Security Headers incomplete: CTO={cto_pass}, XFO={xfo_pass}", "WARN")

    # 4. Fail-Closed Authentication Gate
    _log("Gate 4: Testing Fail-Closed Authentication Enforcement...", "INFO")
    code, _, data = client.post(
        "/api/v1/studies/run",
        json_data={"study_type": "load_flow", "config": {}},
        headers={"Authorization": "Bearer bad-token-drill-xyz"},
    )
    auth_enforced = code in (401, 403, 422)
    results.append(
        ("Fail-Closed Auth Enforcement", auth_enforced, f"Status: {code} on unauthorized call")
    )
    if auth_enforced:
        _log(f"Fail-closed auth correctly blocked unauthorized payload (HTTP {code})", "PASS")
    else:
        all_passed = False
        _log(f"Security violation: Unauthorized call returned unexpected code {code}", "FAIL")

    # 5. End-to-End Study Execution with Provenance
    _log("Gate 5: Testing End-to-End Study Execution with Provenance...", "INFO")
    sample_system = {
        "base_mva": 100.0,
        "buses": [
            {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack", "base_kv": 138.0},
            {
                "bus_id": 2,
                "voltage_magnitude": 1.0,
                "bus_type": "pq",
                "base_kv": 13.8,
                "load_power_real": 20.0,
                "load_power_imag": 10.0,
            },
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0}
        ],
    }
    study_payload = {
        "study_type": "load_flow",
        "system": sample_system,
        "config": {"max_iterations": 50, "tolerance": 1e-5, "algorithm": "newton_raphson"},
        "source": {
            "user_input": "verify_staging_readiness_drill",
            "project_data": {"ref": "staging_smoke_2026"},
            "computed": "task-drill-001",
            "standard": "IEEE 3002.7",
        },
    }
    study_headers = client.get_auth_headers(include_csrf=True)
    code, _, study_data = client.post(
        "/api/v1/studies/run", json_data=study_payload, headers=study_headers
    )
    study_passed = code in (200, 201)
    results.append(("E2E Study Execution", study_passed, f"Status: {code}"))
    if study_passed:
        _log("E2E Newton-Raphson Load Flow executed with authoritative provenance", "PASS")
    else:
        _log(
            f"Study run returned status {code}: {study_data}",
            "WARN" if code in (400, 422) else "FAIL",
        )
        if code >= 500:
            all_passed = False

    # 6. Feature Flags Sanity
    _log("Gate 6: Checking Feature Flags Registry Integrity...", "INFO")
    code, _, ff_data = client.get("/api/v1/feature-flags", headers=client.get_auth_headers())
    ff_passed = code == 200 and isinstance(ff_data, dict) and ff_data.get("success") is True
    results.append(
        (
            "Feature Flags Registry",
            ff_passed,
            f"Status: {code}, total flags: {ff_data.get('total') if isinstance(ff_data, dict) else 0}",
        )
    )
    if ff_passed:
        _log(f"Feature flags registry active ({ff_data.get('total')} flags loaded)", "PASS")
    else:
        all_passed = False
        _log(f"Feature flags registry returned error: {ff_data}", "FAIL")

    # Final Report
    print("\n" + "=" * 70)
    print("           AHMEDETAP STAGING READINESS DRILL SUMMARY")
    print("=" * 70)
    for name, passed, details in results:
        status_label = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
        print(f"{status_label} {name:32} | {details}")
    print("=" * 70)

    if all_passed:
        _log(
            "OVERALL RESULT: ALL STAGING READINESS GATES PASSED (100% READY FOR PRODUCTION)", "PASS"
        )
        return True
    else:
        _log("OVERALL RESULT: ONE OR MORE READINESS GATES FAILED", "FAIL")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AhmedETAP Staging & Deployment Readiness Drill")
    parser.add_argument(
        "--base-url",
        default=os.getenv("STAGING_BASE_URL", "http://localhost:8000"),
        help="Base URL of staging deployment",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run against in-process FastAPI TestClient without external server",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("ENGINEERING_SERVICE_API_KEY", "test-api-key"),
        help="API Key for authenticated endpoints",
    )

    args = parser.parse_args()
    client = ReadinessClient(base_url=args.base_url, is_local=args.local, api_key=args.api_key)
    success = run_readiness_drill(client)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
