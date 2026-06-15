"""acp.observability — Tracing, metrics, and structured logging.

The observability layer provides three complementary signals:

    * **Tracing** — request-scoped spans with parent-child relationships
    * **Metrics** — counters, histograms, and gauges for quantifiable data
    * **Structured Logging** — contextual JSON log entries

All components are async-safe and designed to be lightweight. They can be
used standalone or wired into the Runtime, Router, and Transport layers.

Typical usage::

    from acp.observability import MetricsRegistry, Tracer, StructuredLogger
    from acp.observability import InMemoryMetricsRegistry, InMemoryTracer, InMemoryStructuredLogger

    metrics = InMemoryMetricsRegistry()
    tracer = InMemoryTracer()
    logger = InMemoryStructuredLogger()

    runtime = AcpRuntime([handlers])
    router = Router(runtime, RouterConfig())
    server = Server(router, transport)

    # Wire observability
    runtime.set_metrics(metrics)
    runtime.set_tracer(tracer)
    runtime.set_logger(logger)
"""
from __future__ import annotations

from acp.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    InMemoryMetricsRegistry,
    MetricsRegistry,
)
from acp.observability.structured_logger import (
    ConsoleStructuredLogger,
    InMemoryStructuredLogger,
    LogEntry,
    LogLevel,
    NullStructuredLogger,
    StructuredLogger,
)
from acp.observability.tracer import (
    InMemoryTracer,
    JsonTracer,
    NullTracer,
    Span,
    SpanStatus,
    TraceContext,
    Tracer,
)

__all__ = [
    # tracing
    "TraceContext",
    "Span",
    "SpanStatus",
    "Tracer",
    "InMemoryTracer",
    "JsonTracer",
    "NullTracer",
    # metrics
    "Counter",
    "Histogram",
    "Gauge",
    "MetricsRegistry",
    "InMemoryMetricsRegistry",
    # structured logging
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "ConsoleStructuredLogger",
    "InMemoryStructuredLogger",
    "NullStructuredLogger",
]
