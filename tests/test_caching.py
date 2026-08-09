"""Tests for Redis Caching Layer.

Tests the StudyCache class including cache miss, set/get, TTL expiry,
invalidation, and in-memory fallback behavior.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.caching import StudyCache, _InMemoryStore, get_study_cache

# ---------------------------------------------------------------------------
# _InMemoryStore tests (no Redis needed)
# ---------------------------------------------------------------------------


class TestInMemoryStore:
    """Tests for the in-memory fallback store."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get operations."""
        store = _InMemoryStore()
        await store.set("key1", '{"result": 42}', ttl_seconds=60)
        value = await store.get("key1")
        assert value == '{"result": 42}'

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        """Test get returns None for missing keys."""
        store = _InMemoryStore()
        value = await store.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test delete removes a key."""
        store = _InMemoryStore()
        await store.set("key1", "value1", ttl_seconds=60)
        deleted = await store.delete("key1")
        assert deleted is True
        value = await store.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test delete returns False for nonexistent key."""
        store = _InMemoryStore()
        deleted = await store.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test exists check."""
        store = _InMemoryStore()
        await store.set("key1", "value1", ttl_seconds=60)
        assert await store.exists("key1") is True
        assert await store.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Test TTL-based expiry of entries."""
        store = _InMemoryStore()
        # Set with very short TTL
        await store.set("key1", "value1", ttl_seconds=1)
        # Immediately available
        assert await store.get("key1") == "value1"
        # Wait for expiry
        await asyncio.sleep(1.1)
        value = await store.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_no_ttl_persists(self):
        """Test entries without TTL persist indefinitely."""
        store = _InMemoryStore()
        await store.set("key1", "value1", ttl_seconds=0)  # No expiry
        assert await store.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_keys_pattern(self):
        """Test keys() with glob pattern matching."""
        store = _InMemoryStore()
        await store.set("etap:study:load_flow:abc", "v1", ttl_seconds=0)
        await store.set("etap:study:short_circuit:def", "v2", ttl_seconds=0)
        await store.set("etap:study:load_flow:ghi", "v3", ttl_seconds=0)

        all_keys = await store.keys("*")
        assert len(all_keys) == 3

        lf_keys = await store.keys("etap:study:load_flow:*")
        assert len(lf_keys) == 2

    @pytest.mark.asyncio
    async def test_dbsize(self):
        """Test database size count."""
        store = _InMemoryStore()
        assert await store.dbsize() == 0
        await store.set("k1", "v1", ttl_seconds=0)
        await store.set("k2", "v2", ttl_seconds=0)
        assert await store.dbsize() == 2

    @pytest.mark.asyncio
    async def test_flushdb(self):
        """Test clearing all entries."""
        store = _InMemoryStore()
        await store.set("k1", "v1", ttl_seconds=0)
        await store.set("k2", "v2", ttl_seconds=0)
        await store.flushdb()
        assert await store.dbsize() == 0

    @pytest.mark.asyncio
    async def test_max_entries_eviction(self):
        """Test LRU eviction when max entries is exceeded."""
        store = _InMemoryStore(max_entries=3)
        await store.set("k1", "v1", ttl_seconds=0)
        await store.set("k2", "v2", ttl_seconds=0)
        await store.set("k3", "v3", ttl_seconds=0)
        await store.set("k4", "v4", ttl_seconds=0)  # Should evict k1
        assert await store.dbsize() == 3
        assert await store.get("k1") is None
        assert await store.get("k4") == "v4"


# ---------------------------------------------------------------------------
# StudyCache tests (uses in-memory fallback when Redis unavailable)
# ---------------------------------------------------------------------------


class TestStudyCache:
    """Tests for the StudyCache class (in-memory fallback mode)."""

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test 1: Cache miss returns None for new key."""
        cache = StudyCache(ttl=3600)
        result = await cache.get("load_flow", {"bus_count": 5})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test 2: Cache set and then get returns cached data."""
        cache = StudyCache(ttl=3600)
        params = {"bus_count": 5, "voltage": 13.8}
        data = {"converged": True, "iterations": 5}

        await cache.set("load_flow", params, data)
        result = await cache.get("load_flow", params)
        assert result is not None
        assert result["converged"] is True

    @pytest.mark.asyncio
    async def test_cache_different_params_different_keys(self):
        """Test 3: Different parameters produce different cache keys."""
        cache = StudyCache(ttl=3600)
        params1 = {"bus_count": 5}
        params2 = {"bus_count": 10}

        await cache.set("load_flow", params1, {"result": "small"})
        await cache.set("load_flow", params2, {"result": "large"})

        r1 = await cache.get("load_flow", params1)
        r2 = await cache.get("load_flow", params2)
        assert r1["result"] == "small"
        assert r2["result"] == "large"

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test 4: Cache invalidation removes specific entry."""
        cache = StudyCache(ttl=3600)
        params = {"bus_count": 5}
        await cache.set("load_flow", params, {"result": "cached"})

        # Verify cached
        result = await cache.get("load_flow", params)
        assert result is not None

        # Invalidate
        await cache.invalidate("load_flow", params)

        # Should be a miss now
        result = await cache.get("load_flow", params)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test 5: Cache statistics are tracked."""
        cache = StudyCache(ttl=3600)
        params = {"bus_count": 5}

        # Miss
        await cache.get("load_flow", params)

        # Set
        await cache.set("load_flow", params, {"result": True})

        # Hit
        await cache.get("load_flow", params)

        stats = await cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["sets"] >= 1
        assert "hit_rate" in stats
        assert stats["hit_rate"] > 0

    @pytest.mark.asyncio
    async def test_in_memory_fallback(self):
        """Test 6: Falls back to in-memory when Redis is unavailable."""
        # Use an invalid Redis URL; should fall back gracefully
        cache = StudyCache(
            redis_url="redis://nonexistent:6379",
            ttl=3600,
        )
        params = {"test": True}
        await cache.set("test_study", params, {"data": "hello"})
        result = await cache.get("test_study", params)
        # Should still work via in-memory fallback
        assert result is not None
        assert result["data"] == "hello"

    @pytest.mark.asyncio
    async def test_cache_deterministic_key(self):
        """Test 7: Same parameters always produce same cache key."""
        cache = StudyCache(ttl=3600)
        params = {"bus_count": 5, "voltage": 13.8}
        key1 = cache._make_key("load_flow", params)
        key2 = cache._make_key("load_flow", params)
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_key_includes_study_type(self):
        """Test 8: Cache keys differ by study type."""
        cache = StudyCache(ttl=3600)
        params = {"bus_count": 5}
        key_lf = cache._make_key("load_flow", params)
        key_sc = cache._make_key("short_circuit", params)
        assert key_lf != key_sc

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test 9: Cache clear removes all entries."""
        cache = StudyCache(ttl=3600)
        await cache.set("s1", {"a": 1}, {"r": 1})
        await cache.set("s2", {"b": 2}, {"r": 2})
        await cache.clear()
        assert await cache.get("s1", {"a": 1}) is None
        assert await cache.get("s2", {"b": 2}) is None

    @pytest.mark.asyncio
    async def test_ttl_expiry_in_cache(self):
        """Test 10: Cached entries expire after TTL."""
        cache = StudyCache(ttl=1)  # 1 second TTL
        params = {"test": "ttl"}
        await cache.set("test_study", params, {"data": "expires"})

        # Immediately available
        result = await cache.get("test_study", params)
        assert result is not None

        # After TTL
        await asyncio.sleep(1.1)
        result = await cache.get("test_study", params)
        assert result is None
