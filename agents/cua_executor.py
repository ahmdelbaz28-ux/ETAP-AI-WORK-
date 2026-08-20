"""
agents/cua_executor.py — Computer Use Agent Executor (Desktop/pyautogui)

The actual execution layer that turns the ETAP GUI Agent skill from a
"planning agent" into a real Computer Use Agent (CUA).

This module provides the DesktopCUAExecutor that uses pyautogui for
screenshot capture and action execution on a local desktop with a
display server (X11/Wayland).

The 10-step CUA loop algorithm is now shared via the BaseCUAExecutor
template method pattern (see agents/cua_base_executor.py). This module
only provides the platform-specific hooks for pyautogui-based execution.

Safety guarantees (per skills/etap-gui-agent.md):
    - pyautogui.FAILSAFE = True (move mouse to corner = immediate stop)
    - 60-second timeout per action
    - Full audit log with before/after screenshots
    - CONTROL/SOLVE actions require explicit user confirmation
    - Destructive dialogs (Delete/Format/Override/Reset) are never auto-clicked

This module is import-safe on headless servers: pyautogui is only imported
lazily inside the executor methods, so importing this module never crashes.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from agents.cua_base_executor import (
    DEFAULT_ACTION_TIMEOUT,
    DEFAULT_MAX_STEPS,
    BaseCUAExecutor,
    CUAAction,
    CUAExecutionResult,
    CUAStepResult,
)

logger = logging.getLogger("agent.cua_executor")

# ─── Lazy imports for desktop-only deps ────────────────────────────────────
# pyautogui, pytesseract, cv2 are only importable on a desktop OS with a
# display server. We import them lazily so this module can be imported on
# headless servers without crashing.


def _import_pyautogui():
    """Lazily import pyautogui; return None on non-Windows / headless / missing."""
    if sys.platform != "win32":
        return None
    try:
        import pyautogui

        pyautogui.FAILSAFE = True  # Safety: move mouse to corner = immediate stop
        return pyautogui
    except Exception as exc:  # noqa: BLE001
        logger.warning("pyautogui not available: %s", exc)
        return None


def _import_pytesseract():
    """Lazily import pytesseract; return None if not installed."""
    try:
        import pytesseract

        return pytesseract
    except Exception:  # noqa: BLE001
        return None


# ─── The Desktop Executor ──────────────────────────────────────────────────


class CUAExecutor(BaseCUAExecutor):
    """Executes the Computer Use Agent loop on the local desktop.

    Lifecycle:
        executor = CUAExecutor(audit_dir="~/.etap/cua_audit")
        result = executor.execute_loop(
            objective="Open ETAP and run Load Flow",
            max_steps=15,
            require_confirmation=True,  # CONTROL/SOLVE actions
            on_confirmation_request=callback,  # called before destructive/control actions
        )
    """

    def __init__(
        self,
        audit_dir=None,
        action_timeout: int = DEFAULT_ACTION_TIMEOUT,
    ) -> None:
        super().__init__(audit_dir=audit_dir, action_timeout=action_timeout)
        # Lazy-loaded
        self._pyautogui = None
        self._pytesseract = None

    # ─── Dependency checks ────────────────────────────────────────────────

    def check_dependencies(self) -> dict:
        """Check all deps required for real CUA execution."""
        if sys.platform != "win32":
            return {
                "all_available": False,
                "error": "UNSUPPORTED_PLATFORM",
                "message": "CUA desktop automation requires a Windows worker node.",
                "missing": ["windows_platform"],
                "pyautogui": False,
                "pytesseract": False,
                "tesseract_binary": False,
                "gemini_vision": False,
            }

        self._pyautogui = self._pyautogui or _import_pyautogui()
        self._pytesseract = self._pytesseract or _import_pytesseract()

        from integrations.gemini_vision import gemini_vision

        pyautogui_ok = self._pyautogui is not None
        tesseract_ok = self._pytesseract is not None

        # Check tesseract binary
        tesseract_binary_ok = False
        if tesseract_ok:
            import shutil

            tesseract_binary_ok = bool(shutil.which("tesseract"))

        gemini_ok = gemini_vision.enabled

        all_ok = pyautogui_ok and gemini_ok  # tesseract is optional (Gemini does OCR)

        return {
            "all_available": all_ok,
            "pyautogui": pyautogui_ok,
            "pytesseract": tesseract_ok,
            "tesseract_binary": tesseract_binary_ok,
            "gemini_vision": gemini_ok,
            "missing": [
                k
                for k, v in {
                    "pyautogui": pyautogui_ok,
                    "google-generativeai": gemini_ok,
                }.items()
                if not v
            ],
        }

    # ─── Loop execution with platform preflight ───────────────────────────

    def execute_loop(
        self,
        objective: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        require_confirmation: bool = True,
        on_confirmation_request=None,
        context: str | None = None,
        mode: str = "control",
    ) -> CUAExecutionResult:
        """Run the desktop CUA loop on Windows.

        On non-Windows platforms, immediately fails with a structured
        UNSUPPORTED_PLATFORM result without attempting any desktop automation.
        """
        if sys.platform != "win32":
            logger.warning(
                "CUA desktop automation invoked on unsupported platform: %s (Windows required)",
                sys.platform,
            )
            return CUAExecutionResult(
                success=False,
                aborted_reason="UNSUPPORTED_PLATFORM: CUA desktop automation requires a Windows worker node.",
            )

        return super().execute_loop(
            objective=objective,
            max_steps=max_steps,
            require_confirmation=require_confirmation,
            on_confirmation_request=on_confirmation_request,
            context=context,
            mode=mode,
        )

    # ─── Platform-specific hooks ──────────────────────────────────────────

    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> str | None:
        """Capture a screenshot via pyautogui and save to audit dir."""
        if sys.platform != "win32" or not self._pyautogui:
            return None
        try:
            filename = f"step{step_num:03d}_{phase}_{uuid.uuid4().hex[:8]}.png"
            filepath = self.audit_dir / filename
            img = self._pyautogui.screenshot()
            img.save(str(filepath))

            # Upload to Supabase Storage if available
            self._upload_screenshot_to_supabase(filepath, step_num, phase)

            return str(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Screenshot capture failed: %s", exc)
            return None

    def _action_click(self, pa, action: CUAAction) -> str | None:
        """Perform a left-click at the given coordinates."""
        if action.x is None or action.y is None:
            return f"click action missing x/y: {action}"
        pa.click(action.x, action.y, timeout=self.action_timeout)
        logger.info("click(%d, %d) — %s", action.x, action.y, action.target)
        return None

    def _action_double_click(self, pa, action: CUAAction) -> str | None:
        """Perform a double-click at the given coordinates."""
        if action.x is None or action.y is None:
            return "double_click missing x/y"
        pa.doubleClick(action.x, action.y)
        return None

    def _action_right_click(self, pa, action: CUAAction) -> str | None:
        """Perform a right-click at the given coordinates."""
        if action.x is None or action.y is None:
            return "right_click missing x/y"
        pa.rightClick(action.x, action.y)
        return None

    def _action_type(self, pa, action: CUAAction) -> str | None:
        """Type text, clicking to focus first when coordinates are given."""
        if action.text is None:
            return "type action missing text"
        # If x,y given, click first to focus the input field
        if action.x is not None and action.y is not None:
            pa.click(action.x, action.y)
            time.sleep(0.2)
        # pyautogui.typewrite only supports ASCII; use write for unicode
        try:
            pa.write(action.text, interval=0.02)
        except Exception:  # noqa: BLE001
            # Fallback for non-ASCII — pyperclip via pyautogui
            pa.hotkey("ctrl", "a")
            pa.typewrite(action.text, interval=0.02)
        logger.info("type(%d chars) at (%s,%s)", len(action.text), action.x, action.y)
        return None

    def _action_hotkey(self, pa, action: CUAAction) -> str | None:
        """Press a key combination."""
        if not action.keys:
            return "hotkey missing keys"
        pa.hotkey(*action.keys)
        logger.info("hotkey(%s)", "+".join(action.keys))
        return None

    def _action_wait(self, pa, action: CUAAction) -> str | None:
        """Wait, using a poll-based wait so the failsafe stays responsive."""
        seconds = action.seconds or 1.0
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(0.1)
        logger.info("wait(%.1fs)", seconds)
        return None

    def _execute_action_hook(self, action: CUAAction, **kwargs) -> str | None:
        """Execute a single pyautogui action. Returns error string or None."""
        if sys.platform != "win32":
            return "UNSUPPORTED_PLATFORM: CUA desktop automation requires a Windows worker node."
        if not self._pyautogui:
            return "pyautogui not available"
        try:
            pa = self._pyautogui
            handlers = {
                "click": self._action_click,
                "double_click": self._action_double_click,
                "right_click": self._action_right_click,
                "type": self._action_type,
                "hotkey": self._action_hotkey,
                "wait": self._action_wait,
            }
            handler = handlers.get(action.type)
            if handler is None:
                return f"unsupported action type: {action.type}"
            return handler(pa, action)
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    def _wait_settle(self) -> None:
        """Desktop: use time.sleep to let UI settle."""
        time.sleep(0.5)

    def _cleanup_on_exit(self) -> None:
        """Desktop: no platform resources to close."""
        pass

    # ─── Desktop-specific helpers ──────────────────────────────────────────

    def _upload_screenshot_to_supabase(self, filepath, _step_num, _phase) -> None:
        """Upload screenshot to Supabase Storage (non-blocking)."""
        try:
            from integrations.supabase_integration import supabase_client

            if not supabase_client.enabled:
                return

            with open(filepath, "rb") as f:
                file_bytes = f.read()

            filename = os.path.basename(filepath)
            result = supabase_client.upload_bytes(
                bucket="screenshots",
                path=f"cua/{datetime.now(UTC).strftime('%Y%m%d')}/{filename}",
                data=file_bytes,
                content_type="image/png",
            )

            if result.get("success"):
                logger.debug("Screenshot uploaded to Supabase: %s", filename)
            else:
                logger.debug("Supabase screenshot upload failed: %s", result.get("error"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Supabase screenshot upload failed (non-critical): %s", exc)


# ─── Convenience: standalone OCR (fallback if Gemini is down) ──────────────


def ocr_screenshot(image_path: str) -> str:
    """Run Tesseract OCR on a screenshot. Returns extracted text.

    Used as a fallback when Gemini Vision is unavailable.
    """
    if sys.platform != "win32":
        return ""
    pytesseract = _import_pytesseract()
    if not pytesseract:
        return ""
    try:
        from PIL import Image

        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed: %s", exc)
        return ""


__all__ = [
    "CUAAction",
    "CUAExecutor",
    "CUAExecutionResult",
    "CUAStepResult",
    "ocr_screenshot",
]
