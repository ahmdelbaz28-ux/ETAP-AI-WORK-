"""
Cache Service module for the Engineering Service.

This module is now a thin re-export layer over ``engine/caching.py``.
The ``StudyCache`` class and ``get_study_cache()`` factory are defined
in ``engine/caching.py`` (the single source of truth).

Previously, this file contained a SEPARATE ``StudyCache`` implementation
with a different API (``get(key)`` vs ``get(study_type, params)``),
which caused behavioral divergence. The unified ``StudyCache`` in
``engine/caching.py`` now supports BOTH calling conventions.

Public API (unchanged):
    from services.cache_service import StudyCache, get_study_cache
    cache = StudyCache(redis_url="memory://test", ttl=3600)
    await cache.set("key", {"data": 1}, ttl=3600)
    result = await cache.get("key")
    await cache.clear()
    await cache.ping()

Refs: PRODUCTION_PLAN/02_DUPLICATION_REPORT.md Cluster #6
"""

from __future__ import annotations

# Re-export the unified StudyCache + factory from engine/caching.py
from engine.caching import (  # noqa: F401
    StudyCache,
    _InMemoryStore,
    _is_redis_url,
    get_study_cache,
)

__all__ = ["StudyCache", "get_study_cache", "_is_redis_url", "_InMemoryStore"]
