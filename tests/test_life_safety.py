"""
tests/test_life_safety.py — Tests for the Life Safety Guard

These tests verify that the non-bypassable safety layer correctly:
  1. Blocks lethal actions (protection disable, breaker ops, arc flash delete)
  2. Flags protection-setting changes for dual confirmation
  3. Blocks OpenCV degraded mode from controlling
  4. Activates/deactivates the kill switch
  5. Maintains a tamper-evident audit chain
  6. Enforces cooldown between control actions
  7. Annotates screenshots before clicks

CRITICAL: These tests must NEVER skip. If they fail, lives are at risk.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# 1. Module imports cleanly
# ---------------------------------------------------------------------------


def test_life_safety_module_imports_cleanly():
    """agents.life_safety must be importable on any environment."""
    from agents import life_safety

    assert hasattr(life_safety, "LifeSafetyGuard")
    assert hasattr(life_safety, "life_safety_guard")
    assert hasattr(life_safety, "activate_kill_switch")
    assert hasattr(life_safety, "deactivate_kill_switch")
    assert hasattr(life_safety, "is_kill_switch_active")


# ---------------------------------------------------------------------------
# 2. Kill switch — emergency stop
# ---------------------------------------------------------------------------


def test_kill_switch_activate_and_deactivate():
    """Activating the kill switch must create the file; deactivating removes it."""
    from agents.life_safety import (
        KILL_SWITCH_PATH,
        activate_kill_switch,
        deactivate_kill_switch,
        is_kill_switch_active,
    )

    # Clean start
    deactivate_kill_switch()
    assert not is_kill_switch_active()

    # Activate
    activate_kill_switch(reason="test_emergency")
    assert is_kill_switch_active()
    assert KILL_SWITCH_PATH.exists()

    # Verify content
    data = json.loads(KILL_SWITCH_PATH.read_text())
    assert data["reason"] == "test_emergency"
    assert "activated_at" in data

    # Deactivate
    was_active = deactivate_kill_switch()
    assert was_active is True
    assert not is_kill_switch_active()
    assert not KILL_SWITCH_PATH.exists()


def test_kill_switch_blocks_all_actions():
    """When the kill switch is active, pre_action_check must block ALL actions."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import (
        LifeSafetyGuard,
        activate_kill_switch,
        deactivate_kill_switch,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        activate_kill_switch(reason="test")

        try:
            action = CUAAction(type="click", x=100, y=200, target="Run button")
            result = guard.pre_action_check(
                action=action,
                screenshot_before=None,
                gemini_analysis={"source": "gemini"},
                vision_source="gemini",
                mode="control",
            )
            assert result.blocked is True
            assert "KILL SWITCH" in result.reason
            assert result.safety_level == "blocked"
        finally:
            deactivate_kill_switch()


# ---------------------------------------------------------------------------
# 3. Lethal action patterns — must be blocked UNCONDITIONALLY
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target_text",
    [
        "Disable Protection Relay 50",
        "Disable Arc Flash Detection",
        "Open Breaker BRK-001",
        "Close Breaker Main-Tie",
        "Delete Relay R-1",
        "Reset Protection Settings",
        "Disable Differential 87",
        "Trip Breaker Feeder-3",
    ],
)
def test_lethal_actions_blocked(target_text):
    """Lethal target patterns must be blocked regardless of vision source."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", x=100, y=200, target=target_text)
        result = guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )
        assert result.blocked is True, f"Should block: {target_text}"
        assert "LETHAL ACTION BLOCKED" in result.reason
        assert result.matched_pattern is not None


def test_safe_actions_not_blocked():
    """Safe actions (Run Study, Open File, View Report) must NOT be blocked."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", x=100, y=200, target="Run Load Flow Study")
        result = guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )
        assert result.blocked is False
        assert result.safety_level in ("ok", "dual_confirmation")


# ---------------------------------------------------------------------------
# 4. Dual confirmation for protection-setting changes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target_text",
    [
        "Modify Relay Setting 50/51",
        "Edit Coordination Setting",
        "Change Trip Threshold",
        "Modify Arc Flash Boundary",
        "Apply Changes to Protection",
    ],
)
def test_dual_confirmation_required(target_text):
    """Protection-setting changes must require dual confirmation."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", x=100, y=200, target=target_text)
        result = guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )
        assert result.blocked is False  # Not blocked outright
        assert result.requires_dual_confirmation is True
        assert result.matched_pattern is not None


# ---------------------------------------------------------------------------
# 5. OpenCV degraded mode cannot control
# ---------------------------------------------------------------------------


def test_opencv_degraded_mode_blocked_for_control():
    """OpenCV (degraded vision) must NOT be allowed to control."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", x=100, y=200, target="Run button")
        result = guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "opencv"},
            vision_source="opencv",
            mode="control",
        )
        assert result.blocked is True
        assert "DEGRADED VISION" in result.reason


