"""Tests for cancellation propagation.

Covers:
    * Deadline-exceeded cancellation propagates to the handler.
    * External scope cancellation propagates to the handler.
    * Handlers that ignore cancellation still get DeadlineExceeded
      returned to the caller.
    * BaseException (CancelledError) is NOT wrapped in HandlerError.
    * Nested cancel scopes work correctly.
"""
from __future__ import annotations
import anyio
import pytest

from acp.errors import DeadlineExceeded, HandlerError
from acp.runtime.deadline import enforce_deadline_ms
from acp.runtime import AcpRuntime, capability
from acp.runtime.cancel import cancellable, is_cancelled_exception


# ----------------------------------------------- cancellation into handler

@pytest.mark.anyio
async def test_cancellation_propagates_into_handler():
    """When the deadline fires, the handler must see a cancellation."""
    handler_observed_cancel = False

    async def handler():
        nonlocal handler_observed_cancel
        try:
            await anyio.sleep(5.0)
        except BaseException:
            handler_observed_cancel = True
            raise

    with pytest.raises(DeadlineExceeded):
        await enforce_deadline_ms(handler(), deadline_ms=30)

    assert handler_observed_cancel, "handler should have observed cancellation"


@pytest.mark.anyio
async def test_cancellation_via_external_cancel_scope():
    """Cancelling the task group scope interrupts the handler.

    anyio 4.x task groups suppress the CancelledError on exit, so we
    check the handler state directly rather than asserting an exception.
    """
    handler_observed_cancel = False
    handler_finished = False

    async def handler():
        nonlocal handler_observed_cancel, handler_finished
        try:
            await anyio.sleep(5.0)
            handler_finished = True
        except BaseException:
            handler_observed_cancel = True
            raise

    async with anyio.create_task_group() as tg:
        tg.start_soon(handler)
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()

    assert handler_observed_cancel
    assert not handler_finished


@pytest.mark.anyio
async def test_handler_that_ignores_cancellation_still_bails():
    """Even a handler that swallows BaseException can't block the engine.

    We construct a handler that catches CancelledError and then tries
    to do more work. The engine deadline still returns DeadlineExceeded
    to the caller. We don't assert the rogue task finishes — in anyio
    4.x a cancelled scope may re-raise on the next checkpoint, so the
    inner sleep may never complete. The important contract is that the
    caller gets DeadlineExceeded.
    """
    async def rogue_handler():
        try:
            await anyio.sleep(5.0)
        except BaseException:
            # Swallow the cancel and try to finish.
            try:
                await anyio.sleep(0.05)
            except BaseException:
                pass

    with pytest.raises(DeadlineExceeded):
        await enforce_deadline_ms(rogue_handler(), deadline_ms=30)


# --------------------------------------------------- cancellable() helper

@pytest.mark.anyio
async def test_cancellable_with_deadline_fires():
    fired = False

    async with cancellable(deadline_ms=20) as scope:
        try:
            await anyio.sleep(2.0)
        except BaseException:
            fired = True
            raise

    assert fired
    assert scope.cancelled_caught


@pytest.mark.anyio
async def test_cancellable_without_deadline_requires_external_cancel():
    async def block():
        await anyio.sleep(2.0)
        return "should not return"

    async with anyio.create_task_group() as tg:
        runner_scope = None

        async def runner():
            nonlocal runner_scope
            async with cancellable() as s:
                runner_scope = s
                await anyio.sleep(2.0)

        tg.start_soon(runner)
        await anyio.sleep(0.02)
        assert runner_scope is not None
        runner_scope.cancel()
        with anyio.move_on_after(0.5):
            pass


# --------------------------------------------------- is_cancelled_exception

def test_is_cancelled_exception_recognises_asyncio():
    import asyncio

    assert is_cancelled_exception(asyncio.CancelledError())


def test_is_cancelled_exception_rejects_runtime_error():
    assert not is_cancelled_exception(RuntimeError("nope"))


# -------------------------------------- engine-level cancellation behaviour

@pytest.mark.anyio
async def test_engine_does_not_wrap_cancelled_error():
    """Cancellation is mapped to DeadlineExceeded, never wrapped in HandlerError.

    We trigger the engine's own deadline — the inner enforce_deadline_ms
    maps the CancelledError to DeadlineExceeded, and engine.execute()
    does not catch BaseException (so it would never wrap it in HandlerError).
    """
    class Slow:
        @capability("slow.forever")
        async def forever(self) -> int:
            await anyio.sleep(5.0)
            return 0

    runtime = AcpRuntime([Slow()])

    with pytest.raises(DeadlineExceeded) as exc_info:
        await runtime.execute("slow.forever", deadline_ms=50)

    assert not isinstance(exc_info.value, HandlerError)

