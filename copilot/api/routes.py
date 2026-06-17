"""
Engineering Copilot — FastAPI Backend
=====================================
REST API for the Engineering Copilot that orchestrates ETAP, AutoCAD, Revit,
the Translation Engine, and the AI Drawing Engine.

Endpoints:
  POST   /copilot/process            — Process natural language engineering request
  POST   /copilot/translate          — Translate between engineering formats
  GET    /copilot/tools              — List all MCP tools
  POST   /copilot/tools/{name}       — Execute a specific MCP tool
  POST   /copilot/autocad/draw       — Draw entities in AutoCAD
  POST   /copilot/revit/create       — Create entities in Revit
  POST   /copilot/etap/sync          — Synchronize with ETAP
  GET    /copilot/model              — Get the unified engineering model
  POST   /copilot/model              — Set/replace the unified model
  GET    /copilot/status             — Health check and status
  GET    /copilot/statistics         — Usage statistics
  POST   /copilot/validate           — Run design validation
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from autodesk_connector.autocad.connector import AutoCADConnector
from autodesk_connector.revit.connector import RevitConnector
from autodesk_connector.shared.models import (
    Breaker,
    Bus,
    Cable,
    Load,
    Panel,
    Transformer,
    UnifiedEngineeringModel,
)
from copilot.ai.drawing_engine import AIDrawingEngine
from copilot.mcp.server import CopilotMCPServer
from copilot.translation.engine import TranslationEngine
logger = logging.getLogger(__name__)


def _get_etap_provider():
    """Lazy-load ETAP provider to avoid import errors on non-Windows."""
    try:
        from etap_integration.etap_provider import get_etap_provider
        return get_etap_provider()
    except Exception:
        logger.warning("ETAP provider not available — some features will be disabled")
        return None

# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class ProcessRequest(BaseModel):
    prompt: str = Field(..., description="Natural language engineering request")
    autocad_url: str = Field("http://localhost:4820", description="AutoCAD plugin URL")
    revit_url: str = Field("http://localhost:4830", description="Revit plugin URL")
    auto_sync: bool = Field(True, description="Automatically sync to connected systems")


class TranslateRequest(BaseModel):
    source_system: str = Field(..., description="Source system: etap, autocad, revit, unified")
    target_system: str = Field(..., description="Target system: etap, autocad, revit, unified")
    data: dict = Field(..., description="Source data to translate")


class ModelUpdateRequest(BaseModel):
    model_json: str = Field(..., description="Unified Engineering Model as JSON string")


class ToolCallRequest(BaseModel):
    arguments: dict = Field(default_factory=dict, description="Tool arguments")


class SyncRequest(BaseModel):
    project_path: str = Field("", description="Path to project file")
    direction: str = Field("full", description="import, export, or full")
    systems: List[str] = Field(default_factory=lambda: ["etap", "autocad", "revit"])


class ValidateRequest(BaseModel):
    model_json: Optional[str] = Field(None, description="Optional model JSON to validate")
    checks: List[str] = Field(default_factory=lambda: ["voltage", "overcurrent", "coordination"])


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class CopilotAPI:
    """FastAPI router for the Engineering Copilot."""

    def __init__(
        self,
        autocad_url: str = "http://localhost:4820",
        revit_url: str = "http://localhost:4830",
    ):
        self.mcp = CopilotMCPServer(
            autocad_url=autocad_url,
            revit_url=revit_url,
        )
        self.translation = TranslationEngine()
        self.etap_provider = _get_etap_provider()
        self.ai_engine = AIDrawingEngine(
            autocad_connector=self.mcp.autocad,
            revit_connector=self.mcp.revit,
            etap_provider=self.etap_provider,
        )
        self.start_time = time.time()
        self._call_count = 0

    def get_router(self) -> APIRouter:
        """Create and return the FastAPI router."""
        router = APIRouter(prefix="/copilot", tags=["Engineering Copilot"])

        @router.post("/process")
        async def process_intent(request: ProcessRequest):
            """Process a natural language engineering request.

            Parses intent, generates model, draws in AutoCAD,
            syncs to Revit/ETAP, and validates the design.
            """
            self._call_count += 1
            return self.ai_engine.process(request.prompt)

        @router.post("/translate")
        async def translate(request: TranslateRequest):
            """Translate engineering data between different system formats."""
            self._call_count += 1
            result = self.translation.translate(
                source_system=request.source_system,
                target_system=request.target_system,
                data=request.data,
            )
            return {"success": True, "result": result}

        @router.get("/tools")
        async def list_tools():
            """List all available MCP tools with their schemas."""
            return {
                "success": True,
                "tools": self.mcp.list_tools(),
                "count": len(self.mcp.list_tools()),
            }

        @router.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, request: ToolCallRequest):
            """Execute a specific MCP tool."""
            self._call_count += 1
            result = self.mcp.call_tool(tool_name, request.arguments)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error"))
            return result

        @router.get("/model")
        async def get_model():
            """Get the current unified engineering model as JSON."""
            return {
                "success": True,
                "model": json.loads(self.mcp._model.to_json()),
            }

        @router.post("/model")
        async def set_model(request: ModelUpdateRequest):
            """Set/replace the unified engineering model."""
            try:
                model = UnifiedEngineeringModel.from_json(request.model_json)
                self.mcp._model = model
                return {"success": True, "message": "Model updated"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid model: {e}")

        @router.post("/etap/sync")
        async def sync_etap(request: SyncRequest):
            """Synchronize with ETAP project."""
            self._call_count += 1
            if not request.project_path:
                raise HTTPException(status_code=400, detail="project_path is required for ETAP sync")
            result = self.mcp.call_tool("sync_etap", {
                "project_path": request.project_path,
                "direction": request.direction,
            })
            return result

        @router.post("/autocad/sync")
        async def sync_autocad(request: SyncRequest):
            """Synchronize with AutoCAD drawing."""
            self._call_count += 1
            if not request.project_path:
                raise HTTPException(status_code=400, detail="project_path is required for AutoCAD sync")
            result = self.mcp.call_tool("sync_autocad", {
                "file_path": request.project_path,
                "direction": "export" if request.direction != "import" else "import",
            })
            return result

        @router.post("/revit/sync")
        async def sync_revit(request: SyncRequest):
            """Synchronize with Revit model."""
            self._call_count += 1
            if not request.project_path:
                raise HTTPException(status_code=400, detail="project_path is required for Revit sync")
            result = self.mcp.call_tool("sync_revit", {
                "model_path": request.project_path,
                "direction": request.direction,
            })
            return result

        @router.post("/autocad/draw")
        async def draw_in_autocad(entity_type: str = Query(...), params: dict = {}):
            """Draw a specific entity in AutoCAD.

            Entity types: bus, transformer, cable, breaker, panel, load, equipment
            """
            self._call_count += 1
            cad = self.mcp.autocad

            if not cad.is_connected:
                raise HTTPException(status_code=503, detail="AutoCAD plugin not connected")

            handlers = {
                "bus": lambda p: cad.draw_bus(Bus(**p)),
                "transformer": lambda p: cad.draw_transformer(Transformer(**p)),
                "cable": lambda p: cad.draw_cable(Cable(**p)),
                "breaker": lambda p: cad.draw_breaker(Breaker(**p)),
                "panel": lambda p: cad.draw_panel(Panel(**p)),
                "load": lambda p: cad.draw_load(Load(**p)),
            }

            handler = handlers.get(entity_type)
            if not handler:
                raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")

            try:
                result = handler(params)
                return {"success": True, "result": result}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @router.post("/validate")
        async def validate_design(request: ValidateRequest):
            """Run engineering validation checks."""
            self._call_count += 1
            if request.model_json:
                # Validate against provided model
                result = self.mcp.call_tool("run_engineering_checks", {
                    "model_json": request.model_json,
                })
            else:
                # Validate current model
                result = self.mcp.call_tool("validate_design", {
                    "check_types": request.checks,
                })
            return result

        @router.get("/status")
        async def status():
            """Health check for the copilot."""
            health = self.mcp.health_check()
            health["uptime_seconds"] = round(time.time() - self.start_time, 2)
            health["calls"] = self._call_count
            health["version"] = "1.0.0"
            return health

        @router.get("/statistics")
        async def statistics():
            """Usage statistics for the copilot."""
            return {
                "success": True,
                "calls": self._call_count,
                "uptime_seconds": round(time.time() - self.start_time, 2),
                "autocad_connected": self.mcp.autocad.is_connected,
                "revit_connected": self.mcp.revit.is_connected,
                "etap_available": self.etap_provider.is_available() if self.etap_provider else False,
                "ai_engine": self.ai_engine.get_statistics(),
                "translation": self.translation.get_statistics(),
            }

        return router


# ---------------------------------------------------------------------------
# Standalone FastAPI app
# ---------------------------------------------------------------------------


def create_app(
    autocad_url: str = "http://localhost:4820",
    revit_url: str = "http://localhost:4830",
) -> FastAPI:
    """Create the standalone FastAPI application.

    Usage
    -----
    >>> from copilot.api.routes import create_app
    >>> app = create_app()
    >>> import uvicorn
    >>> uvicorn.run(app, host="0.0.0.0", port=8080)
    """
    app = FastAPI(
        title="Engineering Copilot API",
        description="AI-powered engineering copilot for ETAP, AutoCAD, and Revit",
        version="1.0.0",
    )

    copilot = CopilotAPI(autocad_url=autocad_url, revit_url=revit_url)
    router = copilot.get_router()
    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "name": "Engineering Copilot",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "tools": "/copilot/tools",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
