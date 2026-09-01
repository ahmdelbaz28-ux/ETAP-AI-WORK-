"""
Agent Information API Router
===========================
Handles all AI agent information endpoints.
Separated from main engineering service for better modularity.

SECURITY AUDIT 2026-08-02 (V-49 fix):
- Added prompt injection sanitization for all user-supplied text
  before passing to AI agents. This prevents common injection patterns
  like "ignore previous instructions", "system:", etc.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import urllib.parse
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, List

import aiofiles
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from api._messages import MSG_INTERNAL_ERROR
from api.dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


# V-49: Prompt injection sanitization — strips common injection patterns
# from user-supplied text before passing to AI agents.
_PROMPT_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # System role impersonation
    (r"(?i)\bsystem\s*:", "[filtered]"),
    (r"(?i)\bassistant\s*:", "[filtered]"),
    (r"(?i)\badmin\s*:", "[filtered]"),
    # Instruction override attempts
    (r"(?i)\bignore\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)", "[filtered]"),
    (r"(?i)\bforget\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)", "[filtered]"),
    (
        r"(?i)\bdisregard\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)",
        "[filtered]",
    ),
    (r"(?i)\bnew\s+instructions?\s*:", "[filtered]"),
    (r"(?i)\boverride\s+(previous|all|default)\s+(instructions?|rules?|settings?)", "[filtered]"),
    (r"(?i)\byou\s+are\s+now\s+", "[filtered]"),
    (r"(?i)\bpretend\s+(you\s+are|to\s+be)\s+", "[filtered]"),
    (r"(?i)\bact\s+as\s+(if\s+you\s+are|a)\s+", "[filtered]"),
    # Data exfiltration
    (r"(?i)\b(reveal|show|display|print|dump|expose)\s+(the\s+)?(system\s+)?prompt", "[filtered]"),
    (
        r"(?i)\b(reveal|show|display|print|dump|expose)\s+(your|the)\s+(instructions?|rules?)",
        "[filtered]",
    ),
    (r"(?i)\bwhat\s+(is|are)\s+your\s+(instructions?|rules?|prompt)", "[filtered]"),
    # Escape attempts
    (r"(?i)\bexec\s*\(", "[filtered]"),
    (r"(?i)\beval\s*\(", "[filtered]"),
    (r"(?i)\b__import__\s*\(", "[filtered]"),
    (r"(?i)\bos\.system\s*\(", "[filtered]"),
    (r"(?i)\bsubprocess\s*\.", "[filtered]"),
]

_MAX_USER_INPUT_LENGTH = 4000


def _sanitize_agent_input(text: str) -> str:
    """V-49: Sanitize user input to prevent prompt injection attacks.

    Strips common injection patterns from user-supplied text before
    passing to AI agents. This is a defense-in-depth measure — the
    LLM should also be instructed to ignore injection attempts, but
    we filter at the API layer to reduce the attack surface.

    Returns the sanitized text, or raises ValueError if the text is
    too long or appears to be a pure injection attempt.
    """
    if not text or not text.strip():
        raise ValueError("Input must not be empty")

    if len(text) > _MAX_USER_INPUT_LENGTH:
        raise ValueError(f"Input must not exceed {_MAX_USER_INPUT_LENGTH} characters")

    sanitized = text
    for pattern, replacement in _PROMPT_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    # If more than 50% of the input was filtered, reject entirely
    if len(sanitized) < len(text) * 0.5:
        raise ValueError("Input appears to be a prompt injection attempt")

    return sanitized


class AgentMetaResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    capabilities: List[str] = []
    model: str = ""
    provider: str = ""


@router.get("")
@router.get("/", include_in_schema=False)
async def get_agents_list(request: Request):
    """Return the full list of all 25 agents for frontend administration.

    Uses the canonical AGENTS list from api.shared_handlers so that every
    endpoint (this one, /api/v1/info, the HF Space homepage) reports the
    same 25 agents with their standards and status fields.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from api.shared_handlers import AGENTS

        # Enrich the shared AGENTS list with capabilities + model + provider
        # metadata so the frontend administration panel can display it.
        capability_map = {
            "load-flow-agent": ["load_flow", "voltage_profile", "power_losses"],
            "short-circuit-agent": ["short_circuit", "iec_60909", "equipment_rating"],
            "arcflash-agent": ["arc_flash", "ieee_1584", "ppe_category"],
            "protection-agent": ["protection", "relay_coordination", "time_current_curves"],
            "motorstarting-agent": ["motor_starting", "voltage_dip", "acceleration"],
            "stability-agent": ["stability", "swing_equation", "critical_clearing_time"],
            "harmonic-agent": ["harmonic", "ieee_519", "filter_design"],
            "cable-sizing-agent": ["cable_sizing", "iec_60364", "voltage_drop"],
            "earth-grid-agent": ["earth_grid", "ieee_80", "step_touch_voltage"],
            "opf-agent": ["opf", "economic_dispatch", "optimal_power_flow"],
            "renewable-agent": ["renewable", "solar", "wind", "ieee_1547"],
            "battery-storage-agent": ["battery_storage", "bess", "dispatch_optimization"],
            "scada-agent": ["scada", "iec_61850", "real_time_monitoring"],
            "digital-twin-agent": ["digital_twin", "iec_61970", "state_estimation"],
            "predictive-agent": ["predictive_maintenance", "iso_13381", "failure_prediction"],
            "anomaly-agent": ["anomaly_detection", "ieee_1159", "pattern_recognition"],
            "coordination-agent": ["coordination", "iec_60255", "relay_coordination"],
            "report-agent": ["report_generation", "ieee_3002_7", "documentation"],
            "validation-agent": ["validation", "iec_60038", "compliance_checking"],
            "etap-engineer-agent": ["etap_engineering", "etap_manual", "study_setup"],
            "goal-planner-agent": ["goal_planning", "task_decomposition", "workflow"],
            "weather-agent": ["weather", "iec_60721", "environmental_analysis"],
            "power-system-coordinator": ["coordination", "orchestration", "all_studies"],
            "etap-expert-agent": ["etap_expert", "format_a_b_c_d", "6_step_workflow"],
            "etap-gui-agent": ["gui_automation", "cua", "screenshot_analysis"],
        }
        agents_list = []
        for a in AGENTS:
            agents_list.append(
                {
                    "id": a["id"],
                    "name": a["name"],
                    "description": a.get("description", ""),
                    "standard": a.get("standard", ""),
                    "status": a.get("status", "active"),
                    "capabilities": capability_map.get(a["id"], []),
                    "model": "gpt-4o",
                    "provider": "openai",
                }
            )

        return JSONResponse(
            content={
                "success": True,
                "count": len(agents_list),
                "total": len(agents_list),
                "agents": agents_list,
                "trace_id": trace_id,
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("agents_list_failed error=%s", str(e), extra={"trace_id": trace_id})
        # Return an empty list as fallback
        return JSONResponse(
            content={"success": False, "count": 0, "total": 0, "agents": [], "trace_id": trace_id},
            status_code=500,
        )


# NOTE (P7c route-precedence fix): this static route MUST be registered
# BEFORE the parameterized ``GET /{agent_id}`` catch-all below. FastAPI
# matches routes in registration order; registering ``/mcp-servers`` after
# the catch-all caused it to be shadowed (404 "Agent not found").
@router.get("/mcp-servers")
async def list_mcp_servers(
    request: Request,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Return the list of MCP (Model Context Protocol) servers configured for the platform.

    Reads from `.mcp.json` at repo root (or path in `MCP_CONFIG_PATH` env var).
    Secret fields (api_key, token, secret, password) are masked to '***REDACTED***'
    so the UI can render server metadata without exposing credentials.

    Each server entry contains: id, name, type (stdio|http|websocket if present),
    command, args, status ('configured' — runtime status is not yet probed),
    env_keys (key names only, values redacted).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from pathlib import Path as _Path

        config_path = os.getenv(
            "MCP_CONFIG_PATH",
            str(_Path(__file__).resolve().parent.parent / ".mcp.json"),
        )
        path = _Path(config_path)
        if not path.exists():
            return JSONResponse(
                content={
                    "success": True,
                    "data": {
                        "servers": [],
                        "config_path": str(path),
                        "message": "No .mcp.json found — MCP not configured.",
                    },
                    "trace_id": trace_id,
                }
            )

        raw = json.loads(path.read_text(encoding="utf-8"))
        servers_raw = raw.get("mcpServers", raw.get("servers", {}))

        SECRET_KEY_HINTS = ("key", "token", "secret", "password", "credential")
        servers: list[dict[str, Any]] = []
        for sid, scfg in servers_raw.items():
            env = scfg.get("env", {}) or {}
            redacted_env: dict[str, str] = {}
            for k, _v in env.items():
                if any(h in k.lower() for h in SECRET_KEY_HINTS):
                    redacted_env[k] = "***REDACTED***"
                else:
                    redacted_env[k] = "***REDACTED***"  # mask all env values by default

            servers.append(
                {
                    "id": sid,
                    "name": sid.replace("_", " ").replace("-", " ").title(),
                    "type": scfg.get("type", "stdio"),
                    "command": scfg.get("command", ""),
                    "args": scfg.get("args", []),
                    "env_keys": list(env.keys()),
                    "env_redacted": redacted_env,
                    "status": "configured",
                }
            )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "servers": servers,
                    "total": len(servers),
                    "config_path": str(path),
                },
                "trace_id": trace_id,
            }
        )
    except json.JSONDecodeError as e:
        logger.exception("mcp_servers_config_invalid error=%s", str(e))
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "errors": [f"MCP config is not valid JSON: {e}"],
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        logger.exception("mcp_servers_failed error=%s", str(e))
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.get("/{agent_id}")
async def get_agent_by_id(agent_id: str, request: Request):
    """Return metadata for a specific agent by ID."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from api.shared_handlers import AGENTS

        # Find agent by ID
        agent = None
        for a in AGENTS:
            if a["id"] == agent_id:
                agent = a
                break
        if agent is None:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Agent not found", "trace_id": trace_id},
            )

        # Capability map (same as get_agents_list)
        capability_map = {
            "load-flow-agent": ["load_flow", "voltage_profile", "power_losses"],
            "short-circuit-agent": ["short_circuit", "iec_60909", "equipment_rating"],
            "arcflash-agent": ["arc_flash", "ieee_1584", "ppe_category"],
            "protection-agent": ["protection", "relay_coordination", "time_current_curves"],
            "motorstarting-agent": ["motor_starting", "voltage_dip", "acceleration"],
            "stability-agent": ["stability", "swing_equation", "critical_clearing_time"],
            "harmonic-agent": ["harmonic", "ieee_519", "filter_design"],
            "cable-sizing-agent": ["cable_sizing", "iec_60364", "voltage_drop"],
            "earth-grid-agent": ["earth_grid", "ieee_80", "step_touch_voltage"],
            "opf-agent": ["opf", "economic_dispatch", "optimal_power_flow"],
            "renewable-agent": ["renewable", "solar", "wind", "ieee_1547"],
            "battery-storage-agent": ["battery_storage", "bess", "dispatch_optimization"],
            "scada-agent": ["scada", "iec_61850", "real_time_monitoring"],
            "digital-twin-agent": ["digital_twin", "iec_61970", "state_estimation"],
            "predictive-agent": ["predictive_maintenance", "iso_13381", "failure_prediction"],
            "anomaly-agent": ["anomaly_detection", "ieee_1159", "pattern_recognition"],
            "coordination-agent": ["coordination", "iec_60255", "relay_coordination"],
            "report-agent": ["report_generation", "ieee_3002_7", "documentation"],
            "validation-agent": ["validation", "iec_60038", "compliance_checking"],
            "etap-engineer-agent": ["etap_engineering", "etap_manual", "study_setup"],
            "goal-planner-agent": ["goal_planning", "task_decomposition", "workflow"],
            "weather-agent": ["weather", "iec_60721", "environmental_analysis"],
            "power-system-coordinator": ["coordination", "orchestration", "all_studies"],
            "etap-expert-agent": ["etap_expert", "format_a_b_c_d", "6_step_workflow"],
            "etap-gui-agent": ["gui_automation", "cua", "screenshot_analysis"],
        }

        return JSONResponse(
            content={
                "success": True,
                "agent": {
                    "id": agent["id"],
                    "name": agent["name"],
                    "description": agent.get("description", ""),
                    "standard": agent.get("standard", ""),
                    "status": agent.get("status", "active"),
                    "capabilities": capability_map.get(agent["id"], []),
                    "model": "gpt-4o",
                    "provider": "openai",
                },
                "trace_id": trace_id,
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("get_agent_by_id_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.get("/info")
async def get_agents_info(request: Request):
    """Return metadata for all agents including prompt integration status.

    This endpoint verifies that prompts are loaded into agents at runtime
    and provides prompt handle mapping for debugging and monitoring.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from agents.orchestrator import ChiefEngineeringOrchestrator

        orchestrator = ChiefEngineeringOrchestrator()
        info = orchestrator.get_agents_info()

        # Also list available prompts from the prompt loader
        from agents.prompt_loader import list_available_prompts

        available_prompts = list_available_prompts()

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    **info,
                    "available_prompts": available_prompts,
                    "prompt_count": len(available_prompts),
                },
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("agents_info_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# ETAP Expert Skill chat endpoint
# ---------------------------------------------------------------------------


class ETAPExpertChatRequest(BaseModel):
    """Request body for the ETAP Expert chat endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(
        alias="message",
        min_length=1,
        max_length=4000,
        description="The ETAP-related question to ask the expert agent",
    )
    context: Any = Field(
        default=None,
        description="Optional additional context (voltages, currents, etc.)",
    )

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The ETAP-related question to ask the expert agent",
    )
    context: dict[str, Any] | None = Field(
        default=None, description="Optional additional context (voltages, currents, etc.)"
    )


@router.post("/etap-expert/chat")
async def etap_expert_chat(
    request: Request,
    payload: ETAPExpertChatRequest,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Chat with the ETAP Expert skill agent.

    The agent implements the 6-step workflow (PARSE → SEARCH → VALIDATE →
    SIMULATE → FORMAT → QA) and returns one of four response formats:

    - Format A (Complete)      : ✅ REQUEST ANALYSIS: COMPLETE
    - Format B (Incomplete)    : ⚠️ REQUEST ANALYSIS: INCOMPLETE
    - Format C (Wrong)         : ❌ REQUEST ANALYSIS: INCORRECT APPROACH
    - Format D (ADMS/DER)      : 🔷 ADMS REQUEST ANALYSIS

    Knowledge base: skills/etap-expert.md (4,400+ lines)
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        # V-49: Sanitize user input to prevent prompt injection
        safe_question = _sanitize_agent_input(payload.question)

        from agents.etap_expert_agent import ETAPExpertAgent

        agent = ETAPExpertAgent()
        result = agent.answer(safe_question)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("etap_expert_chat_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# ETAP GUI Agent chat endpoint
# ---------------------------------------------------------------------------


class ETAPGUIChatRequest(BaseModel):
    """Request body for the ETAP GUI Agent chat endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(
        alias="message",
        min_length=1,
        max_length=4000,
        description="The GUI automation question to ask the agent",
    )
    context: Any = Field(
        default=None,
        description="Optional additional context (app name, etc.)",
    )


@router.post("/etap-gui/chat")
async def etap_gui_chat(
    request: Request,
    payload: ETAPGUIChatRequest,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Chat with the ETAP GUI Agent (Computer Use Agent).

    The agent classifies the question into one of four modes:
    - Analyze (Format A) — read-only inspection
    - Monitor (Format B) — passive observation
    - Control (Format C) — modifies app state (REQUIRES CONFIRMATION)
    - Solve (Format D) — multi-step problem-solving (REQUIRES CONFIRMATION)

    If GUI deps (pyautogui, pytesseract, opencv) are unavailable, returns
    Format U (graceful fallback) — never crashes.

    Knowledge base: skills/etap-gui-agent.md (440+ lines)
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        # V-49: Sanitize user input to prevent prompt injection
        safe_question = _sanitize_agent_input(payload.question)

        from agents.etap_gui_agent import ETAPGUIAgent

        agent = ETAPGUIAgent()
        result = agent.answer(safe_question)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("etap_gui_chat_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


class ETAPGUIExecuteRequest(BaseModel):
    """Request body for the ETAP GUI Agent REAL CUA execution endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(
        alias="message",
        min_length=1,
        max_length=4000,
        description="The objective to accomplish (e.g., 'Open ETAP and run Load Flow')",
    )
    max_steps: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Hard safety limit on CUA loop iterations (default: 15)",
    )
    require_confirmation: bool = Field(
        default=True,
        description="If True, CONTROL/SOLVE actions pause for human approval",
    )
    audit_dir: str | None = Field(
        default=None,
        description="Directory for before/after screenshots (default: /tmp/cua_audit)",
    )
    start_url: str | None = Field(
        default=None,
        description=(
            "URL to navigate to before starting the CUA loop (Browser CUA only). "
            "On desktop (pyautogui), this is ignored. On headless servers with "
            "Playwright, the agent opens this URL in a headless Chromium and "
            "controls the web page. Example: 'https://your-app.com/dashboard'"
        ),
    )


@router.post("/etap-gui/execute")
async def etap_gui_execute(
    request: Request,
    payload: ETAPGUIExecuteRequest,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Execute the REAL CUA Loop — captures screenshots, analyzes them via
    Gemini Vision, and drives pyautogui to click/type/hotkey.

    This is the actual Computer Use Agent execution (not just planning).
    The agent:
      1. Captures a screenshot via pyautogui.screenshot()
      2. Sends it to Gemini Vision API for analysis
      3. Receives structured JSON: description, ui_elements, next_action
      4. Executes the next_action (click / type / hotkey / wait / done)
      5. Re-screenshots to verify the action succeeded
      6. Repeats until objective_complete=true or max_steps reached

    Every step is logged with before/after screenshots in audit_dir.

    SAFETY:
      - pyautogui.FAILSAFE = True (move mouse to corner = immediate stop)
      - 60-second timeout per action
      - CONTROL/SOLVE actions require explicit confirmation (via require_confirmation)
      - Destructive dialogs (Delete/Format/Override/Reset) are NEVER auto-clicked

    On headless servers (HF Space, CI), returns Format U fallback — never crashes.

    Required env vars (for real execution):
      - GEMINI_API_KEY — Google AI Studio API key
      - DISPLAY or WAYLAND_DISPLAY — X11/Wayland session (Linux desktop)
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from agents.etap_gui_agent import ETAPGUIAgent
        from compat import to_thread

        agent = ETAPGUIAgent()

        # Run in thread to avoid Playwright Sync API + asyncio conflict
        result = await to_thread(
            agent.execute_cua_loop,
            question=payload.question,
            max_steps=payload.max_steps,
            require_confirmation=payload.require_confirmation,
            audit_dir=payload.audit_dir,
            start_url=payload.start_url,
        )

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("etap_gui_execute_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.get("/etap-gui/health")
async def etap_gui_health(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Health check for the ETAP GUI Agent CUA execution capabilities.

    Returns whether the CUA Loop can run in the current environment:
      - pyautogui availability
      - display server (X11/Wayland)
      - Gemini Vision SDK + API key
      - PIL/Pillow
      - Tesseract (optional OCR fallback)
    """
    from agents.etap_gui_agent import ETAPGUIAgent, _check_gui_deps
    from integrations.gemini_vision import gemini_vision

    deps_ok, missing = _check_gui_deps()
    agent = ETAPGUIAgent()
    info = agent.get_agent_info()

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "cua_loop_available": deps_ok,
                "missing_dependencies": missing,
                "gemini_vision": gemini_vision.health_check(),
                "agent_info": info,
                # Life safety status — non-bypassable safety layer
                "life_safety": _get_life_safety_status(),
            },
        },
    )


