"""
tests/test_cua_display.py — Unit and integration tests for CUA platform guards.

Verifies:
1. Native CUAExecutor on non-Windows fails cleanly with structured UNSUPPORTED_PLATFORM result.
2. CUAExecutor.execute_loop() rejects non-Windows execution before any native activity.
3. CUAExecutor.check_dependencies() reports structured platform capability failure on non-Windows.
4. No pyautogui import or execution is attempted on non-Windows.
5. No X11 / Xvfb / Linux desktop dependencies are introduced.
6. BrowserCUAExecutor and BaseCUAExecutor remain platform-independent.
"""

from __future__ import annotations

import os
import sys
import unittest.mock
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.browser_cua_executor import BrowserCUAExecutor
from agents.cua_base_executor import BaseCUAExecutor, CUAAction, CUAExecutionResult
from agents.cua_executor import CUAExecutor, _import_pyautogui, ocr_screenshot


class TestCUANonWindowsPlatformGuard:
    """Test suite for native desktop CUA platform safety guards."""

    def test_execute_loop_fails_cleanly_on_non_windows(self, monkeypatch):
        """Non-Windows: execute_loop() returns structured UNSUPPORTED_PLATFORM result."""
        monkeypatch.setattr(sys, "platform", "linux")
        executor = CUAExecutor()

        result = executor.execute_loop(objective="Run load flow analysis in ETAP")

        assert isinstance(result, CUAExecutionResult)
        assert result.success is False
        assert result.aborted_reason is not None
        assert "UNSUPPORTED_PLATFORM" in result.aborted_reason
        assert "Windows worker node" in result.aborted_reason
        assert len(result.steps) == 0

    def test_check_dependencies_reports_unsupported_platform(self, monkeypatch):
        """Non-Windows: check_dependencies() reports clean platform rejection."""
        monkeypatch.setattr(sys, "platform", "darwin")
        executor = CUAExecutor()

        deps = executor.check_dependencies()

        assert deps["all_available"] is False
        assert deps.get("error") == "UNSUPPORTED_PLATFORM"
        assert "Windows worker node" in deps.get("message", "")
        assert "windows_platform" in deps.get("missing", [])
        assert deps["pyautogui"] is False

    def test_import_pyautogui_returns_none_on_non_windows(self, monkeypatch):
        """Non-Windows: _import_pyautogui() safely returns None without attempting import."""
        monkeypatch.setattr(sys, "platform", "linux")
        assert _import_pyautogui() is None

    def test_screenshot_hook_returns_none_on_non_windows(self, monkeypatch):
        """Non-Windows: _capture_screenshot_hook() returns None safely."""
        monkeypatch.setattr(sys, "platform", "linux")
        executor = CUAExecutor()
        assert executor._capture_screenshot_hook(1, "before") is None

    def test_execute_action_hook_returns_error_on_non_windows(self, monkeypatch):
        """Non-Windows: _execute_action_hook() returns structured platform error."""
        monkeypatch.setattr(sys, "platform", "linux")
        executor = CUAExecutor()
        action = CUAAction(type="click", x=100, y=200)
        err = executor._execute_action_hook(action)
        assert err is not None
        assert "UNSUPPORTED_PLATFORM" in err

    def test_ocr_screenshot_returns_empty_on_non_windows(self, monkeypatch):
        """Non-Windows: ocr_screenshot() returns empty string safely."""
        monkeypatch.setattr(sys, "platform", "linux")
        assert ocr_screenshot("dummy_path.png") == ""

    def test_no_x11_or_xvfb_in_cua_executor_source(self):
        """Verify no X11/Xvfb/DISPLAY provisioning was added to cua_executor.py."""
        with open("agents/cua_executor.py", encoding="utf-8") as f:
            src = f.read().lower()

        assert "xvfb" not in src
        assert "display" not in src or "display server" in src  # docstring only
        assert "x11" not in src or "x11/wayland" in src  # docstring only

    def test_browser_cua_executor_unaffected_by_platform_guard(self, monkeypatch):
        """BrowserCUAExecutor remains platform-independent and can be initialized on any OS."""
        monkeypatch.setattr(sys, "platform", "linux")
        browser_exec = BrowserCUAExecutor()
        assert isinstance(browser_exec, BaseCUAExecutor)
        # Verify check_dependencies runs playwright checks, not windows platform guard
        deps = browser_exec.check_dependencies()
        assert "windows_platform" not in deps.get("missing", [])
