"""
scada_protocols.manager
=======================
SCADAProtocolManager — orchestrates all three protocol adapters.

The manager is the single integration point the rest of the platform talks
to. It:
- Loads YAML config (or accepts an explicit ``SCADAProtocolsConfig``)
- Probes which protocol libraries are importable
- Builds adapters for every enabled protocol whose library is present
- Wires each adapter's ``on_measurement`` callback into a single
  ``SCADAProtocolBridge`` (which forwards into the platform's
  ``SCADADatabase`` and ``digital_twin.EventBus``)
- Exposes ``start()`` / ``stop()`` / ``status()`` for use from FastAPI /
  CLI / notebooks

Design rules:
- Never crash on missing libraries unless ``strict_lib_check`` is True.
- Never crash on adapter start failure — log and skip.
- All public methods are thread-safe.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from scada_protocols.common.base import (
    AdapterRole,
    ProtocolAdapter,
    ProtocolType,
    probe_all,
)
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import SCADAProtocolsConfig, load_config
from scada_protocols.iec104 import IEC104Adapter
from scada_protocols.modbus import ModbusAdapter
from scada_protocols.opcua import OpcUaAdapter

logger = logging.getLogger(__name__)


class SCADAProtocolManager:
    """Top-level orchestrator for the three SCADA protocol adapters."""

    def __init__(
        self,
        config: Optional[SCADAProtocolsConfig] = None,
        config_path: Optional[str] = None,
        scada_db: Any = None,
        event_bus: Any = None,
        measurement_provider: Optional[Callable[[], Dict[str, float]]] = None,
        system: Any = None,
    ) -> None:
        if config is None:
            config = load_config(config_path)
        self._cfg: SCADAProtocolsConfig = config
        self._lock = threading.RLock()
        self._bridge = SCADAProtocolBridge(
            scada_db=scada_db,
            event_bus=event_bus,
            default_quality=config.default_quality,
        )
        self._measurement_cb = make_callback(self._bridge)
        self._measurement_provider = measurement_provider
        self._system = system

        self._adapters: Dict[ProtocolType, ProtocolAdapter] = {}
        self._library_status: Dict[str, Dict[str, Any]] = probe_all()
        self._started = False
        self._build_adapters()

    # -- adapter construction ----------------------------------------------

    def _build_adapters(self) -> None:
        """Build adapter instances for every enabled + available protocol."""
        cfg = self._cfg

        def _lib_available(key: str) -> tuple[bool, str]:
            entry = self._library_status.get(key, {})
            return bool(entry.get("available", False)), str(entry.get("info", ""))

        # --- Modbus ---
        if cfg.modbus.enabled:
            ok, info = _lib_available("modbus_tcp")
            if ok:
                try:
                    adapter = ModbusAdapter(
                        config=cfg.modbus,
                        role=cfg.modbus.role,
                        on_measurement=self._measurement_cb
                        if cfg.modbus.role in (AdapterRole.CLIENT, AdapterRole.BOTH)
                        else None,
                        provider=self._measurement_provider,
                    )
                    self._adapters[ProtocolType.MODBUS_TCP] = adapter
                except Exception as exc:
                    logger.error("Failed to build Modbus adapter: %s", exc)
            elif cfg.strict_lib_check:
                raise RuntimeError(f"pymodbus not available: {info}")
            else:
                logger.warning(
                    "Modbus enabled in config but pymodbus not available — skipped"
                )

        # --- OPC UA ---
        if cfg.opcua.enabled:
            ok, info = _lib_available("opc_ua")
            if ok:
                try:
                    adapter = OpcUaAdapter(
                        config=cfg.opcua,
                        role=cfg.opcua.role,
                        on_measurement=self._measurement_cb
                        if cfg.opcua.role in (AdapterRole.CLIENT, AdapterRole.BOTH)
                        else None,
                        provider=self._measurement_provider,
                        system=self._system,
                    )
                    self._adapters[ProtocolType.OPC_UA] = adapter
                except Exception as exc:
                    logger.error("Failed to build OPC UA adapter: %s", exc)
            elif cfg.strict_lib_check:
                raise RuntimeError(f"asyncua not available: {info}")
            else:
                logger.warning(
                    "OPC UA enabled in config but asyncua not available — skipped"
                )

        # --- IEC 104 ---
        if cfg.iec104.enabled:
            ok, info = _lib_available("iec_104")
            if ok:
                try:
                    adapter = IEC104Adapter(
                        config=cfg.iec104,
                        role=cfg.iec104.role,
                        on_measurement=self._measurement_cb
                        if cfg.iec104.role in (AdapterRole.CLIENT, AdapterRole.BOTH)
                        else None,
                        provider=self._measurement_provider,
                    )
                    self._adapters[ProtocolType.IEC_104] = adapter
                except Exception as exc:
                    logger.error("Failed to build IEC 104 adapter: %s", exc)
            elif cfg.strict_lib_check:
                raise RuntimeError(f"c104 not available: {info}")
            else:
                logger.warning(
                    "IEC 104 enabled in config but c104 not available — skipped"
                )

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start all configured adapters."""
        with self._lock:
            if self._started:
                return
            for ptype, adapter in list(self._adapters.items()):
                try:
                    adapter.start()
                except Exception as exc:
                    logger.error(
                        "Failed to start %s adapter: %s", ptype.value, exc
                    )
            self._started = True
            logger.info(
                "SCADAProtocolManager started — %d adapter(s) active",
                sum(1 for a in self._adapters.values() if a.is_running()),
            )

    def stop(self) -> None:
        """Stop all adapters. Best-effort; logs but does not raise."""
        with self._lock:
            if not self._started:
                return
            for ptype, adapter in list(self._adapters.items()):
                try:
                    adapter.stop()
                except Exception as exc:
                    logger.error(
                        "Failed to stop %s adapter: %s", ptype.value, exc
                    )
            self._started = False
            logger.info("SCADAProtocolManager stopped")

    # -- introspection ------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of the manager's state."""
        with self._lock:
            adapters = []
            for ptype, adapter in self._adapters.items():
                m = adapter.metric.to_dict()
                m["health"] = adapter.health_check()
                m["describe"] = adapter.describe()
                adapters.append(m)
            return {
                "started": self._started,
                "libraries": self._library_status,
                "adapters": adapters,
                "bridge": self._bridge.stats.to_dict(),
                "config": {
                    "modbus_enabled": self._cfg.modbus.enabled,
                    "opcua_enabled": self._cfg.opcua.enabled,
                    "iec104_enabled": self._cfg.iec104.enabled,
                    "strict_lib_check": self._cfg.strict_lib_check,
                },
            }

    def list_adapters(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "protocol": ptype.value,
                    "describe": adapter.describe(),
                    "metric": adapter.metric.to_dict(),
                    "health": adapter.health_check(),
                }
                for ptype, adapter in self._adapters.items()
            ]

    def get_adapter(self, ptype: ProtocolType) -> Optional[ProtocolAdapter]:
        with self._lock:
            return self._adapters.get(ptype)

    @property
    def bridge(self) -> SCADAProtocolBridge:
        return self._bridge

    @property
    def config(self) -> SCADAProtocolsConfig:
        return self._cfg

    def is_started(self) -> bool:
        return self._started


__all__ = ["SCADAProtocolManager"]
