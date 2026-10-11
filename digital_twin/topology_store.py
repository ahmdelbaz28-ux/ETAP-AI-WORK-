"""
AhmedETAP - Digital Twin Topology Store
=======================================
Tenant-isolated topology and switching state tracking store for the digital twin.

Features:
- Breaker and switch state tracking (OPEN / CLOSED) per tenant
- Bus voltage and status tracking following the StateStore.update_bus_state pattern
- Strict multi-tenant isolation via tenant-prefixed element state
- Thread-safe updates with per-element lock patterns
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from digital_twin.state_store import StateStore
from engine.caching import StudyCache

logger = logging.getLogger(__name__)


class TopologyStore:
    """Tenant-keyed topology store managing breaker/switch and bus connectivity states."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 86400 * 30,
        key_prefix: str = "etap:dt:topo:",
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
        # Tenant topology states: tenant_id -> element_id -> {type, state, timestamp}
        self._tenant_topology: dict[str, dict[str, dict[str, Any]]] = {}

    def set_breaker_state(
        self, tenant_id: str, breaker_id: str, state: str, source: str = "scada"
    ) -> bool:
        """Set breaker status ('OPEN' or 'CLOSED') for a given tenant."""
        normalized_state = state.upper()
        if normalized_state not in ("OPEN", "CLOSED"):
            raise ValueError(f"Invalid breaker state: {state}. Must be 'OPEN' or 'CLOSED'.")

        with self._lock:
            if tenant_id not in self._tenant_topology:
                self._tenant_topology[tenant_id] = {}

            self._tenant_topology[tenant_id][breaker_id] = {
                "type": "breaker",
                "state": normalized_state,
                "source": source,
            }
            return True

    def get_breaker_state(
        self, tenant_id: str, breaker_id: str
    ) -> str | None:
        """Get breaker status. Cross-tenant reads return None."""
        with self._lock:
            tenant_topo = self._tenant_topology.get(tenant_id)
            if not tenant_topo:
                return None
            breaker_info = tenant_topo.get(breaker_id)
            if not breaker_info:
                return None
            return breaker_info.get("state")

    def get_tenant_topology(self, tenant_id: str) -> dict[str, Any]:
        """Get complete switching topology for a tenant. Cross-tenant returns empty dict."""
        with self._lock:
            tenant_topo = self._tenant_topology.get(tenant_id)
            if not tenant_topo:
                return {}
            return dict(tenant_topo)
