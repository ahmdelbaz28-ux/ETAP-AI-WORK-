"""
scada_protocols.modbus
======================
Modbus TCP adapter — server (slave) + client (master) + register codec.

The ``ModbusAdapter`` facade picks server/client (or both) based on
``ModbusConfig.role``.
"""

from __future__ import annotations

from typing import Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus.client import ModbusClientAdapter
from scada_protocols.modbus.register_map import RegisterEntry, RegisterMap
from scada_protocols.modbus.server import MeasurementProvider, ModbusServerAdapter


class ModbusAdapter(ProtocolAdapter):
    """Facade that delegates to ``ModbusServerAdapter`` and/or ``ModbusClientAdapter``.

    Using a facade keeps the manager API uniform: it always sees one adapter
    per protocol, regardless of whether that protocol runs as server, client,
    or both.
    """

    protocol = ProtocolType.MODBUS_TCP
    supports_server = True
    supports_client = True

    def __init__(
        self,
        config: ModbusConfig,
        role: Optional[AdapterRole] = None,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[MeasurementProvider] = None,
    ) -> None:
        role = role or config.role
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        self._cfg = config
        self._server: Optional[ModbusServerAdapter] = None
        self._client: Optional[ModbusClientAdapter] = None
        self._provider = provider
        if role in (AdapterRole.SERVER, AdapterRole.BOTH):
            self._server = ModbusServerAdapter(
                config=config, role=AdapterRole.SERVER, provider=provider
            )
        if role in (AdapterRole.CLIENT, AdapterRole.BOTH):
            self._client = ModbusClientAdapter(
                config=config,
                role=AdapterRole.CLIENT,
                on_measurement=on_measurement,
            )

    # -- lifecycle ----------------------------------------------------------

    def start_server(self) -> None:
        if self._server is not None:
            self._server.start_server()

    def stop_server(self) -> None:
        if self._server is not None:
            self._server.stop_server()

    def start_client(self) -> None:
        if self._client is not None:
            self._client.start_client()

    def stop_client(self) -> None:
        if self._client is not None:
            self._client.stop_client()

    def health_check(self) -> bool:
        ok = True
        if self._server is not None:
            ok = ok and self._server.health_check()
        if self._client is not None:
            ok = ok and self._client.health_check()
        return ok

    # -- extra --------------------------------------------------------------

    @property
    def server(self) -> Optional[ModbusServerAdapter]:
        return self._server

    @property
    def client(self) -> Optional[ModbusClientAdapter]:
        return self._client

    @property
    def register_map(self) -> RegisterMap:
        # Both server and client share the same register map source.
        if self._server is not None:
            return self._server.register_map
        # Client doesn't keep a "live" map; rebuild from config.
        return RegisterMap(self._cfg.register_map)


__all__ = [
    "ModbusAdapter",
    "ModbusServerAdapter",
    "ModbusClientAdapter",
    "RegisterEntry",
    "RegisterMap",
    "MeasurementProvider",
]
