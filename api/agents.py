"""
Agent Information API Router
===========================
Handles all AI agent information endpoints.
Separated from main engineering service for better modularity.
"""

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
        from agents.etap_gui_agent import ETAPGUIAgent

        agent = ETAPGUIAgent()
        result = agent.execute_cua_loop(
            question=payload.question,
            max_steps=payload.max_steps,
            require_confirmation=payload.require_confirmation,
            audit_dir=payload.audit_dir,
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
            },
        }
    )
