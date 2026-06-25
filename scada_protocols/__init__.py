"""
scada_protocols
===============
SCADA protocol integration package for AhmedETAP.

Three protocols, one integration point:

- **Modbus TCP** (pymodbus) — legacy device fallback
- **OPC UA** (asyncua) — Industry 4.0 integration
- **IEC 60870-5-104** (c104) — RTU communication

All three feed the platform's existing ``scada_model.scada_model.SCADADatabase``
and emit ``SCADAUpdateReceived`` events on the digital twin's ``EventBus``,
which automatically triggers the propagation chain defined in
``digital_twin/handlers.py`` (Ybus rebuild -> Load Flow -> State Estimation ->
Short Circuit -> Arc Flash -> Protection -> Digital Twin update).

Quick start::

    from scada_protocols.manager import SCADAProtocolManager

    mgr = SCADAProtocolManager(config_path="scada_protocols/config/scada.yaml")
    mgr.start()
    print(mgr.status())

Or mount into FastAPI::

    from scada_protocols.api import build_router, set_manager
    set_manager(mgr)
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
"""

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
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import (
    ConfigError,
    Iec104Config,
    ModbusConfig,
    OpcUaConfig,
    SCADAProtocolsConfig,
    load_config,
    load_config_from_dict,
)
from scada_protocols.iec104 import (
    IEC104Adapter,
    IEC104ClientAdapter,
    IEC104ServerAdapter,
)
from scada_protocols.manager import SCADAProtocolManager
from scada_protocols.modbus import (
    ModbusAdapter,
    ModbusClientAdapter,
    ModbusServerAdapter,
    RegisterEntry,
    RegisterMap,
)
from scada_protocols.opcua import (
    AddressSpacePlan,
    OpcUaAdapter,
    OpcUaClientAdapter,
    OpcUaServerAdapter,
    UAVariable,
    UAFolder,
    build_plan_from_node_map,
    build_plan_from_system,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
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
    # modbus
    "ModbusAdapter",
    "ModbusServerAdapter",
    "ModbusClientAdapter",
    "RegisterEntry",
    "RegisterMap",
    # opcua
    "OpcUaAdapter",
    "OpcUaServerAdapter",
    "OpcUaClientAdapter",
    "AddressSpacePlan",
    "UAVariable",
    "UAFolder",
    "build_plan_from_node_map",
    "build_plan_from_system",
    # iec104
    "IEC104Adapter",
    "IEC104ServerAdapter",
    "IEC104ClientAdapter",
    # manager
    "SCADAProtocolManager",
]
