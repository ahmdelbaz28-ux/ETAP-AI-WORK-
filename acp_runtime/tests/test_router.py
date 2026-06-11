"""Tests for the router layer — JSON-RPC dispatch, scope validation, error mapping.

Covers:
    * Successful request dispatch (async + sync handlers)
    * Unknown capability → CapabilityNotFound error response
    * Missing scope → ScopeNotPermitted error response
    * Handler exception → HandlerError error response
    * Deadline exceeded → DeadlineExceeded error response
    * Invalid envelope → Invalid Request error response
    * Notification handling (no response, callback invoked)
    * Params as list rejected (ACP convention is dict kwargs)
    * Router with no scopes (public capabilities only)
    * Router with scopes (public + scoped capabilities)
    * ScopeValidator exact match, wildcard, empty set
    * Error response JSON-RPC code correctness
"""
from __future__ import annotations
import anyio
import pytest
from pydantic import ValidationError

from acp.router import Router, RouterConfig, ScopeValidator, check_scope
from acp.runtime import AcpRuntime, capability
from acp.schema import JsonRpcRequest, JsonRpcResponse, JsonRpcNotification, JsonRpcError


# ------------------------------------------------------- test handlers

class MathHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        await anyio.sleep(0.001)
        return a + b

    @capability("math.div", scopes=("math.write",))
    def div(self, a: int, b: int) -> float:
        return a / b

    @capability("math.public")
    async def identity(self, x: int) -> int:
        return x

    @capability("math.slow")
    async def slow(self) -> int:
        await anyio.sleep(5.0)
        return 42

    @capability("math.boom")
    async def boom(self) -> None:
        raise ValueError("intentional")


class StringHandler:
    @capability("text.echo", scopes=("text.read", "text.write"))
    async def echo(self, msg: str) -> str:
        return msg


# ------------------------------------------------------- helpers

async def _handle_request(router: Router, envelope: dict) -> dict:
    """Handle a request envelope and return the response dict."""
    result = await router.handle(envelope)
    assert result is not None
    return result


# ------------------------------------------------------- success paths

@pytest.mark.anyio
async def test_dispatch_async_handler():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "math.sum",
        "params": {"a": 2, "b": 3},
        "capability": "math.sum",
    })
    assert resp["id"] == "req-1"
    assert resp["result"] == 5
    assert "error" not in resp or resp["error"] is None


@pytest.mark.anyio
async def test_dispatch_sync_handler():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.write"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "math.div",
        "params": {"a": 10, "b": 2},
        "capability": "math.div",
    })
    assert resp["id"] == 42
    assert resp["result"] == 5.0


@pytest.mark.anyio
async def test_dispatch_public_capability_no_scopes():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())  # no caller scopes
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-2",
        "method": "math.identity",
        "params": {"x": 7},
        "capability": "math.public",
    })
    assert resp["result"] == 7


@pytest.mark.anyio
async def test_dispatch_with_trace_id_and_deadline():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-3",
        "method": "math.sum",
        "params": {"a": 1, "b": 1},
        "capability": "math.sum",
        "trace_id": "trace-abc",
        "deadline_ms": 1000,
    })
    assert resp["result"] == 2


# ------------------------------------------------------- error paths

@pytest.mark.anyio
async def test_unknown_capability():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-4",
        "method": "does.not.exist",
        "params": {},
        "capability": "does.not.exist",
    })
    assert resp["id"] == "req-4"
    assert resp["error"]["code"] == -32002
    assert "does.not.exist" in resp["error"]["message"]
    assert "math.sum" in resp["error"]["data"]["available"]


@pytest.mark.anyio
async def test_scope_not_permitted():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-5",
        "method": "math.div",
        "params": {"a": 1, "b": 2},
        "capability": "math.div",
    })
    assert resp["id"] == "req-5"
    assert resp["error"]["code"] == -32003
    assert "math.div" in resp["error"]["message"]


@pytest.mark.anyio
async def test_handler_exception():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-6",
        "method": "math.boom",
        "params": {},
        "capability": "math.boom",
    })
    assert resp["id"] == "req-6"
    assert resp["error"]["code"] == -32004
    assert "intentional" in resp["error"]["message"]
    assert resp["error"]["data"]["exception_type"] == "ValueError"


@pytest.mark.anyio
async def test_deadline_exceeded():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-7",
        "method": "math.slow",
        "params": {},
        "capability": "math.slow",
        "deadline_ms": 30,
    })
    assert resp["id"] == "req-7"
    assert resp["error"]["code"] == -32001
    assert "deadline" in resp["error"]["message"].lower()


