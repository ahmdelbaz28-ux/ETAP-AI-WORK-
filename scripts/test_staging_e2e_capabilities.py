#!/usr/bin/env python3
"""
scripts/test_staging_e2e_capabilities.py — Real End-to-End Staging Capability & SSE Probe.

Probes the authentic Staging public ingress and Docker backend:
  Default URL: https://ahmedetap-staging-proxy.ahmedetap.workers.dev

Validates:
1. Public /healthz (HTTP 200, status="ok")
2. Public /readyz (HTTP 200, status="ready", database verified)
3. Public /version (HTTP 200, commit_sha matches exact DEPLOY_SHA from test input)
4. Authenticated Engineering Study POST /api/v1/studies/run (valid positive finite numeric results)
5. Unauthenticated Chat Stream POST /api/v1/chat/stream (strict HTTP 401/403 fail-closed boundary)
6. Optional User Authentication via POST /api/v1/auth/login and GET /api/v1/auth/me (real backend JWT)
7. Authenticated Chat Stream POST /api/v1/chat/stream:
   - Evaluates real Server-Sent Events (SSE) streaming
   - Strict content-type: text/event-stream
   - Event framing: event: token, event: done, [DONE] marker
   - Incremental delivery timing: records client-side chunk arrival timestamps
   - Fails if the response arrives as a single buffered batch
   - Fails if HTTP 503 NO_LLM_PROVIDER_CONFIGURED is returned (real LLM provider required)

Security Invariants:
- Obtains expected commit SHA and API credentials strictly from environment or CLI arguments.
- Never prints, persists, or logs credentials.
- Zero synthetic mock fallbacks: tests the authentic hf-space/app.py backend.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

_HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def validate_sha(sha: str) -> str:
    """Validate that sha is an authentic 40-character hexadecimal git commit SHA."""
    sha = (sha or "").strip()
    if not _HEX_40_RE.match(sha):
        raise ValueError(
            f"Invalid commit SHA '{sha}': must be a full 40-character hexadecimal string"
        )
    return sha


def probe_public_health(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    """Probe public /healthz endpoint."""
    resp = client.get(f"{base_url}/healthz")
    assert resp.status_code == 200, (
        f"/healthz failed with HTTP {resp.status_code}: {resp.text[:200]}"
    )
    data = resp.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got: {data}"
    return data


def probe_public_ready(client: httpx.Client, base_url: str) -> Dict[str, Any]:
    """Probe public /readyz endpoint."""
    resp = client.get(f"{base_url}/readyz")
    assert resp.status_code == 200, (
        f"/readyz failed with HTTP {resp.status_code}: {resp.text[:200]}"
    )
    data = resp.json()
    assert data.get("status") == "ready", f"Expected status 'ready', got: {data}"
    return data


def probe_public_version(client: httpx.Client, base_url: str, expected_sha: str) -> str:
    """Probe public /version endpoint and verify exact build identity."""
    resp = client.get(f"{base_url}/version")
    assert resp.status_code == 200, (
        f"/version failed with HTTP {resp.status_code}: {resp.text[:200]}"
    )
    data = resp.json()
    sha = data.get("commit_sha") or ""
    assert sha.lower() == expected_sha.lower(), (
        f"Build identity mismatch: expected commit_sha '{expected_sha}', got '{sha}'"
    )
    return sha


def probe_engineering_study(client: httpx.Client, base_url: str, api_key: str) -> Dict[str, Any]:
    """Execute arc flash study via authentic POST /api/v1/studies/run endpoint."""
    payload = {
        "study_type": "arc_flash",
        "parameters": {
            "voltage_kv": 13.8,
            "bolted_fault_current_ka": 25.0,
            "arc_duration_sec": 0.1,
            "working_distance_mm": 914.0,
            "gap_mm": 152.0,
            "electrode_config": "VCB",
            "enclosure_type": "box",
            "enclosure_width_mm": 508.0,
            "enclosure_height_mm": 508.0,
            "enclosure_depth_mm": 508.0,
        },
    }
    resp = client.post(
        f"{base_url}/api/v1/studies/run",
        json=payload,
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200, (
        f"Study run failed with HTTP {resp.status_code}: {resp.text[:300]}"
    )
    data = resp.json()
    assert data.get("success") is True, f"Study execution reported success=False: {data}"

    res = data.get("results") or data.get("data")
    assert isinstance(res, dict), f"Study results is not a dict: {type(res)}"

    for field in ["incident_energy_cal_per_cm2", "arc_flash_boundary_mm", "arc_current_ka"]:
        assert field in res, f"Missing required engineering output field '{field}' in study result"
        val = res[field]
        assert isinstance(val, (int, float)) and math.isfinite(val) and val > 0, (
            f"Output field '{field}' is not a positive finite number: {val}"
        )

    return res


def probe_unauthenticated_chat(client: httpx.Client, base_url: str) -> int:
    """Verify that unauthenticated chat stream requests fail closed with 401 or 403."""
    payload = {
        "session_id": "probe-unauth-test",
        "messages": [{"role": "user", "content": "ping"}],
    }
    resp = client.post(f"{base_url}/api/v1/chat/stream", json=payload)
    assert resp.status_code in (401, 403), (
        f"Security boundary violation: unauthenticated chat was not rejected with 401/403 (got HTTP {resp.status_code})"
    )
    return resp.status_code


def probe_user_login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    """Authenticate via POST /api/v1/auth/login and retrieve JWT access token."""
    login_payload = {"email": email, "password": password}
    resp = client.post(f"{base_url}/api/v1/auth/login", json=login_payload)
    assert resp.status_code == 200, (
        f"User login failed with HTTP {resp.status_code}: {resp.text[:200]}"
    )
    data = resp.json()
    token = data.get("access_token") or ""
    assert token, "Login succeeded but response did not contain access_token"

    # Verify profile with token
    me_resp = client.get(f"{base_url}/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200, (
        f"Profile verification /api/v1/auth/me failed with HTTP {me_resp.status_code}"
    )
    return token


def probe_authenticated_sse(
    client: httpx.Client,
    base_url: str,
    auth_header_name: str,
    auth_header_value: str,
    llm_key: Optional[str] = None,
    llm_provider: str = "openai",
) -> Tuple[bool, List[float], str]:
    """Test authenticated SSE streaming and measure incremental inter-chunk arrival times.

    Returns:
        (is_incremental, arrival_timestamps, response_body)
    """
    payload = {
        "session_id": "probe-sse-streaming",
        "messages": [{"role": "user", "content": "What is the standard frequency for IEEE 3002?"}],
    }

    url = f"{base_url}/api/v1/chat/stream"
    headers = {
        auth_header_name: auth_header_value,
        "Accept": "text/event-stream",
    }
    if llm_key:
        headers["X-User-LLM-Key"] = llm_key
        headers["X-User-LLM-Provider"] = llm_provider

    chunk_arrival_times: List[float] = []
    received_chunks: List[str] = []

    req = client.build_request("POST", url, json=payload, headers=headers)
    t0 = time.time()
    resp = client.send(req, stream=True)

    if resp.status_code == 503:
        error_text = resp.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"SSE streaming gate failed: HTTP 503 NO_LLM_PROVIDER_CONFIGURED (no active LLM key in Staging): {error_text[:200]}"
        )

    assert resp.status_code == 200, (
        f"SSE endpoint returned unexpected HTTP {resp.status_code}: {resp.read()[:200]}"
    )
    content_type = (resp.headers.get("content-type") or "").lower()
    assert "text/event-stream" in content_type, (
        f"Expected Content-Type 'text/event-stream', got '{content_type}'"
    )

    for chunk in resp.iter_text():
        if chunk:
            now = time.time()
            chunk_arrival_times.append(now - t0)
            received_chunks.append(chunk)

    full_body = "".join(received_chunks)
    assert "event: token" in full_body, (
        f"Missing 'event: token' framing in SSE stream: {full_body[:200]}"
    )
    assert "event: done" in full_body or "[DONE]" in full_body, (
        f"Missing terminal event framing in SSE stream: {full_body[-200:]}"
    )

    # Incremental timing validation:
    # Chunks must arrive over a measurable interval (> 100ms) with multiple distinct timestamps.
    # If all chunks arrive in a single packet (spread < 20ms for multi-chunk), transport was buffered.
    is_incremental = False
    if len(chunk_arrival_times) > 1:
        total_span = chunk_arrival_times[-1] - chunk_arrival_times[0]
        if total_span > 0.10:
            is_incremental = True

    return is_incremental, chunk_arrival_times, full_body


def run_full_capability_suite(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute complete end-to-end capability verification against public staging."""
    base_url = args.url.rstrip("/")
    expected_sha = validate_sha(args.sha)
    api_key = (args.api_key or "").strip()
    if not api_key:
        raise ValueError(
            "API key must be provided via --api-key or STAGING_ENGINEERING_SERVICE_API_KEY environment variable"
        )

    print(f"=== Probing Public Staging Entrypoint: {base_url} ===")
    print(f"Expected Commit SHA: {expected_sha}")

    with httpx.Client(timeout=45.0) as client:
        # 1. Healthz
        h_data = probe_public_health(client, base_url)
        print(
            f"  [1/7] /healthz: PASS (status={h_data.get('status')}, env={h_data.get('environment')})"
        )

        # 2. Readyz
        r_data = probe_public_ready(client, base_url)
        print(f"  [2/7] /readyz: PASS (status={r_data.get('status')}, db={r_data.get('database')})")

        # 3. Version
        sha = probe_public_version(client, base_url, expected_sha)
        print(f"  [3/7] /version: PASS (commit_sha={sha})")

        # 4. Engineering Study
        study_res = probe_engineering_study(client, base_url, api_key)
        print(
            f"  [4/7] /api/v1/studies/run: PASS (arc_flash: "
            f"energy={study_res.get('incident_energy_cal_per_cm2')} cal/cm², "
            f"boundary={study_res.get('arc_flash_boundary_mm')} mm, "
            f"current={study_res.get('arc_current_ka')} kA)"
        )

        # 5. Unauthenticated Chat Auth Boundary
        unauth_status = probe_unauthenticated_chat(client, base_url)
        print(
            f"  [5/7] /api/v1/chat/stream (Unauth): PASS (strictly rejected with HTTP {unauth_status})"
        )

        # 6. User Login (if credentials provided)
        user_token = args.token or ""
        if not user_token and args.email and args.password:
            print("  [6/7] /api/v1/auth/login: Authenticating test user...")
            user_token = probe_user_login(client, base_url, args.email, args.password)
            print("        User authentication verified; JWT token obtained.")
        elif user_token:
            print("  [6/7] /api/v1/auth/me: Using provided user JWT access token.")
        else:
            if getattr(args, "require_login", False):
                raise AssertionError(
                    "User login verification is mandatory for staging release gate, but no credentials were provided."
                )
            print(
                "  [6/7] /api/v1/auth/login: Skipped (no --email/--password or --token provided; using API key for chat)."
            )

        # 7. Authenticated SSE Stream
        if user_token:
            auth_header_name = "Authorization"
            auth_header_val = f"Bearer {user_token}"
        else:
            auth_header_name = "X-API-Key"
            auth_header_val = api_key

        is_incremental, timings, _ = probe_authenticated_sse(
            client=client,
            base_url=base_url,
            auth_header_name=auth_header_name,
            auth_header_value=auth_header_val,
            llm_key=args.llm_key,
            llm_provider=args.llm_provider,
        )
        total_time = timings[-1] - timings[0] if len(timings) > 1 else 0.0
        status_label = (
            "PASS (INCREMENTAL REAL-TIME STREAMING)"
            if is_incremental
            else "BUFFERED (NON-INCREMENTAL)"
        )
        print(f"  [7/7] /api/v1/chat/stream (Auth SSE): {status_label}")
        print(f"        Chunks received: {len(timings)}, Total stream span: {total_time:.3f}s")
        print(f"        Arrival offsets: {[round(t, 3) for t in timings[:6]]}...")

        if not is_incremental:
            raise AssertionError(
                f"SSE acceptance test defect detected: stream was BUFFERED (total span {total_time:.3f}s < 0.10s, "
                f"chunks={len(timings)}). Non-incremental or buffered responses cannot pass the staging release gate."
            )

        return {
            "health": True,
            "ready": True,
            "version_sha": sha,
            "study_success": True,
            "unauth_status": unauth_status,
            "user_authenticated": bool(user_token),
            "sse_incremental": is_incremental,
            "sse_chunks": len(timings),
            "sse_duration_sec": total_time,
        }


