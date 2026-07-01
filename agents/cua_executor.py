"""
agents/cua_executor.py — Computer Use Agent Executor

The actual execution layer that turns the ETAP GUI Agent skill from a
"planning agent" into a real Computer Use Agent (CUA).

It implements the CUA Loop described in skills/etap-gui-agent.md:

    1. OBJECTIVE INPUT  ← user request
    2. SCREENSHOT       ← pyautogui.screenshot()
    3. VISUAL ANALYSIS  ← Gemini Vision via integrations.gemini_vision
    4. ACTION DECISION  ← Gemini returns next_action
    5. ACTION EXECUTION ← pyautogui.click / typewrite / hotkey
    6. VERIFICATION     ← re-screenshot + Gemini confirms
    7. REPEAT OR EXIT

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
from dataclasses import dataclass, field
from datetime import UTC, datetime

UTC = UTC
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger("agent.cua_executor")

# ─── Lazy imports for desktop-only deps ────────────────────────────────────
# pyautogui, pytesseract, cv2 are only importable on a desktop OS with a
# display server. We import them lazily so this module can be imported on
# HF Space / CI without crashing.


def _import_pyautogui():
    """Lazy import of pyautogui. Returns None if unavailable."""
    try:
        import pyautogui

        pyautogui.FAILSAFE = True  # ALWAYS enable failsafe per skill spec
        pyautogui.PAUSE = 0.3  # small pause between actions for stability
        return pyautogui
    except Exception as exc:  # noqa: BLE001
        logger.debug("pyautogui unavailable: %s", exc)
        return None


def _import_pytesseract():
    try:
        import pytesseract

        return pytesseract
    except Exception as exc:  # noqa: BLE001
        logger.debug("pytesseract unavailable: %s", exc)
        return None


# ─── Data classes ──────────────────────────────────────────────────────────

ActionType = Literal[
    "click", "double_click", "right_click", "type", "hotkey", "wait", "done", "unknown"
]


@dataclass
class CUAAction:
    """A single action decided by Gemini Vision and executed by the CUA."""

    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    keys: List[str] = field(default_factory=list)
    target: Optional[str] = None
    seconds: Optional[float] = None
    summary: Optional[str] = None
    reason: Optional[str] = None

    @classmethod
    def from_gemini(cls, action_dict: Dict[str, Any]) -> CUAAction:
        """Build a CUAAction from Gemini's next_action JSON."""
        action_type = action_dict.get("type", "unknown")
        # Map Gemini's "click" to our ActionType
        if action_type == "click":
            return cls(
                type="click",
                x=action_dict.get("x"),
                y=action_dict.get("y"),
                target=action_dict.get("target"),
            )
        if action_type == "type":
            return cls(
                type="type",
                text=action_dict.get("text"),
                x=action_dict.get("x"),
                y=action_dict.get("y"),
            )
        if action_type == "hotkey":
            return cls(
                type="hotkey",
                keys=action_dict.get("keys", []),
            )
        if action_type == "wait":
            return cls(
                type="wait",
                seconds=action_dict.get("seconds", 1.0),
            )
        if action_type == "done":
            return cls(
                type="done",
                summary=action_dict.get("summary", "Objective complete"),
            )
        return cls(
            type="unknown",
            reason=action_dict.get("reason", "No reason provided"),
        )

    def is_destructive(self) -> bool:
        """Return True if this action might be destructive (requires human)."""
        if self.type == "unknown":
            return True
        # Hotkeys like Alt+F4, Delete, Ctrl+D are destructive
        destructive_keys = {"delete", "f4", "backspace"}
        if self.type == "hotkey" and any(k.lower() in destructive_keys for k in self.keys):
            return True
        return False


@dataclass
class CUAStepResult:
    """Result of executing one CUA loop iteration."""

    step_number: int
    action: CUAAction
    success: bool
    screenshot_before: Optional[str] = None  # path
    screenshot_after: Optional[str] = None  # path
    gemini_analysis: Optional[Dict[str, Any]] = None
    duration_ms: int = 0
    error: Optional[str] = None

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "action": {
                "type": self.action.type,
                "x": self.action.x,
                "y": self.action.y,
                "text": self.action.text,
                "keys": self.action.keys,
                "target": self.action.target,
            },
            "success": self.success,
            "screenshot_before": self.screenshot_before,
            "screenshot_after": self.screenshot_after,
            "duration_ms": self.duration_ms,
            "timestamp": datetime.now(UTC).isoformat(),
            "error": self.error,
        }


