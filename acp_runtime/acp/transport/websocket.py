"""WebSocket transport — JSON messages over WebSocket text frames.

The ``WebSocketTransport`` is transport-library-agnostic: it only
requires two async callables (``send`` and ``receive``) that map to
the WebSocket connection. This keeps the core ACP runtime free of any
WebSocket server dependency.

For production use, wrap a ``websockets`` connection::

    import websockets
    async with websockets.connect("ws://localhost:8765") as ws:
        transport = WebSocketTransport(ws.send, ws.recv)
        server = Server(router, transport)
        await server.run()

``WebSocketListener`` provides a convenience server using the
``websockets`` library (optional dependency).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

import anyio

from acp.transport.base import Transport
from acp.transport.server import Server

__all__ = ["WebSocketTransport", "WebSocketListener"]

# Type aliases for generic WebSocket interface
SendFn = Callable[[str], Coroutine[Any, Any, None]]
RecvFn = Callable[[], Coroutine[Any, Any, str]]


class WebSocketTransport(Transport):
    """Generic WebSocket transport.

    Parameters:
        send: async callable that sends a text frame.
        receive: async callable that returns the next text frame.
    """

    def __init__(self, send: SendFn, receive: RecvFn) -> None:
        self._send = send
        self._receive = receive
        self._write_lock = anyio.Lock()
        self._closed = False
        self._log = logging.getLogger("acp.transport.websocket")

    async def read_message(self) -> str | None:
        if self._closed:
            return None
        try:
            return await self._receive()
        except Exception:
            self._log.debug("websocket read error", exc_info=True)
            return None

    async def write_message(self, message: str) -> None:
        if self._closed:
            return
        async with self._write_lock:
            try:
                await self._send(message)
            except Exception:
                self._log.debug("websocket write error", exc_info=True)

    async def close(self) -> None:
        self._closed = True


class WebSocketListener:
    """Convenience WebSocket server using the ``websockets`` library.

    Parameters:
        host: bind address (default ``localhost``).
        port: bind port (default ``8765``).

    Raises:
        ImportError: if ``websockets`` is not installed.
    """

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._log = logging.getLogger("acp.transport.websocket")

    async def serve(self, router: Any) -> None:
        """Start a WebSocket server and spawn a ``Server`` per client."""
        try:
            import websockets
        except ImportError as exc:
            raise ImportError(
                "WebSocketListener requires the 'websockets' package. "
                "Install it:  pip install websockets>=12.0",
            ) from exc

        async def handler(ws: Any) -> None:
            transport = WebSocketTransport(ws.send, ws.recv)
            server = Server(router, transport)
            await server.run()

        self._log.info("websocket server starting on %s:%d", self.host, self.port)
        async with websockets.serve(handler, self.host, self.port):
            await anyio.sleep_forever()
