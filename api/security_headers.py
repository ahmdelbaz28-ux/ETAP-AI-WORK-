"""
api/security_headers.py — Security Headers & Host Validation Middleware.

Implements defense-in-depth HTTP security headers and Host header validation
for all endpoints in the AhmedETAP platform.
"""

from __future__ import annotations

import os
import re
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9._\-]+(:\d+)?$")
_IPV6_HOST_PATTERN = re.compile(r"^\[[\da-fA-F:]+\](:\d+)?$")


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


_HSTS_MAX_AGE = os.environ.get("HSTS_MAX_AGE", "31536000")
_X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "SAMEORIGIN")


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

        if os.environ.get("ENFORCE_HTTPS", "false").lower() in ("true", "1"):
            req_headers = Headers(scope=scope)
            proto = req_headers.get("x-forwarded-proto", scope.get("scheme", "http"))
            if proto == "http":
                host = req_headers.get("host", "localhost")
                path = scope.get("raw_path", b"").decode("latin-1")
                query = scope.get("query_string", b"").decode("latin-1")
                redirect_url = f"https://{host}{path}"
                if query:
                    redirect_url = f"{redirect_url}?{query}"
                response = JSONResponse(
                    status_code=301,
                    headers={
                        "Location": redirect_url,
                        "Strict-Transport-Security": f"max-age={_HSTS_MAX_AGE}; includeSubDomains; preload",
                    },
                    content={"detail": "HTTPS required"},
                )
                await response(scope, receive, send)
                return

        async def send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # FIX-RC5: HSTS يُرسَل فقط عبر HTTPS — إرساله عبر HTTP يلوّث سجلات التطوير
                # ويمكن أن يُثبّت HSTS على localhost لمدة سنة كاملة.
                is_https = (
                    scope.get("scheme", "http") == "https"
                    or any(
                        k == b"x-forwarded-proto" and v == b"https"
                        for k, v in scope.get("headers", [])
                    )
                )
                if is_https:
                    headers["Strict-Transport-Security"] = (
                        f"max-age={_HSTS_MAX_AGE}; includeSubDomains; preload"
                    )
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = _X_FRAME_OPTIONS
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; font-src 'self'; connect-src 'self' wss: https:; "
                    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
                )
            await send(message)

        await self.app(scope, receive, send_with_headers)


_SecurityHeadersMiddleware = SecurityHeadersMiddleware