# ─── Life Safety endpoints ──────────────────────────────────────────────────
# These endpoints expose the EMERGENCY STOP (kill switch) and the safety
# audit trail. They are critical for life-safety compliance.


def _get_life_safety_status() -> dict:
    """Get the current life safety system status."""
    from agents.life_safety import life_safety_guard

    return life_safety_guard.health_check()


@router.post("/etap-gui/kill-switch/activate", tags=["Agents", "Safety"])
async def etap_gui_activate_kill_switch(
    request: Request,
    reason: str = "manual_api_call",
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """🚨 EMERGENCY STOP — Activate the CUA kill switch.

    Once activated, the CUA Loop will abort on the next action check.
    The kill switch is file-based (/tmp/cua_kill_switch) so it works
    even if the API server is unresponsive.

    Use cases:
      - Operator sees the agent clicking the wrong button
      - Engineering review reveals a hazardous action plan
      - Process safety system triggers an alarm
      - Manual override during commissioning

    After activation, the CUA Loop cannot execute ANY action until
    /etap-gui/kill-switch/deactivate is called.
    """
    from agents.life_safety import activate_kill_switch

    activate_kill_switch(reason=reason)
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "kill_switch_active": True,
                "reason": reason,
                "activated_at": datetime.now(UTC).isoformat(),
                "message": "CUA Loop will abort on next action. Call /deactivate to resume.",
            },
        },
    )


