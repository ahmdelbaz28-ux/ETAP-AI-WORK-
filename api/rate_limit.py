"""api/rate_limit.py — Unified SlowAPI rate limiting Module.

This Module represents the single canonical rate-limiting Seam for the AhmedETAP platform.
It unifies scattered rate-limiting implementations into a high-Depth architectural Interface,
maximizing Leverage and Locality.

Architecture Concepts:
- Module: Single source of truth for rate limiting across API endpoints.
- Interface: Clean test surface exporting `limiter` and key extraction functions.
- Seam: Isolates endpoint handlers from rate-limiting mechanisms and storage engines.
- Adapter: Redis Adapter (distributed multi-replica) vs Memory Adapter (in-memory single-replica).
- Depth: High behavior-to-interface ratio (moving window, spoof-resistant proxy resolution,
  resilient fail-open in-memory fallback, and RFC 6585 / 7231 Retry-After header synthesis).
- Leverage: A single decorator on a route provides full protection against abuse and DoS.
- Locality: All rate-limit algorithms, storage decisions, and key strategies are localized here.

Stacked Semantics & Interface Contract:
- Layer 1 (SlowAPI): Enforces HTTP burst and throughput throttling before expensive handlers.
  Returns HTTP 429 with standard `Retry-After: <seconds>` header. Never resets on successful
  login because request volume was still consumed.
- Layer 2 (Internal User Lockout): Enforces per-username credential stuffing protection (5/15min).
  Resets on successful login (F-11).
- Layer 3 (Internal IP Lockout): Enforces broad IP credential stuffing protection (50/15min).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import time
from typing import Any, Callable, Optional

from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    _SLOWAPI_AVAILABLE = True
except ImportError:
    _SLOWAPI_AVAILABLE = False

    class RateLimitExceeded(Exception):  # type: ignore[no-redef]
        """Fallback RateLimitExceeded when slowapi is not installed."""

        def __init__(self, detail: str = "Rate limit exceeded"):
            super().__init__(detail)
            self.detail = detail

    class SlowAPIMiddleware:  # type: ignore[no-redef]
        """Fallback pass-through middleware when slowapi is not installed."""

        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            await self.app(scope, receive, send)

    class Limiter:  # type: ignore[no-redef]
        """Fallback Limiter when slowapi is not installed."""

        def __init__(
            self,
            key_func: Optional[Callable[..., str]] = None,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            self.key_func = key_func
            self.limiter = None

        def limit(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator


logger = logging.getLogger("etap.rate_limit")

# ---------------------------------------------------------------------------
# Storage Adapter Configuration (Redis vs Memory)
# ---------------------------------------------------------------------------
# Two Adapters = real Seam.
# When REDIS_URL or USE_REDIS_RATE_LIMIT is enabled, uses the Redis Adapter for
# distributed clusters. Otherwise, falls back to the in-memory Adapter.
_REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT: str = os.environ.get("REDIS_PORT", "6379")
_REDIS_PASSWORD: Optional[str] = os.environ.get("REDIS_PASSWORD")
_REDIS_URL: str = os.environ.get("REDIS_URL", "").strip()

if not _REDIS_URL and os.environ.get("USE_REDIS_RATE_LIMIT", "false").lower() in ("true", "1"):
    if _REDIS_PASSWORD:
        _REDIS_URL = f"redis://:{_REDIS_PASSWORD}@{_REDIS_HOST}:{_REDIS_PORT}/0"
    else:
        _REDIS_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/0"

_STORAGE_URI: str = _REDIS_URL if _REDIS_URL.startswith(("redis://", "rediss://")) else "memory://"

logger.info(
    "Rate limiting storage adapter initialized with storage_uri=%s",
    "redis://***" if _STORAGE_URI.startswith(("redis://", "rediss://")) else "memory://",
)


# ---------------------------------------------------------------------------
# Proxy-Aware Client IP Extraction (Spoofing Invariant)
# ---------------------------------------------------------------------------
def get_client_ip(request: Request) -> str:
    """Extract client IP address, honoring X-Forwarded-For only if trusted hops > 0.

    Spoofing Invariant:
    If TRUSTED_PROXY_HOPS is 0 (default), X-Forwarded-For is completely ignored
    to prevent client-controlled header spoofing attacks. If TRUSTED_PROXY_HOPS = N,
    the client IP is taken as the N-th IP from the right side of the header.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        The resolved client IP string.
    """
    trusted_hops_raw = os.environ.get("TRUSTED_PROXY_HOPS", "0")
    try:
        trusted_hops = int(trusted_hops_raw)
    except ValueError:
        trusted_hops = 0

    if trusted_hops > 0:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if len(parts) >= trusted_hops:
                return parts[-trusted_hops]
            return parts[0] if parts else "127.0.0.1"

    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def get_remote_address_proxy_aware(request: Request) -> str:
    """Key function returning the proxy-aware client IP for generic unauthenticated routes.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        The client IP string.
    """
    return get_client_ip(request)


# ---------------------------------------------------------------------------
# Domain-Specific Key Functions
# ---------------------------------------------------------------------------
def get_login_rate_limit_key(request: Request) -> str:
    """Key function returning 'client_ip:username_lower' for login/token endpoints.

    Prevents distributed credential stuffing from locking out legitimate users under NAT,
    and isolates brute-force attempts per target account.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        A compound key 'ip:username' or fallback 'ip'.
    """
    client_ip = get_client_ip(request)
    body_bytes = getattr(request, "_body", None)
    if body_bytes and isinstance(body_bytes, bytes):
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            if isinstance(payload, dict):
                username = payload.get("username")
                if isinstance(username, str) and username.strip():
                    return f"{client_ip}:{username.strip().lower()}"
        except Exception:
            logger.debug("Could not parse request body for login rate-limit username")

    return client_ip


def get_authenticated_or_ip_key(request: Request) -> str:
    """Key function for authenticated or token-bearing routes (e.g. refresh).

    Keys by SHA-256 prefix of Bearer token if present; otherwise falls back to client IP.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        A unique token hash or client IP string.
    """
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            return f"tok:{token_hash}"

    return get_client_ip(request)


# ---------------------------------------------------------------------------
# Canonical Limiter Instance (Single Seam & Type-Safe Decorator)
# ---------------------------------------------------------------------------
class UnifiedLimiter(Limiter):
    """Unified Limiter that preserves resolved FastAPI signatures under __future__.annotations.

    When Python modules use `from __future__ import annotations`, function annotations are
    strings. SlowAPI's default wrapper has `__globals__` pointing to `slowapi.extension`,
    preventing FastAPI from resolving application models/dependencies. This subclass resolves
    type hints using the original function's namespace and attaches the resolved signature.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._override_enabled: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        """Return whether rate limiting is active, checking environment flag if not overridden."""
        if self._override_enabled is not None:
            return self._override_enabled
        disabled = os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_DISABLED", "").lower()
        return disabled not in ("true", "1", "yes")

    @enabled.setter
    def enabled(self, value: Optional[bool]) -> None:
        """Explicitly override rate limiting enabled state (useful for tests)."""
        self._override_enabled = value

    def limit(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:
        """Wrap SlowAPI limit decorator with FastAPI type signature preservation."""
        decorator = super().limit(*args, **kwargs)

        def decorator_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
            wrapper = decorator(func)
            try:
                from fastapi.dependencies.utils import get_typed_annotation

                globalns = getattr(func, "__globals__", {})
                sig = inspect.signature(func)
                resolved_params = [
                    param.replace(annotation=get_typed_annotation(param.annotation, globalns))
                    for param in sig.parameters.values()
                ]
                wrapper.__signature__ = sig.replace(parameters=resolved_params)
            except Exception:
                logger.debug(
                    "Could not resolve signature annotations for %s",
                    getattr(func, "__name__", "endpoint"),
                    exc_info=True,
                )
            return wrapper

        return decorator_wrapper


# D1/D2 Fix: Exactly one Limiter instance for the entire application.
# No default_limits on the instance to avoid unintentionally throttling un-decorated routes.
if _SLOWAPI_AVAILABLE:
    limiter: Limiter = UnifiedLimiter(
        key_func=get_remote_address_proxy_aware,
        storage_uri=_STORAGE_URI,
        strategy="moving-window",
        in_memory_fallback_enabled=True,
    )
else:
    limiter = UnifiedLimiter()

# Deprecated alias to maintain backward compatibility without splitting state (D1)
auth_limiter: Limiter = limiter


# ---------------------------------------------------------------------------
# Exception Handler with Retry-After Header
# ---------------------------------------------------------------------------
def rate_limit_exceeded_handler(request: Request, exc: Any) -> Response:
    """Build a standard JSON 429 response including Retry-After header.

    Args:
        request: The incoming request that triggered rate limiting.
        exc: The RateLimitExceeded exception.

    Returns:
        JSONResponse with HTTP 429 status and Retry-After header.
    """
    retry_after: int = 60  # Default fallback window
    vrl = getattr(request.state, "view_rate_limit", None)

    if vrl and hasattr(limiter, "limiter") and limiter.limiter:
        try:
            window_stats = limiter.limiter.get_window_stats(vrl[0], *vrl[1])
            reset_in = 1 + window_stats[0]
            calculated = int(reset_in - time.time())
            if calculated > 0:
                retry_after = calculated
        except Exception:
            logger.debug("Failed to calculate exact reset time from window stats", exc_info=True)

    headers = {
        "Retry-After": str(retry_after),
    }

    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        {"error": f"Rate limit exceeded: {detail}"},
        status_code=429,
        headers=headers,
    )


# Alias for compatibility with default SlowAPI signature
_rate_limit_exceeded_handler = rate_limit_exceeded_handler

__all__ = [
    "limiter",
    "auth_limiter",
    "SlowAPIMiddleware",
    "RateLimitExceeded",
    "rate_limit_exceeded_handler",
    "_rate_limit_exceeded_handler",
    "get_client_ip",
    "get_remote_address_proxy_aware",
    "get_login_rate_limit_key",
    "get_authenticated_or_ip_key",
]
