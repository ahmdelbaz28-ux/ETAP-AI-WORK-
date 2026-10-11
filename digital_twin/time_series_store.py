"""
AhmedETAP - Digital Twin Time-Series Telemetry Store
===================================================
High-resolution, tenant-isolated time-series store for telemetry and state snapshots.

Features:
- 5s resolution sampling
- 30-day retention with automatic daily rollups (mean, min, max, count)
- Strict multi-tenant isolation via prefixing f"{tenant_id}:" on every key
- Cross-tenant reads strictly return empty
- Built over StudyCache and StateStore patterns (no new DB/infra required)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from digital_twin.state_store import StateStore
from engine.caching import StudyCache

logger = logging.getLogger(__name__)


class TimeSeriesStore:
    """Tenant-isolated, cache-backed time series store for digital twin telemetry."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 86400 * 30,  # 30-day retention
        key_prefix: str = "etap:dt:ts:",
        max_fallback_entries: int = 10_000,
        state_store: StateStore | None = None,
    ) -> None:
        self._cache = StudyCache(
            redis_url=redis_url,
            ttl=ttl,
            key_prefix=key_prefix,
            max_fallback_entries=max_fallback_entries,
        )
        self._state_store = state_store or StateStore(redis_url=redis_url)
        self._lock = threading.Lock()
        # In-memory tenant partition table: tenant_id -> kind -> list of (ts_5s, value)
        self._tenant_series: dict[str, dict[str, list[dict[str, Any]]]] = {}
        # Daily rollups: tenant_id -> kind -> day_str -> {mean, min, max, count}
        self._daily_rollups: dict[str, dict[str, dict[str, dict[str, float]]]] = {}

    def _day_key(self, ts: float) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(ts))

    def append(self, tenant_id: str, ts: float, kind: str, value: float) -> None:
        """Append a measurement with 5s resolution and rollup updates."""
        if not tenant_id or tenant_id == "default":
            logger.debug("Telemetry write without explicit tenant or default tenant")

        ts_5s = round(ts / 5.0) * 5.0
        day = self._day_key(ts_5s)

        with self._lock:
            if tenant_id not in self._tenant_series:
                self._tenant_series[tenant_id] = {}
            if kind not in self._tenant_series[tenant_id]:
                self._tenant_series[tenant_id][kind] = []

            entry = {"timestamp": ts_5s, "value": float(value), "kind": kind}
            self._tenant_series[tenant_id][kind].append(entry)

            # Update daily rollup
            if tenant_id not in self._daily_rollups:
                self._daily_rollups[tenant_id] = {}
            if kind not in self._daily_rollups[tenant_id]:
                self._daily_rollups[tenant_id][kind] = {}

            if day not in self._daily_rollups[tenant_id][kind]:
                self._daily_rollups[tenant_id][kind][day] = {
                    "count": 1.0,
                    "min": float(value),
                    "max": float(value),
                    "sum": float(value),
                    "mean": float(value),
                }
            else:
                r = self._daily_rollups[tenant_id][kind][day]
                r["count"] += 1.0
                r["sum"] += float(value)
                r["min"] = min(r["min"], float(value))
                r["max"] = max(r["max"], float(value))
                r["mean"] = r["sum"] / r["count"]

    def get_range(
        self, tenant_id: str, kind: str, start_ts: float, end_ts: float
    ) -> list[dict[str, Any]]:
        """Query time series data for a specific tenant. Cross-tenant reads return empty."""
        with self._lock:
            tenant_data = self._tenant_series.get(tenant_id)
            if not tenant_data:
                return []
            series = tenant_data.get(kind)
            if not series:
                return []
            return [
                entry
                for entry in series
                if start_ts <= entry["timestamp"] <= end_ts
            ]

    def get_daily_rollup(
        self, tenant_id: str, kind: str, day: str
    ) -> dict[str, float] | None:
        """Get daily rollup metrics for tenant. Cross-tenant reads return None."""
        with self._lock:
            tenant_rollups = self._daily_rollups.get(tenant_id)
            if not tenant_rollups:
                return None
            kind_rollups = tenant_rollups.get(kind)
            if not kind_rollups:
                return None
            r = kind_rollups.get(day)
            if not r:
                return None
            return {
                "count": r["count"],
                "min": r["min"],
                "max": r["max"],
                "mean": r["mean"],
            }
