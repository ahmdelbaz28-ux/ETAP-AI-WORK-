"""
Bootstrap module for the Engineering Service.
Handles initialization of logging, metrics, and core services with privacy controls.
"""

import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, Info

# ---------------------------------------------------------------------------
# Environment Variables and Configuration
# ---------------------------------------------------------------------------

# Privacy mode - when enabled, disables all external telemetry
PRIVACY_MODE = os.environ.get("PRIVACY_MODE", "false").lower() == "true"


# ---------------------------------------------------------------------------
# numpy-aware JSON sanitizer
# ---------------------------------------------------------------------------
# The native PowerSystemEngine returns dicts containing numpy scalars / arrays.
# Pydantic v2's default encoder cannot serialize them, so we recursively
# convert any numpy types to native Python equivalents before returning.
try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except Exception:  # numpy is normally present, but be defensive
    np = None  # type: ignore
    _HAS_NUMPY = False


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy types (and other engine outputs) to native
    Python primitives that FastAPI / Pydantic can serialize as JSON."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        # Reject nan/inf which are not valid JSON
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
            return None
        return obj
    if isinstance(obj, complex):
        re, im = obj.real, obj.imag
        if not _HAS_NUMPY:
            import math as _math
            if not _math.isfinite(re):
                re = 0.0
            if not _math.isfinite(im):
                im = 0.0
        return {"re": _to_jsonable(re), "im": _to_jsonable(im)}
    if _HAS_NUMPY:
        if isinstance(obj, np.ndarray):
            return [_to_jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
            if v != v or v in (float("inf"), float("-inf")):
                return None
            return v
        if isinstance(obj, (np.bool_,)):
            return bool(obj.item())
        if isinstance(obj, np.complexfloating):
            return {"real": _to_jsonable(obj.real), "imag": _to_jsonable(obj.imag)}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    # Fallback: best-effort string coercion
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

class _TraceFilter:
    """Filter to add trace_id to log records when available in thread-local storage."""

    def __init__(self):
        self.local = threading.local()

    def filter(self, record):
        trace_id = getattr(self.local, 'current_trace_id', 'unknown')
        record.trace_id = trace_id
        return True


_trace_filter = _TraceFilter()


def _structlog_processor_wrapper(logger, method_name, event_dict):
    """Wrapper to add trace_id from thread-local storage to structlog events."""
    trace_id = getattr(_trace_filter.local, 'current_trace_id', 'unknown')
    event_dict['trace_id'] = trace_id
    return event_dict


timestamper = structlog.processors.TimeStamper(fmt="iso")
pre_chain = [
    # Add the log level and a timestamp to the event_dict
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    _structlog_processor_wrapper,  # Add our trace_id wrapper
    timestamper,
    structlog.processors.StackInfoRenderer(),
]


# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        _structlog_processor_wrapper,  # Add trace_id
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.JSONRenderer(sort_keys=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


# Create logger
logger = structlog.get_logger("engineering_service")

# Also configure the root logger to ensure consistency
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: trace_id=%(trace_id)s %(message)s",
    handlers=[logging.StreamHandler()],
)
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.addFilter(_trace_filter)


# ---------------------------------------------------------------------------
# Lazy imports (heavy numerical libs only loaded on first request)
# ---------------------------------------------------------------------------

_POWER_SYSTEM_ENGINE: Any = None
_ETAP_PROVIDER: Any = None


def _get_power_system_engine():
    global _POWER_SYSTEM_ENGINE
    if _POWER_SYSTEM_ENGINE is None:
        from engine.engine import PowerSystemEngine

        _POWER_SYSTEM_ENGINE = PowerSystemEngine
    return _POWER_SYSTEM_ENGINE


def _get_etap_provider():
    """Factory function to get ETAP provider with privacy controls."""
    def factory():
        # Respect privacy mode setting
        if PRIVACY_MODE:
            # When privacy mode is enabled, ensure ETAP is disabled
            os.environ["USE_ETAP"] = "false"

        # Import and return the ETAP provider
        from etap_integration.etap_provider import get_etap_provider
        return get_etap_provider
    return factory


# ---------------------------------------------------------------------------
# In-memory metrics (production: push to Prometheus / StatsD)
# ---------------------------------------------------------------------------

# Prometheus metrics
_requests_total = Counter(
    "requests_total",
    "Total number of requests processed",
    labelnames=["endpoint", "method", "status"]
)
_request_duration_seconds = Histogram(
    "request_duration_seconds",
    "Request duration in seconds",
    labelnames=["endpoint", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5,
             0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf"))
)
_active_requests = Gauge(
    "active_requests",
    "Number of active requests",
    labelnames=["endpoint", "method"]
)
_service_info = Info("service", "Service information")

# Internal in-memory counters (thread-safe)
_metrics_lock = threading.Lock()
_request_count = 0
_success_count = 0
_failed_count = 0
_total_execution_time_sec = 0.0


def _increment_counter(counter_type: str) -> None:
    """Thread-safe increment of internal counters."""
    global _request_count, _success_count, _failed_count
    with _metrics_lock:
        if counter_type == "request":
            _request_count += 1
        elif counter_type == "success":
            _success_count += 1
        elif counter_type == "failed":
            _failed_count += 1


def _add_execution_time(delta: float) -> None:
    """Thread-safe execution time accumulator."""
    global _total_execution_time_sec
    with _metrics_lock:
        _total_execution_time_sec += delta


# ---------------------------------------------------------------------------
# Bootstrap lifespan manager
# ---------------------------------------------------------------------------

def _validate_environment() -> None:
    """Validate critical environment variables at startup."""
    env = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    is_production = env in ("production", "prod", "staging")

    # Warn about missing optional-but-recommended vars
    warnings: list[str] = []
    if is_production:
        if not os.environ.get("JWT_SECRET_KEY"):
            warnings.append("JWT_SECRET_KEY not set - JWT tokens will not survive restarts")
        if not os.environ.get("ENGINEERING_SERVICE_API_KEY"):
            auth_disabled = os.environ.get(
                "ENGINEERING_SERVICE_AUTH_DISABLED", ""
            ).lower() in ("1", "true", "yes")
            if not auth_disabled:
                warnings.append(
                    "ENGINEERING_SERVICE_API_KEY not set and auth not disabled"
                )

    for w in warnings:
        logger.warning("env_validation: %s", w)


@asynccontextmanager
async def lifespan(app):
    """
    Lifespan context manager for application startup and shutdown events.
    """
    logger.info("Application starting up")

    # Validate environment
    _validate_environment()

    # Privacy mode notification
    if PRIVACY_MODE:
        logger.info("Privacy mode enabled - external telemetry disabled")

    # Initialize cache
    global _study_cache
    _study_cache = _initialize_cache_with_retry()

    try:
        yield
    finally:
        logger.info("Application shutting down")
        # Perform cleanup if needed
        if hasattr(_study_cache, 'clear'):
            try:
                await _study_cache.clear()
            except Exception as e:
                logger.warning(f"Cache cleanup failed: {e}")


def _initialize_cache_with_retry(max_retries: int = 3) -> Any:
    """Initialize cache with retry mechanism."""
    from services.cache_service import StudyCache
    for attempt in range(max_retries):
        try:
            cache = StudyCache()
            # Test the cache connection
            if hasattr(cache, 'ping') and asyncio.run(cache.ping()):
                logger.info(
                    f"Cache connection established (attempt {attempt + 1})")
                return cache
            else:
                logger.warning(
                    f"Cache connection failed (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(
                f"Cache initialization failed (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                logger.error(
                    "Failed to initialize cache after all retries, using fallback")
                # Return a basic in-memory cache as fallback
                return StudyCache(redis_url="memory://fallback", ttl=3600)
        time.sleep(2 ** attempt)  # Exponential backoff
    return None


# Initialize cache placeholder (actual init happens in lifespan)
_study_cache: Any = None


def get_study_cache():
    """Get the global study cache instance."""
    return _study_cache


def get_logger():
    """Get the configured logger instance."""
    return logger
