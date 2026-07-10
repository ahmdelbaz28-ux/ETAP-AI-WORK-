"""Tracing — request-scoped spans with trace context propagation.

Design:
    * ``TraceContext`` carries trace_id, span_id, parent_span_id, and a sampled flag.
    * ``Span`` represents a unit of work with start/end times, tags, and events.
    * ``Tracer`` is the abstract interface; ``InMemoryTracer`` and ``JsonTracer``
      are concrete implementations.
    * ``NullTracer`` is a no-op tracer for when tracing is disabled.

Trace context is propagated via the ``trace_id`` field in ACP envelopes. The
router extracts the trace_id and passes it to the runtime, which creates a span.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

__all__ = [
    "TraceContext",
    "Span",
    "SpanStatus",
    "Tracer",
    "InMemoryTracer",
    "JsonTracer",
    "NullTracer",
]


# ------------------------------------------------------------------ TraceContext


@dataclass(frozen=True)
class TraceContext:
    """Immutable trace context that propagates across layers.

    Fields:
        trace_id: the root trace identifier (e.g. UUID, ULID).
        span_id: the current span identifier.
        parent_span_id: the parent span identifier (empty if root).
        sampled: whether this trace should be recorded.
    """

    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    sampled: bool = True

    def with_span(self, span_id: str) -> TraceContext:
        """Return a new context with the given span_id and this span as parent."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=self.span_id,
            sampled=self.sampled,
        )

    @classmethod
    def from_trace_id(cls, trace_id: str) -> TraceContext:
        """Create a root context from a trace_id string."""
        return cls(trace_id=trace_id, span_id=trace_id, sampled=True)


# ------------------------------------------------------------------ Span


@dataclass(frozen=True)
class Span:
    """An immutable record of a completed span.

    Fields:
        name: span name (e.g. "capability.execute", "router.handle").
        trace_id: root trace id.
        span_id: unique span id.
        parent_span_id: parent span id (empty if root).
        start_time: Unix epoch seconds (float).
        end_time: Unix epoch seconds (float).
        status: one of "ok", "error", "cancelled".
        tags: free-form key-value pairs.
        events: list of (timestamp, name, attrs) tuples.
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str
    start_time: float
    end_time: float
    status: str = "ok"
    tags: dict[str, Any] = field(default_factory=dict)
    events: list[tuple[float, str, dict[str, Any]]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    def to_json(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration_ms": self.duration_ms,
                "status": self.status,
                "tags": self.tags,
                "events": self.events,
            },
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        )


class SpanStatus:
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


# ------------------------------------------------------------------ Tracer (ABC)


class Tracer:
    """Abstract tracer interface.

    Subclasses must implement ``start_span``, ``finish_span``, and ``record_span``.
    """

    def start_span(self, _name: str, context: Optional[TraceContext] = None) -> TraceContext:
        """Start a new span and return its context.

        The default implementation generates a span_id, creates a child
        context, and returns it. Subclasses may override to record the
        start time.
        """
        span_id = self._generate_span_id()
        if context is None:
            context = TraceContext.from_trace_id(span_id)
        return context.with_span(span_id)

    def finish_span(
        self,
        context: TraceContext,
        name: str,
        start_time: float,
        status: str = SpanStatus.OK,
        tags: dict[str, Any] | None = None,
        events: list[tuple[float, str, dict[str, Any]]] | None = None,
    ) -> None:
        """Finish a span and record it."""
        span = Span(
            name=name,
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
            start_time=start_time,
            end_time=time.time(),
            status=status,
            tags=tags or {},
            events=events or [],
        )
        self.record_span(span)

    def record_span(self, span: Span) -> None:
        """Record a completed span. Must be implemented by subclasses."""
        raise NotImplementedError

    @staticmethod
    def _generate_span_id() -> str:
        """Generate a short unique span id."""
        import random

        return f"{random.getrandbits(64):016x}"  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)


# ------------------------------------------------------------------ NullTracer


class NullTracer(Tracer):
    """No-op tracer."""

    def record_span(self, span: Span) -> None:
        pass  # NOSONAR — S1186: intentional no-op (Null Object pattern)


# ------------------------------------------------------------------ InMemoryTracer


class InMemoryTracer(Tracer):
    """Stores all spans in a list for testing.

    Thread-safe: uses a ``threading.Lock``.
    """

    def __init__(self) -> None:
        self._spans: list[Span] = []
        self._lock = threading.Lock()

    def record_span(self, span: Span) -> None:
        with self._lock:
            self._spans.append(span)

    @property
    def spans(self) -> list[Span]:
        return list(self._spans)

    def clear(self) -> None:
        self._spans.clear()

    def spans_for_trace(self, trace_id: str) -> list[Span]:
        return [s for s in self._spans if s.trace_id == trace_id]


# ------------------------------------------------------------------ JsonTracer


class JsonTracer(Tracer):
    """Append-only JSON line tracer to a file.

    Parameters:
        path: file path for the span output.
        encoding: file encoding (default "utf-8").
    """

    def __init__(self, path: Union[str, Path], encoding: str = "utf-8") -> None:
        self._path = Path(path)
        self._encoding = encoding
        self._lock = threading.Lock()

    def record_span(self, span: Span) -> None:
        with self._lock:
            line = span.to_json() + "\n"
            self._append_line(line)

    def _append_line(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding=self._encoding) as f:
            f.write(line)
