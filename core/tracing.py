"""
core/tracing.py — OpenTelemetry observability for the AhmedETAP platform.

Patterns drawn from open-telemetry/opentelemetry-python:
- TracerProvider initialisation with resource attributes
- Span creation via decorators and context managers
- Trace-context propagation (inject/extract)
- Graceful degradation when exporters are unavailable
"""

from __future__ import annotations

import inspect
import logging
import os as _os
from collections.abc import Callable
from functools import wraps
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.textmap import TextMapPropagator
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_tracer: trace.Tracer | None = None
_propagator: TextMapPropagator = TraceContextTextMapPropagator()

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def setup_tracing(
    service_name: str = "ahmedetap",
    service_version: str = "1.0.0",
    exporter_type: str = "console",
    otlp_endpoint: str | None = None,
    environment: str = "development",
) -> trace.Tracer:
    """Initialise the global TracerProvider and return a named tracer.

    Parameters
    ----------
    service_name : str
        Service name for the ``service.name`` resource attribute.
    service_version : str
        Version label for the ``service.version`` resource attribute.
    exporter_type : str
        ``"console"`` (default) or ``"otlp"``.
    otlp_endpoint : str, optional
        gRPC endpoint for the OTLP exporter (required if *exporter_type* is
        ``"otlp"``).
    environment : str
        Deployment environment label (e.g. ``"production"``).

    Returns
    -------
    trace.Tracer
    """
    global _tracer

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            "deployment.environment": environment,
        }
    )

    provider = TracerProvider(resource=resource)

    if exporter_type == "console":
        exporter = ConsoleSpanExporter()
        processor: Any = SimpleSpanProcessor(exporter)
    elif exporter_type == "otlp" and otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            processor = BatchSpanProcessor(exporter)
        except ImportError:
            logger.warning("OTLP exporter unavailable — falling back to console")
            exporter = ConsoleSpanExporter()
            processor = SimpleSpanProcessor(exporter)
    else:
        exporter = ConsoleSpanExporter()
        processor = SimpleSpanProcessor(exporter)

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer(service_name, service_version)
    set_global_textmap(_propagator)

    logger.info(
        "Tracing initialised for %s v%s (%s)",
        service_name,
        service_version,
        exporter_type,
    )
    return _tracer


# ---------------------------------------------------------------------------
# Auto-initialisation from environment variables
# ---------------------------------------------------------------------------
#
# If ``OTEL_EXPORTER_TYPE`` is set (e.g. ``"otlp"``), tracing is initialised
# automatically at module import time.  This avoids requiring an explicit
# ``setup_tracing()`` call in every entrypoint.
#
# Environment variables:
#   OTEL_EXPORTER_TYPE      — "console" (default) or "otlp"
#   OTEL_EXPORTER_ENDPOINT  — gRPC endpoint (e.g. "jaeger:4317")
#   OTEL_SERVICE_NAME       — service name (default: "ahmedetap")
#   OTEL_SERVICE_VERSION    — version label (default: "1.0.0")
#   OTEL_ENVIRONMENT        — deployment env (default: "development")


_otel_exporter_type = _os.environ.get("OTEL_EXPORTER_TYPE", "").lower()
if _otel_exporter_type:
    _otel_endpoint = _os.environ.get("OTEL_EXPORTER_ENDPOINT", None)
    _otel_svc = _os.environ.get("OTEL_SERVICE_NAME", "ahmedetap")
    _otel_ver = _os.environ.get("OTEL_SERVICE_VERSION", "1.0.0")
    _otel_env = _os.environ.get("OTEL_ENVIRONMENT", "development")
    setup_tracing(
        service_name=_otel_svc,
        service_version=_otel_ver,
        exporter_type=_otel_exporter_type,
        otlp_endpoint=_otel_endpoint,
        environment=_otel_env,
    )


def get_tracer() -> trace.Tracer:
    """Return the global tracer, creating a no-op fallback if uninitialised."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("ahmedetap")
    return _tracer


# ---------------------------------------------------------------------------
# Span creation helpers
# ---------------------------------------------------------------------------


def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> trace.Span:
    """Create and start a standalone span (caller must end it)."""
    tracer = get_tracer()
    return tracer.start_span(name, kind=kind, attributes=attributes or {})


def trace_operation(
    operation_name: str,
    attributes: dict[str, Any] | None = None,
    record_exception: bool = True,
) -> Callable:
    """Decorator: wrap a function in an active span.

    Works transparently with both sync and async functions.

    Usage::

        @trace_operation("load_skill", attributes={"source": "local"})
        def load_skill(path: str) -> SkillDefinition:
            ...

        @trace_operation("agent_execute", attributes={"component": "orchestrator"})
        async def execute(self, task: EngineeringTask) -> AgentResult:
            ...
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    operation_name,
                    kind=SpanKind.INTERNAL,
                    attributes=attributes or {},
                ) as span:
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as exc:
                        if record_exception:
                            span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(
                operation_name,
                kind=SpanKind.INTERNAL,
                attributes=attributes or {},
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    if record_exception:
                        span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Context propagation
# ---------------------------------------------------------------------------


def inject_context(carrier: dict[str, str]) -> None:
    """Inject the current trace context into an arbitrary carrier dict.

    Useful for propagating trace context across HTTP boundaries::

        headers: Dict[str, str] = {}
        inject_context(headers)
        requests.get(url, headers=headers)
    """
    _propagator.inject(carrier)


def extract_context(carrier: dict[str, str]) -> Context:
    """Extract remote trace context from an arbitrary carrier dict."""
    return _propagator.extract(carrier)


def inject_traceparent() -> dict[str, str]:
    """Convenience: build a dict with the W3C ``traceparent`` header."""
    carrier: dict[str, str] = {}
    inject_context(carrier)
    return carrier
