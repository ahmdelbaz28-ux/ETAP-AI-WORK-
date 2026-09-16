"""
api/token_budget.py — Token Budget Manager (Phase 1).

Enforces per-agent token limits, session-level token reservation, usage recording,
chat history pruning to prevent context overflow, and publishes real-time token
telemetry events via the session stream hub.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from api.session_stream import publish_token_usage
from api.telemetry import tracker

logger = logging.getLogger(__name__)

DEFAULT_AGENT_BUDGETS: Dict[str, int] = {
    "load_flow_agent": 4000,
    "short_circuit_agent": 4000,
    "arcflash_agent": 5000,
    "protection_agent": 6000,
    "motor_starting_agent": 4000,
    "goal_planner_agent": 3000,
    "etap_engineer_agent": 8000,
    "etap_expert_agent": 8000,
    "coordinator_agent": 3000,
    "default": 4000,
}

DEFAULT_MAX_HISTORY_TOKENS = 6000


def estimate_tokens(text: str) -> int:
    """Fast, deterministic heuristic token estimation (~4 characters per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class TokenBudgetManager:
    """Thread-safe manager for tracking, reserving, and enforcing token budgets."""

    def __init__(
        self,
        agent_budgets: Optional[Dict[str, int]] = None,
        max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS,
    ) -> None:
        self._lock = threading.Lock()
        self._budgets = dict(DEFAULT_AGENT_BUDGETS)
        if agent_budgets:
            self._budgets.update(agent_budgets)
        self.max_history_tokens = max_history_tokens

        # Per-session state: {session_id: {agent_handle: {"used": int, "reserved": int}}}
        self._session_usage: Dict[str, Dict[str, Dict[str, int]]] = {}

    def get_budget_for_agent(self, agent_handle: str) -> int:
        """Return allocated max token budget for a given agent handle."""
        return self._budgets.get(agent_handle, self._budgets["default"])

    def check_and_reserve(
        self,
        session_id: str,
        agent_handle: str,
        estimated_tokens: int,
    ) -> bool:
        """Attempt to reserve estimated tokens within the agent's budget.

        Returns True if reservation succeeds; False if reservation would exceed budget.
        """
        budget = self.get_budget_for_agent(agent_handle)
        with self._lock:
            agents_map = self._session_usage.setdefault(session_id, {})
            agent_data = agents_map.setdefault(agent_handle, {"used": 0, "reserved": 0})
            current_total = agent_data["used"] + agent_data["reserved"]
            if current_total + estimated_tokens > budget:
                logger.warning(
                    "Token reservation denied for %s in session %s: requested %d, current total %d, budget %d",
                    agent_handle,
                    session_id,
                    estimated_tokens,
                    current_total,
                    budget,
                )
                return False
            agent_data["reserved"] += estimated_tokens
            return True

    def record_usage(
        self,
        session_id: str,
        agent_handle: str,
        input_tokens: int,
        output_tokens: int,
        reserved_offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record actual tokens consumed, release reserved tokens, and publish usage event."""
        total_used = max(0, input_tokens) + max(0, output_tokens)
        budget = self.get_budget_for_agent(agent_handle)

        with self._lock:
            agents_map = self._session_usage.setdefault(session_id, {})
            agent_data = agents_map.setdefault(agent_handle, {"used": 0, "reserved": 0})

            # Release reserved tokens
            release = reserved_offset if reserved_offset is not None else total_used
            agent_data["reserved"] = max(0, agent_data["reserved"] - release)
            agent_data["used"] += total_used

            current_used = agent_data["used"]
            remaining = max(0, budget - current_used)

        # Record to global telemetry
        tracker.record_usage(input_tokens, output_tokens, agent_handle=agent_handle)

        payload = {
            "session_id": session_id,
            "agent_handle": agent_handle,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_used": current_used,
            "budget": budget,
            "remaining": remaining,
            "percent_used": round((current_used / budget * 100.0), 2) if budget > 0 else 100.0,
        }

        try:
            publish_token_usage(session_id, payload)
        except Exception as exc:
            logger.debug("Failed to publish token_usage event: %s", exc)

        return payload

    def get_remaining(self, session_id: str, agent_handle: str) -> int:
        """Return remaining tokens for an agent in a specific session."""
        budget = self.get_budget_for_agent(agent_handle)
        with self._lock:
            agent_data = (
                self._session_usage.get(session_id, {})
                .get(agent_handle, {"used": 0, "reserved": 0})
            )
            allocated = agent_data["used"] + agent_data["reserved"]
            return max(0, budget - allocated)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Return a complete breakdown of token usage across all agents in the session."""
        with self._lock:
            agents_map = self._session_usage.get(session_id, {})
            summary: Dict[str, Any] = {}
            total_session_used = 0
            for handle, data in agents_map.items():
                budget = self.get_budget_for_agent(handle)
                summary[handle] = {
                    "used": data["used"],
                    "reserved": data["reserved"],
                    "budget": budget,
                    "remaining": max(0, budget - (data["used"] + data["reserved"])),
                }
                total_session_used += data["used"]
            return {
                "session_id": session_id,
                "total_used": total_session_used,
                "agents": summary,
            }

    def prune_history(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        keep_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """Prune messages from oldest to newest while preserving system prompts and recent context.

        Guarantees that the resulting message array's estimated token count <= max_tokens.
        """
        limit = max_tokens or self.max_history_tokens
        if not messages:
            return []

        system_messages: List[Dict[str, Any]] = []
        conversation_messages: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role")
            if keep_system and role == "system":
                system_messages.append(msg)
            else:
                conversation_messages.append(msg)

        sys_tokens = sum(
            estimate_tokens(str(m.get("content", ""))) for m in system_messages
        )
        remaining_budget = max(0, limit - sys_tokens)

        # Traverse conversation from newest to oldest
        retained: List[Dict[str, Any]] = []
        accumulated_tokens = 0

        for msg in reversed(conversation_messages):
            msg_tokens = estimate_tokens(str(msg.get("content", "")))
            if accumulated_tokens + msg_tokens <= remaining_budget:
                retained.append(msg)
                accumulated_tokens += msg_tokens
            else:
                # Can't fit this message or earlier ones
                break

        # Re-assemble in chronological order: system first, then oldest retained to newest
        retained.reverse()
        return system_messages + retained

    def reset(self) -> None:
        """Reset internal session data (useful for test isolation)."""
        with self._lock:
            self._session_usage.clear()


# Process-wide singleton
budget_manager = TokenBudgetManager()
