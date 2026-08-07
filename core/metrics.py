"""
core/metrics.py — Prometheus instrumentation for the AhmedETAP platform.

Patterns drawn from prometheus/client_python:
- Counter, Gauge, Histogram, Summary for tracking operations
- Decorators for automatic instrumentation
- Standard label conventions
- Thread-safe metric exposition
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import (
    Request,  # noqa: F401 — required for decorator-wrapped endpoint annotation resolution
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metric factory — handles duplicate registration in test environments
# where both api.routes and hf-space/app.py are imported in the same process.
# ---------------------------------------------------------------------------


def _safe_counter(name, description, labels=None):
    """Create a Counter, or return existing if already registered."""
    # Check if already registered
    existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
    if existing is not None:
        return existing
    try:
        if labels:
            return Counter(name, description, labels)
        return Counter(name, description)
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if existing is not None:
            return existing
        raise


def _safe_histogram(name, description, labels=None, buckets=None):
    """Create a Histogram, or return existing if already registered."""
    existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
    if existing is not None:
        return existing
    try:
        if labels and buckets:
            return Histogram(name, description, labels, buckets=buckets)
        if labels:
            return Histogram(name, description, labels)
        return Histogram(name, description)
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if existing is not None:
            return existing
        raise


def _safe_gauge(name, description, labels=None):
    """Create a Gauge, or return existing if already registered."""
    existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
    if existing is not None:
        return existing
    try:
        if labels:
            return Gauge(name, description, labels)
        return Gauge(name, description)
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if existing is not None:
            return existing
        raise


# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------

REQUEST_ERRORS_TOTAL = _safe_counter(
    "request_errors_total",
    "Total request errors",
    ["method", "route"],
)

REQUEST_LATENCY_SECONDS = _safe_histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# ---------------------------------------------------------------------------
# Cache metrics
# ---------------------------------------------------------------------------

CACHE_HITS_TOTAL = _safe_counter(
    "cache_hits_total",
    "Total cache hits",
)

CACHE_MISSES_TOTAL = _safe_counter(
    "cache_misses_total",
    "Total cache misses",
)

# ---------------------------------------------------------------------------
# System availability metrics
# ---------------------------------------------------------------------------

SCADA_AVAILABLE = _safe_gauge(
    "scada_available",
    "SCADA service availability",
)

DIGITAL_TWIN_AVAILABLE = _safe_gauge(
    "digital_twin_available",
    "Digital Twin service availability",
)

# ---------------------------------------------------------------------------
# Application info
# ---------------------------------------------------------------------------

APP_INFO = None
_existing_info = REGISTRY._names_to_collectors.get("app_info")  # type: ignore[attr-defined]
if _existing_info is not None:
    APP_INFO = _existing_info
else:
    try:
        APP_INFO = Info("app_info", "AhmedETAP platform metadata")
    except ValueError:
        APP_INFO = REGISTRY._names_to_collectors.get("app_info")  # type: ignore[attr-defined]


def set_app_info(name: str, version: str, environment: str = "development") -> None:
    """Set the application-info metric (single-source-of-truth for version)."""
    APP_INFO.info({"name": name, "version": version, "environment": environment})


# ---------------------------------------------------------------------------
# Skill-related metrics
# ---------------------------------------------------------------------------

SKILL_OPERATIONS = _safe_counter(
    "skill_operations_total",
    "Total skill operations, partitioned by operation and status",
    ["operation", "status"],
)

SKILL_LOAD_DURATION = _safe_histogram(
    "skill_load_duration_seconds",
    "Time spent loading individual skills",
    ["skill_name"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

SKILL_OPERATIONS_IN_FLIGHT = _safe_gauge(
    "skill_operations_in_progress",
    "Number of skill operations currently executing",
    ["operation_type"],
)

SKILL_CACHE_ENTRIES = _safe_gauge(
    "skill_cache_entries",
    "Number of entries in the skill cache",
)

SKILL_ERRORS = _safe_counter(
    "skill_errors_total",
    "Total skill errors by error type and skill name",
    ["error_type", "skill_name"],
)

SKILL_VALIDATION_FAILURES = _safe_counter(
    "skill_validation_failures_total",
    "Total validation failures by reason category",
    ["reason"],
)

# ---------------------------------------------------------------------------
# Execution metrics
# ---------------------------------------------------------------------------

EXECUTION_DURATION = _safe_histogram(
    "execution_duration_seconds",
    "End-to-end execution duration by skill and phase",
    ["skill_name", "phase"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

EXECUTION_COUNT = _safe_counter(
    "executions_total",
    "Total executions by skill name and status",
    ["skill_name", "status"],
)

# ---------------------------------------------------------------------------
# System / resource metrics
# ---------------------------------------------------------------------------

MEMORY_USAGE_BYTES = _safe_gauge(
    "memory_usage_bytes",
    "RSS memory usage by subsystem",
    ["component"],
)

ACTIVE_CONNECTIONS = _safe_gauge(
    "active_connections",
    "Currently active database / API connections",
    ["target"],
)

# ---------------------------------------------------------------------------
# Decorators for automatic instrumentation
# ---------------------------------------------------------------------------


def _wrap_with_original_globals(wrapper: Callable, original: Callable) -> Callable:
    """Ensure *wrapper* can resolve annotations from *original*'s module.

    Decorators defined in one module (e.g. ``core/metrics.py``) wrap endpoint
    functions defined in another module (e.g. ``api/studies.py``).  Because
    FastAPI/Pydantic resolve string annotations using the *wrapper* function's
    ``__globals__``, types imported only in the *original* module (such as
    ``fastapi.Request`` or ``core_model.specs.StudyRequest``) would otherwise
    be unresolved, breaking OpenAPI schema generation.

    We mutate the wrapper's ``__globals__`` in-place so that the wrapper
    retains access to both its own module globals (e.g. Prometheus metrics)
    and the original function's module globals (e.g. Pydantic models).
    """
    wrapper.__globals__.update(original.__globals__)  # type: ignore[attr-defined]
    wrapper.__wrapped__ = original
    return wrapper


def track_skill_operation(operation: str) -> Callable:
    """Instrument a function with in-flight gauge + result counter.

    Works transparently with both sync and async functions.

    Usage::

        @track_skill_operation("load")
        def load_skill(name: str) -> SkillDefinition:
            ...
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                SKILL_OPERATIONS_IN_FLIGHT.labels(operation_type=operation).inc()
                try:
                    result = await func(*args, **kwargs)
                    SKILL_OPERATIONS.labels(operation=operation, status="success").inc()
                    return result
                except Exception as exc:
                    SKILL_OPERATIONS.labels(operation=operation, status="error").inc()
                    SKILL_ERRORS.labels(error_type=type(exc).__name__, skill_name="unknown").inc()
                    raise
                finally:
                    SKILL_OPERATIONS_IN_FLIGHT.labels(operation_type=operation).dec()

            return _wrap_with_original_globals(async_wrapper, func)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            SKILL_OPERATIONS_IN_FLIGHT.labels(operation_type=operation).inc()
            try:
                result = func(*args, **kwargs)
                SKILL_OPERATIONS.labels(operation=operation, status="success").inc()
                return result
            except Exception as exc:
                SKILL_OPERATIONS.labels(operation=operation, status="error").inc()
                SKILL_ERRORS.labels(error_type=type(exc).__name__, skill_name="unknown").inc()
                raise
            finally:
                SKILL_OPERATIONS_IN_FLIGHT.labels(operation_type=operation).dec()

        return _wrap_with_original_globals(sync_wrapper, func)

    return decorator


