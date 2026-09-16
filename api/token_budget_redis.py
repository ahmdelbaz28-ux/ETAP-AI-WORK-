"""
api/token_budget_redis.py — Distributed Token Budget Manager using Redis.

Replaces in-memory TokenBudgetManager for multi-instance horizontal scaling,
with seamless fallback to in-memory TokenBudgetManager when Redis is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from api.redis_client import get_redis
from api.session_stream import publish_token_usage
from api.telemetry import tracker
from api.token_budget import (
    DEFAULT_AGENT_BUDGETS,
    DEFAULT_MAX_HISTORY_TOKENS,
)
from api.token_budget import (
    budget_manager as _in_memory_manager,
)

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 86400  # 24h


class DistributedTokenBudgetManager:
    """Redis-backed token budget manager for horizontal scaling with graceful in-memory fallback."""

    def __init__(
        self,
        agent_budgets: Optional[Dict[str, int]] = None,
        max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS,
    ) -> None:
        self._budgets = dict(DEFAULT_AGENT_BUDGETS)
        if agent_budgets:
            self._budgets.update(agent_budgets)
        self.max_history_tokens = max_history_tokens

    def _session_key(self, session_id: str) -> str:
        return f"token_budget:{session_id}"

    def _agent_field(self, agent_handle: str) -> str:
        return f"agent:{agent_handle}"

    def get_budget_for_agent(self, agent_handle: str) -> int:
        return self._budgets.get(agent_handle, self._budgets["default"])

    async def check_and_reserve(
        self,
        session_id: str,
        agent_handle: str,
        estimated_tokens: int,
    ) -> bool:
        budget = self.get_budget_for_agent(agent_handle)
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            key = self._session_key(session_id)
            field = self._agent_field(agent_handle)

            # Atomic check-and-reserve script
            lua = """
            local used = tonumber(redis.call('HGET', KEYS[1], ARGV[1] .. ':used') or '0')
            local reserved = tonumber(redis.call('HGET', KEYS[1], ARGV[1] .. ':reserved') or '0')
            local budget = tonumber(ARGV[2])
            local estimated = tonumber(ARGV[3])
            if (used + reserved + estimated) > budget then
                return 0
            end
            redis.call('HSET', KEYS[1], ARGV[1] .. ':reserved', reserved + estimated)
            redis.call('EXPIRE', KEYS[1], ARGV[4])
            return 1
            """
            result = await r.eval(lua, 1, key, field, budget, estimated_tokens, SESSION_TTL_SECONDS)
            return bool(result == 1)
        except Exception as exc:
            logger.debug("Redis token check_and_reserve failed, falling back to memory: %s", exc)
            return _in_memory_manager.check_and_reserve(session_id, agent_handle, estimated_tokens)

    async def record_usage(
        self,
        session_id: str,
        agent_handle: str,
        input_tokens: int,
        output_tokens: int,
        reserved_offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        total_used = max(0, input_tokens) + max(0, output_tokens)
        budget = self.get_budget_for_agent(agent_handle)
        release = reserved_offset if reserved_offset is not None else total_used

        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            key = self._session_key(session_id)
            field = self._agent_field(agent_handle)

            lua = """
            local reserved = tonumber(redis.call('HGET', KEYS[1], ARGV[1] .. ':reserved') or '0')
            local used = tonumber(redis.call('HGET', KEYS[1], ARGV[1] .. ':used') or '0')
            local release = tonumber(ARGV[2])
            local total_used = tonumber(ARGV[3])
            reserved = math.max(0, reserved - release)
            used = used + total_used
            redis.call('HSET', KEYS[1], ARGV[1] .. ':reserved', reserved)
            redis.call('HSET', KEYS[1], ARGV[1] .. ':used', used)
            redis.call('EXPIRE', KEYS[1], ARGV[4])
            return {reserved, used}
            """
            result = await r.eval(lua, 1, key, field, release, total_used, SESSION_TTL_SECONDS)
            reserved_new, used_new = int(result[0]), int(result[1])
            remaining = max(0, budget - (reserved_new + used_new))

            tracker.record_usage(input_tokens, output_tokens, agent_handle=agent_handle)

            payload = {
                "session_id": session_id,
                "agent_handle": agent_handle,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_used": used_new,
                "budget": budget,
                "remaining": remaining,
                "percent_used": round((used_new / budget * 100.0), 2) if budget > 0 else 100.0,
            }
            try:
                publish_token_usage(session_id, payload)
            except Exception as pub_exc:
                logger.debug("Failed to publish token_usage event: %s", pub_exc)

            return payload
        except Exception as exc:
            logger.debug("Redis record_usage failed, falling back to memory: %s", exc)
            return _in_memory_manager.record_usage(
                session_id,
                agent_handle,
                input_tokens,
                output_tokens,
                reserved_offset,
            )

    async def get_remaining(self, session_id: str, agent_handle: str) -> int:
        budget = self.get_budget_for_agent(agent_handle)
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            key = self._session_key(session_id)
            field = self._agent_field(agent_handle)

            reserved = int(await r.hget(key, f"{field}:reserved") or 0)
            used = int(await r.hget(key, f"{field}:used") or 0)
            return max(0, budget - (reserved + used))
        except Exception as exc:
            logger.debug("Redis get_remaining failed, falling back to memory: %s", exc)
            return _in_memory_manager.get_remaining(session_id, agent_handle)

    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        try:
            r = await get_redis()
            if r is None:
                raise ConnectionError("Redis client is unavailable")

            key = self._session_key(session_id)
            data = await r.hgetall(key)

            summary: Dict[str, Any] = {}
            total_session_used = 0
            for k, v in data.items():
                if k.endswith(":used"):
                    handle = k.replace(":used", "").replace("agent:", "")
                    budget = self.get_budget_for_agent(handle)
                    reserved = int(data.get(f"agent:{handle}:reserved", 0))
                    used = int(v)
                    summary[handle] = {
                        "used": used,
                        "reserved": reserved,
                        "budget": budget,
                        "remaining": max(0, budget - (reserved + used)),
                    }
                    total_session_used += used

            return {
                "session_id": session_id,
                "total_used": total_session_used,
                "agents": summary,
            }
        except Exception as exc:
            logger.debug("Redis get_session_summary failed, falling back to memory: %s", exc)
            return _in_memory_manager.get_session_summary(session_id)

    def prune_history(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, Any]]:
        # Same deterministic logic as in-memory version — purely computational
        return _in_memory_manager.prune_history(
            messages=messages,
            max_tokens=max_tokens or self.max_history_tokens,
            keep_system=keep_system,
        )

    async def reset_session(self, session_id: str) -> None:
        try:
            r = await get_redis()
            if r is not None:
                await r.delete(self._session_key(session_id))
        except Exception as exc:
            logger.debug("Redis reset_session failed: %s", exc)
        _in_memory_manager.reset()


# Backward-compatible singleton getter
_distributed_budget_manager: Optional[DistributedTokenBudgetManager] = None


async def get_distributed_budget_manager() -> DistributedTokenBudgetManager:
    global _distributed_budget_manager
    if _distributed_budget_manager is None:
        _distributed_budget_manager = DistributedTokenBudgetManager()
    return _distributed_budget_manager


def reset_distributed_budget_manager() -> None:
    global _distributed_budget_manager
    _distributed_budget_manager = None
