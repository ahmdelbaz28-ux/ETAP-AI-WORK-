"""Phase A — JSON roundtrip tests for ACP schema layer.

Every model in ``acp.schema`` must survive:
    1. Construction from Python values
    2. ``model_dump(mode="json")`` → plain dict
    3. ``json.dumps`` → JSON string
    4. ``json.loads`` → plain dict
    5. ``model_validate`` → reconstructed model
    6. Equality check with the original

Covers:
    * JsonRpcRequest, JsonRpcResponse, JsonRpcNotification, JsonRpcError
    * AcpParams, AcpResult
    * ProgressEvent (via envelope helpers)
    * Validation errors (invalid fields, extra fields, missing required fields)
"""
from __future__ import annotations

import json

import pytest
from acp.runtime import ProgressEvent
from acp.schema import (
    AcpParams,
    AcpResult,
    CapabilityDescriptor,
    JsonRpcError,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
)
from pydantic import ValidationError

# ------------------------------------------------------- helpers

def _roundtrip(obj: object) -> dict:
    """Serialize ``obj`` to JSON string and back to a plain dict."""
    payload = json.dumps(obj.model_dump(mode="json"), sort_keys=True)
    return json.loads(payload)


def _assert_json_roundtrip(original):
    """Assert that ``original`` survives dict → JSON → dict → model."""
    wire = _roundtrip(original)
    reconstructed = type(original).model_validate(wire)
    assert reconstructed == original
    return reconstructed


# ------------------------------------------------------- JsonRpcRequest

class TestJsonRpcRequest:
    def test_minimal_request(self):
        req = JsonRpcRequest(id="req-1", method="cap.invoke", capability="cap.invoke")
        assert req.jsonrpc == "2.0"
        assert req.id == "req-1"
        assert req.capability == "cap.invoke"
        assert req.trace_id == ""
        assert req.deadline_ms == 30_000
        _assert_json_roundtrip(req)

    def test_full_request_with_params(self):
        req = JsonRpcRequest(
            id="req-2",
            method="math.sum",
            params={"a": 1, "b": 2},
            capability="math.sum",
            trace_id="trace-abc",
            deadline_ms=5000,
        )
        assert req.params == {"a": 1, "b": 2}
        assert req.trace_id == "trace-abc"
        assert req.deadline_ms == 5000
        _assert_json_roundtrip(req)

    def test_request_with_int_id(self):
        req = JsonRpcRequest(id=42, method="math.sum", capability="math.sum")
        assert req.id == 42
        _assert_json_roundtrip(req)

    def test_request_with_list_params(self):
        req = JsonRpcRequest(
            id="req-3",
            method="math.sum",
            params=[1, 2, 3],
            capability="math.sum",
        )
        assert req.params == [1, 2, 3]
        _assert_json_roundtrip(req)

    def test_invalid_jsonrpc_version(self):
        with pytest.raises(ValidationError) as exc_info:
            JsonRpcRequest(id="x", method="m", capability="m", jsonrpc="1.0")
        assert "jsonrpc" in str(exc_info.value)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            JsonRpcRequest(id="x", method="m", capability="m", foo="bar")
        # pydantic v2 extra=forbid raises a validation error; check the error type
        assert any("foo" in str(e) or "extra" in str(e).lower() for e in exc_info.value.errors())

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            JsonRpcRequest(id="x", method="m")  # missing capability

    def test_deadline_ms_bounds(self):
        with pytest.raises(ValidationError):
            JsonRpcRequest(id="x", method="m", capability="m", deadline_ms=0)
        with pytest.raises(ValidationError):
            JsonRpcRequest(id="x", method="m", capability="m", deadline_ms=600_001)


# ------------------------------------------------------- JsonRpcResponse

class TestJsonRpcResponse:
    def test_success_response(self):
        resp = JsonRpcResponse(id="resp-1", result={"sum": 3})
        assert resp.result == {"sum": 3}
        assert resp.error is None
        _assert_json_roundtrip(resp)

    def test_error_response(self):
        err = JsonRpcError(code=-32001, message="Deadline exceeded", data={"deadline_ms": 50})
        resp = JsonRpcResponse(id="resp-2", error=err)
        assert resp.error.code == -32001
        assert resp.result is None
        _assert_json_roundtrip(resp)

    def test_both_result_and_error_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            JsonRpcResponse(id="resp-3", result={"ok": True}, error=JsonRpcError(code=-1, message="boom"))
        assert "exactly one" in str(exc_info.value).lower()

    def test_neither_result_nor_error_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            JsonRpcResponse(id="resp-4")
        assert "exactly one" in str(exc_info.value).lower() or "at least one" in str(exc_info.value).lower()

    def test_response_with_none_id(self):
        resp = JsonRpcResponse(id=None, result={"ok": True})
        assert resp.id is None
        _assert_json_roundtrip(resp)

    def test_response_with_int_id(self):
        resp = JsonRpcResponse(id=99, result={"ok": True})
        assert resp.id == 99
        _assert_json_roundtrip(resp)

    def test_error_json_roundtrip(self):
        err = JsonRpcError(code=-32004, message="Handler failed", data={"capability": "x"})
        _assert_json_roundtrip(err)


# ------------------------------------------------------- JsonRpcNotification

