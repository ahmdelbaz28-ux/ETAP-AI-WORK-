"""
scada_protocols.opcua
=====================
OPC UA adapter — server (exposes measurements) + client (ingests measurements).
"""

from __future__ import annotations

from typing import Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import OpcUaConfig
from scada_protocols.opcua.address_space import (
    AddressSpacePlan,
    UAVariable,
    UAFolder,
    build_plan_from_node_map,
    build_plan_from_system,
)
from scada_protocols.opcua.client import OpcUaClientAdapter
from scada_protocols.opcua.server import MeasurementProvider, OpcUaServerAdapter


class OpcUaAdapter(ProtocolAdapter):
    """Facade delegating to OpcUaServerAdapter and/or OpcUaClientAdapter."""

    protocol = ProtocolType.OPC_UA
    supports_server = True
    supports_client = True

    def __init__(
        self,
        config: OpcUaConfig,
        role: Optional[AdapterRole] = None,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[MeasurementProvider] = None,
        system: any = None,
    ) -> None:
        role = role or config.role
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        self._cfg = config
        self._server: Optional[OpcUaServerAdapter] = None
        self._client: Optional[OpcUaClientAdapter] = None
        if role in (AdapterRole.SERVER, AdapterRole.BOTH):
            self._server = OpcUaServerAdapter(
                config=config,
                role=AdapterRole.SERVER,
                provider=provider,
                system=system,
            )
        if role in (AdapterRole.CLIENT, AdapterRole.BOTH):
            self._client = OpcUaClientAdapter(
                config=config,
                role=AdapterRole.CLIENT,
                on_measurement=on_measurement,
            )

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

    @property
    def server(self) -> Optional[OpcUaServerAdapter]:
        return self._server

    @property
    def client(self) -> Optional[OpcUaClientAdapter]:
        return self._client

    @property
    def plan(self) -> AddressSpacePlan:
        if self._server is not None:
            return self._server.plan
        # Build a throwaway plan for clients (introspection only).
        if self._cfg.node_map:
            return build_plan_from_node_map(
                self._cfg.node_map, namespace=self._cfg.server_namespace
            )
        return AddressSpacePlan(namespace=self._cfg.server_namespace)


__all__ = [
    "OpcUaAdapter",
    "OpcUaServerAdapter",
    "OpcUaClientAdapter",
    "AddressSpacePlan",
    "UAVariable",
    "UAFolder",
    "build_plan_from_node_map",
    "build_plan_from_system",
    "MeasurementProvider",
]
