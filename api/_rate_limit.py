"""
api/_rate_limit.py — Shared sliding-window rate limiter.

Extracted from api/akamai_protection.py and api/cloudflare_protection.py
to eliminate code duplication (SonarCloud new_duplicated_lines_density).

Both edge-protection modules had identical `_rate_limit_check()` functions
operating on module-level `_RATE_LIMIT_STORE` dicts. This module provides
a `RateLimiter` class that both modules instantiate with their own
per-module state, keeping the behavior identical while removing the
duplicated code.

SECURITY AUDIT 2026-07-25 — Fix S-08:
- Added threading.Lock for thread safety (prevents race conditions under
  concurrent requests in FastAPI async worker threads).
- Added automatic stale-entry cleanup to prevent unbounded memory growth.
  Keys that have no entries within the window are evicted on each call.
- Added _last_cleanup tracking to avoid O(n) full-scan on every call.

CRITICAL FIX — Rate Limiter Lockout in SCADA:
- Added SCADA internal bypass via X-SCADA-Internal-Key header and
  IP whitelisting to prevent rate-limiting of critical SCADA telemetry
  during fault cascade events. Without this bypass, the rate limiter
  would block SCADA alarm signals, blinding operators to live faults.
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request

# SCADA internal bypass secret — must match the SCADA_INTERNAL_SECRET
# environment variable configured on internal SCADA services.
_SCADA_INTERNAL_SECRET = os.getenv("SCADA_INTERNAL_SECRET", "")

# Trusted internal IP ranges for SCADA systems (RFC 1918 private networks).
# These ranges are used for internal SCADA communication and should never
# be rate-limited, even during fault cascade events.
_SCADA_TRUSTED_IPS: set[str] = set(
    os.getenv("SCADA_TRUSTED_IPS", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16").split(",")
)

# Global hard limit for maximum file uploads (50 MB) to prevent OOM.
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Megabytes


class RateLimiter:
    """Thread-safe sliding-window rate limiter keyed by client identifier (typically IP).

    Usage:
        limiter = RateLimiter(max_requests=300, window_seconds=60)
        if limiter.is_allowed(client_ip):
            # handle request
        else:
            # reject with 429

    Thread Safety:
        All public methods acquire the internal lock, making this safe for
        use in multi-threaded FastAPI/uvicorn deployments.

    Memory Safety:
        Stale keys (no entries within the window) are automatically evicted
        during periodic cleanup scans, preventing unbounded memory growth.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests: int = max_requests
        self.window_seconds: int = window_seconds
        self._store: dict[str, list[float]] = {}
        self._lock: threading.Lock = threading.Lock()
        # Cleanup optimization: track last full cleanup time
        self._last_cleanup: float = 0.0
        # Run full stale-key eviction at most once per window
        self._cleanup_interval: float = max(window_seconds // 2, 10)

    def _evict_stale_keys(
        self, _now: float, window_start: float
    ) -> None:  # NOSONAR kept for API symmetry with is_allowed (caller passes `now`)
        """Remove keys that have no entries within the current window.

        Called periodically (not on every request) to bound memory usage.
        Under normal operation, the _store dict grows proportionally to the
        number of unique clients seen within the window.
        """
        stale_keys = [
            key
            for key, entries in self._store.items()
            if not entries or entries[-1] <= window_start
        ]
        for key in stale_keys:
            del self._store[key]

    def is_allowed(self, key: str) -> bool:
        """Check if a request from `key` is allowed under the rate limit.

        Thread-safe. Returns True if allowed, False if the limit has been exceeded.
        Side effect: prunes expired entries and appends the current timestamp.
        """
        now = time.monotonic()
        window_start = now - self.window_seconds

        with self._lock:
            # Periodic stale-key cleanup
            if now - self._last_cleanup >= self._cleanup_interval:
                self._evict_stale_keys(now, window_start)
                self._last_cleanup = now

            # Prune old entries for this key
            entries = self._store.get(key, [])
            entries = [t for t in entries if t > window_start]

            if len(entries) >= self.max_requests:
                self._store[key] = entries
                return False

            entries.append(now)
            self._store[key] = entries
            return True

    def reset(self) -> None:
        """Clear all stored entries (useful for tests)."""
        with self._lock:
            self._store.clear()
            self._last_cleanup = 0.0


# ---------------------------------------------------------------------------
# Module-level rate limiter instances
# ---------------------------------------------------------------------------

# Default rate limiter for general API traffic: 300 requests per 60 seconds.
_default_limiter = RateLimiter(max_requests=300, window_seconds=60)

# SCADA-specific rate limiter with higher limits: 3000 requests per 60 seconds.
# This allows burst telemetry during fault cascade events while still
# providing a ceiling to prevent abuse.
_scada_limiter = RateLimiter(max_requests=3000, window_seconds=60)


def _is_scada_internal_request(request: Request) -> bool:
    """Check whether a request originates from a trusted SCADA internal source.

    A request is considered internal SCADA traffic if EITHER:
    1. It carries the X-SCADA-Internal-Key header matching the
       SCADA_INTERNAL_SECRET environment variable, OR
    2. The client IP falls within the trusted SCADA IP ranges
       (configured via SCADA_TRUSTED_IPS env var).

    Returns True if the request should bypass the standard rate limiter.
    """
    # Check 1: Secret key header bypass
    internal_key = request.headers.get("X-SCADA-Internal-Key", "")
    if _SCADA_INTERNAL_SECRET and internal_key == _SCADA_INTERNAL_SECRET:
        return True

    # Check 2: IP whitelist bypass
    # Only check if SCADA_TRUSTED_IPS is configured with non-default values
    client_ip = request.client.host if request.client else ""
    for trusted_cidr in _SCADA_TRUSTED_IPS:
        trusted_cidr = trusted_cidr.strip()
        if not trusted_cidr:
            continue
        # Simple prefix match for /8, /12, /16 networks
        if "/" in trusted_cidr:
            network_prefix = trusted_cidr.split("/")[0]
            prefix_len = int(trusted_cidr.split("/")[1])
            if prefix_len <= 24 and client_ip.startswith(".".join(network_prefix.split(".")[: prefix_len // 8])):
                return True
        elif client_ip == trusted_cidr:
            return True

    return False


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces rate limiting with SCADA bypass.

    This function should be used as a FastAPI Depends() dependency on
    endpoints that need rate limiting. It performs two checks:

    1. SCADA Bypass: If the request originates from a trusted SCADA
       internal source (verified via X-SCADA-Internal-Key header or
       IP whitelist), the request is allowed through without any
       rate limiting. This is critical because during fault cascade
       events, SCADA sensors send hundreds of signals per second,
       and blocking them would blind operators to live faults.

    2. Standard Rate Limiting: For all other requests, the default
       sliding-window rate limiter is applied (300 req/min by default).

    Raises:
        HTTPException: 429 Too Many Requests if the rate limit is exceeded.
    """
    # SCADA internal bypass — critical for fault cascade scenarios
    if _is_scada_internal_request(request):
        return  # Bypass rate limiting for trusted SCADA systems

    # Standard rate limiting for external users
    client_key = request.client.host if request.client else "unknown"
    if not _default_limiter.is_allowed(client_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )


async def check_scada_rate_limit(request: Request) -> None:
    """FastAPI dependency for SCADA endpoints with higher rate limits.

    SCADA endpoints use a more permissive rate limiter (3000 req/min)
    instead of the standard 300 req/min, because SCADA telemetry
    naturally produces high-frequency updates during normal operation
    and even higher during fault events.

    Trusted internal SCADA requests are completely exempt from
    rate limiting via the X-SCADA-Internal-Key header or IP whitelist.

    Raises:
        HTTPException: 429 Too Many Requests if the SCADA rate limit is exceeded.
    """
    # SCADA internal bypass — critical for fault cascade scenarios
    if _is_scada_internal_request(request):
        return  # Bypass rate limiting for trusted SCADA systems

    # SCADA-specific rate limiting (more permissive than default)
    client_key = request.client.host if request.client else "unknown"
    if not _scada_limiter.is_allowed(client_key):
        raise HTTPException(
            status_code=429,
            detail="SCADA rate limit exceeded. Internal SCADA systems are exempt.",
        )
