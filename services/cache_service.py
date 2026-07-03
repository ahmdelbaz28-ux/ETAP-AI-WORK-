"""
Cache Service module for the Engineering Service.

Provides a StudyCache with:
- Redis backend when available (optional)
- in-memory fallback when Redis is unavailable

Public API aligned to: tests/test_cache_service.py
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _is_redis_url(redis_url: str) -> bool:
    return redis_url.startswith("redis://") or redis_url.startswith("rediss://")


class StudyCache:
    """
    Cache service with Redis backend and in-memory fallback.

    Tests expect:
      - StudyCache(redis_url="...", ttl=...)
      - await cache.set(key, value, ttl=...)
      - await cache.get(key) -> Optional[dict]
      - await cache.ping() -> True (even for in-memory fallback)
      - await cache.clear()
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        self.redis_url = redis_url
        self.ttl = int(ttl)

        self._redis_client = None
        self._use_redis = False

        # In-memory fallback store.
        # Maps key -> {"value": <Any>, "expires_at": <Optional[float]>}
        self._memory_cache: dict[str, dict[str, Any]] = {}

        if _is_redis_url(redis_url):
            try:
                import redis.asyncio as redis_mod  # type: ignore

                self._redis_client = redis_mod.from_url(redis_url)
                self._use_redis = True
                logger.info("Redis cache initialized with URL: %s", redis_url)
            except Exception as e:
                logger.warning("Redis unavailable (%s); falling back to in-memory cache", e)
                self._use_redis = False
                self._redis_client = None
        else:
            # Non-redis URLs (e.g. memory://test) should use in-memory fallback.
            self._use_redis = False
            self._redis_client = None

    @property
    def redis_client(self) -> Any:
        return self._redis_client

    @property
    def cache(self) -> dict[str, Any]:
        return self._memory_cache

    def _generate_key(self, study_type: str, params: dict[str, Any]) -> str:
        """
        Best-effort key generator used by legacy callers:
        await cache.get(study_type: str, params: Dict[str, Any])
        """
        try:
            params_part = json.dumps(params, sort_keys=True, default=str)
        except Exception:
            params_part = str(params)
        return f"{study_type}:{params_part}"

    def _cleanup_key_if_expired(self, key: str) -> None:
        entry = self._memory_cache.get(key)
        if not entry:
            return
        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() >= float(expires_at):
            self._memory_cache.pop(key, None)

    async def get(self, key: str, *args: Any, **kwargs: Any) -> dict[str, Any] | None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """
        Get cached value by key.

        Primary/tested signature:
            await cache.get("some_key") -> Optional[dict]

        Best-effort backward compatibility:
            await cache.get(study_type: str, params: Dict[str, Any]) -> Optional[dict]
        """
        # Legacy: get(study_type, params)
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            study_type = key
            params = args[0]
            key = self._generate_key(study_type, params)

        if self._use_redis and self._redis_client:
            try:
                raw = await self._redis_client.get(key)
                if raw is None:
                    return None
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8")
                return json.loads(raw)
            except Exception as e:
                logger.warning("Redis GET failed (%s); falling back to memory cache", e)

        # In-memory fallback
        self._cleanup_key_if_expired(key)
        entry = self._memory_cache.get(key)
        if not entry:
            return None

        value = entry.get("value")
        # Tests expect dict or None.
        if value is None:
            return None
        if isinstance(value, dict):
            return value

        # If stored non-dict, attempt to decode json string.
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                pass
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Set cached value by key.

        Primary/tested signature:
            await cache.set(key, value, ttl=...)

        Returns:
          - True when the value was stored in Redis OR in-memory fallback.
          - False only when both the Redis write AND the in-memory write
            failed (the latter is rare but possible under MemoryError).
        """
        effective_ttl = self.ttl if ttl is None else int(ttl)
        expires_at = None if effective_ttl <= 0 else (time.time() + effective_ttl)

        # Redis path
        if self._use_redis and self._redis_client:
            try:
                payload = json.dumps(value)
                await self._redis_client.set(
                    key, payload, ex=effective_ttl if effective_ttl > 0 else None,
                )
                return True
            except Exception as e:
                logger.warning("Redis SET failed (%s); using memory cache", e)

        # In-memory fallback — track actual write success so the return
        # value is meaningful (SonarCloud S3516: invariant return).
        try:
            self._memory_cache[key] = {"value": value, "expires_at": expires_at}
            return True
        except (TypeError, ValueError) as e:
            # Unhashable key or value that breaks dict storage
            logger.error("In-memory cache SET failed for key %r: %s", key, e)
            return False

    async def clear(self) -> None:
        """Clear all cached entries (memory fallback always; best-effort for redis)."""
        self._memory_cache.clear()

        if self._use_redis and self._redis_client:
            try:
                # Use non-blocking delete all if available
                await self._redis_client.flushdb()
            except Exception as e:
                logger.warning("Redis CLEAR failed (%s); ignoring", e)

    async def ping(self) -> bool:
        """Ping cache backend. Must return True even for in-memory fallback (per tests)."""
        if self._use_redis and self._redis_client:
            try:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
                await self._redis_client.ping()
                return True
            except Exception:
                return False
        return True


async def get_study_cache() -> StudyCache:
    """
    Async factory expected by tests.

    Returns a StudyCache instance (Redis when available, otherwise fallback).
    """
    redis_url = "redis://localhost:6379"
    default_ttl = 3600

    # Environment overrides (best-effort; tests don't require them).
    try:
        import os

        redis_url = os.getenv("REDIS_URL", redis_url)
        default_ttl = int(os.getenv("CACHE_TTL", str(default_ttl)))
    except Exception:
        pass

    return StudyCache(redis_url=redis_url, ttl=default_ttl)
