"""acp.transport — Transport layer adapters.

Provides three transport implementations:
    * StdioTransport      — line-delimited JSON over stdin/stdout
    * UDSTransport        — line-delimited JSON over Unix domain sockets
    * WebSocketTransport  — JSON messages over WebSocket frames

All transports conform to the ``Transport`` ABC and are driven by the
``Server`` class, which maps raw JSON strings → the router → raw JSON
responses.

The transport layer is intentionally thin: it handles framing, JSON
(de)serialisation, and connection lifecycle. JSON-RPC validation and
dispatch live in the router layer.
"""

from __future__ import annotations

from acp.transport.base import Transport
from acp.transport.server import Server
from acp.transport.stdio import StdioTransport
from acp.transport.uds import UDSListener, UDSTransport
from acp.transport.websocket import WebSocketListener, WebSocketTransport

__all__ = [
    "Transport",
    "StdioTransport",
    "UDSTransport",
    "UDSListener",
    "WebSocketTransport",
    "WebSocketListener",
    "Server",
]
