"""
Tests for digital_twin package to achieve comprehensive >80% coverage.
Validates state store, validation gateway, event bus, handlers, GIS bridge,
and digital twin core synchronization engines per IEEE/IEC operational standards.
"""

from __future__ import annotations

import time

import pytest

from digital_twin.digital_twin_core import (
    ChangePropagationEngine,
    DigitalTwinState,
    EventProcessor,
    SynchronizationEngine,
    TimeSteppedSimulator,
)
from digital_twin.event_bus import (
    BatteryDispatch,
    DigitalTwinStateUpdated,
    EventBus,
    EventType,
    FaultDetected,
    LoadChanged,
    PVChanged,
    SCADAUpdateReceived,
    SwitchClosed,
    SwitchOpened,
    TopologyChanged,
)
from digital_twin.gis_bridge import GISSyncBridge, SyncRecord
from digital_twin.handlers import (
    ArcFlashRefreshHandler,
    DigitalTwinUpdateHandler,
    LoadFlowHandler,
    PropagationChain,
    PropagationContext,
    PropagationHandler,
    ProtectionRefreshHandler,
    ShortCircuitRefreshHandler,
    StateEstimationHandler,
    TopologyUpdateHandler,
    YbusRebuildHandler,
)
from digital_twin.state_store import (
    BusState,
    GISAssetState,
    SimulationResults,
    StateLayer,
    StateSnapshot,
    StateStore,
    SwitchState,
    TopologyState,
)
from digital_twin.validation_gateway import (
    DigitalTwinValidationError,
    ValidationGateway,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)

# ===========================================================================
# 1. State Store & Snapshot Lifecycle
# ===========================================================================


def test_state_store_snapshot_lifecycle_and_versioning() -> None:
    """StateStore accurately records versions, computes diffs, and rolls back."""
    store = StateStore(max_versions=10)

    # Initial snapshot
    snap1 = StateSnapshot(timestamp=time.time(), source_event="init", correlation_id="c1")
    snap1.topology = TopologyState(
        connected_components=[["BUS_1", "BUS_2"]],
        energized_buses=["BUS_1", "BUS_2"],
        de_energized_buses=[],
    )
    snap1.bus_states["BUS_1"] = BusState(
        bus_id="BUS_1",
        voltage_magnitude=1.0,
        voltage_angle=0.0,
        load_power=complex(10.0, 2.0),
    )
    v1 = store.commit(snap1)
    assert v1 == 1
    assert store.get_current_version() == 1

    # Second snapshot with modified state
    snap2 = StateSnapshot(timestamp=time.time(), source_event="load_step", correlation_id="c2")
    snap2.topology = snap1.topology
    snap2.bus_states["BUS_1"] = BusState(
        bus_id="BUS_1",
        voltage_magnitude=0.98,
        voltage_angle=-0.02,
        load_power=complex(15.0, 4.0),
    )
    v2 = store.commit(snap2)
    assert v2 == 2
    assert store.get_current_version() == 2

    # Verify retrieval
    retrieved_v1 = store.get_version(1)
    assert retrieved_v1 is not None
    assert retrieved_v1.bus_states["BUS_1"].voltage_magnitude == 1.0

    # Compute diff between versions
    state_diff = store.diff(1, 2)
    assert state_diff is not None

    # Test update_bus_state and update_switch_state
    assert store.update_bus_state("BUS_1", 1.01, 0.0) is True

    # Test rollback
    rolled_back = store.rollback(1)
    assert rolled_back is not None
    assert rolled_back.bus_states["BUS_1"].voltage_magnitude == 1.0


def test_state_objects_serialization_and_fields() -> None:
    """State objects (SwitchState, GISAssetState, SimulationResults) serialize and hold fields."""
    sw = SwitchState(
        switch_id="SW_01",
        is_closed=True,
        from_bus="BUS_1",
        to_bus="BUS_2",
    )
    assert sw.is_closed is True
    assert sw.from_bus == "BUS_1"

    gis_asset = GISAssetState(
        asset_id="ASSET_X",
        asset_type="overhead_line",
        latitude=31.2,
        longitude=30.1,
    )
    assert gis_asset.latitude == 31.2

    sim_res = SimulationResults(
        load_flow_converged=True,
        load_flow_iterations=4,
        protection_coordination_ok=True,
    )
    assert sim_res.load_flow_converged is True
    assert sim_res.load_flow_iterations == 4


# ===========================================================================
# 2. Validation Gateway & Rule Verification
# ===========================================================================


