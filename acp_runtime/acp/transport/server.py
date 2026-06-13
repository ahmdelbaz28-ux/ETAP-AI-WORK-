"""Server — drives a ``Transport`` + ``Router`` event loop.

The server is the glue between the transport layer (framing) and the
router layer (dispatch). It runs a simple loop:

    1. Read raw JSON string from transport
    2. Parse JSON → dict
    3. Dispatch to router
    4. If a response dict is returned, serialise and write back

JSON parse errors are handled at the server level (not the router) so
that a proper JSON-RPC ``-32700`` (Parse Error) response can be sent
back to the caller.

Cancellation (e.g. from the parent ``anyio.TaskGroup``) is propagated
so the server shuts down cleanly.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from acp.transport.base import Transport

__all__ = ["Server"]

# JSON-RPC 2.0 standard error codes
JSONRPC_PARSE_ERROR = -32700


class Server:
    """Drive a single transport connection through the router.

    Parameters:
        router: the ``Router`` instance that handles JSON-RPC dispatch.
        transport: the ``Transport`` instance that provides framing.
        metrics: optional ``MetricsRegistry`` for connection metrics.
        logger: optional ``StructuredLogger`` for structured logging.

    Usage::

        server = Server(router, transport)
        await server.run()
    """

    def __init__(
        self,
        router: Any,
        transport: Transport,
        *,
        metrics: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        self._router = router
        self._transport = transport
        self._metrics = metrics
        self._logger = logger
        self._log = logging.getLogger("acp.server")

    async def run(self) -> None:
        """Run the read → parse → dispatch → write loop.

        The loop exits when the transport returns ``None`` (EOF) or when
        the enclosing task is cancelled.
        """
        try:
            while True:
                raw = await self._transport.read_message()
                if raw is None:
                    self._log.debug("transport EOF; shutting down")
                    break

                # Observability: record message received
                if self._metrics is not None:
                    self._metrics.get_or_create_counter(
                        "acp.transport.messages.received", "Messages received"
                    ).inc()
                    self._metrics.get_or_create_counter(
                        "acp.transport.bytes.received", "Bytes received"
                    ).inc(len(raw.encode("utf-8")))

                try:
                    envelope = json.loads(raw)
                except json.JSONDecodeError as exc:
                    if self._metrics is not None:
                        self._metrics.get_or_create_counter(
                            "acp.transport.messages.parse_errors", "Parse errors"
                        ).inc()
                    await self._send_parse_error(exc)
                    continue

                response = await self._router.handle(envelope)
                if response is not None:
                    resp_json = json.dumps(response)
                    await self._transport.write_message(resp_json)
                    if self._metrics is not None:
                        self._metrics.get_or_create_counter(
                            "acp.transport.messages.sent", "Messages sent"
                        ).inc()
                        self._metrics.get_or_create_counter(
                            "acp.transport.bytes.sent", "Bytes sent"
                        ).inc(len(resp_json.encode("utf-8")))
        except Exception as e:
            self._log.exception("server error: %s", e)
        finally:
            await self._transport.close()

    async def _send_parse_error(self, exc: json.JSONDecodeError) -> None:
        response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": JSONRPC_PARSE_ERROR,
                "message": f"Parse error: {exc}",
            },
        }
        await self._transport.write_message(json.dumps(response))
