"""Tests for the transport layer — stdio, UDS, WebSocket, and Server.

Covers:
    * StdioTransport read/write with memory streams
    * UDSTransport read/write with mock ByteStream
    * WebSocketTransport read/write with mock send/receive
    * Server event loop (request, notification, parse error, EOF)
    * Server integration with Router (full pipeline)
    * Thread-safety (concurrent writes)
    * Graceful shutdown on EOF
"""

from __future__ import annotations

import io
import json

import anyio
import pytest
from acp.router import Router, RouterConfig
from acp.runtime import AcpRuntime, capability
from acp.transport import (
    Server,
    StdioTransport,
    UDSTransport,
    WebSocketTransport,
)
from acp.transport.uds import _LineBuffer

# ------------------------------------------------------- test handlers


class MathHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        await anyio.sleep(0.001)
        return a + b

    @capability("math.public")
    async def identity(self, x: int) -> int:
        return x


# ------------------------------------------------------- helpers


class FakeByteStream:
    """Mock ``anyio.abc.ByteStream`` for testing UDSTransport."""

    def __init__(self, read_data: bytes = b"") -> None:
        self._read_data = read_data
        self._sent: list[bytes] = []
        self._closed = False

    async def receive(self, max_bytes: int = 65536) -> bytes:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        if not self._read_data:
            return b""
        chunk = self._read_data[:max_bytes]
        self._read_data = self._read_data[max_bytes:]
        return chunk

    async def send(self, data: bytes) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        self._sent.append(data)

    async def aclose(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        self._closed = True


def _make_router() -> Router:
    runtime = AcpRuntime([MathHandler()])
    return Router(runtime, RouterConfig(caller_scopes={"math.read"}))


# ------------------------------------------------------- StdioTransport


class TestStdioTransport:
    def test_read_message(self):
        stdin = io.StringIO('{"jsonrpc":"2.0","id":"1","method":"test"}\n')
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)

        msg = anyio.run(transport.read_message)
        assert msg == '{"jsonrpc":"2.0","id":"1","method":"test"}'

    def test_read_eof(self):
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)

        msg = anyio.run(transport.read_message)
        assert msg is None

    def test_write_message(self):
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)

        anyio.run(lambda: transport.write_message('{"result":42}'))
        assert stdout.getvalue() == '{"result":42}\n'

    def test_read_strips_trailing_newline_only(self):
        stdin = io.StringIO('{"jsonrpc":"2.0"}\r\n')
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)

        msg = anyio.run(transport.read_message)
        assert msg == '{"jsonrpc":"2.0"}\r'

    @pytest.mark.anyio
    async def test_read_after_close(self):
        stdin = io.StringIO('{"jsonrpc":"2.0"}\n')
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        await transport.close()
        msg = await transport.read_message()
        assert msg is None

    @pytest.mark.anyio
    async def test_write_after_close(self):
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        await transport.close()
        await transport.write_message("should not write")
        assert stdout.getvalue() == ""


# ------------------------------------------------------- UDSTransport


class TestLineBuffer:
    def test_read_line_single(self):
        stream = FakeByteStream(b"hello\nworld")
        buf = _LineBuffer(stream)
        assert anyio.run(buf.read_line) == b"hello"
        assert anyio.run(buf.read_line) == b"world"

    def test_read_line_empty(self):
        stream = FakeByteStream(b"")
        buf = _LineBuffer(stream)
        assert anyio.run(buf.read_line) == b""

    def test_read_line_no_newline(self):
        stream = FakeByteStream(b"incomplete")
        buf = _LineBuffer(stream)
        assert anyio.run(buf.read_line) == b"incomplete"


class TestUDSTransport:
    @pytest.mark.anyio
    async def test_read_message(self):
        raw = b'{"jsonrpc":"2.0","id":"1","method":"test"}\n'
        stream = FakeByteStream(raw)
        transport = UDSTransport(stream)
        msg = await transport.read_message()
        assert msg == '{"jsonrpc":"2.0","id":"1","method":"test"}'

    @pytest.mark.anyio
    async def test_read_eof(self):
        stream = FakeByteStream(b"")
        transport = UDSTransport(stream)
        msg = await transport.read_message()
        assert msg is None

    @pytest.mark.anyio
    async def test_write_message(self):
        stream = FakeByteStream(b"")
        transport = UDSTransport(stream)
        await transport.write_message('{"result":42}')
        assert stream._sent == [b'{"result":42}\n']

    @pytest.mark.anyio
    async def test_read_after_close(self):
        stream = FakeByteStream(b'{"jsonrpc":"2.0"}\n')
        transport = UDSTransport(stream)
        await transport.close()
        msg = await transport.read_message()
        assert msg is None

    @pytest.mark.anyio
    async def test_write_after_close(self):
        stream = FakeByteStream(b"")
        transport = UDSTransport(stream)
        await transport.close()
        await transport.write_message("should not write")
        assert stream._sent == []


# ------------------------------------------------------- WebSocketTransport


