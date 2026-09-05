"""
Agent Safety & Kill-Switch Service
==================================
Emergency controls, life safety verification, and SIEM audit trail tracking.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timezone
from typing import Any

import aiofiles

from agents.life_safety import (
    activate_kill_switch,
    deactivate_kill_switch,
    is_kill_switch_active,
    life_safety_guard,
)

logger = logging.getLogger(__name__)
UTC = timezone.utc  # noqa: UP017


def get_life_safety_status() -> dict[str, Any]:
    """Return health status of the life safety guard."""
    return life_safety_guard.health_check()


def verify_audit_chain() -> tuple[bool, list[str]]:
    """Verify cryptographic integrity of the tamper-evident audit log."""
    return life_safety_guard.audit_log.verify_chain()


def get_siem_health() -> dict[str, Any]:
    """Return health check dictionary from SIEM forwarder."""
    from integrations.siem_syslog import siem_forwarder

    return siem_forwarder.health_check()


async def read_recent_siem_events(log_path: str, limit: int = 50) -> list[dict[str, Any]]:
    """Read recent SIEM events from JSONL log file."""
    if not os.path.exists(log_path):
        return []
    limit = min(max(limit, 1), 200)
    events: list[dict[str, Any]] = []
    async with aiofiles.open(log_path, encoding="utf-8") as fh:  # NOSONAR
        lines = await fh.readlines()
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


__all__ = [
    "activate_kill_switch",
    "deactivate_kill_switch",
    "is_kill_switch_active",
    "get_life_safety_status",
    "verify_audit_chain",
    "get_siem_health",
    "read_recent_siem_events",
]
