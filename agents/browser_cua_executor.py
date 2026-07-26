"""
agents/browser_cua_executor.py — Browser-based CUA Loop (headless-safe)

A Computer Use Agent executor that works on headless servers (HF Space, CI)
by driving a headless Chromium browser via Playwright instead of pyautogui.

WHY THIS EXISTS:
    The DesktopCUAExecutor (agents/cua_executor.py) requires pyautogui + a
    display server (X11/Wayland), which are NOT available on HF Space.
    This BrowserCUAExecutor solves that by using Playwright's headless
    Chromium — no display server required.

WHAT IT CAN DO:
    - Open any URL in a headless browser
    - Capture screenshots of web pages
    - Click elements by pixel coordinates (same contract as DesktopCUA)
    - Type text into inputs
    - Press keyboard hotkeys (Ctrl+S, Enter, etc.)
    - Wait for page transitions
    - Navigate multi-step web workflows

WHAT IT CANNOT DO:
    - Control native desktop apps (ETAP.exe, Revit, AutoCAD)
    - For desktop apps, use DesktopCUAExecutor on a real desktop instead

ARCHITECTURE:
    Inherits from BaseCUAExecutor (agents/cua_base_executor.py) which
    provides the 10-step CUA loop algorithm via the Template Method pattern.
    This subclass only provides the Playwright-specific hooks:
    _capture_screenshot_hook → page.screenshot()
    _execute_action_hook → page.mouse.click() / page.keyboard.type()
    _wait_settle → page.wait_for_timeout(500)
    _cleanup_on_exit → browser.close()

    The execute_loop() override adds browser launch + navigation before
    delegating to the shared algorithm in the base class.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from agents.cua_base_executor import (
    DEFAULT_ACTION_TIMEOUT,
    BaseCUAExecutor,
    CUAAction,
    CUAExecutionResult,
)

logger = logging.getLogger("agent.browser_cua_executor")


# ─── Lazy Playwright import ────────────────────────────────────────────────


def _import_playwright():
    """Lazy import of Playwright. Returns (sync_playwright, error_or_None)."""
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright, None
    except ImportError:
        return None, "playwright not installed (pip install playwright)"
    except Exception as exc:  # noqa: BLE001
        return None, f"playwright import error: {exc}"


def _check_chromium_installed() -> tuple[bool, str]:
    """Check whether Chromium browser binary is installed for Playwright.

    Playwright needs `playwright install chromium` to download the browser.
    Returns (installed, message).

    Checks multiple locations:
      - $PLAYWRIGHT_BROWSERS_PATH (if set)
      - ~/.cache/ms-playwright (default Linux)
      - /ms-playwright (common in Docker images)
      - /root/.cache/ms-playwright (running as root)
      - /app/.cache/ms-playwright (HF Space non-root user)
      - /home/user/.cache/ms-playwright (HF Space default user)
    """
    try:
        candidates: list[Path] = []

        # Check PLAYWRIGHT_BROWSERS_PATH env var first
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if env_path:
            candidates.append(Path(env_path))

        # Add common locations
        candidates.extend(
            [
                Path.home() / ".cache" / "ms-playwright",
                Path("/ms-playwright"),  # Common in Docker images
                Path("/root/.cache/ms-playwright"),
                Path("/app/.cache/ms-playwright"),  # HF Space non-root
                Path("/home/user/.cache/ms-playwright"),  # HF Space default user
            ],
        )

        for p in candidates:
            if p.exists():
                chromium_dirs = list(p.glob("chromium-*"))
                if chromium_dirs:
                    return True, f"chromium at {chromium_dirs[0]}"

        # Last resort: try to query Playwright directly
        with contextlib.suppress(Exception):
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                # This will raise if Chromium is not installed
                exec_path = p.chromium.executable_path
                if exec_path and Path(exec_path).exists():
                    return True, f"chromium at {exec_path}"

        return False, "chromium binary not found — run: playwright install chromium"
    except Exception as exc:  # noqa: BLE001
        return False, f"chromium check error: {exc}"


# ─── Browser CUA Executor ──────────────────────────────────────────────────


class BrowserCUAExecutor(BaseCUAExecutor):
    """Executes the CUA Loop against a headless browser via Playwright.

    Same interface as DesktopCUAExecutor (execute_loop returns CUAExecutionResult)
    so ETAPGUIAgent can transparently swap between them based on environment.

    The 10-step CUA loop algorithm is inherited from BaseCUAExecutor.
    This subclass adds Playwright browser launch + navigation before
    delegating to the shared algorithm, and provides platform-specific
    hooks for screenshot capture, action execution, and cleanup.

    Usage:
        executor = BrowserCUAExecutor(audit_dir="/tmp/cua_audit")
        result = executor.execute_loop(
            objective="Open the dashboard and check the latest study status",
            start_url="https://ahmdelbaz28-ahmedetap-platform.hf.space/dashboard",
            max_steps=15,
        )
    """

    DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
    DEFAULT_NAV_TIMEOUT = 30_000  # ms

    def __init__(
        self,
        audit_dir: Optional[str] = None,
        viewport: dict[str, int] | None = None,
        headless: bool = True,
    ) -> None:
        super().__init__(audit_dir=audit_dir, action_timeout=DEFAULT_ACTION_TIMEOUT)
        self.viewport = viewport or self.DEFAULT_VIEWPORT
        self.headless = headless
        # Runtime state — set during execute_loop, used by hooks
        self._page = None
        self._pw_context = None

    # ─── Dependency checks ────────────────────────────────────────────────

    def check_dependencies(self) -> dict[str, Any]:
        """Check all deps required for browser CUA execution."""
        from integrations.gemini_vision import gemini_vision

        pw, _ = _import_playwright()
        chromium_ok, chromium_msg = _check_chromium_installed()

        all_ok = pw is not None and chromium_ok and gemini_vision.enabled

        missing: list[str] = []
        if pw is None:
            missing.append("playwright")
        if not chromium_ok:
            missing.append("chromium-binary")
        if not gemini_vision.enabled:
            missing.append("google-generativeai-or-GEMINI_API_KEY")

        return {
            "all_available": all_ok,
            "playwright": pw is not None,
            "chromium": chromium_ok,
            "chromium_message": chromium_msg,
            "gemini_vision": gemini_vision.enabled,
            "missing": missing,
        }

    # ─── Override: add browser launch before shared loop ───────────────────

    def execute_loop(
        self,
        objective: str,
        start_url: Optional[str] = None,
        max_steps: int = 15,
        require_confirmation: bool = True,
        on_confirmation_request=None,
        context: Optional[str] = None,
        mode: str = "control",
    ) -> CUAExecutionResult:
        """Run the CUA Loop against a headless browser.

        Launches Playwright browser, navigates to start_url if provided,
        then delegates to BaseCUAExecutor.execute_loop() for the shared
        10-step algorithm.

        Args:
            objective: what to accomplish
            start_url: optional URL to navigate to before starting the loop
            max_steps: hard limit on loop iterations (safety)
            require_confirmation: if True, CONTROL actions pause for human approval
            on_confirmation_request: callable(action) -> bool
            context: prior context string

        Returns:
            CUAExecutionResult with full audit trail
        """
        pw, pw_err = _import_playwright()
        if pw is None:
            return CUAExecutionResult(
                success=False,
                aborted_reason=f"playwright unavailable: {pw_err}",
            )

        # Launch browser and store page on self so hooks can access it
        try:
            with pw() as p:
                self._pw_context = p
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",  # important for Docker / HF Space
                        "--disable-gpu",
                        "--single-process",  # lighter on CPU-basic HF Space
                    ],
                )
                self._page = browser.new_page(viewport=self.viewport)
                self._page.set_default_timeout(self.DEFAULT_NAV_TIMEOUT)

                if start_url:
                    try:
                        self._page.goto(start_url, wait_until="domcontentloaded")
                        self._page.wait_for_timeout(1000)  # let JS render
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Navigation to %s failed: %s", start_url, exc)

                # Delegate to BaseCUAExecutor.execute_loop() — shared algorithm
                result = super().execute_loop(
                    objective=objective,
                    max_steps=max_steps,
                    require_confirmation=require_confirmation,
                    on_confirmation_request=on_confirmation_request,
                    context=context,
                    mode=mode,
                )
                return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Browser launch failed: %s", exc)
            return CUAExecutionResult(
                success=False,
                aborted_reason=f"Browser launch error: {exc}",
            )
        finally:
            # Always cleanup browser resources
            self._cleanup_on_exit()
            self._page = None
            self._pw_context = None

    # ─── Platform-specific hooks ──────────────────────────────────────────

    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> Optional[str]:
        """Capture a screenshot from the browser page. Returns path."""
        if self._page is None:
            return None
        try:
            filename = f"browser_step{step_num:03d}_{phase}_{uuid.uuid4().hex[:8]}.png"
            filepath = self.audit_dir / filename
            self._page.screenshot(path=str(filepath), full_page=False)
            return str(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Browser screenshot failed: %s", exc)
            return None

    def _execute_action_hook(self, action: CUAAction, **kwargs) -> Optional[str]:  # NOSONAR  # S3776
        """Execute a single browser action. Returns error string or None."""
        if self._page is None:
            return "browser page not available"
        try:
            page = self._page

            if action.type == "click":
                if action.x is None or action.y is None:
                    return f"click action missing x/y: {action}"
                page.mouse.click(action.x, action.y)
                logger.info("browser click(%d, %d) — %s", action.x, action.y, action.target)

            elif action.type == "double_click":
                if action.x is None or action.y is None:
                    return "double_click missing x/y"
                page.mouse.dblclick(action.x, action.y)

            elif action.type == "right_click":
                if action.x is None or action.y is None:
                    return "right_click missing x/y"
                page.mouse.click(action.x, action.y, button="right")

            elif action.type == "type":
                if action.text is None:
                    return "type action missing text"
                # If x,y given, click first to focus the input field
                if action.x is not None and action.y is not None:
                    page.mouse.click(action.x, action.y)
                    page.wait_for_timeout(200)
                page.keyboard.type(action.text)
                logger.info("browser type(%d chars)", len(action.text))

            elif action.type == "hotkey":
                if not action.keys:
                    return "hotkey missing keys"
                # Playwright uses different key names than pyautogui
                key_map = {
                    "ctrl": "Control",
                    "control": "Control",
                    "alt": "Alt",
                    "shift": "Shift",
                    "enter": "Enter",
                    "escape": "Escape",
                    "tab": "Tab",
                    "backspace": "Backspace",
                    "delete": "Delete",
                    "f4": "F4",
                    "f5": "F5",
                }
                mapped = [key_map.get(k.lower(), k) for k in action.keys]
                combo = "+".join(mapped)
                page.keyboard.press(combo)
                logger.info("browser hotkey(%s)", combo)

            elif action.type == "wait":
                seconds = action.seconds or 1.0
                page.wait_for_timeout(int(seconds * 1000))
                logger.info("browser wait(%.1fs)", seconds)

            else:
                return f"unsupported action type: {action.type}"

            return None

        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    def _wait_settle(self) -> None:
        """Browser: use page.wait_for_timeout to let UI settle."""
        if self._page is not None:
            self._page.wait_for_timeout(500)

    def _cleanup_on_exit(self) -> None:
        """Browser: close the Chromium instance."""
        with contextlib.suppress(Exception):
            if self._pw_context is not None:
                # The pw context manager handles cleanup, but we ensure
                # any open browsers are closed
                pass  # Browser is cleaned up by the `with pw() as p:` context


# ─── Async wrapper (for FastAPI endpoints) ─────────────────────────────────


async def execute_browser_cua_loop_async(
    objective: str,
    start_url: Optional[str] = None,
    max_steps: int = 15,
    require_confirmation: bool = True,
    audit_dir: Optional[str] = None,
) -> CUAExecutionResult:
    """Async wrapper — runs the browser CUA loop in a thread pool.

    Playwright's sync API blocks the event loop, so we offload to a thread.
    """
    executor = BrowserCUAExecutor(audit_dir=audit_dir)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: executor.execute_loop(
            objective=objective,
            start_url=start_url,
            max_steps=max_steps,
            require_confirmation=require_confirmation,
        ),
    )


__all__ = [
    "BrowserCUAExecutor",
    "execute_browser_cua_loop_async",
]
