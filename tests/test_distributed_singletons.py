"""
tests/test_distributed_singletons.py — Unit tests for Distributed Redis Singletons.

Tests both active Redis execution (via mock Redis) and seamless in-memory fallback
when Redis is unreachable or offline.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from api.prompt_registry_redis import (
    DistributedPromptRegistry,
    get_distributed_prompt_registry,
    reset_distributed_prompt_registry,
)
from api.rag_retriever_redis import (
    DistributedRAGRetriever,
    get_distributed_rag_retriever,
    reset_distributed_rag_retriever,
)
from api.redis_client import close_redis, get_redis_url, is_redis_available
from api.semantic_cache_redis import (
    DistributedSemanticCache,
    get_distributed_semantic_cache,
    reset_distributed_semantic_cache,
)
from api.token_budget_redis import (
    DistributedTokenBudgetManager,
    get_distributed_budget_manager,
    reset_distributed_budget_manager,
)


@pytest.fixture(autouse=True)
def clean_singletons():
    reset_distributed_budget_manager()
    reset_distributed_semantic_cache()
    reset_distributed_rag_retriever()
    reset_distributed_prompt_registry()
    yield
    reset_distributed_budget_manager()
    reset_distributed_semantic_cache()
    reset_distributed_rag_retriever()
    reset_distributed_prompt_registry()


# ─── 1. Redis Client & Fallback Detection ────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_client_helpers():
    url = get_redis_url()
    assert "redis://" in url
    # On environments without local Redis daemon, is_redis_available returns False gracefully
    available = await is_redis_available()
    assert isinstance(available, bool)
    await close_redis()


# ─── 2. DistributedTokenBudgetManager ───────────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_token_budget_fallback_mode():
    mgr = DistributedTokenBudgetManager()
    session_id = "test-dist-session-fallback"
    agent = "load_flow_agent"

    # In fallback mode (no Redis), delegates to in-memory manager
    res = await mgr.check_and_reserve(session_id, agent, 1000)
    assert res is True

    usage = await mgr.record_usage(session_id, agent, 500, 200)
    assert usage["input_tokens"] == 500
    assert usage["output_tokens"] == 200
    assert usage["total_used"] == 700

    remaining = await mgr.get_remaining(session_id, agent)
    # Budget (4000) - Used (700) - Unreleased Reserved (300) = 3000
    assert remaining == 3000

    summary = await mgr.get_session_summary(session_id)
    assert summary["session_id"] == session_id
    assert summary["total_used"] == 700

    # Prune history
    messages = [
        {"role": "system", "content": "system instruction"},
        {"role": "user", "content": "hello world"},
    ]
    pruned = mgr.prune_history(messages, max_tokens=2000)
    assert len(pruned) == 2

    await mgr.reset_session(session_id)


@pytest.mark.asyncio
async def test_distributed_token_budget_mock_redis():
    mock_redis = AsyncMock()
    # Lua script returns 1 for success
    mock_redis.eval.side_effect = [
        1,  # check_and_reserve
        [300, 700],  # record_usage {reserved, used}
    ]
    mock_redis.hget.side_effect = ["300", "700"]
    mock_redis.hgetall.return_value = {
        "agent:load_flow_agent:used": "700",
        "agent:load_flow_agent:reserved": "300",
    }

    with patch("api.token_budget_redis.get_redis", return_value=mock_redis):
        mgr = DistributedTokenBudgetManager()
        session_id = "mock-session-1"

        ok = await mgr.check_and_reserve(session_id, "load_flow_agent", 1000)
        assert ok is True

        usage = await mgr.record_usage(session_id, "load_flow_agent", 500, 200)
        assert usage["total_used"] == 700
        assert usage["remaining"] == 4000 - (300 + 700)

        rem = await mgr.get_remaining(session_id, "load_flow_agent")
        assert rem == 3000

        summary = await mgr.get_session_summary(session_id)
        assert summary["total_used"] == 700
        assert "load_flow_agent" in summary["agents"]


# ─── 3. DistributedSemanticCache ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_semantic_cache_fallback_mode():
    cache = DistributedSemanticCache()
    sys_data = {"voltage_kv": 11.0, "buses": 3}
    params = {"method": "newton-raphson"}
    agent = "load_flow_agent"

    # Store in fallback mode
    await cache.store(
        system_data=sys_data,
        parameters=params,
        agent_handle=agent,
        result={"status": "converged", "v_min": 0.98},
    )

    # Lookup
    cached = await cache.lookup(sys_data, params, agent)
    assert cached is not None
    assert cached.result["status"] == "converged"

    stats = cache.get_stats()
    assert stats.hits >= 1

    await cache.clear()


@pytest.mark.asyncio
async def test_distributed_semantic_cache_mock_redis():
    mock_redis = AsyncMock()
    cached_payload = {
        "result": {"status": "converged", "iterations": 4},
        "tokens_saved": 2000,
        "cached_at": time.time(),
        "embedding": [0.1] * 256,
        "agent_handle": "load_flow_agent",
        "ttl": 86400,
        "metadata": {},
    }
    mock_redis.hget.return_value = json.dumps(cached_payload)

    with patch("api.semantic_cache_redis.get_redis", return_value=mock_redis):
        cache = DistributedSemanticCache()
        sys_data = {"voltage_kv": 33.0}
        params = {"tolerance": 0.001}

        res = await cache.lookup(sys_data, params, "load_flow_agent")
        assert res is not None
        assert res.result["status"] == "converged"
        assert res.tokens_saved == 2000

        await cache.store(sys_data, params, "load_flow_agent", {"status": "converged"})
        assert mock_redis.hset.called


# ─── 4. DistributedRAGRetriever ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_rag_retriever_fallback_mode():
    rag = DistributedRAGRetriever(similarity_threshold=0.50)
    result_id = "res-test-rag-1"
    summary = {"study_type": "load_flow", "converged": True, "v_min": 0.96}
    metadata = {"agent_handle": "load_flow_agent", "project": "Expansion"}

    await rag.index_result(result_id, summary, metadata)

    retrieved = await rag.retrieve(
        query="Expansion load flow converged",
        agent_handle="load_flow_agent",
    )
    assert len(retrieved) >= 1
    assert retrieved[0].result_id == result_id

    await rag.clear()


@pytest.mark.asyncio
async def test_distributed_rag_retriever_mock_redis():
    mock_redis = AsyncMock()
    dim = 512
    entry = {
        "summary": {"study_type": "short_circuit", "ik_ss_ka": 25.4},
        "metadata": {"agent_handle": "short_circuit_agent"},
        "agent_handle": "short_circuit_agent",
        "tokens_set": ["short", "circuit", "fault", "ka"],
        "embedding": [0.2] * dim,
        "indexed_at": time.time(),
    }
    # Return cursor 0 and dict {id: json}
    mock_redis.hscan.return_value = (0, {"sc_001": json.dumps(entry)})

    with patch("api.rag_retriever_redis.get_redis", return_value=mock_redis):
        rag = DistributedRAGRetriever(similarity_threshold=0.1)
        results = await rag.retrieve(
            query="short circuit fault", agent_handle="short_circuit_agent"
        )
        assert len(results) >= 1
        assert results[0].result_id == "sc_001"
        assert results[0].summary["ik_ss_ka"] == 25.4

        await rag.index_result("sc_002", {"study_type": "short_circuit"})
        assert mock_redis.hset.called


# ─── 5. DistributedPromptRegistry ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_prompt_registry_fallback_mode():
    reg = DistributedPromptRegistry()
    pv = await reg.register_version(
        agent_handle="load_flow_agent",
        prompt_text="You are a load flow specialist.",
        temperature=0.2,
    )
    assert pv.agent_handle == "load_flow_agent"

    active = await reg.get_active_version("load_flow_agent")
    assert active is not None
    assert active.version_id == pv.version_id

    await reg.record_metrics(pv.version_id, tokens_used=1500, latency_ms=250.0, success=True)
    report = await reg.get_tradeoff_report("load_flow_agent")
    assert "load_flow_agent" in report

    promoted = await reg.promote_version(pv.version_id)
    assert promoted is True

    await reg.clear()


@pytest.mark.asyncio
async def test_distributed_prompt_registry_mock_redis():
    mock_redis = AsyncMock()
    mock_redis.llen.return_value = 0
    mock_redis.lrange.return_value = ["load_flow_agent:v1"]

    pv_dict = {
        "version_id": "load_flow_agent:v1",
        "agent_handle": "load_flow_agent",
        "prompt_text": "Specialized prompt",
        "temperature": 0.2,
        "metadata": {},
        "is_active": True,
        "created_at": time.time(),
    }
    mock_redis.get.return_value = json.dumps(pv_dict)

    with patch("api.prompt_registry_redis.get_redis", return_value=mock_redis):
        reg = DistributedPromptRegistry()
        pv = await reg.register_version(
            agent_handle="load_flow_agent",
            prompt_text="Specialized prompt",
        )
        assert pv.version_id == "load_flow_agent:v1"

        active = await reg.get_active_version("load_flow_agent")
        assert active is not None
        assert active.version_id == "load_flow_agent:v1"

        promoted = await reg.promote_version("load_flow_agent:v1")
        assert promoted is True


@pytest.mark.asyncio
async def test_distributed_prompt_registry_mid_chain_redis_failure():
    """
    Regression test: Simulates Redis failure mid-chain during register_version (e.g.
    r.set succeeds, but subsequent r.rpush raises ConnectionError). Proves that sticky
    self._mode = "memory" prevents architectural drift / split-brain by permanently
    routing subsequent operations through in-memory fallback without touching Redis.
    """
    mock_redis = AsyncMock()
    mock_redis.llen.return_value = 0
    # First set succeeds, but rpush fails with ConnectionError mid-operation
    mock_redis.set.return_value = True
    mock_redis.rpush.side_effect = ConnectionError("Redis cluster unreachable mid-chain")

    with patch("api.prompt_registry_redis.get_redis", return_value=mock_redis):
        reg = DistributedPromptRegistry(namespace="test_drift_regression")
        assert reg._mode is None

        # Call register_version: starts with redis, sets key, fails at rpush, catches error,
        # sets sticky self._mode = "memory", and completes registration via in-memory registry.
        pv = await reg.register_version(
            agent_handle="drift_agent",
            prompt_text="Prompt during mid-chain failure",
        )
        assert pv is not None
        assert pv.agent_handle == "drift_agent"
        # Verify sticky mode transitioned to "memory"
        assert reg._mode == "memory"

        # Now simulate Redis recovering:
        mock_redis.rpush.side_effect = None
        mock_redis.rpush.return_value = 1
        mock_redis.get.return_value = None  # Redis would return None or stale state

        # Crucial architectural proof: subsequent calls MUST NOT touch Redis or cause split-brain;
        # because _mode == "memory", _get_client() returns None immediately.
        active = await reg.get_active_version("drift_agent")
        assert active is not None
        assert active.version_id == pv.version_id
        assert active.prompt_text == "Prompt during mid-chain failure"

        # Another registration on the same instance continues in deterministic in-memory mode
        pv2 = await reg.register_version(
            agent_handle="drift_agent",
            prompt_text="Prompt v2 in sticky fallback mode",
        )
        assert pv2 is not None
        assert reg._mode == "memory"


@pytest.mark.asyncio
async def test_distributed_prompt_registry_read_your_writes_on_tradeoff_timeout():
    """
    Regression test: Verifies that when register_version succeeds on Redis,
    but subsequent get_tradeoff_report encounters a TimeoutError on Redis,
    Read-Your-Writes state mirroring guarantees the tradeoff report contains
    the registered agent's metrics instead of collapsing to an empty dict {}.
    """
    mock_redis = AsyncMock()
    mock_redis.llen.return_value = 0
    mock_redis.lrange.return_value = []
    mock_redis.set.return_value = True
    mock_redis.rpush.return_value = 1

    with patch("api.prompt_registry_redis.get_redis", return_value=mock_redis):
        reg = DistributedPromptRegistry(namespace="test_ryw_timeout")
        pv = await reg.register_version(
            agent_handle="load_flow_agent",
            prompt_text="Load flow specialized prompt",
            temperature=0.2,
        )
        assert pv.agent_handle == "load_flow_agent"

        await reg.record_metrics(pv.version_id, tokens_used=1200, latency_ms=180.0, success=True)

        # Now simulate Redis timeout during get_tradeoff_report (scan / lrange)
        mock_redis.lrange.side_effect = TimeoutError("Redis socket timeout under heavy CI load")

        # Must NOT return empty {} — Read-Your-Writes ensures local mirror has data
        report = await reg.get_tradeoff_report("load_flow_agent")
        assert "load_flow_agent" in report
        assert report["load_flow_agent"]["total_versions"] >= 1