def test_opencv_degraded_mode_allowed_for_analyze():
    """OpenCV is OK for ANALYZE mode (read-only — no clicks)."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        # 'done' action in analyze mode — should pass
        action = CUAAction(type="done", summary="Analysis complete")
        result = guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "opencv"},
            vision_source="opencv",
            mode="analyze",
        )
        assert result.blocked is False


# ---------------------------------------------------------------------------
# 6. Tamper-evident audit log
# ---------------------------------------------------------------------------


def test_audit_log_creates_chain():
    """Each audit entry must depend on the previous (SHA-256 chain)."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = str(Path(tmpdir) / "chain.jsonl")
        guard = LifeSafetyGuard(audit_dir=tmpdir, safety_log_path=log_path)

        action = CUAAction(type="click", x=100, y=200, target="Run button")
        guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )

        # Log file should exist with at least one entry
        assert Path(log_path).exists()
        lines = Path(log_path).read_text().strip().split("\n")
        assert len(lines) >= 1

        # Each entry must have a hash field
        entry = json.loads(lines[0])
        assert "hash" in entry
        assert "prev_hash" in entry
        assert len(entry["hash"]) == 64  # SHA-256 hex


def test_audit_log_chain_verification():
    """verify_chain() must return True for an intact chain."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = str(Path(tmpdir) / "chain.jsonl")
        guard = LifeSafetyGuard(audit_dir=tmpdir, safety_log_path=log_path)

        # Append several entries
        for i in range(5):
            action = CUAAction(type="click", x=i, y=i, target=f"button_{i}")
            guard.pre_action_check(
                action=action,
                screenshot_before=None,
                gemini_analysis={"source": "gemini"},
                vision_source="gemini",
                mode="control",
            )

        is_valid, broken = guard.audit_log.verify_chain()
        assert is_valid is True
        assert broken == []


def test_audit_log_detects_tampering():
    """Modifying a past entry must break the chain and be detected."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        # Resolve to absolute, normalized path to satisfy SonarCloud S2083
        # (path injection). `tmpdir` is pytest's fixture, never user input.
        audit_dir = os.path.realpath(tmpdir)
        log_path = os.path.join(audit_dir, "chain.jsonl")
        guard = LifeSafetyGuard(audit_dir=audit_dir, safety_log_path=log_path)

        # Append 3 entries
        for i in range(3):
            action = CUAAction(type="click", x=i, y=i, target=f"button_{i}")
            guard.pre_action_check(
                action=action,
                screenshot_before=None,
                gemini_analysis={"source": "gemini"},
                vision_source="gemini",
                mode="control",
            )

        # Verify intact
        is_valid, _ = guard.audit_log.verify_chain()
        assert is_valid is True

        # Tamper: modify the first entry's data. Path is fully sanitized
        # via os.path.realpath above; no user-controlled input reaches here.
        # `log_path` is derived from tempfile.TemporaryDirectory() — never
        # from user input. nosec B108 marks the test-fixture path as safe.
        lines = Path(log_path).read_text().strip().split("\n")  # nosec B108 — test fixture path
        first_entry = json.loads(lines[0])
        first_entry["data"]["action"]["target"] = "TAMPERED_TARGET"
        lines[0] = json.dumps(first_entry)
        Path(log_path).write_text("\n".join(lines) + "\n")  # nosec B108 — test fixture path  # NOSONAR — S2083: path derived from tempfile fixture, not user input

        # Verify tampering detected
        is_valid, broken = guard.audit_log.verify_chain()
        assert is_valid is False
        assert len(broken) > 0


# ---------------------------------------------------------------------------
# 7. Cooldown enforcement
# ---------------------------------------------------------------------------


def test_cooldown_enforced_between_actions():
    """A 2-second cooldown must be enforced between control actions."""
    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)

        action = CUAAction(type="click", x=100, y=200, target="Run button")

        # First action — no cooldown (no prior action)
        start1 = time.monotonic()
        guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )
        elapsed1 = time.monotonic() - start1
        assert elapsed1 < 0.5  # should be instant

        # Record the action as completed (sets last_control_action_time)
        from agents.life_safety import SafetyCheckResult

        guard.post_action_record(
            action=action,
            screenshot_after=None,
            pre_check=SafetyCheckResult(blocked=False),
            exec_error=None,
        )

        # Second action immediately — should wait for cooldown
        start2 = time.monotonic()
        guard.pre_action_check(
            action=action,
            screenshot_before=None,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )
        elapsed2 = time.monotonic() - start2
        # Should have waited at least 1.5 seconds (cooldown is 2.0)
        assert elapsed2 >= 1.5, f"Cooldown not enforced: only {elapsed2:.2f}s waited"


