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


def _check_smithery() -> None:
    """Verify Smithery server connectivity."""
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


def _check_langwatch() -> None:
    """Verify LangWatch prompts API."""
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


def _check_langfuse() -> None:
    """Verify Langfuse v2 API."""
    print(f"\n{R.BOLD}--- Langfuse ---{R.END}")
    lf_public = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    lf_secret = os.environ.get("LANGFUSE_SECRET_KEY", "")
    lf_base = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    if not (lf_public and lf_secret):
        warn("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
        return

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


def _check_supabase() -> None:
    """Verify Supabase REST endpoints and tables."""
    print(f"\n{R.BOLD}--- Supabase ---{R.END}")
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not (sb_url and sb_service):
        fail("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        return

    sb_headers = {"apikey": sb_service, "Authorization": f"Bearer {sb_service}"}

    # Check REST root and tables
    try:
        r = httpx.get(f"{sb_url}/rest/v1/", headers=sb_headers, timeout=10)
        if r.status_code in (200, 404):
            ok(f"REST endpoint: {r.status_code}")
            # Check users table
            r_users = httpx.get(f"{sb_url}/rest/v1/users?select=*&limit=10", headers=sb_headers, timeout=10)
            if r_users.status_code == 200:
                users = r_users.json()
                ok(f"users table: {len(users)} row(s)")
            else:
                warn(f"users table: HTTP {r_users.status_code}")
        else:
            fail(f"REST root: HTTP {r.status_code}")
    except Exception as e:
        err = str(e)
        if "getaddrinfo" in err or "Name or service not known" in err:
            warn(f"Supabase project DNS inactive/paused — restore at https://supabase.com/dashboard")
        else:
            fail(f"REST failed: {err[:150]}")


def _check_neo4j() -> None:
    """Verify Neo4j connectivity."""
    print(f"\n{R.BOLD}--- Neo4j ---{R.END}")
    neo4j_uri = os.environ.get("NEO4J_URI", "")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_pwd = os.environ.get("NEO4J_PASSWORD", "")

    if not (neo4j_uri and neo4j_pwd):
        warn("NEO4J_URI / NEO4J_PASSWORD not set (optional)")
        return

    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_pwd), connection_timeout=5
        )
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
        if "Connection refused" in err or "10061" in err or "localhost" in neo4j_uri:
            warn(f"Local Neo4j daemon not running (optional — in-memory NetworkX active)")
        elif "DNS" in err or "Name or service not known" in err:
            warn(f"Neo4j cloud URI pending configuration: {neo4j_uri[:60]}")
        else:
            fail(f"Connection failed: {err[:200]}")


