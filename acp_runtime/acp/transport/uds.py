"""Unix Domain Socket (UDS) transport — line-delimited JSON over UDS.

UDS is the preferred IPC transport for low-latency, same-host agent
communication. Each connection is a full-duplex stream; messages are
line-delimited JSON terminated by ``\\n``.

The ``UDSListener`` accepts incoming connections and spawns a
``Server`` instance for each client.

On Windows, ``anyio.create_unix_listener`` is used (Windows 10+
AF_UNIX support). On older Windows versions UDS is not available.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import anyio
from anyio.abc import ByteStream

from acp.transport.base import Transport
from acp.transport.server import Server

__all__ = ["UDSTransport", "UDSListener"]


class _LineBuffer:
    """Simple buffered line reader for ``ByteStream``."""

    def __init__(self, stream: ByteStream) -> None:
        self._stream = stream
        self._buffer = b""

    async def read_line(self) -> bytes:
        """Return the next line (without ``\\n``), or ``b""`` on EOF."""
        while True:
            idx = self._buffer.find(b"\n")
            if idx != -1:
                line = self._buffer[:idx]
                self._buffer = self._buffer[idx + 1 :]
                return line
            try:
                chunk = await self._stream.receive(4096)
            except anyio.EndOfStream:
                return self._buffer
            if not chunk:
                return self._buffer
            self._buffer += chunk


class UDSTransport(Transport):
    """Line-delimited JSON transport over a ``ByteStream``.

    Parameters:
        stream: an ``anyio`` ``ByteStream`` (e.g. from a UDS listener).
    """

    def __init__(self, stream: ByteStream) -> None:
        self._stream = stream
        self._reader = _LineBuffer(stream)
        self._write_lock = anyio.Lock()
        self._closed = False
        self._log = logging.getLogger("acp.transport.uds")

    async def read_message(self) -> Optional[str]:
        if self._closed:
            return None
        try:
            data = await self._reader.read_line()
        except anyio.EndOfStream:
            return None
        if not data:
            return None
        return data.decode("utf-8")

    async def write_message(self, message: str) -> None:
        if self._closed:
            return
        async with self._write_lock:
            try:
                await self._stream.send((message + "\n").encode("utf-8"))
            except anyio.BrokenResourceError:
                self._log.debug("uds write broken resource", exc_info=True)

    async def close(self) -> None:
        self._closed = True
        try:
            await self._stream.aclose()
        except Exception:
            self._log.debug("uds close error", exc_info=True)


class UDSListener:
    """Unix Domain Socket listener.

    Parameters:
        path: filesystem path for the UDS socket.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._log = logging.getLogger("acp.transport.uds")

    async def serve(self, router: Any) -> None:
        """Accept connections and spawn a ``Server`` per client."""
        # Remove stale socket file
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

        listener = await anyio.create_unix_listener(self.path)
        async with listener:
            self._log.info("uds listening on %s", self.path)
            await listener.serve(lambda client: self._handle_client(client, router))

    async def _handle_client(self, client: ByteStream, router: Any) -> None:
        async with client:
            transport = UDSTransport(client)
            server = Server(router, transport)
            await server.run()
