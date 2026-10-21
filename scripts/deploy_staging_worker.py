#!/usr/bin/env python3
"""
scripts/deploy_staging_worker.py — Deploy & Configure Dedicated Staging Cloudflare Worker.

Deploys 'ahmedetap-staging-proxy' to the verified free account subdomain:
    https://ahmedetap-staging-proxy.ahmedetap.workers.dev

Upstream origin must be an explicit staging endpoint (e.g. Quick Tunnel).
Fails closed if origin points to production Hugging Face or is invalid.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

CF_ACCOUNT_ID = "8ea12977423cb0079cf4d227a0195bb1"
CF_SUBDOMAIN = "ahmedetap"
WORKER_NAME = "ahmedetap-staging-proxy"
PROD_DENYLIST = [
    "ahmdelbaz28-ahmedetap-platform.hf.space",
    "etap-ai-work.vercel.app",
    "ahmdelbaz28.com",
]


def validate_origin_url(origin: str) -> str:
    """Validate that origin is a non-empty, valid HTTP/HTTPS URL and NOT production."""
    if not origin:
        return ""
    origin = origin.strip().rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid origin URL format: '{origin}'")
    for denied in PROD_DENYLIST:
        if parsed.netloc.lower() == denied.lower():
            raise ValueError(
                f"SECURITY VIOLATION: Staging worker cannot point to production host '{denied}'"
            )
    return origin


def deploy_staging_worker(origin_url: str = "") -> dict:
    """Deploy ahmedetap-staging-proxy via Cloudflare REST API with ORIGIN_URL binding."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_TOKEN_TEST")
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN environment variable is required")

    clean_origin = validate_origin_url(origin_url)

    repo_root = Path(__file__).resolve().parent.parent
    worker_js_path = repo_root / "cloudflare" / "worker.staging.js"
    if not worker_js_path.exists():
        raise FileNotFoundError(f"Missing worker source file: {worker_js_path}")

    worker_code = worker_js_path.read_text(encoding="utf-8")

    metadata = {
        "main_module": "worker.staging.js",
        "bindings": [
            {"type": "plain_text", "name": "ORIGIN_URL", "text": clean_origin},
            {"type": "plain_text", "name": "ENVIRONMENT", "text": "staging"},
        ],
        "compatibility_date": "2024-09-01",
    }

    files = {
        "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
        "worker.staging.js": (
            "worker.staging.js",
            worker_code,
            "application/javascript+module",
        ),
    }

    headers = {"Authorization": f"Bearer {token}"}

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}"
    with httpx.Client(timeout=30) as client:
        # 1. Upload script
        resp = client.put(url, headers=headers, files=files)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to upload Worker script (HTTP {resp.status_code}): {resp.text}")

        # 2. Enable workers.dev subdomain routing for this script
        sub_url = f"{url}/subdomain"
        sub_resp = client.post(sub_url, headers=headers, json={"enabled": True})
        if sub_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to enable workers.dev subdomain (HTTP {sub_resp.status_code}): {sub_resp.text}"
            )

        public_url = f"https://{WORKER_NAME}.{CF_SUBDOMAIN}.workers.dev"

        # 3. Verify public response
        verify_resp = client.get(public_url, timeout=15)

        return {
            "worker_name": WORKER_NAME,
            "public_url": public_url,
            "origin_url": clean_origin,
            "verify_status": verify_resp.status_code,
            "verify_body": verify_resp.text[:300],
        }


def main():
    parser = argparse.ArgumentParser(description="Deploy dedicated staging Cloudflare Worker")
    parser.add_argument(
        "--origin",
        default="",
        help="Staging upstream origin URL (e.g. Quick Tunnel https://xxx.trycloudflare.com)",
    )
    args = parser.parse_args()

    try:
        res = deploy_staging_worker(args.origin)
        print("Staging Worker Deployment Succeeded:")
        print(f"  Worker Name : {res['worker_name']}")
        print(f"  Public URL  : {res['public_url']}")
        print(f"  Origin URL  : {res['origin_url'] or '(fail-closed: empty)'}")
        print(f"  HTTP Verify : {res['verify_status']}")
        print(f"  Verify Body : {res['verify_body']}")
    except Exception as exc:
        print(f"Error deploying staging worker: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
