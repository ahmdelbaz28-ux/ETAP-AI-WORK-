"""
core/redis_state.py — Redis-backed persistent state for circuit breakers,
distributed locks, and agent workflow tracking.

Why this exists
---------------
The Python ``engine.resilience.CircuitBreaker`` stores all state in-process
memory.  On pod restart or horizontal scale-out this state is lost, causing
all circuit breakers to reset to CLOSED and potentially flood a recovering
downstream service.

This module provides a thin Redis adapter that:
 - Serialises / deserialises ``CircuitBreaker`` state to Redis hashes.
 - Offers a ``RedisDistributedLock`` for cross-process mutual exclusion.
 - Stores ``AgentWorkflowState`` so long-running studies survive pod restarts.

Usage
-----
    from core.redis_state import get_redis_state_client, CircuitBreakerRedisAdapter

    # At startup
    client = await get_redis_state_client()

    # Persist a circuit breaker
    adapter = CircuitBreakerRedisAdapter(client, "etap-worker")
    await adapter.save(breaker)

    # Restore on boot
    await adapter.restore(breaker)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "").strip()

# Optional async redis client — falls back gracefully if not installed
try:
    import redis.asyncio as aioredis  # type: ignore

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore
    REDIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: Optional[Any] = None


async def get_redis_state_client() -> Optional[Any]:
    """Return the shared async Redis client, or None if Redis is unavailable."""
    global _client
    if not REDIS_AVAILABLE or not _REDIS_URL:
        return None
    if _client is None:
        try:
            _client = aioredis.from_url(
                _REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            # Ping to confirm connection
            await _client.ping()
            logger.info("Redis state client connected: %s", _REDIS_URL.split("@")[-1])
        except Exception as exc:
            logger.warning("Redis unavailable — state will be in-memory only: %s", exc)
            _client = None
    return _client


async def close_redis_state_client() -> None:
    """Close the shared Redis connection (call during app shutdown)."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None


# ---------------------------------------------------------------------------
# Circuit Breaker Redis Adapter
# ---------------------------------------------------------------------------

_CB_PREFIX = "etap:cb:"
_CB_TTL = 7 * 24 * 3600  # 7 days


class CircuitBreakerRedisAdapter:
    """Persists and restores a ``CircuitBreaker`` state in Redis.

    The state is stored as a Redis hash under the key
    ``etap:cb:<breaker_name>``.
    """

    def __init__(self, client: Any, breaker_name: str) -> None:
        self._client = client
        self._name = breaker_name
        self._key = f"{_CB_PREFIX}{breaker_name}"

    async def save(self, breaker: Any) -> None:
        """Persist circuit breaker state to Redis (best-effort)."""
        if self._client is None:
            return
        try:
            state_dict = {
                "state": breaker._state,
                "failure_count": str(breaker._failure_count),
                "total_calls": str(breaker._total_calls),
                "failed_calls": str(breaker._failed_calls),
                "last_failure_time": str(breaker._last_failure_time or ""),
                "state_changes": str(breaker._state_changes),
                "saved_at": str(time.time()),
            }
            await self._client.hset(self._key, mapping=state_dict)
            await self._client.expire(self._key, _CB_TTL)
        except Exception as exc:
            logger.debug("Circuit breaker Redis save failed (non-fatal): %s", exc)

    async def restore(self, breaker: Any) -> bool:
        """Restore circuit breaker state from Redis.

        Returns True if state was restored, False if no saved state exists.
        """
        if self._client is None:
            return False
        try:
            data = await self._client.hgetall(self._key)
            if not data:
                return False

            from engine.resilience import CircuitBreakerState

            breaker._state = data.get("state", CircuitBreakerState.CLOSED)
            breaker._failure_count = int(data.get("failure_count", 0))
            breaker._total_calls = int(data.get("total_calls", 0))
            breaker._failed_calls = int(data.get("failed_calls", 0))
            lft = data.get("last_failure_time", "")
            breaker._last_failure_time = float(lft) if lft else None
            breaker._state_changes = int(data.get("state_changes", 0))
            logger.info(
                "Circuit breaker '%s' restored from Redis (state=%s)",
                self._name,
                breaker._state,
            )
            return True
        except Exception as exc:
            logger.debug("Circuit breaker Redis restore failed (non-fatal): %s", exc)
            return False


