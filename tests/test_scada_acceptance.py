"""tests/test_scada_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for SCADA Integration (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEC 61850 data model mapping, measurement telemetry, and bus mapping
   when flag is enabled, returning IEC 61850 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="scada_system")
def fixture_scada_system():
    """Create a 3-bus substation test system for SCADA integration."""
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
            BusSpec(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.04, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.05, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_scada_rejected_when_flag_disabled(scada_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
        "scada_port": 102,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("scada", scada_system, params)

    assert exc_info.value.study_type == "scada"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_scada_rejected_when_empty_parameters(scada_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("scada", scada_system, {})

    assert exc_info.value.study_type == "scada"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_scada_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("scada", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_scada_positive_execution_connect(scada_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEC 61850 SCADA connection protocol."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
        "scada_port": 102,
        "scada_protocol": "IEC61850",
    }

    raw = executor._dispatch("scada", scada_system, params)

    assert "connection" in raw
    conn = raw["connection"]
    assert conn.get("server") == "substation1.grid.local"
    assert conn.get("protocol") == "IEC61850"

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 61850"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.scada_agent.SCADAAgent"


def test_scada_positive_execution_iec61850_model(scada_system, monkeypatch):
    """Positive Test 2: With flag enabled, retrieves IEC 61850 logical node data model."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "iec61850_model",
        "logical_device": "LD0",
    }

    raw = executor._dispatch("scada", scada_system, params)

    assert "iec61850_model" in raw
    model = raw["iec61850_model"]
    assert "logical_nodes" in model
    ln_names = [ln.get("logical_node") for ln in model["logical_nodes"]]
    assert "MMXU" in ln_names
    assert "XCBR" in ln_names

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 61850"
    assert provenance.get("lifecycle") == "pilot"


