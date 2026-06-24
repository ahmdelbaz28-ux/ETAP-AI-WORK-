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

    question: str = Field(..., min_length=1, max_length=4000,
                          description="The ETAP-related question to ask the expert agent")
    context: Optional[Dict[str, Any]] = Field(default=None,
                                            description="Optional additional context (voltages, currents, etc.)")


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

    question: str = Field(..., min_length=1, max_length=4000,
                          description="The GUI automation question to ask the agent")
    context: Optional[Dict[str, Any]] = Field(default=None,
                                            description="Optional additional context (app name, etc.)")


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
