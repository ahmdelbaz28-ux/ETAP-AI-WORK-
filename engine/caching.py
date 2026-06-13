"""
Redis Caching Layer for ETAP AI Platform
==========================================
Provides an async Redis-backed caching layer for repeated study inputs,
with transparent in-memory fallback when Redis is unavailable.

Features:
- Async Redis operations via ``redis.asyncio``
- Deterministic cache key generation (SHA-256 of study type + params)
- TTL-based expiry (default 1 hour)
- In-memory dict fallback when Redis is unreachable
- Cache statistics (hits, misses, size)
- Bulk invalidation by study type
- Connection health checking with automatic reconnection

Usage
-----
>>> cache = StudyCache(redis_url="redis://localhost:6379", ttl=3600)
>>> await cache.set("load_flow", {"bus_count": 5, "voltage": 13.8}, {"result": "..."}...)
>>> result = await cache.get("load_flow", {"bus_count": 5, "voltage": 13.8})
>>> stats = await cache.get_stats()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: redis.asyncio
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------

class _InMemoryStore:
    """Thread-safe, TTL-aware in-memory cache that mimics the Redis interface.

    Used when ``redis.asyncio`` is not installed or the Redis server is
    unreachable.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._data: OrderedDict[str, Tuple[str, float]] = OrderedDict()  # key → (json_value, expires_at)
        self._max = max_entries
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        """Get a value by key.  Returns ``None`` if missing or expired."""
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at > 0 and time.time() > expires_at:
                del self._data[key]
                return None
            # Move to end (LRU)
            self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: str, ttl_seconds: int = 0) -> None:
        """Set a key with optional TTL."""
        expires_at = (time.time() + ttl_seconds) if ttl_seconds > 0 else 0.0
        async with self._lock:
            self._data[key] = (value, expires_at)
            # Evict oldest if over capacity
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    async def delete(self, key: str) -> bool:
        """Delete a key.  Returns ``True`` if the key existed."""
        async with self._lock:
            return self._data.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False
            _, expires_at = entry
            if expires_at > 0 and time.time() > expires_at:
                del self._data[key]
                return False
            return True

    async def keys(self, pattern: str = "*") -> List[str]:
        """Return keys matching a simple glob pattern.

        Only ``*`` (match all) and prefix patterns (``prefix:*``) are
        supported for efficiency.
        """
        async with self._lock:
            if pattern == "*":
                return list(self._data.keys())
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in self._data if k.startswith(prefix)]
            return [k for k in self._data if k == pattern]

    async def dbsize(self) -> int:
        """Return number of non-expired entries."""
        async with self._lock:
            now = time.time()
            expired = [k for k, (_, exp) in self._data.items() if exp > 0 and now > exp]
            for k in expired:
                del self._data[k]
            return len(self._data)

    async def flushdb(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._data.clear()


# ---------------------------------------------------------------------------
# StudyCache
# ---------------------------------------------------------------------------

class StudyCache:
    """Redis caching layer for repeated study inputs.

    When ``redis.asyncio`` is available and the Redis server is reachable,
    all operations use Redis.  Otherwise, an in-memory :class:`_InMemoryStore`
    is used transparently.

    Parameters
    ----------
    redis_url : str
        Redis connection URL (default ``"redis://localhost:6379"``).
    ttl : int
        Time-to-live in seconds for cached entries (default 3600 / 1 hour).
    key_prefix : str
        Prefix for all Redis keys (default ``"etap:study:"``).
    max_fallback_entries : int
        Maximum entries for the in-memory fallback store (default 10 000).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 3600,
        key_prefix: str = "etap:study:",
        max_fallback_entries: int = 10_000,
    ) -> None:
        self._redis_url = redis_url
        self._ttl = ttl
        self._key_prefix = key_prefix
        self._max_fallback_entries = max_fallback_entries

        self._redis: Optional[Any] = None
        self._fallback = _InMemoryStore(max_entries=max_fallback_entries)
        self._using_fallback = True

        # Stats
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._invalidations = 0
        self._stats_lock = asyncio.Lock()

        # Attempt initial Redis connection
        if HAS_REDIS:
            self._init_redis()

    def _init_redis(self) -> None:
        """Create the async Redis client (does not connect yet)."""
        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Actual connection verification happens on first operation
            self._using_fallback = False
            logger.info("Redis client configured for %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis client creation failed: %s — using in-memory fallback", exc)
            self._using_fallback = True

    # -- key generation ------------------------------------------------------

    def _make_key(self, study_type: str, params: dict) -> str:
        """Create a deterministic cache key from study type + parameters.

        The key is ``<prefix><study_type>:<sha256_hex>`` where the SHA-256
        digest is computed over the canonical JSON of *params*.

        Parameters
        ----------
        study_type : str
            Type of study (e.g. ``"load_flow"``, ``"short_circuit"``).
        params : dict
            Study input parameters.

        Returns
        -------
        str
            Cache key string.
        """
        canonical = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}{study_type}:{digest}"

    # -- Redis health --------------------------------------------------------

    async def _ensure_redis(self) -> bool:
        """Check if Redis is available and switch to fallback if not.

        Returns
        -------
        bool
            ``True`` if Redis is available.
        """
        if not HAS_REDIS or self._redis is None:
            return False

        try:
            await self._redis.ping()
            if self._using_fallback:
                logger.info("Redis connection restored — switching from fallback")
                self._using_fallback = False
            return True
        except Exception as exc:
            if not self._using_fallback:
                logger.warning("Redis unavailable (%s) — switching to fallback", exc)
                self._using_fallback = True
            return False

    # -- core operations -----------------------------------------------------

    async def get(self, study_type: str, params: dict) -> Optional[dict]:
        """Get cached study result.

        Parameters
        ----------
        study_type : str
            Type of study.
        params : dict
            Study input parameters.

        Returns
        -------
        dict or None
            Cached result dict, or ``None`` if not found / expired.
        """
        key = self._make_key(study_type, params)

        try:
            if not self._using_fallback:
                await self._ensure_redis()

            if not self._using_fallback and self._redis is not None:
                raw = await self._redis.get(key)
                if raw is not None:
                    async with self._stats_lock:
                        self._hits += 1
                    return json.loads(raw)

            # Fallback
            raw = await self._fallback.get(key)
            if raw is not None:
                async with self._stats_lock:
                    self._hits += 1
                return json.loads(raw)

        except Exception as exc:
            logger.warning("Cache get error for %s: %s", key, exc)

        async with self._stats_lock:
            self._misses += 1
        return None

    async def set(self, study_type: str, params: dict, result: dict) -> None:
        """Cache study result with TTL.

        Parameters
        ----------
        study_type : str
            Type of study.
        params : dict
            Study input parameters.
        result : dict
            Study result to cache.
        """
        key = self._make_key(study_type, params)
        value = json.dumps(result, default=str)

        try:
            if not self._using_fallback:
                await self._ensure_redis()

            if not self._using_fallback and self._redis is not None:
                await self._redis.set(key, value, ex=self._ttl)
            else:
                await self._fallback.set(key, value, ttl_seconds=self._ttl)

            async with self._stats_lock:
                self._sets += 1

        except Exception as exc:
            logger.warning("Cache set error for %s: %s", key, exc)
            # Try fallback
            try:
                await self._fallback.set(key, value, ttl_seconds=self._ttl)
                async with self._stats_lock:
                    self._sets += 1
            except Exception:
                logger.error("Fallback cache set also failed for %s", key)

    async def invalidate(self, study_type: str, params: dict) -> None:
        """Invalidate a cached result.

        Parameters
        ----------
        study_type : str
            Type of study.
        params : dict
            Study input parameters.
        """
        key = self._make_key(study_type, params)

        try:
            if not self._using_fallback:
                await self._ensure_redis()

            if not self._using_fallback and self._redis is not None:
                await self._redis.delete(key)
            else:
                await self._fallback.delete(key)

            async with self._stats_lock:
                self._invalidations += 1

        except Exception as exc:
            logger.warning("Cache invalidate error for %s: %s", key, exc)

    async def invalidate_study_type(self, study_type: str) -> int:
        """Invalidate all cached results for a study type.

        Parameters
        ----------
        study_type : str
            Type of study.

        Returns
        -------
        int
            Number of keys invalidated.
        """
        pattern = f"{self._key_prefix}{study_type}:*"
        count = 0

        try:
            if not self._using_fallback:
                await self._ensure_redis()

            if not self._using_fallback and self._redis is not None:
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    count = await self._redis.delete(*keys)
            else:
                keys = await self._fallback.keys(pattern)
                for key in keys:
                    deleted = await self._fallback.delete(key)
                    if deleted:
                        count += 1

            async with self._stats_lock:
                self._invalidations += count

        except Exception as exc:
            logger.warning("Bulk invalidation error for %s: %s", pattern, exc)

        return count

    # -- stats & management --------------------------------------------------

    async def get_stats(self) -> dict:
        """Return cache statistics.

        Returns
        -------
        dict
            ``{"hits", "misses", "hit_rate", "sets", "invalidations",
            "size", "backend", "ttl"}``
        """
        async with self._stats_lock:
            hits = self._hits
            misses = self._misses
            sets = self._sets
            invalidations = self._invalidations

        total = hits + misses
        hit_rate = (hits / total * 100) if total > 0 else 0.0

        size = 0
        backend = "memory_fallback"
        if not self._using_fallback and self._redis is not None:
            try:
                size = await self._redis.dbsize()
                backend = "redis"
            except Exception:
                size = await self._fallback.dbsize()
                backend = "redis_unavailable_fallback"
        else:
            size = await self._fallback.dbsize()

        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hit_rate, 2),
            "sets": sets,
            "invalidations": invalidations,
            "size": size,
            "backend": backend,
            "ttl": self._ttl,
            "redis_url": self._redis_url if not self._using_fallback else "fallback",
        }

    async def clear(self) -> None:
        """Clear all cached entries."""
        try:
            if not self._using_fallback and self._redis is not None:
                # Only clear our keys (with the prefix)
                pattern = f"{self._key_prefix}*"
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                logger.info("Cleared %d Redis cache entries", len(keys))
            else:
                await self._fallback.flushdb()
                logger.info("Cleared in-memory fallback cache")
        except Exception as exc:
            logger.warning("Cache clear error: %s", exc)
            await self._fallback.flushdb()

    # -- lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Close the Redis connection gracefully."""
        if self._redis is not None:
            try:
                await self._redis.close()
                logger.info("Redis connection closed")
            except Exception as exc:
                logger.warning("Error closing Redis: %s", exc)

    async def __aenter__(self) -> "StudyCache":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache_instance: Optional[StudyCache] = None
_cache_lock = threading.Lock()


def get_study_cache(
    redis_url: str = "redis://localhost:6379",
    ttl: int = 3600,
) -> StudyCache:
    """Get or create the global :class:`StudyCache` singleton.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    ttl : int
        Default TTL in seconds.

    Returns
    -------
    StudyCache
    """
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    with _cache_lock:
        if _cache_instance is not None:
            return _cache_instance
        _cache_instance = StudyCache(redis_url=redis_url, ttl=ttl)
        return _cache_instance
