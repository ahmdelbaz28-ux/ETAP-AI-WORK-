"""Tests for ``AcpRuntime`` — the composition root of the runtime layer.

Covers:
    * successful execution (sync + async handlers)
    * handler exceptions → HandlerError
    * unknown capability → CapabilityNotFound
    * deadline enforced through the engine
    * duplicate capability registration is a constructor error
    * stats tracking
"""
from __future__ import annotations
import anyio
import pytest

from acp.errors import (
    AcpError,
    CapabilityNotFound,
    DeadlineExceeded,
    HandlerError,
)
from acp.runtime import AcpRuntime, capability


class CalcHandler:
    @capability("calc.add", scopes=("calc.write",))
    async def add(self, a: int, b: int) -> int:
        await anyio.sleep(0.001)
        return a + b

    @capability("calc.div", scopes=("calc.read",))
    def div(self, a: int, b: int) -> float:
        return a / b

    @capability("calc.boom", scopes=())
    async def boom(self) -> None:
        raise ValueError("intentional handler failure")

    @capability("calc.slow", scopes=())
    async def slow(self) -> int:
        await anyio.sleep(2.0)
        return 42


# ----------------------------------------------------------------- success

@pytest.mark.anyio
async def test_execute_async_handler():
    runtime = AcpRuntime([CalcHandler()])
    result = await runtime.execute("calc.add", {"a": 2, "b": 3}, deadline_ms=1000)
    assert result == 5


@pytest.mark.anyio
async def test_execute_sync_handler():
    runtime = AcpRuntime([CalcHandler()])
    result = await runtime.execute("calc.div", {"a": 10, "b": 2}, deadline_ms=1000)
    assert result == 5.0


@pytest.mark.anyio
async def test_execute_with_no_input():
    class H:
        @capability("ping.now")
        async def now(self) -> str:
            return "pong"

    runtime = AcpRuntime([H()])
    assert await runtime.execute("ping.now") == "pong"


# ------------------------------------------------------------- error paths

@pytest.mark.anyio
async def test_unknown_capability_raises_capability_not_found():
    runtime = AcpRuntime([CalcHandler()])
    with pytest.raises(CapabilityNotFound) as exc_info:
        await runtime.execute("does.not.exist", deadline_ms=1000)

    assert exc_info.value.code == -32002
    assert exc_info.value.data["capability"] == "does.not.exist"
    assert "calc.add" in exc_info.value.data["available"]


@pytest.mark.anyio
async def test_handler_exception_wrapped_in_handler_error():
    runtime = AcpRuntime([CalcHandler()])
    with pytest.raises(HandlerError) as exc_info:
        await runtime.execute("calc.boom", deadline_ms=1000)

    assert exc_info.value.code == -32004
    assert exc_info.value.data["exception_type"] == "ValueError"
    assert "intentional" in str(exc_info.value)
    # __cause__ preserved for debugging
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.anyio
async def test_handler_deadline_enforced():
    runtime = AcpRuntime([CalcHandler()])
    with pytest.raises(DeadlineExceeded) as exc_info:
        await runtime.execute("calc.slow", deadline_ms=50)

    assert exc_info.value.code == -32001
    assert exc_info.value.data["deadline_ms"] == 50


@pytest.mark.anyio
async def test_handler_does_not_observe_cancellation_on_success():
    """A handler that finishes before the deadline returns normally."""
    runtime = AcpRuntime([CalcHandler()])
    result = await runtime.execute("calc.add", {"a": 1, "b": 1}, deadline_ms=1000)
    assert result == 2


# ------------------------------------------------------------ registration

def test_duplicate_capability_raises_on_construct():
    class H1:
        @capability("dup.x")
        async def x(self) -> int:
            return 1

    class H2:
        @capability("dup.x")  # same name
        async def x(self) -> int:
            return 2

    with pytest.raises(ValueError) as exc_info:
        AcpRuntime([H1(), H2()])
    assert "Duplicate capability" in str(exc_info.value)
    assert "'dup.x'" in str(exc_info.value)


def test_capability_names_sorted():
    class H:
        @capability("z.last")
        async def z_last(self) -> int:
            return 0

        @capability("a.first")
        async def a_first(self) -> int:
            return 0

    runtime = AcpRuntime([H()])
    assert runtime.capability_names == ["a.first", "z.last"]


def test_get_meta_returns_metadata():
    runtime = AcpRuntime([CalcHandler()])
    meta = runtime.get_meta("calc.add")
    assert meta is not None
    assert meta.scopes == ("calc.write",)

    assert runtime.get_meta("does.not.exist") is None


# ----------------------------------------------------------------- stats

@pytest.mark.anyio
async def test_stats_track_calls_and_errors():
    runtime = AcpRuntime([CalcHandler()])

    # 2 successes
    await runtime.execute("calc.add", {"a": 1, "b": 1})
    await runtime.execute("calc.add", {"a": 2, "b": 2})

    # 1 error (handler raised)
    with pytest.raises(HandlerError):
        await runtime.execute("calc.boom")

    # 1 error (deadline)
    with pytest.raises(DeadlineExceeded):
        await runtime.execute("calc.slow", deadline_ms=10)

    stats = runtime.stats
    assert stats["calc.add"]["calls"] == 2
    assert stats["calc.add"]["errors"] == 0
    assert stats["calc.boom"]["calls"] == 1
    assert stats["calc.boom"]["errors"] == 1
    assert stats["calc.slow"]["calls"] == 1
    assert stats["calc.slow"]["errors"] == 1


@pytest.mark.anyio
async def test_unknown_capability_does_not_increment_stats():
    runtime = AcpRuntime([CalcHandler()])
    with pytest.raises(CapabilityNotFound):
        await runtime.execute("nope")
    # calc.* should still show zero calls
    assert all(s["calls"] == 0 for s in runtime.stats.values())


# ------------------------------------------------ multi-handler registration

@pytest.mark.anyio
async def test_multiple_handlers_in_one_runtime():
    class StringHandler:
        @capability("text.echo")
        async def echo(self, msg: str) -> str:
            return msg

    runtime = AcpRuntime([CalcHandler(), StringHandler()])
    assert set(runtime.capability_names) == {
        "calc.add",
        "calc.div",
        "calc.boom",
        "calc.slow",
        "text.echo",
    }
    assert await runtime.execute("text.echo", {"msg": "hi"}, deadline_ms=1000) == "hi"
    assert await runtime.execute("calc.add", {"a": 10, "b": 20}, deadline_ms=1000) == 30


# ------------------------------------------------ error mapping is preserving

@pytest.mark.anyio
async def test_handler_error_preserves_cause():
    class CustomError(RuntimeError):
        pass

    class H:
        @capability("raise.custom")
        async def go(self) -> None:
            raise CustomError("nope")

    runtime = AcpRuntime([H()])
    with pytest.raises(HandlerError) as exc_info:
        await runtime.execute("raise.custom")
    assert isinstance(exc_info.value.__cause__, CustomError)
    assert exc_info.value.data["exception_type"] == "CustomError"
