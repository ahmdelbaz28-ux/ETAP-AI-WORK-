"""
api/rag_retriever.py — RAG for Historical Results (Phase 3).

Retrieves relevant previous power system study summaries and execution plans
to provide historical context and avoid redundant re-computation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from api.telemetry import tracker

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """A retrieved historical study result."""

    result_id: str
    similarity: float
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "similarity": round(self.similarity, 4),
            "summary": self.summary,
            "metadata": self.metadata,
        }


class RAGRetriever:
    """Vector-based retriever for historical study results and summaries."""

    def __init__(
        self,
        collection_name: str = "study_results",
        top_k: int = 3,
        similarity_threshold: float = 0.85,
    ) -> None:
        self.collection_name = collection_name
        self.top_k = top_k
        self.threshold = similarity_threshold
        self._lock = threading.RLock()
        # id -> {summary, metadata, agent_handle, embedding}
        self._index: Dict[str, Dict[str, Any]] = {}

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract words and stem endings from text."""
        import re

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
        """Compute 512-dimensional term frequency vector."""
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
        """Calculate hybrid similarity combining cosine similarity and query recall."""
        if not q_tokens or len(d_tokens_set) == 0:
            return 0.0

        norm_q = np.linalg.norm(q_vec)
        norm_d = np.linalg.norm(d_vec)
        if norm_q < 1e-9 or norm_d < 1e-9:
            return 0.0
        cos = float(np.dot(q_vec, d_vec) / (norm_q * norm_d))

        # Query recall / containment
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
        """Add a study result to the RAG vector index."""
        if not result_id:
            return
        meta = metadata or {}
        agent_handle = str(meta.get("agent_handle") or meta.get("study_type") or "").strip().lower()

        # Build indexable text representation
        text_corpus = (
            f"{agent_handle} {json.dumps(summary, default=str)} {json.dumps(meta, default=str)}"
        )
        tokens = self._extract_tokens(text_corpus)
        emb = self._embed(tokens)

        with self._lock:
            self._index[result_id] = {
                "summary": copy.deepcopy(summary),
                "metadata": copy.deepcopy(meta),
                "agent_handle": agent_handle,
                "tokens_set": set(tokens),
                "embedding": emb,
                "indexed_at": time.time(),
            }

    async def retrieve(
        self,
        query: str,
        system_context: Optional[Dict[str, Any]] = None,
        agent_handle: str = "unknown",
    ) -> List[RAGResult]:
        """Retrieve top_k matching historical results above similarity threshold."""
        start_time = time.time()
        norm_handle = agent_handle.strip().lower()
        context_str = json.dumps(system_context or {}, default=str)
        search_text = f"{norm_handle} {query} {context_str}"
        q_tokens = self._extract_tokens(search_text)
        q_emb = self._embed(q_tokens)

        matches: List[RAGResult] = []

        with self._lock:
            for rid, item in self._index.items():
                stored_handle = item.get("agent_handle", "")
                if (
                    stored_handle
                    and norm_handle not in ("unknown", "")
                    and stored_handle != norm_handle
                ):
                    continue

                sim = self._calculate_similarity(
                    q_tokens,
                    q_emb,
                    item["tokens_set"],
                    item["embedding"],
                )
                if sim >= self.threshold:
                    matches.append(
                        RAGResult(
                            result_id=rid,
                            similarity=round(sim, 4),
                            summary=copy.deepcopy(item["summary"]),
                            metadata=copy.deepcopy(item["metadata"]),
                        )
                    )

        # Sort descending by similarity
        matches.sort(key=lambda r: r.similarity, reverse=True)
        results = matches[: self.top_k]

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.debug(
            "RAG retrieved %d items for %s in %.2fms",
            len(results),
            norm_handle,
            elapsed_ms,
        )

        if results:
            tracker.record_rag_retrieved(len(results), agent_handle=norm_handle)

        return results

    def clear(self) -> None:
        """Clear indexed items (test helper)."""
        with self._lock:
            self._index.clear()


# Global singleton instance
_rag_retriever: Optional[RAGRetriever] = None
_rag_lock = threading.Lock()


def get_rag_retriever() -> RAGRetriever:
    """Retrieve global RAGRetriever singleton."""
    global _rag_retriever
    if _rag_retriever is None:
        with _rag_lock:
            if _rag_retriever is None:
                _rag_retriever = RAGRetriever()
    return _rag_retriever


def reset_rag_retriever() -> None:
    """Reset global RAGRetriever singleton."""
    global _rag_retriever
    with _rag_lock:
        if _rag_retriever is not None:
            _rag_retriever.clear()
        _rag_retriever = None