@pytest.mark.asyncio
async def test_scada_live_modbus_adapter_execution():
    """Live Adapter Test 1: Connect and read against local Modbus TCP server returning live_connection: True."""
    import time

    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import LiveModbusAdapter, SCADAAgent
    from scada_protocols.common.config import ModbusConfig
    from scada_protocols.modbus.register_map import RegisterEntry
    from scada_protocols.modbus.server import ModbusServerAdapter

    reg_map = [
        RegisterEntry(name="BUS1_V", element_id="BUS-1", measurement_type="voltage_magnitude", address=0, function_code=3, data_type="float32", scale=1.0, offset=0.0, unit="p.u."),
        RegisterEntry(name="BUS1_P", element_id="BUS-1", measurement_type="active_power", address=2, function_code=3, data_type="float32", scale=1.0, offset=0.0, unit="MW"),
    ]
    cfg = ModbusConfig(enabled=True, role="server", server_host="127.0.0.1", server_port=5021, server_unit_id=1, register_map=[r.__dict__ for r in reg_map])
    server = ModbusServerAdapter(cfg)
    server.set_provider(lambda: {"BUS1_V": 1.025, "BUS1_P": 45.2})
    server.start_server()
    time.sleep(1.0)

    try:
        adapter = LiveModbusAdapter(host="127.0.0.1", port=5021, unit_id=1, register_map=[r.__dict__ for r in reg_map])
        agent = SCADAAgent(adapter=adapter)
        task = EngineeringTask(
            task_id="task_live_modbus",
            description="Live Modbus telemetry acquisition",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "analysis_type": "full",
                "scada_server": "127.0.0.1",
                "scada_port": 5021,
                "scada_protocol": "modbus",
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.COMPLETED
        assert res.data["live_connection"] is True
        assert res.data["authoritative"] is True
        assert res.data["simulated"] is False
        assert res.data["provenance"]["source"] == "modbus"
        assert res.data["measurements"]["measurement_count"] == 2
        meas = res.data["measurements"]["measurements"]
        if not any(m["tag"] == "BUS1_V" and abs(m["value"] - 1.025) < 0.01 for m in meas):
            # In heavily loaded CI environments, allow one refresh cycle to settle
            await asyncio.sleep(0.5)
            res = await agent.execute(task)
            meas = res.data["measurements"]["measurements"]
        assert any(m["tag"] == "BUS1_V" and abs(m["value"] - 1.025) < 0.01 for m in meas)
    finally:
        adapter.close()
        server.stop_server()


@pytest.mark.asyncio
async def test_scada_live_modbus_server_down_fail_closed():
    """Live Adapter Test 2: Server-down scenario must return REAL_INTEGRATION_UNAVAILABLE failure."""
    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import LiveModbusAdapter, SCADAAgent

    adapter = LiveModbusAdapter(host="127.0.0.1", port=5029)
    agent = SCADAAgent(adapter=adapter)
    task = EngineeringTask(
        task_id="task_modbus_down",
        description="Live Modbus server down test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "connect",
            "scada_server": "127.0.0.1",
            "scada_port": 5029,
            "scada_protocol": "modbus",
        },
    )
    res = await agent.execute(task)
    assert res.status == AgentStatus.FAILED
    assert res.data["error_code"] == "REAL_INTEGRATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scada_live_opcua_adapter_execution():
    """Live Adapter Test 3: Connect and read against local OPC UA server returning live_connection: True."""
    import asyncio

    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import LiveOpcUaAdapter, SCADAAgent
    from scada_protocols.common.config import OpcUaConfig
    from scada_protocols.opcua.server import OpcUaServerAdapter

    cfg = OpcUaConfig(
        enabled=True,
        role="server",
        server_endpoint="opc.tcp://127.0.0.1:4841/etap/server",
        publish_interval_ms=100,
        node_map=[
            {"node_id": "ns=2;i=2", "browse_name": "BUS1.Voltage", "element_id": "BUS-1", "measurement_type": "voltage_magnitude", "unit": "p.u."}
        ],
    )
    server = OpcUaServerAdapter(cfg)
    server.set_provider(lambda: {"ns=2;i=2": 1.025, "BUS1.Voltage": 1.025})
    server.start_server()
    for _ in range(50):
        if server.metric.points_served > 0:
            break
        await asyncio.sleep(0.1)

    try:
        adapter = LiveOpcUaAdapter(
            endpoint="opc.tcp://127.0.0.1:4841/etap/server",
            node_map=[
                {"node_id": "ns=2;i=2", "tag": "BUS1.Voltage", "element_id": "BUS-1", "measurement_type": "voltage_magnitude", "unit": "p.u."}
            ],
        )
        agent = SCADAAgent(adapter=adapter)
        task = EngineeringTask(
            task_id="task_live_opcua",
            description="Live OPC UA telemetry acquisition",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "analysis_type": "full",
                "scada_server": "127.0.0.1",
                "scada_port": 4841,
                "scada_protocol": "opcua",
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.COMPLETED
        assert res.data["live_connection"] is True
        assert res.data["authoritative"] is True
        assert res.data["simulated"] is False
        assert res.data["provenance"]["source"] == "opcua"
        assert res.data["measurements"]["measurement_count"] == 1
        assert abs(res.data["measurements"]["measurements"][0]["value"] - 1.025) < 0.01
    finally:
        await adapter.close()
        server.stop_server()


@pytest.mark.asyncio
async def test_scada_live_opcua_server_down_fail_closed():
    """Live Adapter Test 4: OPC UA server-down scenario must return REAL_INTEGRATION_UNAVAILABLE failure."""
    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import LiveOpcUaAdapter, SCADAAgent

    adapter = LiveOpcUaAdapter(endpoint="opc.tcp://127.0.0.1:4849/etap/server", timeout=1.0)
    agent = SCADAAgent(adapter=adapter)
    task = EngineeringTask(
        task_id="task_opcua_down",
        description="Live OPC UA server down test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "connect",
            "scada_server": "127.0.0.1",
            "scada_port": 4849,
            "scada_protocol": "opcua",
        },
    )
    res = await agent.execute(task)
    assert res.status == AgentStatus.FAILED
    assert res.data["error_code"] == "REAL_INTEGRATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scada_live_iec61850_adapter_absent_fail_closed():
    """Live IEC 61850 Test 1: Adapter absent scenario must return REAL_INTEGRATION_UNAVAILABLE failure."""
    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import SCADAAgent

    agent = SCADAAgent(adapter=None)
    task = EngineeringTask(
        task_id="task_iec61850_absent",
        description="Live IEC 61850 adapter absent fail-closed test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "connect",
            "scada_server": "192.168.30.10",
            "scada_port": 102,
            "scada_protocol": "iec61850",
            "require_live": True,
        },
    )
    res = await agent.execute(task)
    assert res.status == AgentStatus.FAILED
    assert res.data["error_code"] == "REAL_INTEGRATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scada_live_iec61850_placeholder_config_fail_closed():
    """Live IEC 61850 Test 2: Placeholder config must fail closed without connection attempt."""
    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import IEC61850ClientAdapter, SCADAAgent
    from scada_protocols.common.config import Iec61850Config

    placeholder_cfg = Iec61850Config(
        enabled=False,
        clients=[{"name": "field-ied-placeholder", "host": "<PLACEHOLDER_IED_IP>", "port": 102}],
        point_map=[{
            "element_id": "BUS-1",
            "measurement_type": "voltage_magnitude",
            "logical_node": "<PLACEHOLDER_MMXU_VOLTAGE_LN>",
        }],
    )
    adapter = IEC61850ClientAdapter(config=placeholder_cfg)
    agent = SCADAAgent(adapter=adapter)
    task = EngineeringTask(
        task_id="task_iec61850_placeholder",
        description="Live IEC 61850 placeholder config fail-closed test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "connect",
            "scada_server": "192.168.30.10",
            "scada_port": 102,
            "scada_protocol": "iec61850",
        },
    )
    res = await agent.execute(task)
    assert res.status == AgentStatus.FAILED
    assert res.data["error_code"] == "REAL_INTEGRATION_UNAVAILABLE"
    # Verify no connection attempt was made (thread never created)
    assert adapter._thread is None


