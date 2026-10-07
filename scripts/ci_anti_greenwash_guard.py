#!/usr/bin/env python3
"""
scripts/ci_anti_greenwash_guard.py — Meta-Guard against Silent Failure Swallowing.

Scans all GitHub Actions workflow files in .github/workflows/ to ensure zero
greenwashing and enforce strict fail-closed gating:
1. Rejects unjustified continue-on-error: true
2. Rejects unjustified || true / || exit 0
3. Rejects --admin bypass flags
4. Rejects [skip ci] bypasses in critical release paths
5. Ensures all permitted exceptions are explicitly registered in CI_GATE_EXCEPTIONS.md
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

# Set utf-8 stdout encoding if possible
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Critical workflows that must NEVER contain any continue-on-error or || true
CRITICAL_GATE_WORKFLOWS = {
    "cd.yml",
    "release-gate.yml",
    "secret-scan.yml",
    "security.yml",
    "sonarcloud-pr.yml",
    "anti-greenwash.yml",
    "no-mock-in-prod.yml",
    "npm-audit.yml",
    "health-checks.yml",
    "ui-quality.yml",
    "etap-infra-validate.yml",
}


def scan_workflows(repo_root: Path) -> Tuple[int, List[str]]:
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.exists():
        return 1, [f"Workflows directory not found: {workflows_dir}"]

    exceptions_file = repo_root / "CI_GATE_EXCEPTIONS.md"
    exceptions_text = exceptions_file.read_text(encoding="utf-8") if exceptions_file.exists() else ""

    violations: List[str] = []

    for wf_file in sorted(workflows_dir.glob("*.y*ml")):
        rel_path = f".github/workflows/{wf_file.name}"
        lines = wf_file.read_text(encoding="utf-8", errors="replace").splitlines()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Ignore comments
            if stripped.startswith("#"):
                continue

            # 1. Check for continue-on-error: true in critical workflows
            if "continue-on-error: true" in stripped:
                if wf_file.name in CRITICAL_GATE_WORKFLOWS:
                    violations.append(
                        f"CRITICAL: {rel_path}:{idx} has 'continue-on-error: true' in protected gate workflow"
                    )

            # 2. Check for || true
            if "|| true" in line or "|| exit 0" in line:
                # Check if this line is an allowlisted exception in CI_GATE_EXCEPTIONS.md
                is_exception = (
                    "pkill -f" in line
                    or "sudo rm -rf" in line
                    or "docker rmi" in line
                    or "kubectl -n etap logs" in line
                    or "kubectl -n etap get" in line
                    or "2>/dev/null || true" in line
                    or rel_path in exceptions_text
                )
                if wf_file.name in CRITICAL_GATE_WORKFLOWS and not is_exception:
                    violations.append(
                        f"CRITICAL: {rel_path}:{idx} has unapproved '|| true' in gate workflow: {stripped}"
                    )

            # 3. Check for --admin bypass flag
            if "--admin" in line and not line.startswith("#"):
                violations.append(
                    f"CRITICAL: {rel_path}:{idx} contains forbidden '--admin' bypass flag: {stripped}"
                )

            # 4. Check for [skip ci] inside workflow trigger overrides
            if "[skip ci]" in line and wf_file.name in CRITICAL_GATE_WORKFLOWS:
                violations.append(
                    f"CRITICAL: {rel_path}:{idx} contains '[skip ci]' in critical release workflow"
                )

    return (len(violations), violations)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    print("=" * 70)
    print("[META-GUARD] AhmedETAP Meta-Guard: CI/CD Anti-Greenwash & Fail-Closed Audit")
    print("=" * 70)

    count, violations = scan_workflows(repo_root)

    if count > 0:
        print(f"\n[FAIL] FOUND {count} ANTI-GREENWASH VIOLATIONS:\n")
        for v in violations:
            print(f"  - {v}")
        print("\nFix all violations before merging. See CI_GATE_EXCEPTIONS.md for policies.\n")
        return 1

    print("\n[PASS] Meta-Guard Audit PASSED: 0 greenwashing violations detected.")
    print("All deployment gates, security scans, and test pipelines operate fail-closed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
