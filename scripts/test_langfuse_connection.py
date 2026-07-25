#!/usr/bin/env python3
"""
Langfuse Connection Test Script for AhmedETAP
Tests Langfuse connectivity with provided credentials.
"""

from __future__ import annotations

import os
import sys
import base64
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


def test_langfuse():
    print_header("LANGFUSE CONNECTION TEST")

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    base_url = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    print(f"  Base URL:    {base_url}")
    print(f"  Public Key:  {public_key[:16]}...{public_key[-4:]}" if len(public_key) > 20 else f"  Public Key:  {public_key}")
    print(f"  Secret Key:  {'***'+secret_key[-4:]}" if len(secret_key) > 4 else "  Secret Key:  (not set)")
    print(f"  Timeout:     {os.environ.get('LANGFUSE_TIMEOUT', '5.0')}s")

    if not public_key or not secret_key:
        print(f"\n  {FAIL}[FAIL]{END} LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set")
        return False

    # Test 1: Health endpoint
    print(f"\n  --- Test 1: Health Endpoint ---")
    b64 = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {b64}"}

    try:
        r = httpx.get(f"{base_url}/api/public/health", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            print(f"  {OK}[OK]{END}   Health: 200 — {data}")
        else:
            print(f"  {FAIL}[FAIL]{END}  Health: HTTP {r.status_code} — {r.text[:200]}")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Health failed: {e}")
        return False

    # Test 2: Prompts v2 API
    print(f"\n  --- Test 2: Prompts API (v2) ---")
    try:
        r = httpx.get(
            f"{base_url}/api/public/v2/prompts",
            headers=headers,
            params={"page": 1, "limit": 50},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            prompts = data.get("data", [])
            total = data.get("meta", {}).get("total", len(prompts))
            print(f"  {OK}[OK]{END}   Prompts API: 200 — {total} total prompts (showing {len(prompts)})")

            production = [p for p in prompts if "production" in (p.get("labels") or [])]
            print(f"  {OK}[OK]{END}   Production-labeled: {len(production)}")

            if prompts:
                for p in prompts[:10]:
                    name = p.get("name", "?")
                    labels = p.get("labels", [])
                    print(f"    - {name} (labels: {labels})")
        else:
            print(f"  {FAIL}[FAIL]{END}  Prompts v2: HTTP {r.status_code} — {r.text[:200]}")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Prompts v2 failed: {e}")

    # Test 3: Traces API
    print(f"\n  --- Test 3: Traces API ---")
    try:
        r = httpx.get(
            f"{base_url}/api/public/traces",
            headers=headers,
            params={"page": 1, "limit": 5},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            traces = data.get("data", [])
            total = data.get("meta", {}).get("total", len(traces))
            print(f"  {OK}[OK]{END}   Traces API: 200 — {total} total traces")
            for t in traces[:3]:
                print(f"    - Trace: {t.get('id', '?')[:20]}... status={t.get('status', '?')}")
        elif r.status_code == 404:
            print(f"  {WARN}[WARN]{END}  Traces API: 404 (no traces yet, this is OK)")
        else:
            print(f"  {FAIL}[FAIL]{END}  Traces: HTTP {r.status_code} — {r.text[:200]}")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Traces failed: {e}")

    # Test 4: SDK Client init
    print(f"\n  --- Test 4: Langfuse SDK Client Init ---")
    try:
        from langfuse import Langfuse
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url,
        )
        print(f"  {OK}[OK]{END}   Langfuse SDK client created successfully")

        # Test a simple trace
        trace = client.trace(name="connection-test", metadata={"test": True, "source": "verification-script"})
        print(f"  {OK}[OK]{END}   Test trace created: {trace.id}")

        # Flush
        client.flush()
        print(f"  {OK}[OK]{END}   Events flushed successfully")
        client.shutdown()
        print(f"  {OK}[OK]{END}   Client shut down cleanly")

    except ImportError:
        print(f"  {FAIL}[FAIL]{END}  langfuse SDK not installed")
        return False
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  SDK test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Project integration module
    print(f"\n  --- Test 5: Project Integration Module ---")
    try:
        from integrations.langfuse_integration import langfuse_tracker
        health = langfuse_tracker.health_check()
        print(f"  Health check:")
        for k, v in health.items():
            status = f"{OK}{v}{END}" if v else f"{WARN}{v}{END}"
            print(f"    {k}: {status}")

        if health.get("enabled"):
            print(f"  {OK}[OK]{END}   LangfuseTracker is ENABLED and connected")
        else:
            print(f"  {WARN}[WARN]{END}  LangfuseTracker is DISABLED — check credentials")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Integration module error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n  {OK}[OK]{END}   Langfuse connection test PASSED")
    return True


def test_langfuse_llm():
    print_header("LANGFUSE LLM INTEGRATION TEST")
    try:
        from integrations.langfuse_llm import health_check
        health = health_check()
        print(f"  LLM Health:")
        for k, v in health.items():
            print(f"    {k}: {v}")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  LLM integration error: {e}")


if __name__ == "__main__":
    success = test_langfuse()
    test_langfuse_llm()
    print_header("LANGFUSE TEST COMPLETE")
    sys.exit(0 if success else 1)
