"""
tests/test_anti_greenwash_guard.py — Meta-Guard & Anti-Greenwashing Self-Test Suite.

Verifies Mission B2 requirement:
Ensures that the anti-greenwash meta-guard actively rejects:
1. continue-on-error in protected gate workflows
2. unapproved || true / || exit 0
3. --admin bypass flags
4. [skip ci] bypasses
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci_anti_greenwash_guard import scan_workflows


def test_meta_guard_passes_on_current_codebase():
    """Verify that current codebase has 0 greenwashing violations."""
    repo_root = Path(__file__).resolve().parent.parent
    count, violations = scan_workflows(repo_root)
    assert count == 0, f"Unexpected violations in clean codebase: {violations}"


def test_meta_guard_rejects_continue_on_error(tmp_path):
    """Verify that adding continue-on-error to a critical workflow is flagged."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)

    fake_cd = wf_dir / "cd.yml"
    fake_cd.write_text(
        """
name: CD
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: ./deploy.sh
        continue-on-error: true
""",
        encoding="utf-8",
    )

    count, violations = scan_workflows(tmp_path)
    assert count > 0
    assert any("continue-on-error: true" in v for v in violations)


def test_meta_guard_rejects_unapproved_pipe_true(tmp_path):
    """Verify that adding unapproved || true to a critical workflow is flagged."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)

    fake_cd = wf_dir / "cd.yml"
    fake_cd.write_text(
        """
name: CD
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Probe Health
        run: curl http://localhost/healthz || true
""",
        encoding="utf-8",
    )

    count, violations = scan_workflows(tmp_path)
    assert count > 0
    assert any("|| true" in v for v in violations)


def test_meta_guard_rejects_admin_flag(tmp_path):
    """Verify that adding --admin bypass flag to any workflow is flagged."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)

    fake_wf = wf_dir / "auto-merge.yml"
    fake_wf.write_text(
        """
name: Auto Merge
jobs:
  merge:
    runs-on: ubuntu-latest
    steps:
      - name: Merge PR
        run: gh pr merge --admin --auto
""",
        encoding="utf-8",
    )

    count, violations = scan_workflows(tmp_path)
    assert count > 0
    assert any("--admin" in v for v in violations)


def test_meta_guard_rejects_skip_ci_in_critical_workflow(tmp_path):
    """Verify that adding [skip ci] to a critical release workflow is flagged."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)

    fake_release = wf_dir / "release-gate.yml"
    fake_release.write_text(
        """
name: Release Gate
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - name: Tag commit [skip ci]
        run: git commit -m "chore: release [skip ci]"
""",
        encoding="utf-8",
    )

    count, violations = scan_workflows(tmp_path)
    assert count > 0
    assert any("[skip ci]" in v for v in violations)
