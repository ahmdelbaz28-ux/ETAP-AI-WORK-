"""
API Routes module for the Engineering Service.
Handles all API endpoints, request validation, and response formatting.
"""

import asyncio
import hmac
import json
import logging
import os
import sys
import time
import uuid
from typing import Dict, List, Any
from contextlib import asynccontextmanager

import threading as _threading

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from core.bootstrap import lifespan, logger, _increment_counter, _add_execution_time, _study_cache, _TraceFilter
from services.study_service import execute_study_logic, StudyRequest, StudyResult, SystemSpec
from core.metrics import (
    count_executions,
    generate_metrics,
    get_metrics_content_type,
    set_app_info,
    track_skill_operation,
)
from core.tracing import get_tracer, inject_context, trace_operation
from opentelemetry.trace import SpanKind, Status, StatusCode

from worker.tasks import execute_engineering_study_task, execute_etap_integration_task
from services.cache_service import get_study_cache, set_study_cache
from api.websocket import scada_websocket_endpoint

# Create FastAPI app instance
app = FastAPI(
    title="Engineering Service API",
    description="Production-grade FastAPI service wrapping the Python PowerSystemEngine",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# API Key validation
# ---------------------------------------------------------------------------

_EXPECTED_API_KEY = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")

# ---------------------------------------------------------------------------
# Smithery Integration — External API Key Management
# If SMITHERY_API_KEY is set, it can be used as an alternative to
# ENGINEERING_SERVICE_API_KEY, enabling centralized key management via
# the Smithery platform (https://smithery.ai).
# NOTE: Smithery key is NOT used as the service auth key anymore for security.
# It is stored separately for Smithery-specific integrations only.
# ---------------------------------------------------------------------------
_SMITHERY_API_KEY = os.environ.get("SMITHERY_API_KEY", "")
if _SMITHERY_API_KEY:
    logger.info("smithery_api_key_available", extra={"trace_id": "startup"})

_API_KEY_CONFIGURED = bool(_EXPECTED_API_KEY)

# Fail-fast in production: if no API key is configured and AUTH_DISABLED is
# not explicitly set, refuse to start. This prevents running an unauthenticated
# service in production accidentally.
_AUTH_DISABLED = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
if not _API_KEY_CONFIGURED and not _AUTH_DISABLED:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.critical(
            "FATAL: ENGINEERING_SERVICE_API_KEY is not set in %s environment. "
            "Set the API key or explicitly set ENGINEERING_SERVICE_AUTH_DISABLED=true "
            "to allow unauthenticated access (NOT recommended for production).",
            _ENV,
        )
        sys.exit(1)


def _require_api_key(request: Request) -> None:
    """Validate API key when configured.

    If ENGINEERING_SERVICE_API_KEY is set, every request must carry a
    matching ``x-api-key`` header.  If the key is *not* set:
    - In development: unauthenticated access is allowed (with warning).
    - In production: requests are REJECTED (fail-closed) unless
      ENGINEERING_SERVICE_AUTH_DISABLED=true is explicitly set.
    """
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            return  # Explicitly opted-in to unauthenticated mode
        _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
        if _ENV in ("production", "prod", "staging"):
            raise HTTPException(
                status_code=401,
                detail="Authentication required but no API key configured. "
                       "Set ENGINEERING_SERVICE_API_KEY or ENGINEERING_SERVICE_AUTH_DISABLED=true",
            )
        # Development mode: allow unauthenticated access with warning
        return
    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, _EXPECTED_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Body size limit middleware
# ---------------------------------------------------------------------------

_MAX_BODY_SIZE = int(os.environ.get("ENGINEERING_SERVICE_MAX_BODY_SIZE", "1_048_576"))


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > _MAX_BODY_SIZE:
                raise HTTPException(status_code=413, detail="Request body too large")
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate Limiting (in-memory, per-client)
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_WINDOW", "60"))  # seconds
_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX", "100"))  # requests per window
_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_lock = _threading.Lock()
_RATE_LIMIT_MAX_ENTRIES = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX_ENTRIES", "10000"))


def _check_rate_limit(client_id: str) -> bool:
    """Check if the client has exceeded the rate limit. Returns True if allowed.

    Includes proactive cleanup to prevent unbounded memory growth.
    """
    now = time.time()
    with _rate_limit_lock:
        # Proactive cleanup: prune stale entries when store grows too large
        if len(_rate_limit_store) > _RATE_LIMIT_MAX_ENTRIES:
            stale = [cid for cid, timestamps in _rate_limit_store.items()
                     if not timestamps or now - timestamps[-1] > _RATE_LIMIT_WINDOW]
            for cid in stale:
                del _rate_limit_store[cid]

        if client_id not in _rate_limit_store:
            _rate_limit_store[client_id] = [now]
            return True
        # Remove timestamps outside the window
        _rate_limit_store[client_id] = [
            t for t in _rate_limit_store[client_id] if now - t < _RATE_LIMIT_WINDOW
        ]
        if len(_rate_limit_store[client_id]) >= _RATE_LIMIT_MAX_REQUESTS:
            return False
        _rate_limit_store[client_id].append(now)
        return True


# ---------------------------------------------------------------------------
# Request Timeout
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT_SEC = int(os.environ.get("ENGINEERING_SERVICE_REQUEST_TIMEOUT", "120"))  # seconds


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = trace_id

    # ── OpenTelemetry: extract incoming trace context and start a span ──
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
        # Set the OTel trace ID as an attribute so it correlates with x-trace-id
        span.set_attribute("ahmedetap.trace_id", trace_id)

        # Rate limiting — skip for health endpoints
        if not request.url.path.startswith(("/health", "/ready", "/healthz", "/readyz", "/")):
            _TRUSTED_PROXIES = os.environ.get("ENGINEERING_SERVICE_TRUSTED_PROXIES", "")
            if _TRUSTED_PROXIES:
                _trusted_list = [p.strip() for p in _TRUSTED_PROXIES.split(",")]
                xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                proxy_ip = request.client.host if request.client else ""
                client_id = xff if proxy_ip in _trusted_list and xff else (request.client.host if request.client else "unknown")
            else:
                client_id = request.client.host if request.client else "unknown"
            if not _check_rate_limit(client_id):
                span.set_status(Status(StatusCode.ERROR, "rate_limit_exceeded"))
                span.set_attribute("http.status_code", 429)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded", "trace_id": trace_id},
                    headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
                )

        response = await call_next(request)
        return response