@pytest.mark.anyio
async def test_params_as_list_rejected():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
    resp = await _handle_request(router, {
        "jsonrpc": "2.0",
        "id": "req-8",
        "method": "math.sum",
        "params": [1, 2],
        "capability": "math.sum",
    })
    assert resp["id"] == "req-8"
    assert resp["error"]["code"] == -32602
    assert "dict" in resp["error"]["message"].lower()


@pytest.mark.anyio
async def test_invalid_envelope():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())
    resp = await router.handle({"jsonrpc": "1.0", "id": "x"})
    assert resp is not None
    assert resp["error"]["code"] == -32600
    assert "Invalid" in resp["error"]["message"]


@pytest.mark.anyio
async def test_notification_no_response():
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())
    result = await router.handle({
        "jsonrpc": "2.0",
        "method": "progress.update",
        "params": {"percent": 50},
    })
    assert result is None


@pytest.mark.anyio
async def test_notification_callback():
    runtime = AcpRuntime([MathHandler()])
    called_with: dict | None = None

    async def on_notification(env: dict):
        nonlocal called_with
        called_with = env

    router = Router(runtime, RouterConfig(on_notification=on_notification))
    await router.handle({
        "jsonrpc": "2.0",
        "method": "progress.update",
        "params": {"percent": 75},
    })
    assert called_with is not None
    assert called_with["method"] == "progress.update"
    assert called_with["params"]["percent"] == 75


# ------------------------------------------------------- scope validator

class TestScopeValidator:
    def test_no_required_scopes_always_permitted(self):
        v = ScopeValidator({"math.read"})
        assert v.is_permitted(()) is True

    def test_exact_match(self):
        v = ScopeValidator({"math.read", "math.write"})
        assert v.is_permitted(("math.read",)) is True

    def test_partial_match(self):
        v = ScopeValidator({"math.read"})
        assert v.is_permitted(("math.read", "math.write")) is True

    def test_no_match(self):
        v = ScopeValidator({"math.read"})
        assert v.is_permitted(("math.write",)) is False

    def test_empty_caller_scopes(self):
        v = ScopeValidator(set())
        assert v.is_permitted(("math.read",)) is False
        assert v.is_permitted(()) is True

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            ScopeValidator({"BadScope"})

    def test_check_scope_functional(self):
        assert check_scope({"math.read"}, ("math.read",)) is True
        assert check_scope({"math.read"}, ("math.write",)) is False
        assert check_scope(set(), ()) is True

    def test_repr(self):
        v = ScopeValidator({"z", "a"})
        assert "a" in repr(v)
        assert "z" in repr(v)


# ------------------------------------------------------- response structure

class TestResponseStructure:
    def test_success_response_has_all_fields(self):
        resp = JsonRpcResponse(id="r1", result={"ok": True})
        wire = resp.model_dump(mode="json")
        assert wire["jsonrpc"] == "2.0"
        assert wire["id"] == "r1"
        assert wire["result"] == {"ok": True}
        assert "error" not in wire or wire["error"] is None

    def test_error_response_has_all_fields(self):
        err = JsonRpcError(code=-32001, message="too slow", data={"ms": 50})
        resp = JsonRpcResponse(id="r2", error=err)
        wire = resp.model_dump(mode="json")
        assert wire["jsonrpc"] == "2.0"
        assert wire["id"] == "r2"
        assert wire["error"]["code"] == -32001
        assert wire["error"]["message"] == "too slow"
        assert wire["error"]["data"]["ms"] == 50
        assert "result" not in wire or wire["result"] is None


# ------------------------------------------------------- integration: router + runtime + schema

@pytest.mark.anyio
async def test_end_to_end_request_response():
    """Full pipeline: dict → router → runtime → dict."""
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))

    raw = {
        "jsonrpc": "2.0",
        "id": "e2e-1",
        "method": "math.sum",
        "params": {"a": 10, "b": 20},
        "capability": "math.sum",
        "trace_id": "trace-e2e",
    }
    resp = await router.handle(raw)
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == "e2e-1"
    assert resp["result"] == 30

    # Validate the response back through pydantic
    parsed = JsonRpcResponse.model_validate(resp)
    assert parsed.result == 30
    assert parsed.error is None


@pytest.mark.anyio
async def test_end_to_end_error_response():
    """Full pipeline: dict → router → error → dict."""
    runtime = AcpRuntime([MathHandler()])
    router = Router(runtime, RouterConfig())

    raw = {
        "jsonrpc": "2.0",
        "id": "e2e-2",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
    }
    resp = await router.handle(raw)
    assert resp is not None
    assert resp["error"]["code"] == -32003

    parsed = JsonRpcResponse.model_validate(resp)
    assert parsed.error is not None
    assert parsed.error.code == -32003
    assert parsed.result is None
