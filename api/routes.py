"""
API Routes module for the Engineering Service.
Handles all API endpoints, request validation, and response formatting.
"""

import hmac
import os
import sys
import threading as _threading
import time
import uuid
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from api.agents import router as agents_router
from api.health import router as health_router
from api.studies import router as studies_router
from api.websocket import scada_websocket_endpoint
from core.bootstrap import lifespan, logger
from core.tracing import get_tracer
from services.study_service import (
    StudyRequest,
    SystemSpec,
)

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
    """Validate API key when configured."""
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            return
        _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
        if _ENV in ("production", "prod", "staging"):
            raise HTTPException(
                status_code=401,
                detail="Authentication required but no API key configured. "
                "Set ENGINEERING_SERVICE_API_KEY or ENGINEERING_SERVICE_AUTH_DISABLED=true",
            )
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
# Rate Limiting (Redis-backed, per-client) + fallback in-memory
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_WINDOW", "60"))
_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX", "100"))

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_RATE_LIMIT_PREFIX = os.environ.get("RATE_LIMIT_PREFIX", "rate-limit:")

_rate_limit_fallback_store: Dict[str, List[float]] = {}
_rate_limit_fallback_lock = _threading.Lock()
_RATE_LIMIT_MAX_ENTRIES = int(
    os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX_ENTRIES", "10000")
)

try:
    import redis.asyncio as redis_async  # type: ignore
except Exception:  # pragma: no cover
    redis_async = None  # type: ignore

_redis_client = None


def _get_rate_limit_redis():
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
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = trace_id

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
        if not request.url.path.startswith(
            ("/health", "/ready", "/healthz", "/readyz")
        ):
            _TRUSTED_PROXIES = os.environ.get("ENGINEERING_SERVICE_TRUSTED_PROXIES", "")
            if _TRUSTED_PROXIES:
                _trusted_list = [p.strip() for p in _TRUSTED_PROXIES.split(",")]
                xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                proxy_ip = request.client.host if request.client else ""
                client_id = (
                    xff
                    if proxy_ip in _trusted_list and xff
                    else (request.client.host if request.client else "unknown")
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
# @app.head("/health")
# @app.get("/health", response_model=HealthResponse)
# async def health():
#     return HealthResponse(status="ok", timestamp=str(time.time()))
#
#
# @app.head("/ready")
# @app.get("/ready", response_model=ReadyResponse)
# async def ready():
#     return ReadyResponse(status="ok", timestamp=str(time.time()))
#
#
# @app.get("/metrics")
# async def metrics():
#     return Response(content=generate_metrics(), media_type=get_metrics_content_type())
#
#
# @app.get("/prometheus/metrics")
# async def prometheus_metrics():
#     return Response(content=generate_metrics(), media_type="text/plain")

# Main study execution endpoint is now handled by studies router
# See api/studies.py for implementation
# @app.post("/api/v1/studies/run", response_model=StudyResult)
# async def run_study(study_request: StudyRequest, request: Request):
#     _require_api_key(request)
#
#     trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
#     start_time = time.perf_counter()
#
#     # Execute the study with proper arguments
#     result = execute_study_logic(study_request, trace_id=trace_id, start_time=start_time)
#     return result


# Study validation endpoint
@app.post("/api/v1/system/validate")
async def validate_system(system_spec: SystemSpec, request: Request):
    _require_api_key(request)

    # Validate the system specification
    return {"status": "validated", "valid": True}


# --- NEW ASYNC AND WEBSOCKET ENDPOINTS ADDED FOR PRODUCTION SCALABILITY ---

# Import celery components for async task support inside the functions to avoid startup errors
def get_celery_components():
    """Lazy loading of Celery components to avoid import errors during startup."""
    try:
        # Use importlib to dynamically import to avoid Pylance static analysis issues
        import importlib

        celery_result_module = importlib.import_module('celery.result')
        AsyncResult = celery_result_module.AsyncResult

        worker_tasks_module = importlib.import_module('worker.tasks')
        execute_engineering_study_task = worker_tasks_module.execute_engineering_study_task

        worker_celery_app_module = importlib.import_module('worker.celery_app')
        celery_app = worker_celery_app_module.app

        return AsyncResult, execute_engineering_study_task, celery_app
    except ImportError as e:
        logger.warning(f"Celery not available: {e}")
        return None, None, None


@app.post('/api/v1/studies/run_async')
async def run_study_async(study_request: StudyRequest, request: Request):
    """Execute an engineering study asynchronously using Celery."""
    _require_api_key(request)  # Add authentication check

    CeleryAsyncResult, execute_engineering_study_task, celery_app = get_celery_components()

    if not execute_engineering_study_task:
        raise HTTPException(status_code=500, detail="Celery is not available for async processing")

    try:
        # Send the task to Celery queue - using getattr to avoid Pylance type checking errors

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
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get('/api/v1/studies/task_status/{task_id}')
async def get_task_status(task_id: str, request: Request):
    """Get the status of an async study task."""
    _require_api_key(request)  # Add authentication check

    CeleryAsyncResult, execute_engineering_study_task, celery_app = get_celery_components()

    if not CeleryAsyncResult or not celery_app:
        raise HTTPException(status_code=500, detail="Celery is not available")

    try:
        # Using the retrieved AsyncResult class to create an instance
        task_result = CeleryAsyncResult(str(task_id), app=celery_app)

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
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.websocket('/ws/scada/live')
async def websocket_scada_endpoint_handler(websocket: WebSocket):
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
    # Don't allow credentials when no origins are configured
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origin_list,
        allow_credentials=False,  # Don't allow credentials with empty origin list
        allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization"],
        expose_headers=["x-trace-id"],
    )
else:
    # Allow credentials only when specific origins are configured
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization"],
        expose_headers=["x-trace-id"],
    )
app.add_middleware(_BodySizeLimitMiddleware)

# Global exception handler to prevent raw exception exposure
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to prevent raw exception exposure in production.
    Logs the full exception server-side but returns a generic response to clients.
    """
    import traceback

    # Log the full exception details server-side
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}",
        extra={
            "trace_id": getattr(request.state, "trace_id", "unknown"),
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    )

    # Return a generic error response to prevent information disclosure
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please contact support if the issue persists.",
            "trace_id": getattr(request.state, "trace_id", "unknown")
        }
    )

# Module-level shared instances for digital twin endpoint
_shared_state_store = None
_shared_event_bus = None
_shared_validation_gateway = None

# Register only the routers that exist
app.include_router(health_router)
app.include_router(studies_router)
app.include_router(agents_router)
