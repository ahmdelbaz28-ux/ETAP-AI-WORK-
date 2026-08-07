"""
Bootstrap module for the Engineering Service.
Handles initialization of logging, metrics, and core services with privacy controls.
"""

from __future__ import annotations

import asyncio
import json
import logging
<<<<<<< HEAD
import math
import os
import threading
=======
import os
import threading
from contextlib import asynccontextmanager
>>>>>>> origin/fix/scenario-tests-properly

# Prometheus metrics are optional for dev tooling / local environments.
# If prometheus_client isn't installed (or the interpreter isn't wired),
# fall back to no-op metric objects to prevent import-time failures.
<<<<<<< HEAD
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
=======
>>>>>>> origin/fix/scenario-tests-properly
from importlib import import_module
from typing import Any

import structlog

try:
    _pc = import_module("prometheus_client")
    Counter = _pc.Counter
    Gauge = _pc.Gauge
    Histogram = _pc.Histogram
    Info = _pc.Info
except Exception:  # pragma: no cover

    class _PromStub:
        def __init__(self, *args, **kwargs):
<<<<<<< HEAD
            pass  # NOSONAR intentional no-op (protocol stub / test fixture)
=======
            pass
>>>>>>> origin/fix/scenario-tests-properly

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            return None

        def dec(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

    Counter = Gauge = Histogram = Info = _PromStub  # type: ignore

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
from typing import Any as _Any

try:
    import numpy as np  # type: ignore
except Exception:  # numpy is normally present, but be defensive
    np: _Any = None  # type: ignore


<<<<<<< HEAD
def _to_jsonable(  # NOSONAR
    obj: Any,
) -> Any:  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
=======
def _to_jsonable(obj: Any) -> Any:
>>>>>>> origin/fix/scenario-tests-properly
    """Recursively convert numpy types (and other engine outputs) to native
    Python primitives that FastAPI / Pydantic can serialize as JSON."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
<<<<<<< HEAD
        # Reject NaN/inf which are not valid JSON. math.isnan/isinf is
        # clearer than the `obj != obj` trick (SonarCloud S1764).
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
=======
        # Reject nan/inf which are not valid JSON
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
>>>>>>> origin/fix/scenario-tests-properly
            return None
        return obj
    if isinstance(obj, complex):
        re, im = obj.real, obj.imag
        if np is None:
            import math as _math

            if not _math.isfinite(re):
                re = 0.0
            if not _math.isfinite(im):
                im = 0.0
        return {"re": _to_jsonable(re), "im": _to_jsonable(im)}
    if np is not None:
        if isinstance(obj, np.ndarray):
            return [_to_jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
<<<<<<< HEAD
            if math.isnan(v) or math.isinf(v):
=======
            if v != v or v in (float("inf"), float("-inf")):
>>>>>>> origin/fix/scenario-tests-properly
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

<<<<<<< HEAD
    def filter(self, record: logging.LogRecord) -> bool:
=======
    def filter(self, record):
>>>>>>> origin/fix/scenario-tests-properly
        trace_id = getattr(self.local, "current_trace_id", "unknown")
        record.trace_id = trace_id
        return True


_trace_filter = _TraceFilter()


<<<<<<< HEAD
def _structlog_processor_wrapper(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
=======
def _structlog_processor_wrapper(logger, method_name, event_dict):
>>>>>>> origin/fix/scenario-tests-properly
    """Wrapper to add trace_id from thread-local storage to structlog events."""
    trace_id = getattr(_trace_filter.local, "current_trace_id", "unknown")
    event_dict["trace_id"] = trace_id
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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
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

<<<<<<< HEAD
        # Import and CALL the ETAP provider — return instance, not function
        from etap_integration.etap_provider import get_etap_provider

        return get_etap_provider()  # FIX: call the function, return an IEtapProvider instance
=======
        # Import and return the ETAP provider
        from etap_integration.etap_provider import get_etap_provider

        return get_etap_provider
>>>>>>> origin/fix/scenario-tests-properly

    return factory


# ---------------------------------------------------------------------------
# In-memory metrics (production: push to Prometheus / StatsD)
# ---------------------------------------------------------------------------


class _NoopMetric:  # pragma: no cover
    def labels(self, *args, **kwargs):
        return self

    def inc(self, *args, **kwargs):
        return None

    def dec(self, *args, **kwargs):
        return None

    def observe(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None


# Prometheus metrics (runtime no-op fallback if prometheus_client isn't available)
try:  # pragma: no cover
    _requests_total = Counter(
        "requests_total",
        "Total number of requests processed",
        labelnames=["endpoint", "method", "status"],
    )
    _request_duration_seconds = Histogram(
        "request_duration_seconds",
        "Request duration in seconds",
        labelnames=["endpoint", "method"],
        buckets=(
            0.005,
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
            float("inf"),
        ),
    )
    _active_requests = Gauge(
<<<<<<< HEAD
        "active_requests",
        "Number of active requests",
        labelnames=["endpoint", "method"],
=======
        "active_requests", "Number of active requests", labelnames=["endpoint", "method"]
>>>>>>> origin/fix/scenario-tests-properly
    )
    _service_info = Info("service", "Service information")
except Exception:  # pragma: no cover
    _requests_total = _NoopMetric()
    _request_duration_seconds = _NoopMetric()
    _active_requests = _NoopMetric()
    _service_info = _NoopMetric()

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
            auth_disabled = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if not auth_disabled:
                warnings.append("ENGINEERING_SERVICE_API_KEY not set and auth not disabled")

    for w in warnings:
        logger.warning("env_validation: %s", w)


@asynccontextmanager
<<<<<<< HEAD
async def lifespan(_app: Any) -> AsyncIterator[None]:
=======
async def lifespan(app):
>>>>>>> origin/fix/scenario-tests-properly
    """
    Lifespan context manager for application startup and shutdown events.
    """
    logger.info("Application starting up")

    # Validate environment
    _validate_environment()

    # Privacy mode notification
    if PRIVACY_MODE:
        logger.info("Privacy mode enabled - external telemetry disabled")

    # Initialize database
    from api.database import init_db

    await init_db()

    # Initialize cache
    global _study_cache
    _study_cache = await _initialize_cache_with_retry()

    try:
        yield
    finally:
        logger.info("Application shutting down")
        # Perform cleanup if needed
        if hasattr(_study_cache, "clear"):
            try:
                await _study_cache.clear()
            except Exception as e:
<<<<<<< HEAD
                logger.warning("Cache cleanup failed: %s", e, exc_info=True)


async def _initialize_cache_with_retry(max_retries: int = 3) -> Any:
    """Initialize cache with retry mechanism.

    Set ``ENGINEERING_SERVICE_CACHE_DISABLED=true`` to skip Redis entirely
    and use the in-memory fallback immediately — useful for tests and local
    dev where Redis is not running.
    """
    from services.cache_service import StudyCache

    # Short-circuit: if cache is explicitly disabled, go straight to the
    # in-memory fallback. This avoids the 7-second retry delay (1+2+4s)
    # that occurs when Redis is unavailable.
    if os.environ.get("ENGINEERING_SERVICE_CACHE_DISABLED", "").lower() == "true":
        logger.info(
            "Cache disabled via ENGINEERING_SERVICE_CACHE_DISABLED — using in-memory fallback",
        )
        return StudyCache(redis_url="memory://fallback", ttl=3600)

=======
                logger.warning(f"Cache cleanup failed: {e}")


async def _initialize_cache_with_retry(max_retries: int = 3) -> Any:
    """Initialize cache with retry mechanism."""
    from services.cache_service import StudyCache

>>>>>>> origin/fix/scenario-tests-properly
    for attempt in range(max_retries):
        try:
            cache = StudyCache()
            # Test the cache connection
            if hasattr(cache, "ping"):
                ping_result = await cache.ping()
                if ping_result:
<<<<<<< HEAD
                    logger.info("Cache connection established (attempt %s)", attempt + 1)
                    return cache
                else:
                    logger.warning("Cache connection failed (attempt %s)", attempt + 1)
            else:
                logger.info("Cache initialized without ping (attempt %s)", attempt + 1)
                return cache
        except Exception as e:
            logger.warning(
                "Cache initialization failed (attempt %s): %s",
                attempt + 1,
                e,
                exc_info=True,
            )
=======
                    logger.info(f"Cache connection established (attempt {attempt + 1})")
                    return cache
                else:
                    logger.warning(f"Cache connection failed (attempt {attempt + 1})")
            else:
                logger.info(f"Cache initialized without ping (attempt {attempt + 1})")
                return cache
        except Exception as e:
            logger.warning(f"Cache initialization failed (attempt {attempt + 1}): {e}")
>>>>>>> origin/fix/scenario-tests-properly
            if attempt == max_retries - 1:
                logger.error("Failed to initialize cache after all retries, using fallback")
                # Return a basic in-memory cache as fallback
                return StudyCache(redis_url="memory://fallback", ttl=3600)
        await asyncio.sleep(2**attempt)  # Exponential backoff
    return None


# Initialize cache placeholder (actual init happens in lifespan)
_study_cache: Any = None
<<<<<<< HEAD
# NOTE: get_study_cache() accessor removed — had 0 external callers.
# The cache is initialized in lifespan() and used only internally
# for cleanup. External modules should import the canonical factory:
#   from engine.caching import get_study_cache   (engine-layer singleton)
#   from services.cache_service import get_study_cache  (service-layer async factory)


def get_logger() -> Any:
=======


def get_study_cache():
    """Get the global study cache instance."""
    return _study_cache


def get_logger():
>>>>>>> origin/fix/scenario-tests-properly
    """Get the configured logger instance."""
    return logger
