"""
api/prompt_registry_redis.py — Distributed Prompt Registry using Redis.

Replaces in-memory PromptRegistry for multi-instance horizontal scaling,
with seamless fallback to in-memory PromptRegistry when Redis is unavailable.
"""

from __future__ import annotations

import copy
import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional

from api.prompt_registry import (
    PromptMetrics,
    PromptVersion,
)
from api.prompt_registry import (
    get_prompt_registry as _get_in_memory_registry,
)
from api.redis_client import get_redis

logger = logging.getLogger(__name__)


class DistributedPromptRegistry:
    """Distributed Prompt Registry backed by Redis with A/B routing and metric tracking."""

    def __init__(self, namespace: str = "prompt_registry") -> None:
        self.namespace = namespace

    def _versions_key(self, agent_handle: str) -> str:
        return f"{self.namespace}:versions:{agent_handle}"

    def _version_key(self, version_id: str) -> str:
        return f"{self.namespace}:version:{version_id}"

    def _metrics_key(self, version_id: str) -> str:
        return f"{self.namespace}:metrics:{version_id}"

    async def register_version(
        self,
        agent_handle: str,
        prompt_text: str,
        temperature: float = 0.2,
        metadata: Optional[Dict[str, Any]] = None,
        is_active: bool = False,
    ) -> PromptVersion:
        norm_handle = agent_handle.strip().lower()
        meta = metadata or {}

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            version_count = await r.llen(self._versions_key(norm_handle))
            version_num = version_count + 1
            version_id = f"{norm_handle}:v{version_num}"

            should_activate = is_active or (version_count == 0)
            if should_activate:
                existing_ids = await r.lrange(self._versions_key(norm_handle), 0, -1)
                for vid in existing_ids:
                    v_data = await r.get(self._version_key(vid))
                    if v_data:
                        v = json.loads(v_data)
                        v["is_active"] = False
                        await r.set(self._version_key(vid), json.dumps(v))

            pv = PromptVersion(
                version_id=version_id,
                agent_handle=norm_handle,
                prompt_text=prompt_text,
                temperature=temperature,
                metadata=copy.deepcopy(meta),
                is_active=should_activate,
                created_at=time.time(),
            )

            await r.set(self._version_key(version_id), json.dumps(pv.to_dict()))
            await r.rpush(self._versions_key(norm_handle), version_id)
            await r.set(
                self._metrics_key(version_id),
                json.dumps(PromptMetrics(version_id=version_id).to_dict()),
            )

            logger.info(
                "Registered distributed prompt version %s (active=%s)", version_id, should_activate
            )
            return pv
        except Exception as exc:
            logger.debug("Redis prompt register_version failed, falling back to memory: %s", exc)
            return _get_in_memory_registry().register_version(
                agent_handle,
                prompt_text,
                temperature,
                metadata,
                is_active,
            )

    async def get_active_version(
        self,
        agent_handle: str,
        candidate_traffic_pct: float = 0.0,
    ) -> Optional[PromptVersion]:
        norm_handle = agent_handle.strip().lower()
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            vids = await r.lrange(self._versions_key(norm_handle), 0, -1)
            if not vids:
                return None

            active_ver: Optional[PromptVersion] = None
            candidate_vers: List[PromptVersion] = []

            for vid in vids:
                v_data = await r.get(self._version_key(vid))
                if not v_data:
                    continue
                ver = PromptVersion(**json.loads(v_data))
                if ver.is_active:
                    active_ver = ver
                else:
                    candidate_vers.append(ver)

            if candidate_traffic_pct > 0.0 and candidate_vers:
                if secrets.SystemRandom().random() * 100.0 < candidate_traffic_pct:
                    return candidate_vers[-1]

            if active_ver:
                return active_ver

            latest_data = await r.get(self._version_key(vids[-1]))
            if latest_data:
                return PromptVersion(**json.loads(latest_data))
            return None
        except Exception as exc:
            logger.debug("Redis get_active_version failed, falling back to memory: %s", exc)
            return _get_in_memory_registry().get_active_version(agent_handle, candidate_traffic_pct)

    async def record_metrics(
        self,
        version_id: str,
        tokens_used: int,
        latency_ms: float,
        success: bool = True,
        quality_score: Optional[float] = None,
    ) -> None:
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            metrics_data = await r.get(self._metrics_key(version_id))
            if metrics_data:
                metrics = PromptMetrics(**json.loads(metrics_data))
            else:
                metrics = PromptMetrics(version_id=version_id)

            metrics.call_count += 1
            metrics.tokens_used_total += max(0, tokens_used)
            metrics.latency_ms_total += max(0.0, latency_ms)
            if success:
                metrics.successes += 1
            else:
                metrics.failures += 1
            if quality_score is not None:
                metrics.quality_scores.append(float(quality_score))

            await r.set(self._metrics_key(version_id), json.dumps(metrics.to_dict()))
        except Exception as exc:
            logger.debug("Redis record_metrics failed, falling back to memory: %s", exc)
            _get_in_memory_registry().record_metrics(
                version_id, tokens_used, latency_ms, success, quality_score
            )

    async def promote_version(self, version_id: str) -> bool:
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            target_data = await r.get(self._version_key(version_id))
            if not target_data:
                return False

            target = PromptVersion(**json.loads(target_data))
            norm_handle = target.agent_handle

            vids = await r.lrange(self._versions_key(norm_handle), 0, -1)
            for vid in vids:
                v_data = await r.get(self._version_key(vid))
                if v_data:
                    ver = PromptVersion(**json.loads(v_data))
                    ver.is_active = vid == version_id
                    await r.set(self._version_key(vid), json.dumps(ver.to_dict()))

            logger.info("Promoted prompt version %s to active", version_id)
            return True
        except Exception as exc:
            logger.debug("Redis promote_version failed, falling back to memory: %s", exc)
            return _get_in_memory_registry().promote_version(version_id)

    async def get_tradeoff_report(self, agent_handle: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            report: Dict[str, Any] = {}
            if agent_handle:
                handles = [agent_handle.strip().lower()]
            else:
                handles = []
                cursor = 0
                while True:
                    cursor, keys = await r.scan(
                        cursor, match=f"{self.namespace}:versions:*", count=100
                    )
                    for k in keys:
                        k_str = k.decode() if isinstance(k, bytes) else str(k)
                        handles.append(k_str)
                    if cursor == 0:
                        break
                handles = [k.replace(f"{self.namespace}:versions:", "") for k in handles]

            for handle in handles:
                vids = await r.lrange(self._versions_key(handle), 0, -1)
                if not vids:
                    continue

                version_reports: List[Dict[str, Any]] = []
                baseline_tokens: Optional[float] = None

                for idx, vid in enumerate(vids):
                    v_data = await r.get(self._version_key(vid))
                    m_data = await r.get(self._metrics_key(vid))
                    if not v_data:
                        continue
                    ver = PromptVersion(**json.loads(v_data))
                    metrics = (
                        PromptMetrics(**json.loads(m_data))
                        if m_data
                        else PromptMetrics(version_id=vid)
                    )

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
        except Exception as exc:
            logger.debug("Redis get_tradeoff_report failed, falling back to memory: %s", exc)
            return _get_in_memory_registry().get_tradeoff_report(agent_handle)

    async def clear(self) -> None:
        try:
            r = await get_redis()
            if r is not None:
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor, match=f"{self.namespace}:*", count=100)
                    if keys:
                        await r.delete(*keys)
                    if cursor == 0:
                        break
        except Exception as exc:
            logger.debug("Redis clear failed: %s", exc)
        _get_in_memory_registry().clear()


_distributed_prompt_registry: Optional[DistributedPromptRegistry] = None


def get_distributed_prompt_registry() -> DistributedPromptRegistry:
    """Retrieve global DistributedPromptRegistry singleton."""
    global _distributed_prompt_registry
    if _distributed_prompt_registry is None:
        _distributed_prompt_registry = DistributedPromptRegistry()
    return _distributed_prompt_registry


def reset_distributed_prompt_registry() -> None:
    """Reset global DistributedPromptRegistry singleton."""
    global _distributed_prompt_registry
    _distributed_prompt_registry = None