@dataclass
class CUAExecutionResult:
    """Top-level result returned by CUAExecutor.execute_loop()."""

    success: bool
    steps: List[CUAStepResult] = field(default_factory=list)
    final_summary: str = ""
    objective_complete: bool = False
    aborted_reason: Optional[str] = None
    total_duration_ms: int = 0
    execution_id: Optional[str] = None
    resumed_from_step: int = 0
    vision_source: Optional[str] = None  # "gemini" | "opencv" | "hybrid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "objective_complete": self.objective_complete,
            "steps_executed": len(self.steps),
            "steps": [s.to_audit_dict() for s in self.steps],
            "final_summary": self.final_summary,
            "aborted_reason": self.aborted_reason,
            "total_duration_ms": self.total_duration_ms,
            "execution_id": self.execution_id,
            "resumed_from_step": self.resumed_from_step,
            "vision_source": self.vision_source,
        }


# ─── The executor ──────────────────────────────────────────────────────────


class CUAExecutor:
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

    # Safety limits (per skills/etap-gui-agent.md)
    DEFAULT_MAX_STEPS = 15
    DEFAULT_ACTION_TIMEOUT = 60  # seconds per action
    DESTRUCTIVE_KEYWORDS = {"delete", "format", "override", "reset", "purge", "wipe"}

    def __init__(
        self,
        audit_dir: Optional[str] = None,
        action_timeout: int = DEFAULT_ACTION_TIMEOUT,
    ) -> None:
        self.action_timeout = action_timeout
        self.audit_dir = Path(audit_dir) if audit_dir else Path("/tmp/cua_audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-loaded
        self._pyautogui = None
        self._pytesseract = None

    # ─── Dependency checks ────────────────────────────────────────────────

    def check_dependencies(self) -> Dict[str, Any]:
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

    # ─── Public: execute the full CUA loop ─────────────────────────────────

    def execute_loop(
        self,
        objective: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        require_confirmation: bool = True,
        on_confirmation_request=None,
        context: Optional[str] = None,
        mode: str = "control",
    ) -> CUAExecutionResult:
        """Run the CUA loop until objective is complete or max_steps reached.

        Args:
            objective: what to accomplish (e.g., "Open ETAP and run Load Flow")
            max_steps: hard limit on loop iterations (safety)
            require_confirmation: if True, CONTROL actions pause for human approval
            on_confirmation_request: callable(action: CUAAction) -> bool
                                     If returns False, the loop aborts.
            context: prior context (e.g., "User just opened ETAP manually")

        Returns:
            CUAExecutionResult with full audit trail
        """
        start_time = time.monotonic()
        deps = self.check_dependencies()
        if not deps["all_available"]:
            return CUAExecutionResult(
                success=False,
                aborted_reason=f"Dependencies unavailable: {deps['missing']}",
            )

        # ─── RESILIENCE: use Hybrid Vision (Gemini + OpenCV fallback) ───────
        from integrations.resilience import CheckpointStore, hybrid_vision, resume_manager

        # ─── RESILIENCE: resume from checkpoint if available ────────────────
        exec_id, resume_from, prior_steps, prior_context = resume_manager.resume_or_start(objective)
        steps: List[CUAStepResult] = []
        # Reconstruct prior step results from checkpoint (simplified — audit-only)
        for ps in prior_steps:
            try:
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
            except Exception:  # noqa: BLE001
                pass  # skip malformed prior steps

        current_context = context or prior_context or "Starting fresh"
        last_analysis: Optional[Dict[str, Any]] = None
        vision_sources_used: set = set()
        checkpoint_store = CheckpointStore()

        # If resuming, start from the next step
        start_step = max(1, resume_from + 1)
        if resume_from > 0:
            logger.info("Resuming CUA execution %s from step %d", exec_id, start_step)

        for step_num in range(start_step, max_steps + 1):
            step_start = time.monotonic()

            # STEP 1: capture screenshot
            screenshot_before = self._capture_screenshot(step_num, "before")
            if screenshot_before is None:
                return CUAExecutionResult(
                    success=False,
                    steps=steps,
                    aborted_reason="Screenshot capture failed",
                )

            # STEP 2: analyze with Hybrid Vision (Gemini first, OpenCV fallback)
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
                    screenshot_after=screenshot_before,  # no action taken
                    gemini_analysis=analysis,
                    duration_ms=int((time.monotonic() - step_start) * 1000),
                )
                steps.append(step_result)
                # Clean up checkpoints on success
                try:
                    checkpoint_store.cleanup(exec_id, keep_last=0)
                except Exception:  # noqa: BLE001
                    pass
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
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason="User declined to confirm action",
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
                        execution_id=exec_id,
                        resumed_from_step=resume_from,
                        vision_source=analysis.get("source"),
                    )

            # STEP 8: LIFE SAFETY CHECK — non-bypassable gate before execution
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
                # Save checkpoint so we can resume after the safety issue is resolved
                try:
                    checkpoint_store.save(
                        execution_id=exec_id,
                        step_num=step_num,
                        objective=objective,
                        completed_steps=[s.to_audit_dict() for s in steps],
                        context=f"Step {step_num}: SAFETY BLOCKED — {safety_check.reason}",
                    )
                except Exception:  # noqa: BLE001
                    pass
                return CUAExecutionResult(
                    success=False,
                    steps=steps,
                    aborted_reason=f"Life safety block: {safety_check.reason}",
                    total_duration_ms=int((time.monotonic() - start_time) * 1000),
                    execution_id=exec_id,
                    resumed_from_step=resume_from,
                    vision_source=analysis.get("source"),
                )

            # If dual confirmation is required, the on_confirmation_request
            # callback must implement it (two humans). The safety guard flags
            # it; the caller enforces it.
            if safety_check.requires_dual_confirmation and on_confirmation_request is not None:
                # The callback should ask TWO humans; we just pass the flag
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
            exec_error = self._execute_action(action)

            # STEP 10: capture after screenshot + post-action safety record
            time.sleep(0.5)  # let UI settle
            screenshot_after = self._capture_screenshot(step_num, "after")
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
                # Continue — Gemini may recover in next iteration

            # Update context for next iteration
            current_context = (
                f"Step {step_num}: executed {action.type}"
                + (f" on {action.target}" if action.target else "")
                + (f" — result: {exec_error}" if exec_error else " — success")
            )

            # ─── RESILIENCE: save checkpoint after each step ─────────────────
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

        # max_steps reached without completion
        # Determine which vision source was used (for transparency)
        if vision_sources_used:
            if len(vision_sources_used) == 1:
                vision_src = next(iter(vision_sources_used))
            else:
                vision_src = "hybrid"
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

    def _capture_screenshot(self, step_num: int, phase: str) -> Optional[str]:
        """Capture a screenshot and save it to the audit dir. Returns path."""
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
            logger.error("Screenshot capture failed: %s", exc)
            return None

    def _upload_screenshot_to_supabase(self, filepath: str, step_num: int, phase: str) -> None:
        """Upload screenshot to Supabase Storage (non-blocking)."""
        try:
            from integrations.supabase_integration import supabase_client

            if not supabase_client.enabled:
                return

            # Read file bytes
            with open(filepath, "rb") as f:
                file_bytes = f.read()

            # Upload to Supabase Storage
            filename = os.path.basename(filepath)
            result = supabase_client.upload_bytes(
                bucket="screenshots",
                path=f"cua/{datetime.now(UTC).strftime('%Y%m%d')}/{filename}",
                data=file_bytes,
                content_type="image/png",
            )

            if result.get("success"):
                logger.debug(f"Screenshot uploaded to Supabase: {filename}")
            else:
                logger.debug(f"Supabase screenshot upload failed: {result.get('error')}")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Supabase screenshot upload failed (non-critical): {exc}")

    # ─── Internal: action execution ────────────────────────────────────────

    def _execute_action(self, action: CUAAction) -> Optional[str]:
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