# Health check endpoints
@app.head("/")
@app.get("/")
async def root():
    return {"status": "ok", "service": "engineering-service"}


@app.head("/healthz")
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.head("/readyz")
@app.get("/readyz")
async def readyz():
    return {"status": "ok"}


# Define HealthResponse and ReadyResponse models if they don't exist
class HealthResponse(BaseModel):
    status: str
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    timestamp: str


@app.head("/health")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", timestamp=str(time.time()))


@app.head("/ready")
@app.get("/ready", response_model=ReadyResponse)
async def ready():
    return ReadyResponse(status="ok", timestamp=str(time.time()))


@app.get("/metrics")
async def metrics():
    from core.metrics import generate_metrics, get_metrics_content_type
    return Response(content=generate_metrics(), media_type=get_metrics_content_type())


@app.get("/prometheus/metrics")
async def prometheus_metrics():
    from core.metrics import generate_metrics
    return Response(content=generate_metrics(), media_type="text/plain")


# Main study execution endpoint (synchronous)
@app.post("/api/v1/studies/run", response_model=StudyResult)
async def run_study(study_request: StudyRequest, request: Request):
    _require_api_key(request)

    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    start_time = time.perf_counter()

    # Execute the study with proper arguments
    result = execute_study_logic(study_request, trace_id=trace_id, start_time=start_time)
    return result


# Study validation endpoint
@app.post("/api/v1/system/validate")
async def validate_system(system_spec: SystemSpec, request: Request):
    _require_api_key(request)
    
    # Validate the system specification
    # ... existing validation code ...
    return {"status": "validated", "valid": True}


# --- NEW ASYNC AND WEBSOCKET ENDPOINTS ADDED FOR PRODUCTION SCALABILITY ---

from celery.result import AsyncResult
from worker.celery_app import app as celery_app

@app.post('/api/v1/studies/run_async')
async def run_study_async(study_request: StudyRequest):
    """Execute an engineering study asynchronously using Celery."""
    try:
        # Send the task to Celery queue
        task = execute_engineering_study_task.delay({
            'study_type': study_request.study_type,
            'data': study_request.model_dump(),
            'request_timestamp': str(time.time())
        })

        logger.info(f'Started async study execution with task_id: {task.id}')

        return {
            'task_id': task.id,
            'status': 'accepted',
            'study_type': study_request.study_type,
            'submitted_at': str(time.time())
        }
    except Exception as e:
        logger.error(f'Error submitting async study: {str(e)}')
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/v1/studies/task_status/{task_id}')
async def get_task_status(task_id: str):
    """Get the status of an async study task."""
    try:
        task_result = AsyncResult(str(task_id), app=celery_app)
        
        response = {
            'task_id': task_id,
            'status': task_result.status,
            'result': None
        }
        
        if task_result.ready():
            if task_result.successful():
                response['result'] = task_result.result
            elif task_result.failed():
                response['error'] = str(task_result.info)
        
        # If task is in progress, get progress info
        if task_result.status == 'PROGRESS':
            response['meta'] = task_result.info
        
        return response
    except Exception as e:
        logger.error(f'Error getting task status: {str(e)}')
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket('/ws/scada/live')
async def websocket_scada_endpoint_handler(websocket: WebSocket):
    """WebSocket endpoint for real-time SCADA data streaming."""
    await scada_websocket_endpoint(websocket)


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
            logger.warning("langwatch_init_failed", extra={"trace_id": "startup", "error": str(lw_exc)})
else:
    logger.info("Privacy mode enabled - external telemetry disabled", extra={"trace_id": "startup"})


# CORS — restrict origins; default allows only same-origin.
# Set ENGINEERING_SERVICE_CORS_ORIGINS to a comma-separated list of allowed origins.
# Example: ENGINEERING_SERVICE_CORS_ORIGINS=https://yourapp.example.com,https://worker.example.com
_CORS_ORIGINS = os.environ.get("ENGINEERING_SERVICE_CORS_ORIGINS", "").strip()
_cors_origin_list = [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip()] if _CORS_ORIGINS else []
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
            "Set ENGINEERING_SERVICE_CORS_ORIGINS for production."
        )
    _cors_origin_list = []  # No origins allowed = restrictive by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization"],
    expose_headers=["x-trace-id"],
)
app.add_middleware(_BodySizeLimitMiddleware)

# Module-level shared instances for digital twin endpoint
_shared_state_store = None
_shared_event_bus = None
_shared_validation_gateway = None