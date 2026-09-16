"""
api/rag_retriever_redis.py — Distributed RAG Retriever using Redis.

Replaces in-memory RAGRetriever for multi-instance horizontal scaling,
with seamless fallback to in-memory RAGRetriever when Redis is unavailable.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from api.rag_retriever import (
    RAGResult,
)
from api.rag_retriever import (
    get_rag_retriever as _get_in_memory_rag,
)
from api.redis_client import get_redis
from api.telemetry import tracker

logger = logging.getLogger(__name__)


class DistributedRAGRetriever:
    """Distributed RAG Retriever backed by Redis with hybrid similarity matching."""

    def __init__(
        self,
        collection_name: str = "study_results",
        top_k: int = 3,
        similarity_threshold: float = 0.85,
        namespace: str = "rag",
    ) -> None:
        self.collection_name = collection_name
        self.top_k = top_k
        self.threshold = similarity_threshold
        self.namespace = namespace

    def _extract_tokens(self, text: str) -> List[str]:
        clean = text.lower().strip()
        raw = re.findall(r"[a-zA-Z0-9]+", clean)
        tokens: List[str] = []
        for t in raw:
            tokens.append(t)
            if t.endswith("es") and len(t) > 4:
                tokens.append(t[:-2])
            elif t.endswith("s") and len(t) > 3:
                tokens.append(t[:-1])
        return tokens

    def _embed(self, tokens: List[str], dim: int = 512) -> np.ndarray:
        vec = np.zeros(dim, dtype=np.float32)
        for tok in tokens:
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16) % dim
            vec[h] += 1.0
        return vec

    def _calculate_similarity(
        self,
        q_tokens: List[str],
        q_vec: np.ndarray,
        d_tokens_set: set,
        d_vec: np.ndarray,
    ) -> float:
        if not q_tokens or len(d_tokens_set) == 0:
            return 0.0
        norm_q = np.linalg.norm(q_vec)
        norm_d = np.linalg.norm(d_vec)
        if norm_q < 1e-9 or norm_d < 1e-9:
            return 0.0
        cos = float(np.dot(q_vec, d_vec) / (norm_q * norm_d))
        matches = sum(1 for t in q_tokens if t in d_tokens_set)
        recall = matches / len(q_tokens)
        score = 0.5 * cos + 0.5 * recall
        return max(0.0, min(1.0, score))

    async def index_result(
        self,
        result_id: str,
        summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not result_id:
            return
        meta = metadata or {}
        agent_handle = str(meta.get("agent_handle") or meta.get("study_type") or "").strip().lower()

        text_corpus = (
            f"{agent_handle} {json.dumps(summary, default=str)} {json.dumps(meta, default=str)}"
        )
        tokens = self._extract_tokens(text_corpus)
        emb = self._embed(tokens)

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            entry = {
                "summary": copy.deepcopy(summary),
                "metadata": copy.deepcopy(meta),
                "agent_handle": agent_handle,
                "tokens_set": list(set(tokens)),
                "embedding": emb.tolist(),
                "indexed_at": time.time(),
            }
            await r.hset(f"{self.namespace}:index", result_id, json.dumps(entry))
        except Exception as exc:
            logger.debug("Redis RAG index_result failed, falling back to memory: %s", exc)
            await _get_in_memory_rag().index_result(result_id, summary, metadata)

    async def retrieve(
        self,
        query: str,
        system_context: Optional[Dict[str, Any]] = None,
        agent_handle: str = "unknown",
    ) -> List[RAGResult]:
        start_time = time.time()
        norm_handle = agent_handle.strip().lower()
        context_str = json.dumps(system_context or {}, default=str)
        search_text = f"{norm_handle} {query} {context_str}"
        q_tokens = self._extract_tokens(search_text)
        q_emb = self._embed(q_tokens)

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            matches: List[RAGResult] = []
            cursor = 0

            while True:
                cursor, data = await r.hscan(f"{self.namespace}:index", cursor=cursor, count=100)
                items: List[Tuple[str, str]] = []
                if isinstance(data, dict):
                    items = list(data.items())
                elif isinstance(data, (list, tuple)):
                    if data and isinstance(data[0], (list, tuple)):
                        items = [(k, v) for k, v in data]
                    else:
                        for k in data:
                            val = await r.hget(f"{self.namespace}:index", k)
                            if val:
                                items.append((k, val))

                for k, val_json in items:
                    entry = json.loads(val_json)
                    stored_handle = entry.get("agent_handle", "")
                    if (
                        stored_handle
                        and norm_handle not in ("unknown", "")
                        and stored_handle != norm_handle
                    ):
                        continue

                    sim = self._calculate_similarity(
                        q_tokens,
                        q_emb,
                        set(entry["tokens_set"]),
                        np.array(entry["embedding"], dtype=np.float32),
                    )
                    if sim >= self.threshold:
                        matches.append(
                            RAGResult(
                                result_id=k,
                                similarity=round(sim, 4),
                                summary=copy.deepcopy(entry["summary"]),
                                metadata=copy.deepcopy(entry["metadata"]),
                            )
                        )

                if cursor == 0:
                    break

            matches.sort(key=lambda x: x.similarity, reverse=True)
            results = matches[: self.top_k]

            elapsed_ms = (time.time() - start_time) * 1000.0
            logger.debug(
                "Distributed RAG retrieved %d items for %s in %.2fms",
                len(results),
                norm_handle,
                elapsed_ms,
            )

            if results:
                tracker.record_rag_retrieved(len(results), agent_handle=norm_handle)

            return results
        except Exception as exc:
            logger.debug("Redis RAG retrieve failed, falling back to memory: %s", exc)
            return await _get_in_memory_rag().retrieve(query, system_context, agent_handle)

    async def clear(self) -> None:
        try:
            r = await get_redis()
            if r is not None:
                await r.delete(f"{self.namespace}:index")
        except Exception as exc:
            logger.debug("Redis clear failed: %s", exc)
        _get_in_memory_rag().clear()


_distributed_rag_retriever: Optional[DistributedRAGRetriever] = None


def get_distributed_rag_retriever() -> DistributedRAGRetriever:
    """Retrieve global DistributedRAGRetriever singleton."""
    global _distributed_rag_retriever
    if _distributed_rag_retriever is None:
        _distributed_rag_retriever = DistributedRAGRetriever()
    return _distributed_rag_retriever


def reset_distributed_rag_retriever() -> None:
    """Reset global DistributedRAGRetriever singleton."""
    global _distributed_rag_retriever
    _distributed_rag_retriever = None