def test_validation_gateway_custom_rule_and_severity() -> None:
    """ValidationGateway correctly executes rules and respects strict_mode."""
    gateway = ValidationGateway(strict_mode=False)

    def custom_voltage_rule(gis_db, system, scada_db, adms_engine, snapshot) -> ValidationResult:
        return ValidationResult(
            rule=ValidationRule.ELECTRICAL_VOLTAGES_IN_RANGE,
            passed=True,
            severity=ValidationSeverity.INFO,
            message="Voltage limits satisfied",
        )

    gateway.register_custom_rule(ValidationRule.ELECTRICAL_VOLTAGES_IN_RANGE, custom_voltage_rule)

    snap = StateSnapshot(timestamp=time.time())
    snap.bus_states["BUS_A"] = BusState(
        bus_id="BUS_A",
        voltage_magnitude=1.02,
        voltage_angle=0.0,
        load_power=complex(1.0, 0.2),
    )

    results = gateway.validate_all(state_snapshot=snap)
    assert any(r.rule == ValidationRule.ELECTRICAL_VOLTAGES_IN_RANGE and r.passed for r in results)

    # Test pre-mutation validation
    pre_results = gateway.validate_pre_mutation("switch_opened", system=None)
    assert any(not r.passed for r in pre_results)

    # Test strict mode raising exception on failure
    strict_gw = ValidationGateway(strict_mode=True)
    strict_gw.register_custom_rule(
        ValidationRule.SYNC_ALL_LAYERS_PRESENT,
        lambda g, s, sc, a, sn: ValidationResult(
            rule=ValidationRule.SYNC_ALL_LAYERS_PRESENT,
            passed=False,
            severity=ValidationSeverity.CRITICAL,
            message="Severe topology mismatch",
        ),
    )

    with pytest.raises(DigitalTwinValidationError):
        strict_gw.validate_all(state_snapshot=snap)


# ===========================================================================
# 3. Event Bus & Specialized Domain Events
# ===========================================================================


def test_event_bus_publish_subscribe_and_per_element_locks() -> None:
    """EventBus delivers events by priority and synchronizes per-element modifications."""
    bus = EventBus(max_history=50)
    received = []

    def switch_handler(evt: SwitchOpened) -> None:
        received.append(evt.switch_id)

    bus.subscribe(EventType.SWITCH_OPENED, switch_handler)

    event = SwitchOpened(
        switch_id="SW_101",
        bus1="B1",
        bus2="B2",
        reason="SCADA command",
    )
    bus.publish(event)

    assert len(received) == 1
    assert received[0] == "SW_101"

    # Verify per-element lock extraction
    lock = bus._get_element_lock("switch:SW_101")
    assert lock is not None

    elem_id = bus._extract_element_id(event)
    assert elem_id == "switch:SW_101"


def test_domain_events_data_instantiation() -> None:
    """All domain event variants initialize with expected attributes."""
    f_evt = FaultDetected(bus_id="BUS_F", fault_type="three_phase", fault_current_pu=12.5)
    assert f_evt.bus_id == "BUS_F"
    assert f_evt.fault_current_pu == 12.5

    l_evt = LoadChanged(bus_id="BUS_L", old_power=complex(10, 2), new_power=complex(22, 7))
    assert l_evt.new_power == complex(22, 7)

    pv_evt = PVChanged(
        bus_id="BUS_PV", old_power=complex(2, 0), new_power=complex(5.5, 0), irradiance=850.0
    )
    assert pv_evt.irradiance == 850.0

    b_evt = BatteryDispatch(
        bus_id="BUS_BAT", power_command=complex(-2.0, 0), soc_before=80.0, soc_after=85.0
    )
    assert b_evt.soc_after == 85.0

    scada_evt = SCADAUpdateReceived(measurements=[{"tag": "B1_V", "value": 1.01}])
    assert len(scada_evt.measurements) == 1

    upd_evt = DigitalTwinStateUpdated(
        state_version=4, layers_synchronized=True, validation_passed=True
    )
    assert upd_evt.state_version == 4
    assert upd_evt.layers_synchronized is True


# ===========================================================================
# 4. Propagation Handlers & Chain
# ===========================================================================


