"""
etap_integration/worker_registry.py — ETAP Windows Worker heartbeat and registration.

Why this exists
---------------
The ETAP Windows worker runs as an isolated Windows container (or bare-metal
Windows server) outside the main Linux pod cluster.  Without explicit health
registration the Linux services have no way to know whether:

 - The worker is alive
 - How many workers are available
 - Which worker last processed a job
 - When a worker last failed

This module provides:

 1. ``WorkerRegistry`` — Redis-backed pool of alive workers (refreshed by heartbeat).
 2. ``ETAPWorkerHeartbeat`` — background thread that sends heartbeats to Redis every 30s.
 3. ``get_available_workers()`` — returns a list of workers that sent a heartbeat
    within the last 90 seconds (3× heartbeat interval → safe stale threshold).
 4. FastAPI router ``/etap-worker/...`` endpoints that the Linux gateway calls
    to discover and route jobs to healthy Windows workers.

Architecture
------------

  Linux Services
       │
       ▼
  Engineering Gateway
  (calls /etap-worker/workers to discover pool)
       │
       ▼
  Windows ETAP Worker Pool (each worker registers via heartbeat)
       │
       ▼
  ETAP COM Automation

Usage (on Windows worker)
-------------------------
    import asyncio
    from etap_integration.worker_registry import ETAPWorkerHeartbeat, start_heartbeat

    heartbeat = ETAPWorkerHeartbeat(worker_id="etap-win-01", redis_url="redis://...")
    asyncio.create_task(heartbeat.run())

Usage (on Linux gateway)
------------------------
    from etap_integration.worker_registry import WorkerRegistry

    registry = WorkerRegistry(redis_url=os.getenv("REDIS_URL"))
    workers = await registry.get_available_workers()
    if not workers:
        raise HTTPException(503, "No ETAP Windows workers available")
    target = workers[0]  # pick first available (or implement load balancing)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import socket
import time
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REGISTRY_PREFIX = "etap:worker:registry:"
_HEARTBEAT_INTERVAL = 30  # seconds — worker sends HB every 30s
_WORKER_TTL = 90  # seconds — worker considered dead after 90s
_WORKER_CAPABILITY_VERSION = "2.1.0"

# ---------------------------------------------------------------------------
# Redis connection helper
# ---------------------------------------------------------------------------

_redis_client: Any | None = None


def _get_sync_redis(redis_url: str) -> Any | None:
    """Return a synchronous Redis client (used by the heartbeat thread)."""
    try:
        import redis as _redis  # type: ignore

        return _redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=5)
    except Exception as exc:
        logger.warning("Redis unavailable for worker registry: %s", exc)
        return None


async def _get_async_redis(redis_url: str) -> Any | None:
    """Return an async Redis client (used by FastAPI endpoints)."""
    try:
        import redis.asyncio as aioredis  # type: ignore

        r = aioredis.from_url(redis_url, socket_timeout=5)
        await r.ping()
        return r
    except Exception as exc:
        logger.warning("Async Redis unavailable for worker registry: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Worker info structure
# ---------------------------------------------------------------------------


def _build_worker_info(worker_id: str) -> dict[str, Any]:
    """Build the worker info dict that is registered in Redis."""
    return {
        "worker_id": worker_id,
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "pid": os.getpid(),
        "capability_version": _WORKER_CAPABILITY_VERSION,
        "registered_at": time.time(),
        "last_heartbeat": time.time(),
        "status": "idle",
    }


# ---------------------------------------------------------------------------
# ETAPWorkerHeartbeat — runs on the Windows worker
# ---------------------------------------------------------------------------


class ETAPWorkerHeartbeat:
    """Background coroutine that keeps the Windows worker registered in Redis.

    Parameters
    ----------
    worker_id : str
        Unique identifier for this worker instance.
        Defaults to a combination of hostname + PID.
    redis_url : str
        Redis connection URL.
    interval : int
        Heartbeat interval in seconds (default 30).
    """

    def __init__(
        self,
        worker_id: str | None = None,
        redis_url: str | None = None,
        interval: int = _HEARTBEAT_INTERVAL,
    ) -> None:
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.interval = interval
        self._stop_event = asyncio.Event()
        self._redis: Any | None = None
        self._key = f"{_REGISTRY_PREFIX}{self.worker_id}"

    async def _get_redis(self) -> Any | None:
        if self._redis is None:
            self._redis = await _get_async_redis(self.redis_url)
        return self._redis

    async def register(self, status: str = "idle") -> None:
        """Register / refresh this worker in Redis."""
        r = await self._get_redis()
        if r is None:
            logger.warning("Cannot register worker — Redis unavailable")
            return
        info = _build_worker_info(self.worker_id)
        info["status"] = status
        info["last_heartbeat"] = time.time()
        try:
            await r.set(self._key, json.dumps(info), ex=_WORKER_TTL)
            logger.debug("Worker heartbeat sent: %s", self.worker_id)
        except Exception as exc:
            logger.warning("Worker heartbeat failed: %s", exc)

    async def deregister(self) -> None:
        """Remove this worker from the registry (called on shutdown)."""
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.delete(self._key)
            logger.info("Worker deregistered: %s", self.worker_id)
        except Exception as exc:
            logger.warning("Worker deregister failed: %s", exc)

    async def set_status(self, status: str) -> None:
        """Update the worker status without full re-registration."""
        await self.register(status=status)

    async def run(self) -> None:
        """Run the heartbeat loop indefinitely until stop() is called."""
        logger.info(
            "ETAP worker heartbeat started (worker_id=%s, interval=%ds)",
            self.worker_id,
            self.interval,
        )
        await self.register(status="starting")
        try:
            while not self._stop_event.is_set():
                await self.register(status="idle")
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
                except TimeoutError:
                    pass  # normal — just heartbeat interval elapsed
        finally:
            await self.deregister()
            logger.info("ETAP worker heartbeat stopped: %s", self.worker_id)

    def stop(self) -> None:
        """Signal the heartbeat loop to stop."""
        self._stop_event.set()


# ---------------------------------------------------------------------------
# WorkerRegistry — used by the Linux gateway to discover workers
# ---------------------------------------------------------------------------


class WorkerRegistry:
    """Queries Redis to discover healthy ETAP Windows workers.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    stale_threshold : int
        Workers that haven't sent a heartbeat within this many seconds
        are excluded (default 90).
    """

    def __init__(
        self,
        redis_url: str | None = None,
        stale_threshold: int = _WORKER_TTL,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.stale_threshold = stale_threshold
        self._redis: Any | None = None

    async def _get_redis(self) -> Any | None:
        if self._redis is None:
            self._redis = await _get_async_redis(self.redis_url)
        return self._redis

    async def get_available_workers(self) -> list[dict[str, Any]]:
        """Return a list of workers that are alive and available."""
        r = await self._get_redis()
        if r is None:
            return []
        try:
            keys = await r.keys(f"{_REGISTRY_PREFIX}*")
            now = time.time()
            workers: list[dict[str, Any]] = []
            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    info = json.loads(raw)
                    last_hb = float(info.get("last_heartbeat", 0))
                    if now - last_hb <= self.stale_threshold:
                        workers.append(info)
                except Exception:
                    continue
            # Sort by last heartbeat (most recent first)
            workers.sort(key=lambda w: float(w.get("last_heartbeat", 0)), reverse=True)
            return workers
        except Exception as exc:
            logger.warning("Worker registry query failed: %s", exc)
            return []

    async def get_worker_count(self) -> int:
        """Return the number of currently healthy workers."""
        return len(await self.get_available_workers())

    async def is_any_worker_available(self) -> bool:
        """Return True if at least one healthy worker exists."""
        return await self.get_worker_count() > 0


# ---------------------------------------------------------------------------
# FastAPI router — exposes worker pool status to the Linux gateway
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/etap-worker", tags=["etap-windows-worker"])

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@router.get("/workers")
async def list_workers():
    """Return the pool of healthy ETAP Windows workers."""
    registry = WorkerRegistry(redis_url=_REDIS_URL)
    workers = await registry.get_available_workers()
    return {
        "count": len(workers),
        "workers": workers,
        "healthy": len(workers) > 0,
        "checked_at": time.time(),
    }


@router.get("/workers/health")
async def worker_pool_health():
    """Health check for the ETAP Windows worker pool.

    Returns 200 if ≥1 worker is healthy, 503 if no workers are available.
    Used by the Linux services circuit breaker.
    """
    registry = WorkerRegistry(redis_url=_REDIS_URL)
    available = await registry.get_available_workers()
    if not available:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "message": "No ETAP Windows workers are currently registered",
                "worker_count": 0,
            },
        )
    return {
        "status": "healthy",
        "worker_count": len(available),
        "workers": [w["worker_id"] for w in available],
    }


@router.post("/register")
async def register_worker(worker_id: str, host: str, port: int = 8081):
    """Allow a Windows worker to self-register (alternative to Redis heartbeat).

    This endpoint is useful when the Windows worker cannot reach Redis directly
    but can reach the Linux gateway over HTTP.
    """
    r = await _get_async_redis(_REDIS_URL)
    if r is None:
        raise HTTPException(status_code=503, detail="Registry unavailable — Redis not connected")

    info = {
        "worker_id": worker_id,
        "host": host,
        "port": port,
        "registered_at": time.time(),
        "last_heartbeat": time.time(),
        "status": "idle",
        "registration_mode": "http",
    }
    key = f"{_REGISTRY_PREFIX}{worker_id}"
    await r.set(key, json.dumps(info), ex=_WORKER_TTL)
    return {"registered": True, "worker_id": worker_id, "ttl_seconds": _WORKER_TTL}


@router.post("/heartbeat")
async def worker_heartbeat(worker_id: str):
    """HTTP-based heartbeat from a Windows worker.

    Used when the worker cannot connect to Redis directly.
    """
    r = await _get_async_redis(_REDIS_URL)
    if r is None:
        raise HTTPException(status_code=503, detail="Registry unavailable")

    key = f"{_REGISTRY_PREFIX}{worker_id}"
    raw = await r.get(key)
    if raw:
        info = json.loads(raw)
        info["last_heartbeat"] = time.time()
        info["status"] = "idle"
        await r.set(key, json.dumps(info), ex=_WORKER_TTL)
    else:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not registered")

    return {"acknowledged": True, "worker_id": worker_id}
