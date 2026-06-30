"""
Agent Information API Router
===========================
Handles all AI agent information endpoints.
Separated from main engineering service for better modularity.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies import get_api_key

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


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
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("agents_info_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# ETAP Expert Skill chat endpoint
# ---------------------------------------------------------------------------


class ETAPExpertChatRequest(BaseModel):
    """Request body for the ETAP Expert chat endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The ETAP-related question to ask the expert agent",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional additional context (voltages, currents, etc.)"
    )


@router.post("/etap-expert/chat")
async def etap_expert_chat(
    request: Request,
    payload: ETAPExpertChatRequest,
    _: str = Depends(get_api_key),
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
        from agents.etap_expert_agent import ETAPExpertAgent

        agent = ETAPExpertAgent()
        result = agent.answer(payload.question)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("etap_expert_chat_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# ETAP GUI Agent chat endpoint
# ---------------------------------------------------------------------------


class ETAPGUIChatRequest(BaseModel):
    """Request body for the ETAP GUI Agent chat endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The GUI automation question to ask the agent",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional additional context (app name, etc.)"
    )


@router.post("/etap-gui/chat")
async def etap_gui_chat(
    request: Request,
    payload: ETAPGUIChatRequest,
    _: str = Depends(get_api_key),
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
        from agents.etap_gui_agent import ETAPGUIAgent

        agent = ETAPGUIAgent()
        result = agent.answer(payload.question)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("etap_gui_chat_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


class ETAPGUIExecuteRequest(BaseModel):
    """Request body for the ETAP GUI Agent REAL CUA execution endpoint."""

    question: str = Field(
        ...,
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
    audit_dir: Optional[str] = Field(
        default=None,
        description="Directory for before/after screenshots (default: /tmp/cua_audit)",
    )
    start_url: Optional[str] = Field(
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
    _: str = Depends(get_api_key),
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
        import asyncio

        from agents.etap_gui_agent import ETAPGUIAgent

        agent = ETAPGUIAgent()
        # Run in thread to avoid Playwright Sync API + asyncio conflict
        result = await asyncio.to_thread(
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
            }
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("etap_gui_execute_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@router.get("/etap-gui/health")
async def etap_gui_health(
    _: str = Depends(get_api_key),
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
        }
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
    _: str = Depends(get_api_key),
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
        }
    )


@router.post("/etap-gui/kill-switch/deactivate", tags=["Agents", "Safety"])
async def etap_gui_deactivate_kill_switch(
    _: str = Depends(get_api_key),
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
        }
    )


@router.get("/etap-gui/safety/health", tags=["Agents", "Safety"])
async def etap_gui_safety_health(
    _: str = Depends(get_api_key),
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
    _: str = Depends(get_api_key),
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
        }
    )


# ─── SIEM endpoints ─────────────────────────────────────────────────────────


@router.get("/etap-gui/siem/health", tags=["Agents", "Safety"])
async def etap_gui_siem_health(
    _: str = Depends(get_api_key),
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
    _: str = Depends(get_api_key),
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
            }
        )

    # Read last N lines (efficient for large files)
    limit = min(max(limit, 1), 200)
    events: list = []
    try:
        with open(log_path, encoding="utf-8") as fh:
            lines = fh.readlines()
        # Take the last N lines
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError as exc:
        return JSONResponse(
            content={"success": False, "error": "read_failed", "message": str(exc)},
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
        }
    )