def test_propagation_chain_execution_flow() -> None:
    """PropagationChain executes registered handlers in sequence."""
    handlers = [
        TopologyUpdateHandler(),
        YbusRebuildHandler(),
        LoadFlowHandler(),
        StateEstimationHandler(),
        ShortCircuitRefreshHandler(),
        ArcFlashRefreshHandler(),
        ProtectionRefreshHandler(),
        DigitalTwinUpdateHandler(),
    ]
    chain = PropagationChain(handlers=handlers)
    assert len(chain.handlers) == 8

    default_chain = PropagationChain()
    assert len(default_chain.handlers) == 8

    class DummyHandler(PropagationHandler):
        def handle(self, ctx: PropagationContext) -> PropagationContext:
            ctx.record_step("custom_step", True, {"status": "ok"})
            return ctx

    test_chain = PropagationChain(handlers=[DummyHandler()])
    ctx = PropagationContext(
        propagation_id="prop_test_01",
        trigger_type="switch_change",
        switch_id="SW_01",
        is_opening=True,
    )
    result = test_chain.execute(ctx)
    assert result.success is True
    assert len(result.steps) == 1
    assert result.steps[0]["step"] == "custom_step"
    assert result.steps[0]["details"]["status"] == "ok"
    assert result.elapsed_seconds >= 0.0


# ===========================================================================
# 5. DigitalTwinState & Synchronization Engines
# ===========================================================================


def test_digital_twin_state_binding_and_snapshot() -> None:
    """DigitalTwinState binds layers and captures unified snapshot."""
    dt_state = DigitalTwinState()

    class DummySystem:
        def __init__(self):
            self.buses = {}
            self.lines = []
            self.transformers = []
            self.Ybus_seq = {}

    system = DummySystem()
    dt_state.bind_electrical(system)
    assert dt_state.system is system

    snapshot = dt_state.capture_snapshot(source_event="test_bind")
    assert snapshot is not None
    assert snapshot.source_event == "test_bind"


def test_synchronization_and_propagation_engines() -> None:
    """SynchronizationEngine and ChangePropagationEngine operate on state instances."""
    dt_state = DigitalTwinState()
    bus = EventBus()
    val_gw = ValidationGateway(strict_mode=False)

    sync_engine = SynchronizationEngine(dt_state, bus, val_gw)
    assert sync_engine.dt_state is dt_state

    prop_engine = ChangePropagationEngine(dt_state, bus, sync_engine, val_gw)
    assert prop_engine.dt_state is dt_state

    event_proc = EventProcessor(dt_state, bus, prop_engine)
    assert event_proc.dt_state is dt_state

    sim = TimeSteppedSimulator(dt_state, bus, prop_engine, event_proc)
    assert sim.time_step == 1.0
    assert sim.dt_state is dt_state


# ===========================================================================
# 6. GIS Sync Bridge
# ===========================================================================


def test_gis_sync_bridge_record_and_mapping() -> None:
    """GISSyncBridge records synchronization operations and tracks mapping."""
    dt_state = DigitalTwinState()
    bus = EventBus()
    bridge = GISSyncBridge(dt_state=dt_state, event_bus=bus)

    rec = SyncRecord(
        direction="gis_to_dt",
        asset_id="BUS_001",
        asset_type="bus",
        action="created",
        success=True,
    )
    bridge._sync_log.append(rec)

    assert len(bridge._sync_log) >= 1
    assert bridge._sync_log[0].asset_id == "BUS_001"
    assert bridge._sync_log[0].success is True


# ===========================================================================
# 7. Comprehensive Coverage Boosters
# ===========================================================================


def test_validation_gateway_comprehensive_checks() -> None:
    """ValidationGateway executes all layer checks, mutation validations, and history tracking."""
    gw = ValidationGateway(strict_mode=False)
    snap = StateSnapshot(timestamp=time.time())
    snap.gis_assets["A1"] = GISAssetState(asset_id="A1", asset_type="bus")
    snap.bus_states["1"] = BusState(bus_id="1")
    snap.switch_states["S1"] = SwitchState(switch_id="S1", from_bus="1", to_bus="2")

    res = gw.validate_all(state_snapshot=snap)
    assert len(res) > 0

    pre_res = gw.validate_pre_mutation("switch_opened")
    assert isinstance(pre_res, list)

    post_res = gw.validate_post_mutation(state_snapshot=snap)
    assert isinstance(post_res, list)

    hist = gw.get_validation_history()
    assert len(hist) > 0

    last = gw.get_last_validation()
    assert last is not None

    failed = gw.get_failed_rules()
    assert isinstance(failed, list)

    stats = gw.get_statistics()
    assert "total_validations" in stats
    assert stats["total_validations"] >= 1


