#!/usr/bin/env python3
"""
scripts/ci_audit_runners.py — Audit GitHub Actions workflows for unassigned runners (runner_id == 0).

Queries the GitHub Actions API for recent workflow runs and their jobs,
identifying jobs that failed with runner_id == 0 (meaning the job never acquired
a runner due to billing/spending limits or quota limits on GitHub-hosted runners).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Any, Dict, List


def _gh_api(endpoint: str) -> Any:
    """Call GitHub API via gh CLI if available, otherwise urllib with GITHUB_TOKEN."""
    if shutil.which("gh"):
        cmd = ["gh", "api", endpoint]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return json.loads(res.stdout)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def audit_workflows() -> Dict[str, Any]:
    print("=" * 70)
    print("AUDITING GITHUB ACTIONS WORKFLOW RUNS FOR UNASSIGNED RUNNERS (runner_id == 0)")
    print("=" * 70)

    try:
        runs_data = _gh_api("repos/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/runs?per_page=50")
        runs = runs_data.get("workflow_runs", [])
    except Exception as exc:
        print(f"Error fetching workflow runs: {exc}")
        return {"error": str(exc)}

    print(f"Total recent workflow runs fetched: {len(runs)}")

    unassigned_workflows: List[Dict[str, Any]] = []
    seen_workflows = set()

    for run in runs:
        wf_name = run.get("name")
        conclusion = run.get("conclusion")
        run_id = run.get("id")
        status = run.get("status")
        html_url = run.get("html_url")
        head_sha = run.get("head_sha", "")[:9]

        # Only inspect failed runs
        if conclusion != "failure":
            continue

        try:
            jobs_data = _gh_api(f"repos/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/runs/{run_id}/jobs?per_page=50")
            jobs = jobs_data.get("jobs", [])

            zero_runner_jobs = []
            for j in jobs:
                runner_id = j.get("runner_id")
                job_conclusion = j.get("conclusion")
                job_name = j.get("name")
                labels = j.get("labels", [])
                steps = j.get("steps", [])
                if (runner_id == 0 or runner_id is None) and job_conclusion == "failure" and len(steps) == 0:
                    zero_runner_jobs.append({
                        "name": job_name,
                        "labels": labels,
                        "runner_id": runner_id,
                    })

            if zero_runner_jobs and wf_name not in seen_workflows:
                seen_workflows.add(wf_name)
                unassigned_workflows.append({
                    "name": wf_name,
                    "run_id": run_id,
                    "sha": head_sha,
                    "status": status,
                    "conclusion": conclusion,
                    "url": html_url,
                    "zero_runner_jobs": zero_runner_jobs,
                })
        except Exception as err:
            print(f"Error checking jobs for run {run_id}: {err}")
            continue

    print(f"\nUnique workflows with failing jobs due to unassigned runner (runner_id == 0): {len(unassigned_workflows)}")
    for item in unassigned_workflows:
        print(f"\n[UNASSIGNED RUNNER] Workflow: {item['name']} (commit: {item['sha']})")
        print(f"  Run ID: {item['run_id']} | Status: {item['status']} | URL: {item['url']}")
        for j in item["zero_runner_jobs"]:
            print(f"  - Job: '{j['name']}' | Runner ID: {j['runner_id']} | Labels: {j['labels']}")

    print("\n" + "=" * 70)
    print("AUDIT FINDINGS & ROOT CAUSE:")
    print("  When runner_id == 0, steps == [], and conclusion == failure:")
    print("  The job was rejected by GitHub before acquiring a runner.")
    print("  Primary causes:")
    print("  1. GitHub Actions spending limit ($0 limit reached or payment method needed)")
    print("  2. Self-hosted runner label requested but no matching runner online")
    print("  3. Workflow triggered concurrently exhausting repository concurrency limits")
    print("=" * 70)

    return {
        "unassigned_workflows": unassigned_workflows,
    }


if __name__ == "__main__":
    audit_workflows()