@pytest.mark.asyncio
async def test_scada_live_iec61850_library_missing_and_mocked_states(monkeypatch):
    """Live IEC 61850 Test 3: Documented ImportError path testing BOTH states (missing vs mocked library)."""
    import sys
    from unittest.mock import MagicMock

    import pytest

    from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
    from agents.scada_agent import IEC61850ClientAdapter, SCADAAgent
    from scada_protocols.common.config import Iec61850Config

    valid_cfg = Iec61850Config(
        enabled=True,
        clients=[{"name": "substation-ied-1", "host": "192.168.30.10", "port": 102, "ied_name": "BAY01_IED"}],
        point_map=[{
            "element_id": "BUS-1",
            "measurement_type": "voltage_magnitude",
            "logical_node": "MMXU1",
            "data_attribute": "Vol.mag.f",
            "unit": "p.u.",
        }],
    )

    # State A: Libraries absent (unmocked in this environment) -> start_client raises documented ImportError
    adapter_absent = IEC61850ClientAdapter(config=valid_cfg)
    # Ensure neither iec61850datamodel nor py61850 is in sys.modules
    for mod in ["iec61850datamodel", "py61850"]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    with pytest.raises(ImportError) as exc_info:
        adapter_absent.start_client()
    assert "Neither 'iec61850datamodel' nor 'py61850' is installed" in str(exc_info.value)

    # Executing through agent must return REAL_INTEGRATION_UNAVAILABLE
    agent = SCADAAgent(adapter=adapter_absent)
    task = EngineeringTask(
        task_id="task_iec61850_missing_lib",
        description="Missing library fail-closed",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "connect",
            "scada_server": "192.168.30.10",
            "scada_port": 102,
            "scada_protocol": "iec61850",
        },
    )
    res = await agent.execute(task)
    assert res.status == AgentStatus.FAILED
    assert res.data["error_code"] == "REAL_INTEGRATION_UNAVAILABLE"

    # State B: Library present (mocked) -> start_client succeeds in library probing
    mock_py61850 = MagicMock()
    monkeypatch.setitem(sys.modules, "py61850", mock_py61850)
    adapter_present = IEC61850ClientAdapter(config=valid_cfg)
    try:
        adapter_present.start_client()
        assert adapter_present._thread is not None
    finally:
        adapter_present.stop_client()


@pytest.mark.skip(reason="requires field IED (owner step)")
def test_scada_live_iec61850_field_ied():
    """Live IEC 61850 field test against physical substation IED.

    Safety Gated: Requires physical substation IED connection.
    To be executed exclusively by the Owner during the physical field commissioning step.
    Never faked in CI or local loopback.
    """
    pass

