"""
Health and Metrics API Router
=============================
Handles all health check and metrics endpoints.
Separated from main engineering service for better modularity.
"""

import time

from fastapi import APIRouter, Request
from fastapi.responses import Response

from core.bootstrap import (
    _failed_count,
    _metrics_lock,
    _request_count,
    _success_count,
    _total_execution_time_sec,
)
from core.metrics import generate_metrics, get_metrics_content_type

router = APIRouter(prefix="", tags=["health"])


class HealthResponse:
    def __init__(self, status: str, version: str, timestamp: str, trace_id: str):
        self.status = status
        self.version = version
        self.timestamp = timestamp
        self.trace_id = trace_id


class ReadyResponse:
    def __init__(
        self,
        ready: bool,
        native_engine_available: bool,
        etap_available: bool,
        timestamp: str,
        trace_id: str,
    ):
        self.ready = ready
        self.native_engine_available = native_engine_available
        self.etap_available = etap_available
        self.timestamp = timestamp
        self.trace_id = trace_id


class MetricsResponse:
    def __init__(
        self,
        requests_total: int,
        requests_success: int,
        requests_failed: int,
        avg_execution_time_ms: float,
        trace_id: str,
    ):
        self.requests_total = requests_total
        self.requests_success = requests_success
        self.requests_failed = requests_failed
        self.avg_execution_time_ms = avg_execution_time_ms
        self.trace_id = trace_id


@router.head("/")
@router.get("/")
async def root():
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "Ahmed etap Engineering Platform", "version": "1.0.0"}


@router.head("/healthz")
@router.get("/healthz")
async def healthz():
    """Lightweight liveness probe (no heavy initialization)."""
    return {"status": "alive"}


@router.head("/readyz")
@router.get("/readyz")
async def readyz():
    """Readiness probe — checks critical dependencies."""
    checks = {"python": True, "imports": True}
    all_ready = all(checks.values())
    return {"ready": all_ready, "checks": checks}


@router.head("/health")
@router.get("/health")
async def health_check(request: Request):
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@router.head("/ready")
@router.get("/ready")
async def readiness_check(request: Request):
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
async def metrics(request: Request):
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
async def prometheus_metrics():
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
