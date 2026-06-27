"""
AhmedETAP - Enterprise Engineering Intelligence Platform
Hugging Face Spaces Entry Point
Author: Eng. Ahmed Elbaz

This file now imports shared logic from ``api.shared_handlers`` so that
constants, models, agent lists, study execution, rate limiting, and auth
are defined in one place and reused by both the HF Space and the main API.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# -- Shared handlers (single source of truth) ---------------------------------
from api.shared_handlers import (
    AGENT_COUNT,
    AGENTS,
    ETAP_MANUAL_COUNT,
    PUBLIC_PATHS,
    START_TIME,
    STUDY_TYPES,
    VERSION,
    ZENON_GUIDE_COUNT,
    SharedContextRetrieveRequest,
    SharedETAPExpertChatRequest,
    SharedETAPGUIChatRequest,
    SharedImpactAnalysisRequest,
    SharedStudyRequest,
    build_health_response,
    build_knowledge_info,
    build_metrics_response,
    build_platform_info,
    build_ready_response,
    handle_context_retrieval,
    handle_detect_anomalies,
    handle_etap_expert_chat,
    handle_etap_gui_chat,
    handle_impact_analysis,
    handle_ml_capabilities,
    handle_predict_load,
    rate_limiter,
    run_study_lightweight,
    verify_api_key,
)

# -- Logging ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("etap-ai")


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
    # API key check (uses shared verify_api_key with HF_API_KEY env var)
    verify_api_key(request)
    # Rate limit (skip health/docs)
    if request.url.path not in PUBLIC_PATHS:
        client_id = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_id):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(rate_limiter.window)},
            )
    return await call_next(request)


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


# -- Health (delegates to shared builders) ------------------------------------
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
    return build_health_response(platform="huggingface-spaces")


@app.get("/ready", tags=["Health"])
async def ready():
    return build_ready_response()


# -- Metrics ------------------------------------------------------------------
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    return build_metrics_response(platform="huggingface-spaces")


# -- Platform Info ------------------------------------------------------------
@app.get("/api/v1/info", tags=["Platform"])
async def platform_info():
    return build_platform_info()


# -- Agents -------------------------------------------------------------------
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
async def etap_expert_chat(request: SharedETAPExpertChatRequest):
    """Chat with the ETAP Expert skill agent.

    Implements the 6-step workflow (PARSE → SEARCH → VALIDATE → SIMULATE →
    FORMAT → QA) and returns one of four response formats:
      - Format A (Complete)   : ✅ REQUEST ANALYSIS: COMPLETE
      - Format B (Incomplete) : ⚠️ REQUEST ANALYSIS: INCOMPLETE
      - Format C (Wrong)      : ❌ REQUEST ANALYSIS: INCORRECT APPROACH
      - Format D (ADMS/DER)   : 🔷 ADMS REQUEST ANALYSIS

    Knowledge base: skills/etap-expert.md (4,400+ lines)
    """
    result = handle_etap_expert_chat(request.question)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


@app.post("/api/v1/agents/etap-gui/chat", tags=["Agents"])
async def etap_gui_chat(request: SharedETAPGUIChatRequest):
    """Chat with the ETAP GUI Agent (Computer Use Agent).

    Classifies the question into Analyze/Monitor/Control/Solve modes.
    Falls back to Format U (unavailable) on headless servers / HF Space
    where pyautogui, pytesseract, opencv are not installed.

    Knowledge base: skills/etap-gui-agent.md (440+ lines)
    """
    result = handle_etap_gui_chat(request.question)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


# -- Studies ------------------------------------------------------------------
@app.get("/api/v1/studies/types", tags=["Studies"])
async def study_types():
    return {"study_types": STUDY_TYPES}


@app.post("/api/v1/studies/run", tags=["Studies"])
async def run_study(request: SharedStudyRequest):
    result = run_study_lightweight(request.study_type, request.system, request.parameters)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


# -- Context Engine -----------------------------------------------------------
@app.post("/api/v1/context/retrieve", tags=["Context Engine"])
async def retrieve_context(request: SharedContextRetrieveRequest):
    """Retrieve and compress matching code snippets for a given query."""
    result = handle_context_retrieval(
        query=request.query, top_k=request.top_k, max_tokens=request.max_tokens
    )
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


@app.post("/api/v1/context/impact", tags=["Context Engine"])
async def analyze_impact(request: SharedImpactAnalysisRequest):
    """Perform dependency impact analysis on a component using the Code Property Graph."""
    result = handle_impact_analysis(component=request.component, max_depth=request.max_depth)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


# -- Knowledge Base Info ------------------------------------------------------
@app.get("/api/v1/knowledge", tags=["Knowledge"])
async def knowledge_info():
    return build_knowledge_info()


# -- HEAD at root for HF health probe -----------------------------------------
@app.head("/", include_in_schema=False)
async def root_head():
    return JSONResponse(content={}, status_code=200)


# -- ML Capabilities ----------------------------------------------------------
@app.get("/api/v1/ml/capabilities", tags=["AI/ML"])
async def ml_capabilities():
    """Discover available ML/AI capabilities and their status."""
    result = handle_ml_capabilities()
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


@app.post("/api/v1/predict/load", tags=["AI/ML"])
async def predict_load(request: Request):
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    body = await request.json()
    result = handle_predict_load(body)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


@app.post("/api/v1/predict/anomaly", tags=["AI/ML"])
async def detect_anomalies(request: Request):
    """Detect anomalies using Isolation Forest / PyOD."""
    body = await request.json()
    result = handle_detect_anomalies(body)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


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
