"""
tests/test_concurrency_load_gate.py — In-Process Concurrency & Mock Load Testing Gate.

Validates application behavior under concurrent load using an in-process mock (ConcurrentMockRedis):
1. 50 concurrent health and probe requests with tight in-process p95 latency (< 0.25s).
2. In-process LockManager mutual exclusion simulation under concurrent coroutine contention.
3. In-process RedisTaskQueue enqueue and atomic dequeue simulation.
4. Integration test against a real distributed Redis server when REDIS_URL is provided.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from api.routes import app
from api.task_queue import JobStatus, RedisTaskQueue
from core.redis_state import LockManager


class ConcurrentMockRedis:
    """In-process thread/task safe mock Redis client (simulation only, not real distributed Redis)."""

    def __init__(self) -> None:
        self.hashes: Dict[str, Dict[str, str]] = {}
        self.strings: Dict[str, str] = {}
        self.lists: Dict[str, List[str]] = {}
        self.ttls: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        async with self._lock:
            bucket = self.hashes.setdefault(key, {})
            count = 0
            for k, v in mapping.items():
                if k not in bucket:
                    count += 1
                bucket[k] = str(v)
            return count

    async def hgetall(self, key: str) -> Dict[str, str]:
        async with self._lock:
            return dict(self.hashes.get(key, {}))

    async def hget(self, key: str, field: str) -> Optional[str]:
        async with self._lock:
            return self.hashes.get(key, {}).get(field)

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        async with self._lock:
            if nx and (key in self.strings or key in self.hashes):
                return False
            self.strings[key] = str(value)
            if ex:
                self.ttls[key] = time.monotonic() + ex
            elif px:
                self.ttls[key] = time.monotonic() + (px / 1000.0)
            return True

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            if key in self.ttls and time.monotonic() > self.ttls[key]:
                self.strings.pop(key, None)
                self.ttls.pop(key, None)
                return None
            return self.strings.get(key)

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        async with self._lock:
            self.ttls[key] = time.monotonic() + ttl_seconds
            return True

    async def delete(self, key: str) -> int:
        async with self._lock:
            c1 = 1 if self.hashes.pop(key, None) is not None else 0
            c2 = 1 if self.strings.pop(key, None) is not None else 0
            c3 = 1 if self.lists.pop(key, None) is not None else 0
            self.ttls.pop(key, None)
            return max(c1, c2, c3)

    async def rpush(self, key: str, value: str) -> int:
        async with self._lock:
            lst = self.lists.setdefault(key, [])
            lst.append(str(value))
            return len(lst)

    async def lpop(self, key: str) -> Optional[str]:
        async with self._lock:
            lst = self.lists.get(key, [])
            if lst:
                return lst.pop(0)
            return None

    async def blpop(self, key: str, timeout: int = 0) -> Optional[tuple[str, str]]:
        # Fast non-blocking simulation for testing
        val = await self.lpop(key)
        if val is not None:
            return (key, val)
        return None

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        async with self._lock:
            if "GET" in script and "DEL" in script:
                key = args[0]
                token = args[1]
                if self.strings.get(key) == token:
                    self.strings.pop(key, None)
                    self.ttls.pop(key, None)
                    return 1
                return 0
            return 0


@pytest.mark.asyncio
async def test_concurrent_health_probes_p95_latency() -> None:
    """Execute 50 concurrent in-process health check requests and assert p95 latency < 0.25s."""
    client = TestClient(app)
    latencies: List[float] = []

    loop = asyncio.get_event_loop()

    async def single_probe() -> int:
        start = time.perf_counter()
        resp = await loop.run_in_executor(None, client.get, "/health")
        duration = time.perf_counter() - start
        latencies.append(duration)
        return resp.status_code

    # Launch 50 concurrent requests
    results = await asyncio.gather(*(single_probe() for _ in range(50)))

    # Assert 100% success
    assert all(code == 200 for code in results), "Some health probe requests failed"
    assert len(results) == 50

    # Calculate p95 latency
    sorted_latencies = sorted(latencies)
    p95_idx = int(len(sorted_latencies) * 0.95)
    p95_val = sorted_latencies[p95_idx]

    # Assert p95 latency is sub-250ms for local in-process execution
    assert p95_val < 0.25, f"In-process p95 latency {p95_val:.3f}s exceeded 0.25s threshold"


@pytest.mark.asyncio
async def test_concurrent_distributed_locks_mutual_exclusion() -> None:
    """Test 20 concurrent coroutines competing for the same in-process mock lock.

    Guarantees within the local process:
    - At most ONE coroutine enters the critical section at any given time.
    - Zero deadlocks occur.
    - Note: This is an in-process asyncio.Lock simulation, not multi-replica distributed isolation.
    """
    mock_redis = ConcurrentMockRedis()
    lock_manager = LockManager(client=mock_redis)

    lock_name = "test:concurrency:critical_section"
    active_holders = 0
    max_concurrent_holders = 0
    successful_executions = 0
    lock_violations = 0

    async def worker(worker_id: int) -> None:
        nonlocal active_holders, max_concurrent_holders, successful_executions, lock_violations
        acquired = False
        for _ in range(50):
            try:
                async with lock_manager.lock(lock_name, ttl_seconds=5, timeout_ms=1000):
                    acquired = True
                    active_holders += 1
                    if active_holders > max_concurrent_holders:
                        max_concurrent_holders = active_holders
                    if active_holders > 1:
                        lock_violations += 1

                    # Simulate work in critical section
                    await asyncio.sleep(0.005)

                    active_holders -= 1
                    successful_executions += 1
                    break
            except TimeoutError:
                await asyncio.sleep(0.01)

        assert acquired, f"Worker {worker_id} timed out waiting for lock"

    # Launch 20 workers simultaneously
    await asyncio.gather(*(worker(i) for i in range(20)))

    assert max_concurrent_holders == 1, (
        f"Lock mutual exclusion failed: max {max_concurrent_holders} holders"
    )
    assert lock_violations == 0, (
        f"Detected {lock_violations} concurrent holders in critical section"
    )
    assert successful_executions == 20, f"Expected 20 executions, got {successful_executions}"


@pytest.mark.asyncio
async def test_concurrent_task_queue_atomic_processing() -> None:
    """Test concurrent enqueueing and dequeueing in RedisTaskQueue.

    Guarantees:
    - Multiple tasks enqueued concurrently are all preserved.
    - Dequeueing assigns each task to exactly one worker (no duplicates).
    """
    mock_redis = ConcurrentMockRedis()

    with patch("api.task_queue.get_redis", AsyncMock(return_value=mock_redis)):
        queue = RedisTaskQueue(queue_name="concurrent_study_jobs")

        total_tasks = 25
        enqueued_job_ids: List[str] = []

        # Concurrently enqueue 25 tasks
        async def enqueue_worker(i: int) -> str:
            job_id = await queue.enqueue(
                task_name="load_flow_study",
                payload={"bus_id": i, "voltage_setpoint": 1.02},
            )
            return job_id

        enqueued_job_ids = list(
            await asyncio.gather(*(enqueue_worker(i) for i in range(total_tasks)))
        )

        assert len(enqueued_job_ids) == total_tasks
        assert len(set(enqueued_job_ids)) == total_tasks

        # Concurrently dequeue all tasks across 5 workers
        processed_job_ids: List[str] = []
        lock = asyncio.Lock()

        async def dequeue_worker() -> None:
            while True:
                dequeued = await queue.dequeue(timeout_seconds=0)
                if not dequeued:
                    break
                job_id, task_name, payload = dequeued
                async with lock:
                    processed_job_ids.append(job_id)
                await queue.set_result(job_id, result={"status": "completed"})
                await asyncio.sleep(0.005)

        await asyncio.gather(*(dequeue_worker() for _ in range(5)))

        assert len(processed_job_ids) == total_tasks, (
            f"Expected {total_tasks} processed tasks, got {len(processed_job_ids)}"
        )
        assert set(processed_job_ids) == set(enqueued_job_ids), (
            "Processed job IDs do not match enqueued IDs"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_redis_distributed_lock_integration() -> None:
    """Live integration test against a real Redis server (requires REDIS_URL).

    Skipped automatically in CI/local runs where no live Redis instance is configured.
    """
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("Live Redis test skipped: REDIS_URL environment variable is not set.")

    import redis.asyncio as aioredis

    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        pytest.skip(f"Live Redis unreachable at {redis_url}: {exc}")

    lock_manager = LockManager(client=client)
    lock_name = "test:live_redis:integration_lock"

    try:
        async with lock_manager.lock(lock_name, ttl_seconds=5, timeout_ms=2000):
            val = await client.get(f"etap:lock:{lock_name}")
            assert val is not None
    finally:
        await client.delete(f"etap:lock:{lock_name}")
        await client.aclose()
