"""
Agent Information API Router
===========================
Handles all AI agent information endpoints.
Separated from main engineering service for better modularity.
"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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

        return JSONResponse(content={
            "success": True,
            "data": {
                **info,
                "available_prompts": available_prompts,
                "prompt_count": len(available_prompts),
            },
            "trace_id": trace_id,
        })
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("agents_info_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )