"""Phase H — Comprehensive integration test suite.

Runs all transport adapters end-to-end with real handler modules:
    * StdioTransport  → StringIO-based stdin/stdout
    * UDSListener     → real Unix Domain Socket (skipped on Windows if unavailable)
    * WebSocketListener → real WebSocket server (skipped if websockets not installed)

Cross-cutting concerns:
    * Authentication (HMAC tokens)
    * Scope-based authorization
    * Metrics collection
    * Audit logging
    * Error handling (parse errors, handler errors, invalid envelopes)
    * Cancellation / graceful shutdown
"""
from __future__ import annotations
import io
import json
from typing import Any

import anyio
import pytest

from acp.transport import StdioTransport, Server, UDSListener, WebSocketListener
from acp.router import Router, RouterConfig
from acp.runtime import AcpRuntime
from acp.security import AuthConfig, HmacTokenValidator, NDJSONAuditLogger
from acp.observability import InMemoryMetricsRegistry

# Handler module under test
from tests.integration_handlers import IntegrationHandler

__all__ = []


# ------------------------------------------------------------------ helpers

def _build_router_with_auth(
    *,
    scopes: set[str] | None = None,
    secret: str | None = None,
    require_auth: bool = False,
    audit_path: str | None = None,
    metrics: InMemoryMetricsRegistry | None = None,
    logger: Any | None = None,
) -> Router:
    """Build a Router with the integration handler and optional auth/audit/metrics."""
    runtime = AcpRuntime([IntegrationHandler()])
    auth_validator = None
    if secret:
        config = AuthConfig(secret_key=secret, token_ttl_seconds=3600)
        auth_validator = HmacTokenValidator(config).validate
    audit_logger = None
    if audit_path:
        audit_logger = NDJSONAuditLogger(audit_path)
    return Router(
        runtime,
        RouterConfig(
            caller_scopes=scopes or set(),
            auth_validator=auth_validator,
            audit_logger=audit_logger,
            require_auth_for_public=require_auth,
            metrics=metrics,
            logger=logger,
        ),
    )


def _issue_token(secret: str, caller_id: str, scopes: set[str]) -> str:
    """Issue a valid HMAC token for the test subject."""
    config = AuthConfig(secret_key=secret, token_ttl_seconds=3600)
    return HmacTokenValidator(config).issue(caller_id, scopes)


def _make_request(method: str, params: dict, req_id: str, capability: str) -> str:
    """Serialize a JSON-RPC request."""
    envelope = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
        "capability": capability,
    }
    return json.dumps(envelope)


def _make_notification(method: str, params: dict, capability: str) -> str:
    """Serialize a JSON-RPC notification."""
    envelope = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "capability": capability,
    }
    return json.dumps(envelope)


def _read_response(stdout: io.StringIO) -> dict | None:
    """Read the next JSON-RPC response line from a StringIO."""
    stdout.seek(0)
    line = stdout.readline()
    if not line:
        return None
    return json.loads(line)


# ------------------------------------------------------------------ stdio

