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
    User request → ETAPGUIAgent.execute_cua_loop()
                       ↓
                  Auto-detect environment:
                    - pyautogui + display available → DesktopCUAExecutor
                    - Playwright available         → BrowserCUAExecutor (THIS)
                    - Neither available             → Format U fallback

    BrowserCUAExecutor.execute_loop():
      1. Launch headless Chromium via Playwright
      2. If start_url provided, navigate to it
      3. Loop:
         a. page.screenshot() → send to Gemini Vision
         b. Gemini returns next_action {click(x,y) | type(text) | Union[hotkey, done}]
         c. page.mouse.click(x,y) / page.keyboard.type(text) / page.keyboard.press(key)
         d. Re-screenshot for verification
      4. Close browser, return CUAExecutionResult

References:
    - skills/etap-gui-agent.md (CUA Loop spec)
    - integrations/gemini_vision.py (Visual perception)
    - agents/cua_executor.py (DesktopCUAExecutor — sibling)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# Reuse the dataclasses from the desktop executor — same contract
from agents.cua_executor import CUAAction, CUAExecutionResult, CUAStepResult

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


class BrowserCUAExecutor:
    """Executes the CUA Loop against a headless browser via Playwright.

    Same interface as DesktopCUAExecutor (execute_loop returns CUAExecutionResult)
    so ETAPGUIAgent can transparently swap between them based on environment.

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
        self.audit_dir = Path(audit_dir) if audit_dir else Path("/tmp/cua_audit")  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.viewport = viewport or self.DEFAULT_VIEWPORT
        self.headless = headless

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

    # ─── Public: execute the full CUA loop ─────────────────────────────────

    def execute_loop(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
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

        Args:
            objective: what to accomplish (e.g., "Navigate to Studies and run Load Flow")
            start_url: optional URL to navigate to before starting the loop
            max_steps: hard limit on loop iterations (safety)
            require_confirmation: if True, CONTROL actions pause for human approval
            on_confirmation_request: callable(action) -> bool
            context: prior context string

        Returns:
            CUAExecutionResult with full audit trail (same as DesktopCUAExecutor)
        """
        start_time = time.monotonic()
        deps = self.check_dependencies()
        if not deps["all_available"]:
            return CUAExecutionResult(
                success=False,
                aborted_reason=f"Browser CUA deps unavailable: {deps['missing']}",
            )

        # ─── RESILIENCE: Hybrid Vision (Gemini + OpenCV fallback) ──────────
        from integrations.resilience import CheckpointStore, hybrid_vision, resume_manager

        # ─── RESILIENCE: resume from checkpoint if available ────────────────
        exec_id, resume_from, prior_steps, prior_context = resume_manager.resume_or_start(objective)
        steps: list[CUAStepResult] = []
        # Reconstruct prior steps from checkpoint
        for ps in prior_steps:
            with contextlib.suppress(Exception):
                step = CUAStepResult(
                    step_number=ps.get("step", 0),
                    action=CUAAction(
                        type=ps.get("action", {}).get("type", "unknown"),
                        x=ps.get("action", {}).get("x"),
                        y=ps.get("action", {}).get("y"),
                        text=ps.get("action", {}).get("text"),
                        keys=ps.get("action", {}).get("keys", []),
                        target=ps.get("action", {}).get("target"),
                    ),
                    success=ps.get("success", False),
                    screenshot_before=ps.get("screenshot_before"),
                    screenshot_after=ps.get("screenshot_after"),
                    duration_ms=ps.get("duration_ms", 0),
                    error=ps.get("error"),
                )
                steps.append(step)

        current_context = context or prior_context or "Starting browser CUA"
        last_analysis: dict[str, Any] | None = None
        vision_sources_used: set = set()
        checkpoint_store = CheckpointStore()
        start_step = max(1, resume_from + 1)
        if resume_from > 0:
            logger.info("Resuming browser CUA execution %s from step %d", exec_id, start_step)

        pw, _ = _import_playwright()
        if pw is None:  # defensive — already checked above
            return CUAExecutionResult(success=False, aborted_reason="playwright unavailable")

        try:
            with pw() as p:
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
                page = browser.new_page(viewport=self.viewport)
                page.set_default_timeout(self.DEFAULT_NAV_TIMEOUT)

                if start_url:
                    try:
                        page.goto(start_url, wait_until="domcontentloaded")
                        page.wait_for_timeout(1000)  # let JS render
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Navigation to %s failed: %s", start_url, exc)

                # Main CUA loop — start from resume point
                for step_num in range(start_step, max_steps + 1):
                    step_start = time.monotonic()

                    # STEP 1: capture screenshot
                    screenshot_before = self._capture_screenshot(page, step_num, "before")
                    if screenshot_before is None:
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason="Screenshot capture failed",
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                        )

                    # STEP 2: analyze with Hybrid Vision (Gemini + OpenCV fallback)
                    analysis = hybrid_vision.analyze_screenshot(
                        image=screenshot_before,
                        objective=objective,
                        context=current_context,
                    )
                    if analysis and "source" in analysis:
                        vision_sources_used.add(analysis["source"])
                    if not analysis or "error" in analysis:
                        err = (analysis or {}).get("error", "unknown")
                        msg = (analysis or {}).get("message", "")
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=CUAAction(type="unknown", reason=msg or err),
                            success=False,
                            screenshot_before=screenshot_before,
                            error=f"Hybrid Vision error: {err} — {msg}",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason=f"Hybrid Vision failed at step {step_num}: {err}",
                            total_duration_ms=int((time.monotonic() - step_start) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                        )

                    last_analysis = analysis

                    # STEP 3: build action
                    action = CUAAction.from_gemini(analysis.get("next_action", {}))

                    # STEP 4: check for completion
                    if action.type == "done":
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=True,
                            screenshot_before=screenshot_before,
                            screenshot_after=screenshot_before,
                            gemini_analysis=analysis,
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        browser.close()
                        # Cleanup is best effort — never fail the success path
                        # because of a checkpoint cleanup error.
                        with contextlib.suppress(Exception):
                            checkpoint_store.cleanup(exec_id, keep_last=0)
                        return CUAExecutionResult(
                            success=True,
                            steps=steps,
                            final_summary=action.summary or "Objective complete",
                            objective_complete=True,
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # STEP 5: check for unknown / blocked
                    if action.type == "unknown":
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error=action.reason,
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        browser.close()
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason=f"Vision could not determine action: {action.reason}",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # STEP 6: safety check — destructive actions
                    if action.is_destructive():
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error="Destructive action blocked by safety rule",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        browser.close()
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason="Destructive action requires human intervention",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # STEP 7: human confirmation for CONTROL actions
                    if require_confirmation and on_confirmation_request is not None:
                        approved = on_confirmation_request(action)
                        if not approved:
                            step_result = CUAStepResult(
                                step_number=step_num,
                                action=action,
                                success=False,
                                screenshot_before=screenshot_before,
                                gemini_analysis=analysis,
                                error="User did not confirm action",
                                duration_ms=int((time.monotonic() - step_start) * 1000),
                            )
                            steps.append(step_result)
                            browser.close()
                            return CUAExecutionResult(
                                success=False,
                                steps=steps,
                                aborted_reason="User declined to confirm action",
                                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                                execution_id=exec_id,
                                resumed_from_step=resume_from,
                                vision_source=analysis.get("source"),
                            )

                    # STEP 8: LIFE SAFETY CHECK — non-bypassable gate
                    from agents.life_safety import life_safety_guard

                    safety_check = life_safety_guard.pre_action_check(
                        action=action,
                        screenshot_before=screenshot_before,
                        gemini_analysis=analysis,
                        vision_source=analysis.get("source", "gemini"),
                        mode=mode,
                    )
                    if safety_check.blocked:
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error=f"SAFETY BLOCKED: {safety_check.reason}",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        # Save checkpoint (best effort) so we can resume after
                        # the safety issue is resolved.
                        with contextlib.suppress(Exception):
                            checkpoint_store.save(
                                execution_id=exec_id,
                                step_num=step_num,
                                objective=objective,
                                completed_steps=[s.to_audit_dict() for s in steps],
                                context=f"Step {step_num}: SAFETY BLOCKED — {safety_check.reason}",
                            )
                        browser.close()
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason=f"Life safety block: {safety_check.reason}",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # Dual confirmation for protection-setting changes
                    if (
                        safety_check.requires_dual_confirmation
                        and on_confirmation_request is not None
                    ):
                        approved = on_confirmation_request(action)
                        if not approved:
                            step_result = CUAStepResult(
                                step_number=step_num,
                                action=action,
                                success=False,
                                screenshot_before=screenshot_before,
                                gemini_analysis=analysis,
                                error="Dual confirmation not obtained for protection-setting change",
                                duration_ms=int((time.monotonic() - step_start) * 1000),
                            )
                            steps.append(step_result)
                            browser.close()
                            return CUAExecutionResult(
                                success=False,
                                steps=steps,
                                aborted_reason="Dual confirmation required (life-safety setting)",
                                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                                execution_id=exec_id,
                                resumed_from_step=resume_from,
                                vision_source=analysis.get("source"),
                            )

                    # STEP 9: execute the action (passed safety check)
                    exec_error = self._execute_browser_action(page, action)

                    # STEP 10: capture after screenshot + post-action safety record
                    page.wait_for_timeout(500)  # let UI settle
                    screenshot_after = self._capture_screenshot(page, step_num, "after")
                    life_safety_guard.post_action_record(
                        action=action,
                        screenshot_after=screenshot_after,
                        pre_check=safety_check,
                        exec_error=exec_error,
                    )

                    step_result = CUAStepResult(
                        step_number=step_num,
                        action=action,
                        success=exec_error is None,
                        screenshot_before=screenshot_before,
                        screenshot_after=screenshot_after,
                        gemini_analysis=analysis,
                        error=exec_error,
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                    )
                    steps.append(step_result)

                    if exec_error:
                        logger.warning("Step %d failed: %s", step_num, exec_error)

                    # Update context for next iteration
                    current_context = (
                        f"Step {step_num}: executed {action.type}"
                        + (f" on {action.target}" if action.target else "")
                        + (f" — result: {exec_error}" if exec_error else " — success")
                    )

                    # ─── RESILIENCE: save checkpoint after each step ─────────
                    try:
                        checkpoint_store.save(
                            execution_id=exec_id,
                            step_num=step_num,
                            objective=objective,
                            completed_steps=[s.to_audit_dict() for s in steps],
                            context=current_context,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Checkpoint save failed (non-critical): %s", exc)

                browser.close()

        except Exception as exc:  # noqa: BLE001
            logger.exception("BrowserCUAExecutor failed")
            # ─── RESILIENCE: checkpoint was already saved, so user can resume ─
            return CUAExecutionResult(
                success=False,
                steps=steps,
                aborted_reason=f"Browser crashed: {type(exc).__name__}: {exc}",
                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                execution_id=exec_id,
                resumed_from_step=resume_from,
            )

        # max_steps reached without completion
        if vision_sources_used:
            vision_src = (
                next(iter(vision_sources_used)) if len(vision_sources_used) == 1 else "hybrid"
            )
        else:
            vision_src = None
        return CUAExecutionResult(
            success=False,
            steps=steps,
            aborted_reason=f"Reached max_steps={max_steps} without objective_complete",
            final_summary=last_analysis.get("description", "") if last_analysis else "",
            total_duration_ms=int((time.monotonic() - start_time) * 1000),
            execution_id=exec_id,
            resumed_from_step=resume_from,
            vision_source=vision_src,
        )

    # ─── Internal: screenshot capture ──────────────────────────────────────

    def _capture_screenshot(self, page, step_num: int, phase: str) -> Optional[str]:
        """Capture a screenshot from the browser page. Returns path."""
        try:
            filename = f"browser_step{step_num:03d}_{phase}_{uuid.uuid4().hex[:8]}.png"
            filepath = self.audit_dir / filename
            page.screenshot(path=str(filepath), full_page=False)
            return str(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Browser screenshot failed: %s", exc)
            return None

    # ─── Internal: browser action execution ────────────────────────────────

    @staticmethod
    def _execute_browser_action(page, action: CUAAction) -> Optional[str]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Execute a single browser action. Returns error string or None."""
        try:
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
                # e.g., "ctrl" → "Control", "s" → "s"
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
                # For combos like Ctrl+S, use press with +
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
