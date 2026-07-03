"""Tests for ``acp.runtime.deadline.enforce_deadline_ms``.

Covers:
    * completes within deadline → returns result
    * exceeds deadline → raises DeadlineExceeded
    * deadline_ms <= 0 → ValueError
    * deadline_ms > 10 minutes → ValueError (sanity)
"""

from __future__ import annotations

import time

import anyio
import pytest
from acp.errors import DeadlineExceeded
from acp.runtime.deadline import deadline_scope, enforce_deadline_ms


@pytest.mark.anyio
async def test_completes_within_deadline():
    async def quick() -> str:
        await anyio.sleep(0.001)
        return "done"

    result = await enforce_deadline_ms(quick(), 1000)
    assert result == "done"


@pytest.mark.anyio
async def test_exceeds_deadline_raises():
    async def slow() -> str:
        await anyio.sleep(2.0)
        return "should not get here"

    started = time.monotonic()
    with pytest.raises(DeadlineExceeded) as exc_info:  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
        await enforce_deadline_ms(slow(), 50)
    elapsed_ms = (time.monotonic() - started) * 1000

    assert exc_info.value.code == -32001
    assert exc_info.value.data["deadline_ms"] == 50
    # Should bail out well before the 2s sleep.
    assert elapsed_ms < 500, f"deadline took too long to fire: {elapsed_ms:.1f}ms"


@pytest.mark.anyio
async def test_deadline_data_carries_deadline_ms():
    async def slow() -> None:
        await anyio.sleep(2.0)

    with pytest.raises(DeadlineExceeded) as exc_info:  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
        await enforce_deadline_ms(slow(), 25)
    assert exc_info.value.data["deadline_ms"] == 25


def test_zero_deadline_raises():
    async def noop() -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        return None

    with pytest.raises(ValueError):
        anyio.run(lambda: enforce_deadline_ms(noop(), 0))


def test_negative_deadline_raises():
    async def noop() -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        return None

    with pytest.raises(ValueError):
        anyio.run(lambda: enforce_deadline_ms(noop(), -100))


def test_excessive_deadline_raises():
    async def noop() -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        return None

    with pytest.raises(ValueError):
        anyio.run(lambda: enforce_deadline_ms(noop(), 10 * 60 * 1000 + 1))


@pytest.mark.anyio
async def test_deadline_scope_yields_cancellable_scope():
    fired = False

    async def worker() -> None:
        nonlocal fired
        try:
            await anyio.sleep(2.0)
        except BaseException:
            fired = True
            raise

    async with deadline_scope(20) as scope:
        await worker()
    assert scope.cancelled_caught
    assert fired, "worker should have observed cancellation"