def main():
    parser = argparse.ArgumentParser(
        description="AhmedETAP Staging Capability & SSE Verification Probe"
    )
    parser.add_argument(
        "--url",
        default=os.environ.get(
            "STAGING_WORKER_URL", "https://ahmedetap-staging-proxy.ahmedetap.workers.dev"
        ),
        help="Target Staging base URL (default: ahmedetap-staging-proxy.ahmedetap.workers.dev)",
    )
    parser.add_argument(
        "--sha",
        default=os.environ.get("DEPLOY_SHA", ""),
        help="Expected commit SHA (defaults to DEPLOY_SHA env var)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("STAGING_ENGINEERING_SERVICE_API_KEY")
        or os.environ.get("STAGING_API_KEY", ""),
        help="Staging Engineering Service API Key (defaults to STAGING_ENGINEERING_SERVICE_API_KEY env var)",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("STAGING_TEST_EMAIL", ""),
        help="Staging test user email for login verification",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("STAGING_TEST_PASSWORD", ""),
        help="Staging test user password for login verification",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("STAGING_USER_TOKEN", ""),
        help="Pre-authenticated Staging JWT Bearer token",
    )
    parser.add_argument(
        "--llm-key",
        default=os.environ.get("STAGING_LLM_KEY", ""),
        help="BYOK LLM API key for testing streaming copilot",
    )
    parser.add_argument(
        "--llm-provider",
        default=os.environ.get("STAGING_LLM_PROVIDER", "openai"),
        help="BYOK LLM provider (default: openai)",
    )
    parser.add_argument(
        "--require-login",
        action="store_true",
        default=os.environ.get("STAGING_REQUIRE_LOGIN", "").lower() in ("1", "true", "yes"),
        help="Enforce mandatory user login verification (fails if omitted)",
    )

    args = parser.parse_args()

    try:
        run_full_capability_suite(args)
        print("\nAll Public Staging Capability Probes Succeeded!")
    except Exception as exc:
        print(f"\n[FAIL] Staging Capability Probe failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
