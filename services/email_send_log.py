"""
services/email_send_log.py — Email Send Log Storage
===================================================

Lightweight log of every email send attempt. Used by:
* Email Dashboard (`/api/v1/email-dashboard/*`)
* Email Digests (to compute daily/weekly stats)
* Webhooks (to correlate outbound sends with inbound delivery events)

Storage: in-memory ring buffer (default 5000 entries) with optional Redis
persistence. Survives single-instance restarts only when Redis is configured.

Public API
----------
    await log_email_send(recipient, subject, flow, success, ...)
    records = get_recent_sends(limit=100)
    stats = get_send_stats(window_hours=24)

Author: ETAP Integration Team
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger("etap.email_send_log")

# In-memory ring buffer (per-instance)
_BUFFER_MAX = int(os.getenv("EMAIL_LOG_BUFFER_MAX", "5000"))
_buffer: deque = deque(maxlen=_BUFFER_MAX)
_lock = asyncio.Lock()

# Optional Redis client for persistence
try:
    import redis.asyncio as redis_async  # type: ignore

    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    redis_async = None
    _REDIS_AVAILABLE = False


def _get_redis():
    if not _REDIS_AVAILABLE:
        return None
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    return redis_async.from_url(url, decode_responses=True)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmailSendRecord:
    """A single email send attempt."""

    id: str
    timestamp: str  # ISO-8601 UTC
    recipient: str
    subject: str
    flow: str  # otp, password_reset, welcome, login_alert, etc.
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    elapsed_ms: int = 0
    tags: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def log_email_send(
    recipient: str,
    subject: str,
    flow: str,
    success: bool,
    message_id: Optional[str] = None,
    error: Optional[str] = None,
    status_code: Optional[int] = None,
    elapsed_ms: int = 0,
    tags: Optional[list] = None,
) -> str:
    """Log a single email send. Returns the record ID."""
    import uuid

    record = EmailSendRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        recipient=recipient,
        subject=subject[:500],  # truncate very long subjects
        flow=flow,
        success=success,
        message_id=message_id,
        error=(error[:500] if error else None),
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        tags=tags or [],
    )

    async with _lock:
        _buffer.append(record)

    # Persist to Redis (best-effort)
    r = _get_redis()
    if r is not None:
        try:
            await r.lpush(
                "etap:email_send_log",
                __import__("json").dumps(asdict(record)),
            )
            await r.ltrim("etap:email_send_log", 0, _BUFFER_MAX - 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis_log_persist_failed err=%s", exc)

    return record.id


def get_recent_sends(limit: int = 100, flow: Optional[str] = None) -> list[dict]:
    """Return recent send records (newest first)."""
    items = list(reversed(_buffer))
    if flow:
        items = [r for r in items if r.flow == flow]
    items = items[:limit]
    return [asdict(r) for r in items]


def get_send_stats(window_hours: int = 24) -> dict:
    """Return aggregate stats over the last `window_hours`."""
    cutoff = datetime.now(UTC).timestamp() - (window_hours * 3600)
    in_window = []
    for r in _buffer:
        try:
            ts = datetime.fromisoformat(r.timestamp).timestamp()
            if ts >= cutoff:
                in_window.append(r)
        except (ValueError, TypeError):
            continue

    total = len(in_window)
    succeeded = sum(1 for r in in_window if r.success)
    failed = total - succeeded

    # Per-flow breakdown
    by_flow: dict[str, dict[str, int]] = {}
    for r in in_window:
        flow_stats = by_flow.setdefault(r.flow, {"total": 0, "success": 0, "failed": 0})
        flow_stats["total"] += 1
        if r.success:
            flow_stats["success"] += 1
        else:
            flow_stats["failed"] += 1

    # Top errors
    errors: dict[str, int] = {}
    for r in in_window:
        if not r.success and r.error:
            errors[r.error[:100]] = errors.get(r.error[:100], 0) + 1
    top_errors = sorted(errors.items(), key=lambda kv: -kv[1])[:10]

    # Top recipients (by volume)
    recipients: dict[str, int] = {}
    for r in in_window:
        recipients[r.recipient] = recipients.get(r.recipient, 0) + 1
    top_recipients = sorted(recipients.items(), key=lambda kv: -kv[1])[:10]

    # Avg elapsed ms
    elapsed_values = [r.elapsed_ms for r in in_window if r.elapsed_ms > 0]
    avg_elapsed = sum(elapsed_values) / len(elapsed_values) if elapsed_values else 0

    success_rate = (succeeded / total * 100) if total > 0 else 0.0

    return {
        "window_hours": window_hours,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "success_rate": round(success_rate, 2),
        "avg_elapsed_ms": round(avg_elapsed, 2),
        "by_flow": by_flow,
        "top_errors": [{"error": e, "count": c} for e, c in top_errors],
        "top_recipients": [{"email": e, "count": c} for e, c in top_recipients],
        "buffer_size": len(_buffer),
        "buffer_max": _BUFFER_MAX,
    }


def get_send_count_by_day(days: int = 7) -> list[dict]:
    """Return per-day send counts for the last `days` days."""
    today = datetime.now(UTC).date()
    buckets: dict[str, dict[str, int]] = {}
    for d in range(days):
        day = today - __import__("datetime").timedelta(days=d)
        buckets[day.isoformat()] = {"date": day.isoformat(), "total": 0, "succeeded": 0, "failed": 0}

    for r in _buffer:
        try:
            day_str = datetime.fromisoformat(r.timestamp).date().isoformat()
            if day_str in buckets:
                buckets[day_str]["total"] += 1
                if r.success:
                    buckets[day_str]["succeeded"] += 1
                else:
                    buckets[day_str]["failed"] += 1
        except (ValueError, TypeError):
            continue

    return sorted(buckets.values(), key=lambda b: b["date"])


def get_record_by_id(record_id: str) -> Optional[dict]:
    """Look up a single record by ID."""
    for r in reversed(_buffer):
        if r.id == record_id:
            return asdict(r)
    return None


def clear_old_records(max_age_hours: int = 720) -> int:
    """Remove records older than max_age_hours (default 30 days). Returns count removed."""
    cutoff = datetime.now(UTC).timestamp() - (max_age_hours * 3600)
    kept = deque(maxlen=_BUFFER_MAX)
    removed = 0
    for r in _buffer:
        try:
            ts = datetime.fromisoformat(r.timestamp).timestamp()
            if ts >= cutoff:
                kept.append(r)
            else:
                removed += 1
        except (ValueError, TypeError):
            kept.append(r)  # keep malformed records (safer)
    _buffer.clear()
    _buffer.extend(kept)
    return removed


__all__ = [
    "EmailSendRecord",
    "log_email_send",
    "get_recent_sends",
    "get_send_stats",
    "get_send_count_by_day",
    "get_record_by_id",
    "clear_old_records",
]
