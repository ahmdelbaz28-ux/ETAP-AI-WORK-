"""
agents/cua_base_executor.py — Base CUA Executor (Template Method pattern)

Extracts the shared CUA loop algorithm from DesktopCUAExecutor and
BrowserCUAExecutor into a single abstract base class.  The 10-step loop
(objective → screenshot → visual analysis → action decision → safety
checks → execution → verification → repeat/exit) is identical across both
executors; only the platform-specific hooks differ:

    _capture_screenshot_hook  → pyautogui.screenshot() vs page.screenshot()
    _execute_action_hook      → pyautogui.click/type/hotkey vs page.mouse/keyboard
    _wait_settle              → time.sleep(0.5) vs page.wait_for_timeout(500)
    _cleanup_on_exit          → no-op vs browser.close()

Data classes (CUAAction, CUAStepResult, CUAExecutionResult, ActionType)
are centralized here so both executors import from a single canonical
source instead of the previous chain:
    browser_cua_executor → cua_executor → (dataclasses)

Usage:
    class DesktopCUAExecutor(BaseCUAExecutor):
        def _capture_screenshot_hook(self, step_num, phase, **kwargs): ...
        def _execute_action_hook(self, action, **kwargs): ...
        def _wait_settle(self): ...
        def _cleanup_on_exit(self): ...
        def check_dependencies(self): ...
"""

from __future__ import annotations

import abc
import contextlib
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("agent.cua_base_executor")

# ─── Shared constants ────────────────────────────────────────────────────────

DEFAULT_MAX_STEPS = 15
DEFAULT_ACTION_TIMEOUT = 60  # seconds per action

# ─── Data classes (centralized) ─────────────────────────────────────────────

ActionType = Literal[
    "click",
    "double_click",
    "right_click",
    "type",
    "hotkey",
    "wait",
    "done",
    "unknown",
]