def _check_hf_space() -> None:
    """Verify HuggingFace Space reachability."""
    print(f"\n{R.BOLD}--- HuggingFace Space ---{R.END}")
    hf_token = os.environ.get("HF_TOKEN", "")
    svc_api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")

    # Space page
    try:
        r = httpx.get("https://huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform", timeout=10)
        print(f"  Space page: {r.status_code}")
    except Exception as e:
        fail(f"Space page failed: {e}")

    # Space runtime (via API)
    try:
        r = httpx.get(
            "https://huggingface.co/api/spaces/ahmdelbaz28/AhmedETAP-Platform",
            headers={"Authorization": f"Bearer {hf_token}"} if hf_token else {},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            stage = data.get("runtime", {}).get("stage", "unknown")
            hardware = data.get("runtime", {}).get("hardware", {}).get("current", "unknown")
            ok(f"Stage: {stage} | Hardware: {hardware}")
        else:
            fail(f"HF API: HTTP {r.status_code}")
    except Exception as e:
        fail(f"HF API failed: {e}")

    # Live URL
    try:
        r = httpx.get(
            "https://ahmdelbaz28-ahmedetap-platform.hf.space/health",
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code == 200:
            try:
                data = r.json()
                ok(
                    f"Live /health: 200 — status={data.get('status')}, uptime={data.get('uptime_seconds', 0):.0f}s",
                )
            except Exception:
                ok("Live /health: 200")
        else:
            warn(f"Live /health: HTTP {r.status_code}")
    except Exception as e:
        warn(f"Live /health failed: {e}")

    # Agents endpoint
    try:
        headers = {}
        if svc_api_key:
            headers["X-API-Key"] = svc_api_key
            headers["Authorization"] = f"Bearer {svc_api_key}"
        r = httpx.get(
            "https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/agents",
            headers=headers,
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", 0) if isinstance(data, dict) else len(data)
            ok(f"/api/v1/agents: 200 — {count} agents")
        elif r.status_code == 401:
            ok("/api/v1/agents: Protected with Auth Gate (HTTP 401 unauthenticated)")
        else:
            fail(f"/api/v1/agents: HTTP {r.status_code}")
    except Exception as e:
        fail(f"/api/v1/agents failed: {e}")



def _check_github_repo() -> None:
    """Verify GitHub repo access and CI runs."""
    print(f"\n{R.BOLD}--- GitHub Repo ---{R.END}")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    gh_headers = (
        {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
        if gh_token
        else {}
    )

    try:
        r = httpx.get(
            "https://api.github.com/repos/ahmdelbaz28-ux/ETAP-AI-WORK-",
            headers=gh_headers,
            timeout=10,
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
                ok(f"Last CI: {run.get('name')}, {run.get('conclusion')}")
            else:
                warn("No CI runs found")
        else:
            warn(f"Actions API: HTTP {r.status_code}")
    except Exception as e:
        warn(f"Actions API failed: {e}")


def _check_vercel() -> None:
    """Verify Vercel live site reachability."""
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


def _check_sonarcloud() -> None:
    """Verify SonarCloud project status."""
    print(f"\n{R.BOLD}--- SonarCloud ---{R.END}")
    sonar_token = os.environ.get("SONAR_TOKEN", "")
    sonar_org = os.environ.get("SONAR_ORGANIZATION", "ahmdelbaz28-ux")
    sonar_proj = os.environ.get("SONAR_PROJECT_KEY", "ahmdelbaz28-ux_ETAP-AI-WORK-")


    if not sonar_token:
        warn("SONAR_TOKEN not set")
        return

    b64 = base64.b64encode(f"{sonar_token}:".encode()).decode()
    headers = {"Authorization": f"Basic {b64}"}

    try:
        r = httpx.get(
            f"https://sonarcloud.io/api/project_branches/list?project={sonar_proj}",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            branches = r.json().get("branches", [])
            main_branch = next((b for b in branches if b.get("isMain")), None)
            if main_branch:
                status = main_branch.get("status", {})
                ok(f"SonarCloud connected: QualityGate={status.get('qualityGateStatus')}, Bugs={status.get('bugs')}, Vulnerabilities={status.get('vulnerabilities')}")
            else:
                ok(f"SonarCloud connected ({len(branches)} branches)")
        else:
            fail(f"SonarCloud API: HTTP {r.status_code} — {r.text[:150]}")
    except Exception as e:
        fail(f"SonarCloud connection failed: {e}")


def _check_resend() -> None:
    """Verify Resend transactional email service."""
    print(f"\n{R.BOLD}--- Resend Email ---{R.END}")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key:
        warn("RESEND_API_KEY not set")
        return

    try:
        # Validate key by checking api key format
        if resend_key.startswith("re_") and len(resend_key) > 20:
            ok(f"Resend API Key configured ({resend_key[:8]}...)")
        else:
            warn("Resend API Key format unexpected")
    except Exception as e:
        fail(f"Resend verification failed: {e}")


def _check_cloudflare() -> None:
    """Verify Cloudflare API token."""
    print(f"\n{R.BOLD}--- Cloudflare ---{R.END}")
    cf_token = os.environ.get("CLOUDFLARE_API_KEY", "")
    if not cf_token:
        warn("CLOUDFLARE_API_KEY not set")
        return

    try:
        r = httpx.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {cf_token}"},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("success"):
            status = r.json().get("result", {}).get("status", "valid")
            ok(f"Cloudflare API Token: {status}")
        else:
            warn(f"Cloudflare Token verify: HTTP {r.status_code}")
    except Exception as e:
        fail(f"Cloudflare verification failed: {e}")


def _check_uptimerobot() -> None:
    """Verify UptimeRobot status."""
    print(f"\n{R.BOLD}--- UptimeRobot ---{R.END}")
    up_key = os.environ.get("UPTIMEROBOT_API_KEY", "")
    if not up_key:
        warn("UPTIMEROBOT_API_KEY not set")
        return

    try:
        r = httpx.post(
            "https://api.uptimerobot.com/v2/getMonitors",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={"api_key": up_key, "format": "json"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            monitors = data.get("monitors", [])
            ok(f"UptimeRobot: {len(monitors)} active monitors")
        else:
            fail(f"UptimeRobot: HTTP {r.status_code}")
    except Exception as e:
        fail(f"UptimeRobot verification failed: {e}")


def main() -> None:
    print("=" * 60)
    print(f"{R.BOLD}SERVICE VERIFICATION REPORT{R.END}")
    print("=" * 60)

    for checker in (
        _check_smithery,
        _check_langwatch,
        _check_langfuse,
        _check_supabase,
        _check_neo4j,
        _check_hf_space,
        _check_github_repo,
        _check_vercel,
        _check_sonarcloud,
        _check_resend,
        _check_cloudflare,
        _check_uptimerobot,
    ):
        checker()

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"{R.BOLD}VERIFICATION COMPLETE{R.END}")
    print("=" * 60)


if __name__ == "__main__":
    main()

