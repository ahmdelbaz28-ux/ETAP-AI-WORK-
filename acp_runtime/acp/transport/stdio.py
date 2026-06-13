"""Stdio transport — line-delimited JSON over stdin / stdout.

The canonical transport for local editor integration (LSP-style).
Each JSON-RPC message is a single line terminated by ``\\n``. Reads
and writes are protected by locks so concurrent tasks are safe.

For testing, pass ``io.StringIO`` instances as ``stdin`` and
``stdout``.
"""
from __future__ import annotations
import logging
import sys
from typing import TextIO

import anyio

from acp.transport.base import Transport

__all__ = ["StdioTransport"]


class StdioTransport(Transport):
    """Line-delimited JSON transport over stdin/stdout.

    Parameters:
        stdin: input stream. Defaults to ``sys.stdin``.
        stdout: output stream. Defaults to ``sys.stdout``.
    """

    def __init__(self, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._read_lock = anyio.Lock()
        self._write_lock = anyio.Lock()
        self._closed = False
        self._log = logging.getLogger("acp.transport.stdio")

    async def read_message(self) -> str | None:
        """Read one line from stdin."""
        if self._closed:
            return None
        async with self._read_lock:
            try:
                line = await anyio.to_thread.run_sync(self.stdin.readline)
            except Exception:
                self._log.debug("stdio read error", exc_info=True)
                return None
            if not line:
                return None
            # Remove trailing newline only — keep other whitespace
            return line.rstrip("\n")

    async def write_message(self, message: str) -> None:
        """Write one line to stdout."""
        if self._closed:
            return
        async with self._write_lock:
            try:
                await anyio.to_thread.run_sync(self.stdout.write, message + "\n")
                await anyio.to_thread.run_sync(self.stdout.flush)
            except Exception:
                self._log.debug("stdio write error", exc_info=True)

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True
