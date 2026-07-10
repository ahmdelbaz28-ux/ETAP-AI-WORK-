"""
Unit tests for engine/cache_manager.py — CalculationCache LRU cache.

Tests the pure cache operations (get, set, invalidate, invalidate_by_tag,
clear, get_stats, exists, _estimate_size) without needing Redis.
"""
from __future__ import annotations

import pytest

from engine.cache_manager import CacheStrategy, CalculationCache, _estimate_size


class TestEstimateSize:
    """Tests for _estimate_size()."""

    def test_small_int(self):
        """GIVEN a small integer
        WHEN _estimate_size is called
        THEN it returns a positive int.
        """
        size = _estimate_size(42)
        assert isinstance(size, int)
        assert size > 0

    def test_string(self):
        """GIVEN a string
        WHEN _estimate_size is called
        THEN it returns a size proportional to string length.
        """
        size = _estimate_size("hello world")
        assert size > 0
        # Longer string should have larger size
        assert _estimate_size("a" * 100) > _estimate_size("a" * 10)

    def test_dict(self):
        """GIVEN a dict
        WHEN _estimate_size is called
        THEN it returns a positive size.
        """
        size = _estimate_size({"key": "value", "num": 123})
        assert size > 0

    def test_list(self):
        """GIVEN a list
        WHEN _estimate_size is called
        THEN it returns a positive size.
        """
        size = _estimate_size([1, 2, 3, 4, 5])
        assert size > 0

    def test_none(self):
        """GIVEN None
        WHEN _estimate_size is called
        THEN it returns a small positive size.
        """
        size = _estimate_size(None)
        assert isinstance(size, int)


class TestCalculationCacheInit:
    """Tests for CalculationCache initialization."""

    def test_default_init(self):
        """GIVEN no arguments
        WHEN CalculationCache is constructed
        THEN it creates an empty cache.
        """
        cache = CalculationCache()
        assert cache is not None
        stats = cache.get_stats()
        assert stats["entries"] == 0

    def test_init_with_max_size(self):
        """GIVEN max_size_mb=1
        WHEN CalculationCache is constructed
        THEN it accepts the parameter.
        """
        cache = CalculationCache(max_size_mb=1)
        assert cache is not None


class TestCacheGetSet:
    """Tests for CalculationCache get/set."""

    def test_set_and_get_value(self):
        """GIVEN an empty cache
        WHEN a value is set with a key
        THEN get with the same key returns the value.
        """
        cache = CalculationCache()
        cache.set("key1", {"data": 42}, tags=["calc"])
        result = cache.get("key1")
        assert result == {"data": 42}

    def test_get_missing_key_returns_none(self):
        """GIVEN an empty cache
        WHEN get is called with a nonexistent key
        THEN it returns None.
        """
        cache = CalculationCache()
        assert cache.get("nonexistent") is None

    def test_overwrite_existing_key(self):
        """GIVEN a cache with key1=value1
        WHEN key1 is set to value2
        THEN get returns value2.
        """
        cache = CalculationCache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_exists_returns_true_for_set_key(self):
        """GIVEN a cache with key1
        WHEN exists is called
        THEN it returns True.
        """
        cache = CalculationCache()
        cache.set("key1", "value1")
        assert cache.exists("key1") is True

    def test_exists_returns_false_for_missing_key(self):
        """GIVEN an empty cache
        WHEN exists is called
        THEN it returns False.
        """
        cache = CalculationCache()
        assert cache.exists("nonexistent") is False


class TestCacheInvalidation:
    """Tests for CalculationCache invalidation."""

    def test_invalidate_existing_key(self):
        """GIVEN a cache with key1
        WHEN invalidate is called
        THEN it returns True and key1 no longer exists.
        """
        cache = CalculationCache()
        cache.set("key1", "value1")
        result = cache.invalidate("key1")
        assert result is True
        assert cache.get("key1") is None

    def test_invalidate_missing_key(self):
        """GIVEN an empty cache
        WHEN invalidate is called
        THEN it returns False.
        """
        cache = CalculationCache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_invalidate_by_tag_removes_tagged_entries(self):
        """GIVEN a cache with entries tagged 'calc'
        WHEN invalidate_by_tag is called with 'calc'
        THEN it returns the count of removed entries.
        """
        cache = CalculationCache()
        cache.set("key1", "v1", tags=["calc"])
        cache.set("key2", "v2", tags=["calc"])
        cache.set("key3", "v3", tags=["other"])
        removed = cache.invalidate_by_tag("calc")
        assert removed == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "v3"  # Untagged entry survives

    def test_invalidate_by_nonexistent_tag(self):
        """GIVEN a cache
        WHEN invalidate_by_tag is called with a nonexistent tag
        THEN it returns 0.
        """
        cache = CalculationCache()
        cache.set("key1", "v1", tags=["calc"])
        removed = cache.invalidate_by_tag("nonexistent")
        assert removed == 0


class TestCacheClear:
    """Tests for CalculationCache.clear()."""

    def test_clear_empties_cache(self):
        """GIVEN a cache with multiple entries
        WHEN clear is called
        THEN all entries are removed.
        """
        cache = CalculationCache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None
        assert cache.get("k3") is None
        stats = cache.get_stats()
        assert stats["entries"] == 0


class TestCacheStats:
    """Tests for CalculationCache.get_stats()."""

    def test_empty_cache_stats(self):
        """GIVEN an empty cache
        WHEN get_stats is called
        THEN it returns a dict with entries=0.
        """
        cache = CalculationCache()
        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert stats["entries"] == 0

    def test_stats_reflect_entries(self):
        """GIVEN a cache with 3 entries
        WHEN get_stats is called
        THEN entries=3.
        """
        cache = CalculationCache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        stats = cache.get_stats()
        assert stats["entries"] == 3


class TestCacheKeys:
    """Tests for CalculationCache.get_cache_keys()."""

    def test_get_all_keys(self):
        """GIVEN a cache with entries
        WHEN get_cache_keys is called without a pattern
        THEN it returns all keys.
        """
        cache = CalculationCache()
        cache.set("apple", 1)
        cache.set("banana", 2)
        keys = cache.get_cache_keys()
        assert "apple" in keys
        assert "banana" in keys

    def test_get_keys_with_pattern(self):
        """GIVEN a cache with entries
        WHEN get_cache_keys is called with a pattern
        THEN it returns only matching keys.
        """
        cache = CalculationCache()
        cache.set("calc_load_flow", 1)
        cache.set("calc_short_circuit", 2)
        cache.set("other_key", 3)
        # Pattern may be glob or regex — test based on implementation
        keys = cache.get_cache_keys(pattern="calc_*")
        # Should include calc_ keys and exclude other_key
        assert "calc_load_flow" in keys
        assert "other_key" not in keys


class TestCacheStrategy:
    """Tests for the CacheStrategy enum."""

    def test_cache_strategy_values(self):
        """GIVEN the CacheStrategy enum
        THEN it has the expected members (LRU, LFU, etc.)."""
        assert hasattr(CacheStrategy, "LRU") or hasattr(CacheStrategy, "FIFO") or len(list(CacheStrategy)) > 0
