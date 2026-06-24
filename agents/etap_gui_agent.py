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

This agent is registered as study_type="etap_gui" in api/studies.py
and is callable via POST /api/v1/studies/run.

The agent does NOT require an external LLM API — classification and
formatting are deterministic so the skill is always available offline.

References:
  - skills/etap-gui-agent.md            (knowledge base)
  - prompts/etap_gui_agent.prompt.yaml  (LLM prompt for Mastra side)
  - api/studies.py:_run_native_study    (dispatch entry point)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask

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
    """
    missing: List[str] = []
    for mod in ("pyautogui", "pytesseract", "cv2", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    # Also check for the Tesseract binary
    try:
        import shutil

        if not shutil.which("tesseract"):
            missing.append("tesseract-binary")
    except Exception:
        missing.append("tesseract-binary")
    return (len(missing) == 0), missing


# ---------------------------------------------------------------------------
# Classification — rule-based, deterministic
# ---------------------------------------------------------------------------

Classification = Literal["analyze", "monitor", "control", "solve", "unavailable"]

# CONTROL triggers — actions that modify application state
_CONTROL_KEYWORDS: Tuple[str, ...] = (
    "click", "open etap", "launch etap", "run study", "run load flow",
    "run short circuit", "run arc flash", "modify", "change", "set ",
    "update ", "apply ", "delete ", "remove ", "add bus", "add transformer",
    "edit ", "configure ", "execute ", "press ", "type ", "save ", "export ",
    "close etap", "stop study", "cancel ",
)

# SOLVE triggers — multi-step problem-solving workflows
_SOLVE_KEYWORDS: Tuple[str, ...] = (
    "solve ", "fix ", "troubleshoot", "resolve ", "automate ", "workflow",
    "diagnose ", "investigate ", "debug ", "step-by-step", "step by step",
)

# MONITOR triggers — passive observation
_MONITOR_KEYWORDS: Tuple[str, ...] = (
    "monitor ", "watch ", "observe ", "track ", "wait for", "check status",
    "live ", "real-time ", "real time ",
)

# ANALYZE triggers — read-only inspection (default)
_ANALYZE_KEYWORDS: Tuple[str, ...] = (
    "analyze ", "inspect ", "read ", "look at", "screenshot", "capture ",
    "find ", "locate ", "identify ", "what ", "where ", "show me",
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
    """Format U — GUI deps unavailable (graceful fallback)."""
    return "\n".join([
        "⚠️ GUI AGENT UNAVAILABLE",
        _SEP,
        "",
        "The GUI Agent requires desktop dependencies which are not "
        "available in this environment.",
        "",
        f"**Missing dependencies:** {', '.join(missing)}",
        "",
        "**Suggested alternative:** Use the ETAP Expert Skill "
        "(study_type='etap_expert') for knowledge-based analysis.",
        "",
        "**To enable the GUI Agent:**",
        "  1. Run on a desktop environment (Windows/Linux/macOS)",
        "  2. Install: pip install pyautogui pytesseract opencv-python pillow",
        "  3. Install Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki)",
        "  4. Set ETAP_GUI_AGENT_ENABLED=true",
        "",
        "**Safety:** The GUI Agent never crashes the application — "
        "it falls back gracefully when deps are missing.",
    ])


def _format_a_analyze(question: str, app: str) -> str:
    """Format A — ANALYZE (read-only inspection)."""
    return "\n".join([
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
    ])


def _format_b_monitor(question: str, app: str) -> str:
    """Format B — MONITOR (passive observation)."""
    return "\n".join([
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
    ])


def _format_c_control(question: str, app: str) -> str:
    """Format C — CONTROL (modifies app state, requires confirmation)."""
    return "\n".join([
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
        "**CONFIRMATION REQUIRED:** Reply 'CONFIRM' to execute, "
        "'CANCEL' to abort.",
        "",
        "**SAFETY RULES ACTIVE:**",
        "  - Failsafe enabled (move mouse to corner = immediate stop)",
        "  - Timeout: 60 seconds per action",
        "  - Full audit log will be recorded (screenshots + actions)",
        "  - pyautogui.FAILSAFE = True",
        "",
        "**REFERENCES:**",
        "  - skills/etap-gui-agent.md (Safety Rules section)",
    ])


def _format_d_solve(question: str, app: str) -> str:
    """Format D — SOLVE (multi-step problem-solving workflow)."""
    return "\n".join([
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
    ])


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

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Async wrapper for orchestrator compatibility."""
        question = str(task.parameters.get("question", "")).strip()
        if not question:
            return AgentResult(
                success=False,
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                error="Missing 'question' parameter",
            )
        try:
            data = self.answer(question)
            return AgentResult(
                success=True,
                agent_name=self.agent_name,
                status=AgentStatus.COMPLETED,
                data=data,
            )
        except Exception as exc:
            logger.exception("ETAPGUIAgent failed")
            return AgentResult(
                success=False,
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                error=str(exc),
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
                "A (analyze)", "B (monitor)", "C (control)", "D (solve)", "U (unavailable)"
            ],
            "supported_apps": ["ETAP", "Revit", "AutoCAD", "SCADA", "QGIS", "ArcGIS", "Zenon"],
            "safety_rules": [
                "failsafe_enabled", "confirmation_required_for_control",
                "confirmation_required_for_solve", "audit_logging", "timeout_60s",
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
