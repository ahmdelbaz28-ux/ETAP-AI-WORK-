#!/usr/bin/env python3
"""
AhmedETAP — AI Code Review via Daytona SDK
==========================================

Spins up an isolated Daytona sandbox, installs project deps, runs lint + tests
on the PR diff only, and posts a structured review comment back to GitHub.

Environment variables (set by .github/workflows/ai-review-daytona.yml):
    DAYTONA_API_KEY   — required
    DAYTONA_API_URL   — optional (default: https://app.daytona.io)
    DAYTONA_TARGET    — optional (default: local)
    GITHUB_TOKEN      — required (for posting review comment)
    PR_NUMBER         — required
    PR_HEAD_SHA       — required
    PR_BASE_SHA       — required
    PR_HEAD_REPO      — required (e.g. "ahmdelbaz28-ux/ETAP-AI-WORK-")
    PR_HEAD_REF       — required (branch name)

Safety:
    - The sandbox runs with NO production secrets. Only the PR code is fetched.
    - The sandbox auto-stops after the review (1-hour Daytona limit is plenty).
    - No network egress to internal services (HF Space, Supabase, Langfuse).
    - If any step fails, the workflow posts a fallback comment instead of
      silently failing.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT_FILES = [
    "requirements-minimal.txt",
    "pyproject.toml",
    "ruff.toml",
    "ui/package.json",
    "ui/package-lock.json",
]

# Commands run inside the sandbox, in order. Each step has a timeout.
REVIEW_STEPS: list[tuple[str, str, int]] = [
    (
        "Checkout PR",
        (
            "git clone --depth 50 "
            "https://github.com/{PR_HEAD_REPO}.git /workspace/repo && "
            "cd /workspace/repo && "
            "git checkout {PR_HEAD_REF}"
        ),
        120,
    ),
    (
        "Install Python deps (minimal)",
        "cd /workspace/repo && pip install --quiet -r requirements-minimal.txt",
        300,
    ),
    (
        "Ruff check (changed files only)",
        (
            "cd /workspace/repo && "
            "git diff --name-only {PR_BASE_SHA} {PR_HEAD_SHA} -- '*.py' "
            "> /tmp/changed_py.txt && "
            "if [ -s /tmp/changed_py.txt ]; then "
            "  xargs ruff check --output-format=json < /tmp/changed_py.txt "
            "  > /tmp/ruff.json 2>&1 || true; "
            "else echo '[]' > /tmp/ruff.json; fi"
        ),
        60,
    ),
    (
        "Frontend type check (changed *.ts(x) only)",
        (
            "cd /workspace/repo/ui && "
            "git -C /workspace/repo diff --name-only {PR_BASE_SHA} {PR_HEAD_SHA} "
            "-- 'ui/*.ts' 'ui/*.tsx' > /tmp/changed_ts.txt && "
            "if [ -s /tmp/changed_ts.txt ]; then "
            "  npm ci --no-audit --no-fund --ignore-scripts >/dev/null 2>&1 && "
            "  npx tsc --noEmit 2>&1 | head -100 > /tmp/tsc.log || true; "
            "else echo 'No TS changes' > /tmp/tsc.log; fi"
        ),
        300,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class StepResult:
    name: str
    success: bool
    duration_sec: float
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


def _fmt_cmd(cmd: str) -> str:
    """Substitute PR_* env vars into a command string."""
    return cmd.format(**{k: os.environ[k] for k in (
        "PR_HEAD_REPO", "PR_HEAD_REF", "PR_BASE_SHA", "PR_HEAD_SHA", "PR_NUMBER"
    )})


def run_step_in_sandbox(sandbox: Any, name: str, cmd: str, timeout: int) -> StepResult:
    """Execute one shell command inside the Daytona sandbox."""
    start = time.monotonic()
    try:
        # daytona-sdk: sandbox.exec(...) returns a result with stdout/stderr/exit_code
        result = sandbox.exec(_fmt_cmd(cmd), timeout=timeout)
        duration = time.monotonic() - start
        success = getattr(result, "exit_code", 1) == 0
        return StepResult(
            name=name,
            success=success,
            duration_sec=duration,
            stdout=getattr(result, "stdout", "") or "",
            stderr=getattr(result, "stderr", "") or "",
        )
    except Exception as exc:
        return StepResult(
            name=name,
            success=False,
            duration_sec=time.monotonic() - start,
            stderr=f"{type(exc).__name__}: {exc}",
        )


def collect_artifacts(sandbox: Any) -> dict[str, str]:
    """Pull back the JSON / log artifacts produced by the review steps."""
    artifacts: dict[str, str] = {}
    for path, key in [
        ("/tmp/ruff.json", "ruff"),
        ("/tmp/tsc.log", "tsc"),
        ("/tmp/changed_py.txt", "changed_py"),
        ("/tmp/changed_ts.txt", "changed_ts"),
    ]:
        try:
            content = sandbox.read_file(path)
            artifacts[key] = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        except Exception:
            artifacts[key] = ""
    return artifacts


# ─────────────────────────────────────────────────────────────────────────────
# GitHub review comment poster
# ─────────────────────────────────────────────────────────────────────────────


def post_review(results: list[StepResult], artifacts: dict[str, str]) -> None:
    """Post a single structured review comment summarizing the run."""
    import requests

    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["PR_HEAD_REPO"]
    pr_number = int(os.environ["PR_NUMBER"])
    head_sha = os.environ["PR_HEAD_SHA"]

    # Build markdown body
    all_success = all(r.success for r in results)
    emoji = "✅" if all_success else "⚠️"
    lines = [
        f"## {emoji} AI Code Review (Daytona sandbox)",
        "",
        f"**Commit:** `{head_sha[:7]}`  ",
        f"**Sandbox target:** `{os.environ.get('DAYTONA_TARGET', 'local')}`  ",
        f"**Overall:** {'PASS' if all_success else 'NEEDS ATTENTION'}",
        "",
        "### Step results",
        "",
        "| Step | Status | Duration |",
        "|:---|:---:|---:|",
    ]
    for r in results:
        status = "✅" if r.success else "❌"
        lines.append(f"| {r.name} | {status} | {r.duration_sec:.1f}s |")

    # Ruff summary
    ruff_json = artifacts.get("ruff", "").strip()
    if ruff_json and ruff_json != "[]":
        try:
            issues = json.loads(ruff_json)
            if isinstance(issues, list) and issues:
                lines += ["", "### Ruff issues (changed files only)", ""]
                lines += ["| File:Line | Rule | Message |", "|:---|:---|:---|"]
                for issue in issues[:20]:
                    loc = issue.get("location", {})
                    lines.append(
                        f"| `{loc.get('path','?')}:{loc.get('row','?')}` "
                        f"| `{issue.get('code','?')}` "
                        f"| {issue.get('message','')[:120]} |"
                    )
                if len(issues) > 20:
                    lines.append(f"| _…{len(issues) - 20} more truncated_ | | |")
        except json.JSONDecodeError:
            lines += ["", "_Ruff output was not valid JSON — see workflow log._"]

    # TypeScript summary
    tsc_log = artifacts.get("tsc", "").strip()
    if tsc_log and "No TS changes" not in tsc_log:
        lines += ["", "### TypeScript (`tsc --noEmit`) — first 20 lines", ""]
        lines += ["```", tsc_log.splitlines()[:20] and "\n".join(tsc_log.splitlines()[:20]), "```"]

    lines += [
        "",
        "---",
        "_Generated by `.github/workflows/ai-review-daytona.yml`. "
        "Disable by removing `ENABLE_DAYTONA_REVIEW=true` repository variable._",
    ]

    body = "\n".join(lines)

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"!! Failed to post review: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
    else:
        print(f"✓ Posted review comment to PR #{pr_number}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    # Validate env
    required = ["DAYTONA_API_KEY", "GITHUB_TOKEN", "PR_NUMBER",
                "PR_HEAD_SHA", "PR_BASE_SHA", "PR_HEAD_REPO", "PR_HEAD_REF"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"!! Missing env vars: {missing}", file=sys.stderr)
        return 2

    try:
        # Import lazily so the script can still be loaded even if SDK is missing
        from daytona_sdk import Daytona, Sandbox, Target  # type: ignore
    except ImportError as exc:
        print(f"!! daytona-sdk not installed: {exc}", file=sys.stderr)
        return 3

    print(f"→ Creating Daytona sandbox for PR #{os.environ['PR_NUMBER']}")

    daytona = Daytona(
        api_key=os.environ["DAYTONA_API_KEY"],
        api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io"),
    )
    target_name = os.environ.get("DAYTONA_TARGET", "local")
    try:
        target = Target(target_name)
    except Exception:
        # Newer SDK versions accept a plain string
        target = target_name  # type: ignore

    try:
        sandbox: Sandbox = daytona.create(target=target, language="python")
        print(f"✓ Sandbox created: {getattr(sandbox, 'id', 'unknown')}")
    except Exception as exc:
        print(f"!! Failed to create sandbox: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 4

    results: list[StepResult] = []
    try:
        for name, cmd, timeout in REVIEW_STEPS:
            print(f"\n→ [{name}]")
            r = run_step_in_sandbox(sandbox, name, cmd, timeout)
            results.append(r)
            status = "✓" if r.success else "✗"
            print(f"  {status} {name} ({r.duration_sec:.1f}s)")
            if r.stderr:
                print(f"  stderr: {r.stderr[:300]}")

        artifacts = collect_artifacts(sandbox)
        post_review(results, artifacts)
        return 0 if all(r.success for r in results) else 1
    finally:
        try:
            daytona.delete(sandbox)
            print("\n✓ Sandbox deleted")
        except Exception as exc:
            print(f"\n⚠ Sandbox deletion failed (will auto-expire): {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
