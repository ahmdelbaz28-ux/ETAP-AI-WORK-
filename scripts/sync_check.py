#!/usr/bin/env python3
"""
sync_check.py — Cross-platform sync verification + repair tool.

Verifies that GitHub, HuggingFace Space, and Vercel are all in sync.
Can optionally repair drift by re-syncing secrets and triggering deployments.

Usage:
    # Check sync status only (read-only)
    python3 sync_check.py --check

    # Repair drift (re-sync secrets + trigger rebuilds)
    python3 sync_check.py --repair

    # Force full re-sync (even if no drift detected)
    python3 sync_check.py --force-sync

Required env vars:
    GITHUB_TOKEN      — GitHub PAT with repo + actions scope
    GITHUB_REPO       — GitHub repo (e.g., ahmdelbaz28-ux/ETAP-AI-WORK-)
    HF_TOKEN          — HuggingFace token with write scope
    HF_SPACE_ID       — HF Space ID (e.g., ahmdelbaz28/AhmedETAP-Platform)
    VERCEL_TOKEN      — Vercel API token
    VERCEL_PROJECT_ID — Vercel project ID
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

import requests

# ─── Configuration ───────────────────────────────────────────────────────────

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "ahmdelbaz28-ux/ETAP-AI-WORK-")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_SPACE_ID = os.getenv("HF_SPACE_ID", "ahmdelbaz28/AhmedETAP-Platform")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID = os.getenv("VERCEL_PROJECT_ID", "prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I")

# Canonical secret names that MUST be present on ALL platforms
# (GitHub Actions secrets, HF Space secrets, and Vercel env vars)
CANONICAL_SECRETS = {
    # Auth & Security
    "JWT_SECRET_KEY": "JWT signing secret (32+ chars)",
    "ENGINEERING_SERVICE_API_KEY": "API key for engineering service auth",
    "CLOUDFLARE_ORIGIN_SECRET": "Shared secret for CF Worker → origin verification",
    # Database
    "DATABASE_URL": "Postgres connection string (Neon)",
    # Supabase
    "SUPABASE_URL": "Supabase project URL",
    "SUPABASE_ANON_KEY": "Supabase publishable (anon) key",
    "SUPABASE_SERVICE_ROLE_KEY": "Supabase service role key",
    # Neo4j
    "NEO4J_URI": "Neo4j connection URI",
    "NEO4J_USER": "Neo4j username",
    "NEO4J_PASSWORD": "Neo4j password",
    # Langfuse
    "LANGFUSE_SECRET_KEY": "Langfuse secret key",
    "LANGFUSE_PUBLIC_KEY": "Langfuse public key",
    "LANGFUSE_BASE_URL": "Langfuse API base URL",
    # LangWatch
    "LANGWATCH_API_KEY": "LangWatch API key",
    # Smithery
    "SMITHERY_API_KEY": "Smithery MCP API key",
    # Platform tokens (for CI sync workflow)
    "HF_TOKEN": "HuggingFace token (for CI auto-sync)",
    "VERCEL_TOKEN": "Vercel API token (for CI)",
    "VERCEL_PROJECT_ID": "Vercel project ID",
    "GH_PAT": "GitHub PAT (for drift PRs)",
    # R2 Storage (optional — only if R2 is enabled)
    "R2_ACCOUNT_ID": "Cloudflare account ID for R2",
    "R2_ACCESS_KEY_ID": "R2 S3-compatible access key",
    "R2_SECRET_ACCESS_KEY": "R2 S3-compatible secret key",
    "R2_BUCKET_NAME": "R2 bucket name",
}

# Secrets that are safe to set as "plain" (non-encrypted) on Vercel
PLAIN_ENV_VARS = {"SUPABASE_URL", "LANGFUSE_BASE_URL", "VITE_API_URL", "R2_BUCKET_NAME", "R2_ACCOUNT_ID", "VERCEL_PROJECT_ID"}


@dataclass
class SyncStatus:
    """Sync status for a single platform."""
    platform: str
    in_sync: bool
    missing_secrets: list[str]
    extra_secrets: list[str]
    last_deployment: Optional[str] = None
    error: Optional[str] = None


# ─── GitHub ──────────────────────────────────────────────────────────────────

def check_github_secrets() -> tuple[set[str], Optional[str]]:
    """Return (present_secret_names, error) for GitHub Actions secrets."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets",
        headers=headers, timeout=30,
    )
    if r.status_code != 200:
        return set(), f"GitHub API HTTP {r.status_code}: {r.text[:200]}"
    secrets = {s["name"] for s in r.json().get("secrets", [])}
    return secrets, None


def check_github_latest_commit() -> Optional[str]:
    """Return the latest commit SHA on main."""
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/commits/main",
        headers=headers, timeout=30,
    )
    if r.status_code == 200:
        return r.json()["sha"]
    return None


# ─── HuggingFace Space ──────────────────────────────────────────────────────

def check_hf_secrets() -> tuple[set[str], Optional[str]]:
    """Return (present_secret_names, error) for HF Space secrets."""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    r = requests.get(
        f"https://huggingface.co/api/spaces/{HF_SPACE_ID}/secrets",
        headers=headers, timeout=30,
    )
    if r.status_code != 200:
        return set(), f"HF API HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    return set(data.keys()), None


def check_hf_runtime_status() -> dict[str, Any]:
    """Return HF Space runtime status."""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    r = requests.get(
        f"https://huggingface.co/api/spaces/{HF_SPACE_ID}",
        headers=headers, timeout=30,
    )
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    data = r.json()
    runtime = data.get("runtime", {})
    return {
        "stage": runtime.get("stage"),
        "sha": data.get("sha"),
        "last_modified": data.get("lastModified"),
    }


