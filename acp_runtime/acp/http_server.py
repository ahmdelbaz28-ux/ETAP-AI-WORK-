"""Lightweight async HTTP server for health/ready/metrics probes.

Intended for container and Kubernetes environments where a simple HTTP
endpoint is needed for liveness/readiness checks.  Uses only the stdlib
and *anyio* — no external HTTP framework required.

Example::

    from acp.http_server import start_http_server
    from acp.health import HealthHandler

    handler = HealthHandler(transport_name="stdio")
    await start_http_server(handler, port=8080)

Endpoints:

* ``GET /health`` → ``system.health`` JSON
* ``GET /ready``  → ``system.ready`` JSON
* ``GET /metrics`` (or the configured ``metrics_path``) → ``system.metrics`` JSON

Any other path or method returns 404/405.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anyio

__all__ = ["start_http_server"]


async def _handle_client(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    health_handler: Any, client: anyio.abc.ByteStream, metrics_path: str = "/metrics",
) -> None:
    """Parse a minimal HTTP request and dispatch to the health handler."""
    log = logging.getLogger("acp.http_server")
    try:
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = await client.receive(4096)
            if not chunk:
                break
            buffer += chunk

        header_end = buffer.find(b"\r\n\r\n")
        if header_end == -1:
            return

        headers = buffer[:header_end].decode("utf-8", errors="replace")
        lines = headers.split("\r\n")
        if not lines:
            return

        parts = lines[0].split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]

        if method != "GET":
            body = b'{"error":"Method not allowed"}'
            response = (
                b"HTTP/1.1 405 Method Not Allowed\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"  # NOSONAR — S1192: intentional repetition (audit constant)
                + body
            )
        elif path == "/health":
            result = await health_handler.health()
            body = json.dumps(result).encode()
            response = (
                b"HTTP/1.1 200 OK\r\n"  # NOSONAR — S1192: intentional repetition (audit constant)
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"
                + body
            )
        elif path == "/ready":
            result = await health_handler.ready()
            body = json.dumps(result).encode()
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"
                + body
            )
        elif path == metrics_path:
            # Content negotiation: prefer OpenMetrics if the client asks for it,
            # otherwise fall back to Prometheus text format.
            accept_header = ""
            for line in lines:
                if line.lower().startswith("accept:"):
                    accept_header = line.split(":", 1)[1].strip()
                    break

            wants_openmetrics = "application/openmetrics-text" in accept_header
            if wants_openmetrics and hasattr(health_handler, "openmetrics"):
                om_text = health_handler.openmetrics()
                body = om_text.encode()
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/openmetrics-text; version=1.0.0; charset=utf-8\r\n"
                    + f"Content-Length: {len(body)}\r\n".encode()
                    + b"Connection: close\r\n\r\n"
                    + body
                )
            elif hasattr(health_handler, "prometheus"):
                prom_text = health_handler.prometheus()
                body = prom_text.encode() if prom_text else b""
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                    + f"Content-Length: {len(body)}\r\n".encode()
                    + b"Connection: close\r\n\r\n"
                    + body
                )
            else:
                result = await health_handler.metrics()
                body = json.dumps(result).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n".encode()
                    + b"Connection: close\r\n\r\n"
                    + body
                )
        else:
            body = b'{"error":"Not found"}'
            response = (
                b"HTTP/1.1 404 Not Found\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"
                + body
            )

        await client.send(response)
    except (anyio.EndOfStream, OSError, ConnectionError, BrokenPipeError, ConnectionResetError):
        # Expected when a client disconnects abruptly.
        pass
    except Exception:
        log.debug("HTTP client handler error", exc_info=True)
    finally:
        await client.aclose()


async def start_http_server(health_handler: Any, port: int, metrics_path: str = "/metrics") -> None:
    """Start a TCP listener that serves health/ready/metrics JSON.

    Parameters:
        health_handler: a ``HealthHandler`` instance (or anything with
            ``health()``, ``ready()``, and ``metrics()`` async methods).
        port: TCP port to bind to.
    """
    listener = await anyio.create_tcp_listener(local_port=port)
    await listener.serve(lambda client: _handle_client(health_handler, client, metrics_path))