class TestJsonRpcNotification:
    def test_minimal_notification(self):
        n = JsonRpcNotification(method="progress.update")
        assert n.jsonrpc == "2.0"
        assert n.capability is None
        assert n.trace_id == ""
        _assert_json_roundtrip(n)

    def test_full_notification(self):
        n = JsonRpcNotification(
            method="cap.advertise",
            params={"names": ["a", "b"]},
            capability="cap.advertise",
            trace_id="trace-xyz",
        )
        assert n.params == {"names": ["a", "b"]}
        _assert_json_roundtrip(n)

    def test_notification_with_list_params(self):
        n = JsonRpcNotification(
            method="cap.advertise",
            params=["a", "b"],
        )
        assert n.params == ["a", "b"]
        _assert_json_roundtrip(n)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            JsonRpcNotification(method="m", unknown="field")
        assert any("unknown" in str(e) or "extra" in str(e).lower() for e in exc_info.value.errors())

    def test_notification_deadline_ms_bounds(self):
        with pytest.raises(ValidationError):
            JsonRpcNotification(method="m", deadline_ms=0)
        with pytest.raises(ValidationError):
            JsonRpcNotification(method="m", deadline_ms=600_001)


# ------------------------------------------------------- AcpParams / AcpResult

class TestAcpParams:
    def test_minimal_params(self):
        p = AcpParams(capability="math.sum")
        assert p.capability == "math.sum"
        assert p.trace_id == ""
        assert p.deadline_ms == 30_000
        _assert_json_roundtrip(p)

    def test_full_params(self):
        p = AcpParams(capability="math.sum", trace_id="t-1", deadline_ms=1000)
        assert p.deadline_ms == 1000
        _assert_json_roundtrip(p)

    def test_invalid_deadline(self):
        with pytest.raises(ValidationError):
            AcpParams(capability="x", deadline_ms=0)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AcpParams(capability="x", foo="bar")
        assert any("foo" in str(e) or "extra" in str(e).lower() for e in exc_info.value.errors())


class TestAcpResult:
    def test_minimal_result(self):
        r = AcpResult(capability="math.sum")
        assert r.output is None
        _assert_json_roundtrip(r)

    def test_result_with_output(self):
        r = AcpResult(capability="math.sum", trace_id="t-1", output={"sum": 42})
        assert r.output == {"sum": 42}
        _assert_json_roundtrip(r)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AcpResult(capability="x", foo="bar")
        assert any("foo" in str(e) or "extra" in str(e).lower() for e in exc_info.value.errors())


# ------------------------------------------------------- CapabilityDescriptor

class TestCapabilityDescriptor:
    def test_roundtrip(self):
        cd = CapabilityDescriptor(name="math.sum", scopes=["math.read", "math.write"])
        assert cd.name == "math.sum"
        assert cd.scopes == ("math.read", "math.write")
        _assert_json_roundtrip(cd)

    def test_invalid_name(self):
        with pytest.raises(ValidationError):
            CapabilityDescriptor(name="", scopes=[])
        with pytest.raises(ValidationError):
            CapabilityDescriptor(name="BadName", scopes=[])

    def test_invalid_scope(self):
        with pytest.raises(ValueError):
            CapabilityDescriptor(name="math.sum", scopes=["BadScope"])


# ------------------------------------------------------- ProgressEvent

class TestProgressEvent:
    def test_envelope_roundtrip(self):
        event = ProgressEvent(trace_id="t-1", percent=50, stage="running", message="halfway")
        env = event.to_envelope()
        assert env["jsonrpc"] == "2.0"
        assert env["method"] == "progress.update"
        assert env["params"]["percent"] == 50

        reconstructed = ProgressEvent.from_envelope(env)
        assert reconstructed.trace_id == "t-1"
        assert reconstructed.percent == 50
        assert reconstructed.stage == "running"
        assert reconstructed.message == "halfway"

    def test_default_message(self):
        event = ProgressEvent(trace_id="t-2", percent=0, stage="start")
        assert event.message == ""

    def test_json_string_roundtrip(self):
        event = ProgressEvent(trace_id="t-3", percent=100, stage="done", message="complete")
        env = event.to_envelope()
        payload = json.dumps(env)
        parsed = json.loads(payload)
        reconstructed = ProgressEvent.from_envelope(parsed)
        assert reconstructed == event


# ------------------------------------------------------- integration: request → params

class TestRequestParamsIntegration:
    def test_request_params_nested_roundtrip(self):
        """A real-world flow: params model → dict → JSON → dict → params model."""
        params = AcpParams(capability="math.sum", trace_id="abc", deadline_ms=2000)
        req = JsonRpcRequest(
            id="req-42",
            method="math.sum",
            params=params.model_dump(mode="json"),
            capability="math.sum",
            trace_id="abc",
            deadline_ms=2000,
        )
        wire = _roundtrip(req)
        reconstructed_req = JsonRpcRequest.model_validate(wire)
        reconstructed_params = AcpParams.model_validate(reconstructed_req.params)
        assert reconstructed_params == params

    def test_response_result_nested_roundtrip(self):
        """A real-world flow: result model → dict → JSON → dict → result model."""
        result = AcpResult(capability="math.sum", trace_id="abc", output={"sum": 42})
        resp = JsonRpcResponse(id="resp-42", result=result.model_dump(mode="json"))
        wire = _roundtrip(resp)
        reconstructed_resp = JsonRpcResponse.model_validate(wire)
        reconstructed_result = AcpResult.model_validate(reconstructed_resp.result)
        assert reconstructed_result == result


# ------------------------------------------------------- integration: error from exception

class TestErrorFromException:
    def test_error_from_acp_exception(self):
        from acp.errors import DeadlineExceeded

        exc = DeadlineExceeded("too slow", data={"deadline_ms": 50})
        wire = exc.to_wire()
        err = JsonRpcError.model_validate(wire)
        assert err.code == -32001
        assert err.message == "too slow"
        assert err.data == {"deadline_ms": 50}
        _assert_json_roundtrip(err)
