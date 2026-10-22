#!/usr/bin/env python3
"""
scripts/run_staging_quick_tunnel.py — Start Quick Tunnel & Update Staging Cloudflare Worker.

1. Spawns `cloudflared.exe tunnel --no-autoupdate --url http://127.0.0.1:7860 --logfile quick_tunnel.log`
2. Extracts the generated ephemeral Quick Tunnel URL (`https://*.trycloudflare.com`)
3. Verifies liveness of the Quick Tunnel
4. Updates `ahmedetap-staging-proxy` Cloudflare Worker with ORIGIN_URL
5. Verifies public Worker entrypoint `https://ahmedetap-staging-proxy.ahmedetap.workers.dev`
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.deploy_staging_worker import deploy_staging_worker

CLOUDFLARED_BIN = REPO_ROOT / "cloudflared.exe"
LOG_FILE = REPO_ROOT / "quick_tunnel.log"
WORKER_PUBLIC_URL = "https://ahmedetap-staging-proxy.ahmedetap.workers.dev"


def start_quick_tunnel(local_url: str = "http://127.0.0.1:7860", timeout: int = 40):
    if not CLOUDFLARED_BIN.exists():
        raise FileNotFoundError(f"cloudflared binary not found at: {CLOUDFLARED_BIN}")

    # Remove previous log file if exists
    if LOG_FILE.exists():
        try:
            LOG_FILE.unlink()
        except Exception:
            pass

    cmd = [
        str(CLOUDFLARED_BIN),
        "tunnel",
        "--no-autoupdate",
        "--url",
        local_url,
        "--logfile",
        str(LOG_FILE),
    ]

    print(f"Launching Quick Tunnel targeting {local_url} (logfile: {LOG_FILE})...", flush=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"cloudflared exited unexpectedly with code {proc.returncode}")

        if LOG_FILE.exists():
            try:
                content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
                match = url_pattern.search(content)
                if match:
                    tunnel_url = match.group(0)
                    print(f"Discovered Quick Tunnel URL: {tunnel_url}", flush=True)
                    break
            except Exception:
                pass
        time.sleep(0.5)

    if not tunnel_url:
        proc.kill()
        raise RuntimeError("Timed out waiting for trycloudflare.com URL from cloudflared")

    # Verify that the tunnel is reachable externally
    print(f"Verifying reachability of Quick Tunnel at {tunnel_url}/healthz...", flush=True)
    verified = False
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        for attempt in range(1, 15):
            try:
                resp = client.get(f"{tunnel_url}/healthz")
                if resp.status_code == 200:
                    print(f"Quick Tunnel verified healthy (HTTP 200) on attempt {attempt}", flush=True)
                    verified = True
                    break
            except Exception:
                time.sleep(2)

    if not verified:
        print("Warning: Direct Quick Tunnel probe did not return 200 within timeout, continuing to worker update...", flush=True)

    # Update Cloudflare Staging Worker with the verified Quick Tunnel origin
    print(f"Deploying/updating Staging Worker with origin: {tunnel_url}...", flush=True)
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise RuntimeError("CLOUDFLARE_API_TOKEN environment variable is required to update staging worker")

    deploy_res = deploy_staging_worker(origin_url=tunnel_url)
    print("Staging Worker Updated Successfully:", flush=True)
    print(f"  Public Endpoint: {deploy_res['public_url']}", flush=True)
    print(f"  Upstream Origin: {deploy_res['origin_url']}", flush=True)
    print(f"  HTTP Verification Status: {deploy_res['verify_status']}", flush=True)

    return proc, tunnel_url


if __name__ == "__main__":
    try:
        proc, url = start_quick_tunnel()
        print("\nStaging Domainless Ingress is LIVE and ROUTED:", flush=True)
        print(f"  Public Entrypoint: {WORKER_PUBLIC_URL}", flush=True)
        print(f"  Quick Tunnel     : {url}", flush=True)
        print("Tunnel process is active. Press Ctrl+C to terminate.", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping Quick Tunnel...", flush=True)
    except Exception as err:
        print(f"Fatal error: {err}", file=sys.stderr, flush=True)
        sys.exit(1)
