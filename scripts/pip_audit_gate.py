#!/usr/bin/env python3
"""
scripts/pip_audit_gate.py — Blocking dependency security audit gate.

Validates all accepted vulnerabilities in .pip-audit-baseline.json for expiration,
checks validity window consumption (>=80% warning alert), runs pip-audit against
requirements.txt, hf-space/requirements.hf.txt, and requirements-prod.txt, and
blocks if any unaccepted or expired vulnerability is found.
"""

from __future__ import annotations

import datetime
import json
import subprocess  # nosec B404 # nosemgrep  # subprocess used exclusively for pinned internal pip-audit CLI invocation
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    baseline_path = repo_root / ".pip-audit-baseline.json"
    req_files = [
        repo_root / "requirements.txt",
        repo_root / "hf-space" / "requirements.hf.txt",
        repo_root / "requirements-prod.txt",
    ]

    if not baseline_path.exists():
        sys.stderr.write(f"::error::Baseline file not found: {baseline_path}\n")
        return 1

    for rf in req_files:
        if not rf.exists():
            sys.stderr.write(f"::error::Requirements file not found: {rf}\n")
            return 1

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    today = datetime.date.today()
    generated_at_str = baseline.get("generated_at", "2026-09-22T00:00:00Z")[:10]
    default_start_date = datetime.date.fromisoformat(generated_at_str)

    accepted_vulns = baseline.get("accepted_vulnerabilities", [])
    ignore_args = []
    has_expired = False

    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("[SECURITY] AhmedETAP Python Dependency Security Audit Gate\n")
    sys.stdout.write("=" * 60 + "\n")

    for item in accepted_vulns:
        vid = item["id"]
        expires_at_str = item.get("expires_at")
        if expires_at_str:
            expires_at = datetime.date.fromisoformat(expires_at_str)
            if expires_at < today:
                sys.stderr.write(f"::error::Accepted vulnerability {vid} ({item.get('package')}) EXPIRED on {expires_at_str}!\n")
                has_expired = True
            else:
                days_left = (expires_at - today).days
                item_start = datetime.date.fromisoformat(item["added_at"]) if "added_at" in item else default_start_date
                total_window = (expires_at - item_start).days
                elapsed = (today - item_start).days
                if total_window > 0:
                    consumed_ratio = elapsed / total_window
                    if consumed_ratio >= 0.80:
                        sys.stdout.write(
                            f"::warning::Accepted vulnerability {vid} ({item.get('package')}) has consumed "
                            f"{consumed_ratio * 100:.1f}% of its validity window ({days_left} days remaining until {expires_at_str})!\n"
                        )
                sys.stdout.write(f"  [ACCEPTED] {vid} ({item.get('package')} - {item.get('severity')}): valid for {days_left} more days\n")
                ignore_args.extend(["--ignore-vuln", vid])
        else:
            sys.stderr.write(f"::error::Accepted vulnerability {vid} has no expires_at date!\n")
            has_expired = True

    if has_expired:
        sys.stderr.write("\n[BLOCKED] One or more baseline vulnerabilities have expired or missing expiry dates.\n")
        return 1

    import time

    for rf in req_files:
        cmd = [
            sys.executable,
            "-m",
            "pip_audit",
            "--requirement",
            str(rf),
            "--vulnerability-service",
            "osv",
            "--timeout",
            "30",
            "--desc",
        ] + ignore_args

        sys.stdout.write(f"\nRunning command: pip-audit -r {rf.name} --vulnerability-service osv {' '.join(ignore_args)}\n\n")
        sys.stdout.flush()

        max_retries = 3
        res = None
        for attempt in range(1, max_retries + 1):
            res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)  # nosec B603 # nosemgrep
            sys.stdout.write(res.stdout)
            sys.stdout.flush()

            if res.returncode == 0:
                break

            stderr_lower = res.stderr.lower()
            is_infra_error = any(
                err_token in stderr_lower
                for err_token in [
                    "503",
                    "502",
                    "504",
                    "serviceerror",
                    "backend is unhealthy",
                    "connectionerror",
                    "timeout",
                    "temporarily unavailable",
                ]
            )

            if is_infra_error and attempt < max_retries:
                backoff = attempt * 5
                sys.stderr.write(
                    f"\n[WARNING] pip-audit encountered transient service/network error on attempt {attempt}/{max_retries}. Retrying in {backoff}s...\n"
                )
                sys.stderr.write(res.stderr)
                sys.stderr.flush()
                time.sleep(backoff)
            else:
                sys.stderr.write(res.stderr)
                sys.stderr.flush()
                break

        if res is None or res.returncode != 0:
            sys.stderr.write(f"\n[BLOCKED] pip-audit failed on {rf.name} (exit code {res.returncode if res else 'None'}).\n")
            return res.returncode if res else 1

    sys.stdout.write("\n[OK] pip-audit dependency audit gate PASSED with zero unaccepted vulnerabilities across all requirements files.\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
