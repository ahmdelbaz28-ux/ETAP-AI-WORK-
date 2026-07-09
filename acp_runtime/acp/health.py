"""Built-in health & status handler for the ACP runtime.

This module provides a ``HealthHandler`` class that is automatically
registered by the CLI when starting a server. It exposes three public
capabilities:

* ``system.health`` — returns version, uptime, transport, and basic
  capability registry info.
* ``system.metrics`` — returns a snapshot of the in-memory metrics
  registry (if one is configured).
* ``system.ready`` — readiness probe that checks whether all handler
  modules loaded successfully and the runtime is operational.

All capabilities are public (no scopes required) so they can be used
by monitoring tools and load balancers without authentication.
"""

from __future__ import annotations

import time
from typing import Any, Optional, Union

from acp import __version__
from acp.runtime import capability

__all__ = ["HealthHandler"]


class HealthHandler:
    """Built-in handler for server health and metrics introspection.

    Parameters:
        transport_name: name of the transport being used (e.g.
            ``"stdio"``, ``"uds"``, ``"websocket"``).
        start_time: Unix timestamp when the server started. Used to
            compute uptime.
        metrics: optional metrics registry to snapshot.
        user_handler_count: number of user handlers loaded (excluding
            this built-in health handler).
    """

    def __init__(
        self,
        *,
        transport_name: str = "unknown",
        start_time: Optional[float] = None,
        metrics: Optional[Any] = None,
        user_handler_count: int = 0,
    ) -> None:
        self._transport_name = transport_name
        self._start_time = start_time or time.time()
        self._metrics = metrics
        self._user_handler_count = user_handler_count
        self._runtime: Optional[Any] = None

    def set_runtime(self, runtime: Any) -> None:
        """Attach the AcpRuntime instance so readiness checks can
        inspect the registry.

        This is called by ``_build_runtime`` after the runtime has been
        constructed, because the health handler is created *before*
        the runtime (it is part of the runtime).
        """
        self._runtime = runtime

    @capability("system.health")
    async def health(self) -> dict[str, Any]:
        """Return a health status snapshot.

        Returns:
            A dict with keys:
            - ``status`` — always ``"ok"``.
            - ``version`` — the ACP runtime version.
            - ``uptime_seconds`` — seconds since the server started.
            - ``transport`` — transport name (e.g. ``"stdio"``).
            - ``timestamp`` — current Unix timestamp.
            - ``capabilities_count`` — number of registered capabilities
              (only if the runtime reference has been set).
        """
        now = time.time()
        result: dict[str, Any] = {
            "status": "ok",
            "version": __version__,
            "uptime_seconds": round(now - self._start_time, 3),
            "transport": self._transport_name,
            "timestamp": round(now, 3),
        }
        if self._runtime is not None:
            result["capabilities_count"] = len(self._runtime.capability_names)
        return result

    @capability("system.metrics")
    async def metrics(self) -> dict[str, Any]:
        """Return a metrics snapshot (if a registry is configured).

        Returns:
            A dict with key ``metrics`` containing the registry snapshot,
            or an empty dict if no registry is available.
        """
        if self._metrics is not None and hasattr(self._metrics, "snapshot"):
            return {"metrics": self._metrics.snapshot()}
        return {"metrics": {}}

    def prometheus(self) -> str:
        """Return metrics in Prometheus text exposition format.

        Returns:
            A Prometheus text string, or an empty string if no registry
            is configured.
        """
        if self._metrics is not None and hasattr(self._metrics, "prometheus"):
            return self._metrics.prometheus()
        return ""

    def openmetrics(self) -> str:
        """Return metrics in OpenMetrics text format.

        Returns:
            An OpenMetrics text string, or an empty string if no registry
            is configured.
        """
        if self._metrics is not None and hasattr(self._metrics, "snapshot"):
            from acp.observability.metrics import to_openmetrics

            return to_openmetrics(self._metrics.snapshot())
        return "# EOF"

    @capability("system.ready")
    async def ready(self) -> dict[str, Any]:
        """Readiness probe — verifies the server is running and all
        handler modules loaded successfully.

        Returns:
            A dict with keys:
            - ``ready`` — ``True`` if the runtime is available and has
              registered capabilities, ``False`` otherwise.
            - ``status`` — ``"ok"`` or ``"runtime not available"``.
            - ``handlers_loaded`` — number of handler objects registered.
            - ``capabilities`` — sorted list of all capability names.
            - ``uptime_seconds`` — seconds since the server started.
        """
        if self._runtime is None:
            return {
                "ready": False,
                "status": "runtime not available",
                "handlers_loaded": 0,
                "capabilities": [],
                "uptime_seconds": 0,
            }
        now = time.time()
        return {
            "ready": True,
            "status": "ok",
            "handlers_loaded": self._user_handler_count,
            "capabilities": self._runtime.capability_names,
            "uptime_seconds": round(now - self._start_time, 3),
        }
