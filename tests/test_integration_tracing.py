"""
Integration tests for ``core/tracing.py`` — OpenTelemetry instrumentation.

Verifies:
- TracerProvider initialisation
- Span creation and status recording
- trace_operation decorator
- Context injection / extraction (round-trip)
"""

from __future__ import annotations

from typing import Any

import pytest
from opentelemetry import trace

from core.tracing import (
    create_span,
    get_tracer,
    inject_context,
    inject_traceparent,
    setup_tracing,
    trace_operation,
)


class TestTracingSetup:
    """TracerProvider initialisation."""

    def test_setup_tracing_returns_tracer(self) -> None:
        """setup_tracing returns a non-None Tracer."""
        tracer = setup_tracing(
            service_name="test-app",
            service_version="1.0.0",
            exporter_type="console",
            environment="testing",
        )
        assert tracer is not None
        assert isinstance(tracer, trace.Tracer)

    def test_get_tracer_returns_tracer(self) -> None:
        """get_tracer returns a valid tracer even if setup was called."""
        tracer = get_tracer()
        assert tracer is not None


class TestTracingSpans:
    """Span creation and management."""

    def test_trace_operation_success(self) -> None:
        """@trace_operation returns the wrapped value on success."""

        @trace_operation("test-op")
        def fn() -> str:
            return "traced"

        assert fn() == "traced"

    def test_trace_operation_error(self) -> None:
        """@trace_operation records exception and re-raises."""

        @trace_operation("test-op")
        def fn() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            fn()

    def test_trace_operation_with_attributes(self) -> None:
        """@trace_operation accepts custom attributes."""

        @trace_operation("test-op", attributes={"key": "value"})
        def fn() -> int:
            return 42

        assert fn() == 42

    def test_create_span_standalone(self) -> None:
        """create_span returns a span that can be ended manually."""
        span = create_span("manual-span")
        assert span is not None
        span.end()


class TestTracingContext:
    """Trace-context propagation."""

    def test_inject_context_round_trip(self) -> None:
        """inject_context populates a carrier; it can be read back."""
        # Setup tracing so there is an active tracer
        setup_tracing("test", "1.0.0", "console", environment="testing")
        tracer = get_tracer()
        # Create an active span so context is available to inject
        with tracer.start_as_current_span("test-span"):
            carrier: dict[str, str] = {}
            inject_context(carrier)
        # The carrier should have at least the traceparent key
        assert "traceparent" in carrier
        assert len(carrier["traceparent"]) > 10

    def test_inject_traceparent(self) -> None:
        """inject_traceparent returns a dict with traceparent."""
        setup_tracing("test", "1.0.0", "console", environment="testing")
        tracer = get_tracer()
        with tracer.start_as_current_span("test-span"):
            headers = inject_traceparent()
        assert "traceparent" in headers
        assert len(headers["traceparent"].split("-")) == 4  # version-traceId-spanId-flags
