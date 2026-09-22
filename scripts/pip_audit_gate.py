#!/usr/bin/env python3
"""
scripts/pip_audit_gate.py — Blocking dependency security audit gate.

Validates all accepted vulnerabilities in .pip-audit-baseline.json for expiration,
runs pip-audit against requirements.txt, and blocks if any unaccepted or expired
vulnerability is found.
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
    req_file = repo_root / "requirements.txt"

    if not baseline_path.exists():
        sys.stderr.write(f"::error::Baseline file not found: {baseline_path}\n")
        return 1

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    today = datetime.date.today()
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
                sys.stdout.write(f"  [ACCEPTED] {vid} ({item.get('package')} - {item.get('severity')}): valid for {days_left} more days\n")
                ignore_args.extend(["--ignore-vuln", vid])
        else:
            sys.stderr.write(f"::error::Accepted vulnerability {vid} has no expires_at date!\n")
            has_expired = True

    if has_expired:
        sys.stderr.write("\n[BLOCKED] One or more baseline vulnerabilities have expired or missing expiry dates.\n")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--requirement",
        str(req_file),
        "--desc",
    ] + ignore_args

    sys.stdout.write(f"\nRunning command: pip-audit -r requirements.txt {' '.join(ignore_args)}\n\n")
    res = subprocess.run(cmd, cwd=repo_root, check=False)  # nosec B603 # nosemgrep

    if res.returncode != 0:
        sys.stderr.write("\n[BLOCKED] pip-audit found unaccepted vulnerabilities in dependencies.\n")
        return res.returncode

    sys.stdout.write("\n[OK] pip-audit dependency audit gate PASSED with zero unaccepted vulnerabilities.\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
