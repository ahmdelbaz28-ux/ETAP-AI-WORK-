"""
AhmedETAP - Enterprise Engineering Intelligence Platform
Hugging Face Spaces Entry Point
Author: Eng. Ahmed Elbaz

This file now imports shared logic from ``api.shared_handlers`` so that
constants, models, agent lists, study execution, rate limiting, and auth
are defined in one place and reused by both the HF Space and the main API.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket
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
    SUPPORTED_STANDARDS,
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
        "Knowledge base: %d ETAP manuals + %d Zenon guides", ETAP_MANUAL_COUNT, ZENON_GUIDE_COUNT,
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


# -- Security headers middleware ----------------------------------------------
#
# Adds standard HTTP security headers to every response. The CSP is intentionally
# permissive on ``'unsafe-inline'`` and ``'unsafe-eval'`` because:
#   1. Swagger UI (/docs) and ReDoc (/redoc) require inline scripts/styles.
#   2. The homepage uses an inline <style> block.
# A stricter CSP would break the API documentation viewers. The other headers
# (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy) are safe to
# enforce everywhere and protect against common attack vectors (MIME sniffing,
# clickjacking, referrer leakage, SSL downgrade).
#
# HSTS is only sent over HTTPS — sending it over HTTP is a no-op (browsers
# ignore it) but it pollutes dev logs and can confuse local testing.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # HSTS only over HTTPS (production). On localhost HTTP dev, skip it so the
    # browser doesn't pin HSTS for a year on a non-TLS origin.
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Permissive CSP that allows Swagger UI + ReDoc + homepage inline styles.
    # Tightening this requires moving Swagger/ReDoc to a CDN-less self-hosted
    # build, which is out of scope for the HF Space deployment.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self'"
    )
    return response


# -- Auth + Rate-limit middleware ---------------------------------------------
@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    # API key check — prefer ENGINEERING_SERVICE_API_KEY (the canonical name
    # used everywhere else in the platform), fall back to HF_API_KEY for
    # backward compatibility with older Space secrets. If NEITHER is set,
    # verify_api_key() returns early and auth is DISABLED — which is
    # acceptable only in development, NOT in production.
    _eng_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
    _hf_key = os.environ.get("HF_API_KEY", "")
    if _eng_key and not _hf_key:
        # Alias the canonical key so verify_api_key (which reads HF_API_KEY
        # by default) picks it up without needing a separate secret.
        os.environ["HF_API_KEY"] = _eng_key
    # NOTE: verify_api_key() raises HTTPException(401) when auth fails.
    # FastAPI's @app.middleware("http") does NOT automatically convert
    # HTTPException into proper JSON responses — it lets the exception
    # propagate to Starlette's error handler which returns HTTP 500.
    # We must catch it here and return the correct JSONResponse ourselves.
    try:
        verify_api_key(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
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
      <div class="stat"><div class="stat-num">{len(SUPPORTED_STANDARDS)}</div><div class="stat-label">Standards</div></div>
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


@app.post("/api/v1/agents/etap-gui/execute", tags=["Agents"])
async def etap_gui_execute(
    question: str | None = None,
    max_steps: int = 15,
    require_confirmation: bool = True,
    audit_dir: str | None = None,
    start_url: str | None = None,
    body: dict[str, Any] | None = Body(None),
):
    """Execute the REAL CUA Loop (Computer Use Agent).

    AUTO-DETECTS THE ENVIRONMENT:
      - Desktop (pyautogui + display) → controls native apps (ETAP.exe, etc.)
      - Headless (Playwright + Chromium) → controls web pages via headless browser
      - Neither available → returns Format U fallback

    On HF Space, the Browser CUA path is used (Playwright + Chromium are
    installed in the Dockerfile). The agent opens start_url in a headless
    Chromium and controls the web page — clicking, typing, navigating.

    Required env vars:
      - GEMINI_API_KEY (for visual perception via Gemini Vision)

    See: agents/browser_cua_executor.py and integrations/gemini_vision.py

    ``question`` can be provided as a query parameter OR inside a JSON
    body (e.g. ``{"command": "...", "params": {...}, "message": "..."}``).
    This maintains backward compatibility with older Postman collections
    that send JSON bodies instead of query parameters.
    """
    # Postman compatibility: accept question/message/command from JSON body
    if not question and body:
        question = (
            body.get("question")
            or body.get("message")
            or body.get("command")
        )
        if body.get("params") and isinstance(body["params"], dict):
            start_url = start_url or body["params"].get("start_url") or body["params"].get("study_id")

    if not question:
        raise HTTPException(
            status_code=422,
            detail="'question' is required (as query param or in JSON body)",
        )

    from agents.etap_gui_agent import ETAPGUIAgent

    agent = ETAPGUIAgent()
    # Run the CUA Loop in a thread to avoid Playwright Sync API conflict
    # with the asyncio event loop. Playwright Sync API cannot run inside
    # an asyncio loop, so we offload to a thread.
    import asyncio

    result = await asyncio.to_thread(
        agent.execute_cua_loop,
        question=question,
        max_steps=max_steps,
        require_confirmation=require_confirmation,
        audit_dir=audit_dir,
        start_url=start_url,
    )
    return {"success": True, "data": result}


@app.get("/api/v1/agents/etap-gui/health", tags=["Agents"])
async def etap_gui_health():
    """Health check for CUA execution capabilities.

    Returns whether the CUA Loop can run in the current environment.
    Reports BOTH Desktop CUA (pyautogui) and Browser CUA (Playwright)
    availability — the agent auto-detects which to use.
    """
    from agents.etap_gui_agent import ETAPGUIAgent, _check_gui_deps
    from agents.life_safety import life_safety_guard
    from integrations.gemini_vision import gemini_vision

    # Check Desktop CUA deps (pyautogui + display)
    desktop_deps_ok, desktop_missing = _check_gui_deps()

    # Check Browser CUA deps (Playwright + Chromium)
    browser_deps = {"all_available": False, "missing": ["not-checked"]}
    try:
        from agents.browser_cua_executor import BrowserCUAExecutor

        browser_exec = BrowserCUAExecutor()
        browser_deps = browser_exec.check_dependencies()
    except Exception:  # noqa: BLE001
        pass

    # CUA Loop is available if EITHER Desktop OR Browser deps are met
    cua_loop_available = desktop_deps_ok or browser_deps.get("all_available", False)

    agent = ETAPGUIAgent()
    info = agent.get_agent_info()
    return {
        "success": True,
        "data": {
            "cua_loop_available": cua_loop_available,
            "desktop_cua_available": desktop_deps_ok,
            "browser_cua_available": browser_deps.get("all_available", False),
            "missing_dependencies": desktop_missing if not desktop_deps_ok else [],
            "browser_cua_deps": browser_deps,
            "gemini_vision": gemini_vision.health_check(),
            "agent_info": info,
            "life_safety": life_safety_guard.health_check(),
        },
    }


# -- Life Safety endpoints (mirrored from api/agents.py) --------------------


@app.post("/api/v1/agents/etap-gui/kill-switch/activate", tags=["Agents", "Safety"])
async def etap_gui_activate_kill_switch(reason: str = "manual_api_call"):
    """🚨 EMERGENCY STOP — Activate the CUA kill switch on HF Space.

    Once activated, the CUA Loop will abort on the next action check.
    The kill switch is file-based (/tmp/cua_kill_switch) so it works
    even if the API server is unresponsive.
    """
    from agents.life_safety import activate_kill_switch

    activate_kill_switch(reason=reason)
    from datetime import UTC, datetime

    return {
        "success": True,
        "data": {
            "kill_switch_active": True,
            "reason": reason,
            "activated_at": datetime.now(UTC).isoformat(),
            "message": "CUA Loop will abort on next action. Call /deactivate to resume.",
        },
    }


@app.post("/api/v1/agents/etap-gui/kill-switch/deactivate", tags=["Agents", "Safety"])
async def etap_gui_deactivate_kill_switch():
    """Deactivate the CUA kill switch.

    Use with caution — only after the safety issue has been resolved.
    """
    from agents.life_safety import deactivate_kill_switch, is_kill_switch_active

    was_active = deactivate_kill_switch()
    return {
        "success": True,
        "data": {
            "was_active": was_active,
            "kill_switch_active": is_kill_switch_active(),
            "message": "Kill switch deactivated. CUA Loop can resume."
            if was_active
            else "Kill switch was not active.",
        },
    }


@app.get("/api/v1/agents/etap-gui/safety/health", tags=["Agents", "Safety"])
async def etap_gui_safety_health():
    """Get the life safety system status on HF Space."""
    from agents.life_safety import life_safety_guard

    return {"success": True, "data": life_safety_guard.health_check()}


@app.get("/api/v1/agents/etap-gui/safety/audit/verify", tags=["Agents", "Safety"])
async def etap_gui_safety_audit_verify():
    """Verify the integrity of the tamper-evident audit log on HF Space.

    Returns is_valid=True if the SHA-256 chain is intact, plus any
    broken entries if tampering is detected.
    """
    from agents.life_safety import life_safety_guard

    is_valid, broken = life_safety_guard.audit_log.verify_chain()
    return {
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


@app.get("/api/v1/agents/etap-gui/siem/health", tags=["Agents", "Safety"])
async def etap_gui_siem_health():
    """Get the SIEM Syslog forwarder status on HF Space."""
    from integrations.siem_syslog import siem_forwarder

    return {"success": True, "data": siem_forwarder.health_check()}


@app.get("/api/v1/agents/etap-gui/siem/events", tags=["Agents", "Safety"])
async def etap_gui_siem_events(limit: int = 50):
    """Read recent SIEM events from the logging-only JSONL file on HF Space."""
    import json
    import os

    from integrations.siem_syslog import siem_forwarder

    if not siem_forwarder.logging_only or not siem_forwarder.log_file:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "logging_only_mode_not_active",
                "message": "Set SIEM_LOG_FILE env var to enable event viewing",
            },
        )

    log_path = siem_forwarder.log_file
    if not os.path.exists(log_path):
        return {"success": True, "data": {"events": [], "total": 0, "message": "No events yet"}}

    limit = min(max(limit, 1), 200)
    events = []
    try:
        # Read the file in a worker thread to avoid blocking the event loop
        # (SonarCloud S7493: synchronous file I/O inside an async function).
        def _read_log_lines() -> list[str]:
            with open(log_path, encoding="utf-8") as fh:
                return fh.readlines()

        lines = await asyncio.to_thread(_read_log_lines)
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
            status_code=500,
            content={"success": False, "error": "read_failed", "message": str(exc)},
        )

    return {
        "success": True,
        "data": {"events": events, "total": len(events), "log_file": log_path},
    }


# -- Studies ------------------------------------------------------------------
@app.get("/api/v1/studies/types", tags=["Studies"])
async def study_types():
    return {"study_types": STUDY_TYPES}


@app.websocket("/ws/cua/confirmation")
async def websocket_cua_confirmation(websocket: WebSocket):
    """WebSocket endpoint for real-time CUA dual-confirmation on HF Space.

    Allows two humans to approve life-safety-critical CUA actions
    (protection setting changes, breaker operations) in real time.

    Protocol:
      Client → Server: {"action": "confirm", "request_id": "...", "session_id": "..."}
                       {"action": "reject", "request_id": "...", "session_id": "...", "reason": "..."}
      Server → Client: {"type": "confirmation_request", "data": {...}}
                       {"type": "confirmation_resolved", "approved": true/false}
    """
    from api.cua_confirmation_ws import cua_confirmation_ws

    await cua_confirmation_ws(websocket)


@app.post("/api/v1/studies/run", tags=["Studies"])
async def run_study(request: SharedStudyRequest):
    # Use merged_parameters() so top-level question/query (Postman compat)
    # are passed to the study runner.
    result = run_study_lightweight(
        request.study_type, request.system, request.merged_parameters(),
    )
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return result


# -- Context Engine -----------------------------------------------------------
@app.post("/api/v1/context/retrieve", tags=["Context Engine"])
async def retrieve_context(request: SharedContextRetrieveRequest):
    """Retrieve and compress matching code snippets for a given query."""
    result = handle_context_retrieval(
        query=request.query, top_k=request.top_k, max_tokens=request.max_tokens,
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


# -- Settings (API Keys) ------------------------------------------------------
# User-supplied API keys stored encrypted in SQLite.
# Allows end users to enter their own OpenAI/Gemini/Anthropic keys
# via the Settings UI, overriding the server-side env vars.


@app.get("/api/v1/settings/keys", tags=["Settings"])
async def settings_list_keys():
    """List all stored API keys (masked — never returns plaintext)."""
    from services.api_key_store import api_key_store

    keys = api_key_store.get_all_keys()
    return {"success": True, "data": keys, "providers": list(keys.keys())}


@app.get("/api/v1/settings/keys/{provider}", tags=["Settings"])
async def settings_get_key(provider: str):
    """Get a single API key (masked)."""
    from services.api_key_store import APIKeyStore, api_key_store

    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Unsupported provider: {provider}"},
        )
    config = api_key_store.get_key(provider)
    if not config:
        return {"success": True, "data": None, "message": f"No key for '{provider}'"}
    return {"success": True, "data": config.to_masked_dict()}


@app.post("/api/v1/settings/keys/{provider}", tags=["Settings"])
async def settings_save_key(
    provider: str,
    api_key: str,
    base_url: str = None,
    model_name: str = None,
    is_active: bool = True,
):
    """Save or update an API key (encrypted with AES-256)."""
    import logging

    from services.api_key_store import APIKeyStore, api_key_store

    logger = logging.getLogger(__name__)
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Unsupported provider: {provider}"},
        )
    try:
        api_key_store.set_key(provider, api_key, base_url, model_name, is_active)
        config = api_key_store.get_key(provider)
        masked = config.to_masked_dict() if config else None
        return {
            "success": True,
            "data": masked,
            "message": f"API key for '{provider}' saved (encrypted)",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to save API key")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "save_failed", "message": str(exc)},
        )


@app.delete("/api/v1/settings/keys/{provider}", tags=["Settings"])
async def settings_delete_key(provider: str):
    """Delete an API key permanently."""
    from services.api_key_store import api_key_store

    provider = provider.lower().strip()
    deleted = api_key_store.delete_key(provider)
    return {
        "success": deleted,
        "message": f"Key for '{provider}' deleted" if deleted else f"No key for '{provider}'",
    }


@app.post("/api/v1/settings/keys/{provider}/test", tags=["Settings"])
async def settings_test_key(provider: str):
    """Test an API key by making a minimal API call."""
    from api.settings import _test_anthropic_key, _test_gemini_key, _test_openai_key
    from services.api_key_store import api_key_store

    provider = provider.lower().strip()
    config = api_key_store.get_key(provider)
    if not config:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "key_not_found",
                "message": f"No key for '{provider}'",
            },
        )
    try:
        if provider == "openai":
            result = _test_openai_key(config)
        elif provider == "gemini":
            result = _test_gemini_key(config)
        elif provider == "anthropic":
            result = _test_anthropic_key(config)
        else:
            result = {"success": False, "message": f"Unknown provider: {provider}"}
        return {"success": True, "data": result}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "test_failed", "message": str(exc)},
        )


@app.get("/api/v1/settings/health", tags=["Settings"])
async def settings_health():
    """Get the API key storage health status."""
    from services.api_key_store import api_key_store

    return {"success": True, "data": api_key_store.health_check()}


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
    # Bind to 0.0.0.0 — REQUIRED on Hugging Face Spaces (and most container
    # platforms). The container's ingress proxy handles the public-facing
    # interface; binding to 127.0.0.1 would prevent HF Spaces from reaching
    # the app at all. SonarCloud S8392 flags this, but it's intentional.
    host = os.environ.get("HOST", "0.0.0.0")  # NOSONAR — S8392: HF Spaces requires 0.0.0.0 binding; ingress proxy handles public exposure
    logger.info("Starting server on %s:%d", host, port)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
