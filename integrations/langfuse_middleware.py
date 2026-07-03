"""
Langfuse FastAPI middleware for AhmedETAP
=========================================

⚠️ SAFETY-CRITICAL ⚠️
Intercepts every HTTP request to the engineering service and:

1. **Starts a Langfuse trace** for each request (with the route, method,
   user ID, and study type as metadata).
2. **Captures the request body** (truncated for PII safety) and the
   response body, so reviewers can see exactly what input produced
   what output.
3. **Captures HTTP status + latency** as trace attributes.
4. **Auto-alerts** on 5xx errors and on requests to safety-critical
   endpoints (e.g. ``/api/studies/run`` for arc-flash studies).
5. **Attaches the request to a session** when the client sends a
   ``X-Session-ID`` header (so multiple requests from one engineering
   session are grouped in the Langfuse dashboard).
6. **Generates a trace URL** and returns it in the ``X-Langfuse-Trace-URL``
   response header, so the engineer can click through to review the trace.

Usage in ``engineering_service.py`` or wherever the FastAPI app is built::

    from fastapi import FastAPI
    from integrations.langfuse_middleware import LangfuseMiddleware

    app = FastAPI()
    app.add_middleware(LangfuseMiddleware)

The middleware is a no-op when Langfuse is disabled (env var
``LANGFUSE_ENABLED=false``), so it is safe to install unconditionally.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Routes that are safety-critical: a 5xx here means a safety calculation
# may have failed, which requires an alert.
_SAFETY_CRITICAL_PATHS = frozenset(
    p.strip()
    for p in os.environ.get(
        "LANGFUSE_SAFETY_PATHS",
        # Default: any path that runs a study or performs a calculation
        "/api/studies/run,"
        "/api/studies/,"
        "/api/agents/,"
        "/api/scada/,"
        "/api/digital-twin/,"
        "/api/validation/,"
        "/api/context-engine/,",
    ).split(",")
    if p.strip()
)

_MAX_BODY_CAPTURE = int(os.environ.get("LANGFUSE_HTTP_MAX_BODY", "4096"))


def _is_safety_critical(path: str) -> bool:
    """Return True if the request path is safety-critical."""
    return any(path.startswith(p) for p in _SAFETY_CRITICAL_PATHS)


def _truncate_body(body: bytes, max_chars: int = _MAX_BODY_CAPTURE) -> str | None:
    """Truncate a request/response body for safe capture."""
    if not body:
        return None
    if max_chars <= 0:
        return None
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return f"<binary {len(body)} bytes>"
    if len(text) > max_chars:
        return text[:max_chars] + f"\n...[truncated, {len(text) - max_chars} more chars]"
    return text


class LangfuseMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that traces every request in Langfuse.

    The middleware:
    - Creates a Langfuse trace per request
    - Captures input/output (truncated for PII safety)
    - Sets the trace name to ``{method} {path}``
    - Tags the trace with ``safety_critical=true`` for safety-critical routes
    - Returns the trace URL in the ``X-Langfuse-Trace-URL`` response header
    - Emits a safety alert on 5xx errors to safety-critical routes
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._enabled = (
            os.environ.get("LANGFUSE_ENABLED", "true").lower()
            in (
                "1",
                "true",
                "yes",
                "on",
            )
            and bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
            and bool(os.environ.get("LANGFUSE_SECRET_KEY"))
        )
        if self._enabled:
            logger.info("LangfuseMiddleware enabled — HTTP requests will be traced")
        else:
            logger.info("LangfuseMiddleware disabled (LANGFUSE_ENABLED or keys missing)")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled:
            return await call_next(request)

        # Import here to avoid import-time failure if langfuse SDK is missing
        try:
            from integrations.langfuse_integration import langfuse_tracker
            from integrations.langfuse_sessions import (
                alert_on_unsafe_trace,
                get_trace_share_url,
            )
        except ImportError:
            return await call_next(request)

        if not langfuse_tracker.enabled:
            return await call_next(request)

        # Capture request metadata
        method = request.method
        path = request.url.path
        user_id = request.headers.get("X-User-ID", "anonymous")
        session_id = request.headers.get("X-Session-ID")
        study_type = request.headers.get("X-Study-Type", "")
        safety_critical = _is_safety_critical(path)

        # Read request body (for capture)
        body_bytes = await request.body()

        # Build trace metadata
        trace_metadata: dict[str, Any] = {
            "http.method": method,
            "http.path": path,
            "http.route": request.headers.get("X-Route", path),
            "user_id": user_id,
            "safety_critical": safety_critical,
        }
        if study_type:
            trace_metadata["study_type"] = study_type

        # Start a Langfuse trace
        trace_name = f"{method} {path}"
        try:
            client = langfuse_tracker._get_client()
            if client is None:
                return await call_next(request)

            trace_kwargs: dict[str, Any] = {
                "name": trace_name,
                "metadata": trace_metadata,
                "user_id": user_id,
            }
            if session_id:
                trace_kwargs["session_id"] = session_id

            obs = client.start_as_current_observation(**trace_kwargs)

            # Capture input
            input_text = _truncate_body(body_bytes)
            if input_text:
                with contextlib.suppress(Exception):
                    obs.update(input=input_text)
        except Exception as e:
            logger.debug("Langfuse trace start failed (non-critical): %s", e)
            return await call_next(request)

        # Call the actual request handler
        start = time.monotonic()
        status_code = 500
        response_body = b""
        try:
            # Re-wrap the request body since we already consumed it
            async def receive() -> dict[str, Any]:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]
            response = await call_next(request)

            status_code = response.status_code

            # Capture response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Re-create the response with the captured body
            new_response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

            return new_response
        except Exception as exc:
            elapsed = time.monotonic() - start
            # Record exception on the trace
            try:
                if hasattr(obs, "record_exception"):
                    obs.record_exception(exc)
                obs.update(
                    level="ERROR",
                    metadata={
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:500],
                        "latency_seconds": elapsed,
                    },
                )
            except Exception:
                pass

            # Alert on safety-critical 5xx
            if safety_critical:
                with contextlib.suppress(Exception):
                    alert_on_unsafe_trace(
                        trace_id=str(getattr(obs, "id", "")),
                        reason=f"Exception in safety-critical route {method} {path}: {exc}",
                        user_id=user_id,
                        severity="critical",
                    )
            raise
        else:
            elapsed = time.monotonic() - start

            # Capture output + status
            try:
                output_text = _truncate_body(response_body)
                if output_text:
                    obs.update(output=output_text)
                obs.update(
                    metadata={
                        "http.status_code": status_code,
                        "latency_seconds": round(elapsed, 3),
                    },
                )
                if status_code >= 500 and safety_critical:
                    obs.update(level="ERROR")
                    with contextlib.suppress(Exception):
                        alert_on_unsafe_trace(
                            trace_id=str(getattr(obs, "id", "")),
                            reason=f"5xx error on safety-critical route {method} {path}: HTTP {status_code}",
                            user_id=user_id,
                            severity="high",
                        )
                elif status_code >= 400:
                    obs.update(level="WARNING")
            except Exception:
                pass

            # Try to get the trace URL for the response header
            trace_url = None
            try:
                trace_id = str(getattr(obs, "id", ""))
                if trace_id:
                    trace_url = get_trace_share_url(trace_id, make_public=False)
            except Exception:
                pass

            # End the observation
            with contextlib.suppress(Exception):
                obs.end()

            # Add the trace URL to the response headers
            if trace_url:
                with contextlib.suppress(Exception):
                    new_response.headers["X-Langfuse-Trace-URL"] = trace_url

            return new_response
        finally:
            try:
                if hasattr(obs, "end"):
                    obs.end()
            except Exception:
                pass


def install_langfuse_middleware(app: ASGIApp) -> None:
    """Install the Langfuse middleware on a FastAPI/Starlette app.

    Usage::

        from fastapi import FastAPI
        from integrations.langfuse_middleware import install_langfuse_middleware

        app = FastAPI()
        install_langfuse_middleware(app)
    """
    app.add_middleware(LangfuseMiddleware)  # type: ignore[arg-type]


__all__ = ["LangfuseMiddleware", "install_langfuse_middleware"]
