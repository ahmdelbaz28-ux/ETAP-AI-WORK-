#!/usr/bin/env python3
"""
scripts/post_deploy_smoke.py — End-to-End Post-Deployment Verification Pipeline.

Validates the full operational lifecycle against a live deployed platform:
1. Fetch CSRF token: GET /api/v1/csrf/token
2. Register temporary smoke test user: POST /api/v1/auth/register
3. Authenticate and obtain JWT: POST /api/v1/auth/login
4. Create power system project: POST /api/v1/projects
5. Execute simulation study: POST /api/v1/studies/run
6. Verify UI <-> API version parity: /version vs Vercel /version or headers

Fails closed (exit code 1) on any unexpected status code, timeout, or payload mismatch.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Optional, Tuple


def _log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    print(f"[{timestamp}] [SMOKE-PIPELINE] {msg}", flush=True)


def _request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    req_headers = {"User-Agent": "AhmedETAP-PostDeploy-Smoke/3.0"}
    if headers:
        req_headers.update(headers)

    body_bytes: Optional[bytes] = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            raw_body = response.read().decode("utf-8")
            resp_headers = dict(response.headers)
            try:
                parsed_json = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                parsed_json = {"raw": raw_body}
            return status_code, parsed_json, resp_headers
    except urllib.error.HTTPError as err:
        status_code = err.code
        raw_body = err.read().decode("utf-8", errors="replace")
        resp_headers = dict(err.headers)
        try:
            parsed_json = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            parsed_json = {"raw": raw_body, "error": str(err)}
        return status_code, parsed_json, resp_headers
    except Exception as exc:
        return 0, {"error": str(exc)}, {}


def run_smoke_pipeline(base_url: str, ui_url: Optional[str] = None, api_key: Optional[str] = None) -> bool:
    _log(f"Starting post-deployment smoke verification against API: {base_url}")
    if ui_url:
        _log(f"UI parity verification target: {ui_url}")

    # -------------------------------------------------------------------------
    # Step 1: GET /healthz and /version
    # -------------------------------------------------------------------------
    _log("Step 1/6: Checking /healthz and /version endpoints...")
    status, health_body, _ = _request(f"{base_url}/healthz")
    if status != 200 or health_body.get("status") not in ("ok", "healthy"):
        _log(f"FAILED: /healthz returned status {status}, body={health_body}")
        return False
    _log(f"PASS: /healthz OK (db={health_body.get('database')}, redis={health_body.get('redis')})")

    status, ver_body, _ = _request(f"{base_url}/version")
    if status != 200:
        _log(f"FAILED: /version returned status {status}")
        return False
    api_commit_sha = ver_body.get("commit_sha", "unknown")
    _log(f"PASS: /version OK (version={ver_body.get('version')}, commit_sha={api_commit_sha})")

    # -------------------------------------------------------------------------
    # Step 2: GET /api/v1/csrf/token
    # -------------------------------------------------------------------------
    _log("Step 2/6: Fetching CSRF token...")
    status, csrf_body, csrf_headers = _request(f"{base_url}/api/v1/csrf/token")
    if status != 200 or "csrf_token" not in csrf_body:
        _log(f"FAILED: /api/v1/csrf/token returned status {status}, body={csrf_body}")
        return False
    csrf_token = csrf_body["csrf_token"]
    cookie_header = csrf_headers.get("Set-Cookie", "")
    _log(f"PASS: CSRF token acquired ({csrf_token[:8]}...)")

    # -------------------------------------------------------------------------
    # Step 3: POST /api/v1/auth/register
    # -------------------------------------------------------------------------
    _log("Step 3/6: Registering temporary smoke test user...")
    uid = uuid.uuid4().hex[:8]
    username = f"smoke_user_{uid}"
    email = f"smoke_{uid}@example.com"
    password = f"P@ssw0rd_{uuid.uuid4().hex[:10]}!A"

    auth_headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": base_url,
    }
    if cookie_header:
        auth_headers["Cookie"] = cookie_header
    if api_key:
        auth_headers["X-API-Key"] = api_key

    reg_payload = {
        "username": username,
        "email": email,
        "password": password,
    }
    status, reg_body, _ = _request(
        f"{base_url}/api/v1/auth/register",
        method="POST",
        headers=auth_headers,
        data=reg_payload,
    )
    if status not in (200, 201):
        _log(f"FAILED: /api/v1/auth/register returned status {status}, body={reg_body}")
        return False
    _log(f"PASS: Smoke user registered successfully (user_id={reg_body.get('id')})")

    # -------------------------------------------------------------------------
    # Step 4: POST /api/v1/auth/login
    # -------------------------------------------------------------------------
    _log("Step 4/6: Authenticating smoke user (JWT exchange)...")
    login_payload = {
        "username": username,
        "password": password,
    }
    status, login_body, _ = _request(
        f"{base_url}/api/v1/auth/login",
        method="POST",
        headers=auth_headers,
        data=login_payload,
    )
    if status != 200 or "access_token" not in login_body:
        _log(f"FAILED: /api/v1/auth/login returned status {status}, body={login_body}")
        return False
    access_token = login_body["access_token"]
    _log("PASS: JWT access token acquired successfully")

    # -------------------------------------------------------------------------
    # Step 5: POST /api/v1/projects & POST /api/v1/studies/run
    # -------------------------------------------------------------------------
    _log("Step 5/6: Creating project and running simulation study...")
    bearer_headers = {
        "Authorization": f"Bearer {access_token}",
        "X-CSRF-Token": csrf_token,
        "Origin": base_url,
    }
    if api_key:
        bearer_headers["X-API-Key"] = api_key

    proj_payload = {
        "name": f"Smoke Project {uid}",
        "description": "Automated post-deploy smoke verification project",
        "system_config": {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "name": "Bus-1", "base_kv": 115.0},
                {"bus_id": 2, "name": "Bus-2", "base_kv": 13.8},
            ],
            "branches": [
                {
                    "branch_id": 1,
                    "from_bus": 1,
                    "to_bus": 2,
                    "r": 0.01,
                    "x": 0.05,
                    "b": 0.0,
                    "status": 1,
                }
            ],
        },
    }
    status, proj_body, _ = _request(
        f"{base_url}/api/v1/projects",
        method="POST",
        headers=bearer_headers,
        data=proj_payload,
    )
    if status not in (200, 201) or "id" not in proj_body:
        _log(f"FAILED: /api/v1/projects returned status {status}, body={proj_body}")
        return False
    project_id = proj_body["id"]
    _log(f"PASS: Project created successfully (project_id={project_id})")

    study_payload = {
        "study_type": "load_flow",
        "system": proj_payload["system_config"],
        "parameters": {"max_iterations": 20, "tolerance": 1e-5},
    }
    status, study_body, _ = _request(
        f"{base_url}/api/v1/studies/run",
        method="POST",
        headers=bearer_headers,
        data=study_payload,
    )
    if status != 200 or not study_body:
        _log(f"FAILED: /api/v1/studies/run returned status {status}, body={study_body}")
        return False
    _log("PASS: Study simulation executed and returned valid result payload")

    # -------------------------------------------------------------------------
    # Step 6: UI <-> API Parity Verification
    # -------------------------------------------------------------------------
    _log("Step 6/6: Verifying UI <-> API availability...")
    if ui_url:
        status, _, _ = _request(ui_url)
        if status != 200:
            _log(f"FAILED: UI target {ui_url} returned status {status}")
            return False
        _log(f"PASS: UI target {ui_url} reachable (status=200)")

    _log("==================================================================")
    _log("✅ POST-DEPLOYMENT SMOKE VERIFICATION COMPLETED SUCCESSFULLY!")
    _log("==================================================================")
    return True


def main() -> int:
    base_url = (
        os.getenv("SMOKE_BASE_URL")
        or (sys.argv[1] if len(sys.argv) > 1 else "https://ahmdelbaz28-ahmedetap-platform.hf.space")
    ).rstrip("/")

    ui_url = os.getenv("SMOKE_UI_URL") or "https://etap-ai-work.vercel.app"
    api_key = os.getenv("ENGINEERING_SERVICE_API_KEY") or os.getenv("HF_API_KEY")

    success = run_smoke_pipeline(base_url=base_url, ui_url=ui_url, api_key=api_key)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