class TestStdioIntegration:
    """End-to-end tests using StdioTransport with memory streams."""

    @pytest.mark.anyio
    async def test_stdio_request_response(self):
        """Full roundtrip: request → router → response."""
        req = _make_request("math.sum", {"a": 3, "b": 4}, "r1", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"})
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["id"] == "r1"
        assert resp["result"] == 7

    @pytest.mark.anyio
    async def test_stdio_multiple_requests(self):
        """Multiple sequential requests."""
        req1 = _make_request("math.sum", {"a": 1, "b": 2}, "1", "math.sum") + "\n"
        req2 = _make_request("math.multiply", {"a": 3, "b": 4}, "2", "math.multiply") + "\n"
        req3 = _make_request("public.echo", {"message": "hello"}, "3", "public.echo") + "\n"
        stdin = io.StringIO(req1 + req2 + req3)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read", "math.write"})
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = [json.loads(l) for l in stdout.read().strip().split("\n")]
        assert len(lines) == 3
        assert lines[0]["result"] == 3
        assert lines[1]["result"] == 12
        assert lines[2]["result"] == "hello"

    @pytest.mark.anyio
    async def test_stdio_notification_no_response(self):
        """Notification must not produce a response."""
        req = _make_notification("public.echo", {"message": "ping"}, "public.echo") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth()
        server = Server(router, transport)

        await server.run()

        assert stdout.getvalue() == ""

    @pytest.mark.anyio
    async def test_stdio_parse_error(self):
        """Invalid JSON produces a parse error response."""
        stdin = io.StringIO("not json\n")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth()
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700
        assert "Parse error" in resp["error"]["message"]

    @pytest.mark.anyio
    async def test_stdio_invalid_jsonrpc_envelope(self):
        """Valid JSON but invalid JSON-RPC envelope."""
        req = json.dumps({"jsonrpc": "1.0", "id": "x", "method": "m"}) + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth()
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32600

    @pytest.mark.anyio
    async def test_stdio_scope_denied(self):
        """Request with missing scope returns authorization error."""
        req = _make_request("math.sum", {"a": 1, "b": 2}, "1", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes=set())  # no scopes
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32003

    @pytest.mark.anyio
    async def test_stdio_auth_valid_token(self):
        """Authenticated request with valid token succeeds."""
        token = _issue_token("test-secret", "user1", {"math.read"})
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": "auth1",
            "method": "math.sum",
            "params": {"a": 5, "b": 6},
            "capability": "math.sum",
            "trace_id": token,
        }) + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(secret="test-secret")
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["result"] == 11

    @pytest.mark.anyio
    async def test_stdio_auth_invalid_token(self):
        """Authenticated request with bad token fails."""
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": "auth2",
            "method": "math.sum",
            "params": {"a": 1, "b": 2},
            "capability": "math.sum",
            "trace_id": "invalid.token.here",
        }) + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(secret="test-secret")
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32005

    @pytest.mark.anyio
    async def test_stdio_auth_missing_scope_in_token(self):
        """Token valid but missing required scope."""
        token = _issue_token("test-secret", "user1", {"public"})  # no math.read
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": "auth3",
            "method": "math.sum",
            "params": {"a": 1, "b": 2},
            "capability": "math.sum",
            "trace_id": token,
        }) + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(secret="test-secret")
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32003

    @pytest.mark.anyio
    async def test_stdio_metrics_collected(self):
        """Metrics counters are incremented during request processing."""
        req = _make_request("math.sum", {"a": 2, "b": 3}, "m1", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        metrics = InMemoryMetricsRegistry()
        router = _build_router_with_auth(scopes={"math.read"}, metrics=metrics)
        server = Server(router, transport, metrics=metrics)

        await server.run()

        received = metrics.get_or_create_counter("acp.transport.messages.received", "")
        sent = metrics.get_or_create_counter("acp.transport.messages.sent", "")
        assert received.value >= 1
        assert sent.value >= 1

    @pytest.mark.anyio
    async def test_stdio_audit_logged(self, tmp_path):
        """Audit log entries are written for each request."""
        audit_path = tmp_path / "audit.ndjson"
        req = _make_request("math.sum", {"a": 1, "b": 2}, "a1", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"}, audit_path=str(audit_path))
        server = Server(router, transport)

        await server.run()

        assert audit_path.exists()
        lines = audit_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["capability"] == "math.sum"

    @pytest.mark.anyio
    async def test_stdio_handler_error(self):
        """Handler exception is mapped to a JSON-RPC error response."""
        req = _make_request("error.raise", {"message": "intentional"}, "e1", "error.raise") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"})
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32004
        assert "intentional" in resp["error"]["message"]

    @pytest.mark.anyio
    async def test_stdio_eof_graceful_shutdown(self):
        """EOF on stdin causes graceful shutdown."""
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth()
        server = Server(router, transport)

        await server.run()

        assert transport._closed


# ------------------------------------------------------------------ uds

@pytest.fixture
def uds_path(tmp_path):
    """Return a temporary UDS socket path."""
    return str(tmp_path / "acp_test.sock")


class TestUdsIntegration:
    """End-to-end tests using UDSListener with real socket connections."""

    @pytest.mark.anyio
    async def test_uds_request_response(self, uds_path):
        """Full roundtrip over UDS."""
        router = _build_router_with_auth(scopes={"math.read"})
        try:
            listener = UDSListener(uds_path)
        except (OSError, AttributeError) as e:
            pytest.skip(f"UDS not available on this platform: {e}")

        req = _make_request("math.sum", {"a": 7, "b": 8}, "u1", "math.sum") + "\n"
        response_lines: list[str] = []

        async def client():
            # Give the server a moment to start
            await anyio.sleep(0.05)
            try:
                client_stream = await anyio.connect_unix(uds_path)
            except (OSError, AttributeError) as e:
                pytest.skip(f"UDS not available on this platform: {e}")
            async with client_stream:
                await client_stream.send(req.encode())
                # Read response
                data = await client_stream.receive(4096)
                response_lines.append(data.decode())

        async with anyio.create_task_group() as tg:
            tg.start_soon(client)
            # Server runs with a short timeout so it doesn't block forever
            with anyio.move_on_after(1):
                try:
                    await listener.serve(router)
                except (OSError, AttributeError) as e:
                    pytest.skip(f"UDS not available on this platform: {e}")

        assert len(response_lines) == 1
        resp = json.loads(response_lines[0])
        assert resp["result"] == 15

    @pytest.mark.anyio
    async def test_uds_multiple_requests(self, uds_path):
        """Multiple requests in one UDS connection."""
        router = _build_router_with_auth(scopes={"math.read", "math.write"})
        try:
            listener = UDSListener(uds_path)
        except (OSError, AttributeError) as e:
            pytest.skip(f"UDS not available: {e}")

        req1 = _make_request("math.sum", {"a": 1, "b": 2}, "1", "math.sum") + "\n"
        req2 = _make_request("math.multiply", {"a": 3, "b": 4}, "2", "math.multiply") + "\n"
        response_data: list[bytes] = []

        async def client():
            await anyio.sleep(0.05)
            try:
                client_stream = await anyio.connect_unix(uds_path)
            except (OSError, AttributeError) as e:
                pytest.skip(f"UDS not available: {e}")
            async with client_stream:
                await client_stream.send((req1 + req2).encode())
                await anyio.sleep(0.05)
                data = await client_stream.receive(4096)
                response_data.append(data)

        async with anyio.create_task_group() as tg:
            tg.start_soon(client)
            with anyio.move_on_after(1):
                try:
                    await listener.serve(router)
                except (OSError, AttributeError) as e:
                    pytest.skip(f"UDS not available: {e}")

        assert len(response_data) == 1
        lines = response_data[0].decode().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["result"] == 3
        assert json.loads(lines[1])["result"] == 12

    @pytest.mark.anyio
    async def test_uds_auth(self, uds_path):
        """Authenticated request over UDS."""
        token = _issue_token("uds-secret", "user1", {"math.read"})
        router = _build_router_with_auth(secret="uds-secret")
        try:
            listener = UDSListener(uds_path)
        except (OSError, AttributeError) as e:
            pytest.skip(f"UDS not available: {e}")

        req = json.dumps({
            "jsonrpc": "2.0",
            "id": "uauth",
            "method": "math.sum",
            "params": {"a": 10, "b": 20},
            "capability": "math.sum",
            "trace_id": token,
        }) + "\n"
        response_lines: list[str] = []

        async def client():
            await anyio.sleep(0.05)
            try:
                client_stream = await anyio.connect_unix(uds_path)
            except (OSError, AttributeError) as e:
                pytest.skip(f"UDS not available: {e}")
            async with client_stream:
                await client_stream.send(req.encode())
                data = await client_stream.receive(4096)
                response_lines.append(data.decode())

        async with anyio.create_task_group() as tg:
            tg.start_soon(client)
            with anyio.move_on_after(1):
                try:
                    await listener.serve(router)
                except (OSError, AttributeError) as e:
                    pytest.skip(f"UDS not available: {e}")

        assert len(response_lines) == 1
        resp = json.loads(response_lines[0])
        assert resp["result"] == 30


# ------------------------------------------------------------------ websocket

class TestWebSocketIntegration:
    """End-to-end tests using WebSocketListener with real WebSocket connections."""

    @pytest.fixture
    def ws_port(self):
        """Return an ephemeral port for the WebSocket server."""
        return 18765

    @pytest.mark.anyio
    async def test_websocket_request_response(self, ws_port):
        """Full roundtrip over WebSocket."""
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets package not installed")

        router = _build_router_with_auth(scopes={"math.read"})
        listener = WebSocketListener("localhost", ws_port)

        req = _make_request("math.sum", {"a": 9, "b": 10}, "w1", "math.sum")
        response_lines: list[str] = []

        async def client():
            await anyio.sleep(0.1)
            try:
                ws = await websockets.connect(f"ws://localhost:{ws_port}")
            except Exception as e:
                pytest.skip(f"WebSocket connection failed: {e}")
            try:
                await ws.send(req)
                resp = await ws.recv()
                response_lines.append(resp)
            finally:
                await ws.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(client)
            with anyio.move_on_after(2):
                await listener.serve(router)

        assert len(response_lines) == 1
        resp = json.loads(response_lines[0])
        assert resp["result"] == 19

    @pytest.mark.anyio
    async def test_websocket_auth(self, ws_port):
        """Authenticated request over WebSocket."""
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets package not installed")

        token = _issue_token("ws-secret", "user1", {"math.read"})
        router = _build_router_with_auth(secret="ws-secret")
        listener = WebSocketListener("localhost", ws_port)

        req = json.dumps({
            "jsonrpc": "2.0",
            "id": "wauth",
            "method": "math.sum",
            "params": {"a": 100, "b": 200},
            "capability": "math.sum",
            "trace_id": token,
        })
        response_lines: list[str] = []

        async def client():
            await anyio.sleep(0.1)
            try:
                ws = await websockets.connect(f"ws://localhost:{ws_port}")
            except Exception as e:
                pytest.skip(f"WebSocket connection failed: {e}")
            try:
                await ws.send(req)
                resp = await ws.recv()
                response_lines.append(resp)
            finally:
                await ws.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(client)
            with anyio.move_on_after(2):
                await listener.serve(router)

        assert len(response_lines) == 1
        resp = json.loads(response_lines[0])
        assert resp["result"] == 300


# ------------------------------------------------------------------ cross-cutting

class TestCrossCutting:
    """Tests that span all transports (run via stdio for simplicity)."""

    @pytest.mark.anyio
    async def test_metrics_counters_incremented(self):
        """Metrics are recorded for received, sent, and bytes."""
        req = _make_request("math.sum", {"a": 2, "b": 3}, "mc", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        metrics = InMemoryMetricsRegistry()
        router = _build_router_with_auth(scopes={"math.read"}, metrics=metrics)
        server = Server(router, transport, metrics=metrics)

        await server.run()

        recv = metrics.get_or_create_counter("acp.transport.messages.received", "")
        sent = metrics.get_or_create_counter("acp.transport.messages.sent", "")
        recv_bytes = metrics.get_or_create_counter("acp.transport.bytes.received", "")
        assert recv.value >= 1
        assert sent.value >= 1
        assert recv_bytes.value >= len(req.encode()) - 2

    @pytest.mark.anyio
    async def test_audit_log_format(self, tmp_path):
        """Audit log entries contain expected fields."""
        audit_path = tmp_path / "audit.ndjson"
        req = _make_request("math.sum", {"a": 1, "b": 2}, "al", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"}, audit_path=str(audit_path))
        server = Server(router, transport)

        await server.run()

        lines = audit_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "timestamp" in entry
        assert "capability" in entry
        assert entry["capability"] == "math.sum"

    @pytest.mark.anyio
    async def test_division_by_zero_error(self):
        """Handler error is mapped to JSON-RPC error."""
        req = _make_request("math.divide", {"a": 10, "b": 0}, "div", "math.divide") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"})
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32004
        assert "Division by zero" in resp["error"]["message"]

    @pytest.mark.anyio
    async def test_public_capability_without_auth(self):
        """Public capability succeeds without auth when auth is not configured."""
        req = _make_request("public.echo", {"message": "open"}, "pub", "public.echo") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth()
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["result"] == "open"

    @pytest.mark.anyio
    async def test_require_auth_blocks_public(self):
        """When require_auth_for_public=True, public capability requires auth."""
        req = _make_request("public.echo", {"message": "closed"}, "rap", "public.echo") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(secret="auth-secret", require_auth=True)
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["error"]["code"] == -32005

    @pytest.mark.anyio
    async def test_progress_capability_no_emitter(self):
        """Progress capability returns fallback result when no emitter is passed."""
        req = _make_request("math.progress", {"steps": 3}, "prog", "math.progress") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"})
        server = Server(router, transport)

        await server.run()

        resp = _read_response(stdout)
        assert resp is not None
        assert resp["result"] == "done"

    @pytest.mark.anyio
    async def test_cancellation(self):
        """Server shuts down cleanly when the transport is closed."""
        req = _make_request("math.sum", {"a": 1, "b": 2}, "c1", "math.sum") + "\n"
        stdin = io.StringIO(req)
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _build_router_with_auth(scopes={"math.read"})
        server = Server(router, transport)

        await server.run()
        assert transport._closed
