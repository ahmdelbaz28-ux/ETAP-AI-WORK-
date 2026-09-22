"""
api/prompt_registry.py — Prompt Versioning and A/B Measurement (Phase 4).

Provides systematic prompt version control, candidate A/B evaluation,
trade-off reporting (tokens vs. latency vs. quality score), and safe promotion.
"""

from __future__ import annotations

import copy
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """A versioned prompt configuration for an agent."""

    version_id: str
    agent_handle: str
    prompt_text: str
    temperature: float = 0.2
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "agent_handle": self.agent_handle,
            "prompt_text": self.prompt_text,
            "temperature": self.temperature,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass
class PromptMetrics:
    """Telemetry and performance metrics for a specific prompt version."""

    version_id: str
    call_count: int = 0
    tokens_used_total: int = 0
    latency_ms_total: float = 0.0
    successes: int = 0
    failures: int = 0
    quality_scores: List[float] = field(default_factory=list)

    @property
    def avg_tokens(self) -> float:
        return round(self.tokens_used_total / self.call_count, 2) if self.call_count > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return round(self.latency_ms_total / self.call_count, 2) if self.call_count > 0 else 0.0

    @property
    def success_rate(self) -> float:
        return round(self.successes / self.call_count, 4) if self.call_count > 0 else 0.0

    @property
    def avg_quality_score(self) -> float:
        return (
            round(sum(self.quality_scores) / len(self.quality_scores), 4)
            if self.quality_scores
            else 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "call_count": self.call_count,
            "tokens_used_total": self.tokens_used_total,
            "avg_tokens": self.avg_tokens,
            "latency_ms_total": round(self.latency_ms_total, 2),
            "avg_latency_ms": self.avg_latency_ms,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": self.success_rate,
            "avg_quality_score": self.avg_quality_score,
        }