def track_execution_duration(skill_name: str, phase: str = "total") -> Callable:
    """Time a function via Histogram, recording the *skill_name* label."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            hist = EXECUTION_DURATION.labels(skill_name=skill_name, phase=phase)
            with hist.time():
                return func(*args, **kwargs)

        return wrapper

    return decorator


def count_executions(skill_name: str) -> Callable:
    """Increment success / error counter on function exit.

    Works transparently with both sync and async functions.
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = await func(*args, **kwargs)
                    EXECUTION_COUNT.labels(skill_name=skill_name, status="success").inc()
                    return result
                except Exception:
                    EXECUTION_COUNT.labels(skill_name=skill_name, status="error").inc()
                    raise

            return _wrap_with_original_globals(async_wrapper, func)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = func(*args, **kwargs)
                EXECUTION_COUNT.labels(skill_name=skill_name, status="success").inc()
                return result
            except Exception:
                EXECUTION_COUNT.labels(skill_name=skill_name, status="error").inc()
                raise

        return _wrap_with_original_globals(sync_wrapper, func)

    return decorator


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_metrics_content_type() -> str:
    """Content-type header value for the ``/metrics`` endpoint."""
    return CONTENT_TYPE_LATEST


def generate_metrics() -> bytes:
    """Return the latest Prometheus exposition format as bytes."""
    return generate_latest(REGISTRY)


def observe_memory(component: str, rss_bytes: int) -> None:
    """Record a single RSS-memory observation for *component*."""
    MEMORY_USAGE_BYTES.labels(component=component).set(rss_bytes)


def set_cache_entries(count: int) -> None:
    """Update the cache-entry gauge."""
    SKILL_CACHE_ENTRIES.set(count)


def record_validation_failure(reason: str) -> None:
    """Increment the validation-failure counter."""
    SKILL_VALIDATION_FAILURES.labels(reason=reason).inc()
