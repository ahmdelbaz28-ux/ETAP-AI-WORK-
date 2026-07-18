"""
Health and Metrics API Router
=============================
Handles all health check endpoints with REAL dependency checks.
Separated from main engineering service for better modularity.
"""

import os
import time
from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import text

from core.bootstrap import (
    _failed_count,
    _metrics_lock,
    _request_count,
    _success_count,
    _total_execution_time_sec,
)
from core.metrics import generate_metrics, get_metrics_content_type

router = APIRouter(prefix="", tags=["health"])


# Lazy imports for optional dependencies (DB + Redis). These are imported
# lazily inside the readiness check so that a missing or unreachable DB/Redis
# does not crash the /healthz liveness probe or import-time of this module.
def _get_db_context():
    """Lazy import of the DB session context manager."""
    from api.database import get_db_context
    return get_db_context


def _get_redis_client_func():
    """Lazy import of the Redis client getter (returns None if not configured)."""
    from api.auth import _get_redis_client
    return _get_redis_client


# Fix for CRITICAL #1 (AhmedETAP_Error_Report_AR.pdf):
# These response models MUST inherit from pydantic.BaseModel so FastAPI can
# generate a valid response_model schema. Plain Python classes cause
# `fastapi.exceptions.FastAPIError: Invalid args for response field!` at
# router decoration time, which crashes the entire app on import.
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    trace_id: str


class ReadyResponse(BaseModel):
    ready: bool
    native_engine_available: bool
    etap_available: bool
    timestamp: str
    trace_id: str


class MetricsResponse(BaseModel):
    requests_total: int
    requests_success: int
    requests_failed: int
    avg_execution_time_ms: float
    trace_id: str


@router.head("/")
@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "Ahmed etap Engineering Platform", "version": "1.0.0"}


@router.head("/healthz")
@router.get("/healthz")
async def healthz() -> Dict[str, str]:
    """Lightweight liveness probe (no heavy initialization)."""
    return {"status": "ok"}


@router.head("/readyz")
@router.get("/readyz")
async def readyz() -> Dict[str, object]:
    """Readiness probe — checks critical dependencies.

    SECURITY/OPS (E-07): Previously this returned a hardcoded {"ready": True}
    regardless of DB/Redis state. K8s/HF would route traffic to a broken
    instance. Now performs real checks on DB + Redis and returns 503 if
    any critical dependency is down.
    """
    checks: Dict[str, object] = {"python": True, "imports": True}

    # DB check
    try:
        get_db_context = _get_db_context()
        async with get_db_context() as db:
            result = await db.execute(text("SELECT 1"))
            if result.scalar() == 1:
                checks["db"] = "ok"
            else:
                checks["db"] = "fail: unexpected scalar"
    except Exception as exc:
        checks["db"] = f"fail: {type(exc).__name__}: {exc}"

    # Redis check
    try:
        get_redis_client = _get_redis_client_func()
        r = get_redis_client()
        if r is None:
            # Redis is optional — mark as not-configured, not failed
            checks["redis"] = "not_configured"
        else:
            await r.ping()
            checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"fail: {type(exc).__name__}: {exc}"

    # Critical dependencies: DB must be ok. Redis is optional in dev but
    # required in production (fail-closed if configured but unreachable).
    _env = os.getenv("ENVIRONMENT", "development").lower()
    is_prod = _env in ("production", "prod", "staging")

    db_ok = checks["db"] == "ok"
    redis_ok = checks["redis"] == "ok"
    redis_required = is_prod

    all_ready = db_ok and (redis_ok or not redis_required)
    # SECURITY (LB-2): Return HTTP 503 when not ready — K8s/HF readiness
    # probes check the HTTP status code, not the JSON body. Previously
    # this always returned 200, so the probe would route traffic to a
    # broken instance even when DB/Redis were down.
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"ready": all_ready, "checks": checks},
    )


@router.head("/health")
@router.get("/health")
async def health_check(request: Request) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@router.get("/api/v1/info")
async def platform_info(request: Request) -> Dict[str, object]:
    """Platform information endpoint — returns version, agent count, and module list.

    Provides a single endpoint for dashboards and monitoring tools to discover
    what this platform is and what it supports.
    """
    from api.shared_handlers import AGENT_COUNT, AGENTS, SUPPORTED_STANDARDS

    return {
        "version": "1.0.0",
        "name": "AhmedETAP Engineering Platform",
        "status": "healthy",
        "agent_count": AGENT_COUNT,
        "active_agents": sum(1 for a in AGENTS if a.get("status") == "active"),
        "beta_agents": sum(1 for a in AGENTS if a.get("status") == "beta"),
        "supported_standards": list(SUPPORTED_STANDARDS) if hasattr(SUPPORTED_STANDARDS, "__iter__") else SUPPORTED_STANDARDS,
        "modules": [
            "arcflash", "motorstarting", "stability", "cable-sizing",
            "earth-grid", "renewable", "battery-storage", "scada",
            "digital-twin", "predictive", "anomaly", "coordination",
            "goal-planner", "weather",
        ],
        "trace_id": request.state.trace_id,
    }


@router.get("/api/v1/knowledge")
async def knowledge_info():
    """Get knowledge base info (skills, RAG context metadata)."""
    from api.shared_handlers import build_knowledge_info
    return build_knowledge_info()


@router.head("/ready")
@router.get("/ready")
async def readiness_check(request: Request) -> ReadyResponse:
    native_ok = False
    etap_ok = False
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401

        native_ok = True
    except ImportError:
        pass
    try:
        from etap_integration.etap_provider import get_etap_provider

        provider = get_etap_provider()
        etap_ok = provider.is_available()
    except Exception as exc:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.warning("etap_provider_unavailable: %s", str(exc))
    return ReadyResponse(
        ready=native_ok,
        native_engine_available=native_ok,
        etap_available=etap_ok,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@router.get("/metrics")
async def metrics(request: Request) -> MetricsResponse:
    with _metrics_lock:
        req_count = _request_count
        suc_count = _success_count
        fail_count = _failed_count
        total_time = _total_execution_time_sec
    avg_ms = (total_time / max(req_count, 1)) * 1000.0
    return MetricsResponse(
        requests_total=req_count,
        requests_success=suc_count,
        requests_failed=fail_count,
        avg_execution_time_ms=round(avg_ms, 2),
        trace_id=request.state.trace_id,
    )


@router.get("/prometheus/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint exposing counters, histograms, and gauges
    from ``core.metrics`` in the standard Prometheus exposition format.

    Returns
    -------
    Response with ``Content-Type: text/plain; version=0.0.4``

    Metrics include:
    - ``skill_operations_total`` — partitioned by operation and status
    - ``skill_operations_in_progress`` — gauge per operation type
    - ``skill_errors_total`` — by error type and skill name
    - ``execution_duration_seconds`` — histogram by skill and phase
    - ``executions_total`` — counter by skill and status
    - ``app_info`` — version metadata
    """
    return Response(
        content=generate_metrics(),
        media_type=get_metrics_content_type(),
    )