# ---------------------------------------------------------------------------
# 8. Screenshot annotation
# ---------------------------------------------------------------------------


def test_screenshot_annotation_creates_file():
    """Pre-action check must create an annotated screenshot for click actions."""
    from PIL import Image

    from agents.cua_executor import CUAAction
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake screenshot
        screenshot_path = str(Path(tmpdir) / "before.png")
        Image.new("RGB", (800, 600), "white").save(screenshot_path)

        guard = LifeSafetyGuard(audit_dir=tmpdir)
        action = CUAAction(type="click", x=400, y=300, target="Run button")
        result = guard.pre_action_check(
            action=action,
            screenshot_before=screenshot_path,
            gemini_analysis={"source": "gemini"},
            vision_source="gemini",
            mode="control",
        )

        assert result.annotated_screenshot is not None
        assert Path(result.annotated_screenshot).exists()
        # Annotated file should have "_annotated" in the name
        assert "_annotated" in result.annotated_screenshot


# ---------------------------------------------------------------------------
# 9. Health check
# ---------------------------------------------------------------------------


def test_health_check_returns_dict():
    """health_check() must return a comprehensive status dict."""
    from agents.life_safety import LifeSafetyGuard

    with tempfile.TemporaryDirectory() as tmpdir:
        guard = LifeSafetyGuard(audit_dir=tmpdir)
        health = guard.health_check()

        assert isinstance(health, dict)
        assert "kill_switch_active" in health
        assert "audit_chain_valid" in health
        assert "lethal_patterns_count" in health
        assert "dual_confirmation_patterns_count" in health
        assert "cooldown_seconds" in health
        assert "degraded_vision_sources" in health
        assert health["lethal_patterns_count"] > 0
        assert health["dual_confirmation_patterns_count"] > 0


# ---------------------------------------------------------------------------
# 10. CUAExecutor integrates safety guard
# ---------------------------------------------------------------------------


def test_cua_executor_uses_life_safety_guard():
    """CUAExecutor must import and use life_safety_guard."""
    p = Path(__file__).resolve().parent.parent / "agents" / "cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "from agents.life_safety import" in content
    assert "life_safety_guard" in content
    assert "pre_action_check" in content
    assert "LIFE SAFETY CHECK" in content


def test_browser_cua_executor_uses_life_safety_guard():
    """BrowserCUAExecutor must import and use life_safety_guard."""
    p = Path(__file__).resolve().parent.parent / "agents" / "browser_cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "from agents.life_safety import" in content
    assert "life_safety_guard" in content
    assert "pre_action_check" in content


# ---------------------------------------------------------------------------
# 11. API endpoints exist
# ---------------------------------------------------------------------------


def test_kill_switch_endpoints_exist():
    """api/agents.py must expose kill switch activate/deactivate endpoints."""
    p = Path(__file__).resolve().parent.parent / "api" / "agents.py"
    content = p.read_text(encoding="utf-8")
    assert "/etap-gui/kill-switch/activate" in content
    assert "/etap-gui/kill-switch/deactivate" in content
    assert "/etap-gui/safety/health" in content
    assert "/etap-gui/safety/audit/verify" in content


def test_kill_switch_endpoints_in_hf_space():
    """hf-space/app.py should also expose safety endpoints (soft contract)."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    content = p.read_text(encoding="utf-8")
    # At minimum, the health endpoint should be mirrored
    # (kill switch endpoints are optional on HF Space since it's read-only by default)
    if "/etap-gui" in content:
        # The CUA endpoints exist; safety endpoints are a bonus
        assert "/etap-gui/health" in content or "/etap-gui/safety" in content


# ---------------------------------------------------------------------------
# 12. Documentation
# ---------------------------------------------------------------------------


def test_life_safety_module_docstring_extensive():
    """The module docstring must explain WHY this layer exists (life safety)."""
    from agents import life_safety

    assert life_safety.__doc__ is not None
    doc = life_safety.__doc__
    # Must mention life safety critical terms
    assert "arc flash" in doc.lower() or "life" in doc.lower()
    assert "protection" in doc.lower()
    assert "bypass" in doc.lower() or "non-bypassable" in doc.lower()


def test_lethal_patterns_include_protection_keywords():
    """LETHAL_TARGET_PATTERNS must include protection-relay keywords."""
    from agents.life_safety import LETHAL_TARGET_PATTERNS

    all_patterns = " ".join(LETHAL_TARGET_PATTERNS)
    # Must cover: protection disable, breaker ops, arc flash delete, relay delete
    assert "disable protection" in all_patterns
    assert "breaker" in all_patterns
    assert "arc flash" in all_patterns
    assert "relay" in all_patterns
    assert "protection" in all_patterns
