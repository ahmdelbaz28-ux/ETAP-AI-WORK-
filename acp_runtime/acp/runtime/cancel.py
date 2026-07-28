"""Cancellation helpers.

Thin wrappers over ``anyio.CancelScope``. Most uses are covered by
``enforce_deadline_ms`` (which uses ``move_on_after`` internally);
this module provides a slightly higher-level surface for callers that
need an explicit, externally-cancellable scope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

import anyio

__all__ = ["cancellable", "is_cancelled_exception"]


@asynccontextmanager
async def cancellable(
    deadline_ms: Optional[int] = None,
) -> AsyncIterator[anyio.CancelScope]:
    """A cancel scope with an optional deadline.

    Usage::

        async with cancellable(deadline_ms=5000) as scope:
            await long_running()
            if scope.cancelled_caught:
                # we either ran out of time or someone cancelled us
                ...

    To cancel from elsewhere, hold a reference to the scope and call
    ``scope.cancel()``. (For typical request/response flows the
    engine-level deadline is sufficient.)
    """
    if deadline_ms is not None:
        if deadline_ms <= 0:
            raise ValueError("deadline_ms must be > 0")
        with anyio.move_on_after(deadline_ms / 1000.0) as scope:
            yield scope
    else:
        with anyio.CancelScope() as scope:
            yield scope


def is_cancelled_exception(exc: BaseException) -> bool:
    """Return True if ``exc`` is a cancellation for the current anyio backend."""
    import asyncio

    if isinstance(exc, asyncio.CancelledError):
        return True
    try:
        cls = anyio.get_cancelled_exc_class()
    except Exception:
        return False
    return isinstance(exc, cls)
