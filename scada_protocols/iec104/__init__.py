"""
scada_protocols.iec104
======================
IEC 60870-5-104 adapter — server (RTU) + client (master) + ASDU codec.
"""

from __future__ import annotations

from typing import Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import Iec104Config
from scada_protocols.iec104.asdu_mapper import (
    DEFAULT_COT,
    IEC104Point,
    PointMap,
    decode_information,
    decode_quality,
    default_measurement_type_for,
    suggested_asdu_type,
)
from scada_protocols.iec104.client import IEC104ClientAdapter
from scada_protocols.iec104.server import IEC104ServerAdapter


class IEC104Adapter(ProtocolAdapter):
    """Facade delegating to IEC104ServerAdapter and/or IEC104ClientAdapter."""

    protocol = ProtocolType.IEC_104
    supports_server = True
    supports_client = True

    def __init__(
        self,
        config: Iec104Config,
        role: Optional[AdapterRole] = None,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[any] = None,
    ) -> None:
        role = role or config.role
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        self._cfg = config
        self._server: Optional[IEC104ServerAdapter] = None
        self._client: Optional[IEC104ClientAdapter] = None
        if role in (AdapterRole.SERVER, AdapterRole.BOTH):
            self._server = IEC104ServerAdapter(
                config=config, role=AdapterRole.SERVER, provider=provider
            )
        if role in (AdapterRole.CLIENT, AdapterRole.BOTH):
            self._client = IEC104ClientAdapter(
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
    def server(self) -> Optional[IEC104ServerAdapter]:
        return self._server

    @property
    def client(self) -> Optional[IEC104ClientAdapter]:
        return self._client


__all__ = [
    "IEC104Adapter",
    "IEC104ServerAdapter",
    "IEC104ClientAdapter",
    "IEC104Point",
    "PointMap",
    "DEFAULT_COT",
    "decode_information",
    "decode_quality",
    "default_measurement_type_for",
    "suggested_asdu_type",
]
