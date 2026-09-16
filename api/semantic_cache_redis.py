"""
api/semantic_cache_redis.py — Distributed Semantic Cache using Redis.

Replaces in-memory SemanticCache for multi-instance horizontal scaling,
with seamless fallback to in-memory SemanticCache when Redis is unavailable.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from api.redis_client import get_redis
from api.semantic_cache import (
    CachedResult,
    CacheStats,
    _canonicalize_value,
)
from api.semantic_cache import (
    get_semantic_cache as _get_in_memory_cache,
)
from api.telemetry import tracker

logger = logging.getLogger(__name__)


class DistributedSemanticCache:
    """Distributed Semantic Cache backed by Redis with cosine similarity and TTL management."""

    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 86400,
        namespace: str = "semantic_cache",
    ) -> None:
        self.embedding_model = embedding_model
        self.threshold = similarity_threshold
        self.ttl = ttl_seconds
        self.namespace = namespace
        self._hits = 0
        self._misses = 0
        self._similarities: List[float] = []

    def _make_cache_key(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
    ) -> str:
        canonical_sys = _canonicalize_value(system_data or {})
        canonical_params = _canonicalize_value(parameters or {})
        payload = {
            "agent_handle": agent_handle.strip().lower(),
            "system": canonical_sys,
            "parameters": canonical_params,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _embed(self, system_text: str, param_text: str) -> np.ndarray:
        dim = 256
        vec = np.zeros(dim, dtype=np.float32)
        if system_text:
            s_clean = system_text.lower().strip()
            for i in range(max(1, len(s_clean) - 2)):
                tri = s_clean[i : i + 3]
                idx = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16) % 128
                vec[idx] += 1.0
        if param_text:
            p_clean = param_text.lower().strip()
            for i in range(max(1, len(p_clean) - 2)):
                tri = p_clean[i : i + 3]
                idx = 128 + (int(hashlib.sha256(("p:" + tri).encode("utf-8")).hexdigest(), 16) % 128)
                vec[idx] += 2.0
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom < 1e-9:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _is_degraded(self) -> bool:
        return not bool(os.getenv("OPENAI_API_KEY"))

    async def lookup(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
    ) -> Optional[CachedResult]:
        norm_handle = agent_handle.strip().lower()
        key = self._make_cache_key(system_data, parameters, norm_handle)

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            # 1. Exact match
            entry_json = await r.hget(f"{self.namespace}:entries", key)
            if entry_json:
                entry = json.loads(entry_json)
                if time.time() - entry["cached_at"] <= entry.get("ttl", self.ttl):
                    self._hits += 1
                    self._similarities.append(1.0)
                    tokens_saved = entry.get("tokens_saved", 2000)
                    tracker.record_cache_hit(tokens_saved, agent_handle=norm_handle)
                    return CachedResult(
                        result=copy.deepcopy(entry["result"]),
                        tokens_saved=tokens_saved,
                        similarity=1.0,
                        cached_at=entry["cached_at"],
                        cache_key=key,
                        metadata=copy.deepcopy(entry.get("metadata", {})),
                    )
                else:
                    await r.hdel(f"{self.namespace}:entries", key)

            # 2. Vector similarity (only if not degraded)
            if not self._is_degraded():
                sys_str = json.dumps(_canonicalize_value(system_data), sort_keys=True)
                param_str = json.dumps(_canonicalize_value(parameters), sort_keys=True)
                query_emb = self._embed(sys_str, param_str)

                cursor = 0
                best_match: Optional[Tuple[str, Dict[str, Any]]] = None
                best_sim = 0.0

                while True:
                    cursor, data = await r.hscan(
                        f"{self.namespace}:entries", cursor=cursor, count=100
                    )
                    items: List[Tuple[str, str]] = []
                    if isinstance(data, dict):
                        items = list(data.items())
                    elif isinstance(data, (list, tuple)):
                        if data and isinstance(data[0], (list, tuple)):
                            items = [(k, v) for k, v in data]
                        else:
                            for k in data:
                                val = await r.hget(f"{self.namespace}:entries", k)
                                if val:
                                    items.append((k, val))

                    for k, val_json in items:
                        entry = json.loads(val_json)
                        if entry.get("agent_handle") != norm_handle:
                            continue
                        if time.time() - entry["cached_at"] > entry.get("ttl", self.ttl):
                            await r.hdel(f"{self.namespace}:entries", k)
                            continue
                        sim = self._cosine_similarity(
                            query_emb, np.array(entry["embedding"], dtype=np.float32)
                        )
                        if sim >= self.threshold and sim > best_sim:
                            best_sim = sim
                            best_match = (k, entry)

                    if cursor == 0:
                        break

                if best_match:
                    matched_key, entry = best_match
                    self._hits += 1
                    self._similarities.append(best_sim)
                    tokens_saved = entry.get("tokens_saved", 2000)
                    tracker.record_cache_hit(tokens_saved, agent_handle=norm_handle)
                    return CachedResult(
                        result=copy.deepcopy(entry["result"]),
                        tokens_saved=tokens_saved,
                        similarity=round(best_sim, 4),
                        cached_at=entry["cached_at"],
                        cache_key=matched_key,
                        metadata=copy.deepcopy(entry.get("metadata", {})),
                    )

            self._misses += 1
            tracker.record_cache_miss(agent_handle=norm_handle)
            return None
        except Exception as exc:
            logger.debug("Redis semantic cache lookup failed, falling back to memory: %s", exc)
            return await _get_in_memory_cache().lookup(system_data, parameters, agent_handle)

    async def store(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None,
        custom_ttl: Optional[int] = None,
    ) -> None:
        norm_handle = agent_handle.strip().lower()
        key = self._make_cache_key(system_data, parameters, norm_handle)
        meta = metadata or {}
        tokens_used = meta.get("tokens_used", 2000)

        sys_str = json.dumps(_canonicalize_value(system_data), sort_keys=True)
        param_str = json.dumps(_canonicalize_value(parameters), sort_keys=True)
        emb = self._embed(sys_str, param_str)

        res_dict = result.model_dump() if hasattr(result, "model_dump") else copy.deepcopy(result)

        entry = {
            "result": res_dict,
            "tokens_saved": tokens_used,
            "cached_at": time.time(),
            "embedding": emb.tolist(),
            "agent_handle": norm_handle,
            "ttl": custom_ttl or self.ttl,
            "metadata": meta,
        }

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            await r.hset(f"{self.namespace}:entries", key, json.dumps(entry))
            await r.expire(f"{self.namespace}:entries", self.ttl)
        except Exception as exc:
            logger.debug("Redis semantic cache store failed, falling back to memory: %s", exc)
            await _get_in_memory_cache().store(
                system_data,
                parameters,
                agent_handle,
                result,
                metadata,
                custom_ttl,
            )

    def get_stats(self) -> CacheStats:
        total_lookups = self._hits + self._misses
        if total_lookups == 0:
            mem_stats = _get_in_memory_cache().get_stats()
            if (mem_stats.hits + mem_stats.misses) > 0:
                return mem_stats

        hit_rate = (self._hits / total_lookups) if total_lookups > 0 else 0.0
        avg_sim = (sum(self._similarities) / len(self._similarities)) if self._similarities else 0.0
        return CacheStats(
            hit_rate=round(hit_rate, 4),
            total_entries=0,
            memory_usage=0,
            avg_similarity=round(avg_sim, 4),
            hits=self._hits,
            misses=self._misses,
        )

    async def clear(self) -> None:
        try:
            r = await get_redis()
            if r is not None:
                await r.delete(f"{self.namespace}:entries")
        except Exception as exc:
            logger.debug("Redis clear failed: %s", exc)
        self._hits = 0
        self._misses = 0
        self._similarities.clear()
        _get_in_memory_cache().clear()


_distributed_semantic_cache: Optional[DistributedSemanticCache] = None


def get_distributed_semantic_cache() -> DistributedSemanticCache:
    """Retrieve global DistributedSemanticCache singleton."""
    global _distributed_semantic_cache
    if _distributed_semantic_cache is None:
        _distributed_semantic_cache = DistributedSemanticCache()
    return _distributed_semantic_cache


def reset_distributed_semantic_cache() -> None:
    """Reset global DistributedSemanticCache singleton."""
    global _distributed_semantic_cache
    _distributed_semantic_cache = None