@dataclass
class CUAAction:
    """A single action decided by Gemini Vision and executed by the CUA."""

    type: ActionType
    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: list[str] = field(default_factory=list)
    target: str | None = None
    seconds: float | None = None
    summary: str | None = None
    reason: str | None = None

    @classmethod
    def from_gemini(cls, action_dict: dict[str, Any]) -> CUAAction:
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
                target=action_dict.get("target"),
            )
        if action_type == "hotkey":
            return cls(
                type="hotkey",
                keys=action_dict.get("keys", []),
                target=action_dict.get("target"),
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
        return bool(self.type == "hotkey" and any(k.lower() in destructive_keys for k in self.keys))


@dataclass
class ControlValidationResult:
    """Result of control action pre-validation before operator confirmation."""

    valid: bool
    reason: str = ""
    target_exists: bool = True
    within_envelope: bool = True
    interlock_ok: bool = True
    destructive_refused: bool = False
    suggested_value: Any = None
    advisory: str = "GO"  # "GO" or "NO-GO"

    @property
    def program_suggestion(self) -> dict[str, Any]:
        return {
            "recommended_value": self.suggested_value,
            "advisory": self.advisory,
            "validation_status": "PASSED" if self.valid else "FAILED",
        }

    @property
    def risk_note(self) -> str:
        return f"Single-operator validated self-confirmation (advisory: {self.advisory})"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfirmationPayload(dict):
    """Payload delivered to on_confirmation_request in validated self-confirmation mode."""

    def __init__(
        self,
        action: CUAAction,
        target: str | None,
        value: Any,
        validation_results: dict[str, Any],
        program_suggestion: dict[str, Any],
        risk_note: str,
        override_reason: str | None = None,
        overridden: bool = False,
        decided_by_user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            action=action,
            target=target,
            value=value,
            validation_results=validation_results,
            program_suggestion=program_suggestion,
            risk_note=risk_note,
            override_reason=override_reason,
            overridden=overridden,
            decided_by_user_id=decided_by_user_id,
            **kwargs,
        )
        self.action = action
        self.target = target
        self.value = value
        self.validation_results = validation_results
        self.program_suggestion = program_suggestion
        self.risk_note = risk_note
        self.override_reason = override_reason
        self.overridden = overridden
        self.decided_by_user_id = decided_by_user_id

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'ConfirmationPayload' object has no attribute '{name}'") from None

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        self[name] = value

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        super().__setattr__(key, value)

    @property
    def type(self) -> str:
        return self.action.type

    @property
    def text(self) -> str | None:
        return self.action.text

    @property
    def keys(self) -> list[str]:
        return self.action.keys

    @property
    def x(self) -> int | None:
        return self.action.x

    @property
    def y(self) -> int | None:
        return self.action.y

    def is_destructive(self) -> bool:
        return self.action.is_destructive()


def validate_control_action(
    action: CUAAction,
    gemini_analysis: dict[str, Any] | None = None,
    safety_check: Any = None,
) -> ControlValidationResult:
    """Validate a control action before presenting it for operator self-confirmation.

    Checks:
      1. Target element exists on screen or model (non-empty, recognized target).
      2. Value within safe envelope for the action type.
      3. No conflicting interlock state.
      4. Destructive-dialog class still hard-refused.
    """
    from agents.life_safety import LETHAL_TARGET_PATTERNS

    target_raw = getattr(action, "target", None)
    target_str = (target_raw or "").strip()
    target_lower = target_str.lower()
    action_text = (getattr(action, "text", "") or "").strip()
    action_text_lower = action_text.lower()

    # 1. Target existence check
    if not target_str or target_lower in ("unknown", "none", "null", "undefined"):
        return ControlValidationResult(
            valid=False,
            reason=f"Target element does not exist or is unknown: {target_raw!r}",
            target_exists=False,
            advisory="NO-GO",
        )

    if getattr(action, "target_exists", None) is False:
        return ControlValidationResult(
            valid=False,
            reason=f"Target element does not exist on screen/model: {target_raw!r}",
            target_exists=False,
            advisory="NO-GO",
        )

    # 2. Destructive-dialog class hard-refusal
    if action.is_destructive():
        return ControlValidationResult(
            valid=False,
            reason=f"Destructive dialog / hotkey action class hard-refused: {action.type}",
            destructive_refused=True,
            advisory="NO-GO",
        )

    for pat in LETHAL_TARGET_PATTERNS:
        if pat in target_lower or pat in action_text_lower:
            return ControlValidationResult(
                valid=False,
                reason=f"Destructive operation pattern '{pat}' is hard-refused for auto-execution",
                destructive_refused=True,
                advisory="NO-GO",
            )

    # 3. Interlock check
    if ("earth" in target_lower or "ground" in target_lower) and any(
        k in target_lower or k in action_text_lower for k in ("close", "closed", "enable")
    ):
        if not getattr(action, "is_deenergized", False):
            return ControlValidationResult(
                valid=False,
                reason="Conflicting interlock state: grounding switch cannot close while circuit is in service",
                interlock_ok=False,
                advisory="NO-GO",
            )

    # 4. Value envelope check
    val_raw = getattr(action, "value", None)
    if val_raw is None and action.text:
        val_raw = action.text

    num_val: float | None = None
    if val_raw is not None:
        try:
            cleaned = (
                str(val_raw)
                .replace("p.u.", "")
                .replace("pu", "")
                .replace("kV", "")
                .replace("V", "")
                .replace("Hz", "")
                .replace("MW", "")
                .replace("A", "")
                .strip()
            )
            num_val = float(cleaned)
        except (ValueError, TypeError):
            pass

    suggested_val: Any = None

    # Custom envelope override if specified on action
    envelope = getattr(action, "envelope", None)
    if envelope and isinstance(envelope, dict) and num_val is not None:
        min_v = envelope.get("min")
        max_v = envelope.get("max")
        if (min_v is not None and num_val < min_v) or (max_v is not None and num_val > max_v):
            return ControlValidationResult(
                valid=False,
                reason=f"Value {num_val} is outside safe operating envelope [{min_v}, {max_v}]",
                within_envelope=False,
                suggested_value=(min_v + max_v) / 2 if (min_v is not None and max_v is not None) else min_v,
                advisory="NO-GO",
            )

    # Domain envelopes
    # Voltage (p.u. or kV)
    if any(k in target_lower or k in action_text_lower for k in ("voltage", "v_bus", "p.u.", "pu", "vset")):
        suggested_val = 1.0
        if num_val is not None:
            if num_val > 5.0:  # kV scale
                if num_val < 0.0 or num_val > 765.0:
                    return ControlValidationResult(
                        valid=False,
                        reason=f"Voltage value {num_val} kV is outside safe physical limits [0, 765]",
                        within_envelope=False,
                        suggested_value=suggested_val,
                        advisory="NO-GO",
                    )
            else:  # p.u. scale
                if num_val < 0.80 or num_val > 1.20:
                    return ControlValidationResult(
                        valid=False,
                        reason=f"Voltage value {num_val} p.u. is outside safe operating envelope [0.80, 1.20]",
                        within_envelope=False,
                        suggested_value=suggested_val,
                        advisory="NO-GO",
                    )

    # Tap position
    elif "tap" in target_lower or "tap" in action_text_lower:
        suggested_val = 0
        if num_val is not None:
            if num_val < -16.0 or num_val > 33.0:
                return ControlValidationResult(
                    valid=False,
                    reason=f"Tap position {num_val} is outside safe operating envelope [-16, 16] / [1, 33]",
                    within_envelope=False,
                    suggested_value=suggested_val,
                    advisory="NO-GO",
                )

    # Frequency
    elif any(k in target_lower or k in action_text_lower for k in ("frequency", "freq", "hz")):
        suggested_val = 50.0
        if num_val is not None:
            if num_val < 45.0 or num_val > 65.0:
                return ControlValidationResult(
                    valid=False,
                    reason=f"Frequency {num_val} Hz is outside safe operating envelope [45.0, 65.0]",
                    within_envelope=False,
                    suggested_value=suggested_val,
                    advisory="NO-GO",
                )

    # Current
    elif any(k in target_lower or k in action_text_lower for k in ("current", "amp")):
        suggested_val = 100.0
        if num_val is not None:
            if num_val < 0.0 or num_val > 50000.0:
                return ControlValidationResult(
                    valid=False,
                    reason=f"Current {num_val} A is outside safe operating envelope [0, 50000]",
                    within_envelope=False,
                    suggested_value=suggested_val,
                    advisory="NO-GO",
                )

    return ControlValidationResult(
        valid=True,
        reason="Action passed pre-control safety envelope and interlock checks",
        target_exists=True,
        within_envelope=True,
        interlock_ok=True,
        destructive_refused=False,
        suggested_value=suggested_val if suggested_val is not None else val_raw,
        advisory="GO",
    )


@dataclass
class CUAStepResult:
    """Result of executing one CUA loop iteration."""

    step_number: int
    action: CUAAction
    success: bool
    screenshot_before: str | None = None  # path
    screenshot_after: str | None = None  # path
    gemini_analysis: dict[str, Any] | None = None
    duration_ms: int = 0
    error: str | None = None
    audit_fields: dict[str, Any] = field(default_factory=dict)

    def to_audit_dict(self) -> dict[str, Any]:
        base = {
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
        if self.audit_fields:
            base.update(self.audit_fields)
        return base


@dataclass
class CUAExecutionResult:
    """Top-level result returned by CUAExecutor.execute_loop()."""

    success: bool
    steps: list[CUAStepResult] = field(default_factory=list)
    final_summary: str = ""
    objective_complete: bool = False
    aborted_reason: str | None = None
    total_duration_ms: int = 0
    execution_id: str | None = None
    resumed_from_step: int = 0
    vision_source: str | None = None  # "gemini" | "opencv" | "hybrid"

    def to_dict(self) -> dict[str, Any]:
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


# ─── Base CUA Executor (Template Method) ───────────────────────────────────


class BaseCUAExecutor(abc.ABC):
    """Abstract base class for Computer Use Agent executors.

    Implements the Template Method pattern: the shared 10-step CUA loop
    is defined once in execute_loop(), and platform-specific behaviour
    is injected via four abstract hook methods.

    Lifecycle:
        executor = SubclassCUAExecutor(audit_dir="~/.etap/cua_audit")
        result = executor.execute_loop(
            objective="Open ETAP and run Load Flow",
            max_steps=15,
            require_confirmation=True,
            on_confirmation_request=callback,
        )
    """

    # Safety limits (per skills/etap-gui-agent.md)
    DEFAULT_MAX_STEPS = DEFAULT_MAX_STEPS
    DEFAULT_ACTION_TIMEOUT = DEFAULT_ACTION_TIMEOUT
    DESTRUCTIVE_KEYWORDS = {"delete", "format", "override", "reset", "purge", "wipe"}

    def __init__(
        self,
        audit_dir: str | None = None,
        action_timeout: int = DEFAULT_ACTION_TIMEOUT,
    ) -> None:
        self.action_timeout = action_timeout
        # Per-user default audit dir (~/.etap/cua_audit) avoids S5443 (publicly
        # writable directories). The life_safety module defines the canonical
        # constant with 0o700 permissions; here we use the same default.
        _default_audit_dir = str(Path.home() / ".etap" / "cua_audit")
        self.audit_dir = (
            Path(audit_dir) if audit_dir else Path(_default_audit_dir)
        )  # NOSONAR S5443 — audit_dir is permission-hardened to 0o700 below (mkdir mode + chmod)
        self.audit_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Harden audit_dir to owner-only (0o700) so other users on the host
        # cannot read CUA screenshots / action logs. mkdir's `mode` arg is
        # masked by umask, so we chmod explicitly to guarantee the bits.
        try:
            os.chmod(self.audit_dir, 0o700)
        except OSError:
            # Best-effort: chmod can fail on Windows or read-only filesystems.
            pass

    # ─── Abstract hooks (platform-specific) ────────────────────────────────

    @abc.abstractmethod
    def check_dependencies(self) -> dict[str, Any]:
        """Check all deps required for CUA execution.

        Returns dict with at least 'all_available' (bool) and 'missing' (list[str]).
        Each subclass implements its own dependency checks (pyautogui for desktop,
        playwright for browser, etc.).
        """

    @abc.abstractmethod
    def _capture_screenshot_hook(self, step_num: int, phase: str, **kwargs) -> str | None:
        """Capture a screenshot and save it to the audit dir. Returns path.

        Platform-specific:
            Desktop: uses pyautogui.screenshot()
            Browser: uses page.screenshot() (page passed via kwargs or stored on self)
        """

    @abc.abstractmethod
    def _execute_action_hook(self, action: CUAAction, **kwargs) -> str | None:
        """Execute a single action. Returns error string or None.

        Platform-specific:
            Desktop: uses pyautogui.click / typewrite / hotkey
            Browser: uses page.mouse.click / page.keyboard.type / page.keyboard.press
        """

    @abc.abstractmethod
    def _wait_settle(self) -> None:
        """Wait for the UI to settle after an action.

        Platform-specific:
            Desktop: time.sleep(0.5)
            Browser: page.wait_for_timeout(500)
        """

    @abc.abstractmethod
    def _cleanup_on_exit(self) -> None:
        """Cleanup platform-specific resources on exit.

        Desktop: no-op (nothing to close)
        Browser: closes the Chromium browser instance
        """

    def _assert_coordinate_bounds(
        self,
        action: CUAAction,
        bounds: dict[str, int] | tuple[int, int, int, int] | None = None,
        mode: str = "control",
    ) -> str | None:
        """Validate that action coordinates lie within application screen boundaries (M5.1(d))."""
        if action.x is None and action.y is None:
            return None

        # In control mode, bounds must be explicitly specified (no over-wide desktop fallback)
        if mode == "control" and bounds is None:
            return "BOUNDS VIOLATION: missing-bounds (window boundaries must be specified in control mode to prevent out-of-window operations)"

        # Default bounds: desktop 0..3840 x 0..2160 allowed ONLY for observe/analyze mode
        min_x, min_y, max_x, max_y = 0, 0, 3840, 2160
        if isinstance(bounds, dict):
            min_x = bounds.get("min_x", 0)
            min_y = bounds.get("min_y", 0)
            max_x = bounds.get("max_x", 3840)
            max_y = bounds.get("max_y", 2160)
        elif isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            min_x, min_y, max_x, max_y = bounds

        if action.x is not None and (action.x < min_x or action.x > max_x):
            return f"Coordinate x={action.x} is outside allowed window bounds [{min_x}, {max_x}]"
        if action.y is not None and (action.y < min_y or action.y > max_y):
            return f"Coordinate y={action.y} is outside allowed window bounds [{min_y}, {max_y}]"
        return None

    # ─── Public: execute the full CUA loop ─────────────────────────────────

    def validate_control_action(
        self,
        action: CUAAction,
        gemini_analysis: dict[str, Any] | None = None,
        safety_check: Any = None,
    ) -> ControlValidationResult:
        """Validate a control action before presenting it for operator self-confirmation."""
        return validate_control_action(action, gemini_analysis=gemini_analysis, safety_check=safety_check)

    def execute_loop(  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self,
        objective: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        require_confirmation: bool = True,
        on_confirmation_request=None,
        context: str | None = None,
        mode: str = "control",
        tenant_id: str | None = None,
        allowed_tools: list[str] | set[str] | None = None,
        bounds: dict[str, int] | tuple[int, int, int, int] | None = None,
        allow_unverified: bool = False,
        single_operator_mode: bool = True,
        user_id: str | None = None,
    ) -> CUAExecutionResult:
        """Run the CUA loop until objective is complete or max_steps reached.

        Args:
            objective: what to accomplish (e.g., "Open ETAP and run Load Flow")
            max_steps: hard limit on loop iterations (safety)
            require_confirmation: if True, CONTROL actions pause for human approval
            on_confirmation_request: callable(action: CUAAction) -> bool
                                     If returns False, the loop aborts.
            context: prior context (e.g., "User just opened ETAP manually")
            mode: execution mode ("control" or "observe")
            tenant_id: optional tenant ID for isolation
            allowed_tools: optional list of permitted CUA action types
            bounds: optional window boundaries (min_x, min_y, max_x, max_y)
            allow_unverified: if True, permits unverified passthrough in control mode
                              when no verifier hook or visual screenshot diff is present

        Returns:
            CUAExecutionResult with full audit trail
        """
        try:
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
            exec_id, resume_from, prior_steps, prior_context = resume_manager.resume_or_start(
                objective
            )
            steps: list[CUAStepResult] = []
            # Reconstruct prior step results from checkpoint (simplified — audit-only)
            for ps in prior_steps:
                with contextlib.suppress(Exception):  # skip malformed prior steps
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

            current_context = context or prior_context or "Starting fresh"
            last_analysis: dict[str, Any] | None = None
            vision_sources_used: set = set()
            checkpoint_store = CheckpointStore()

            # If resuming, start from the next step
            start_step = max(1, resume_from + 1)
            if resume_from > 0:
                logger.info("Resuming CUA execution %s from step %d", exec_id, start_step)

            for step_num in range(start_step, max_steps + 1):
                step_start = time.monotonic()

                # STEP 1: capture screenshot
                screenshot_before = self._capture_screenshot_hook(step_num, "before")
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
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
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
                    # Clean up checkpoints on success — best effort, never fail
                    # the CUA execution because of a checkpoint cleanup error.
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
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason=f"Vision could not determine action: {action.reason}",
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
                        execution_id=exec_id,
                        resumed_from_step=resume_from,
                        vision_source=analysis.get("source"),
                    )

                # STEP 5.5: Coordinate bounds and tool policy checks (M5.1(d))
                bounds_err = self._assert_coordinate_bounds(action, bounds, mode=mode)
                if bounds_err:
                    step_result = CUAStepResult(
                        step_number=step_num,
                        action=action,
                        success=False,
                        screenshot_before=screenshot_before,
                        gemini_analysis=analysis,
                        error=f"BOUNDS VIOLATION: {bounds_err}",
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                    )
                    steps.append(step_result)
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason=f"Bounds violation: {bounds_err}",
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
                        execution_id=exec_id,
                        resumed_from_step=resume_from,
                        vision_source=analysis.get("source"),
                    )

                if allowed_tools is not None and action.type not in allowed_tools:
                    policy_err = (
                        f"Action '{action.type}' disallowed by tool policy for tenant '{tenant_id or 'default'}'"
                    )
                    step_result = CUAStepResult(
                        step_number=step_num,
                        action=action,
                        success=False,
                        screenshot_before=screenshot_before,
                        gemini_analysis=analysis,
                        error=f"TOOL POLICY VIOLATION: {policy_err}",
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                    )
                    steps.append(step_result)
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason=policy_err,
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

                # STEP 7: LIFE SAFETY CHECK — non-bypassable gate before execution
                from agents.life_safety import life_safety_guard

                safety_check = life_safety_guard.pre_action_check(
                    action=action,
                    screenshot_before=screenshot_before,
                    gemini_analysis=analysis,
                    vision_source=analysis.get("source", "gemini"),
                    mode=mode,
                    single_operator_mode=single_operator_mode,
                )
                if safety_check.blocked:
                    # ── Attempt rollback from pre-action snapshot ────────────
                    # The safety guard already captured a state snapshot in
                    # pre_action_check(). We call rollback() to log a tamper-
                    # evident audit entry and return operator instructions.
                    # Best-effort: never fail the execution because of a rollback
                    # error.
                    if safety_check.state_snapshot_id:
                        with contextlib.suppress(Exception):
                            life_safety_guard.rollback(
                                snapshot_id=safety_check.state_snapshot_id,
                                reason=f"safety_check_blocked: {safety_check.reason}",
                            )

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
                    # Save checkpoint so we can resume after the safety issue is
                    # resolved — best effort, never fail the CUA execution because
                    # of a checkpoint save error.
                    with contextlib.suppress(Exception):
                        checkpoint_store.save(
                            execution_id=exec_id,
                            step_num=step_num,
                            objective=objective,
                            completed_steps=[s.to_audit_dict() for s in steps],
                            context=f"Step {step_num}: SAFETY BLOCKED — {safety_check.reason}",
                        )
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason=f"Life safety block: {safety_check.reason}",
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
                        execution_id=exec_id,
                        resumed_from_step=resume_from,
                        vision_source=analysis.get("source"),
                    )

                # STEP 8: VALIDATED SELF-CONFIRMATION GATE (replacing dual-human gate)
                needs_confirmation = (
                    require_confirmation
                    or safety_check.requires_validated_self_confirmation
                    or safety_check.requires_dual_confirmation
                )
                audit_step_fields: dict[str, Any] = {}

                if needs_confirmation:
                    # (a) validate_control_action
                    val_res = validate_control_action(
                        action,
                        gemini_analysis=analysis,
                        safety_check=safety_check,
                    )
                    if not val_res.valid:
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason=f"validation_failed: {val_res.reason}",
                                )
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error=f"VALIDATION FAILED: {val_res.reason}",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                            audit_fields={
                                "validation": val_res.to_dict(),
                                "suggestion": val_res.program_suggestion,
                                "overridden": False,
                                "override_reason": None,
                                "decided_by_user_id": None,
                            },
                        )
                        steps.append(step_result)
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason=f"Action validation failed: {val_res.reason}",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # Missing callback check (fail-closed)
                    if on_confirmation_request is None:
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason="confirmation_callback_missing",
                                )
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error="Action requires confirmation but no callback registered (fail-closed)",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                            audit_fields={
                                "validation": val_res.to_dict(),
                                "suggestion": val_res.program_suggestion,
                                "overridden": False,
                                "override_reason": None,
                                "decided_by_user_id": None,
                            },
                        )
                        steps.append(step_result)
                        abort_msg = (
                            "Dual confirmation required but no confirmation callback provided (fail-closed)"
                            if safety_check.requires_dual_confirmation
                            else "Missing confirmation callback for confirmed action (fail-closed)"
                        )
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason=abort_msg,
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # Enforce distinct dual confirmation; reject single self-confirmation before action callback
                    if safety_check.requires_dual_confirmation and single_operator_mode:
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason="dual_confirmation_required_in_single_operator_mode",
                                )
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error="DUAL CONFIRMATION REQUIRED: Action requires two distinct operators. Single-operator self-confirmation is rejected.",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                        )
                        steps.append(step_result)
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason="Dual confirmation required: action cannot be self-confirmed by a single operator (fail-closed)",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    # (b) Build confirmation payload and invoke confirmation callback
                    val_raw = getattr(action, "value", None)
                    if val_raw is None and action.text:
                        val_raw = action.text

                    decided_user = getattr(action, "user_id", None) or user_id or "operator"
                    confirm_payload = ConfirmationPayload(
                        action=action,
                        target=action.target,
                        value=val_raw,
                        validation_results=val_res.to_dict(),
                        program_suggestion=val_res.program_suggestion,
                        risk_note=val_res.risk_note,
                        override_reason=getattr(action, "override_reason", None),
                        overridden=bool(getattr(action, "overridden", False)),
                        decided_by_user_id=decided_user,
                        requires_dual_confirmation=safety_check.requires_dual_confirmation,
                    )

                    approved = on_confirmation_request(confirm_payload)
                    if not approved:
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason="confirmation_denied",
                                )
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error="User did not confirm action",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                            audit_fields={
                                "validation": val_res.to_dict(),
                                "suggestion": val_res.program_suggestion,
                                "overridden": False,
                                "override_reason": None,
                                "decided_by_user_id": confirm_payload.get("decided_by_user_id") or decided_user,
                            },
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

                    if safety_check.requires_dual_confirmation:
                        confirmations = confirm_payload.get("confirmations") or []
                        approvers = confirm_payload.get("approvers") or []
                        if isinstance(approved, dict):
                            confirmations = approved.get("confirmations") or confirmations
                            approvers = approved.get("approvers") or approvers

                        distinct_approvers = {str(u) for u in (list(confirmations) + list(approvers)) if u}
                        if len(distinct_approvers) < 2:
                            if safety_check.state_snapshot_id:
                                with contextlib.suppress(Exception):
                                    life_safety_guard.rollback(
                                        snapshot_id=safety_check.state_snapshot_id,
                                        reason="insufficient_confirmations_for_dual_confirmation",
                                    )
                            step_result = CUAStepResult(
                                step_number=step_num,
                                action=action,
                                success=False,
                                screenshot_before=screenshot_before,
                                gemini_analysis=analysis,
                                error="DUAL CONFIRMATION VIOLATION: Two distinct approvers required (fail-closed)",
                                duration_ms=int((time.monotonic() - step_start) * 1000),
                            )
                            steps.append(step_result)
                            return CUAExecutionResult(
                                success=False,
                                steps=steps,
                                aborted_reason="Dual confirmation violation: two distinct approvers required (fail-closed)",
                                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                                execution_id=exec_id,
                                resumed_from_step=resume_from,
                                vision_source=analysis.get("source"),
                            )

                    # (c) Suggestion-override validation
                    is_overridden = bool(
                        confirm_payload.get("overridden")
                        or getattr(confirm_payload, "overridden", False)
                        or getattr(action, "overridden", False)
                        or (
                            confirm_payload.get("override_value") is not None
                            and confirm_payload.get("override_value") != val_res.suggested_value
                        )
                        or (
                            getattr(action, "override_value", None) is not None
                            and getattr(action, "override_value", None) != val_res.suggested_value
                        )
                    )
                    override_reason = (
                        confirm_payload.get("override_reason")
                        or getattr(confirm_payload, "override_reason", None)
                        or getattr(action, "override_reason", None)
                        or ""
                    )

                    if is_overridden and (not override_reason or not str(override_reason).strip()):
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason="override_reason_missing",
                                )
                        step_result = CUAStepResult(
                            step_number=step_num,
                            action=action,
                            success=False,
                            screenshot_before=screenshot_before,
                            gemini_analysis=analysis,
                            error="OVERRIDE REASON REQUIRED: Suggestion override requires an explicit override_reason string (fail-closed)",
                            duration_ms=int((time.monotonic() - step_start) * 1000),
                            audit_fields={
                                "validation": val_res.to_dict(),
                                "suggestion": val_res.program_suggestion,
                                "overridden": True,
                                "override_reason": None,
                                "decided_by_user_id": confirm_payload.get("decided_by_user_id") or decided_user,
                            },
                        )
                        steps.append(step_result)
                        return CUAExecutionResult(
                            success=False,
                            steps=steps,
                            aborted_reason="Suggestion override requires an explicit override_reason string (fail-closed)",
                            total_duration_ms=int((time.monotonic() - start_time) * 1000),
                            execution_id=exec_id,
                            resumed_from_step=resume_from,
                            vision_source=analysis.get("source"),
                        )

                    audit_step_fields = {
                        "validation": val_res.to_dict(),
                        "suggestion": val_res.program_suggestion,
                        "overridden": bool(is_overridden),
                        "override_reason": str(override_reason).strip() if (is_overridden and override_reason) else None,
                        "decided_by_user_id": confirm_payload.get("decided_by_user_id") or decided_user,
                        "self_approved": not safety_check.requires_dual_confirmation,
                        "dual_confirmed": bool(safety_check.requires_dual_confirmation),
                    }

                # STEP 9: execute the action (passed safety check & validation)
                exec_error = self._execute_action_hook(action)

                # STEP 10: capture after screenshot + post-action safety record
                self._wait_settle()  # let UI settle
                screenshot_after = self._capture_screenshot_hook(step_num, "after")
                life_safety_guard.post_action_record(
                    action=action,
                    screenshot_after=screenshot_after,
                    pre_check=safety_check,
                    exec_error=exec_error,
                )

                # STEP 10.5: Deterministic Post-Action Verification (M5.1(b))
                if exec_error is None:
                    verification = life_safety_guard.verify_post_action(
                        action=action,
                        screenshot_before=screenshot_before,
                        screenshot_after=screenshot_after,
                        pre_snapshot_id=safety_check.state_snapshot_id,
                    )
                    is_verified = verification.get("verified", False)
                    is_unverified = verification.get("unverified_passthrough", False)

                    if not is_verified and is_unverified and allow_unverified:
                        is_verified = True
                        logger.warning("Unverified post-action passthrough permitted by allow_unverified flag")

                    if not is_verified:
                        v_reason = verification.get("reason", "Post-action state verification failed")
                        logger.error("Deterministic post-action verification FAILED: %s", v_reason)
                        exec_error = f"Post-action verification failed: {v_reason}"
                        # Automatic Rollback on verification failure (M5.1(c))
                        if safety_check.state_snapshot_id:
                            with contextlib.suppress(Exception):
                                life_safety_guard.rollback(
                                    snapshot_id=safety_check.state_snapshot_id,
                                    reason=f"post_action_verification_failed: {v_reason}",
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
                    audit_fields=audit_step_fields,
                )
                steps.append(step_result)

                if exec_error:
                    logger.warning("Step %d failed: %s — aborting CUA loop (fail-closed)", step_num, exec_error)
                    return CUAExecutionResult(
                        success=False,
                        steps=steps,
                        aborted_reason=f"Action execution or post-action verification failed: {exec_error}",
                        total_duration_ms=int((time.monotonic() - start_time) * 1000),
                        execution_id=exec_id,
                        resumed_from_step=resume_from,
                        vision_source=analysis.get("source"),
                    )

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
        finally:
            self._cleanup_on_exit()


__all__ = [
    "ActionType",
    "BaseCUAExecutor",
    "CUAAction",
    "CUAExecutionResult",
    "CUAStepResult",
]
