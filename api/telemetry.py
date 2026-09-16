"""
api/telemetry.py — Token Governance Observability and Telemetry Tracker.

Tracks metrics for token consumption, tokens saved via semantic caching,
cache hit/miss ratios, RAG retrieval events, and prompt version utilization.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict

logger = logging.getLogger(__name__)


class TokenUsageTracker:
    """Thread-safe telemetry tracker for token governance operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens_used_input: int = 0
        self._tokens_used_output: int = 0
        self._tokens_saved: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._rag_retrieved: int = 0
        self._version_usage: Dict[str, int] = {}
        self._study_counter: int = 0

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        agent_handle: str = "unknown",
    ) -> None:
        """Record actual LLM / tool token consumption."""
        with self._lock:
            self._tokens_used_input += max(0, input_tokens)
            self._tokens_used_output += max(0, output_tokens)
            self._study_counter += 1
        logger.debug(
            "Telemetry usage recorded for %s: input=%d, output=%d",
            agent_handle,
            input_tokens,
            output_tokens,
        )

    def record_cache_hit(self, tokens_saved: int, agent_handle: str = "unknown") -> None:
        """Record a semantic cache hit and tokens avoided."""
        with self._lock:
            self._cache_hits += 1
            self._tokens_saved += max(0, tokens_saved)
        logger.info(
            "Semantic cache hit for %s (saved ~%d tokens)",
            agent_handle,
            tokens_saved,
        )

    def record_cache_miss(self, agent_handle: str = "unknown") -> None:
        """Record a semantic cache miss."""
        with self._lock:
            self._cache_misses += 1
        logger.debug("Semantic cache miss for %s", agent_handle)

    def record_rag_retrieved(self, count: int = 1, agent_handle: str = "unknown") -> None:
        """Record RAG context retrievals."""
        with self._lock:
            self._rag_retrieved += max(0, count)
        logger.debug(
            "RAG retrieved %d items for %s",
            count,
            agent_handle,
        )

    def record_version_used(self, version_id: str, agent_handle: str = "unknown") -> None:
        """Record prompt version execution."""
        with self._lock:
            self._version_usage[version_id] = self._version_usage.get(version_id, 0) + 1
        logger.debug(
            "Prompt version %s used for agent %s",
            version_id,
            agent_handle,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Return snapshot of current metrics."""
        with self._lock:
            total_lookups = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_lookups * 100.0) if total_lookups > 0 else 0.0
            return {
                "tokens_used_input": self._tokens_used_input,
                "tokens_used_output": self._tokens_used_output,
                "total_tokens_used": self._tokens_used_input + self._tokens_used_output,
                "tokens_saved": self._tokens_saved,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_lookups": total_lookups,
                "cache_hit_rate_pct": round(hit_rate, 2),
                "rag_retrieved": self._rag_retrieved,
                "version_usage": dict(self._version_usage),
                "total_studies_tracked": self._study_counter,
            }

    def reset(self) -> None:
        """Reset all metrics (primarily for test isolation)."""
        with self._lock:
            self._tokens_used_input = 0
            self._tokens_used_output = 0
            self._tokens_saved = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._rag_retrieved = 0
            self._version_usage.clear()
            self._study_counter = 0


# Global singleton instance
tracker = TokenUsageTracker()
