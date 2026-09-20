"""
api/semantic_cache_v2.py — Dense Neural Semantic Cache with Vectorized Similarity.

Upgrades trigram-hashed semantic cache to 384-dimensional dense sentence embeddings
(all-MiniLM-L6-v2) with vectorized cosine similarity matrix evaluations, significantly
boosting semantic hit-rates across paraphrased engineering requests.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from api.semantic_cache import (
    CachedResult,
    CacheStats,
    _canonicalize_value,
)
from api.telemetry import tracker

logger = logging.getLogger(__name__)

# Global lazy embedder model singleton
_EMBEDDER_MODEL = None
_EMBEDDER_TRIED = False


def _get_sentence_transformer():
    global _EMBEDDER_MODEL, _EMBEDDER_TRIED
    if not _EMBEDDER_TRIED:
        _EMBEDDER_TRIED = True
        try:
            from sentence_transformers import SentenceTransformer
            _EMBEDDER_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded all-MiniLM-L6-v2 for SemanticCacheV2")
        except Exception as e:
            logger.debug("SentenceTransformer load skipped or offline: %s", e)
            _EMBEDDER_MODEL = None
    return _EMBEDDER_MODEL


class SemanticCacheV2:
    """Vectorized Neural Semantic Cache satisfying the standard cache protocol."""

    def __init__(
        self,
        similarity_threshold: float = 0.88,
        max_entries: int = 500,
        ttl_seconds: int = 86400,
    ) -> None:
        self.threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl = ttl_seconds

        # Storage
        self._keys: List[str] = []
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._vectors: Optional[np.ndarray] = None  # (N x D) normalized matrix

        self._hits = 0
        self._misses = 0
        self._similarities: List[float] = []

    def _embed(self, query_text: str) -> np.ndarray:
        """Embed text using all-MiniLM-L6-v2 or deterministic projection fallback."""
        model = _get_sentence_transformer()
        if model is not None:
            try:
                emb = model.encode(query_text, convert_to_numpy=True)
                norm = np.linalg.norm(emb)
                return (emb / norm).astype(np.float32) if norm > 1e-6 else emb
            except Exception as e:
                logger.debug("Neural embedding failed, using local projector: %s", e)

        # Fallback: 384-dimensional seeded character/word projection
        dim = 384
        vec = np.zeros(dim, dtype=np.float32)
        words = query_text.lower().split()
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            vec[idx] += 1.0

        norm = np.linalg.norm(vec)
        return (vec / norm) if norm > 1e-6 else vec

    def _make_key(self, system_data: Any, parameters: Dict[str, Any], agent_handle: str) -> str:
        canonical_sys = _canonicalize_value(system_data or {})
        canonical_params = _canonicalize_value(parameters or {})
        payload = {
            "agent": agent_handle.strip().lower(),
            "system": canonical_sys,
            "parameters": canonical_params,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def lookup(
        self,
        system_data: Any,
        parameters: Dict[str, Any],
        agent_handle: str = "unknown",
    ) -> Optional[CachedResult]:
        """Perform vectorized cosine similarity search over cached engineering requests."""
        norm_handle = agent_handle.strip().lower()
        exact_key = self._make_key(system_data, parameters, norm_handle)

        # 1. Exact hash match
        if exact_key in self._entries:
            entry = self._entries[exact_key]
            if (time.time() - entry["cached_at"]) <= self.ttl:
                self._hits += 1
                self._similarities.append(1.0)
                tokens_saved = entry.get("tokens_saved", 2000)
                tracker.record_cache_hit(tokens_saved, agent_handle=norm_handle)
                return CachedResult(
                    result=copy.deepcopy(entry["result"]),
                    tokens_saved=tokens_saved,
                    similarity=1.0,
                    cached_at=entry["cached_at"],
                    cache_key=exact_key,
                    metadata=copy.deepcopy(entry.get("metadata", {})),
                )
            else:
                self._evict(exact_key)

        # 2. Vectorized semantic search
        if self._vectors is not None and len(self._keys) > 0:
            query_str = f"{norm_handle} {json.dumps(parameters, default=str)}"
            query_emb = self._embed(query_str)

            # Vectorized dot product against all cached vectors: (N,)
            similarities = self._vectors.dot(query_emb)
            best_idx = int(np.argmax(similarities))
            best_sim = float(similarities[best_idx])

            if best_sim >= self.threshold:
                matched_key = self._keys[best_idx]
                entry = self._entries[matched_key]

                if (time.time() - entry["cached_at"]) <= self.ttl:
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
                else:
                    self._evict(matched_key)

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
    ) -> str:
        """Store an engineering result into the semantic cache with its dense vector representation."""
        norm_handle = agent_handle.strip().lower()
        key = self._make_key(system_data, parameters, norm_handle)
        query_str = f"{norm_handle} {json.dumps(parameters, default=str)}"
        emb = self._embed(query_str)

        tokens_saved = int(metadata.get("tokens_saved", 2000)) if metadata else 2000

        entry = {
            "result": copy.deepcopy(result),
            "tokens_saved": tokens_saved,
            "cached_at": time.time(),
            "ttl": custom_ttl or self.ttl,
            "metadata": copy.deepcopy(metadata or {}),
        }

        # Handle capacity eviction
        if len(self._keys) >= self.max_entries and key not in self._entries:
            oldest_key = self._keys[0]
            self._evict(oldest_key)

        if key in self._entries:
            idx = self._keys.index(key)
            self._vectors[idx] = emb
        else:
            self._keys.append(key)
            if self._vectors is None:
                self._vectors = emb.reshape(1, -1)
            else:
                self._vectors = np.vstack([self._vectors, emb.reshape(1, -1)])

        self._entries[key] = entry
        return key

    def _evict(self, key: str) -> None:
        """Evict an entry from keys, entries, and matrix."""
        if key in self._entries:
            idx = self._keys.index(key)
            self._keys.pop(idx)
            del self._entries[key]
            if self._vectors is not None:
                if len(self._keys) == 0:
                    self._vectors = None
                else:
                    self._vectors = np.delete(self._vectors, idx, axis=0)

    @property
    def stats(self) -> CacheStats:
        total = self._hits + self._misses
        hit_ratio = (self._hits / total) if total > 0 else 0.0
        avg_sim = float(np.mean(self._similarities)) if self._similarities else 0.0
        return CacheStats(
            hit_rate=round(hit_ratio, 4),
            total_entries=len(self._entries),
            memory_usage=len(self._entries) * 384 * 4,
            avg_similarity=round(avg_sim, 4),
            hits=self._hits,
            misses=self._misses,
        )
