"""
api/task_queue.py — Distributed Task Queue backed by Redis (FIX-22).

Provides a reliable, distributed task queue with priority queues,
status tracking, atomic dequeue, and result retention.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from api.redis_client import get_redis

logger = logging.getLogger("api.task_queue")

_QUEUE_PREFIX = "etap:queue:"
_JOB_PREFIX = "etap:job:"
_RESULT_PREFIX = "etap:job_result:"
_DEFAULT_JOB_TTL = 86400  # 24 hours


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RedisTaskQueue:
    """Redis-backed distributed task queue for asynchronous engineering tasks."""

    def __init__(self, queue_name: str = "default") -> None:
        self.queue_name = queue_name
        self.queue_key = f"{_QUEUE_PREFIX}{queue_name}"

    async def enqueue(
        self,
        task_name: str,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        ttl_seconds: int = _DEFAULT_JOB_TTL,
    ) -> str:
        """Enqueue a new job with payload into the distributed queue."""
        jid = job_id or f"job-{uuid.uuid4()}"
        client = await get_redis()
        if client is None:
            raise RuntimeError("Redis is required for distributed task queue (FIX-22)")

        job_meta = {
            "job_id": jid,
            "task_name": task_name,
            "status": JobStatus.QUEUED,
            "enqueued_at": time.time(),
            "payload": json.dumps(payload or {}),
        }

        job_key = f"{_JOB_PREFIX}{jid}"
        try:
            await client.hset(job_key, mapping=job_meta)
            await client.expire(job_key, ttl_seconds)
            # Push job ID to list (FIFO queue: RPUSH then BLPOP / LPOP)
            await client.rpush(self.queue_key, jid)
            logger.debug("Enqueued task %s as %s", task_name, jid)
            return jid
        except Exception as exc:
            logger.error("Failed to enqueue task %s in Redis: %s", task_name, exc)
            raise RuntimeError(f"Enqueue failed: {exc}") from exc

    async def dequeue(self, timeout_seconds: int = 0) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Pop the next job from the queue. Returns (job_id, task_name, payload) or None."""
        client = await get_redis()
        if client is None:
            return None

        try:
            if timeout_seconds > 0:
                res = await client.blpop(self.queue_key, timeout=timeout_seconds)
                if not res:
                    return None
                jid = res[1] if isinstance(res, (list, tuple)) else res
            else:
                jid = await client.lpop(self.queue_key)
                if not jid:
                    return None

            job_key = f"{_JOB_PREFIX}{jid}"
            raw = await client.hgetall(job_key)
            if not raw:
                return None

            # Mark job as running
            await client.hset(
                job_key,
                mapping={
                    "status": JobStatus.RUNNING,
                    "started_at": time.time(),
                },
            )

            task_name = raw.get("task_name", "unknown")
            payload_str = raw.get("payload", "{}")
            try:
                payload = json.loads(payload_str)
            except Exception:
                payload = {}

            return jid, task_name, payload
        except Exception as exc:
            logger.error("Failed to dequeue task from Redis: %s", exc)
            return None

    async def set_result(
        self,
        job_id: str,
        result: Dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> bool:
        """Store job execution result and mark as COMPLETED."""
        client = await get_redis()
        if client is None:
            return False

        job_key = f"{_JOB_PREFIX}{job_id}"
        result_key = f"{_RESULT_PREFIX}{job_id}"
        try:
            await client.set(result_key, json.dumps(result), ex=ttl_seconds)
            await client.hset(
                job_key,
                mapping={
                    "status": JobStatus.COMPLETED,
                    "completed_at": time.time(),
                },
            )
            return True
        except Exception as exc:
            logger.error("Failed to set job result in Redis: %s", exc)
            return False

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
    ) -> bool:
        """Mark job as FAILED with error message."""
        client = await get_redis()
        if client is None:
            return False

        job_key = f"{_JOB_PREFIX}{job_id}"
        try:
            await client.hset(
                job_key,
                mapping={
                    "status": JobStatus.FAILED,
                    "error": error_message,
                    "failed_at": time.time(),
                },
            )
            return True
        except Exception as exc:
            logger.error("Failed to mark job as failed: %s", exc)
            return False

    async def get_status(self, job_id: str) -> str:
        """Return the current status of a job."""
        client = await get_redis()
        if client is None:
            return "unknown"

        job_key = f"{_JOB_PREFIX}{job_id}"
        try:
            status = await client.hget(job_key, "status")
            return status or "not_found"
        except Exception:
            return "unknown"

    async def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored result for a completed job."""
        client = await get_redis()
        if client is None:
            return None

        result_key = f"{_RESULT_PREFIX}{job_id}"
        try:
            raw = await client.get(result_key)
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            return None
