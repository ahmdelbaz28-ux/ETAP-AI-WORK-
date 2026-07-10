"""ProgressEmitter — fire-and-forget progress notifications.

Handlers that do long-running work can call ``emitter.emit(...)`` to
push a progress event to the connected transport. The emitter is safe
to call from inside an awaited coroutine; emissions are not awaited on
the caller's hot path beyond the (very fast) ``send`` callback.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

__all__ = ["ProgressEmitter", "ProgressEvent"]


@dataclass(frozen=True)
class ProgressEvent:
    trace_id: str
    percent: int
    stage: str
    message: str = ""
    ts: float = field(default_factory=time.time)

    def to_envelope(self) -> dict:
        return {
            "jsonrpc": "2.0",
            "method": "progress.update",
            "params": {
                "trace_id": self.trace_id,
                "stage": self.stage,
                "percent": int(self.percent),
                "message": self.message,
                "ts": self.ts,
            },
        }

    @classmethod
    def from_envelope(cls, env: dict) -> ProgressEvent:
        p = env.get("params", {})
        return cls(
            trace_id=p.get("trace_id", ""),
            percent=int(p.get("percent", 0)),
            stage=p.get("stage", ""),
            message=p.get("message", ""),
            ts=float(p.get("ts", time.time())),
        )


# Type alias for the transport-side sink. A transport provides an
# ``async def send(envelope)`` that ships the notification.
ProgressSink = Callable[[dict], Awaitable[None]]


class ProgressEmitter:
    """Emit progress notifications during a handler invocation.

    The emitter is constructed per request and passed into the handler
    (typically as a keyword argument named ``progress``). Handlers
    that don't care about progress simply ignore it.

    If no ``send`` callback is wired (e.g. in-process calls), events
    are buffered on the emitter and accessible via ``.events``.
    """

    def __init__(
        self,
        trace_id: str,
        send: Optional[ProgressSink] = None,
        *,
        on_drop: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        self._trace_id = trace_id
        self._send = send
        self._on_drop = on_drop
        self._events: list[ProgressEvent] = []

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def events(self) -> list[ProgressEvent]:
        """Snapshot of buffered events (empty if a transport is wired)."""
        return list(self._events)

    async def emit(self, percent: int, stage: str, message: str = "") -> None:
        """Record and (optionally) ship one progress event.

        ``percent`` is clamped to [0, 100]. Non-blocking from the
        caller's point of view: the sink is awaited, but the typical
        sink is a non-blocking enqueue.
        """
        if not 0 <= percent <= 100:
            raise ValueError(f"percent must be in [0,100], got {percent!r}")
        event = ProgressEvent(
            trace_id=self._trace_id,
            percent=percent,
            stage=stage,
            message=message,
        )
        if self._send is None:
            self._events.append(event)
            return
        try:
            await self._send(event.to_envelope())
        except Exception:
            # Progress is best-effort: never break the handler over a
            # failed notification. Optionally notify a drop observer.
            if self._on_drop is not None:
                with contextlib.suppress(Exception):
                    self._on_drop(event)