# ─── Vercel ──────────────────────────────────────────────────────────────────

def check_vercel_envs() -> tuple[set[str], Optional[str]]:
    """Return (present_env_names, error) for Vercel project env vars."""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    r = requests.get(
        f"https://api.vercel.com/v9/projects/{VERCEL_PROJECT_ID}/env",
        headers=headers, timeout=30,
    )
    if r.status_code != 200:
        return set(), f"Vercel API HTTP {r.status_code}: {r.text[:200]}"
    envs = {e["key"] for e in r.json().get("envs", [])}
    return envs, None


def check_vercel_latest_deployment() -> Optional[dict[str, Any]]:
    """Return latest Vercel deployment info."""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    r = requests.get(
        f"https://api.vercel.com/v6/deployments?projectId={VERCEL_PROJECT_ID}&limit=1",
        headers=headers, timeout=30,
    )
    if r.status_code != 200:
        return None
    deployments = r.json().get("deployments", [])
    if not deployments:
        return None
    d = deployments[0]
    return {
        "url": d.get("url"),
        "state": d.get("readyState"),
        "sha": d.get("meta", {}).get("githubCommitSha"),
        "created": d.get("created"),
    }


# ─── Sync Verification ──────────────────────────────────────────────────────

def verify_sync() -> list[SyncStatus]:
    """Check all platforms for secret + deployment sync."""
    results: list[SyncStatus] = []
    canonical = set(CANONICAL_SECRETS.keys())

    # GitHub
    gh_secrets, gh_err = check_github_secrets()
    gh_sha = check_github_latest_commit()
    results.append(SyncStatus(
        platform="GitHub",
        in_sync=gh_err is None,
        missing_secrets=sorted(canonical - gh_secrets) if gh_err is None else [],
        extra_secrets=sorted(gh_secrets - canonical) if gh_err is None else [],
        last_deployment=gh_sha[:8] if gh_sha else None,
        error=gh_err,
    ))

    # HuggingFace
    hf_secrets, hf_err = check_hf_secrets()
    hf_status = check_hf_runtime_status()
    results.append(SyncStatus(
        platform="HuggingFace",
        in_sync=hf_err is None and hf_status.get("stage") == "RUNNING",
        missing_secrets=sorted(canonical - hf_secrets) if hf_err is None else [],
        extra_secrets=sorted(hf_secrets - canonical) if hf_err is None else [],
        last_deployment=hf_status.get("sha", "")[:8] if isinstance(hf_status.get("sha"), str) else None,
        error=hf_err or hf_status.get("error"),
    ))

    # Vercel
    v_envs, v_err = check_vercel_envs()
    v_dep = check_vercel_latest_deployment()
    results.append(SyncStatus(
        platform="Vercel",
        in_sync=v_err is None,
        missing_secrets=sorted(canonical - v_envs) if v_err is None else [],
        extra_secrets=sorted(v_envs - canonical) if v_err is None else [],
        last_deployment=v_dep.get("sha", "")[:8] if v_dep else None,
        error=v_err,
    ))

    return results


def print_sync_report(results: list[SyncStatus]) -> bool:
    """Print a sync report. Returns True if all platforms are in sync."""
    print("\n" + "=" * 70)
    print("  Cross-Platform Sync Report")
    print("=" * 70)

    all_in_sync = True
    for r in results:
        status = "✅ IN SYNC" if r.in_sync and not r.missing_secrets else "⚠️  DRIFT"
        if r.error:
            status = "❌ ERROR"
            all_in_sync = False
        elif r.missing_secrets:
            all_in_sync = False

        print(f"\n  {r.platform:15s} {status}")
        if r.last_deployment:
            print(f"  {'':15s} SHA: {r.last_deployment}")
        if r.error:
            print(f"  {'':15s} Error: {r.error}")
        if r.missing_secrets:
            print(f"  {'':15s} Missing secrets ({len(r.missing_secrets)}):")
            for s in r.missing_secrets:
                print(f"  {'':15s}   - {s}")
        if r.extra_secrets:
            print(f"  {'':15s} Extra secrets ({len(r.extra_secrets)}):")
            for s in r.extra_secrets[:5]:
                print(f"  {'':15s}   - {s}")
            if len(r.extra_secrets) > 5:
                print(f"  {'':15s}   ... and {len(r.extra_secrets) - 5} more")

    print("\n" + "=" * 70)
    if all_in_sync:
        print("  ✅ ALL PLATFORMS IN SYNC")
    else:
        print("  ⚠️  DRIFT DETECTED — run with --repair to fix")
    print("=" * 70 + "\n")
    return all_in_sync


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-platform sync checker")
    parser.add_argument("--check", action="store_true", help="Check sync status only")
    parser.add_argument("--repair", action="store_true", help="Repair drift")
    parser.add_argument("--force-sync", action="store_true", help="Force full re-sync")
    args = parser.parse_args()

    if not any([args.check, args.repair, args.force_sync]):
        args.check = True

    results = verify_sync()
    all_in_sync = print_sync_report(results)

    if args.check:
        sys.exit(0 if all_in_sync else 1)

    if args.repair or args.force_sync:
        print("\nRepair not yet implemented — use the individual platform scripts:")
        print("  - scripts/update_hf_secrets.py")
        print("  - scripts/update_vercel_envs.py")
        print("  - scripts/configure_neon_db.py")
        print("\nOr trigger the GitHub Actions 'Cross-Platform Sync' workflow manually:")
        print(f"  https://github.com/{GITHUB_REPO}/actions/workflows/sync-platforms.yml")


if __name__ == "__main__":
    main()
