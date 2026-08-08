"""
Unit tests for life_safety kill-switch functions (SonarCloud new_coverage).

Tests cover activate_kill_switch, deactivate_kill_switch, and
is_kill_switch_active — the public API of the kill-switch module.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add repo root to sys.path so we can import life_safety
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def tmp_kill_switch_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect KILL_SWITCH_PATH and _CUA_AUDIT_DIR to a temp directory."""
    tmp_kill = tmp_path / "kill_switch.json"
    tmp_audit = tmp_path / "cua_audit"
    tmp_audit.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Patch BEFORE importing life_safety so the module-level _CUA_AUDIT_DIR
    # gets our temp path. But life_safety is likely already imported by
    # other tests, so we patch the module attribute directly.
    import agents.life_safety as ls

    monkeypatch.setattr(ls, "KILL_SWITCH_PATH", tmp_kill)
    monkeypatch.setattr(ls, "_CUA_AUDIT_DIR", tmp_audit)
    return tmp_kill


class TestKillSwitch:
    """Tests for activate_kill_switch / deactivate_kill_switch / is_kill_switch_active."""

    def test_activate_then_is_active(self, tmp_kill_switch_dir: Path):
        """Activating the kill switch should make is_kill_switch_active True."""
        from agents.life_safety import activate_kill_switch, is_kill_switch_active

        # Initially not active
        assert not is_kill_switch_active()

        # Activate
        activate_kill_switch(reason="test_activation")

        # Now active
        assert is_kill_switch_active()

        # The kill switch file should exist and contain the reason
        assert tmp_kill_switch_dir.exists()
        data = json.loads(tmp_kill_switch_dir.read_text())
        assert data["reason"] == "test_activation"
        assert "activated_at" in data
        assert "pid" in data

    def test_activate_with_default_reason(self, tmp_kill_switch_dir: Path):
        """activate_kill_switch() with no args uses 'manual' as the reason."""
        from agents.life_safety import activate_kill_switch

        activate_kill_switch()
        data = json.loads(tmp_kill_switch_dir.read_text())
        assert data["reason"] == "manual"

    def test_deactivate_after_activate(self, tmp_kill_switch_dir: Path):
        """deactivate_kill_switch should remove the kill switch file."""
        from agents.life_safety import (
            activate_kill_switch,
            deactivate_kill_switch,
            is_kill_switch_active,
        )

        activate_kill_switch(reason="to_be_deactivated")
        assert is_kill_switch_active()

        result = deactivate_kill_switch()
        assert result is True
        assert not is_kill_switch_active()
        assert not tmp_kill_switch_dir.exists()

    def test_deactivate_when_not_active_returns_false(self, tmp_kill_switch_dir: Path):
        """deactivate_kill_switch returns False when no kill switch is active."""
        from agents.life_safety import deactivate_kill_switch

        result = deactivate_kill_switch()
        assert result is False

    def test_is_active_when_file_missing(self, tmp_kill_switch_dir: Path):
        """is_kill_switch_active returns False when the kill switch file is missing."""
        from agents.life_safety import is_kill_switch_active

        # Ensure file doesn't exist
        if tmp_kill_switch_dir.exists():
            tmp_kill_switch_dir.unlink()
        assert not is_kill_switch_active()

    def test_is_active_when_file_contains_valid_json(self, tmp_kill_switch_dir: Path):
        """is_kill_switch_active returns True when the file contains valid JSON."""
        from agents.life_safety import is_kill_switch_active

        # Write a valid kill switch file
        tmp_kill_switch_dir.write_text(
            json.dumps({"activated_at": "2026-01-01T00:00:00Z", "reason": "test", "pid": 1234})
        )
        assert is_kill_switch_active()


class TestRollbackSnapshotIdValidation:
    """Tests for the snapshot_id regex validation in LifeSafetyCoordinator.rollback.

    Verifies the path-injection defense (CodeQL py/path-injection) added in
    PR #242: snapshot_id must match [a-f0-9]+ before being used in a path.
    """

    def _make_coordinator(self, tmp_path: Path):
        """Create a LifeSafetyGuard with a temp audit_dir."""
        from agents.life_safety import LifeSafetyGuard

        return LifeSafetyGuard(audit_dir=str(tmp_path / "audit"))

    def test_rollback_rejects_path_traversal_snapshot_id(self, tmp_path: Path):
        """rollback returns an error dict when snapshot_id contains '/'."""
        coord = self._make_coordinator(tmp_path)
        result = coord.rollback(snapshot_id="../../etc/passwd", reason="test")
        assert result["success"] is False
        assert "Invalid snapshot_id format" in result["message"]
        assert result["snapshot"] is None

    def test_rollback_rejects_dotdot_snapshot_id(self, tmp_path: Path):
        """rollback returns an error dict when snapshot_id contains '..'."""
        coord = self._make_coordinator(tmp_path)
        result = coord.rollback(snapshot_id="..", reason="test")
        assert result["success"] is False
        assert "Invalid snapshot_id format" in result["message"]

    def test_rollback_rejects_uppercase_snapshot_id(self, tmp_path: Path):
        """rollback returns an error dict when snapshot_id contains uppercase letters."""
        coord = self._make_coordinator(tmp_path)
        result = coord.rollback(snapshot_id="ABCDEF123456", reason="test")
        assert result["success"] is False
        assert "Invalid snapshot_id format" in result["message"]

    def test_rollback_rejects_special_chars_snapshot_id(self, tmp_path: Path):
        """rollback returns an error dict when snapshot_id contains special chars."""
        coord = self._make_coordinator(tmp_path)
        result = coord.rollback(snapshot_id="abc; rm -rf /", reason="test")
        assert result["success"] is False
        assert "Invalid snapshot_id format" in result["message"]

    def test_rollback_accepts_valid_hex_snapshot_id(self, tmp_path: Path):
        """rollback accepts a valid 16-char hex snapshot_id (doesn't reject format).

        Note: this test verifies the snapshot_id passes the regex validation.
        The rollback will still fail with 'snapshot not found' because no
        snapshot was actually captured, but the failure should be a
        'No snapshot found' error, NOT an 'Invalid snapshot_id format' error.
        """
        coord = self._make_coordinator(tmp_path)
        # Use a valid hex snapshot_id (matches _capture_state_snapshot output)
        result = coord.rollback(snapshot_id="abcdef0123456789", reason="test")
        assert result["success"] is False
        # The error should be 'No snapshot found', NOT 'Invalid snapshot_id format'
        assert "Invalid snapshot_id format" not in result["message"]
        assert "No snapshot found" in result["message"]
