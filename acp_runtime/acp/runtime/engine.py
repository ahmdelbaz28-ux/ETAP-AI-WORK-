"""AcpRuntime — the main async execution engine.

Responsibilities:
    * Build a frozen capability registry from a list of handlers.
    * Dispatch an incoming request to the right method.
    * Wrap every handler call in a deadline-enforced cancel scope.
    * Map handler exceptions to ACP errors (DeadlineExceeded is
      re-raised, everything else becomes HandlerError).
    * Track metrics (call count, error count, per-capability).

Out of scope (handled by other layers):
    * JSON-RPC parsing  — Router layer
    * Auth / scope check — Security layer
    * Transport I/O     — Transport layer
"""

from __future__ import annotations

import inspect
import logging
import time
from collections import defaultdict
from collections.abc import Iterable
from functools import partial
from typing import Any

import anyio

from acp.errors import (
    CapabilityNotFound,
    DeadlineExceeded,
    HandlerError,
    ScopeNotPermitted,
)
from acp.runtime.deadline import enforce_deadline_ms
from acp.runtime.handler import CapabilityMeta, discover_capabilities

__all__ = ["AcpRuntime"]

# Observability imports (optional, lazy to avoid circular deps)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AcpRuntime:
    """Async execution engine for capabilities.

    Parameters:
        handlers: iterable of objects that carry @capability methods.

    Raises:
        ValueError: if two handlers expose the same capability name.
    """

    def __init__(
        self,
        handlers: Iterable[Any],
        *,
        tracer: Any | None = None,
        metrics: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        self._handlers: list[Any] = list(handlers)
        self._registry: dict[str, tuple[Any, CapabilityMeta]] = {}
        self._call_count: dict[str, int] = defaultdict(int)
        self._error_count: dict[str, int] = defaultdict(int)
        self._log = logging.getLogger("acp.runtime")
        self._tracer = tracer
        self._metrics = metrics
        self._logger = logger
        self._build_registry()

    # --------------------------------------------------------------- registry

    def _build_registry(self) -> None:
        for handler in self._handlers:
            class_name = type(handler).__name__
            for cap_name, meta in discover_capabilities(handler).items():
                if cap_name in self._registry:
                    raise ValueError(
                        f"Duplicate capability {cap_name!r}: "
                        f"registered on {self._registry[cap_name][0]!r}, "
                        f"also exposed by {class_name!r}",
                    )
                getattr(handler, meta.method_name)
                self._registry[cap_name] = (handler, meta)
        self._log.debug("acp runtime registry built: %d capabilities", len(self._registry))

    @property
    def capability_names(self) -> list[str]:
        """Sorted list of all registered capability names."""
        return sorted(self._registry.keys())

    def get_meta(self, name: str) -> CapabilityMeta | None:
        """Return the metadata for a capability, or None if not registered."""
        entry = self._registry.get(name)
        return entry[1] if entry is not None else None

    # -------------------------------------------------------------- execution

    async def execute(
        self,
        capability: str,
        input: dict[str, Any] | None = None,
        *,
        trace_id: str = "",
        deadline_ms: int = 30_000,
    ) -> Any:
        """Dispatch a request to the named capability.

        Args:
            capability: the registered name of the capability to invoke.
            input: keyword arguments to pass to the underlying method.
                Defaults to ``{}``.
            trace_id: opaque correlation id; included in error metadata.
            deadline_ms: hard timeout. Defaults to 30 s.

        Returns:
            Whatever the handler method returns.

        Raises:
            CapabilityNotFound: ``capability`` is not in the registry.
            ScopeNotPermitted: (reserved — actual scope check is the
                router's job, but we re-raise it if a handler does it
                itself).
            DeadlineExceeded: the handler exceeded the deadline.
            HandlerError: the handler raised any other exception.
        """
        entry = self._registry.get(capability)
        if entry is None:
            raise CapabilityNotFound(
                f"Capability {capability!r} is not registered",
                data={
                    "capability": capability,
                    "available": self.capability_names,
                    "trace_id": trace_id,
                },
            )

        handler, meta = entry
        call_kwargs = dict(input or {})
        self._call_count[capability] += 1

        self._log.debug(
            "execute capability=%s trace=%s deadline_ms=%d kwargs_keys=%s",
            capability,
            trace_id,
            deadline_ms,
            sorted(call_kwargs.keys()),
        )

        # Observability: start span
        t0 = time.time()
        span_ctx = None
        if self._tracer is not None:
            from acp.observability.tracer import TraceContext

            span_ctx = self._tracer.start_span(
                "capability.execute",
                TraceContext.from_trace_id(trace_id) if trace_id else None,
            )

        try:
            method = handler.__getattribute__(meta.method_name)
            raw = getattr(method, "__func__", method)
            if inspect.iscoroutinefunction(raw):
                coro = method(**call_kwargs)
            else:
                # Run sync handlers in a thread so they don't block the loop.
                coro = anyio.to_thread.run_sync(partial(method, **call_kwargs))
            result = await enforce_deadline_ms(coro, deadline_ms)
            # Observability: record success
            self._record_metrics(capability, True, (time.time() - t0) * 1000)
            if self._tracer is not None and span_ctx is not None:
                self._tracer.finish_span(
                    span_ctx,
                    "capability.execute",
                    t0,
                    tags={"capability": capability, "trace_id": trace_id},
                )
            return result
        except (DeadlineExceeded, CapabilityNotFound, ScopeNotPermitted):
            # ACP control errors pass through unchanged.
            self._error_count[capability] += 1
            self._record_metrics(capability, False, (time.time() - t0) * 1000)
            if self._tracer is not None and span_ctx is not None:
                from acp.observability.tracer import SpanStatus

                self._tracer.finish_span(
                    span_ctx,
                    "capability.execute",
                    t0,
                    status=SpanStatus.ERROR,
                    tags={"capability": capability, "trace_id": trace_id, "error": "control"},
                )
            raise
        except Exception as e:
            # Any other exception becomes HandlerError; we preserve the
            # cause for debugging. CancelledError (asyncio.CancelledError
            # or trio.Cancelled) is a BaseException, not Exception, so
            # it's NOT caught here — it propagates.
            self._error_count[capability] += 1
            self._record_metrics(capability, False, (time.time() - t0) * 1000)
            if self._tracer is not None and span_ctx is not None:
                from acp.observability.tracer import SpanStatus

                self._tracer.finish_span(
                    span_ctx,
                    "capability.execute",
                    t0,
                    status=SpanStatus.ERROR,
                    tags={
                        "capability": capability,
                        "trace_id": trace_id,
                        "error": type(e).__name__,
                    },
                )
            raise HandlerError(
                f"Handler for {capability!r} raised {type(e).__name__}: {e}",
                data={
                    "capability": capability,
                    "trace_id": trace_id,
                    "exception_type": type(e).__name__,
                },
            ) from e

    def _record_metrics(self, capability: str, success: bool, duration_ms: float) -> None:
        """Record execution metrics if a metrics registry is configured."""
        if self._metrics is None:
            return
        self._metrics.get_or_create_counter(
            "acp.runtime.calls.total", "Total capability calls",
        ).inc()
        self._metrics.get_or_create_histogram(
            "acp.runtime.calls.duration_ms",
            "Capability call duration in milliseconds",
        ).observe(duration_ms)
        if not success:
            self._metrics.get_or_create_counter(
                "acp.runtime.calls.errors", "Total capability errors",
            ).inc()
        self._metrics.get_or_create_counter(
            f"acp.runtime.calls.per_capability.{capability}",
            f"Calls for {capability}",
        ).inc()

    # ---------------------------------------------------------------- metrics

    @property
    def handler_count(self) -> int:
        """Number of handler objects registered in the runtime."""
        return len(self._handlers)

    @property
    def stats(self) -> dict[str, dict[str, int]]:
        """Per-capability call + error counts (snapshot)."""
        return {
            cap: {"calls": self._call_count[cap], "errors": self._error_count[cap]}
            for cap in self.capability_names
        }