@router.post("/etap-gui/kill-switch/deactivate", tags=["Agents", "Safety"])
async def etap_gui_deactivate_kill_switch(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Deactivate the CUA kill switch.

    Use with caution — only after the safety issue that triggered the
    kill switch has been resolved and reviewed.
    """
    from agents.life_safety import deactivate_kill_switch, is_kill_switch_active

    was_active = deactivate_kill_switch()
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "was_active": was_active,
                "kill_switch_active": is_kill_switch_active(),
                "message": "Kill switch deactivated. CUA Loop can resume."
                if was_active
                else "Kill switch was not active.",
            },
        },
    )


@router.get("/etap-gui/safety/health", tags=["Agents", "Safety"])
async def etap_gui_safety_health(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Get the life safety system status.

    Returns:
      - kill_switch_active: whether the emergency stop is active
      - audit_chain_valid: whether the tamper-evident audit log is intact
      - audit_chain_broken_entries: any broken entries (indicates tampering)
      - lethal_patterns_count: how many lethal patterns are blocked
      - dual_confirmation_patterns_count: how many patterns need 2 humans
      - cooldown_seconds: mandatory pause between control actions
      - degraded_vision_sources: which vision backends are read-only
    """
    return JSONResponse(content={"success": True, "data": _get_life_safety_status()})


@router.get("/etap-gui/safety/audit/verify", tags=["Agents", "Safety"])
async def etap_gui_safety_audit_verify(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Verify the integrity of the tamper-evident audit log.

    The audit log uses SHA-256 chaining — each entry's hash depends on
    the previous entry. Any modification to a past entry breaks the chain.

    Returns:
      - is_valid: True if the entire chain is intact
      - broken_entries: list of broken entry IDs (empty if valid)
    """
    from agents.life_safety import life_safety_guard

    is_valid, broken = life_safety_guard.audit_log.verify_chain()
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "is_valid": is_valid,
                "broken_entries": broken,
                "total_broken": len(broken),
                "message": "Audit chain is intact"
                if is_valid
                else f"Audit chain has {len(broken)} broken entries — possible tampering!",
            },
        },
    )


# ─── SIEM endpoints ─────────────────────────────────────────────────────────


@router.get("/etap-gui/siem/health", tags=["Agents", "Safety"])
async def etap_gui_siem_health(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Get the SIEM Syslog forwarder status.

    Returns whether SIEM forwarding is enabled, which protocol is used
    (udp/tcp/tls/file), and the target host or log file path.
    """
    from integrations.siem_syslog import siem_forwarder

    return JSONResponse(content={"success": True, "data": siem_forwarder.health_check()})


@router.get("/etap-gui/siem/events", tags=["Agents", "Safety"])
async def etap_gui_siem_events(
    limit: int = 50,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Read recent SIEM events from the logging-only JSONL file.

    Only available when SIEM_LOG_FILE is set (logging-only mode).
    Returns the last N events (default 50, max 200).
    """
    from integrations.siem_syslog import siem_forwarder

    if not siem_forwarder.logging_only or not siem_forwarder.log_file:
        return JSONResponse(
            content={
                "success": False,
                "error": "logging_only_mode_not_active",
                "message": "Set SIEM_LOG_FILE env var to enable event viewing",
            },
            status_code=400,
        )

    log_path = siem_forwarder.log_file
    if not os.path.exists(log_path):
        return JSONResponse(
            content={
                "success": True,
                "data": {"events": [], "total": 0, "message": "No events yet"},
            },
        )

    # Read last N lines (efficient for large files)
    limit = min(max(limit, 1), 200)
    events: list = []
    try:
        async with aiofiles.open(  # NOSONAR
            log_path, encoding="utf-8"
        ) as fh:
            lines = await fh.readlines()
        # Take the last N lines
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        logger.exception("agent_events_read_failed")
        return JSONResponse(
            content={
                "success": False,
                "error": "read_failed",
                "message": "Failed to read agent events",
            },
            status_code=500,
        )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "events": events,
                "total": len(events),
                "log_file": log_path,
            },
        },
    )


# ---------------------------------------------------------------------------
# AhmedETAP Orchestration Skill — /api/v1/agents/ahmed-etap/*
# ---------------------------------------------------------------------------


class AhmedETAPOrchestrateRequest(BaseModel):
    """Request body for the AhmedETAP skill orchestration endpoint.

    The skill wraps any of the 24 underlying agents and enforces:
      - SharedContext (single source of truth)
      - Token budget with compression at 70 %
      - Deterministic MathGuard on every numerical claim
      - Mandatory Peer Review per REFERENCE.md matrix
    """

    model_config = ConfigDict(populate_by_name=True)

    study_type: str = Field(
        ...,
        description="Canonical study type (load_flow, short_circuit, arc_flash, ...). "
        "Aliases are normalised: fault→short_circuit, coordination→protection_coordination.",
    )
    project_name: str = Field(
        default="default",
        description="Project reference name (for SharedContext.project).",
    )
    base_mva: float = Field(default=100.0, description="Per-unit base MVA for the project.")
    base_kv: float = Field(default=115.0, description="Per-unit base kV for the project.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Study-specific parameters passed to the Lead Agent.",
    )
    claim_value: float = Field(
        ...,
        description="The numerical value the Lead Agent claims as the answer. "
        "MathGuard recomputes this and compares within 0.01 % tolerance.",
    )
    claim_unit: str = Field(
        default="pu",
        description="Unit string the Lead Agent claims (kV, A, MVA, pu, ...).",
    )
    quantity_kind: str = Field(
        default="voltage",
        description="Quantity kind for units check (voltage, current, power, energy, ...).",
    )
    expected_unit: str | None = Field(
        default=None,
        description="If set, MathGuard requires the agent's unit to match exactly.",
    )
    budget_tokens: int = Field(
        default=8000,
        description="Token budget for the workflow. Compression triggers at 70 %.",
    )
    lead_agent: str | None = Field(
        default=None,
        description="Override the default Lead Agent (e.g. 'load_flow'). "
        "If omitted, derived from study_type.",
    )


@router.post("/ahmed-etap/orchestrate")
async def ahmed_etap_orchestrate(
    request: Request,
    payload: AhmedETAPOrchestrateRequest,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Run a study through the AhmedETAP orchestration skill pipeline.

    Pipeline (per skills/ahmed-etap/SKILL.md):
        Parse → canonical StudyType
        → load SharedContext with project + standards
        → route to Lead Agent (run computation)
        → MathGuard (deterministic Python recompute, 0.01 % tolerance)
        → Peer Review (per REFERENCE.md matrix)
        → ship | loop back (max 2 retries)

    Returns the full :class:`OrchestrationResult` including:
      - ``verdict``: approved / blocked_math_guard / blocked_peer_review / ...
      - ``math_guard``: { passed, reason, claim_value, recomputed_value, units_ok }
      - ``peer_review``: { passed, reviewer, notes }
      - ``shared_context``: snapshot of the shared context (budget, tasks, errors)
      - ``response``: the Lead Agent's result dict (only present if approved)
      - ``iterations``: number of iterations (1 = first try, 3 = exhausted)
      - ``elapsed_seconds``: wall-clock time

    Knowledge base: skills/ahmed-etap/SKILL.md
    Reference:      skills/ahmed-etap/REFERENCE.md
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        # Resolve the canonical StudyType enum for the inner task
        from agents.ahmed_etap_orchestrator import AhmedETAPSkillAgent, canonicalize_study_type
        from agents.orchestrator import (
            EngineeringTask as _ET,  # noqa: N814
        )
        from agents.orchestrator import (
            StudyType as _ST,  # noqa: N814
        )
        from agents.orchestrator import (
            get_orchestrator,
        )

        canonical = canonicalize_study_type(payload.study_type)
        try:
            st_enum = _ST(canonical)
        except ValueError:
            st_enum = _ST.LOAD_FLOW

        # Build the workflow parameters expected by AhmedETAPSkillAgent.execute
        workflow_params: dict[str, Any] = {
            "study_type": payload.study_type,
            "project": {
                "name": payload.project_name,
                "base_mva": payload.base_mva,
                "base_kv": payload.base_kv,
            },
            "parameters": payload.parameters,
            "claim_value": payload.claim_value,
            "claim_unit": payload.claim_unit,
            "quantity_kind": payload.quantity_kind,
            "expected_unit": payload.expected_unit,
            "budget_tokens": payload.budget_tokens,
        }
        if payload.lead_agent:
            workflow_params["lead_agent"] = payload.lead_agent

        skill_task = _ET(
            task_id=f"ahmed_etap_api_{int(datetime.now(UTC).timestamp())}",
            description=f"Skill-orchestrated {payload.study_type}",
            study_types=[st_enum],
            parameters=workflow_params,
        )

        agent = AhmedETAPSkillAgent(orchestrator=get_orchestrator())
        result = await agent.execute(skill_task)

        return JSONResponse(
            content={
                "success": result.validation_status,
                "data": result.data,
                "trace_id": trace_id,
            },
            status_code=200 if result.validation_status else 422,
        )
    except Exception as e:
        from logging import getLogger

        getLogger("engineering_service").exception(
            "ahmed_etap_orchestrate_failed error=%s",
            str(e),
            extra={"trace_id": trace_id},
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# MCP server health probe (P7c)
# ---------------------------------------------------------------------------


_RESTRICTED_IP_MSG = (
    "Target resolves to a restricted network destination (SSRF guard)."
)
_HTTP_BLOCKED_MSG = "Remote MCP endpoints must use HTTPS (HTTP transport is disabled)."


def _is_restricted_ip(ip: str) -> bool:
    """True for loopback/private/link-local/multicast/reserved/unspecified IPs.

    IPv4-mapped IPv6 addresses (e.g. ``::ffff:127.0.0.1``) are unwrapped to
    their IPv4 form first so mapped restricted addresses cannot slip through
    on Python versions whose ``ipaddress`` properties do not account for
    IPv4-mapped IPv6.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _probe_headers() -> dict[str, str]:
    """Minimal headers — NO auth, NO cookies, NO secrets."""
    return {
        "User-Agent": "ETAP-AI-mcp-health-probe/1.0",
        "Accept": "application/json",
    }


class _PinnedAddressBackend:
    """httpcore network-backend adapter that pins TCP connections to
    pre-validated IP addresses (SSRF anti-DNS-rebinding guard).

    ``socket.getaddrinfo()`` in :func:`_probe_remote_mcp` decides WHERE the
    probe is allowed to go, but a plain ``httpx.Client().get(url)`` would let
    the HTTP client resolve the hostname a second time when it opens the
    socket — a TOCTOU / DNS-rebinding gap (first resolution -> public IP,
    second resolution -> private IP). This adapter closes that gap: every TCP
    connection is opened to one of the already-validated IP addresses, while
    the request URL keeps the original hostname so the ``Host`` header, TLS
    SNI, and certificate-verification semantics are preserved exactly.

    Duck-types the ``httpcore.NetworkBackend`` interface (only
    ``connect_tcp`` is needed for sync TCP connections).
    """

    def __init__(
        self,
        pinned_ips: list,
        delegate: Any = None,
    ) -> None:
        self._pinned_ips = [ip for ip in pinned_ips if ip]
        self._delegate = delegate  # None -> real httpcore.SyncBackend

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Any = None,
        local_address: Any = None,
        socket_options: Any = None,
    ) -> Any:
        # ``host`` is deliberately IGNORED: connections must be made to the
        # validated destination, never to a fresh (re)resolution of it.
        if not self._pinned_ips:
            raise OSError("No validated IP address available for connection")
        import httpcore

        delegate = self._delegate
        if delegate is None:
            delegate = httpcore.SyncBackend()
        last_exc: Any = None
        for pinned_ip in self._pinned_ips:
            try:
                return delegate.connect_tcp(
                    pinned_ip, port, timeout, local_address, socket_options
                )
            except Exception as exc:  # noqa: BLE001 — try the next validated IP
                last_exc = exc
        if last_exc is not None:
            raise last_exc
        raise OSError("Connection to validated destination failed")


def _open_pinned_connection_pool(pinned_ips: list) -> Any:
    """Create an httpcore connection pool pinned to the validated IPs.

    httpcore (the engine under httpx) never follows redirects, performs full
    TLS verification against the request hostname, and lets us inject the
    destination-pinning backend above. ``pinned_ips`` must already have been
    SSRF-validated by the caller.
    """
    import httpcore

    return httpcore.ConnectionPool(network_backend=_PinnedAddressBackend(pinned_ips))


def _resolve_mcp_config_path() -> str:
    """Resolve the configured MCP config path (same source as list_mcp_servers)."""
    from pathlib import Path as _Path

    return os.getenv(
        "MCP_CONFIG_PATH",
        str(_Path(__file__).resolve().parent.parent / ".mcp.json"),
    )


def _probe_stdio_mcp(server_id: str, server_config: dict) -> dict[str, Any]:
    """Resolve a stdio launch command WITHOUT executing it."""
    command = str(server_config.get("command", "") or "").strip()
    if not command:
        return {
            "id": server_id,
            "transport": "stdio",
            "connected": False,
            "status": "invalid",
            "message": "MCP server has no launch command configured.",
        }
    resolvable = shutil.which(command) is not None
    return {
        "id": server_id,
        "transport": "stdio",
        "connected": False,
        "command_resolvable": resolvable,
        "status": "ready" if resolvable else "unreachable",
        "message": (
            "Local command is resolvable; the server is NOT spawned by this probe."
            if resolvable
            else "Local command is not resolvable on this host."
        ),
    }


def _probe_remote_mcp(
    server_id: str, server_config: dict, transport: str
) -> dict[str, Any]:
    """SSRF-guarded bare-GET health probe for remote MCP endpoints.

    Security properties:
      * Every address the hostname resolves to is validated; the connection is
        then PINNED to the validated IP addresses (no second DNS resolution).
      * The request URL keeps the original hostname, so Host/TLS SNI and
        certificate verification are unaffected by the pinning.
      * Redirects are never followed (httpcore has no redirect following).
      * HTTP is blocked unless MCP_HEALTH_ALLOW_HTTP is explicitly enabled.
      * Only bare probe headers are sent — no credentials of any kind.
    """
    url = str(server_config.get("url") or server_config.get("endpoint") or "").strip()
    if not url:
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP server has no url/endpoint configured.",
        }

    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL is not parseable.",
        }

    if parsed.scheme not in ("http", "https"):
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL scheme must be http/https.",
        }

    allow_http = os.getenv("MCP_HEALTH_ALLOW_HTTP", "").lower() in (
        "1", "true", "yes", "on",
    )
    if parsed.scheme == "http" and not allow_http:
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "blocked",
            "message": _HTTP_BLOCKED_MSG,
        }

    host = parsed.hostname or ""
    if not host:
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL has no host.",
        }

    fallback_port = 443 if parsed.scheme == "https" else 80
    try:
        addrinfos = socket.getaddrinfo(
            host, port if port else fallback_port, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "unreachable",
            "message": "Remote MCP endpoint host could not be resolved.",
        }

    # Validate EVERY resolved address and keep the validated set for the
    # actual connection. The HTTP client must never re-resolve the hostname
    # (DNS-rebinding / TOCTOU SSRF guard) — see _PinnedAddressBackend.
    pinned_ips: list[str] = []
    for addr_info in addrinfos:
        candidate_ip = str(addr_info[4][0])
        if _is_restricted_ip(candidate_ip):
            return {
                "id": server_id,
                "transport": transport,
                "connected": False,
                "status": "blocked",
                "message": _RESTRICTED_IP_MSG,
            }
        if candidate_ip not in pinned_ips:
            pinned_ips.append(candidate_ip)

    try:
        pool = _open_pinned_connection_pool(pinned_ips)
        try:
            core_resp = pool.request(
                "GET",
                url,
                headers=_probe_headers(),
                extensions={
                    "timeout": {
                        "connect": 5.0,
                        "read": 5.0,
                        "write": 5.0,
                        "pool": 5.0,
                    }
                },
            )
            core_resp.read()
            status_code = int(core_resp.status)
        finally:
            pool.close()
        if 200 <= status_code < 300:
            status = "ok"
            message = f"Remote MCP endpoint responded with HTTP {status_code}."
        elif 300 <= status_code < 400:
            # Redirects are NEVER followed: the destination actually connected
            # to was SSRF-validated, but a redirect target would not have been.
            # ``connected`` stays False — only a verified 2xx counts.
            status = "degraded"
            message = (
                f"Remote MCP endpoint responded with HTTP {status_code} "
                "(redirect NOT followed)."
            )
        else:
            status = "degraded"
            message = f"Remote MCP endpoint responded with HTTP {status_code}."
        return {
            "id": server_id,
            "transport": transport,
            "connected": 200 <= status_code < 300,
            "reachable": True,
            "status": status,
            "http_status": status_code,
            "message": message,
        }
    except Exception:  # noqa: BLE001
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "reachable": False,
            "status": "unreachable",
            "message": "Remote MCP endpoint did not respond.",
        }


