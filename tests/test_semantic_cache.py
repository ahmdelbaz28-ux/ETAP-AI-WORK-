"""
tests/test_semantic_cache.py — Unit tests for Semantic Cache Layer.
"""

import time
import pytest

from api.semantic_cache import (
    SemanticCache,
    _canonicalize_value,
    get_semantic_cache,
    reset_semantic_cache,
)
from api.telemetry import tracker


@pytest.fixture(autouse=True)
def clean_cache():
    reset_semantic_cache()
    tracker.reset()
    yield
    reset_semantic_cache()
    tracker.reset()


@pytest.mark.asyncio
async def test_semantic_cache_hit_saves_tokens():
    cache = SemanticCache(ttl_seconds=3600)
    system_data = {"buses": [{"id": 1, "vn_kv": 11.0}], "generators": []}
    parameters = {"tolerance": 1e-5, "max_iterations": 20}
    agent_handle = "load_flow_agent"
    study_result = {
        "success": True,
        "results": {"bus_voltages": {1: 1.02}},
        "warnings": [],
        "errors": [],
    }

    # Store in cache with token metadata
    await cache.store(
        system_data=system_data,
        parameters=parameters,
        agent_handle=agent_handle,
        result=study_result,
        metadata={"tokens_used": 2500, "quality_score": 1.0},
    )

    # Lookup with exact same network + params
    cached = await cache.lookup(system_data, parameters, agent_handle)
    assert cached is not None
    assert cached.tokens_saved == 2500
    assert cached.result["success"] is True
    val = cached.result["results"]["bus_voltages"].get(1) or cached.result["results"]["bus_voltages"].get("1")
    assert val == 1.02

    # Verify telemetry recorded cache hit
    metrics = tracker.get_metrics()
    assert metrics["cache_hits"] == 1
    assert metrics["tokens_saved"] == 2500


@pytest.mark.asyncio
async def test_semantic_cache_miss_on_parameter_change():
    cache = SemanticCache(ttl_seconds=3600)
    system_data = {"buses": [{"id": 1, "vn_kv": 11.0}]}
    params_1 = {"tolerance": 1e-5}
    params_2 = {"tolerance": 1e-4}
    agent_handle = "short_circuit_agent"

    await cache.store(
        system_data=system_data,
        parameters=params_1,
        agent_handle=agent_handle,
        result={"success": True, "results": {"ikss_ka": 25.4}},
        metadata={"tokens_used": 1800},
    )

    # Different parameter -> miss
    cached = await cache.lookup(system_data, params_2, agent_handle)
    assert cached is None

    metrics = tracker.get_metrics()
    assert metrics["cache_misses"] == 1
    assert metrics["cache_hits"] == 0


@pytest.mark.asyncio
async def test_semantic_cache_ttl_expiration():
    cache = SemanticCache(ttl_seconds=1)
    system_data = {"buses": [{"id": 1}]}
    parameters = {"tolerance": 1e-3}
    agent_handle = "arcflash_agent"

    await cache.store(
        system_data=system_data,
        parameters=parameters,
        agent_handle=agent_handle,
        result={"incident_energy": 4.2},
        custom_ttl=1,  # 1 second TTL
    )

    # Immediate lookup hits
    cached_immediate = await cache.lookup(system_data, parameters, agent_handle)
    assert cached_immediate is not None

    # Wait for TTL expiry
    time.sleep(1.1)

    cached_expired = await cache.lookup(system_data, parameters, agent_handle)
    assert cached_expired is None


@pytest.mark.asyncio
async def test_canonical_key_dict_order_insensitivity():
    cache = SemanticCache()
    sys1 = {"buses": [{"id": 1, "vn_kv": 11.0}], "name": "Substation Alpha"}
    sys2 = {"name": "Substation Alpha", "buses": [{"vn_kv": 11.0, "id": 1}]}
    params = {"mode": "auto", "limit": 100}

    key1 = cache._make_cache_key(sys1, params, "etap_engineer_agent")
    key2 = cache._make_cache_key(sys2, params, "etap_engineer_agent")

    assert key1 == key2


@pytest.mark.asyncio
async def test_cache_stats_and_clearing():
    cache = SemanticCache()
    await cache.store({}, {"p": 1}, "agent1", {"res": 1})
    await cache.lookup({}, {"p": 1}, "agent1")  # Hit
    await cache.lookup({}, {"p": 2}, "agent1")  # Miss

    stats = cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.hit_rate == 0.5
    assert stats.total_entries == 1

    cache.clear()
    assert cache.get_stats().total_entries == 0
