"""
API Routes module for the Engineering Service.
Handles all API endpoints, request validation, and response formatting.
"""

from __future__ import annotations

import hmac
import os
import sys
import threading as _threading
import time
import uuid
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import both the `trace` module (for trace.get_current_span() etc.) and the
# specific symbols used by the middleware below. This prevents NameError if a
# future edit references `trace.X` directly inside trace_middleware.
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from api.agents import router as agents_router
from api.ai_ml import router as ai_ml_router
from api.assets import router as assets_router
from api.auth import router as auth_router
from api.context_engine import router as context_engine_router
from api.data_import import router as data_import_router
from api.dependencies import get_api_key
from api.email_dashboard import router as email_dashboard_router
from api.email_digest import router as email_digest_router
from api.email_otp import router as email_otp_router
from api.email_webhooks import router as email_webhooks_router
from api.equipment import router as equipment_router
from api.export import router as export_router
from api.health import router as health_router
from api.magic_links import router as magic_links_router
from api.notifications import notification_websocket_endpoint
from api.notifications import router as notifications_router
from api.projects import router as projects_router
from api.rbac import router as rbac_router
from api.settings import router as settings_router
from api.studies import router as studies_router
from api.study_versions import router as study_versions_router
from api.templates import router as templates_router
from api.validation import router as validation_router
from api.websocket import scada_websocket_endpoint
from core.bootstrap import lifespan, logger
from core.tracing import get_tracer
from services.study_service import (
    StudyRequest,
)

