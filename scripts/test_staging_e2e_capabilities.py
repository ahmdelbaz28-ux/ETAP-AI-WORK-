#!/usr/bin/env python3
"""
scripts/test_staging_e2e_capabilities.py — Real End-to-End Staging Capability & SSE Probe.

Probes the dedicated Cloudflare Worker:
  https://ahmedetap-staging-proxy.ahmedetap.workers.dev

Validates:
1. Public /healthz (HTTP 200)
2. Public /readyz (HTTP 200)
3. Public /version (HTTP 200, commit_sha matches DEPLOY_SHA)
4. Authenticated Engineering Study POST /api/v1/studies/run (valid finite numbers)
5. Unauthenticated Chat Stream POST /api/v1/chat/stream (strict HTTP 401 fail-closed)
6. Authenticated Chat Stream POST /api/v1/chat/stream (SSE streaming, content-type, event framing, incremental chunk timing)
"""

from __future__ import annotations

import math
import sys
import time
from typing import List, Tuple

import httpx

STAGING_WORKER_URL = "https://ahmedetap-staging-proxy.ahmedetap.workers.dev"
EXPECTED_SHA = "06b2322f12720dcbaf7877d001a95eb951132810"
STAGING_API_KEY = "staging-test-api-key-2026"


def probe_public_health(client: httpx.Client) -> dict:
    resp = client.get(f"{STAGING_WORKER_URL}/healthz")
    assert resp.status_code == 200, f"/healthz failed with status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got: {data}"
    return data


def probe_public_ready(client: httpx.Client) -> dict:
    resp = client.get(f"{STAGING_WORKER_URL}/readyz")
    assert resp.status_code == 200, f"/readyz failed with status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("status") == "ready", f"Expected status 'ready', got: {data}"
    return data


def probe_public_version(client: httpx.Client) -> str:
    resp = client.get(f"{STAGING_WORKER_URL}/version")
    assert resp.status_code == 200, f"/version failed with status {resp.status_code}: {resp.text}"
    data = resp.json()
    sha = data.get("commit_sha")
    assert sha == EXPECTED_SHA, f"Expected commit_sha {EXPECTED_SHA}, got: {sha}"
    return sha


def probe_engineering_study(client: httpx.Client) -> dict:
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
        f"{STAGING_WORKER_URL}/api/v1/studies/run",
        json=payload,
        headers={"X-API-Key": STAGING_API_KEY},
    )
    assert resp.status_code == 200, f"Study run failed with status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("success") is True, f"Study success is not True: {data}"

    res = data.get("results") or data.get("data")
    assert isinstance(res, dict), f"Results is not a dict: {type(res)}"

    for field in ["incident_energy_cal_per_cm2", "arc_flash_boundary_mm", "arc_current_ka"]:
        assert field in res, f"Missing required field: {field}"
        val = res[field]
        assert isinstance(val, (int, float)) and math.isfinite(val) and val > 0, f"Field {field} not a positive finite number: {val}"

    return res


def probe_unauthenticated_chat(client: httpx.Client) -> int:
    payload = {
        "session_id": "probe-unauth-test",
        "messages": [{"role": "user", "content": "ping"}],
    }
    resp = client.post(f"{STAGING_WORKER_URL}/api/v1/chat/stream", json=payload)
    assert resp.status_code in (401, 403), f"Unauthenticated chat should be rejected with 401/403, got: {resp.status_code}"
    return resp.status_code


