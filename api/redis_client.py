"""
api/redis_client.py — Shared Redis client for distributed singletons.

Supports distributed TokenBudgetManager, SemanticCache, RAGRetriever, and PromptRegistry.
Includes connection health verification and loop-safe client management.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover
    redis_async = None  # type: ignore

_redis_client: Optional[redis_async.Redis] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def get_redis() -> Optional[redis_async.Redis]:
    """Retrieve or create the shared Redis client for the current event loop."""
    global _redis_client, _client_loop
    if redis_async is None:
        return None

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    # Recreate client if the running event loop has changed (e.g. pytest-asyncio runs)
    if _redis_client is not None and _client_loop is not None and current_loop is not _client_loop:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
        _client_loop = None

    if _redis_client is None:
        url = get_redis_url()
        max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0"))
        socket_connect_timeout = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0"))
        try:
            _redis_client = redis_async.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=max_connections,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
            )
            _client_loop = current_loop
        except Exception as exc:
            logger.warning("Failed to initialize Redis client from %s: %s", url, exc)
            return None

    return _redis_client


async def is_redis_available() -> bool:
    """Check if the configured Redis server is currently reachable and responding to PING."""
    try:
        client = await get_redis()
        if client is None:
            return False
        res = await client.ping()
        return bool(res)
    except Exception as exc:
        logger.debug("Redis availability check failed: %s", exc)
        return False


async def close_redis() -> None:
    """Safely close the shared Redis client."""
    global _redis_client, _client_loop
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            logger.debug("Error while closing Redis client: %s", exc)
        finally:
            _redis_client = None
            _client_loop = None


def reset_redis_client() -> None:
    """Synchronously reset the shared Redis client reference for test isolation."""
    global _redis_client, _client_loop
    if _redis_client is not None:
        try:
            pool = getattr(_redis_client, "connection_pool", None)
            if pool is not None:
                pool.disconnect()
        except Exception:
            pass
    _redis_client = None
    _client_loop = None
