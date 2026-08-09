# scada_protocols — Real SCADA Protocols for AhmedETAP

**Three protocols, one integration point, zero changes to existing code.**

Adds Modbus TCP, OPC UA, and IEC 60870-5-104 support to the platform. All
three feed the existing `scada_model.scada_model.SCADADatabase` and emit
`SCADAUpdateReceived` events on the `digital_twin.event_bus.EventBus`, so
the propagation chain defined in `digital_twin/handlers.py`
(Ybus rebuild → Load Flow → State Estimation → Short Circuit → Arc Flash →
Protection → Digital Twin update) fires automatically.

## Why this package exists

Before this package, the platform's `scada_model/` and `digital_twin/`
layers were complete and well-tested, but the only data source was
`SimulatedSCADA` in `etap_integration/scada_client.py` — a sinusoidal +
Gaussian-noise generator. The platform's "Real-Time Digital Twin" claim
was therefore not real-time in any operational sense.

This package plugs that gap by adding three real, production-grade SCADA
protocols:

| Protocol | Library | Role | Status |
|---|---|---|---|
| Modbus TCP | `pymodbus` | server (slave) + client (master) | live integration test passing |
| OPC UA | `asyncua` | server + client | adapter implemented, address-space builder tested |
| IEC 60870-5-104 | `c104` (lib60870) | server (RTU) + client (master) | adapter implemented, ASDU codec tested |

## Package layout

```
scada_protocols/
├── common/
│   ├── base.py            # ProtocolAdapter ABC, AdapterRole, ProtocolMetric
│   ├── config.py          # YAML config schema + loader
│   └── bridge.py          # SCADAProtocolBridge -> SCADADatabase + EventBus
├── modbus/
│   ├── register_map.py    # float32/uint16/int16/uint32/int32 codec
│   ├── server.py          # ModbusServerAdapter (slave)
│   ├── client.py          # ModbusClientAdapter (master)
│   └── __init__.py        # ModbusAdapter facade
├── opcua/
│   ├── address_space.py   # build_plan_from_node_map / from_system
│   ├── server.py          # OpcUaServerAdapter
│   ├── client.py          # OpcUaClientAdapter
│   └── __init__.py        # OpcUaAdapter facade
├── iec104/
│   ├── asdu_mapper.py     # ASDU type <-> MeasurementType codec
│   ├── server.py          # IEC104ServerAdapter (RTU)
│   ├── client.py          # IEC104ClientAdapter (master)
│   └── __init__.py        # IEC104Adapter facade
├── config/
│   └── scada.yaml         # full template (all 3 protocols)
├── tests/                 # 76 tests (unit + integration)
├── manager.py             # SCADAProtocolManager — orchestrator
├── api.py                 # FastAPI router
└── __init__.py
```

## Quick start

### 1. Install dependencies

```bash
pip install pymodbus<3.8 asyncua c104 pyyaml numpy
```

> **pymodbus version note:** pymodbus 3.13 deprecated the
> `ModbusDeviceContext`/`ModbusSequentialDataBlock` API in favour of
> `SimData`/`SimDevice`. The server adapter currently targets the
> 3.7.x API; the client adapter works on both. Pin `pymodbus<3.8` until
> the v4 SimData migration is complete.

### 2. Create a config (or use the template)

```bash
cp scada_protocols/config/scada.yaml /etc/etap/scada.yaml
$EDITOR /etc/etap/scada.yaml
```

### 3. Mount into the FastAPI app (one-line wiring)

In `api/routes.py` (or any startup hook), add **one line**:

```python
from scada_protocols.wiring import wire_into_app

# After `app = FastAPI(...)` and the other include_router calls:
wire_into_app(app, scada_db=my_scada_database, event_bus=my_event_bus)
```

That's it. `wire_into_app`:
- loads `$SCADA_PROTOCOLS_CONFIG` (or defaults),
- builds the SCADAProtocolManager wired to your SCADADatabase + EventBus,
- starts all enabled protocols,
- mounts the API router at `/api/v1/scada/protocols`,
- registers a shutdown handler to stop protocols cleanly.

For more control (custom provider, system object, no autostart), see the
`scada_protocols.wiring.wire_into_app` docstring.

### 4. Verify

```bash
# Which libraries are available?
curl http://localhost:8000/api/v1/scada/protocols/libraries

# Overall status
curl http://localhost:8000/api/v1/scada/protocols/status

# Per-protocol
curl http://localhost:8000/api/v1/scada/protocols/modbus_tcp/status
curl http://localhost:8000/api/v1/scada/protocols/opc_ua/status
curl http://localhost:8000/api/v1/scada/protocols/iec_104/status
```

## How it integrates with existing code

The integration is **additive only** — no existing file is modified.

```
            ┌─────────────────────────────────────────────────────┐
            │                EXISTING CODE (untouched)             │
            │                                                     │
            │  scada_model.scada_model.SCADADatabase               │
            │     ↑                                               │
            │     │ add_measurement()                              │
            │     │                                               │
            │  digital_twin.event_bus.EventBus                     │
            │     ↑                                               │
            │     │ publish(SCADAUpdateReceived)                   │
            │     │                                               │
            │  digital_twin.handlers.*Handler                      │
            │     ↑                                               │
            │     │ propagation chain (Ybus → LF → SE → SC → AF)   │
            └─────┼───────────────────────────────────────────────┘
                  │
            ┌─────┴───────────────────────────────────────────────┐
            │               NEW PACKAGE (this file)                │
            │                                                     │
            │  scada_protocols.common.bridge.SCADAProtocolBridge   │
            │     ↑                                               │
            │     │ ingest(element_id, type, value, quality, src)  │
            │     │                                               │
            │  scada_protocols.manager.SCADAProtocolManager        │
            │     │                                               │
            │     ├── ModbusAdapter (server + client)              │
            │     ├── OpcUaAdapter  (server + client)              │
            │     └── IEC104Adapter (server + client)              │
            └─────────────────────────────────────────────────────┘
```