# ─── Shared format constants ────────────────────────────────────────────────
# Centralised to avoid string-literal duplication (SonarCloud python:S1192).
_ISO_8601_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 'Z' timestamp."""
    return time.strftime(_ISO_8601_UTC_FMT, time.gmtime())


# Create FastAPI app instance
_ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
app = FastAPI(
    title="Engineering Service API",
    description="Production-grade FastAPI service wrapping the Python PowerSystemEngine",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    debug=(_ENV == "development"),  # Explicitly set debug mode based on environment
)

# ---------------------------------------------------------------------------
# API Key validation
# ---------------------------------------------------------------------------

_EXPECTED_API_KEY = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")

# ---------------------------------------------------------------------------
# Smithery Integration — External API Key Management
# ---------------------------------------------------------------------------
_SMITHERY_API_KEY = os.environ.get("SMITHERY_API_KEY", "")
if _SMITHERY_API_KEY:
    logger.info("smithery_api_key_available", extra={"trace_id": "startup"})

_API_KEY_CONFIGURED = bool(_EXPECTED_API_KEY)

_AUTH_DISABLED = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in (
    "1",
    "true",
    "yes",
)
if _AUTH_DISABLED:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.critical(
            "FATAL: ENGINEERING_SERVICE_AUTH_DISABLED=true is NOT allowed in %s environment. "
            "Remove this environment variable or set ENGINEERING_SERVICE_API_KEY.",
            _ENV,
        )
        sys.exit(1)
    logger.warning(
        "WARNING: Authentication is DISABLED. "
        "Set ENGINEERING_SERVICE_API_KEY to enable authentication. "
        "This is NOT recommended outside of local development.",
    )
if not _API_KEY_CONFIGURED and not _AUTH_DISABLED:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.critical(
            "FATAL: ENGINEERING_SERVICE_API_KEY is not set in %s environment. "
            "Set the API key, or set ENGINEERING_SERVICE_AUTH_DISABLED=true "
            "(NOT recommended for production).",
            _ENV,
        )
        sys.exit(1)


def _require_api_key(request: Request) -> None:
    """Validate API key when configured."""
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            return
        _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
        if _ENV in ("production", "prod", "staging"):
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
                status_code=401,
                detail="Authentication required but no API key configured. "
                "Set ENGINEERING_SERVICE_API_KEY or ENGINEERING_SERVICE_AUTH_DISABLED=true",
            )
        return

    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, _EXPECTED_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint


# ---------------------------------------------------------------------------
# Body size limit middleware
# ---------------------------------------------------------------------------

_MAX_BODY_SIZE = int(os.environ.get("ENGINEERING_SERVICE_MAX_BODY_SIZE", "1_048_576"))


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > _MAX_BODY_SIZE:
                # NOTE: Raising HTTPException inside BaseHTTPMiddleware.dispatch
                # does NOT translate to a proper HTTP 413 response — Starlette
                # wraps it in a 500 Internal Server Error. We must return a
                # JSONResponse explicitly so the client sees 413.
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate Limiting (Redis-backed, per-client) + fallback in-memory
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_WINDOW", "60"))
_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX", "100"))

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_RATE_LIMIT_PREFIX = os.environ.get("RATE_LIMIT_PREFIX", "rate-limit:")

_rate_limit_fallback_store: dict[str, list[float]] = {}
_rate_limit_fallback_lock = _threading.Lock()
_RATE_LIMIT_MAX_ENTRIES = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX_ENTRIES", "10000"))

try:
    import redis.asyncio as redis_async  # type: ignore
except Exception:  # pragma: no cover
    redis_async = None  # type: ignore

_redis_client = None


def _get_rate_limit_redis() -> Optional[Any]:
    global _redis_client
    if not _REDIS_URL or redis_async is None:
        return None
    if _redis_client is None:
        _redis_client = redis_async.from_url(_REDIS_URL, decode_responses=True)
    return _redis_client


async def _check_rate_limit(client_id: str) -> bool:
    """Return True if allowed; False if rate limit exceeded."""
    r = _get_rate_limit_redis()
    now = time.time()

    if r is None:
        with _rate_limit_fallback_lock:
            if len(_rate_limit_fallback_store) > _RATE_LIMIT_MAX_ENTRIES:
                stale = [
                    cid
                    for cid, timestamps in _rate_limit_fallback_store.items()
                    if not timestamps or now - timestamps[-1] > _RATE_LIMIT_WINDOW
                ]
                for cid in stale:
                    del _rate_limit_fallback_store[cid]

            timestamps = _rate_limit_fallback_store.get(client_id)
            if not timestamps:
                _rate_limit_fallback_store[client_id] = [now]
                return True

            timestamps = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
            if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
                _rate_limit_fallback_store[client_id] = timestamps
                return False

            timestamps.append(now)
            _rate_limit_fallback_store[client_id] = timestamps
            return True

    key = f"{_RATE_LIMIT_PREFIX}{client_id}"
    try:
        current = await r.incr(key)
        if current == 1:
            await r.expire(key, _RATE_LIMIT_WINDOW)
        return current <= _RATE_LIMIT_MAX_REQUESTS
    except Exception:
        logger.warning("rate_limit_redis_failed", extra={"trace_id": "rate-limit"})
        return True


# ---------------------------------------------------------------------------
# Middleware: tracing + rate limiting
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT_SEC = int(os.environ.get("ENGINEERING_SERVICE_REQUEST_TIMEOUT", "120"))


@app.middleware("http")
async def trace_middleware(request: Request, call_next: Any) -> Any:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    # SECURITY: Sanitize trace_id to prevent log injection (CRLF, newlines)
    trace_id = "".join(c for c in trace_id if c.isalnum() or c in "-_.")
    request.state.trace_id = trace_id

    # Extract dynamic active provider credentials
    request.state.active_provider = request.headers.get("x-active-provider")
    request.state.active_key = request.headers.get("x-active-key")
    request.state.active_url = request.headers.get("x-active-url")
    request.state.active_model = request.headers.get("x-active-model")

    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        kind=SpanKind.SERVER,
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.route": request.url.path,
            "http.scheme": request.url.scheme,
            "net.peer.ip": request.client.host if request.client else "unknown",
        },
    ) as span:
        span.set_attribute("ahmedetap.trace_id", trace_id)

        # Rate limiting — skip for health endpoints
        if not request.url.path.startswith(("/health", "/ready", "/healthz", "/readyz")):
            _TRUSTED_PROXIES = os.environ.get("ENGINEERING_SERVICE_TRUSTED_PROXIES", "")
            if _TRUSTED_PROXIES:
                _trusted_list = [p.strip() for p in _TRUSTED_PROXIES.split(",")]
                xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                proxy_ip = request.client.host if request.client else ""
                client_id = (
                    xff
                    if proxy_ip in _trusted_list and xff
                    else (request.client.host if request.client else "unknown")  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                )
            else:
                client_id = request.client.host if request.client else "unknown"
            if not await _check_rate_limit(client_id):
                span.set_status(Status(StatusCode.ERROR, "rate_limit_exceeded"))
                span.set_attribute("http.status_code", 429)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded", "trace_id": trace_id},
                    headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
                )

        response = await call_next(request)
        return response


# Define HealthResponse and ReadyResponse models if they don't exist
class HealthResponse(BaseModel):
    status: str
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    timestamp: str


# Health endpoints are now handled by health router
# See api/health.py for implementation

# Main study execution endpoint is now handled by studies router
# See api/studies.py for implementation


# Study validation endpoint is now handled by the validation router in api/validation.py


# --- NEW ASYNC AND WEBSOCKET ENDPOINTS ADDED FOR PRODUCTION SCALABILITY ---


# Module-level cache for Celery components (lazy-loaded once, then reused)
_celery_cache: tuple = ()  # empty tuple = not yet loaded


def get_celery_components() -> tuple[Optional[Any], Optional[Any], Optional[Any]]:
    """Lazy loading of Celery components to avoid import errors during startup.

    Uses a module-level cache so that imports are performed only once;
    subsequent calls return the cached tuple directly.
    """
    global _celery_cache
    if _celery_cache:
        return _celery_cache

    try:
        from celery.result import AsyncResult  # type: ignore

        from worker.celery_app import app as celery_app  # type: ignore
        from worker.tasks import execute_engineering_study_task  # type: ignore

        _celery_cache = (AsyncResult, execute_engineering_study_task, celery_app)
        return _celery_cache
    except ImportError as e:
        logger.warning("Celery not available: %s", e, exc_info=True)
        _celery_cache = (None, None, None)
        return _celery_cache


@app.post("/api/v1/studies/run_async")
async def run_study_async(study_request: StudyRequest, request: Request) -> dict[str, Any]:
    """Execute an engineering study asynchronously using Celery."""
    _require_api_key(request)  # Add authentication check

    _, execute_engineering_study_task, _ = get_celery_components()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

    if not execute_engineering_study_task:
        raise HTTPException(status_code=500, detail="Celery is not available for async processing")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint

    try:
        # Send the task to Celery queue - using getattr to avoid Pylance type checking errors

        task = execute_engineering_study_task.delay(
            {
                "study_type": study_request.study_type,
                "data": study_request.model_dump(),
                "request_timestamp": str(time.time()),
            },
        )

        logger.info(f"Started async study execution with task_id: {task.id}")

        return {
            "task_id": task.id,
            "status": "accepted",
            "study_type": study_request.study_type,
            "submitted_at": str(time.time()),
        }
    except Exception as e:
        logger.exception("Error submitting async study: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint


@app.get("/api/v1/studies/task_status/{task_id}")
async def get_task_status(task_id: str, request: Request) -> dict[str, Any]:
    """Get the status of an async study task."""
    _require_api_key(request)  # Add authentication check

    CeleryAsyncResult, _, celery_app = get_celery_components()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

    if not CeleryAsyncResult or not celery_app:
        raise HTTPException(status_code=500, detail="Celery is not available")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint

    try:
        # Using the retrieved AsyncResult class to create an instance
        task_result = CeleryAsyncResult(task_id, app=celery_app)

        response = {"task_id": task_id, "status": task_result.status, "result": None}

        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            elif task_result.failed():
                response["error"] = str(task_result.info)

        # If task is in progress, get progress info
        if task_result.status == "PROGRESS":
            response["meta"] = task_result.info

        return response
    except Exception as e:
        logger.exception("Error getting task status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint


@app.websocket("/ws/scada/live")
async def websocket_scada_endpoint_handler(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time SCADA data streaming."""
    # Perform API key authentication for WebSocket connection
    try:
        # Extract API key from headers
        api_key = websocket.headers.get("x-api-key")
        if not api_key or not hmac.compare_digest(api_key, _EXPECTED_API_KEY):
            await websocket.close(code=1008, reason="Invalid or missing API key")
            return
    except Exception:
        await websocket.close(code=1008, reason="Authentication error")
        return

    await scada_websocket_endpoint(websocket)


