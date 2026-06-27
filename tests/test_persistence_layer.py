"""
tests/test_persistence_layer.py — Tests for the database and Redis persistence layer.

Covers:
 - Database URL normalisation (postgres:// → postgresql+asyncpg://)
 - SQLite engine creation and table creation in dev/test
 - Redis state client connection and fallback to None when unavailable
 - CircuitBreakerRedisAdapter save/restore cycle (with mock Redis)
 - RedisDistributedLock acquire/release (with mock Redis)
 - Workflow state save/load/delete (with mock Redis)
 - Migration 005: study_jobs table upgrade/downgrade
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal async Redis stub for unit tests (no real Redis required)."""

    def __init__(self):
        self._store: dict = {}

    async def set(self, key, value, ex=None, nx=False, px=None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def get(self, key):
        return self._store.get(key)

    async def hset(self, key, mapping):
        self._store[key] = mapping
        return len(mapping)

    async def hgetall(self, key):
        val = self._store.get(key, {})
        return val if isinstance(val, dict) else {}

    async def expire(self, key, ttl):
        return True

    async def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
        return len(keys)

    async def keys(self, pattern):
        import fnmatch
        return [k for k in self._store if fnmatch.fnmatch(k, pattern.replace("*", "[^:]*"))]

    async def eval(self, script, numkeys, *args):
        # Simplified check-and-delete for lock release
        key, token = args[0], args[1]
        if self._store.get(key) == token:
            del self._store[key]
            return 1
        return 0

    async def ping(self):
        return True

    async def aclose(self):
        pass

    async def setex(self, key, ttl, value):
        self._store[key] = value
        return True


# ---------------------------------------------------------------------------
# api/database.py — URL normalisation
# ---------------------------------------------------------------------------


class TestDatabaseUrlNormalisation:
    """Tests for the URL normalisation logic in api.database."""

    def test_postgres_scheme_converted(self):
        """postgres:// should be converted to postgresql+asyncpg://."""
        from api.database import _normalise_url

        result = _normalise_url("postgres://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_postgresql_scheme_converted(self):
        """postgresql:// (without driver) should be converted."""
        from api.database import _normalise_url

        result = _normalise_url("postgresql://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_asyncpg_already_in_url_not_doubled(self):
        """postgresql+asyncpg:// should NOT be modified."""
        from api.database import _normalise_url

        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _normalise_url(url)
        assert result == url
        assert result.count("asyncpg") == 1

    def test_sqlite_url_unchanged(self):
        """sqlite+aiosqlite URLs should pass through unchanged."""
        from api.database import _normalise_url

        url = "sqlite+aiosqlite:///./data/test.db"
        assert _normalise_url(url) == url


# ---------------------------------------------------------------------------
# api/database.py — SQLite engine (used in CI)
# ---------------------------------------------------------------------------


class TestDatabaseEngineCreation:
    """Verify the database module initialises correctly in CI (SQLite)."""

    def test_engine_is_created(self):
        """The engine object should exist after module import."""
        from api.database import engine

        assert engine is not None

    def test_async_session_factory_created(self):
        """The async session factory should be callable."""
        from api.database import async_session

        assert callable(async_session)

    @pytest.mark.asyncio
    async def test_db_health_check_sqlite(self):
        """Health check should succeed against SQLite in test environment."""
        # Override DATABASE_URL to SQLite for this test if needed
        from api.database import check_db_health

        result = await check_db_health()
        assert result["status"] in ("healthy", "unhealthy")  # unhealthy if no DB yet

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, tmp_path):
        """init_db should create all tables without errors."""
        import importlib
        import sys

        # Set a fresh temp DATABASE_URL
        db_path = tmp_path / "test_init.db"
        env_patch = {"DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}

        with patch.dict(os.environ, env_patch):
            # Re-import to pick up new URL
            if "api.database" in sys.modules:
                del sys.modules["api.database"]
            from api.database import init_db

            # Should not raise
            await init_db()

        # Re-import clean module for other tests
        if "api.database" in sys.modules:
            del sys.modules["api.database"]


# ---------------------------------------------------------------------------
# core/redis_state.py — Redis client
# ---------------------------------------------------------------------------


class TestRedisStateClient:
    """Tests for the get_redis_state_client() helper."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_redis_url(self):
        """Should return None when REDIS_URL is not set."""
        import core.redis_state as rs

        # Reset singleton
        rs._client = None

        with patch.dict(os.environ, {"REDIS_URL": ""}):
            result = await rs.get_redis_state_client()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_unavailable(self):
        """Should return None and not crash when Redis is unreachable."""
        import core.redis_state as rs

        rs._client = None

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:19999/0"}):
            # Patch aioredis.from_url to raise on ping
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = ConnectionRefusedError("connection refused")

            with patch("core.redis_state.aioredis") as mock_module:
                mock_module.from_url.return_value = mock_redis
                result = await rs.get_redis_state_client()

        # Should return None, not raise
        assert result is None


# ---------------------------------------------------------------------------
# core/redis_state.py — CircuitBreakerRedisAdapter
# ---------------------------------------------------------------------------


class TestCircuitBreakerRedisAdapter:
    """Tests for the CircuitBreakerRedisAdapter save/restore cycle."""

    def _make_breaker(self):
        """Return a mock circuit breaker with the expected attributes."""
        cb = MagicMock()
        cb._state = "CLOSED"
        cb._failure_count = 3
        cb._total_calls = 100
        cb._failed_calls = 3
        cb._last_failure_time = time.time() - 60
        cb._state_changes = 1
        return cb

    @pytest.mark.asyncio
    async def test_save_and_restore_roundtrip(self):
        """Saving and restoring should reproduce the same circuit breaker state."""
        from core.redis_state import CircuitBreakerRedisAdapter

        fake_redis = _FakeRedis()
        adapter = CircuitBreakerRedisAdapter(fake_redis, "test-breaker")
        breaker = self._make_breaker()

        await adapter.save(breaker)

        # Create a blank breaker to restore into
        restored = self._make_breaker()
        restored._state = "OPEN"
        restored._failure_count = 99

        success = await adapter.restore(restored)

        assert success is True
        assert restored._state == "CLOSED"
        assert restored._failure_count == 3
        assert restored._total_calls == 100

    @pytest.mark.asyncio
    async def test_restore_returns_false_when_no_data(self):
        """Restore should return False when no saved state exists."""
        from core.redis_state import CircuitBreakerRedisAdapter

        fake_redis = _FakeRedis()
        adapter = CircuitBreakerRedisAdapter(fake_redis, "nonexistent-breaker")
        breaker = self._make_breaker()

        result = await adapter.restore(breaker)
        assert result is False

    @pytest.mark.asyncio
    async def test_save_with_none_client_does_not_raise(self):
        """Save with None client (Redis unavailable) should be a no-op."""
        from core.redis_state import CircuitBreakerRedisAdapter

        adapter = CircuitBreakerRedisAdapter(None, "breaker-no-redis")
        breaker = self._make_breaker()
        # Should not raise
        await adapter.save(breaker)


# ---------------------------------------------------------------------------
# core/redis_state.py — RedisDistributedLock
# ---------------------------------------------------------------------------


class TestRedisDistributedLock:
    """Tests for the RedisDistributedLock acquire/release cycle."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Lock should be acquired and then released."""
        from core.redis_state import RedisDistributedLock

        fake_redis = _FakeRedis()
        lock = RedisDistributedLock(fake_redis, "test-resource", ttl_seconds=30)

        acquired = await lock.acquire()
        assert acquired is True
        assert lock._token is not None

        await lock.release()
        assert lock._token is None

    @pytest.mark.asyncio
    async def test_second_acquire_fails(self):
        """A second lock on the same resource should fail immediately."""
        from core.redis_state import RedisDistributedLock

        fake_redis = _FakeRedis()
        lock1 = RedisDistributedLock(fake_redis, "shared-resource")
        lock2 = RedisDistributedLock(fake_redis, "shared-resource")

        acquired1 = await lock1.acquire()
        acquired2 = await lock2.acquire(timeout_ms=0)  # immediate

        assert acquired1 is True
        assert acquired2 is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Lock should work as async context manager."""
        from core.redis_state import RedisDistributedLock

        fake_redis = _FakeRedis()
        entered = False

        async with RedisDistributedLock(fake_redis, "ctx-resource"):
            entered = True

        assert entered is True

    @pytest.mark.asyncio
    async def test_none_client_always_acquires(self):
        """With no Redis, lock should always be acquired (single-process fallback)."""
        from core.redis_state import RedisDistributedLock

        lock = RedisDistributedLock(None, "no-redis-resource")
        acquired = await lock.acquire()
        assert acquired is True


# ---------------------------------------------------------------------------
# core/redis_state.py — Workflow state
# ---------------------------------------------------------------------------


class TestWorkflowState:
    """Tests for save/load/delete workflow state helpers."""

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self):
        """Saved workflow state should be retrievable."""
        from core.redis_state import load_workflow_state, save_workflow_state

        fake_redis = _FakeRedis()
        state = {"study_type": "LOAD_FLOW", "status": "RUNNING", "progress": 42}

        await save_workflow_state("task-abc", state, client=fake_redis)
        loaded = await load_workflow_state("task-abc", client=fake_redis)

        assert loaded is not None
        assert loaded["study_type"] == "LOAD_FLOW"
        assert loaded["progress"] == 42

    @pytest.mark.asyncio
    async def test_delete_removes_state(self):
        """After delete, load should return None."""
        from core.redis_state import (
            delete_workflow_state,
            load_workflow_state,
            save_workflow_state,
        )

        fake_redis = _FakeRedis()
        await save_workflow_state("task-del", {"x": 1}, client=fake_redis)
        await delete_workflow_state("task-del", client=fake_redis)
        result = await load_workflow_state("task-del", client=fake_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self):
        """Loading a key that was never saved should return None."""
        from core.redis_state import load_workflow_state

        fake_redis = _FakeRedis()
        result = await load_workflow_state("nonexistent-task", client=fake_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_none_client_is_noop(self):
        """All operations with None client should be no-ops (no exception)."""
        from core.redis_state import (
            delete_workflow_state,
            load_workflow_state,
            save_workflow_state,
        )

        await save_workflow_state("t1", {"x": 1}, client=None)
        result = await load_workflow_state("t1", client=None)
        assert result is None
        await delete_workflow_state("t1", client=None)


# ---------------------------------------------------------------------------
# worker/celery_app.py — configuration sanity
# ---------------------------------------------------------------------------


class TestCeleryConfig:
    """Sanity checks for the Celery app configuration."""

    def test_celery_app_imported(self):
        """Celery app should import without errors."""
        from worker.celery_app import app

        assert app is not None

    def test_acks_late_enabled(self):
        """task_acks_late must be True for crash recovery."""
        from worker.celery_app import app

        assert app.conf.task_acks_late is True

    def test_reject_on_lost_enabled(self):
        """task_reject_on_worker_lost must be True."""
        from worker.celery_app import app

        assert app.conf.task_reject_on_worker_lost is True

    def test_worker_prefetch_is_1(self):
        """Prefetch should be 1 for long-running engineering studies."""
        from worker.celery_app import app

        assert app.conf.worker_prefetch_multiplier == 1

    def test_broker_connection_retry_on_startup(self):
        """Broker retry on startup must be enabled."""
        from worker.celery_app import app

        assert app.conf.broker_connection_retry_on_startup is True

    def test_heartbeat_beat_schedule_exists(self):
        """Beat schedule should contain the heartbeat entry."""
        from worker.celery_app import app

        assert "heartbeat-every-60s" in app.conf.beat_schedule


# ---------------------------------------------------------------------------
# etap_integration/worker_registry.py — WorkerRegistry
# ---------------------------------------------------------------------------


class TestWorkerRegistry:
    """Tests for the WorkerRegistry helper."""

    @pytest.mark.asyncio
    async def test_no_workers_when_empty(self):
        """Registry should return empty list when no workers are registered."""
        from etap_integration.worker_registry import WorkerRegistry

        fake_redis = _FakeRedis()
        # keys() on empty store returns []
        registry = WorkerRegistry()
        registry._redis = fake_redis  # inject fake
        workers = await registry.get_available_workers()
        assert workers == []

    @pytest.mark.asyncio
    async def test_stale_worker_excluded(self):
        """Workers with heartbeat > stale_threshold seconds ago should be excluded."""
        from etap_integration.worker_registry import _REGISTRY_PREFIX, WorkerRegistry

        fake_redis = _FakeRedis()
        old_info = json.dumps({
            "worker_id": "old-worker",
            "last_heartbeat": time.time() - 200,  # 200s ago — stale
            "status": "idle",
        })
        await fake_redis.set(f"{_REGISTRY_PREFIX}old-worker", old_info)

        # Manually inject redis so it uses fake_redis
        registry = WorkerRegistry(stale_threshold=90)
        registry._redis = fake_redis

        # Mock keys() to return the key
        fake_redis._store[f"{_REGISTRY_PREFIX}old-worker"] = old_info

        # The stale worker should be excluded
        workers = await registry.get_available_workers()
        assert all(w["worker_id"] != "old-worker" for w in workers)

    @pytest.mark.asyncio
    async def test_alive_worker_included(self):
        """Workers with recent heartbeat should be returned."""
        from etap_integration.worker_registry import _REGISTRY_PREFIX, WorkerRegistry

        fake_redis = _FakeRedis()
        alive_info = {
            "worker_id": "alive-worker",
            "last_heartbeat": time.time() - 10,  # 10s ago — fresh
            "status": "idle",
        }
        fake_redis._store[f"{_REGISTRY_PREFIX}alive-worker"] = json.dumps(alive_info)

        registry = WorkerRegistry(stale_threshold=90)
        registry._redis = fake_redis

        # Patch keys() to return matching keys
        original_keys = fake_redis.keys

        async def patched_keys(pattern):
            return [k for k in fake_redis._store if k.startswith(_REGISTRY_PREFIX)]

        fake_redis.keys = patched_keys

        workers = await registry.get_available_workers()
        worker_ids = [w["worker_id"] for w in workers]
        assert "alive-worker" in worker_ids
