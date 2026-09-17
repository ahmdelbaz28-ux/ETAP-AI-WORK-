"""
tests/test_fix22_redis_shared_state.py — Verification for FIX-22 (Redis Shared State).

Tests:
1. Multi-replica shared session persistence (survives replica restart, shared across instances).
2. Distributed Lock mutual exclusion and atomic check-and-delete release.
3. Redis distributed task queue enqueue/dequeue/result lifecycle.
4. SessionMiddleware integration attaching session state to request.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from api.session_redis import RedisSessionStore, SessionMiddleware
from api.task_queue import JobStatus, RedisTaskQueue
from core.redis_state import LockManager, RedisDistributedLock


class MockRedisClient:
    """In-memory Async Redis client simulating Redis server semantics for unit testing."""

    def __init__(self) -> None:
        self.hashes: Dict[str, Dict[str, str]] = {}
        self.strings: Dict[str, str] = {}
        self.lists: Dict[str, List[str]] = {}
        self.ttls: Dict[str, float] = {}

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        bucket = self.hashes.setdefault(key, {})
        count = 0
        for k, v in mapping.items():
            if k not in bucket:
                count += 1
            bucket[k] = str(v)
        return count

    async def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def hget(self, key: str, field: str) -> Optional[str]:
        return self.hashes.get(key, {}).get(field)

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        if nx and (key in self.strings or key in self.hashes):
            return False
        self.strings[key] = str(value)
        if ex:
            self.ttls[key] = time.monotonic() + ex
        elif px:
            self.ttls[key] = time.monotonic() + (px / 1000.0)
        return True

    async def get(self, key: str) -> Optional[str]:
        if key in self.ttls and time.monotonic() > self.ttls[key]:
            self.strings.pop(key, None)
            self.ttls.pop(key, None)
            return None
        return self.strings.get(key)

    async def exists(self, key: str) -> int:
        return int(key in self.hashes or key in self.strings or key in self.lists)

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        self.ttls[key] = time.monotonic() + ttl_seconds
        return True

    async def delete(self, key: str) -> int:
        c1 = 1 if self.hashes.pop(key, None) is not None else 0
        c2 = 1 if self.strings.pop(key, None) is not None else 0
        c3 = 1 if self.lists.pop(key, None) is not None else 0
        self.ttls.pop(key, None)
        return max(c1, c2, c3)

    async def rpush(self, key: str, value: str) -> int:
        lst = self.lists.setdefault(key, [])
        lst.append(str(value))
        return len(lst)

    async def lpop(self, key: str) -> Optional[str]:
        lst = self.lists.get(key, [])
        if lst:
            return lst.pop(0)
        return None

    async def blpop(self, key: str, timeout: int = 0) -> Optional[tuple[str, str]]:
        val = await self.lpop(key)
        if val is not None:
            return (key, val)
        return None

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        # Atomic lock release check-and-del simulation
        if "GET" in script and "DEL" in script:
            key, expected_token = args[0], args[1]
            if self.strings.get(key) == expected_token:
                self.strings.pop(key, None)
                self.ttls.pop(key, None)
                return 1
            return 0
        return 0


# ---------------------------------------------------------------------------
# Tests for FIX-22
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_replica_session_persistence() -> None:
    """Verify session survives replica restarts and is visible across multiple replicas."""
    mock_redis = MockRedisClient()

    with patch("api.session_redis.get_redis", AsyncMock(return_value=mock_redis)):
        store_replica_1 = RedisSessionStore(ttl_seconds=3600)
        store_replica_2 = RedisSessionStore(ttl_seconds=3600)

        # 1. Replica 1 creates a user session
        session_id = await store_replica_1.create_session(
            user_id="eng_ahmed_01",
            initial_data={"project_id": "proj-substation-400kv", "role": "lead_engineer"},
        )
        assert session_id is not None
        assert len(session_id) >= 32

        # 2. Replica 2 reads the session created by Replica 1
        session_data = await store_replica_2.get_session(session_id)
        assert session_data is not None
        assert session_data["user_id"] == "eng_ahmed_01"
        assert session_data["data"]["project_id"] == "proj-substation-400kv"
        assert session_data["data"]["role"] == "lead_engineer"

        # 3. Replica 2 updates state (e.g. study parameter modification)
        updated = await store_replica_2.update_session(
            session_id,
            {"project_id": "proj-substation-400kv", "active_study": "short_circuit_iec60909"},
        )
        assert updated is True

        # 4. Replica 1 verifies state updated by Replica 2
        r1_read = await store_replica_1.get_session(session_id)
        assert r1_read is not None
        assert r1_read["data"]["active_study"] == "short_circuit_iec60909"

        # 5. Terminate session from Replica 1
        deleted = await store_replica_1.delete_session(session_id)
        assert deleted is True

        # 6. Replica 2 confirms session is invalidated
        assert await store_replica_2.get_session(session_id) is None


@pytest.mark.asyncio
async def test_distributed_lock_prevents_race_conditions() -> None:
    """Verify RedisDistributedLock provides mutual exclusion across parallel tasks."""
    mock_redis = MockRedisClient()

    lock1 = RedisDistributedLock(mock_redis, "breaker_study_101", ttl_seconds=10)
    lock2 = RedisDistributedLock(mock_redis, "breaker_study_101", ttl_seconds=10)

    # Worker 1 acquires the lock
    acquired_1 = await lock1.acquire(timeout_ms=100)
    assert acquired_1 is True

    # Worker 2 attempts to acquire the same lock -> must fail immediately
    acquired_2 = await lock2.acquire(timeout_ms=50)
    assert acquired_2 is False

    # Worker 1 releases the lock
    await lock1.release()

    # Now Worker 2 can acquire the lock
    acquired_2_retry = await lock2.acquire(timeout_ms=100)
    assert acquired_2_retry is True
    await lock2.release()


@pytest.mark.asyncio
async def test_lock_manager_context_manager() -> None:
    """Verify LockManager context manager auto-releases distributed locks."""
    mock_redis = MockRedisClient()
    mgr = LockManager(client=mock_redis)

    async with mgr.lock("transformer_tx1", ttl_seconds=5) as lock:
        # Inside context, second attempt must time out
        with pytest.raises(TimeoutError, match="Could not acquire distributed lock"):
            async with mgr.lock("transformer_tx1", timeout_ms=50):
                pass

    # Outside context, lock is released and can be acquired again
    async with mgr.lock("transformer_tx1", timeout_ms=100):
        pass


@pytest.mark.asyncio
async def test_redis_task_queue_execution_lifecycle() -> None:
    """Verify distributed task queue enqueue, running state, and result retrieval."""
    mock_redis = MockRedisClient()

    with patch("api.task_queue.get_redis", AsyncMock(return_value=mock_redis)):
        queue = RedisTaskQueue(queue_name="load_flow_studies")

        # 1. Enqueue job
        job_id = await queue.enqueue(
            task_name="newton_raphson_solve",
            payload={"bus_count": 14, "tolerance": 1e-4},
        )
        assert job_id.startswith("job-")
        assert await queue.get_status(job_id) == JobStatus.QUEUED

        # 2. Worker dequeues job
        dequeued = await queue.dequeue(timeout_seconds=0)
        assert dequeued is not None
        jid, task_name, payload = dequeued
        assert jid == job_id
        assert task_name == "newton_raphson_solve"
        assert payload["bus_count"] == 14
        assert await queue.get_status(job_id) == JobStatus.RUNNING

        # 3. Worker sets result
        stored = await queue.set_result(
            job_id,
            result={"converged": True, "iterations": 4, "total_losses_mw": 0.42},
        )
        assert stored is True
        assert await queue.get_status(job_id) == JobStatus.COMPLETED

        # 4. Client retrieves result
        res = await queue.get_result(job_id)
        assert res is not None
        assert res["converged"] is True
        assert res["iterations"] == 4


def test_session_middleware_integration() -> None:
    """Verify SessionMiddleware attaches Redis session to Starlette request."""
    mock_redis = MockRedisClient()

    with patch("api.session_redis.get_redis", AsyncMock(return_value=mock_redis)):
        store = RedisSessionStore()

        # Seed session
        loop = asyncio.get_event_loop()
        session_id = loop.run_until_complete(
            store.create_session("engineer_test", {"org": "NationalGrid"})
        )

        app = Starlette()
        app.add_middleware(SessionMiddleware, store=store)

        @app.route("/profile")
        async def profile_handler(request: Request) -> JSONResponse:
            session = getattr(request.state, "session", None)
            if not session:
                return JSONResponse({"authenticated": False}, status_code=401)
            return JSONResponse(
                {
                    "authenticated": True,
                    "user_id": session["user_id"],
                    "org": session["data"].get("org"),
                }
            )

        client = TestClient(app)

        # 1. Request without session header
        resp_unauth = client.get("/profile")
        assert resp_unauth.status_code == 401

        # 2. Request with valid X-Session-ID header
        resp_auth = client.get("/profile", headers={"X-Session-ID": session_id})
        assert resp_auth.status_code == 200
        assert resp_auth.json()["authenticated"] is True
        assert resp_auth.json()["user_id"] == "engineer_test"
        assert resp_auth.json()["org"] == "NationalGrid"
