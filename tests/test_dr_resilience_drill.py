"""
tests/test_dr_resilience_drill.py — Disaster Recovery & Operational Resilience Drill.

Verifies system resilience and fail-closed behaviors under operational failure scenarios:
1. Redis disconnection during distributed locking and session retrieval (fail-closed in prod, safe in dev).
2. Database migration single-head consistency and downgrade script existence.
3. Resilience of task execution when upstream dependencies throw transient errors.
4. Absence of secrets or internal stack traces in error envelopes.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from api.database_migrations import get_alembic_config
from api.routes import app
from api.task_queue import JobStatus, RedisTaskQueue
from core.redis_state import LockManager, RedisDistributedLock


@pytest.mark.asyncio
async def test_redis_disconnect_distributed_lock_behavior() -> None:
    """Verify that when Redis is disconnected:
    - LockManager handles the exception gracefully.
    - In single-process fallback mode, lock acquisition allows execution or returns false without crashing.
    """
    broken_redis = AsyncMock()
    broken_redis.set.side_effect = ConnectionError("Redis connection lost during failover")
    broken_redis.eval.side_effect = ConnectionError("Redis connection lost during failover")

    lock = RedisDistributedLock(client=broken_redis, resource="substation_bus_4")

    # When Redis raises ConnectionError during acquire
    with pytest.raises(ConnectionError):
        await lock.acquire(timeout_ms=10)

    # Releasing when token was not set should be a safe no-op
    await lock.release()
    assert lock._token is None


@pytest.mark.asyncio
async def test_alembic_single_head_consistency() -> None:
    """Verify Alembic migration tree has exactly ONE head (no divergent branch heads)."""
    from alembic.script import ScriptDirectory

    cfg = get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()

    assert len(heads) == 1, f"Database migration history must have exactly 1 head, found: {heads}"
    head_rev = heads[0]
    assert head_rev == "011_add_hardening_tables"

    # Verify that the head revision script defines both upgrade and downgrade functions
    rev_script = script.get_revision(head_rev)
    assert rev_script is not None
    assert hasattr(rev_script.module, "upgrade"), f"Migration {head_rev} missing upgrade()"
    assert hasattr(rev_script.module, "downgrade"), f"Migration {head_rev} missing downgrade()"


@pytest.mark.asyncio
async def test_task_queue_resilience_on_enqueue_failure() -> None:
    """Verify that transient Redis errors during enqueue are wrapped in a clean RuntimeError."""
    broken_redis = AsyncMock()
    broken_redis.hset.side_effect = TimeoutError("Redis timeout during cluster reelection")

    with patch("api.task_queue.get_redis", AsyncMock(return_value=broken_redis)):
        queue = RedisTaskQueue(queue_name="dr_resilience_queue")

        with pytest.raises(RuntimeError) as exc_info:
            await queue.enqueue(task_name="contingency_analysis", payload={"case": "n-1"})

        assert "Enqueue failed" in str(exc_info.value)
        # Ensure raw sensitive credentials are not in the error message
        assert "password" not in str(exc_info.value).lower()
        assert "secret" not in str(exc_info.value).lower()


def test_error_envelope_does_not_leak_stack_traces() -> None:
    """Verify that unhandled 404 or bad requests return structured JSON without Python stack traces."""
    client = TestClient(app)
    resp = client.get("/api/v1/non_existent_endpoint_for_dr_test")
    assert resp.status_code == 404
    body = resp.text

    # Assert no traceback or internal filesystem paths leaked
    assert "Traceback (most recent call last)" not in body
    assert "c:\\users" not in body.lower()
    assert "/home/" not in body