class PromptRegistry:
    """Manages prompt versions, A/B routing, and metric evaluation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # version_id -> PromptVersion
        self._versions: Dict[str, PromptVersion] = {}
        # agent_handle -> list of version_id
        self._agent_versions: Dict[str, List[str]] = {}
        # version_id -> PromptMetrics
        self._metrics: Dict[str, PromptMetrics] = {}

    def register_version(
        self,
        agent_handle: str,
        prompt_text: str,
        temperature: float = 0.2,
        metadata: Optional[Dict[str, Any]] = None,
        is_active: bool = False,
    ) -> PromptVersion:
        """Register a new prompt version for an agent."""
        norm_handle = agent_handle.strip().lower()
        meta = metadata or {}

        with self._lock:
            existing = self._agent_versions.get(norm_handle, [])
            version_num = len(existing) + 1
            version_id = f"{norm_handle}:v{version_num}"

            # If this is the first version, make it active automatically
            should_activate = is_active or (len(existing) == 0)

            if should_activate:
                for vid in existing:
                    if vid in self._versions:
                        self._versions[vid].is_active = False

            pv = PromptVersion(
                version_id=version_id,
                agent_handle=norm_handle,
                prompt_text=prompt_text,
                temperature=temperature,
                metadata=copy.deepcopy(meta),
                is_active=should_activate,
                created_at=time.time(),
            )

            self._versions[version_id] = pv
            if norm_handle not in self._agent_versions:
                self._agent_versions[norm_handle] = []
            self._agent_versions[norm_handle].append(version_id)
            self._metrics[version_id] = PromptMetrics(version_id=version_id)

            logger.info("Registered prompt version %s (active=%s)", version_id, should_activate)
            return copy.deepcopy(pv)

    def get_active_version(
        self,
        agent_handle: str,
        candidate_traffic_pct: float = 0.0,
    ) -> Optional[PromptVersion]:
        """Get the active or canary candidate prompt version with optional A/B traffic split."""
        norm_handle = agent_handle.strip().lower()

        with self._lock:
            vids = self._agent_versions.get(norm_handle, [])
            if not vids:
                return None

            active_ver: Optional[PromptVersion] = None
            candidate_vers: List[PromptVersion] = []

            for vid in vids:
                ver = self._versions.get(vid)
                if ver:
                    if ver.is_active:
                        active_ver = ver
                    else:
                        candidate_vers.append(ver)

            # A/B candidate evaluation if requested
            if candidate_traffic_pct > 0.0 and candidate_vers:
                if (secrets.randbelow(10000) / 100.0) < candidate_traffic_pct:
                    # Serve latest candidate
                    return copy.deepcopy(candidate_vers[-1])

            if active_ver is not None:
                return copy.deepcopy(active_ver)

            # Fallback to the latest version if none marked active
            return copy.deepcopy(self._versions[vids[-1]])

    def record_metrics(
        self,
        version_id: str,
        tokens_used: int,
        latency_ms: float,
        success: bool = True,
        quality_score: Optional[float] = None,
    ) -> None:
        """Record runtime invocation metrics for a prompt version."""
        with self._lock:
            metrics = self._metrics.get(version_id)
            if not metrics:
                metrics = PromptMetrics(version_id=version_id)
                self._metrics[version_id] = metrics

            metrics.call_count += 1
            metrics.tokens_used_total += max(0, tokens_used)
            metrics.latency_ms_total += max(0.0, latency_ms)
            if success:
                metrics.successes += 1
            else:
                metrics.failures += 1

            if quality_score is not None:
                metrics.quality_scores.append(float(quality_score))

    def promote_version(self, version_id: str) -> bool:
        """Promote a candidate version to be the active version."""
        with self._lock:
            target = self._versions.get(version_id)
            if not target:
                return False

            norm_handle = target.agent_handle
            vids = self._agent_versions.get(norm_handle, [])
            for vid in vids:
                ver = self._versions.get(vid)
                if ver:
                    ver.is_active = vid == version_id

            logger.info("Promoted prompt version %s to active", version_id)
            return True

    def get_tradeoff_report(self, agent_handle: Optional[str] = None) -> Dict[str, Any]:
        """Generate a comparative trade-off report across versions."""
        with self._lock:
            handles = (
                [agent_handle.strip().lower()]
                if agent_handle
                else list(self._agent_versions.keys())
            )
            report: Dict[str, Any] = {}

            for handle in handles:
                vids = self._agent_versions.get(handle, [])
                if not vids:
                    continue

                version_reports: List[Dict[str, Any]] = []
                baseline_tokens: Optional[float] = None

                for idx, vid in enumerate(vids):
                    ver = self._versions.get(vid)
                    metrics = self._metrics.get(vid, PromptMetrics(version_id=vid))
                    if not ver:
                        continue

                    avg_tok = metrics.avg_tokens
                    if idx == 0 and avg_tok > 0:
                        baseline_tokens = avg_tok

                    token_savings_pct = 0.0
                    if baseline_tokens and baseline_tokens > 0 and avg_tok > 0:
                        token_savings_pct = round(
                            ((baseline_tokens - avg_tok) / baseline_tokens) * 100.0, 2
                        )

                    version_reports.append(
                        {
                            "version_id": vid,
                            "is_active": ver.is_active,
                            "temperature": ver.temperature,
                            "metrics": metrics.to_dict(),
                            "token_savings_pct": token_savings_pct,
                        }
                    )

                report[handle] = {
                    "total_versions": len(vids),
                    "versions": version_reports,
                }

            return report

    def clear(self) -> None:
        """Clear all registered versions and metrics (test helper)."""
        with self._lock:
            self._versions.clear()
            self._agent_versions.clear()
            self._metrics.clear()


# Global singleton instance
_prompt_registry: Optional[PromptRegistry] = None
_registry_lock = threading.Lock()


def get_prompt_registry() -> PromptRegistry:
    """Retrieve global PromptRegistry singleton."""
    global _prompt_registry
    if _prompt_registry is None:
        with _registry_lock:
            if _prompt_registry is None:
                _prompt_registry = PromptRegistry()
    return _prompt_registry


def reset_prompt_registry() -> None:
    """Reset global PromptRegistry singleton."""
    global _prompt_registry
    with _registry_lock:
        if _prompt_registry is not None:
            _prompt_registry.clear()
        _prompt_registry = None
