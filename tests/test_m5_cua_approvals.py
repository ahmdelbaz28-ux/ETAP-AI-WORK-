"""
tests/test_m5_cua_approvals.py — Verification tests for Phase M5.1 CUA Automation & Governance.

Verifies Acceptance Gates 1 and 2:
1. Negative CUA CONTROL test: Any command of type CONTROL without interactive approval
   results in explicit waiting or documented abort — no silent execution or bypass.
2. Post-action verification test: A test proving that failing/disabling the deterministic effect
   results in failing the CUA step and executing automated rollback.
3. Coordinate bounds violation test: Actions outside defined window coordinates abort fail-closed.
4. Tool policy violation test: Actions outside allowed_tools abort fail-closed.
5. Automated rollback execution: Verification that auto-rollback handler executes on rollback.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from agents.cua_base_executor import BaseCUAExecutor
from agents.cua_executor import CUAAction, CUAExecutionResult
from agents.life_safety import LifeSafetyGuard, life_safety_guard


class MockCUAExecutor(BaseCUAExecutor):
    """Concrete mock executor for testing CUA loop governance, approvals, and rollback."""

    def __init__(self, actions_to_return: list[dict[str, Any]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.actions_to_return = actions_to_return or []
        self.action_index = 0
        self.executed_actions: list[CUAAction] = []
        self.temp_dir = tempfile.TemporaryDirectory()

    def check_dependencies(self) -> dict[str, Any]:
        return {"all_available": True, "missing": []}

    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> str | None:
        p = Path(self.temp_dir.name) / f"screen_{step_num}_{phase}.png"
        color = "white" if phase == "before" else "lightgray"
        Image.new("RGB", (800, 600), color).save(str(p))
        return str(p)

    def _execute_action_hook(self, action: CUAAction, **kwargs) -> str | None:
        self.executed_actions.append(action)
        return None

    def _wait_settle(self) -> None:
        pass

    def _cleanup_on_exit(self) -> None:
        self.temp_dir.cleanup()


# ==============================================================================
# Gate 1: Negative CUA CONTROL Tests
# ==============================================================================


def test_cua_control_fails_closed_without_confirmation_callback():
    """Negative test: CONTROL action with require_confirmation=True and no callback must abort."""
    executor = MockCUAExecutor()
    mock_action_dict = {
        "source": "gemini",
        "next_action": {
            "type": "click",
            "x": 200,
            "y": 300,
            "target": "Run Simulation Button",
        },
    }

    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=mock_action_dict):
        result: CUAExecutionResult = executor.execute_loop(
            objective="Run simulation safely",
            max_steps=1,
            mode="control",
            require_confirmation=True,
            on_confirmation_request=None,
            bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
        )

    # Must fail closed: not executed, aborted reason documented
    assert not result.success
    assert "confirmation" in result.aborted_reason.lower() or "callback" in result.aborted_reason.lower()
    assert len(executor.executed_actions) == 0


def test_cua_control_fails_when_user_rejects_confirmation():
    """Negative test: CONTROL action where on_confirmation_request returns False must abort."""
    executor = MockCUAExecutor()
    mock_action_dict = {
        "source": "gemini",
        "next_action": {
            "type": "click",
            "x": 200,
            "y": 300,
            "target": "Breaker Open Operation",
        },
    }

    # Callback explicitly denies confirmation
    rejection_callback = MagicMock(return_value=False)

    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=mock_action_dict):
        result: CUAExecutionResult = executor.execute_loop(
            objective="Open circuit breaker",
            max_steps=1,
            mode="control",
            require_confirmation=True,
            on_confirmation_request=rejection_callback,
            bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
        )

    assert not result.success
    assert "declined" in (result.aborted_reason or "").lower()
    assert "User did not confirm action" in (result.steps[0].error or "")
    rejection_callback.assert_called_once()
    assert len(executor.executed_actions) == 0


def test_cua_control_proceeds_when_user_confirms():
    """Positive test: CONTROL action executes when user confirmation callback returns True."""
    import uuid

    executor = MockCUAExecutor()
    # Sequence: step 1 click, step 2 done
    action_1 = {
        "source": "gemini",
        "next_action": {
            "type": "click",
            "x": 200,
            "y": 300,
            "target": "Apply Settings",
        },
    }
    action_2 = {
        "source": "gemini",
        "next_action": {"type": "done"},
    }

    approval_callback = MagicMock(return_value=True)

    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", side_effect=[action_1, action_2]):
        result: CUAExecutionResult = executor.execute_loop(
            objective=f"Apply settings {uuid.uuid4().hex[:8]}",
            max_steps=2,
            mode="control",
            require_confirmation=True,
            on_confirmation_request=approval_callback,
            bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
        )

    assert result.success
    approval_callback.assert_called_once()
    assert len(executor.executed_actions) == 1
    assert executor.executed_actions[0].target == "Apply Settings"


# ==============================================================================
# Gate 2: Deterministic Post-Action Verification & Automated Rollback Tests
# ==============================================================================


def test_cua_post_action_verification_failure_triggers_auto_rollback():
    """Gate 2: Action succeeds physically, but post-action verification fails -> auto rollback + abort."""
    import uuid

    executor = MockCUAExecutor()
    action_1 = {
        "source": "gemini",
        "next_action": {
            "type": "click",
            "x": 250,
            "y": 350,
            "target": "Change Bus Nominal Voltage",
        },
    }

    rollback_called_with = []

    def mock_auto_rollback(snapshot, reason=None):
        rollback_called_with.append((snapshot, reason))
        return True

    # Register auto-rollback handler
    life_safety_guard.register_auto_rollback_handler(mock_auto_rollback)

    # Force post-action verification to FAIL
    failing_verification_hook = MagicMock(return_value=False)
    life_safety_guard.set_verification_hook(failing_verification_hook)

    try:
        with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_1):
            result: CUAExecutionResult = executor.execute_loop(
                objective=f"Change voltage {uuid.uuid4().hex[:8]}",
                max_steps=2,
                mode="control",
                require_confirmation=False,
                bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
            )

        # 1. Loop must abort with failure
        assert not result.success
        assert "post_action_verification_failed" in (result.aborted_reason or "").lower() or "verification failed" in (result.aborted_reason or "").lower()

        # 2. Step 1 must have executed physically but failed post-verification
        assert len(executor.executed_actions) == 1
        assert len(result.steps) == 1
        step_1 = result.steps[0]
        assert not step_1.success
        assert "verification failed" in (step_1.error or "").lower()

        # 3. Automated rollback handler must have been invoked with reason
        assert len(rollback_called_with) >= 1
        snapshot_used, reason_used = rollback_called_with[0]
        assert "post_action_verification_failed" in reason_used
    finally:
        # Clean up hooks
        life_safety_guard.set_verification_hook(None)
        life_safety_guard.register_auto_rollback_handler(None)


def test_life_safety_guard_auto_rollback_tamper_evident_audit():
    """Verify that automated rollback marks rollback_type='automated' in audit trail."""
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        rollback_events = []

        guard.register_auto_rollback_handler(lambda snap, rsn=None: rollback_events.append((snap, rsn)) or True)

        # Snapshot before action
        action = CUAAction(type="click", target="bus_1", x=100, y=100)
        snap_id = guard._capture_state_snapshot(action, None, datetime.now(timezone.utc).isoformat())
        assert snap_id is not None

        # Execute rollback
        res = guard.rollback(snap_id, reason="test_auto_rollback_event")
        assert res["success"] is True
        assert len(rollback_events) == 1
        assert rollback_events[0][1] == "test_auto_rollback_event"

        # Check audit trail
        audit_file = Path(tmpdir) / "safety_chain.jsonl"
        assert audit_file.exists()
        lines = [line.strip() for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) >= 1

        import json

        record = json.loads(lines[-1])
        assert "hash" in record
        assert "prev_hash" in record
        data = record["data"]
        assert data["event_type"].lower() == "rollback"
        assert data["extra"]["rollback_type"] == "automated"
        assert data["extra"]["rollback_reason"] == "test_auto_rollback_event"


# ==============================================================================
# Isolation & Governance: Coordinate Bounds & Tool Policy Tests
# ==============================================================================


def test_cua_coordinate_bounds_violation_aborts_before_action():
    """M5.1(d): Actions with coordinates outside allowed screen bounds must abort immediately."""
    executor = MockCUAExecutor()
    # Click at x=4000, outside 1920x1080 bounds
    action_out_of_bounds = {
        "source": "gemini",
        "next_action": {
            "type": "click",
            "x": 4000,
            "y": 500,
            "target": "Desktop Outside Window",
        },
    }

    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_out_of_bounds):
        result: CUAExecutionResult = executor.execute_loop(
            objective="Click outside bounds",
            max_steps=1,
            mode="control",
            require_confirmation=False,
            bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
        )

    # Must fail closed immediately
    assert not result.success
    assert "bounds violation" in (result.aborted_reason or "").lower()
    assert "BOUNDS VIOLATION" in (result.steps[0].error or "")
    # Must NOT have executed the action
    assert len(executor.executed_actions) == 0


def test_cua_tool_policy_violation_aborts_before_action():
    """M5.1(d): Actions not included in allowed_tools must abort immediately."""
    executor = MockCUAExecutor()
    # Action type "hotkey" when only ["click", "type"] are allowed
    disallowed_action = {
        "source": "gemini",
        "next_action": {
            "type": "hotkey",
            "keys": ["ctrl", "alt", "delete"],
            "target": "OS shortcut",
        },
    }

    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=disallowed_action):
        result: CUAExecutionResult = executor.execute_loop(
            objective="Invoke dangerous shortcut",
            max_steps=1,
            mode="control",
            require_confirmation=False,
            allowed_tools=["click", "type"],
            bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
        )

    # Must fail closed immediately
    assert not result.success
    assert "disallowed by tool policy" in (result.aborted_reason or "").lower()
    assert "TOOL POLICY VIOLATION" in (result.steps[0].error or "")
    assert len(executor.executed_actions) == 0


# ==============================================================================
# Hardening Follow-up Tests (Items 1, 2, 3)
# ==============================================================================


def test_life_safety_guard_rollback_without_callback_manual_only():
    """Item 1: Rollback without an auto-reversal callback must be manual_only with automated=False."""
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", target="breaker_1", x=100, y=100)
        snap_id = guard._capture_state_snapshot(action, None, datetime.now(timezone.utc).isoformat())
        assert snap_id is not None

        # Rollback without callback registered
        res = guard.rollback(snap_id, reason="test_manual_only")
        assert res["success"] is True
        assert res["rollback_type"] == "manual_only"
        assert res["automated"] is False
        assert "MANUAL" in res["message"]


def test_verify_post_action_mutating_without_evidence_not_silently_verified():
    """Item 2: Mutating action with no screenshots and no verifier hook must not be silently verified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", target="bus_voltage", x=100, y=100)

        # No screenshots, no verifier hook
        res = guard.verify_post_action(action, screenshot_before=None, screenshot_after=None)
        assert res["verified"] is False
        assert res["unverified_passthrough"] is True
        assert "no verifier evidence" in res["reason"].lower()


