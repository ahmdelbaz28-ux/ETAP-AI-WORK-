"""scada_protocols.common — shared protocol-agnostic pieces."""

from scada_protocols.common.base import (
    AdapterRole,
    AdapterState,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolMetric,
    ProtocolType,
    probe_all,
    probe_iec104,
    probe_modbus,
    probe_opcua,
)
from scada_protocols.common.bridge import (
    BridgeStats,
    SCADAProtocolBridge,
    make_callback,
)
from scada_protocols.common.config import (
    ConfigError,
    Iec104Config,
    ModbusConfig,
    OpcUaConfig,
    SCADAProtocolsConfig,
    load_config,
    load_config_from_dict,
)

__all__ = [
    # base
    "ProtocolType",
    "AdapterRole",
    "AdapterState",
    "ProtocolMetric",
    "ProtocolAdapter",
    "MeasurementCallback",
    "probe_modbus",
    "probe_opcua",
    "probe_iec104",
    "probe_all",
    # bridge
    "BridgeStats",
    "SCADAProtocolBridge",
    "make_callback",
    # config
    "ConfigError",
    "ModbusConfig",
    "OpcUaConfig",
    "Iec104Config",
    "SCADAProtocolsConfig",
    "load_config",
    "load_config_from_dict",
]