def _probe_mcp_server(server_id: str, server_config: dict) -> dict[str, Any]:
    """Probe a single configured MCP server (never spawns it)."""
    transport = str(server_config.get("type", "stdio")).lower()
    if transport in ("http", "https", "sse", "websocket", "ws", "wss"):
        return _probe_remote_mcp(server_id, server_config, transport)
    return _probe_stdio_mcp(server_id, server_config)


@router.post("/mcp-servers/{server_id}/health")
async def check_mcp_server_health(
    server_id: str,
    request: Request,
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Backend-authoritative health probe for ONE configured MCP server.

    Security (P7c):
      * stdio servers are resolved on PATH but NEVER spawned.
      * Remote endpoints are SSRF-validated (HTTPS-only unless
        MCP_HEALTH_ALLOW_HTTP=1; loopback/RFC1918/link-local blocked) and the
        TCP connection is pinned to the validated IP addresses so the HTTP
        client cannot escape the policy via a second DNS resolution.
      * Redirects are never followed; only a verified 2xx marks ``connected``.
      * No credentials are sent or echoed back.
      * Statuses: ok | degraded | unreachable | blocked | invalid.
      * ``connected`` is only True after a verified 2xx HTTP/S probe.
      * Authorization: MCP config is platform-global; this endpoint is behind
        the same ``get_api_key`` boundary as the server list endpoint.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    from pathlib import Path as _Path

    path = _Path(_resolve_mcp_config_path())
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "errors": ["MCP config not found"],
                "trace_id": trace_id,
            },
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.exception("mcp_health_config_invalid error=%s", str(e))
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "errors": ["MCP config is not valid JSON"],
                "trace_id": trace_id,
            },
        )

    servers_raw = raw.get("mcpServers", raw.get("servers", {}))
    server_config = servers_raw.get(server_id)
    if server_config is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "errors": ["MCP server not found"],
                "trace_id": trace_id,
            },
        )

    try:
        data = _probe_mcp_server(server_id, server_config)
    except Exception as e:  # noqa: BLE001
        logger.exception(
            "mcp_health_probe_failed server=%s error=%s", server_id, str(e)
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "errors": [MSG_INTERNAL_ERROR],
                "trace_id": trace_id,
            },
        )

    data["checked_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(
        "mcp_health_checked server=%s transport=%s status=%s trace_id=%s",
        server_id,
        data.get("transport"),
        data.get("status"),
        trace_id,
    )
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": data, "trace_id": trace_id},
    )


@router.get("/ahmed-etap/info")
async def ahmed_etap_info(
    _: str = Depends(
        get_api_key
    ),  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
):
    """Return metadata about the AhmedETAP orchestration skill.

    Reports which principles are enforced, the peer-review matrix, the
    canonical study types, and the token budget defaults — i.e. everything
    a client needs to construct a valid ``/ahmed-etap/orchestrate`` call.
    """
    from agents.ahmed_etap_orchestrator import (
        PEER_REVIEW_MATRIX,
        AhmedETAPOrchestrator,
        AhmedETAPSkillAgent,
        TokenBudget,
        load_skill_text,
    )

    agent = AhmedETAPSkillAgent()
    return JSONResponse(
        content={
            "success": True,
            "data": {
                **agent.get_agent_info(),
                "skill_text_chars": len(load_skill_text()),
                "peer_review_matrix": PEER_REVIEW_MATRIX,
                "token_budget_defaults": TokenBudget.DEFAULTS,
                "max_retries": AhmedETAPOrchestrator.MAX_RETRIES,
                "math_guard_tolerance_pct": 0.01,
            },
        },
    )