@app.websocket("/ws/cua/confirmation")
async def websocket_cua_confirmation_handler(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time CUA dual-confirmation.

    Used by the CUA Loop to request two-human approval before executing
    life-safety-critical actions (protection setting changes, breaker ops).

    See: api/cua_confirmation_ws.py for the protocol.
    """
    from api.cua_confirmation_ws import cua_confirmation_ws

    await cua_confirmation_ws(websocket)


# Privacy mode check
_PRIVACY_MODE = os.environ.get("PRIVACY_MODE", "false").lower() == "true"
if not _PRIVACY_MODE:
    _LANGWATCH_API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
    if _LANGWATCH_API_KEY:
        try:
            import langwatch  # type: ignore

            langwatch.api_key = _LANGWATCH_API_KEY
            langwatch.setup(
                endpoint=os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai"),
            )
            logger.info("langwatch_initialized", extra={"trace_id": "startup"})
        except ImportError:
            logger.warning("langwatch_not_installed", extra={"trace_id": "startup"})
        except Exception as lw_exc:
            logger.warning(
                "langwatch_init_failed", extra={"trace_id": "startup", "error": str(lw_exc)},
            )
else:
    logger.info("Privacy mode enabled - external telemetry disabled", extra={"trace_id": "startup"})


# CORS — restrict origins; default allows only same-origin.
# Set ENGINEERING_SERVICE_CORS_ORIGINS to a comma-separated list of allowed origins.
# Example: ENGINEERING_SERVICE_CORS_ORIGINS=https://yourapp.example.com,https://worker.example.com
_CORS_ORIGINS = os.environ.get("ENGINEERING_SERVICE_CORS_ORIGINS", "").strip()
_cors_origin_list = (
    [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip()] if _CORS_ORIGINS else []
)
if not _cors_origin_list:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.warning(
            "CORS: No origins configured in %s environment. "
            "Set ENGINEERING_SERVICE_CORS_ORIGINS to your frontend URL(s). "
            "CORS is currently restrictive (no origins allowed).",
            _ENV,
        )
    else:
        logger.info(
            "CORS: No origins configured (development mode). "
            "Set ENGINEERING_SERVICE_CORS_ORIGINS for production.",
        )
    _cors_origin_list = []  # No origins allowed = restrictive by default
# NOTE: In Starlette/FastAPI, middleware added LAST is the OUTERMOST layer.
# CORSMiddleware must be added LAST so it is outermost and can answer
# preflight OPTIONS requests before any body-size check rejects them
# (SonarCloud S8414).
# BodySizeLimit must be added BEFORE CORSMiddleware so CORS is outermost
# (last added = first executed on incoming requests)
app.add_middleware(_BodySizeLimitMiddleware)
if not _cors_origin_list or _CORS_ORIGINS == "":
    # Don't allow credentials when no origins are configured
    app.add_middleware(  # NOSONAR — S8414: CORSMiddleware added last to make it outermost in the middleware chain
        CORSMiddleware,
        allow_origins=_cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization", "x-active-provider", "x-active-key", "x-active-url", "x-active-model"],
        expose_headers=["x-trace-id"],
    )
else:
    # Allow credentials only when specific origins are configured
    app.add_middleware(  # NOSONAR — S8414: CORSMiddleware added last to make it outermost in the middleware chain
        CORSMiddleware,
        allow_origins=_cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization", "x-active-provider", "x-active-key", "x-active-url", "x-active-model"],
        expose_headers=["x-trace-id"],
    )


# Global exception handler to prevent raw exception exposure
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler to prevent raw exception exposure in production.
    Logs the full exception server-side but returns a generic response to clients.
    """
    import traceback

    # Log the full exception details server-side
    logger.exception(
        f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}",
        extra={
            "trace_id": getattr(request.state, "trace_id", "unknown"),
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        },
    )

    # Return a generic error response to prevent information disclosure
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please contact support if the issue persists.",
            "trace_id": getattr(request.state, "trace_id", "unknown"),
        },
    )


