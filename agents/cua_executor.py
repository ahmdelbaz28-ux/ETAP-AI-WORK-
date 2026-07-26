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
import time
import uuid
from datetime import UTC, datetime

from agents.cua_base_executor import (
    BaseCUAExecutor,
    CUAAction,
    CUAExecutionResult,
    CUAStepResult,
    DEFAULT_ACTION_TIMEOUT,
)

logger = logging.getLogger("agent.cua_executor")

# ─── Lazy imports for desktop-only deps ────────────────────────────────────
# pyautogui, pytesseract, cv2 are only importable on a desktop OS with a
# display server. We import them lazily so this module can be imported on
# headless servers without crashing.


def _import_pyautogui():
    """Lazily import pyautogui; return None on headless / missing."""
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
        executor = CUAExecutor(audit_dir="/tmp/cua_audit")
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

    # ─── Platform-specific hooks ──────────────────────────────────────────

    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> str | None:
        """Capture a screenshot via pyautogui and save to audit dir."""
        if not self._pyautogui:
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

    def _execute_action_hook(self, action: CUAAction, **kwargs) -> str | None:  # NOSONAR — S3776
        """Execute a single pyautogui action. Returns error string or None."""
        if not self._pyautogui:
            return "pyautogui not available"
        try:
            pa = self._pyautogui

            if action.type == "click":
                if action.x is None or action.y is None:
                    return f"click action missing x/y: {action}"
                pa.click(action.x, action.y, timeout=self.action_timeout)
                logger.info("click(%d, %d) — %s", action.x, action.y, action.target)

            elif action.type == "double_click":
                if action.x is None or action.y is None:
                    return "double_click missing x/y"
                pa.doubleClick(action.x, action.y)

            elif action.type == "right_click":
                if action.x is None or action.y is None:
                    return "right_click missing x/y"
                pa.rightClick(action.x, action.y)

            elif action.type == "type":
                if action.text is None:
                    return "type action missing text"
                # If x,y given, click first to focus the input field
                if action.x is not None and action.y is not None:
                    pa.click(action.x, action.y)
                    time.sleep(0.2)
                # pyautogui.typewrite only supports ASCII; use write for unicode
                try:
                    pa.write(action.text, interval=0.02)
                except Exception:
                    # Fallback for non-ASCII — pyperclip via pyautogui
                    pa.hotkey("ctrl", "a")
                    pa.typewrite(action.text, interval=0.02)
                logger.info("type(%d chars) at (%s,%s)", len(action.text), action.x, action.y)

            elif action.type == "hotkey":
                if not action.keys:
                    return "hotkey missing keys"
                pa.hotkey(*action.keys)
                logger.info("hotkey(%s)", "+".join(action.keys))

            elif action.type == "wait":
                seconds = action.seconds or 1.0
                # Use poll-based wait so failsafe stays responsive
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    time.sleep(0.1)
                logger.info("wait(%.1fs)", seconds)

            else:
                return f"unsupported action type: {action.type}"

            return None

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
                logger.debug("Supabase screenshot upload failed: %s", result.get('error'))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Supabase screenshot upload failed (non-critical): %s", exc)


# ─── Convenience: standalone OCR (fallback if Gemini is down) ──────────────


def ocr_screenshot(image_path: str) -> str:
    """Run Tesseract OCR on a screenshot. Returns extracted text.

    Used as a fallback when Gemini Vision is unavailable.
    """
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