Each protocol adapter:
- Calls `self._ingest(element_id, measurement_type, value, quality, source)`
  for every measurement received as a client.
- The base class forwards that to the `MeasurementCallback` registered
  by the manager.
- The callback is `SCADAProtocolBridge.ingest`, which:
  1. Maps the loose type/quality strings to `MeasurementType` /
     `QualityFlag` enum values (using a comprehensive alias table).
  2. Constructs a `Measurement` and calls `SCADADatabase.add_measurement()`.
  3. Publishes a `SCADAUpdateReceived` event on the EventBus.
- The existing propagation chain in `digital_twin/handlers.py` picks up
  the event and runs the full refresh.

**Failure isolation:** the bridge callback swallows all exceptions from
`SCADADatabase` / `EventBus` so a broken bridge can never kill the
protocol receive loop.

## Configuration reference

See `config/scada.yaml` for the full template. Key points:

- Every protocol section supports `enabled: false` to skip it entirely.
- `role: server | client | both` controls which side runs.
- Missing protocol libraries are SKIPPED at startup with a warning,
  unless `strict_lib_check: true` is set at the top level.
- `default_quality` is the fallback quality when a protocol doesn't
  carry one (default: `"good"`).

## Tests

```bash
# All 84 tests (unit + integration + end-to-end)
pytest scada_protocols/tests/

# Live integration tests (require pymodbus + asyncua + c104)
pytest scada_protocols/tests/test_integration_modbus_live.py -v
pytest scada_protocols/tests/test_integration_opcua_live.py -v
pytest scada_protocols/tests/test_integration_iec104_live.py -v

# 3-protocol manager lifecycle (requires all 3 libs)
pytest scada_protocols/tests/test_integration_three_protocols.py -v

# End-to-end with real AhmedETAP SCADADatabase + EventBus
# (requires the AhmedETAP repo on sys.path)
pytest scada_protocols/tests/test_integration_etap_stack.py -v

# Just unit tests (no sockets, no external libs required)
pytest scada_protocols/tests/test_common.py scada_protocols/tests/test_modbus.py \
       scada_protocols/tests/test_opcua.py scada_protocols/tests/test_iec104.py \
       scada_protocols/tests/test_manager.py scada_protocols/tests/test_api.py \
       scada_protocols/tests/test_wiring.py
```

Test breakdown (84 tests total):
- `test_common.py` — 22 tests (config, bridge, adapter base, probes)
- `test_modbus.py` — 10 tests (register codec round-trips)
- `test_opcua.py` — 9 tests (address-space builder)
- `test_iec104.py` — 18 tests (ASDU decoder, quality decoder)
- `test_manager.py` — 8 tests (orchestrator lifecycle)
- `test_api.py` — 8 tests (FastAPI router)
- `test_wiring.py` — 4 tests (additive integration into FastAPI)
- `test_integration_modbus_live.py` — 1 live round-trip test (Modbus)
- `test_integration_opcua_live.py` — 1 live round-trip test (OPC UA)
- `test_integration_iec104_live.py` — 1 live round-trip test (IEC 104)
- `test_integration_three_protocols.py` — 1 multi-protocol test (all 3)
- `test_integration_etap_stack.py` — 1 end-to-end test (with real SCADADatabase + EventBus)

## Known limitations & honest notes

1. **pymodbus 3.13+ API churn.** pymodbus 3.13 deprecated
   `ModbusDeviceContext` / `ModbusSequentialDataBlock` in favour of
   `SimData` / `SimDevice`. The server adapter currently targets the
   3.7.x API. The client adapter works on both 3.7 and 3.13 because
   the `read_holding_registers` signature change is handled with
   feature detection. Pin `pymodbus<3.8` until the v4 SimData
   migration is implemented.

2. **OPC UA security.** The default config uses `SecurityMode=None`.
   For production, set `security_mode: SignAndEncrypt` and provide a
   certificate/private key. The adapter passes the security settings
   to asyncua but does not manage certificates itself.

3. **IEC 104 server transmission modes.** The server currently drives
   spontaneous transmissions from the refresh thread (1 Hz by default).
   Cyclic (`report_ms > 0`) and on-change modes are supported by the
   `c104` library but not yet exposed via the YAML config.

4. **`SCADAProtocolBridge` lazy imports.** The bridge tries to import
   `scada_model.scada_model` and `digital_twin.event_bus` lazily. When
   either is absent (e.g. running this package standalone), the bridge
   degrades to log-only mode and still tracks statistics. This is
   intentional — it makes the package testable in isolation.

5. **No protocol-level security hardening.** Modbus TCP has no
   authentication by spec; OPC UA security is config-driven; IEC 104
   has optional TLS via `c104.TransportSecurity` (not yet wired up).
   Do NOT expose any of these ports directly to the internet without
   a proper industrial firewall / VPN in front.

## License

MIT — same as the parent AhmedETAP project.
