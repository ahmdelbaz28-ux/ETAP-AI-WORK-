#!/usr/bin/env python3
"""
Cloudflare Connection Test Script for AhmedETAP
Tests Cloudflare Workers, R2 Storage, and Edge Protection connectivity.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"[INFO] Loaded .env from {env_path}")
else:
    print(f"[WARN] .env not found at {env_path}")

import httpx

# Color codes
OK = "\033[92m"
FAIL = "\033[91m"
WARN = "\033[93m"
BOLD = "\033[1m"
END = "\033[0m"


def print_header(title):
    print(f"\n{'='*60}")
    print(f"{BOLD}{title}{END}")
    print(f"{'='*60}")


def test_cloudflare_api():
    """Test Cloudflare API token validity."""
    print_header("CLOUDFLARE API TOKEN TEST")

    cf_api_key = os.environ.get("CLOUDFLARE_API_KEY", "")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

    print(f"  API Key:     {cf_api_key[:16]}...{cf_api_key[-4:]}" if len(cf_api_key) > 20 else f"  API Key:     {cf_api_key or '(not set)'}")
    print(f"  Account ID:  {cf_account_id or '(not set)'}")

    if not cf_api_key:
        print(f"\n  {WARN}[WARN]{END}  CLOUDFLARE_API_KEY not set (optional — needed for Workers AI)")
        return None

    headers = {"Authorization": f"Bearer {cf_api_key}", "Content-Type": "application/json"}

    # Test 1: Token verification
    print(f"\n  --- Test 1: Token Verification ---")
    try:
        r = httpx.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                print(f"  {OK}[OK]{END}   Token is VALID")
                token_info = data.get("result", {})
                if token_info.get("status"):
                    print(f"  {OK}[OK]{END}   Status: {token_info['status']}")
                if token_info.get("expires_at"):
                    print(f"  {OK}[OK]{END}   Expires: {token_info['expires_at']}")
            else:
                print(f"  {FAIL}[FAIL]{END}  Token verification failed: {data.get('errors', [])}")
        else:
            print(f"  {FAIL}[FAIL]{END}  Token verify: HTTP {r.status_code} — {r.text[:200]}")
            return False
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Token verify failed: {e}")
        return False

    # Test 2: Account access
    if cf_account_id:
        print(f"\n  --- Test 2: Account Access ---")
        try:
            r = httpx.get(
                f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}",
                headers=headers, timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    account = data.get("result", {})
                    print(f"  {OK}[OK]{END}   Account: {account.get('name', '?')}")
                    print(f"  {OK}[OK]{END}   Account ID: {account.get('id', '?')}")
                    print(f"  {OK}[OK]{END}   Plan: {account.get('plan', {}).get('name', '?')}")
                else:
                    print(f"  {FAIL}[FAIL]{END}  Account access failed: {data.get('errors', [])}")
            else:
                print(f"  {FAIL}[FAIL]{END}  Account: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {FAIL}[FAIL]{END}  Account access failed: {e}")
    else:
        print(f"\n  {WARN}[WARN]{END}  CLOUDFLARE_ACCOUNT_ID not set")

    # Test 3: Workers list
    print(f"\n  --- Test 3: Workers List ---")
    if cf_account_id:
        try:
            r = httpx.get(
                f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/workers/scripts",
                headers=headers, timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    workers = data.get("result", [])
                    print(f"  {OK}[OK]{END}   Workers: {len(workers)}")
                    for w in workers[:5]:
                        print(f"    - {w.get('id', '?')} ({w.get('modified_on', '?')})")
                else:
                    print(f"  {FAIL}[FAIL]{END}  Workers list failed: {data.get('errors', [])}")
            else:
                print(f"  {FAIL}[FAIL]{END}  Workers: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {FAIL}[FAIL]{END}  Workers list failed: {e}")
    else:
        print(f"  {WARN}[WARN]{END}  Skipped (no account ID)")

    # Test 4: R2 buckets
    print(f"\n  --- Test 4: R2 Buckets ---")
    r2_account = os.environ.get("R2_ACCOUNT_ID", "") or cf_account_id
    if r2_account:
        try:
            r = httpx.get(
                f"https://api.cloudflare.com/client/v4/accounts/{r2_account}/r2/buckets",
                headers=headers, timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    buckets = data.get("result", [])
                    print(f"  {OK}[OK]{END}   R2 Buckets: {len(buckets)}")
                    for b in buckets:
                        print(f"    - {b.get('name', '?')} (created: {b.get('creation_date', '?')})")
                else:
                    errors = data.get("errors", [])
                    if any("not entitled" in str(e) for e in errors):
                        print(f"  {WARN}[WARN]{END}  R2 not enabled on this account (optional)")
                    else:
                        print(f"  {FAIL}[FAIL]{END}  R2 buckets: {errors}")
            else:
                print(f"  {FAIL}[FAIL]{END}  R2: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {FAIL}[FAIL]{END}  R2 buckets failed: {e}")
    else:
        print(f"  {WARN}[WARN]{END}  Skipped (no R2 account ID)")

    return True


def test_cloudflare_worker_live():
    """Test the deployed Cloudflare Worker proxy."""
    print_header("CLOUDFLARE WORKER LIVE TEST")

    origin_url = os.environ.get("VITE_API_URL", "")
    worker_names = [
        "https://ahmdelbaz28-ahmedetap-platform.hf.space",
        "https://etap.ahmed.net",
        origin_url,
    ]

    tested = set()
    for url in worker_names:
        if not url or url in tested:
            continue
        tested.add(url)
        print(f"\n  --- Testing: {url} ---")
        try:
            r = httpx.get(f"{url}/health", timeout=15, follow_redirects=True)
            if r.status_code == 200:
                try:
                    data = r.json()
                    print(f"  {OK}[OK]{END}   /health: 200 — status={data.get('status', '?')}")
                except Exception:
                    print(f"  {OK}[OK]{END}   /health: 200 — (non-JSON response)")
            else:
                print(f"  {WARN}[WARN]{END}  /health: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {FAIL}[FAIL]{END}  Connection failed: {e}")


def test_cloudflare_origin_secret():
    """Test Cloudflare origin protection configuration."""
    print_header("CLOUDFLARE ORIGIN PROTECTION CONFIG")

    origin_secret = os.environ.get("CLOUDFLARE_ORIGIN_SECRET", "")
    blocked_countries = os.environ.get("CF_BLOCKED_COUNTRIES", "")
    rate_limit = os.environ.get("CF_ORIGIN_RATE_LIMIT", "300")

    print(f"  Origin Secret:  {'SET' if origin_secret else 'NOT SET (dev mode)'}")
    print(f"  Blocked Countries: {blocked_countries or '(none)'}")
    print(f"  Rate Limit:    {rate_limit} req/min/IP")

    if origin_secret:
        print(f"  {OK}[OK]{END}   Origin verification is ENABLED")
    else:
        print(f"  {WARN}[WARN]{END}  Origin verification is DISABLED (acceptable for dev)")

    # Check if running on HF Space
    space_id = os.environ.get("SPACE_ID", "")
    if space_id:
        print(f"  {OK}[OK]{END}   Running on HF Space: {space_id} (auto-disable CF verification)")

    # Test the integration module
    try:
        from api.cloudflare_protection import is_cloudflare_enabled, get_cloudflare_metadata
        enabled = is_cloudflare_enabled()
        print(f"\n  Integration module:")
        print(f"    is_cloudflare_enabled(): {enabled}")
        print(f"  {OK}[OK]{END}   Module imported successfully")
    except ImportError:
        print(f"\n  {WARN}[WARN]{END}  api.cloudflare_protection not importable (FastAPI may not be installed)")
    except Exception as e:
        print(f"\n  {FAIL}[FAIL]{END}  Module error: {e}")


def test_r2_storage():
    """Test R2 storage configuration and connectivity."""
    print_header("CLOUDFLARE R2 STORAGE CONFIG")

    r2_account_id = os.environ.get("R2_ACCOUNT_ID", "")
    r2_access_key = os.environ.get("R2_ACCESS_KEY_ID", "")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    r2_bucket = os.environ.get("R2_BUCKET_NAME", "ahmedetap-storage")
    r2_public_url = os.environ.get("R2_PUBLIC_URL_PREFIX", "")

    print(f"  Account ID:   {r2_account_id[:16]}...{r2_account_id[-4:]}" if len(r2_account_id) > 20 else f"  Account ID:   {r2_account_id or '(not set)'}")
    print(f"  Access Key:   {r2_access_key[:16]}..." if len(r2_access_key) > 20 else f"  Access Key:   {r2_access_key or '(not set)'}")
    print(f"  Secret Key:   {'***'+r2_secret[-4:]}" if len(r2_secret) > 4 else f"  Secret Key:   {r2_secret or '(not set)'}")
    print(f"  Bucket Name:  {r2_bucket}")
    print(f"  Public URL:   {r2_public_url or '(not set)'}")

    r2_enabled = bool(r2_account_id and r2_access_key and r2_secret)
    print(f"\n  R2 Enabled:   {r2_enabled}")

    if r2_enabled:
        print(f"  {OK}[OK]{END}   All required R2 credentials are set")
    else:
        print(f"  {WARN}[WARN]{END}  R2 not fully configured (optional)")

    # Test the integration module
    try:
        from api.r2_storage import is_r2_enabled, R2_ENDPOINT_URL
        enabled = is_r2_enabled()
        print(f"\n  Integration module:")
        print(f"    is_r2_enabled(): {enabled}")
        print(f"    R2_ENDPOINT_URL:  {R2_ENDPOINT_URL or '(empty)'}")
        print(f"  {OK}[OK]{END}   Module imported successfully")
    except ImportError:
        print(f"\n  {WARN}[WARN]{END}  api.r2_storage not importable (boto3 may not be installed)")
    except Exception as e:
        print(f"\n  {FAIL}[FAIL]{END}  Module error: {e}")


def test_wrangler_config():
    """Verify wrangler.toml configuration."""
    print_header("CLOUDFLARE WRANGLER CONFIG VERIFICATION")

    for toml_file in ["cloudflare/wrangler.toml", "cloudflare/wrangler-r2.toml"]:
        fpath = Path(__file__).resolve().parent.parent / toml_file
        print(f"\n  --- {toml_file} ---")
        if fpath.exists():
            print(f"  {OK}[OK]{END}   File exists")
            content = fpath.read_text()
            # Check for account_id
            if "account_id" in content:
                print(f"  {OK}[OK]{END}   account_id is set")
            else:
                print(f"  {WARN}[WARN]{END}  account_id not found")
            # Check for origin URL
            if "ORIGIN_URL" in content:
                print(f"  {OK}[OK]{END}   ORIGIN_URL is configured")
            else:
                print(f"  {WARN}[WARN]{END}  ORIGIN_URL not found")
        else:
            print(f"  {FAIL}[FAIL]{END}  File not found")


if __name__ == "__main__":
    test_cloudflare_api()
    test_cloudflare_worker_live()
    test_cloudflare_origin_secret()
    test_r2_storage()
    test_wrangler_config()
    print_header("CLOUDFLARE TEST COMPLETE")
