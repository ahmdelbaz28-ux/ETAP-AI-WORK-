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
"""
from __future__ import annotations

import threading
import time


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

    def _evict_stale_keys(self, now: float, window_start: float) -> None:
        """Remove keys that have no entries within the current window.

        Called periodically (not on every request) to bound memory usage.
        Under normal operation, the _store dict grows proportionally to the
        number of unique clients seen within the window.
        """
        stale_keys = [
            key for key, entries in self._store.items()
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
