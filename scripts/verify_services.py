#!/usr/bin/env python3
"""Verify all external service connections.

Updated version (2026-07):
  - Added Langfuse integration (v2 API)
  - Added Supabase tables + admin user check
  - Added Neo4j connectivity test
  - Added HF Space runtime + live endpoints
  - Uses authenticated GitHub API
  - Color-coded output
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx

# Load .env if available
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass


class R:
    OK = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    INFO = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {R.OK}[OK]{R.END}   {msg}")


def fail(msg: str) -> None:
    print(f"  {R.FAIL}[FAIL]{R.END} {msg}")


def warn(msg: str) -> None:
    print(f"  {R.WARN}[WARN]{R.END} {msg}")


def info(msg: str) -> None:
    print(f"  {R.INFO}[INFO]{R.END} {msg}")


print("=" * 60)
print(f"{R.BOLD}SERVICE VERIFICATION REPORT{R.END}")
print("=" * 60)

# ─── 1. Smithery ──────────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- Smithery ---{R.END}")
s_api_key = os.environ.get("SMITHERY_API_KEY", "")
s_headers = {"Authorization": f"Bearer {s_api_key}", "User-Agent": "AhmedETAP/1.0.0"}

try:
    r = httpx.get("https://api.smithery.ai/servers", headers=s_headers, timeout=10)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        servers = r.json().get("servers", []) if isinstance(r.json(), dict) else r.json()
        ok(f"Available servers: {len(servers)}")
        for s in servers[:5]:
            info(f"  - {s.get('displayName', '?')} ({s.get('qualifiedName', '?')})")
        if len(servers) > 5:
            info(f"  ... and {len(servers) - 5} more")
    else:
        fail(f"Error: {r.text[:200]}")
except Exception as e:
    fail(f"Connection failed: {e}")

# ─── 2. LangWatch ─────────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- LangWatch ---{R.END}")
l_api_key = os.environ.get("LANGWATCH_API_KEY", "")
l_headers = {"Authorization": f"Bearer {l_api_key}", "Content-Type": "application/json"}

try:
    r = httpx.get("https://app.langwatch.ai/api/prompts", headers=l_headers, timeout=10)
    print(f"  Prompts API: {r.status_code}")
    if r.status_code == 200:
        prompts = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        warn(f"Registered prompts: {len(prompts)} (free plan limit = 3)")
        for p in prompts:
            if isinstance(p, dict):
                info(f"  - {p.get('handle', '?')} (id: {p.get('id', '?')[:20]}...)")
    else:
        fail(f"Error: {r.text[:200]}")
except Exception as e:
    fail(f"Connection failed: {e}")

# ─── 3. Langfuse (NEW) ────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- Langfuse ---{R.END}")
lf_public = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
lf_secret = os.environ.get("LANGFUSE_SECRET_KEY", "")
lf_base = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

if lf_public and lf_secret:
    b64 = base64.b64encode(f"{lf_public}:{lf_secret}".encode()).decode()
    lf_headers = {"Authorization": f"Basic {b64}"}

    try:
        r = httpx.get(f"{lf_base}/api/public/health", headers=lf_headers, timeout=10)
        if r.status_code == 200:
            ok("Health endpoint: 200")
        else:
            fail(f"Health: HTTP {r.status_code}")
    except Exception as e:
        fail(f"Health failed: {e}")

    try:
        r = httpx.get(
            f"{lf_base}/api/public/v2/prompts",
            headers=lf_headers,
            params={"page": 1, "limit": 100},
            timeout=15,
        )
        if r.status_code == 200:
            prompts = r.json().get("data", [])
            ok(f"Prompts (v2 API): {len(prompts)} prompts")
            production = [p for p in prompts if "production" in (p.get("labels") or [])]
            ok(f"  - Production-labeled: {len(production)}")
            for p in prompts[:5]:
                info(f"  - {p.get('name')} ({p.get('labels', [])})")
            if len(prompts) > 5:
                info(f"  ... and {len(prompts) - 5} more")
        else:
            fail(f"Prompts v2: HTTP {r.status_code}")
    except Exception as e:
        fail(f"Prompts v2 failed: {e}")
else:
    warn("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")

# ─── 4. Supabase (NEW) ────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- Supabase ---{R.END}")
sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
sb_service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if sb_url and sb_service:
    sb_headers = {"apikey": sb_service, "Authorization": f"Bearer {sb_service}"}

    # Health check on REST root
    try:
        r = httpx.get(f"{sb_url}/rest/v1/", headers=sb_headers, timeout=10)
        if r.status_code in (200, 404):
            ok(f"REST endpoint: {r.status_code} (404 on root is normal)")
        else:
            fail(f"REST root: HTTP {r.status_code}")
    except Exception as e:
        fail(f"REST failed: {e}")

    # Check users table
    try:
        r = httpx.get(f"{sb_url}/rest/v1/users?select=*&limit=10", headers=sb_headers, timeout=10)
        if r.status_code == 200:
            users = r.json()
            ok(f"users table: {len(users)} row(s)")
            admins = [u for u in users if u.get("role") == "admin"]
            if admins:
                ok(f"  - admin user(s): {len(admins)}")
            else:
                warn("  - no admin user found (run scripts/etap_fix_supabase_init.py)")
        else:
            fail(f"users table: HTTP {r.status_code}")
    except Exception as e:
        fail(f"users table query failed: {e}")

    # Check projects table
    try:
        r = httpx.get(
            f"{sb_url}/rest/v1/projects?select=*&limit=10", headers=sb_headers, timeout=10
        )
        if r.status_code == 200:
            projects = r.json()
            ok(f"projects table: {len(projects)} row(s)")
        else:
            fail(f"projects table: HTTP {r.status_code}")
    except Exception as e:
        fail(f"projects table query failed: {e}")
else:
    fail("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")

# ─── 5. Neo4j (NEW) ───────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- Neo4j ---{R.END}")
neo4j_uri = os.environ.get("NEO4J_URI", "")
neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
neo4j_pwd = os.environ.get("NEO4J_PASSWORD", "")

if neo4j_uri and neo4j_pwd:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pwd))
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok").single()
            if result and result["ok"] == 1:
                ok(f"Neo4j query OK (uri: {neo4j_uri[:50]}...)")
            else:
                fail("Neo4j query returned unexpected result")
        driver.close()
    except ImportError:
        warn("neo4j package not installed — skipping")
    except Exception as e:
        err = str(e)
        if "DNS" in err or "Name or service not known" in err:
            fail(f"DNS resolution failed — URI is incorrect: {neo4j_uri[:60]}")
        else:
            fail(f"Connection failed: {err[:200]}")
else:
    warn("NEO4J_URI / NEO4J_PASSWORD not set (optional)")

# ─── 6. HuggingFace Space ─────────────────────────────────────────────────
print(f"\n{R.BOLD}--- HuggingFace Space ---{R.END}")
hf_token = os.environ.get("HF_TOKEN", "")

# Space page
try:
    r = httpx.get("https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP", timeout=10)
    print(f"  Space page: {r.status_code}")
except Exception as e:
    fail(f"Space page failed: {e}")

# Space runtime (via API)
try:
    r = httpx.get(
        "https://huggingface.co/api/spaces/ahmdelbaz28/AHMEDETAP",
        headers={"Authorization": f"Bearer {hf_token}"} if hf_token else {},
        timeout=10,
    )
    if r.status_code == 200:
        data = r.json()
        stage = data.get("runtime", {}).get("stage", "unknown")
        hardware = data.get("runtime", {}).get("hardware", {}).get("current", "unknown")
        ok(f"Stage: {stage} | hardware: {hardware}")
    else:
        fail(f"HF API: HTTP {r.status_code}")
except Exception as e:
    fail(f"HF API failed: {e}")

# Live URL
try:
    r = httpx.get(
        "https://ahmdelbaz28-ahmedetap.hf.space/health", timeout=15, follow_redirects=True
    )
    if r.status_code == 200:
        try:
            data = r.json()
            ok(
                f"Live /health: 200 — status={data.get('status')}, uptime={data.get('uptime_seconds', 0):.0f}s"
            )
        except Exception:
            ok("Live /health: 200")
    else:
        warn(f"Live /health: HTTP {r.status_code}")
except Exception as e:
    warn(f"Live /health failed: {e}")

# Agents endpoint
try:
    r = httpx.get(
        "https://ahmdelbaz28-ahmedetap.hf.space/api/v1/agents", timeout=15, follow_redirects=True
    )
    if r.status_code == 200:
        data = r.json()
        count = data.get("count", 0) if isinstance(data, dict) else len(data)
        ok(f"/api/v1/agents: 200 — {count} agents")
    else:
        fail(f"/api/v1/agents: HTTP {r.status_code}")
except Exception as e:
    fail(f"/api/v1/agents failed: {e}")

# ─── 7. GitHub Repo ───────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- GitHub Repo ---{R.END}")
gh_token = os.environ.get("GITHUB_TOKEN", "")
gh_headers = (
    {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
    if gh_token
    else {}
)

try:
    r = httpx.get(
        "https://api.github.com/repos/ahmdelbaz28-ux/ETAP-AI-WORK-", headers=gh_headers, timeout=10
    )
    print(f"  Repo API: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        ok(f"Name: {data.get('full_name', '?')}")
        ok(f"Default branch: {data.get('default_branch', '?')}")
        ok(f"Last push: {data.get('pushed_at', '?')}")
    else:
        fail(f"Error: {r.text[:200]}")
except Exception as e:
    fail(f"Connection failed: {e}")

# Latest CI run
try:
    r = httpx.get(
        "https://api.github.com/repos/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/runs?per_page=1",
        headers=gh_headers,
        timeout=10,
    )
    if r.status_code == 200:
        runs = r.json().get("workflow_runs", [])
        if runs:
            run = runs[0]
            ok(f"Last CI: {run.get('name')} | {run.get('conclusion')}")
        else:
            warn("No CI runs found")
    else:
        warn(f"Actions API: HTTP {r.status_code}")
except Exception as e:
    warn(f"Actions API failed: {e}")

# ─── 8. Vercel ────────────────────────────────────────────────────────────
print(f"\n{R.BOLD}--- Vercel ---{R.END}")
try:
    r = httpx.get("https://etap-ai-work.vercel.app/", timeout=10, follow_redirects=True)
    print(f"  Live site: {r.status_code}")
    if r.status_code == 200:
        ok("Vercel live site reachable")
    else:
        fail(f"HTTP {r.status_code}")
except Exception as e:
    fail(f"Connection failed: {e}")

# ─── Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"{R.BOLD}VERIFICATION COMPLETE{R.END}")
print("=" * 60)