class TestWebSocketTransport:
    @pytest.mark.anyio
    async def test_read_message(self):
        messages = ['{"jsonrpc":"2.0","id":"1","method":"test"}']
        idx = 0

        async def recv() -> str:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            nonlocal idx
            msg = messages[idx]
            idx += 1
            return msg

        async def send(_: str) -> None:
            pass

        transport = WebSocketTransport(send, recv)
        msg = await transport.read_message()
        assert msg == '{"jsonrpc":"2.0","id":"1","method":"test"}'

    @pytest.mark.anyio
    async def test_read_eof(self):
        async def recv() -> str:
            raise ConnectionError("closed")

        async def send(_: str) -> None:
            pass

        transport = WebSocketTransport(send, recv)
        msg = await transport.read_message()
        assert msg is None

    @pytest.mark.anyio
    async def test_write_message(self):
        sent: list[str] = []

        async def recv() -> str:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            return ""

        async def send(msg: str) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            sent.append(msg)

        transport = WebSocketTransport(send, recv)
        await transport.write_message('{"result":42}')
        assert sent == ['{"result":42}']

    @pytest.mark.anyio
    async def test_read_after_close(self):
        async def recv() -> str:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            return '{"jsonrpc":"2.0"}'

        async def send(_: str) -> None:
            pass

        transport = WebSocketTransport(send, recv)
        await transport.close()
        msg = await transport.read_message()
        assert msg is None

    @pytest.mark.anyio
    async def test_write_after_close(self):
        sent: list[str] = []

        async def recv() -> str:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            return ""

        async def send(msg: str) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            sent.append(msg)

        transport = WebSocketTransport(send, recv)
        await transport.close()
        await transport.write_message("should not write")
        assert sent == []


# ------------------------------------------------------- Server


class TestServer:
    @pytest.mark.anyio
    async def test_server_request_response(self):
        """Full loop: request → router → response."""
        stdin = io.StringIO(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "r1",
                    "method": "math.sum",
                    "params": {"a": 3, "b": 4},
                    "capability": "math.sum",
                }
            )
            + "\n"
        )
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 1
        resp = json.loads(lines[0])
        assert resp["id"] == "r1"
        assert resp["result"] == 7

    @pytest.mark.anyio
    async def test_server_notification_no_response(self):
        """Notification must produce no response."""
        stdin = io.StringIO(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "progress.update",
                    "params": {"percent": 50},
                }
            )
            + "\n"
        )
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        assert stdout.read() == ""

    @pytest.mark.anyio
    async def test_server_parse_error(self):
        """Invalid JSON produces a parse error response."""
        stdin = io.StringIO("not json\n")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 1
        resp = json.loads(lines[0])
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700
        assert "Parse error" in resp["error"]["message"]

    @pytest.mark.anyio
    async def test_server_eof(self):
        """EOF on stdin causes graceful shutdown."""
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        assert transport._closed  # close is called in finally

    @pytest.mark.anyio
    async def test_server_multiple_requests(self):
        """Multiple requests in sequence."""
        req1 = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "math.sum",
                "params": {"a": 1, "b": 2},
                "capability": "math.sum",
            }
        )
        req2 = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "2",
                "method": "math.sum",
                "params": {"a": 3, "b": 4},
                "capability": "math.sum",
            }
        )
        stdin = io.StringIO(req1 + "\n" + req2 + "\n")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["result"] == 3
        assert json.loads(lines[1])["result"] == 7

    @pytest.mark.anyio
    async def test_server_scope_denied(self):
        """Request with missing scope returns error."""
        req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "math.sum",
                "params": {"a": 1, "b": 2},
                "capability": "math.sum",
            }
        )
        stdin = io.StringIO(req + "\n")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        runtime = AcpRuntime([MathHandler()])
        router = Router(runtime, RouterConfig())  # no scopes
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 1
        resp = json.loads(lines[0])
        assert resp["error"]["code"] == -32003

    @pytest.mark.anyio
    async def test_server_invalid_jsonrpc_envelope(self):
        """Valid JSON but invalid JSON-RPC envelope."""
        req = json.dumps({"jsonrpc": "1.0", "id": "x", "method": "m"})
        stdin = io.StringIO(req + "\n")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)
        router = _make_router()
        server = Server(router, transport)

        await server.run()

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 1
        resp = json.loads(lines[0])
        assert resp["error"]["code"] == -32600

    @pytest.mark.anyio
    async def test_server_concurrent_writes(self):
        """Concurrent writes to the same transport are serialised."""
        stdin = io.StringIO("")
        stdout = io.StringIO()
        transport = StdioTransport(stdin, stdout)

        async def write_many():
            for i in range(10):
                await transport.write_message(f'"{i}"')

        async with anyio.create_task_group() as tg:
            tg.start_soon(write_many)
            tg.start_soon(write_many)

        stdout.seek(0)
        lines = stdout.read().strip().split("\n")
        assert len(lines) == 20
        # All messages present (order may vary due to concurrency)
        assert all(line in [f'"{i}"' for i in range(10)] for line in lines)


# ------------------------------------------------------- integration: Server + Router + Runtime


@pytest.mark.anyio
async def test_end_to_end_stdio():
    """Full pipeline: StringIO → StdioTransport → Server → Router → Runtime."""
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "e2e",
            "method": "math.public",
            "params": {"x": 99},
            "capability": "math.public",
        }
    )
    stdin = io.StringIO(req + "\n")
    stdout = io.StringIO()
    transport = StdioTransport(stdin, stdout)
    router = _make_router()
    server = Server(router, transport)

    await server.run()

    stdout.seek(0)
    lines = stdout.read().strip().split("\n")
    assert len(lines) == 1
    resp = json.loads(lines[0])
    assert resp["result"] == 99