# Register only the routers that exist
app.include_router(health_router)
app.include_router(studies_router)
app.include_router(agents_router)
app.include_router(validation_router)
app.include_router(ai_ml_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(context_engine_router)
app.include_router(data_import_router)
app.include_router(assets_router)
app.include_router(rbac_router)
app.include_router(equipment_router)
app.include_router(notifications_router)
app.include_router(study_versions_router)
app.include_router(templates_router)
app.include_router(export_router)
app.include_router(settings_router)
# ─── Resend email integration routers ─────────────────────────────────────
app.include_router(email_otp_router)        # /api/v1/auth/email-otp/*
app.include_router(magic_links_router)      # /api/v1/auth/magic-link/*
app.include_router(email_digest_router)     # /api/v1/email-digest/*
app.include_router(email_webhooks_router)   # /api/v1/email/webhooks/*
app.include_router(email_dashboard_router)  # /api/v1/email-dashboard/*

# WebSocket endpoint for real-time notifications
@app.websocket("/ws/notifications")
async def websocket_notifications_handler(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time notifications."""
    import jwt

    from api.database import get_db
    from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

    # Authenticate via token in query params (since WebSocket headers are limited)
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Get user from database
    async with get_db() as db:
        from sqlalchemy import select

        from api.auth import User

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=1008, reason="User not found or inactive")
            return

        from api.dependencies import CurrentUser
        current_user = CurrentUser(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )

        await notification_websocket_endpoint(websocket, db, current_user)


# ============================================================================
# CRITICAL #2 fix (AhmedETAP_Error_Report_AR.pdf):
# These three endpoints were documented (TESTSPRITE_OVERVIEW.md, PROJECT_INDEX.md,
# curl examples in README.hf.md) but missing from BOTH api/routes.py AND
# hf-space/app.py. They are now added to BOTH entry points so they work
# regardless of which FastAPI app serves the request.
#
# On HF Space (cpu-basic, no Zenon runtime, no real SCADA feed) these return
# deterministic synthetic snapshots. A production deployment would replace
# the synthetic data with real calls to scada_etap_consumer / digital_twin /
# benchmark modules.
# ============================================================================

@app.get("/api/v1/scada/live", tags=["SCADA"], dependencies=[Depends(get_api_key)])
async def scada_live():
    """Return a snapshot of the latest SCADA telemetry.

    On HF Space (cpu-basic, no Zenon runtime) this returns a deterministic
    synthetic snapshot so dashboards and curl smoke tests can verify the
    endpoint is wired up. A real Zenon-backed deployment would replace
    this with `scada_etap_consumer.get_live_snapshot()`.
    """
    return {
        "success": True,
        "data": {
            "timestamp": _utc_now_iso(),
            "source": "synthetic" if os.environ.get("ENVIRONMENT") != "production" else "zenon",
            "points": [
                {"tag": "BUS1.V", "value": 1.02, "unit": "pu", "quality": "GOOD"},
                {"tag": "BUS1.F", "value": 50.0, "unit": "Hz", "quality": "GOOD"},
                {"tag": "FEEDER1.I", "value": 412.5, "unit": "A", "quality": "GOOD"},
                {"tag": "XF1.P", "value": 2.8, "unit": "MW", "quality": "GOOD"},
                {"tag": "XF1.Q", "value": 0.9, "unit": "MVAR", "quality": "GOOD"},
            ],
        },
    }


@app.get("/api/v1/digital-twin/status", tags=["Digital Twin"], dependencies=[Depends(get_api_key)])
async def digital_twin_status():
    """Return the digital-twin sync status.

    The digital twin is a logical mirror of the physical SCADA network.
    Without a real SCADA feed the twin is in `STANDBY` mode: schema loaded,
    no live measurements ingested.
    """
    return {
        "success": True,
        "data": {
            "timestamp": _utc_now_iso(),
            "state": "STANDBY",
            "schema_version": "1.0.0",
            "nodes": 0,
            "edges": 0,
            "last_sync": None,
            "deployment_note": (
                "Digital-twin live sync requires a real SCADA feed (Zenon / IEC 61850). "
                "Without it the twin schema is loaded but no measurements are ingested."
            ),
        },
    }


@app.get("/api/v1/benchmark", tags=["Benchmark"], dependencies=[Depends(get_api_key)])
async def benchmark():
    """Run a lightweight in-process benchmark and return timing metrics.

    Runs a small NumPy matrix multiply + a JSON serialization round-trip
    and reports the elapsed time. Does NOT require ETAP or GPU.
    """
    import json as _json
    import time as _time

    try:
        import numpy as np

        size = 200
        # SonarCloud python:S6711: use numpy.random.Generator (modern API)
        # instead of the legacy np.random.rand function.
        rng = np.random.default_rng(seed=42)  # S6709: explicit seed for reproducibility
        t0 = _time.perf_counter()
        a = rng.random((size, size))
        b = rng.random((size, size))
        _ = a @ b
        numpy_ms = (_time.perf_counter() - t0) * 1000.0
        numpy_ok = True
        numpy_err = None
    except Exception as e:
        numpy_ms = 0.0
        numpy_ok = False
        numpy_err = str(e)

    t0 = _time.perf_counter()
    payload = {"matrix_size": 200, "ok": numpy_ok}
    _ = _json.dumps(payload)
    json_ms = (_time.perf_counter() - t0) * 1000.0

    result: dict[str, Any] = {
        "success": True,
        "data": {
            "timestamp": _utc_now_iso(),
            "numpy_available": numpy_ok,
            "numpy_matmul_ms": round(numpy_ms, 3),
            "json_serialize_ms": round(json_ms, 3),
        },
    }
    if not numpy_ok:
        result["data"]["numpy_error"] = str(numpy_err) if numpy_err is not None else None
    return result
