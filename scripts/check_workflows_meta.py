#!/usr/bin/env python3
"""
scripts/check_workflows_meta.py — Authoritative GitHub Workflows Meta-CI Gate.

Enforces structural and security invariants across all GitHub Actions workflows:
1. Valid YAML syntax (fail-closed on parsing errors).
2. Explicit permissions block (at top-level or on every individual job).
3. Explicit timeout-minutes on every job (preventing runaway hanging runners).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


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
    sys.stdout.write("[META-CI] Validating GitHub Actions Workflows\n")
    sys.stdout.write(f"Found {len(workflow_files)} workflow files.\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()

    violations = []

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

    if violations:
        sys.stderr.write(f"\n[BLOCKED] Meta-CI found {len(violations)} workflow standard violation(s):\n")
        for v in violations:
            sys.stderr.write(f"  ❌ {v}\n")
        sys.stderr.flush()
        return 1

    sys.stdout.write(f"\n[OK] All {len(workflow_files)} GitHub Actions workflows comply with Meta-CI standards.\n")
    sys.stdout.write("  - YAML syntax: VALID\n")
    sys.stdout.write("  - Permissions: EXPLICIT\n")
    sys.stdout.write("  - Job timeouts: ENFORCED\n\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
