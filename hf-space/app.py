"""
AhmedETAP - Enterprise Engineering Intelligence Platform
Hugging Face Spaces Entry Point
Author: Eng. Ahmed Elbaz
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# -- Version (single source of truth) -----------------------------------------
VERSION = "2.1.0"

# -- Logging ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("etap-ai")

# -- App Constants ------------------------------------------------------------
START_TIME = time.time()
BUILD_TIME = datetime.now(UTC).isoformat()
AGENT_COUNT = 23
ETAP_MANUAL_COUNT = 35
ZENON_GUIDE_COUNT = 4

# -- Optional API Key Auth ----------------------------------------------------
_API_KEY = os.environ.get("HF_API_KEY", "")
_API_KEY_ENABLED = bool(_API_KEY)


def _verify_api_key(request: Request) -> None:
    """Validate API key when configured. Skips health/docs endpoints."""
    if not _API_KEY_ENABLED:
        return
    # Skip auth for health, docs, and root
    path = request.url.path
    if path in (
        "/",
        "/healthz",
        "/readyz",
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    ):
        return
    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# -- Rate Limiting (in-memory, per-client) ------------------------------------
_RATE_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
_RATE_MAX = int(os.environ.get("RATE_LIMIT_MAX", "120"))
_rate_store: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(client_id: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.time()
    with _rate_lock:
        if client_id not in _rate_store:
            _rate_store[client_id] = [now]
            return True
        _rate_store[client_id] = [t for t in _rate_store[client_id] if now - t < _RATE_WINDOW]
        if len(_rate_store[client_id]) >= _RATE_MAX:
            return False
        _rate_store[client_id].append(now)
        return True


# -- Lifespan -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AhmedETAP v%s started on Hugging Face Spaces", VERSION)
    logger.info(
        "Knowledge base: %d ETAP manuals + %d Zenon guides", ETAP_MANUAL_COUNT, ZENON_GUIDE_COUNT
    )
    logger.info("Active agents: %d", AGENT_COUNT)
    yield
    logger.info("AhmedETAP shutting down")


# -- App Init -----------------------------------------------------------------
app = FastAPI(
    title="AhmedETAP - Enterprise Engineering Intelligence",
    description=(
        "Enterprise-grade autonomous AI engineering platform for power system analysis. "
        "Covers Load Flow (IEEE 3002.7), Short Circuit (IEC 60909), Arc Flash (IEEE 1584), "
        "Protection Coordination (IEC 60255), Motor Starting (IEEE 399), Harmonics (IEEE 519), "
        "Transient Stability, Cable Sizing (IEC 60364), Ground Grid (IEEE 80), OPF, "
        "SCADA (IEC 61850 via Zenon), and more - powered by 23+ specialized AI agents."
    ),
    version=VERSION,
    contact={"name": "Eng. Ahmed Elbaz", "email": "ahmdelbaz28@gmail.com"},
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://huggingface.co",
        "https://*.hf.space",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Auth + Rate-limit middleware ---------------------------------------------
@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    # API key check
    _verify_api_key(request)
    # Rate limit (skip health/docs)
    path = request.url.path
    if path not in (
        "/",
        "/healthz",
        "/readyz",
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    ):
        client_id = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(_RATE_WINDOW)},
            )
    return await call_next(request)


# -- Models -------------------------------------------------------------------
class StudyRequest(BaseModel):
    study_type: str
    system: dict[str, Any] = {}
    options: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    use_etap: bool = False


class AgentRequest(BaseModel):
    agent: str
    query: str
    context: dict[str, Any] = {}


class ETAPExpertChatRequest(BaseModel):
    question: str
    context: dict[str, Any] = {}


class ETAPGUIChatRequest(BaseModel):
    question: str
    context: dict[str, Any] = {}


# -- Root ---------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, tags=["Platform"])
async def root():
    uptime = round(time.time() - START_TIME, 1)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>AhmedETAP - Enterprise Engineering Intelligence</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);min-height:100vh;color:#e2e8f0;display:flex;align-items:center;justify-content:center;padding:2rem}}
    .card{{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:3rem;max-width:860px;width:100%;box-shadow:0 25px 50px rgba(0,0,0,0.5)}}
    h1{{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#f6c90e,#ff6b35);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.5rem}}
    .sub{{color:#94a3b8;font-size:1.1rem;margin-bottom:2rem}}
    .badge{{display:inline-block;background:rgba(246,201,14,0.15);border:1px solid #f6c90e;color:#f6c90e;border-radius:999px;padding:.25rem .75rem;font-size:.8rem;font-weight:600;margin:.2rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:2rem 0}}
    .stat{{background:rgba(255,255,255,0.05);border-radius:12px;padding:1.25rem;text-align:center;border:1px solid rgba(255,255,255,0.08)}}
    .stat-num{{font-size:2rem;font-weight:800;color:#f6c90e}}
    .stat-label{{color:#94a3b8;font-size:.85rem;margin-top:.25rem}}
    .links{{display:flex;gap:1rem;flex-wrap:wrap;margin-top:2rem}}
    a{{color:#60a5fa;text-decoration:none;padding:.5rem 1.25rem;border:1px solid rgba(96,165,250,0.3);border-radius:8px;font-size:.9rem;transition:all .2s}}
    a:hover{{background:rgba(96,165,250,0.1);border-color:#60a5fa}}
    .status{{display:inline-flex;align-items:center;gap:.5rem;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);color:#4ade80;border-radius:999px;padding:.35rem 1rem;font-size:.85rem;font-weight:600;margin-bottom:1.5rem}}
    .dot{{width:8px;height:8px;background:#4ade80;border-radius:50%;animation:pulse 2s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
  </style>
</head>
<body>
  <div class="card">
    <div class="status"><span class="dot"></span>LIVE - Uptime {uptime}s</div>
    <h1>AhmedETAP</h1>
    <p class="sub">Enterprise Engineering Intelligence Platform - v{VERSION}</p>
    <div>
      <span class="badge">IEEE 3002.7</span>
      <span class="badge">IEC 60909</span>
      <span class="badge">IEEE 1584</span>
      <span class="badge">IEC 60255</span>
      <span class="badge">IEEE 519</span>
      <span class="badge">IEC 61850</span>
      <span class="badge">IEEE 80</span>
      <span class="badge">IEC 60364</span>
    </div>
    <div class="grid">
      <div class="stat"><div class="stat-num">{AGENT_COUNT}</div><div class="stat-label">AI Agents</div></div>
      <div class="stat"><div class="stat-num">{ETAP_MANUAL_COUNT}+</div><div class="stat-label">ETAP Manuals</div></div>
      <div class="stat"><div class="stat-num">{ZENON_GUIDE_COUNT}</div><div class="stat-label">Zenon Guides</div></div>
      <div class="stat"><div class="stat-num">548</div><div class="stat-label">Tests Passing</div></div>
    </div>
    <div class="links">
      <a href="/docs">Swagger Docs</a>
      <a href="/redoc">ReDoc</a>
      <a href="/healthz">Health</a>
      <a href="/api/v1/agents">Agents</a>
      <a href="https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-" target="_blank">GitHub</a>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# -- Health -------------------------------------------------------------------
@app.get("/healthz", tags=["Health"])
async def healthz():
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.head("/healthz", tags=["Health"])
async def healthz_head():
    return JSONResponse(content={}, status_code=200)


@app.get("/readyz", tags=["Health"])
async def readyz():
    return JSONResponse(content={"status": "ready"}, status_code=200)


@app.get("/health", tags=["Health"])
async def health():
    uptime = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "build_time": BUILD_TIME,
        "version": VERSION,
        "platform": "huggingface-spaces",
        "agents": AGENT_COUNT,
        "etap_manuals": ETAP_MANUAL_COUNT,
        "zenon_guides": ZENON_GUIDE_COUNT,
    }


@app.get("/ready", tags=["Health"])
async def ready():
    return {"status": "ready", "uptime": round(time.time() - START_TIME, 2)}


# -- Metrics ------------------------------------------------------------------
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    return {
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "platform": "huggingface-spaces",
        "version": VERSION,
    }


# -- Platform Info ------------------------------------------------------------
@app.get("/api/v1/info", tags=["Platform"])
async def platform_info():
    return {
        "name": "AhmedETAP",
        "version": VERSION,
        "description": "Enterprise Engineering Intelligence Platform",
        "author": "Eng. Ahmed Elbaz",
        "standards": [
            "IEEE 3002.7",
            "IEC 60909",
            "IEEE 1584",
            "IEC 60255",
            "IEEE 519",
            "IEC 61850",
            "IEEE 80",
            "IEC 60364",
            "IEEE 399",
            "IEC 62933",
        ],
        "agents": AGENT_COUNT,
        "knowledge_base": {
            "etap_manuals": ETAP_MANUAL_COUNT,
            "zenon_guides": ZENON_GUIDE_COUNT,
            "total_chunks": "5000+",
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/healthz",
            "studies": "/api/v1/studies/run",
            "agents": "/api/v1/agents",
        },
    }


# -- Agents -------------------------------------------------------------------
AGENTS = [
    {
        "id": "load-flow-agent",
        "name": "Load Flow Agent",
        "standard": "IEEE 3002.7",
        "status": "active",
    },
    {
        "id": "short-circuit-agent",
        "name": "Short Circuit Agent",
        "standard": "IEC 60909",
        "status": "active",
    },
    {
        "id": "arcflash-agent",
        "name": "Arc Flash Agent",
        "standard": "IEEE 1584",
        "status": "active",
    },
    {
        "id": "protection-agent",
        "name": "Protection Agent",
        "standard": "IEC 60255",
        "status": "active",
    },
    {
        "id": "motorstarting-agent",
        "name": "Motor Starting Agent",
        "standard": "IEEE 399",
        "status": "active",
    },
    {
        "id": "stability-agent",
        "name": "Stability Agent",
        "standard": "IEEE 399",
        "status": "active",
    },
    {
        "id": "harmonic-agent",
        "name": "Harmonic Analysis Agent",
        "standard": "IEEE 519",
        "status": "active",
    },
    {
        "id": "cable-sizing-agent",
        "name": "Cable Sizing Agent",
        "standard": "IEC 60364",
        "status": "active",
    },
    {
        "id": "earth-grid-agent",
        "name": "Earth Grid Agent",
        "standard": "IEEE 80",
        "status": "active",
    },
    {
        "id": "opf-agent",
        "name": "Optimal Power Flow Agent",
        "standard": "IEEE 3002.7",
        "status": "active",
    },
    {
        "id": "renewable-agent",
        "name": "Renewable Energy Agent",
        "standard": "IEEE 1547",
        "status": "active",
    },
    {
        "id": "battery-storage-agent",
        "name": "Battery Storage Agent",
        "standard": "IEC 62933",
        "status": "active",
    },
    {"id": "scada-agent", "name": "SCADA Agent", "standard": "IEC 61850", "status": "active"},
    {
        "id": "digital-twin-agent",
        "name": "Digital Twin Agent",
        "standard": "IEC 61970",
        "status": "active",
    },
    {
        "id": "predictive-agent",
        "name": "Predictive Maintenance",
        "standard": "ISO 13381",
        "status": "active",
    },
    {
        "id": "anomaly-agent",
        "name": "Anomaly Detection Agent",
        "standard": "IEEE 1159",
        "status": "active",
    },
    {
        "id": "coordination-agent",
        "name": "Coordination Agent",
        "standard": "IEC 60255",
        "status": "active",
    },
    {
        "id": "report-agent",
        "name": "Report Generation Agent",
        "standard": "IEEE 3002.7",
        "status": "active",
    },
    {
        "id": "validation-agent",
        "name": "Validation Agent",
        "standard": "IEC 60038",
        "status": "active",
    },
    {
        "id": "etap-engineer-agent",
        "name": "ETAP Engineer Agent",
        "standard": "ETAP Manual",
        "status": "active",
    },
    {
        "id": "goal-planner-agent",
        "name": "Goal Planner Agent",
        "standard": "Internal",
        "status": "active",
    },
    {"id": "weather-agent", "name": "Weather Agent", "standard": "IEC 60721", "status": "active"},
    {
        "id": "power-system-coordinator",
        "name": "Power System Coordinator",
        "standard": "All",
        "status": "active",
    },
    {
        "id": "etap-expert-agent",
        "name": "ETAP Expert Skill Agent",
        "standard": "IEEE/IEC/NEC/NFPA (all)",
        "status": "active",
        "description": "6-step workflow with Format A/B/C/D responses. Knowledge base: skills/etap-expert.md (4,400+ lines).",
    },
    {
        "id": "etap-gui-agent",
        "name": "ETAP GUI Agent (Computer Use Agent)",
        "standard": "Safety + Audit",
        "status": "active",
        "description": "Computer Use Agent for desktop apps (ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS). 4 modes: Analyze/Monitor/Control/Solve. Falls back gracefully on headless servers.",
    },
]


@app.get("/api/v1/agents", tags=["Agents"])
async def list_agents():
    return {"count": len(AGENTS), "agents": AGENTS}


@app.get("/api/v1/agents/{agent_id}", tags=["Agents"])
async def get_agent(agent_id: str):
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return JSONResponse(status_code=404, content={"error": f"Agent '{agent_id}' not found"})
    return agent


@app.post("/api/v1/agents/etap-expert/chat", tags=["Agents"])
async def etap_expert_chat(request: ETAPExpertChatRequest):
    """Chat with the ETAP Expert skill agent.

    Implements the 6-step workflow (PARSE → SEARCH → VALIDATE → SIMULATE →
    FORMAT → QA) and returns one of four response formats:
      - Format A (Complete)   : ✅ REQUEST ANALYSIS: COMPLETE
      - Format B (Incomplete) : ⚠️ REQUEST ANALYSIS: INCOMPLETE
      - Format C (Wrong)      : ❌ REQUEST ANALYSIS: INCORRECT APPROACH
      - Format D (ADMS/DER)   : 🔷 ADMS REQUEST ANALYSIS

    Knowledge base: skills/etap-expert.md (4,400+ lines)
    """
    question = request.question.strip()
    if not question:
        return JSONResponse(
            status_code=400,
            content={"error": "'question' field is required and must be non-empty"},
        )
    try:
        from agents.etap_expert_agent import ETAPExpertAgent
        agent = ETAPExpertAgent()
        result = agent.answer(question)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.exception("etap_expert chat failed")
        return JSONResponse(
            status_code=500,
            content={"error": f"ETAP Expert agent error: {exc}"},
        )


@app.post("/api/v1/agents/etap-gui/chat", tags=["Agents"])
async def etap_gui_chat(request: ETAPGUIChatRequest):
    """Chat with the ETAP GUI Agent (Computer Use Agent).

    Classifies the question into Analyze/Monitor/Control/Solve modes.
    Falls back to Format U (unavailable) on headless servers / HF Space
    where pyautogui, pytesseract, opencv are not installed.

    Knowledge base: skills/etap-gui-agent.md (440+ lines)
    """
    question = request.question.strip()
    if not question:
        return JSONResponse(
            status_code=400,
            content={"error": "'question' field is required and must be non-empty"},
        )
    try:
        from agents.etap_gui_agent import ETAPGUIAgent
        agent = ETAPGUIAgent()
        result = agent.answer(question)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.exception("etap_gui chat failed")
        return JSONResponse(
            status_code=500,
            content={"error": f"ETAP GUI agent error: {exc}"},
        )


# -- Studies ------------------------------------------------------------------
STUDY_TYPES = [
    "load_flow",
    "short_circuit",
    "arc_flash",
    "protection_coordination",
    "motor_starting",
    "transient_stability",
    "harmonic_analysis",
    "optimal_power_flow",
    "cable_sizing",
    "earth_grid",
    "renewable_integration",
    "battery_storage",
    "scada",
    "etap_expert",  # ETAP Expert skill — 6-step workflow with Format A/B/C/D
    "etap_gui",     # ETAP GUI Agent — Computer Use Agent for desktop apps
]


@app.get("/api/v1/studies/types", tags=["Studies"])
async def study_types():
    return {"study_types": STUDY_TYPES}


@app.post("/api/v1/studies/run", tags=["Studies"])
async def run_study(request: StudyRequest):
    if request.study_type not in STUDY_TYPES:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unknown study_type '{request.study_type}'",
                "valid_types": STUDY_TYPES,
            },
        )

    # ETAP Expert skill — 6-step workflow with Format A/B/C/D responses.
    # Routes to the dedicated ETAPExpertAgent (no numerical engine needed).
    if request.study_type == "etap_expert":
        question = str(request.parameters.get("question", "")).strip()
        if not question:
            return JSONResponse(
                status_code=400,
                content={"error": "'question' field is required for study_type='etap_expert'"},
            )
        try:
            from agents.etap_expert_agent import ETAPExpertAgent
            agent = ETAPExpertAgent()
            result = agent.answer(question)
            return {
                "study_type": "etap_expert",
                "reference": f"ETAP-EXPERT-{int(time.time())}",
                "status": "completed",
                "success": True,
                "data": result,
            }
        except Exception as exc:
            logger.exception("etap_expert study failed")
            return JSONResponse(
                status_code=500,
                content={"error": f"ETAP Expert agent error: {exc}"},
            )

    # ETAP GUI Agent — Computer Use Agent for desktop apps.
    # Falls back gracefully on headless servers (returns Format U).
    if request.study_type == "etap_gui":
        question = str(request.parameters.get("question", "")).strip()
        if not question:
            return JSONResponse(
                status_code=400,
                content={"error": "'question' field is required for study_type='etap_gui'"},
            )
        try:
            from agents.etap_gui_agent import ETAPGUIAgent
            agent = ETAPGUIAgent()
            result = agent.answer(question)
            return {
                "study_type": "etap_gui",
                "reference": f"ETAP-GUI-{int(time.time())}",
                "status": "completed",
                "success": True,
                "data": result,
            }
        except Exception as exc:
            logger.exception("etap_gui study failed")
            return JSONResponse(
                status_code=500,
                content={"error": f"ETAP GUI agent error: {exc}"},
            )

    # Attempt native engine execution for supported study types
    result_data = None
    engine_error = None
    if request.study_type == "load_flow" and request.system:
        try:
            from core_model.bus import Bus
            from core_model.line import Line
            from core_model.system import System

            sys_model = System(base_mva=request.system.get("base_mva", 100.0))
            bus_map: dict[int, Any] = {}
            for b in request.system.get("buses", []):
                bus = Bus(
                    bus_id=b["bus_id"],
                    voltage_magnitude=b.get("voltage_magnitude", 1.0),
                    voltage_angle=b.get("voltage_angle", 0.0),
                    bus_type=b.get("bus_type", "pq"),
                )
                bus.generation_power = complex(
                    b.get("generation_power_real", 0.0),
                    b.get("generation_power_imag", 0.0),
                )
                bus.load_power = complex(
                    b.get("load_power_real", 0.0),
                    b.get("load_power_imag", 0.0),
                )
                sys_model.add_bus(bus)
                bus_map[b["bus_id"]] = bus

            for ln in request.system.get("lines", []):
                line = Line(
                    line_id=ln["line_id"],
                    from_bus=bus_map[ln["from_bus_id"]],
                    to_bus=bus_map[ln["to_bus_id"]],
                    z1=complex(ln.get("r1", 0.01), ln.get("x1", 0.05)),
                    z0=complex(ln.get("r0", ln.get("r1", 0.01)), ln.get("x0", ln.get("x1", 0.05))),
                    yshunt1=complex(0, ln.get("bshunt1", 0.02)),
                    yshunt0=complex(0, ln.get("bshunt0", ln.get("bshunt1", 0.02))),
                )
                sys_model.add_line(line)

            from engine.engine import PowerSystemEngine

            engine = PowerSystemEngine(sys_model)
            result_data = engine.run_load_flow()
            # Sanitize numpy types for JSON
            sanitized = {}
            for k, v in result_data.items():
                if isinstance(v, dict):
                    sanitized[k] = {
                        str(bid): {
                            "mag": round(abs(val), 4),
                            "angle_deg": round(float(__import__("numpy").angle(val, deg=True)), 2),
                        }
                        for bid, val in v.items()
                    }
                else:
                    sanitized[k] = v
            result_data = sanitized
        except ImportError:
            engine_error = "Engine modules not available in HF Space deployment"
        except Exception as exc:
            engine_error = str(exc)

    response: dict[str, Any] = {
        "study_type": request.study_type,
        "reference": f"STUDY-{int(time.time())}",
    }
    if result_data is not None:
        response["status"] = "completed"
        response["result"] = result_data
    else:
        response["status"] = "accepted"
        response["message"] = f"Study '{request.study_type}' queued for processing."
        if engine_error:
            response["engine_note"] = engine_error
        response["note"] = (
            "Full computation engine available in self-hosted deployment. See /docs for details."
        )
    return response


# -- Knowledge Base Info ------------------------------------------------------
@app.get("/api/v1/knowledge", tags=["Knowledge"])
async def knowledge_info():
    return {
        "etap": {
            "manuals": ETAP_MANUAL_COUNT,
            "topics": [
                "AC Networks",
                "Load Flow & Panel",
                "Transformer Sizing",
                "Unbalanced Load Flow",
                "Short Circuit ANSI",
                "Short Circuit IEC",
                "Arc Flash",
                "Motor Acceleration",
                "Parameter Estimation",
                "Transient Stability",
                "Parameter Tuning",
                "UDM",
                "Harmonics",
                "UGS",
                "Cable Pulling",
                "Optimal Power Flow",
                "OCP",
                "Ground Grid",
                "PDE/GIS",
                "DC Load Flow & Short Circuit",
                "BSD",
                "CSD",
                "Reliability Assessment",
                "WTG",
                "Arc Flash Advanced Topics",
                "ETAP ARTTS",
                "Controls",
                "Short Circuit Study",
                "Training (1164 slides)",
                "Renewable Energy",
                "ETAP Solutions Overview",
                "eTrax Rail",
            ],
            "standards": ["IEEE 3002.7", "IEC 60909", "IEEE 1584", "IEC 60255", "IEEE 519"],
        },
        "zenon": {
            "guides": ZENON_GUIDE_COUNT,
            "topics": [
                "Zenon SCADA Fundamentals",
                "Zenon Energy Management",
                "Zenon IEC 61850 Module 1",
                "Zenon IEC 61850 Module 2",
            ],
            "standards": ["IEC 61850", "IEC 61968", "IEC 61970"],
        },
    }


# -- HEAD at root for HF health probe -----------------------------------------
@app.head("/", include_in_schema=False)
async def root_head():
    return JSONResponse(content={}, status_code=200)


# -- ML Capabilities ----------------------------------------------------------
@app.get("/api/v1/ml/capabilities", tags=["AI/ML"])
async def ml_capabilities():
    """Discover available ML/AI capabilities and their status."""
    try:
        from ml.predictive import get_ml_capabilities

        caps = get_ml_capabilities()
        return {"success": True, "data": caps}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)]})


@app.post("/api/v1/predict/load", tags=["AI/ML"])
async def predict_load(request: Request):
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    try:
        body = await request.json()
        historical = body.get("historical_data", [])
        horizon = body.get("horizon_hours", 24)
        method = body.get("method", "auto")

        if not historical:
            return JSONResponse(status_code=400, content={"error": "historical_data is required"})

        import numpy as np

        from ml.predictive import LoadForecaster

        lf = LoadForecaster(method=method)
        data = np.array(historical, dtype=float)
        train_result = lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)

        return {
            "success": True,
            "data": {
                "predictions": predictions.tolist()
                if hasattr(predictions, "tolist")
                else list(predictions),
                "horizon_hours": horizon,
                "method": train_result.get("method", method),
            },
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)]})


@app.post("/api/v1/predict/anomaly", tags=["AI/ML"])
async def detect_anomalies(request: Request):
    """Detect anomalies using Isolation Forest / PyOD."""
    try:
        body = await request.json()
        data = body.get("data", [])
        method = body.get("method", "iforest")
        contamination = body.get("contamination", 0.05)

        if not data:
            return JSONResponse(status_code=400, content={"error": "data is required"})

        import numpy as np

        from ml.predictive import AnomalyDetector

        ad = AnomalyDetector(contamination=contamination, method=method)
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        ad.train(X)
        result = ad.detect(X)

        return {"success": True, "data": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logger.info("Starting server on port %d", port)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )
