"""Deadline enforcement — wraps a coroutine with a hard timeout.

Built on ``anyio.move_on_after`` so it works on both asyncio and trio.
Cancellation is propagated into the wrapped coroutine; if the handler
ignores the cancellation, the function still returns ``DeadlineExceeded``
to the caller (best-effort cancel).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio

from acp.errors import DeadlineExceeded

__all__ = ["enforce_deadline_ms", "deadline_scope"]


async def enforce_deadline_ms(coro: Any, deadline_ms: int) -> Any:
    """Await ``coro`` with a hard deadline of ``deadline_ms`` milliseconds.

    Args:
        coro: an awaitable (typically a coroutine object from calling
            an async function).
        deadline_ms: timeout in milliseconds. Must be > 0.

    Returns:
        The result of awaiting ``coro`` if it completes in time.

    Raises:
        ValueError: if ``deadline_ms`` is non-positive.
        DeadlineExceeded: if the deadline elapses.
    """
    if deadline_ms <= 0:
        raise ValueError("deadline_ms must be > 0")
    if deadline_ms > 10 * 60 * 1000:  # 10 minutes — sanity guard
        raise ValueError("deadline_ms must be <= 600000 (10 minutes)")

    seconds = deadline_ms / 1000.0
    with anyio.move_on_after(seconds) as scope:
        result = await coro
        if not scope.cancel_called:
            return result

    if scope.cancelled_caught:
        raise DeadlineExceeded(
            f"Execution exceeded deadline of {deadline_ms}ms",
            data={"deadline_ms": deadline_ms, "elapsed_seconds": seconds},
        )

    # Defensive: if move_on_after exited for any other reason.
    raise DeadlineExceeded(
        f"Execution did not complete within {deadline_ms}ms",
        data={"deadline_ms": deadline_ms},
    )


@asynccontextmanager
async def deadline_scope(deadline_ms: int) -> AsyncIterator[anyio.CancelScope]:
    """Yield a cancel scope that triggers after ``deadline_ms``.

    Lower-level primitive for callers that want to manage the scope
    themselves. Caller checks ``scope.cancelled_caught`` after the block.
    """
    if deadline_ms <= 0:
        raise ValueError("deadline_ms must be > 0")
    with anyio.move_on_after(deadline_ms / 1000.0) as scope:
        yield scope