def test_cua_control_mode_missing_bounds_aborts_fail_closed():
    """Item 3: In control mode, bounds=None must abort fail-closed with BOUNDS VIOLATION missing-bounds."""
    executor = MockCUAExecutor()
    action = {
        "source": "gemini",
        "next_action": {"type": "click", "x": 100, "y": 100, "target": "Some Button"},
    }
    with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action):
        result = executor.execute_loop(
            objective="Click button without window bounds",
            max_steps=1,
            mode="control",
            bounds=None,  # Missing bounds in control mode
        )

    assert not result.success
    assert "bounds" in (result.aborted_reason or "").lower()
    assert "BOUNDS VIOLATION" in (result.steps[0].error or "")
    assert len(executor.executed_actions) == 0


def test_default_production_rollback_handler_allowlist_precedence_and_word_boundaries():
    """Verify that safe UI actions (like modal_close) take precedence over substring checks,
    and word-boundary checks prevent false positives on harmless words like 'opened_panel'."""
    from agents.life_safety import LifeSafetyGuard, default_production_rollback_handler

    # 1. Allow-listed action (modal_close) has 'close' substring but MUST return True
    snap_modal = {"action": {"type": "modal_close", "target": "settings_dialog"}}
    assert default_production_rollback_handler(snap_modal) is True

    snap_cancel = {"action": {"type": "ui_dialog_cancel", "target": "confirm_dialog"}}
    assert default_production_rollback_handler(snap_cancel) is True

    # 2. Target containing 'open' as substring (e.g. 'opened_panel') does not match \\bopen\\b
    # and fail-closes safely without false-positive trigger
    snap_opened = {"action": {"type": "navigate", "target": "opened_panel"}}
    assert default_production_rollback_handler(snap_opened) is False

    # 3. Safety-critical breaker / switch operations MUST strictly return False
    snap_breaker_open = {"action": {"type": "breaker_open", "target": "breaker_52a"}}
    assert default_production_rollback_handler(snap_breaker_open) is False

    snap_switch_close = {"action": {"type": "switch", "target": "main_incomer"}}
    assert default_production_rollback_handler(snap_switch_close) is False

    snap_bus = {"action": {"type": "reconfigure", "target": "bus_101"}}
    assert default_production_rollback_handler(snap_bus) is False

    # 4. LifeSafetyGuard default state must be manual-only (_auto_rollback_enabled == False)
    guard = LifeSafetyGuard()
    assert guard._auto_rollback_enabled is False
    assert guard._auto_rollback_handler is None