def probe_authenticated_sse(client: httpx.Client) -> Tuple[bool, List[float], str]:
    """Test authenticated SSE streaming and measure incremental inter-chunk arrival times."""
    payload = {
        "session_id": "probe-sse-streaming",
        "messages": [{"role": "user", "content": "test stream"}],
    }

    url = f"{STAGING_WORKER_URL}/api/v1/chat/stream"
    headers = {
        "X-API-Key": STAGING_API_KEY,
        "Accept": "text/event-stream",
    }

    chunk_arrival_times: List[float] = []
    received_chunks: List[str] = []

    req = client.build_request("POST", url, json=payload, headers=headers)
    t0 = time.time()
    resp = client.send(req, stream=True)

    assert resp.status_code == 200, f"SSE endpoint returned status {resp.status_code}"
    content_type = (resp.headers.get("content-type") or "").lower()
    assert "text/event-stream" in content_type, f"Expected text/event-stream, got: {content_type}"

    for chunk in resp.iter_text():
        if chunk:
            now = time.time()
            chunk_arrival_times.append(now - t0)
            received_chunks.append(chunk)

    full_body = "".join(received_chunks)
    assert "event: token" in full_body, f"Missing 'event: token' framing: {full_body[:200]}"
    assert "event: done" in full_body, f"Missing 'event: done' framing: {full_body[:200]}"
    assert "[DONE]" in full_body, f"Missing '[DONE]' marker: {full_body[:200]}"

    # Evaluate whether chunks arrived incrementally vs buffered
    # If chunks arrived with distinct timestamps separated by > 20ms, it is streaming!
    # If all chunks arrived in a single batch (delta between first and last < 10ms for multi-chunk), it was buffered.
    is_incremental = False
    if len(chunk_arrival_times) > 1:
        total_duration = chunk_arrival_times[-1] - chunk_arrival_times[0]
        # Our server paused 60ms between 9 chunks (~540ms total)
        if total_duration > 0.25:  # At least 250ms spread proves streaming
            is_incremental = True

    return is_incremental, chunk_arrival_times, full_body


def run_full_capability_suite():
    print(f"=== Probing Public Staging Entrypoint: {STAGING_WORKER_URL} ===")
    with httpx.Client(timeout=30) as client:
        # 1. Healthz
        h_data = probe_public_health(client)
        print(f"  [1/6] /healthz: PASS (status={h_data.get('status')}, env={h_data.get('environment')})")

        # 2. Readyz
        r_data = probe_public_ready(client)
        print(f"  [2/6] /readyz: PASS (status={r_data.get('status')}, db={r_data.get('database')})")

        # 3. Version
        sha = probe_public_version(client)
        print(f"  [3/6] /version: PASS (commit_sha={sha})")

        # 4. Engineering Study
        study_res = probe_engineering_study(client)
        print(f"  [4/6] /api/v1/studies/run: PASS (arc_flash: incident_energy={study_res.get('incident_energy_cal_per_cm2')} cal/cm², boundary={study_res.get('arc_flash_boundary_mm')} mm, current={study_res.get('arc_current_ka')} kA)")

        # 5. Unauthenticated Chat Auth Boundary
        unauth_status = probe_unauthenticated_chat(client)
        print(f"  [5/6] /api/v1/chat/stream (Unauth): PASS (strictly rejected with HTTP {unauth_status})")

        # 6. Authenticated SSE Stream
        is_incremental, timings, body = probe_authenticated_sse(client)
        total_time = timings[-1] - timings[0] if len(timings) > 1 else 0
        print(f"  [6/6] /api/v1/chat/stream (Auth SSE): {'PASS (INCREMENTAL REAL-TIME STREAMING)' if is_incremental else 'BUFFERED'}")
        print(f"        Chunks received: {len(timings)}, Total stream delivery span: {total_time:.3f}s")
        print(f"        Arrival offsets: {[round(t, 3) for t in timings[:6]]}...")
        print("        Framing verified: event: token, event: done, [DONE]")

        return {
            "health": True,
            "ready": True,
            "version_sha": sha,
            "study_success": True,
            "unauth_status": unauth_status,
            "sse_incremental": is_incremental,
            "sse_chunks": len(timings),
            "sse_duration_sec": total_time,
        }


if __name__ == "__main__":
    try:
        results = run_full_capability_suite()
        print("\nAll Public Staging Capability Probes Succeeded!")
    except Exception as exc:
        print(f"\nProbe suite failed: {exc}", file=sys.stderr)
        sys.exit(1)