# ---------------------------------------------------------------------------
# Distributed Lock
# ---------------------------------------------------------------------------

_LOCK_PREFIX = "etap:lock:"
_DEFAULT_LOCK_TTL = 30  # seconds


class RedisDistributedLock:
    """Simple Redis-backed distributed lock (SET NX PX).

    Prevents duplicate Celery tasks, double-submissions, etc.

    Usage::

        client = await get_redis_state_client()
        lock = RedisDistributedLock(client, "study:abc123")
        acquired = await lock.acquire(timeout_ms=5000)
        if acquired:
            try:
                ...  # do work
            finally:
                await lock.release()
    """

    def __init__(self, client: Any, resource: str, ttl_seconds: int = _DEFAULT_LOCK_TTL) -> None:
        self._client = client
        self._key = f"{_LOCK_PREFIX}{resource}"
        self._ttl_ms = ttl_seconds * 1000
        self._token: Optional[str] = None

    async def acquire(self, timeout_ms: int = 0) -> bool:
        """Attempt to acquire the lock.

        Parameters
        ----------
        timeout_ms : int
            Maximum time to wait in ms. 0 = try once and return immediately.

        Returns True if lock was acquired.
        """
        if self._client is None:
            return True  # no Redis — allow (single-process fallback)

        import uuid

        token = str(uuid.uuid4())
        deadline = time.monotonic() + timeout_ms / 1000

        while True:
            result = await self._client.set(
                self._key, token, nx=True, px=self._ttl_ms
            )
            if result:
                self._token = token
                return True
            if timeout_ms == 0 or time.monotonic() >= deadline:
                return False
            await __import__("asyncio").sleep(0.05)

    async def release(self) -> None:
        """Release the lock (only if we still own it)."""
        if self._client is None or self._token is None:
            return
        # Lua script for atomic check-and-delete
        script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        try:
            await self._client.eval(script, 1, self._key, self._token)
        except Exception as exc:
            logger.debug("Lock release failed (non-fatal): %s", exc)
        finally:
            self._token = None

    async def __aenter__(self) -> RedisDistributedLock:
        await self.acquire()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.release()


# ---------------------------------------------------------------------------
# Agent Workflow State
# ---------------------------------------------------------------------------

_WF_PREFIX = "etap:workflow:"
_WF_TTL = 24 * 3600  # 24 hours


async def save_workflow_state(
    task_id: str,
    state: dict,
    client: Optional[Any] = None,
    ttl: int = _WF_TTL,
) -> None:
    """Persist agent workflow state to Redis.

    Parameters
    ----------
    task_id : str
        Unique study / task identifier.
    state : dict
        JSON-serialisable workflow state snapshot.
    client : optional
        Redis client. Defaults to the shared singleton.
    ttl : int
        TTL in seconds (default 24 hours).
    """
    r = client or await get_redis_state_client()
    if r is None:
        return
    key = f"{_WF_PREFIX}{task_id}"
    try:
        await r.set(key, json.dumps(state, default=str), ex=ttl)
    except Exception as exc:
        logger.debug("Workflow state save failed (non-fatal): %s", exc)


async def load_workflow_state(
    task_id: str,
    client: Optional[Any] = None,
) -> Optional[dict]:
    """Load agent workflow state from Redis.

    Returns the state dict or None if no state was saved.
    """
    r = client or await get_redis_state_client()
    if r is None:
        return None
    key = f"{_WF_PREFIX}{task_id}"
    try:
        raw = await r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Workflow state load failed (non-fatal): %s", exc)
    return None


async def delete_workflow_state(
    task_id: str,
    client: Optional[Any] = None,
) -> None:
    """Remove a workflow state entry from Redis."""
    r = client or await get_redis_state_client()
    if r is None:
        return
    key = f"{_WF_PREFIX}{task_id}"
    try:
        await r.delete(key)
    except Exception as exc:
        logger.debug("Workflow state delete failed (non-fatal): %s", exc)
