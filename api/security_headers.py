"""
api/security_headers.py — Security Headers & Host Validation Middleware.

Implements defense-in-depth HTTP security headers and Host header validation
for all endpoints in the AhmedETAP platform.
"""

from __future__ import annotations

import re
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9._\-]+(:[0-9]+)?$")
_IPV6_HOST_PATTERN = re.compile(r"^\[[0-9a-fA-F:]+\](:[0-9]+)?$")


class HostValidationMiddleware:
    """Validate incoming Host headers to mitigate DNS rebinding and Host injection attacks."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            host = headers.get("host", "")
            if not host or (not _HOST_PATTERN.match(host) and not _IPV6_HOST_PATTERN.match(host)):
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Host header"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Inject strict security headers into all HTTP responses.

    Implemented as pure ASGI middleware to maintain full compatibility with
    SSE (StreamingResponse) and WebSockets without memory buffering.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
                )
            await send(message)

        await self.app(scope, receive, send_with_headers)
