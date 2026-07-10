"""
api/_rate_limit.py — Shared sliding-window rate limiter.

Extracted from api/akamai_protection.py and api/cloudflare_protection.py
to eliminate code duplication (SonarCloud new_duplicated_lines_density).

Both edge-protection modules had identical `_rate_limit_check()` functions
operating on module-level `_RATE_LIMIT_STORE` dicts. This module provides
a `RateLimiter` class that both modules instantiate with their own
per-module state, keeping the behavior identical while removing the
duplicated code.
"""
from __future__ import annotations

import time


class RateLimiter:
    """Sliding-window rate limiter keyed by client identifier (typically IP).

    Usage:
        limiter = RateLimiter(max_requests=300, window_seconds=60)
        if limiter.is_allowed(client_ip):
            # handle request
        else:
            # reject with 429
    """

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests: int = max_requests
        self.window_seconds: int = window_seconds
        self._store: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if a request from `key` is allowed under the rate limit.

        Returns True if allowed, False if the limit has been exceeded.
        Side effect: prunes expired entries and appends the current timestamp.
        """
        now = time.monotonic()
        window_start = now - self.window_seconds

        # Prune old entries
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
        self._store.clear()
