"""
agents/etap_gui_agent.py — ETAP GUI Agent Skill (Computer Use Agent)

Implements the ETAP GUI Agent skill as a runtime-active agent that:
  1. Loads its knowledge base from skills/etap-gui-agent.md
  2. Detects whether GUI dependencies (pyautogui, pytesseract, opencv)
     are available — falls back gracefully on headless servers / HF Space
  3. Classifies each user question into one of four modes:
     ANALYZE / MONITOR / CONTROL / SOLVE
  4. Formats the response using the mandatory Format A/B/C/D templates
     defined by the skill
  5. Enforces safety rules: failsafe, confirmation required for CONTROL/SOLVE,
     audit logging, timeouts
  6. **Executes the CUA Loop** by delegating to agents.cua_executor.CUAExecutor,
     which captures real screenshots, analyzes them via Gemini Vision, and
     drives pyautogui to click/type/hotkey the target desktop application.

This agent is registered as study_type="etap_gui" in api/studies.py
and is callable via POST /api/v1/studies/run.

On headless servers (HF Space, CI), the executor reports deps unavailable
and the agent falls back to Format U (planning-only response).

References:
  - skills/etap-gui-agent.md            (knowledge base)
  - prompts/etap_gui_agent.prompt.yaml  (LLM prompt for Mastra side)
  - api/studies.py:_run_native_study    (dispatch entry point)
  - agents/cua_executor.py              (CUA Loop execution layer)
  - integrations/gemini_vision.py       (Visual perception via Gemini Vision API)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger("agent.etap_gui")

# ---------------------------------------------------------------------------
# Skill knowledge loader — single source of truth, loaded once
# ---------------------------------------------------------------------------

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "etap-gui-agent.md"

_skill_cache: Optional[str] = None


def _load_skill() -> str:
    """Load the skill knowledge base (cached after first call)."""
    global _skill_cache
    if _skill_cache is None:
        if not _SKILL_PATH.exists():
            logger.warning("GUI skill knowledge file missing: %s", _SKILL_PATH)
            _skill_cache = ""
        else:
            _skill_cache = _SKILL_PATH.read_text(encoding="utf-8")
            logger.info("ETAP GUI skill loaded: %d chars", len(_skill_cache))
    return _skill_cache


# ---------------------------------------------------------------------------
# Dependency detection — graceful fallback on headless servers
# ---------------------------------------------------------------------------


def _check_gui_deps() -> Tuple[bool, List[str]]:
    """Check whether the GUI automation dependencies are available.

    Returns (all_available, missing_list).

    Required for real CUA execution:
      - pyautogui   (mouse/keyboard control)
      - PIL/Pillow  (image handling)
      - google.generativeai (Gemini Vision for visual perception)
      - pyautogui needs a display server (X11 / Windows / macOS GUI)

    Optional (fallback OCR if Gemini is unavailable):
      - pytesseract + tesseract binary
    """
    missing: List[str] = []

    # pyautogui imports succeed even without a display, but screenshot() will fail.
    # We detect the actual display server here.
    try:
        import pyautogui  # noqa: F401

        # Check display server
        if os.name == "posix":
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                missing.append("display-server")
    except ImportError:
        missing.append("pyautogui")

    # PIL/Pillow
    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("PIL")

    # Gemini Vision SDK (required — we use it instead of pytesseract for OCR)
    try:
        import google.generativeai  # noqa: F401

        if not os.environ.get("GEMINI_API_KEY"):
            missing.append("GEMINI_API_KEY-env-var")
    except ImportError:
        missing.append("google-generativeai")

    # Optional: pytesseract + binary (only needed if Gemini Vision is down)
    try:
        import shutil

        import pytesseract  # noqa: F401

        if not shutil.which("tesseract"):
            missing.append("tesseract-binary-optional")
    except ImportError:
        missing.append("pytesseract-optional")

    # cv2 is no longer required (Gemini does visual analysis)
    # but we keep it in the deps list for backward compatibility
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("cv2-optional")

    return (len(missing) == 0), missing


# ---------------------------------------------------------------------------
# Classification — rule-based, deterministic
# ---------------------------------------------------------------------------

Classification = Literal["analyze", "monitor", "control", "solve", "unavailable"]

# CONTROL triggers — actions that modify application state
_CONTROL_KEYWORDS: Tuple[str, ...] = (
    "click",
    "open etap",
    "launch etap",
    "run study",
    "run load flow",
    "run short circuit",
    "run arc flash",
    "modify",
    "change",
    "set ",
    "update ",
    "apply ",
    "delete ",
    "remove ",
    "add bus",
    "add transformer",
    "edit ",
    "configure ",
    "execute ",
    "press ",
    "type ",
    "save ",
    "export ",
    "close etap",
    "stop study",
    "cancel ",
)

# SOLVE triggers — multi-step problem-solving workflows
_SOLVE_KEYWORDS: Tuple[str, ...] = (
    "solve ",
    "fix ",
    "troubleshoot",
    "resolve ",
    "automate ",
    "workflow",
    "diagnose ",
    "investigate ",
    "debug ",
    "step-by-step",
    "step by step",
)

# MONITOR triggers — passive observation
_MONITOR_KEYWORDS: Tuple[str, ...] = (
    "monitor ",
    "watch ",
    "observe ",
    "track ",
    "wait for",
    "check status",
    "live ",
    "real-time ",
    "real time ",
)

# ANALYZE triggers — read-only inspection (default)
_ANALYZE_KEYWORDS: Tuple[str, ...] = (
    "analyze ",
    "inspect ",
    "read ",
    "look at",
    "screenshot",
    "capture ",
    "find ",
    "locate ",
    "identify ",
    "what ",
    "where ",
    "show me",
)


def classify(question: str) -> Classification:
    """Classify a question into analyze / monitor / control / solve.

    Decision order (first match wins):
      0. UNAVAILABLE — if GUI deps missing (handled by answer(), not here)
      1. SOLVE — if a solve keyword is present (multi-step workflows
         often contain control actions, so SOLVE takes precedence)
      2. CONTROL — if a control keyword is present
      3. MONITOR — if a monitor keyword is present
      4. ANALYZE — default (read-only inspection)
    """
    q = question.lower()

    # 1. Solve (highest precedence among action modes)
    if any(kw in q for kw in _SOLVE_KEYWORDS):
        return "solve"

    # 2. Control
    if any(kw in q for kw in _CONTROL_KEYWORDS):
        return "control"

    # 3. Monitor
    if any(kw in q for kw in _MONITOR_KEYWORDS):
        return "monitor"

    # 4. Analyze (default)
    return "analyze"


# ---------------------------------------------------------------------------
# Target app detection
# ---------------------------------------------------------------------------

_APP_KEYWORDS: List[Tuple[str, str]] = [
    ("etap", "ETAP"),
    ("revit", "Revit"),
    ("autocad", "AutoCAD"),
    ("scada", "SCADA"),
    ("qgis", "QGIS"),
    ("arcgis", "ArcGIS"),
    ("zenon", "Zenon"),
]


def detect_target_app(question: str) -> str:
    """Detect which desktop app the user is asking about."""
    q = question.lower()
    for kw, name in _APP_KEYWORDS:
        if kw in q:
            return name
    return "unknown"


# ---------------------------------------------------------------------------
# Response formatters — produce the exact Format A/B/C/D signatures
# ---------------------------------------------------------------------------

_SEP = "━" * 60


def _format_unavailable(missing: List[str]) -> str:
    """Format U — GUI deps unavailable (graceful fallback).

    Lists both options to enable CUA:
      1. Desktop CUA (pyautogui) — controls native apps (ETAP, Revit, etc.)
      2. Browser CUA (Playwright) — controls web pages, works on headless servers
    """
    # Determine whether Gemini Vision is missing (required for BOTH paths)
    has_gemini_issue = any("gemini" in m.lower() or "google" in m.lower() for m in missing)

    lines = [
        "⚠️ GUI AGENT UNAVAILABLE",
        _SEP,
        "",
        "The CUA Loop cannot run in this environment.",
        "",
        f"**Missing dependencies:** {', '.join(missing)}",
        "",
    ]

    if has_gemini_issue:
        lines.extend(
            [
                "**Required for BOTH paths:**",
                "  • Set GEMINI_API_KEY env var (get one at https://aistudio.google.com/app/apikey)",
                "  • pip install google-generativeai",
                "",
            ]
        )

    lines.extend(
        [
            "**Two ways to enable the CUA Loop:**",
            "",
            "  Option 1 — Desktop CUA (controls native apps like ETAP.exe):",
            "    • Run on Windows/Linux/macOS with a display",
            "    • pip install pyautogui pillow",
            "    • Set DISPLAY or WAYLAND_DISPLAY env var (Linux)",
            "",
            "  Option 2 — Browser CUA (controls web pages, works on HF Space!):",
            "    • pip install playwright",
            "    • playwright install chromium",
            "    • Then call execute_cua_loop(question=..., start_url='https://your-app')",
            "",
            "**Suggested alternative (no deps needed):** Use the ETAP Expert Skill "
            "(study_type='etap_expert') for knowledge-based analysis.",
            "",
            "**Safety:** The GUI Agent never crashes — it always falls back gracefully.",
        ]
    )
    return "\n".join(lines)


def _format_a_analyze(question: str, app: str) -> str:
    """Format A — ANALYZE (read-only inspection)."""
    return "\n".join(
        [
            "👁️ GUI AGENT — ANALYZE MODE",
            _SEP,
            "",
            f"**Your Request:** {question}",
            "**Mode:** Analyze (read-only)",
            f"**Target App:** {app}",
            "",
            "**PLANNED STEPS:**",
            f"  1. Launch {app} (if not already running)",
            "  2. Capture initial screenshot",
            "  3. OCR-analyze the screen",
            "  4. Identify UI elements (menus, buttons, dialogs)",
            "  5. Report findings",
            "",
            "**SAFETY:** Read-only — no modifications will be made.",
            "",
            "**REQUIRES:** Human confirmation to proceed with screen capture.",
            "",
            "**REFERENCES:**",
            "  - skills/etap-gui-agent.md (knowledge base)",
            "  - Safety rule: read-only by default",
        ]
    )


def _format_b_monitor(question: str, app: str) -> str:
    """Format B — MONITOR (passive observation)."""
    return "\n".join(
        [
            "📊 GUI AGENT — MONITOR MODE",
            _SEP,
            "",
            f"**Your Request:** {question}",
            "**Mode:** Monitor (passive observation)",
            f"**Target App:** {app}",
            "**Duration:** Until study completes or user stops (default: 5 minutes)",
            "",
            "**MONITORING POINTS:**",
            "  1. Study convergence status",
            "  2. Error/warning dialogs",
            "  3. Progress indicators",
            "  4. Result availability",
            "",
            "**SAFETY:** Passive observation only — no actions taken.",
            "",
            "**REQUIRES:** Human confirmation to start monitoring.",
        ]
    )


def _format_c_control(question: str, app: str) -> str:
    """Format C — CONTROL (modifies app state, requires confirmation)."""
    return "\n".join(
        [
            "🖱️ GUI AGENT — CONTROL MODE",
            _SEP,
            "",
            f"**Your Request:** {question}",
            "**Mode:** Control (modifies application state)",
            f"**Target App:** {app}",
            "",
            "**PLANNED ACTIONS:**",
            f"  1. Focus {app} window",
            "  2. Navigate to target menu/dialog",
            "  3. Execute the requested action (click/type)",
            "  4. Capture before/after screenshots",
            "",
            "⚠️ **WARNING:** This will modify the application state.",
            "",
            "**CONFIRMATION REQUIRED:** Reply 'CONFIRM' to execute, 'CANCEL' to abort.",
            "",
            "**SAFETY RULES ACTIVE:**",
            "  - Failsafe enabled (move mouse to corner = immediate stop)",
            "  - Timeout: 60 seconds per action",
            "  - Full audit log will be recorded (screenshots + actions)",
            "  - pyautogui.FAILSAFE = True",
            "",
            "**REFERENCES:**",
            "  - skills/etap-gui-agent.md (Safety Rules section)",
        ]
    )


def _format_d_solve(question: str, app: str) -> str:
    """Format D — SOLVE (multi-step problem-solving workflow)."""
    return "\n".join(
        [
            "⚡ GUI AGENT — SOLVE MODE",
            _SEP,
            "",
            f"**Your Request:** {question}",
            "**Mode:** Solve (multi-step problem-solving)",
            f"**Target App:** {app}",
            "",
            "**WORKFLOW:**",
            "  1. Analyze current state (screenshot + OCR)",
            "  2. Identify problem (read errors, compare to expected)",
            "  3. Propose solution (with ETAP Expert Skill knowledge)",
            "  4. Apply solution (requires explicit confirmation)",
            "  5. Verify result (re-run study, check output)",
            "  6. Report outcome (success/failure + audit log)",
            "",
            "**INTEGRATION:**",
            "  - ETAP Expert Skill: knowledge base (skills/etap-expert.md)",
            "  - GUI Agent: execution (mouse/keyboard control)",
            "  - LLM Vision: decision making (optional)",
            "",
            "⚠️ Step 4 requires explicit user confirmation.",
            "",
            "**SAFETY RULES ACTIVE:**",
            "  - Failsafe enabled",
            "  - Timeout: 60 seconds per action",
            "  - Audit log: every action recorded with before/after screenshots",
            "",
            "**REFERENCES:**",
            "  - skills/etap-gui-agent.md (CUA Loop + Safety Rules)",
        ]
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ETAPGUIAgent(BaseAgent):
    """ETAP GUI Agent — Computer Use Agent for engineering desktop apps.

    Registered as study_type="etap_gui" in api/studies.py.
    Loads its knowledge base from skills/etap-gui-agent.md.
    Falls back gracefully when GUI deps are unavailable (headless servers).
    """

    prompt_handle = "etap_gui_agent"

    def __init__(self) -> None:
        super().__init__("etap_gui")
        # Eagerly load the skill so missing-file errors surface at startup
        skill_text = _load_skill()
        if not skill_text:
            logger.warning(
                "ETAP GUI skill knowledge base is empty — agent will operate in degraded mode"
            )

    # ----- Public API -----

    def answer(self, question: str) -> Dict[str, Any]:
        """Answer a question using the CUA workflow.

        Returns a dict with keys: classification, format, response,
        skill_loaded (bool), skill_chars (int), deps_available (bool),
        target_app (str), workflow_steps_executed (int).
        """
        # STEP 0: Check GUI deps — fall back gracefully if missing
        deps_ok, missing = _check_gui_deps()
        if not deps_ok:
            return {
                "classification": "unavailable",
                "format": "U",
                "response": _format_unavailable(missing),
                "skill_loaded": bool(_load_skill()),
                "skill_chars": len(_load_skill()),
                "deps_available": False,
                "missing_deps": missing,
                "target_app": detect_target_app(question),
                "workflow_steps_executed": 1,
            }

        # STEP 1: PARSE & CLASSIFY
        cls = classify(question)
        app = detect_target_app(question)

        # STEP 2-5: FORMULATE RESPONSE (Format A/B/C/D)
        if cls == "analyze":
            response = _format_a_analyze(question, app)
        elif cls == "monitor":
            response = _format_b_monitor(question, app)
        elif cls == "control":
            response = _format_c_control(question, app)
        elif cls == "solve":
            response = _format_d_solve(question, app)
        else:
            response = _format_a_analyze(question, app)

        return {
            "classification": cls,
            "format": {"analyze": "A", "monitor": "B", "control": "C", "solve": "D"}[cls],
            "response": response,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "deps_available": True,
            "target_app": app,
            "workflow_steps_executed": 6,
        }

    def execute_cua_loop(
        self,
        question: str,
        max_steps: int = 15,
        require_confirmation: bool = True,
        on_confirmation_request=None,
        audit_dir: Optional[str] = None,
        start_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the actual CUA Loop — captures screenshots, analyzes them
        via Gemini Vision, and drives the appropriate executor to click/type/hotkey.

        AUTO-DETECTS THE ENVIRONMENT and picks the best executor:
          1. DesktopCUAExecutor (pyautogui + display server) — controls native apps
          2. BrowserCUAExecutor (Playwright + Chromium) — controls web pages,
             works on headless servers like HF Space
          3. Format U fallback — if neither is available

        Args:
            question: the user's objective (e.g., "Open ETAP and run Load Flow")
            max_steps: hard safety limit on CUA loop iterations
            require_confirmation: pause for human approval before CONTROL/SOLVE actions
            on_confirmation_request: callable(action) -> bool; if returns False, abort
            audit_dir: directory for before/after screenshots (default /tmp/cua_audit)
            start_url: optional URL to navigate to (BrowserCUA only; ignored by Desktop)

        Returns:
            Dict with: executed (bool), result (CUAExecutionResult.to_dict()),
            classification, format, target_app, deps_available, executor_used.
        """
        cls = classify(question)
        app = detect_target_app(question)

        # Try Desktop CUA first (pyautogui + display server)
        desktop_deps_ok, desktop_missing = _check_gui_deps()
        # Check Browser CUA (Playwright + Chromium)
        browser_executor = None
        browser_deps: Dict[str, Any] = {"all_available": False, "missing": ["not-checked"]}
        try:
            from agents.browser_cua_executor import BrowserCUAExecutor

            browser_executor = BrowserCUAExecutor(audit_dir=audit_dir or "/tmp/cua_audit")
            browser_deps = browser_executor.check_dependencies()
        except Exception as exc:  # noqa: BLE001
            logger.debug("BrowserCUAExecutor init failed: %s", exc)

        # Decide which executor to use
        if desktop_deps_ok:
            # Desktop environment — control native apps via pyautogui
            from agents.cua_executor import CUAExecutor

            executor = CUAExecutor(
                audit_dir=audit_dir or "/tmp/cua_audit",
                action_timeout=60,
            )
            executor_type = "desktop"
            result = executor.execute_loop(
                objective=question,
                max_steps=max_steps,
                require_confirmation=cls in ("control", "solve") and require_confirmation,
                on_confirmation_request=on_confirmation_request,
                context=f"Target app: {app}. Mode: {cls}.",
            )
        elif browser_deps["all_available"]:
            # Headless environment with Playwright — control a browser instead
            assert browser_executor is not None  # for type checker
            executor_type = "browser"
            result = browser_executor.execute_loop(
                objective=question,
                start_url=start_url,
                max_steps=max_steps,
                require_confirmation=cls in ("control", "solve") and require_confirmation,
                on_confirmation_request=on_confirmation_request,
                context=f"Target app: {app}. Mode: {cls}. Browser CUA.",
            )
        else:
            # Neither available — Format U fallback
            all_missing = list(set(desktop_missing + browser_deps.get("missing", [])))
            return {
                "executed": False,
                "classification": "unavailable",
                "format": "U",
                "response": _format_unavailable(all_missing),
                "deps_available": False,
                "missing_deps": all_missing,
                "target_app": app,
                "executor_used": "none",
                "result": None,
            }

        return {
            "executed": True,
            "classification": cls,
            "format": {"analyze": "A", "monitor": "B", "control": "C", "solve": "D"}[cls],
            "target_app": app,
            "deps_available": True,
            "executor_used": executor_type,
            "result": result.to_dict(),
            "response": self._format_cua_result_response(cls, app, question, result),
        }

    @staticmethod
    def _format_cua_result_response(cls: str, app: str, question: str, result) -> str:
        """Format the human-readable summary of a CUA execution."""
        icon = {"analyze": "👁️", "monitor": "📊", "control": "🖱️", "solve": "⚡"}[cls]
        lines = [
            f"{icon} GUI AGENT — {cls.upper()} MODE (EXECUTED)",
            _SEP,
            "",
            f"**Your Request:** {question}",
            f"**Mode:** {cls} (executed via CUA Loop)",
            f"**Target App:** {app}",
            "",
            f"**Outcome:** {'✅ SUCCESS' if result.success else '❌ FAILED'}",
            f"**Steps Executed:** {len(result.steps)}",
            f"**Objective Complete:** {result.objective_complete}",
            f"**Total Duration:** {result.total_duration_ms} ms",
            "",
        ]
        if result.final_summary:
            lines.append(f"**Final Summary:** {result.final_summary}")
            lines.append("")
        if result.aborted_reason:
            lines.append(f"**Aborted Reason:** {result.aborted_reason}")
            lines.append("")
        lines.append("**Audit Trail:**")
        for step in result.steps:
            status = "✓" if step.success else "✗"
            action_desc = step.action.type
            if step.action.target:
                action_desc += f" ({step.action.target})"
            elif step.action.x is not None:
                action_desc += f" ({step.action.x},{step.action.y})"
            lines.append(
                f"  {status} Step {step.step_number}: {action_desc} — {step.duration_ms}ms"
            )
            if step.error:
                lines.append(f"      error: {step.error}")
        lines.append("")
        lines.append("**Screenshots:** saved to /tmp/cua_audit/")
        lines.append("")
        lines.append("**Safety:** All actions logged with before/after screenshots.")
        return "\n".join(lines)

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Async wrapper for orchestrator compatibility."""
        question = str(task.parameters.get("question", "")).strip()
        if not question:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=["Missing 'question' parameter"],
            )
        try:
            data = self.answer(question)
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data=data,
            )
        except Exception as exc:
            logger.exception("ETAPGUIAgent failed")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(exc)],
            )

    def get_agent_info(self) -> Dict[str, Any]:
        """Return metadata about this agent."""
        deps_ok, missing = _check_gui_deps()
        return {
            "name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "knowledge_base": "skills/etap-gui-agent.md",
            "study_type": "etap_gui",
            "deps_available": deps_ok,
            "missing_deps": missing if not deps_ok else [],
            "supported_formats": [
                "A (analyze)",
                "B (monitor)",
                "C (control)",
                "D (solve)",
                "U (unavailable)",
            ],
            "supported_apps": ["ETAP", "Revit", "AutoCAD", "SCADA", "QGIS", "ArcGIS", "Zenon"],
            "safety_rules": [
                "failsafe_enabled",
                "confirmation_required_for_control",
                "confirmation_required_for_solve",
                "audit_logging",
                "timeout_60s",
            ],
        }


# ---------------------------------------------------------------------------
# Module-level convenience — allows `python -m agents.etap_gui_agent` smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agents.etap_gui_agent 'your GUI automation question'")
        sys.exit(1)

    agent = ETAPGUIAgent()
    result = agent.answer(" ".join(sys.argv[1:]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
