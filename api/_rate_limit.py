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

CRITICAL FIX — Rate Limiter Lockout in SCADA (v2 — hardened):
- Added SCADA internal bypass via X-SCADA-Internal-Key header and
  IP whitelisting to prevent rate-limiting of critical SCADA telemetry
  during fault cascade events.
- v2 hardening: Uses ipaddress module for proper CIDR matching (not
  broken string prefix matching). Uses hmac.compare_digest for
  timing-attack-resistant secret comparison. Does NOT default to
  trusting all RFC 1918 networks (that would bypass ALL rate limiting
  behind a load balancer). SCADA_TRUSTED_IPS must be explicitly
  configured — empty by default for safety.
- Added audit logging for SCADA bypass events.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import threading
import time

from fastapi import HTTPException, Request

_logger = logging.getLogger("api._rate_limit")

# SCADA internal bypass secret — must match the SCADA_INTERNAL_SECRET
# environment variable configured on internal SCADA services.
# IMPORTANT: Empty string means bypass is DISABLED (fail-closed).
_SCADA_INTERNAL_SECRET = os.getenv("SCADA_INTERNAL_SECRET", "")

# Trusted SCADA IP ranges — MUST be explicitly configured.
# SECURITY: Intentionally defaults to EMPTY (no IPs trusted).
# The previous version defaulted to all RFC 1918 private networks
# (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), which is a CRITICAL
# security hole: if the server is behind a load balancer with a private
# IP, ALL external requests would bypass rate limiting.
# Set SCADA_TRUSTED_IPS env var to specific SCADA server IPs, e.g.:
#   SCADA_TRUSTED_IPS=10.0.1.100,10.0.1.101
# Or use CIDR notation for SCADA VLANs:
#   SCADA_TRUSTED_IPS=10.0.1.0/24
_SCADA_TRUSTED_IPS_RAW = os.getenv("SCADA_TRUSTED_IPS", "")
_SCADA_TRUSTED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
for _cidr in _SCADA_TRUSTED_IPS_RAW.split(","):
    _cidr = _cidr.strip()
    if _cidr:
        try:
            _SCADA_TRUSTED_NETWORKS.append(ipaddress.ip_network(_cidr, strict=False))
        except ValueError:
            _logger.warning("Invalid SCADA_TRUSTED_IPS entry ignored: %r", _cidr)


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
       SCADA_INTERNAL_SECRET environment variable (timing-safe comparison), OR
    2. The client IP falls within the explicitly configured SCADA_TRUSTED_IPS
       networks (using ipaddress module for proper CIDR matching).

    SECURITY NOTES (v2 hardening):
    - Uses hmac.compare_digest() for constant-time secret comparison
      to prevent timing attacks.
    - Uses ipaddress.ip_network/ip_address for proper CIDR matching
      instead of broken string prefix matching.
    - SCADA_TRUSTED_IPS defaults to EMPTY (fail-closed) — must be
      explicitly configured. The previous version defaulted to all
      RFC 1918 private networks, which would bypass ALL rate limiting
      behind a load balancer.
    - All bypass events are logged for audit trail.

    Returns True if the request should bypass the standard rate limiter.
    """
    # Check 1: Secret key header bypass (timing-safe comparison)
    internal_key = request.headers.get("X-SCADA-Internal-Key", "")
    if _SCADA_INTERNAL_SECRET and len(internal_key) == len(_SCADA_INTERNAL_SECRET):
        if hmac.compare_digest(internal_key, _SCADA_INTERNAL_SECRET):
            _logger.info(
                "scada_rate_limit_bypass method=secret_key client_ip=%s path=%s",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return True

    # Check 2: IP whitelist bypass (proper CIDR matching via ipaddress module)
    client_ip = request.client.host if request.client else ""
    if not client_ip or not _SCADA_TRUSTED_NETWORKS:
        return False

    try:
        client_addr = ipaddress.ip_address(client_ip)
        for network in _SCADA_TRUSTED_NETWORKS:
            if client_addr in network:
                _logger.info(
                    "scada_rate_limit_bypass method=ip_whitelist client_ip=%s network=%s path=%s",
                    client_ip,
                    str(network),
                    request.url.path,
                )
                return True
    except ValueError:
        _logger.warning("Invalid client IP address in rate limit check: %r", client_ip)

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

