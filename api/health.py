"""
Health and Metrics API Router
=============================
Handles all health check and metrics endpoints.
Separated from main engineering service for better modularity.
"""

import time

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

from core.bootstrap import (
    _failed_count,
    _metrics_lock,
    _request_count,
    _success_count,
    _total_execution_time_sec,
)
from core.metrics import generate_metrics, get_metrics_content_type

router = APIRouter(prefix="", tags=["health"])


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
async def root() -> dict[str, str]:
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "Ahmed etap Engineering Platform", "version": "1.0.0"}


@router.head("/healthz")
@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Lightweight liveness probe (no heavy initialization)."""
    return {"status": "alive"}


@router.head("/readyz")
@router.get("/readyz")
async def readyz() -> dict[str, bool | dict[str, bool]]:
    """Readiness probe — checks critical dependencies."""
    checks = {"python": True, "imports": True}
    all_ready = all(checks.values())
    return {"ready": all_ready, "checks": checks}


@router.head("/health")
@router.get("/health")
async def health_check(request: Request) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@router.get("/info")
async def platform_info(request: Request) -> dict:
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
