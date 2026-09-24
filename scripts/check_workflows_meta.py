#!/usr/bin/env python3
"""
scripts/check_workflows_meta.py — Authoritative GitHub Workflows Meta-CI Gate.

Enforces structural and security invariants across all GitHub Actions workflows:
1. Valid YAML syntax (fail-closed on parsing errors).
2. Explicit permissions block (at top-level or on every individual job).
3. Explicit timeout-minutes on every job (preventing runaway hanging runners).
4. Valid branch trigger patterns (no malformed bracket suffixes like ain]).
5. Overrides consistency between package.json and pnpm-workspace.yaml (T-2.1).
6. Line count ratchet on .gitleaksignore (R-3).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


def check_overrides_consistency(repo_root: Path, violations: list[str]) -> None:
    pkg_path = repo_root / "package.json"
    ws_path = repo_root / "pnpm-workspace.yaml"

    if not pkg_path.exists() or not ws_path.exists():
        return

    try:
        with open(pkg_path, encoding="utf-8") as f:
            pkg_data = json.load(f)
        with open(ws_path, encoding="utf-8") as f:
            ws_data = yaml.safe_load(f)

        pkg_overrides = pkg_data.get("pnpm", {}).get("overrides", {})
        ws_overrides = ws_data.get("overrides", {}) if isinstance(ws_data, dict) else {}

        only_in_pkg = set(pkg_overrides.keys()) - set(ws_overrides.keys())
        only_in_ws = set(ws_overrides.keys()) - set(pkg_overrides.keys())

        if only_in_pkg:
            violations.append(
                f"Overrides drift (T-2.1): Keys in package.json (pnpm.overrides) but missing from pnpm-workspace.yaml: {sorted(only_in_pkg)}"
            )
        if only_in_ws:
            violations.append(
                f"Overrides drift (T-2.1): Keys in pnpm-workspace.yaml but missing from package.json: {sorted(only_in_ws)}"
            )

        # Check values matching (R-8)
        common_keys = sorted(set(pkg_overrides.keys()) & set(ws_overrides.keys()))
        for k in common_keys:
            pkg_val = str(pkg_overrides[k]).strip()
            ws_val = str(ws_overrides[k]).strip()
            if pkg_val != ws_val:
                violations.append(
                    f"Overrides value drift (T-2.1): Key '{k}' has mismatched versions: "
                    f"package.json='{pkg_val}' vs pnpm-workspace.yaml='{ws_val}'"
                )
    except Exception as e:
        violations.append(f"Failed to check overrides consistency: {e}")


def check_gitleaksignore_ratchet(repo_root: Path, violations: list[str]) -> None:
    gitleaksignore_path = repo_root / ".gitleaksignore"
    if not gitleaksignore_path.exists():
        return

    # Maximum allowed non-empty lines in .gitleaksignore (ratchet ceiling)
    RATCHET_CEILING = 799
    try:
        with open(gitleaksignore_path, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        count = len(lines)
        if count > RATCHET_CEILING:
            violations.append(
                f"Gitleaksignore ratchet violation (R-3): {count} entries exceeds maximum ratchet ceiling of {RATCHET_CEILING}. "
                "Do not add unapproved exemptions to .gitleaksignore."
            )
    except Exception as e:
        violations.append(f"Failed to check .gitleaksignore ratchet: {e}")


def check_release_gate_job_names(
    repo_root: Path, defined_job_names: set[str], violations: list[str]
) -> None:
    release_gate_path = repo_root / ".github" / "workflows" / "release-gate.yml"
    if not release_gate_path.exists():
        return

    try:
        content = release_gate_path.read_text(encoding="utf-8")
        m_initial = re.search(r"REQUIRED_CHECKS=\((.*?)\n\s*\)", content, re.DOTALL)
        required_checks: list[str] = []
        if m_initial:
            required_checks.extend(re.findall(r'"([^"]+)"', m_initial.group(1)))
        required_checks.extend(
            re.findall(r'REQUIRED_CHECKS\+=\("([^"]+)"\)', content)
        )

        for check in required_checks:
            if check not in defined_job_names:
                violations.append(
                    f".github/workflows/release-gate.yml: REQUIRED_CHECK '{check}' does not match "
                    "any defined workflow job name or job ID across the repository. "
                    "Ensure exact naming without emojis or case discrepancies (G-3 / N28 guard)."
                )
    except Exception as e:
        violations.append(f"Failed to check release gate job names: {e}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.exists():
        sys.stderr.write(f"::error::Workflows directory not found: {workflows_dir}\n")
        return 1

    workflow_files = sorted(
        list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    )

    if not workflow_files:
        sys.stderr.write("::error::No workflow files found to validate!\n")
        return 1

    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("[META-CI] Validating GitHub Actions Workflows & Invariants\n")
    sys.stdout.write(f"Found {len(workflow_files)} workflow files.\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()

    violations = []
    defined_job_names: set[str] = set()

    for wf_path in workflow_files:
        rel_path = wf_path.relative_to(repo_root)
        try:
            with open(wf_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            violations.append(f"{rel_path}: Invalid YAML syntax — {e}")
            continue

        if not isinstance(data, dict):
            violations.append(f"{rel_path}: Workflow root must be a YAML mapping")
            continue

        has_top_level_perms = "permissions" in data
        jobs = data.get("jobs", {})

        if not isinstance(jobs, dict) or not jobs:
            violations.append(f"{rel_path}: No valid 'jobs' block found")
            continue

        for job_name, job_data in jobs.items():
            defined_job_names.add(job_name)
            if isinstance(job_data, dict) and "name" in job_data:
                defined_job_names.add(str(job_data["name"]).strip())

            if not isinstance(job_data, dict):
                violations.append(f"{rel_path} -> job '{job_name}': Job configuration must be a mapping")
                continue

            # Check permissions
            if not has_top_level_perms and "permissions" not in job_data:
                violations.append(
                    f"{rel_path} -> job '{job_name}': Missing explicit 'permissions' block (neither top-level nor job-level specified)"
                )

            # Check timeout-minutes (skip if workflow call / reusable workflow `uses`)
            is_reusable_call = bool(job_data.get("uses") and not job_data.get("steps"))
            if not is_reusable_call and "timeout-minutes" not in job_data:
                violations.append(
                    f"{rel_path} -> job '{job_name}': Missing 'timeout-minutes'"
                )

        # Check triggers and branch names
        on_data = data.get("on") or data.get(True)
        if isinstance(on_data, dict):
            for event_name in ["push", "pull_request", "workflow_run"]:
                ev = on_data.get(event_name)
                if isinstance(ev, dict) and "branches" in ev:
                    branches = ev["branches"]
                    if isinstance(branches, str):
                        branches = [branches]
                    if isinstance(branches, list):
                        for b in branches:
                            if not isinstance(b, str):
                                continue
                            # Canonical branch pattern: alphanumeric, slashes, dashes, dots, wildcards
                            if not b or b.endswith("]") or "[" in b or not re.match(r"^[a-zA-Z0-9_./*-]+$", b):
                                violations.append(
                                    f"{rel_path} -> event '{event_name}': Invalid branch pattern '{b}'"
                                )

    # Check repository-level invariants (T-2.1, R-3, G-3)
    check_overrides_consistency(repo_root, violations)
    check_gitleaksignore_ratchet(repo_root, violations)
    check_release_gate_job_names(repo_root, defined_job_names, violations)

    if violations:
        sys.stderr.write(f"\n[BLOCKED] Meta-CI found {len(violations)} workflow standard violation(s):\n")
        for v in violations:
            sys.stderr.write(f"  ❌ {v}\n")
        sys.stderr.flush()
        return 1

    sys.stdout.write(f"\n[OK] All {len(workflow_files)} GitHub Actions workflows comply with Meta-CI standards.\n")
    sys.stdout.write("  - YAML syntax: VALID\n")
    sys.stdout.write("  - Permissions: EXPLICIT\n")
    sys.stdout.write("  - Job timeouts: ENFORCED\n")
    sys.stdout.write("  - Branch triggers: VALIDATED\n")
    sys.stdout.write("  - Overrides consistency (T-2.1): SYNCHRONIZED\n")
    sys.stdout.write("  - Gitleaksignore ratchet (R-3): ENFORCED (ceiling: 799)\n")
    sys.stdout.write("  - Release Gate job names (G-3 / N28): VERIFIED\n\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
