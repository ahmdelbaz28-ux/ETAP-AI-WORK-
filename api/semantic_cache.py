"""
api/semantic_cache.py — Semantic Cache Layer (Phase 2).

Provides semantic caching for power system studies and LLM agent outputs.
Key features:
1. Deterministic canonical key generation (SHA256 of sorted, normalized JSON + agent handle)
2. Vector similarity search with local cosine embedding and fallback
3. TTL enforcement (24h default, configurable)
4. Telemetry integration tracking tokens saved and cache hit rates
5. Thread-safe in-memory cache with optional disk persistence
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from api.telemetry import tracker

logger = logging.getLogger(__name__)


@dataclass
class CachedResult:
    """Represents a cached study or agent result."""

    result: Dict[str, Any]
    tokens_saved: int
    similarity: float
    cached_at: float
    cache_key: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """Statistics for the Semantic Cache."""

    hit_rate: float
    total_entries: int
    memory_usage: int
    avg_similarity: float
    hits: int
    misses: int


def _canonicalize_value(val: Any) -> Any:
    """Deterministically canonicalize data structures for exact hash matching.

    - dicts: sorted by key, keys stripped, values recursively canonicalized
    - lists: canonicalized item by item
    - strings: trimmed
    - floats: rounded to 5 decimal places to withstand minor float precision variances
      while strictly detecting intentional parameter changes (e.g. 1e-5 vs 1e-4)
    """
    if isinstance(val, dict):
        return {
            str(k).strip(): _canonicalize_value(v)
            for k, v in sorted(val.items(), key=lambda item: str(item[0]).strip())
        }
    elif isinstance(val, (list, tuple)):
        return [_canonicalize_value(v) for v in val]
    elif isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return str(val)
        return round(val, 5)
    elif isinstance(val, str):
        return val.strip()
    return val


class SemanticCache:
    """Semantic Cache with canonical keying, cosine similarity, and TTL management."""

    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 86400,
        storage_path: Optional[str] = None,
    ) -> None:
        self.embedding_model = embedding_model
        self.threshold = similarity_threshold
        self.ttl = ttl_seconds
        self.storage_path = Path(storage_path) if storage_path else None
        self._lock = threading.RLock()
        # storage: cache_key -> dict(result, tokens_saved, cached_at, embedding, agent_handle, metadata)
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._similarities: List[float] = []

        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    def _make_cache_key(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
    ) -> str:
        """Compute SHA256 hash of canonical JSON + agent handle."""
        canonical_sys = _canonicalize_value(system_data or {})
        canonical_params = _canonicalize_value(parameters or {})
        payload = {
            "agent_handle": agent_handle.strip().lower(),
            "system": canonical_sys,
            "parameters": canonical_params,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _is_degraded(self) -> bool:
        """Check if cache is in degraded mode (exact-match SHA256 only).
        Per safety guardrail: when Embedding API is down/absent,
        Semantic Cache falls back to exact-match key (SHA256).
        """
        return not bool(os.getenv("OPENAI_API_KEY")) and not getattr(
            self, "_force_vector_search", False
        )

    def _embed(self, system_text: str, param_text: str) -> np.ndarray:
        """Generate partitioned vector embedding with deterministic local fallback.
        System topology and parameters occupy distinct orthogonal subspaces (0..127 and 128..255),
        ensuring simulation parameter changes (e.g. tolerance 1e-5 vs 1e-4) are strongly preserved.
        """
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
                vec[idx] += 2.0  # Simulation parameters have high discriminant weight

        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two unit vectors."""
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom < 1e-9:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _is_expired(self, cached_at: float, custom_ttl: Optional[int] = None) -> bool:
        ttl = custom_ttl if custom_ttl is not None else self.ttl
        return (time.time() - cached_at) > ttl

    async def lookup(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
    ) -> Optional[CachedResult]:
        """Lookup cached result if match exists and is within TTL."""
        norm_handle = agent_handle.strip().lower()
        key = self._make_cache_key(system_data, parameters, norm_handle)

        with self._lock:
            # 1. Exact match by canonical SHA256 key
            if key in self._entries:
                entry = self._entries[key]
                if not self._is_expired(entry["cached_at"], entry.get("ttl")):
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
                    # Evict expired
                    del self._entries[key]

            # If in degraded mode (Embedding API down/absent), exact-match SHA256 is authoritative
            if self._is_degraded():
                self._misses += 1
                tracker.record_cache_miss(agent_handle=norm_handle)
                return None

            # 2. Semantic vector similarity match across entries for same agent
            sys_str = json.dumps(_canonicalize_value(system_data), sort_keys=True)
            param_str = json.dumps(_canonicalize_value(parameters), sort_keys=True)
            query_emb = self._embed(sys_str, param_str)

            best_match: Optional[Tuple[str, Dict[str, Any], float]] = None
            expired_keys: List[str] = []

            for k, entry in self._entries.items():
                if entry.get("agent_handle") != norm_handle:
                    continue
                if self._is_expired(entry["cached_at"], entry.get("ttl")):
                    expired_keys.append(k)
                    continue

                sim = self._cosine_similarity(query_emb, entry["embedding"])
                if sim >= self.threshold:
                    if best_match is None or sim > best_match[2]:
                        best_match = (k, entry, sim)

            for exp_k in expired_keys:
                self._entries.pop(exp_k, None)

            if best_match:
                matched_key, entry, sim = best_match
                self._hits += 1
                self._similarities.append(sim)
                tokens_saved = entry.get("tokens_saved", 2000)
                tracker.record_cache_hit(tokens_saved, agent_handle=norm_handle)
                return CachedResult(
                    result=copy.deepcopy(entry["result"]),
                    tokens_saved=tokens_saved,
                    similarity=round(sim, 4),
                    cached_at=entry["cached_at"],
                    cache_key=matched_key,
                    metadata=copy.deepcopy(entry.get("metadata", {})),
                )

            # 3. Cache miss
            self._misses += 1
            tracker.record_cache_miss(agent_handle=norm_handle)
            return None

    async def store(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None,
        custom_ttl: Optional[int] = None,
    ) -> None:
        """Store study result along with embedding, canonical key, and metadata."""
        norm_handle = agent_handle.strip().lower()
        key = self._make_cache_key(system_data, parameters, norm_handle)
        meta = metadata or {}
        tokens_used = meta.get("tokens_used", 2000)

        sys_str = json.dumps(_canonicalize_value(system_data), sort_keys=True)
        param_str = json.dumps(_canonicalize_value(parameters), sort_keys=True)
        emb = self._embed(sys_str, param_str)

        # Convert Pydantic model to dict if needed
        res_dict = result.model_dump() if hasattr(result, "model_dump") else copy.deepcopy(result)

        with self._lock:
            self._entries[key] = {
                "result": res_dict,
                "tokens_saved": tokens_used,
                "cached_at": time.time(),
                "embedding": emb,
                "agent_handle": norm_handle,
                "ttl": custom_ttl or self.ttl,
                "metadata": meta,
            }
            if self.storage_path:
                self._persist_to_disk()

    def get_stats(self) -> CacheStats:
        """Return cache hit rate, size, and similarity statistics."""
        with self._lock:
            total_lookups = self._hits + self._misses
            hit_rate = (self._hits / total_lookups) if total_lookups > 0 else 0.0
            avg_sim = (
                (sum(self._similarities) / len(self._similarities)) if self._similarities else 0.0
            )
            # Rough memory estimate
            entry_count = len(self._entries)
            memory_usage = entry_count * 1024  # approx 1KB per entry in memory

            return CacheStats(
                hit_rate=round(hit_rate, 4),
                total_entries=entry_count,
                memory_usage=memory_usage,
                avg_similarity=round(avg_sim, 4),
                hits=self._hits,
                misses=self._misses,
            )

    def clear(self) -> None:
        """Clear all cache entries and stats (used in testing)."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._similarities.clear()
            if self.storage_path and self.storage_path.exists():
                try:
                    self.storage_path.unlink()
                except Exception as e:
                    logger.warning("Could not delete cache file: %s", e)

    def _persist_to_disk(self) -> None:
        """Safely save cache state to disk."""
        if not self.storage_path:
            return
        try:
            data = {}
            for k, entry in self._entries.items():
                item = dict(entry)
                item["embedding"] = item["embedding"].tolist()
                data[k] = item
            tmp = self.storage_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(self.storage_path)
        except Exception as e:
            logger.warning("Failed to persist semantic cache to %s: %s", self.storage_path, e)

    def _load_from_disk(self) -> None:
        """Safely load cache state from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            content = self.storage_path.read_text(encoding="utf-8")
            raw_data = json.loads(content)
            for k, entry in raw_data.items():
                entry["embedding"] = np.array(entry["embedding"], dtype=np.float32)
                self._entries[k] = entry
        except Exception as e:
            logger.warning("Failed to load semantic cache from %s: %s", self.storage_path, e)


# Global singleton
_semantic_cache: Optional[SemanticCache] = None
_cache_lock = threading.Lock()


def get_semantic_cache() -> SemanticCache:
    """Retrieve global SemanticCache singleton."""
    global _semantic_cache
    if _semantic_cache is None:
        with _cache_lock:
            if _semantic_cache is None:
                _semantic_cache = SemanticCache()
    return _semantic_cache


def reset_semantic_cache() -> None:
    """Reset global SemanticCache singleton."""
    global _semantic_cache
    with _cache_lock:
        if _semantic_cache is not None:
            _semantic_cache.clear()
        _semantic_cache = None