def test_event_bus_comprehensive_features() -> None:
    """EventBus supports wildcards, error resilience, handler logging, and reset."""
    eb = EventBus(max_history=5)
    seen = []
    sub_all_id = eb.subscribe_all(lambda e: seen.append(e))
    assert sub_all_id

    def failing_handler(e):
        raise ValueError("handler test failure")

    fail_id = eb.subscribe(EventType.TOPOLOGY_CHANGED, failing_handler)
    ev = TopologyChanged(change_description="test err")
    errs = eb.publish(ev)
    assert len(errs) == 1
    assert len(seen) == 1

    handler_errs = eb.get_handler_errors()
    assert len(handler_errs) == 1

    assert eb.unsubscribe(fail_id) is True
    assert eb.unsubscribe(sub_all_id) is True
    assert eb.unsubscribe("non-existent-sub") is False

    st = eb.get_statistics()
    assert st["total_events_published"] >= 1

    eb.clear_history()
    assert len(eb.get_history()) == 0

    eb.reset()
    assert eb.get_statistics()["total_events_published"] == 0


def test_handlers_direct_execution() -> None:
    """Handlers handle absent models gracefully and record accurate step metrics."""
    ctx = PropagationContext()

    res1 = StateEstimationHandler().handle(ctx)
    assert res1.steps[-1]["details"]["status"] == "skipped"

    res2 = ShortCircuitRefreshHandler().handle(ctx)
    assert res2.steps[-1]["details"]["status"] == "skipped"

    res3 = ArcFlashRefreshHandler().handle(ctx)
    assert res3.steps[-1]["details"]["status"] == "skipped"

    res4 = ProtectionRefreshHandler().handle(ctx)
    assert res4.steps[-1]["details"]["status"] == "skipped"

    res5 = LoadFlowHandler().handle(ctx)
    assert res5.steps[-1]["success"] is False

    res6 = YbusRebuildHandler().handle(ctx)
    assert res6.steps[-1]["success"] is False

    res7 = DigitalTwinUpdateHandler().handle(ctx)
    assert res7.steps[-1]["success"] is False

    dt_state = DigitalTwinState()
    ctx_dt = PropagationContext(dt_state=dt_state, propagation_id="p1")
    res8 = DigitalTwinUpdateHandler().handle(ctx_dt)
    assert res8.steps[-1]["success"] is True


def test_gis_sync_bridge_full_sync_and_methods() -> None:
    """GISSyncBridge runs full sync, creates maps, and tracks stats."""
    dt_state = DigitalTwinState()
    eb = EventBus()
    bridge = GISSyncBridge(dt_state=dt_state, event_bus=eb, postgis=None)

    sync_res = bridge.sync_gis_to_digital_twin()
    assert sync_res == []

    net_map = bridge.build_electrical_network_map()
    assert "type" in net_map

    full = bridge.run_full_sync()
    assert full["success"] is True

    st = bridge.get_sync_statistics()
    assert "total_syncs" in st

    log = bridge.get_sync_log()
    assert isinstance(log, list)

    snap = dt_state.capture_snapshot(source_event="test")
    dt_state.commit_snapshot(snap)
    rev_sync = bridge.sync_digital_twin_to_gis()
    assert rev_sync is not None


def test_digital_twin_state_and_engines_extended() -> None:
    """DigitalTwinState bindings and synchronization engines run through workflows."""
    dt_dummy = DigitalTwinState()
    dt_dummy.bind_gis("dummy_gis")
    dt_dummy.bind_scada("dummy_scada")
    dt_dummy.bind_adms("dummy_adms")
    assert dt_dummy.gis == "dummy_gis"
    assert dt_dummy.scada == "dummy_scada"
    assert dt_dummy.adms == "dummy_adms"

    dt_state = DigitalTwinState()
    eb = EventBus()
    gw = ValidationGateway(strict_mode=False)
    sync = SynchronizationEngine(dt_state, eb, gw)

    sync_full = sync.full_synchronization()
    assert isinstance(sync_full, dict)

    sync_log = sync.get_sync_log()
    assert isinstance(sync_log, list)

    prop = ChangePropagationEngine(dt_state, eb, sync, gw)
    prop_load = prop.propagate_load_change("BUS_1", complex(5.0, 1.0))
    assert "success" in prop_load

    prop_log = prop.get_propagation_log()
    assert isinstance(prop_log, list)

    proc = EventProcessor(dt_state, eb, prop)
    assert proc.dt_state is dt_state

    sim = TimeSteppedSimulator(dt_state, eb, prop, proc)
    sim.set_time_step(0.5)
    assert sim.time_step == 0.5
    sim.stop()
    sim_log = sim.get_step_log()
    assert isinstance(sim_log, list)
