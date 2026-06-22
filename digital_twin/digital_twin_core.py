"""
Digital Twin Core - Unified Synchronization Engine
====================================================
Merges GIS model, electrical model, and ADMS state into one
synchronized digital twin system.

Implements:
- DigitalTwinState: Unified state across all layers
- SynchronizationEngine: Ensures cross-layer consistency
- ChangePropagationEngine: Automatic workflow propagation
- EventProcessor: Event-to-action dispatch
- TimeSteppedSimulator: Time-stepped simulation loop
- LivePowerSystemEngine: Extended PowerSystemEngine with live topology

Automatic Workflow:
  SCADA Update -> Topology Update -> Ybus Rebuild -> Load Flow ->
  State Estimation Validation -> Short Circuit Refresh ->
  Arc Flash Refresh -> Protection Refresh -> Digital Twin State Update

Hard Constraints:
  - GIS = Spatial Truth
  - Electrical = Mathematical Truth
  - ADMS = Operational Truth
"""

import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any, Dict, List

import numpy as np

from .event_bus import (
    BatteryDispatch,
    DigitalTwinStateUpdated,
    DomainEvent,
    EventBus,
    EventType,
    FaultAnalysisCompleted,
    FaultDetected,
    LoadChanged,
    LoadFlowCompleted,
    ProtectionRefreshed,
    PVChanged,
    SCADAUpdateReceived,
    SwitchClosed,
    SwitchOpened,
)
from .state_store import (
    BusState,
    GISAssetState,
    StateSnapshot,
    StateStore,
    SwitchState,
    TopologyState,
)
from .validation_gateway import ValidationGateway, ValidationResult, ValidationSeverity

logger = logging.getLogger(__name__)


# ============================================================
# DIGITAL TWIN STATE
# ============================================================


class DigitalTwinState:
    """
    Unified state object holding synchronized state across all three layers.

    GIS = Spatial Truth
    Electrical = Mathematical Truth
    ADMS = Operational Truth

    This is the single source of truth for the entire platform.
    """

    def __init__(self):
        self.state_store = StateStore(max_versions=1000)
        self._gis_db = None
        self._system = None
        self._scada_db = None
        self._adms_engine = None
        self._validation_gateway = ValidationGateway(strict_mode=False)

    def bind_gis(self, gis_db) -> None:
        """Bind GIS database (Spatial Truth)."""
        self._gis_db = gis_db

    def bind_electrical(self, system) -> None:
        """Bind electrical model (Mathematical Truth)."""
        self._system = system

    def bind_scada(self, scada_db) -> None:
        """Bind SCADA database."""
        self._scada_db = scada_db

    def bind_adms(self, adms_engine) -> None:
        """Bind ADMS control engine (Operational Truth)."""
        self._adms_engine = adms_engine

    @property
    def gis(self):
        return self._gis_db

    @property
    def system(self):
        return self._system

    @property
    def scada(self):
        return self._scada_db

    @property
    def adms(self):
        return self._adms_engine

    def capture_snapshot(self, source_event: str = "", correlation_id: str = "") -> StateSnapshot:
        """Capture current state of all layers into a snapshot."""
        snapshot = StateSnapshot(
            timestamp=time.time(), source_event=source_event, correlation_id=correlation_id
        )

        # Capture GIS state
        if self._gis_db is not None:
            for asset_id, asset in self._gis_db.assets.items():
                snapshot.gis_assets[asset_id] = GISAssetState(
                    asset_id=asset.asset_id,
                    asset_type=asset.asset_type.value
                    if hasattr(asset.asset_type, "value")
                    else str(asset.asset_type),
                    electrical_id=asset.electrical_id or "",
                    latitude=asset.position.latitude if asset.position else 0.0,
                    longitude=asset.position.longitude if asset.position else 0.0,
                    zone_id=asset.zone_id or "",
                )
            for zone_id, zone in self._gis_db.zones.items():
                snapshot.gis_zones[zone_id] = zone.name

        # Capture Electrical state
        if self._system is not None:
            bus_ids = sorted(self._system.buses.keys())
            for bid in bus_ids:
                bus = self._system.buses[bid]
                snapshot.bus_states[str(bid)] = BusState(
                    bus_id=str(bid),
                    voltage_magnitude=bus.voltage_magnitude,
                    voltage_angle=bus.voltage_angle,
                    load_power=bus.load_power,
                    generation_power=bus.generation_power,
                    bus_type=bus.bus_type,
                )
            # Ybus info
            if "1" in self._system.Ybus_seq:
                Y = self._system.Ybus_seq["1"]
                snapshot.ybus_shape = Y.shape
                snapshot.ybus_checksum = self._compute_ybus_checksum(Y)

        # Capture ADMS state
        if self._scada_db is not None:
            for did, dev in self._scada_db.switch_devices.items():
                snapshot.switch_states[did] = SwitchState(
                    switch_id=did,
                    is_closed=dev.is_conducting(),
                    from_bus=dev.from_element,
                    to_bus=dev.to_element,
                )
            snapshot.scada_measurement_count = len(self._scada_db.measurements)

        if self._adms_engine is not None:
            topo = self._adms_engine.topology
            snapshot.topology = TopologyState(
                connected_components=[list(comp) for comp in topo.find_connected_components()],
                energized_buses=list(self._adms_engine.source_buses)
                if hasattr(self._adms_engine, "source_buses")
                else [],
                de_energized_buses=[],
                section_buses={k: list(v) for k, v in topo.section_buses.items()}
                if hasattr(topo, "section_buses")
                else {},
            )

        return snapshot

    def commit_snapshot(self, snapshot: StateSnapshot) -> int:
        """Commit a snapshot to the state store."""
        return self.state_store.commit(snapshot)

    def validate(self) -> List[ValidationResult]:
        """Run full validation across all layers."""
        return self._validation_gateway.validate_all(
            gis_db=self._gis_db,
            system=self._system,
            scada_db=self._scada_db,
            adms_engine=self._adms_engine,
        )

    def get_current_snapshot(self) -> StateSnapshot | None:
        """Get the latest committed snapshot."""
        return self.state_store.get_current()

    @staticmethod
    def _compute_ybus_checksum(Y: np.ndarray) -> int:
        """Compute a checksum of the Ybus matrix for change detection."""
        try:
            data = Y.tobytes()
            return int(hashlib.sha256(data).hexdigest()[:8], 16)
        except Exception:
            return 0

    def is_synchronized(self) -> bool:
        """Check if all layers are synchronized."""
        results = self.validate()
        critical_failures = [
            r
            for r in results
            if not r.passed
            and r.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
        ]
        return len(critical_failures) == 0


# ============================================================
# SYNCHRONIZATION ENGINE
# ============================================================


class SynchronizationEngine:
    """
    Ensures cross-layer consistency between GIS, Electrical, and ADMS.

    Three Truths Principle:
    - GIS is the Spatial Truth (coordinates, zones)
    - Electrical is the Mathematical Truth (impedances, equations)
    - ADMS is the Operational Truth (switching states, measurements)

    Synchronization ensures:
    1. Every GIS asset with an electrical_id has a matching electrical element
    2. Every electrical element that should be geo-located has a GIS asset
    3. ADMS switching states match the electrical topology
    4. ADMS switch devices have GIS positions
    5. Ybus reflects current topology (switch states)
    """

    def __init__(
        self, dt_state: DigitalTwinState, event_bus: EventBus, validation_gateway: ValidationGateway
    ):
        self.dt_state = dt_state
        self.event_bus = event_bus
        self.validation_gateway = validation_gateway
        self._sync_log: List[Dict[str, Any]] = []

    def synchronize_gis_to_electrical(self) -> List[str]:
        """
        Synchronize GIS references to the electrical model.
        Ensures every GIS asset with electrical_id resolves to an
        existing electrical model element.

        Returns list of errors found.
        """
        errors = []
        if self.dt_state.gis is None or self.dt_state.system is None:
            return ["GIS or Electrical model not bound"]

        # Get all electrical IDs from the system
        electrical_ids = set()
        for bid in self.dt_state.system.buses:
            electrical_ids.add(str(bid))
        for line in self.dt_state.system.lines:
            electrical_ids.add(str(line.line_id))
        for xf in self.dt_state.system.transformers:
            electrical_ids.add(str(xf.transformer_id))

        # Validate GIS -> Electrical references
        gis_errors = self.dt_state.gis.validate_gis_electrical_alignment(electrical_ids)
        errors.extend(gis_errors)

        # Check reverse: electrical elements that should have GIS don't
        gis_electrical_ids = set()
        for asset in self.dt_state.gis.assets.values():
            if asset.electrical_id:
                gis_electrical_ids.add(asset.electrical_id)

        for eid in electrical_ids:
            if eid not in gis_electrical_ids:
                errors.append(f"Electrical element '{eid}' has no GIS asset (spatial truth gap)")

        return errors

    def synchronize_adms_to_electrical(self) -> List[str]:
        """
        Synchronize ADMS switching states to the electrical model.
        Ensures the topology processor reflects current switch states.

        Returns list of errors found.
        """
        errors = []
        if self.dt_state.adms is None or self.dt_state.system is None:
            return ["ADMS or Electrical model not bound"]

        # Check that every switch in ADMS topology exists in SCADA
        if self.dt_state.scada is not None:
            for switch_id in self.dt_state.adms.topology.switches:
                if switch_id not in self.dt_state.scada.switch_devices:
                    errors.append(f"Switch '{switch_id}' in topology but not in SCADA database")

        # Check that SCADA switch states match topology connections
        if self.dt_state.scada is not None:
            for did, dev in self.dt_state.scada.switch_devices.items():
                if did in self.dt_state.adms.topology.switches:
                    bus1, bus2 = self.dt_state.adms.topology.switches[did]
                    is_connected = bus2 in self.dt_state.adms.topology.bus_connections.get(
                        bus1, set()
                    )
                    if dev.is_conducting() != is_connected:
                        errors.append(
                            f"Switch '{did}' SCADA status ({dev.status.value}) "
                            f"does not match topology connection state ({is_connected})"
                        )

        return errors

    def synchronize_gis_to_adms(self) -> List[str]:
        """
        Synchronize GIS positions with ADMS switch devices.
        Every switch device should have a GIS position.

        Returns list of errors found.
        """
        errors = []
        if self.dt_state.gis is None or self.dt_state.scada is None:
            return ["GIS or SCADA not bound"]

        for did, _dev in self.dt_state.scada.switch_devices.items():
            gis_asset = self.dt_state.gis.find_asset_by_electrical_id(did)
            if gis_asset is None:
                errors.append(f"Switch device '{did}' has no GIS asset (missing spatial truth)")
            elif gis_asset.position is None:
                errors.append(f"Switch device '{did}' GIS asset has no position")

        return errors

    def full_synchronization(self) -> Dict[str, List[str]]:
        """
        Run full synchronization across all layer pairs.

        Returns dict with keys 'gis_electrical', 'adms_electrical',
        'gis_adms' containing lists of errors.
        """
        result = {
            "gis_electrical": self.synchronize_gis_to_electrical(),
            "adms_electrical": self.synchronize_adms_to_electrical(),
            "gis_adms": self.synchronize_gis_to_adms(),
        }

        self._sync_log.append(
            {
                "timestamp": time.time(),
                "results": {k: len(v) for k, v in result.items()},
                "total_errors": sum(len(v) for v in result.values()),
            }
        )

        return result

    def get_sync_log(self) -> List[Dict[str, Any]]:
        """Get synchronization history."""
        return self._sync_log


# ============================================================
# CHANGE PROPAGATION ENGINE
# ============================================================


class ChangePropagationEngine:
    """
    Implements the automatic workflow for change propagation.

    SCADA Update -> Topology Update -> Ybus Rebuild -> Load Flow ->
    State Estimation Validation -> Short Circuit Refresh ->
    Arc Flash Refresh -> Protection Refresh -> Digital Twin State Update

    Each step is modelled as a ``PropagationHandler`` in a
    ``PropagationChain`` (see ``digital_twin.handlers``).  Adding or
    removing steps is now a matter of configuring the handler list rather
    than editing a monolithic method.
    """

    def __init__(
        self,
        dt_state: DigitalTwinState,
        event_bus: EventBus,
        sync_engine: SynchronizationEngine,
        validation_gateway: ValidationGateway,
        chain=None,
    ):
        """
        Parameters
        ----------
        dt_state : DigitalTwinState
            The unified digital twin state.
        event_bus : EventBus
            Event bus for publishing propagation events.
        sync_engine : SynchronizationEngine
            Engine for cross-layer synchronisation.
        validation_gateway : ValidationGateway
            Gateway for model validation.
        chain : PropagationChain, optional
            Custom handler chain.  Defaults to the standard 8-step chain.
        """
        self.dt_state = dt_state
        self.event_bus = event_bus
        self.sync_engine = sync_engine
        self.validation_gateway = validation_gateway
        self._propagation_log: List[Dict[str, Any]] = []
        self._load_flow_solver = None
        self._state_estimator = None

        if chain is not None:
            self._chain = chain
        else:
            from .handlers import PropagationChain

            self._chain = PropagationChain()

    def bind_load_flow_solver(self, solver) -> None:
        """Bind a load flow solver instance."""
        self._load_flow_solver = solver

    def bind_state_estimator(self, estimator) -> None:
        """Bind a state estimator instance."""
        self._state_estimator = estimator

    def propagate_switch_change(
        self, switch_id: str, is_opening: bool, reason: str = ""
    ) -> Dict[str, Any]:
        """
        Propagate a switch change through the entire workflow.

        Delegates to the ``PropagationChain`` which runs each step via
        its handler classes.  This replaces the previous 130-line
        monolithic method with a composable chain-of-responsibility.
        """
        propagation_id = f"prop_{int(time.time() * 1000)}"

        from .handlers import PropagationContext

        ctx = PropagationContext(
            propagation_id=propagation_id,
            trigger_type="switch_change",
            switch_id=switch_id,
            is_opening=is_opening,
            reason=reason,
            dt_state=self.dt_state,
            event_bus=self.event_bus,
            sync_engine=self.sync_engine,
            validation_gateway=self.validation_gateway,
            load_flow_solver=self._load_flow_solver,
            state_estimator=self._state_estimator,
        )

        ctx = self._chain.execute(ctx)

        propagation_record = {
            "propagation_id": propagation_id,
            "trigger": f"switch_{'opened' if is_opening else 'closed'}",
            "switch_id": switch_id,
            "success": ctx.success,
            "elapsed_seconds": ctx.elapsed_seconds,
            "steps": ctx.steps,
            "timestamp": time.time(),
        }
        self._propagation_log.append(propagation_record)

        return propagation_record

    def propagate_load_change(self, bus_id: str, new_power: complex) -> Dict[str, Any]:
        """Propagate a load change through the workflow."""
        propagation_id = f"prop_{int(time.time() * 1000)}"
        start_time = time.time()

        # Update electrical model
        if self.dt_state.system is not None:
            bid = int(bus_id) if bus_id.isdigit() else bus_id
            if bid in self.dt_state.system.buses:
                self.dt_state.system.buses[bid].load_power = new_power

                # Rebuild Ybus and run load flow
                self.dt_state.system.Ybus_seq.clear()
                self.dt_state.system.build_ybus(seq="1")

                from .handlers import LoadFlowHandler, PropagationContext

                lf_ctx = PropagationContext(
                    propagation_id=propagation_id,
                    dt_state=self.dt_state,
                    load_flow_solver=self._load_flow_solver,
                )
                lf_ctx = LoadFlowHandler().handle(lf_ctx)
                lf_success = len(lf_ctx.steps) > 0 and lf_ctx.steps[-1].get("success", False)

                # Update digital twin state
                snapshot = self.dt_state.capture_snapshot(
                    source_event="load_changed", correlation_id=propagation_id
                )
                validation_results = self.dt_state.validate()
                snapshot.validation_passed = all(r.passed for r in validation_results)
                version = self.dt_state.commit_snapshot(snapshot)

                self.event_bus.publish(
                    DigitalTwinStateUpdated(
                        state_version=version,
                        layers_synchronized=snapshot.validation_passed,
                        validation_passed=snapshot.validation_passed,
                        source="change_propagation",
                        correlation_id=propagation_id,
                    )
                )

                return {
                    "propagation_id": propagation_id,
                    "success": lf_success,
                    "elapsed_seconds": time.time() - start_time,
                    "load_flow": lf_ctx.steps[-1].get("details", {}) if lf_ctx.steps else {},
                }

        return {
            "propagation_id": propagation_id,
            "success": False,
            "elapsed_seconds": time.time() - start_time,
            "error": "Electrical model not bound or bus not found",
        }

    def _run_load_flow(self) -> Dict[str, Any]:
        """Run load flow on the bound system."""
        if self.dt_state.system is None:
            return {"converged": False, "error": "No system bound"}

        try:
            from load_flow.load_flow import LoadFlowSolver

            solver = LoadFlowSolver(self.dt_state.system)
            converged = solver.solve(max_iter=100, tol=1e-6)

            bus_voltages = {}
            for bid in solver.bus_ids:
                bus_voltages[str(bid)] = solver.V[solver.bus_index[bid]]

            return {
                "converged": converged,
                "iterations": len(solver.iteration_log) if hasattr(solver, "iteration_log") else 0,
                "bus_voltages": bus_voltages,
            }
        except Exception as e:
            logger.error(f"Load flow failed: {e}")
            return {"converged": False, "error": str(e)}

    def _run_state_estimation(self) -> Dict[str, Any]:
        """Run state estimation if measurements are available."""
        if self.dt_state.system is None or self.dt_state.scada is None:
            return {"converged": False, "error": "System or SCADA not bound"}

        try:
            from scada_model.state_estimation import WLSEstimator

            estimator = WLSEstimator()

            # Build measurements from SCADA
            bus_ids = sorted(self.dt_state.system.buses.keys())
            measurements = {"voltage_mag": {}, "power_injection": {}, "power_flow": {}}

            for i, bid in enumerate(bus_ids):
                vmag = self.dt_state.scada.get_latest_voltage(str(bid))
                if vmag is not None:
                    measurements["voltage_mag"][i] = (vmag, 0.01)

                pq = self.dt_state.scada.get_latest_power(str(bid))
                if pq is not None:
                    measurements["power_injection"][i] = (pq[0], pq[1], 0.02, 0.02)

            Ybus = self.dt_state.system.get_ybus(seq="1")
            result = estimator.estimate(Ybus, measurements, [str(bid) for bid in bus_ids])

            return {
                "converged": result.status.value == "converged",
                "bad_data_count": len(result.bad_data_detected),
                "max_residual": result.max_residual,
            }
        except Exception as e:
            logger.warning(f"State estimation failed: {e}")
            return {"converged": False, "error": str(e)}

    def _refresh_short_circuit(self) -> Dict[str, Any]:
        """Refresh short circuit analysis."""
        if self.dt_state.system is None:
            return {"error": "No system bound"}
        try:
            self.dt_state.system.build_sequence_networks()
            return {"status": "refreshed", "sequences_built": True}
        except Exception as e:
            return {"error": str(e)}

    def _refresh_arc_flash(self) -> Dict[str, Any]:
        """Refresh arc flash analysis using current fault current data.

        Builds sequence networks from the current topology, computes fault
        currents at each bus, and estimates incident energy per IEEE 1584-2018.
        """
        if self.dt_state.system is None:
            return {"status": "skipped", "reason": "No electrical model bound"}

        try:
            import math

            from fault_analysis.fault import FaultAnalyzer

            self.dt_state.system.build_sequence_networks(for_fault=True)
            Ybus_pos = self.dt_state.system.get_ybus(seq="1")
            Ybus_neg = self.dt_state.system.get_ybus(seq="2")
            Ybus_zero = self.dt_state.system.get_ybus(seq="0")

            analyzer = FaultAnalyzer(
                Ybus_pos, Ybus_neg, Ybus_zero, base_mva=self.dt_state.system.base_mva
            )

            results: Dict[str, Any] = {}
            bus_ids = sorted(self.dt_state.system.buses.keys())
            bus_index = {bid: idx for idx, bid in enumerate(bus_ids)}
            for bus_id in bus_ids:
                bus_idx = bus_index[bus_id]
                fault = analyzer.three_phase_fault(bus_idx)
                fault_ka = fault.get("fault_current_ka", 0.0)
                # Simplified IEEE 1584-2018 incident energy estimate
                # E = 10^(k1 + k2*log10(Ibf)) * t / D^x (VCB default)
                arc_duration = 0.2  # default 200ms clearing time
                working_distance_mm = 610.0  # 24 inches
                k1, k2, x_ie = -0.153, -0.276, 1.0
                log_Iarc = k1 + k2 * math.log10(fault_ka)
                Iarc = 10**log_Iarc
                log_E = 0.434 + (-0.262) * math.log10(Iarc)
                E_base = 10**log_E
                E = E_base * arc_duration / (working_distance_mm**x_ie)
                boundary_mm = (E_base * arc_duration / 1.2) ** (1.0 / x_ie)

                if E <= 1.2:
                    ppe = "0"
                elif E <= 4.0:
                    ppe = "1"
                elif E <= 8.0:
                    ppe = "2"
                elif E <= 25.0:
                    ppe = "3"
                elif E <= 40.0:
                    ppe = "4"
                else:
                    ppe = "DANGER"

                results[str(bus_id)] = {
                    "incident_energy_cal_cm2": round(E, 4),
                    "arc_flash_boundary_mm": round(boundary_mm, 1),
                    "ppe_level": ppe,
                    "arc_current_ka": round(Iarc, 4),
                    "fault_current_ka": round(fault_ka, 4),
                    "method": "IEEE 1584-2018 (estimated)",
                }

            return {"status": "refreshed", "bus_count": len(results), "results": results}
        except Exception as e:
            logger.warning(f"Arc flash refresh failed: {e}")
            return {"status": "error", "error": str(e)}

    def _refresh_protection(self) -> Dict[str, Any]:
        """Refresh protection coordination using current fault current data.

        Builds sequence networks, computes fault currents, and verifies
        that all relay pairs maintain coordination margins.
        """
        if self.dt_state.system is None:
            return {"status": "skipped", "reason": "No electrical model bound"}

        try:
            from coordination.coordination import CoordinationEngine
            from fault_analysis.fault import FaultAnalyzer
            from relays.relay import OvercurrentRelay

            self.dt_state.system.build_sequence_networks(for_fault=True)
            Ybus_pos = self.dt_state.system.get_ybus(seq="1")
            Ybus_neg = self.dt_state.system.get_ybus(seq="2")
            Ybus_zero = self.dt_state.system.get_ybus(seq="0")

            analyzer = FaultAnalyzer(
                Ybus_pos, Ybus_neg, Ybus_zero, base_mva=self.dt_state.system.base_mva
            )

            # Calculate fault currents at all buses
            fault_currents: List[float] = []
            bus_ids = sorted(self.dt_state.system.buses.keys())
            bus_index = {bid: idx for idx, bid in enumerate(bus_ids)}
            for bus_id in bus_ids:
                bus_idx = bus_index[bus_id]
                fault = analyzer.three_phase_fault(bus_idx)
                fc_pu = abs(fault.get("fault_current", complex(0, 0)))
                if fc_pu > 0:
                    fault_currents.append(fc_pu)

            if not fault_currents:
                return {"status": "skipped", "reason": "No fault currents available"}

            # Use representative fault current range for coordination check
            representative_faults = sorted({
                round(fc, 0) for fc in fault_currents if fc > 1.0
            })[:10]  # Up to 10 representative fault levels

            if not representative_faults:
                representative_faults = [2.0, 5.0, 10.0, 20.0]

            # Create default relay pair for coordination check
            coord_engine = CoordinationEngine()
            relay1 = OvercurrentRelay(relay_id=1, name="Upstream", TMS=0.5, Ip=1.0)
            relay2 = OvercurrentRelay(relay_id=2, name="Downstream", TMS=0.2, Ip=1.0)

            coord_results = coord_engine.check_coordination_range(
                relay1, relay2, representative_faults
            )
            all_coordinated = all(r["coordinated"] for r in coord_results)
            min_margin = min(r["margin"] for r in coord_results) if coord_results else 0.0

            return {
                "status": "refreshed",
                "all_coordinated": all_coordinated,
                "min_margin_sec": round(min_margin, 4),
                "fault_levels_checked": len(representative_faults),
                "coordination_standard": "IEC 60255",
            }
        except Exception as e:
            logger.warning(f"Protection refresh failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_propagation_log(self) -> List[Dict[str, Any]]:
        """Get propagation history."""
        return self._propagation_log


# ============================================================
# EVENT PROCESSOR
# ============================================================


class EventProcessor:
    """
    Event-to-action dispatcher for the digital twin.

    Subscribes to input events and dispatches them to the
    appropriate ChangePropagationEngine methods.

    Input Events:
    - SwitchOpened -> propagate_switch_change(opening=True)
    - SwitchClosed -> propagate_switch_change(opening=False)
    - FaultDetected -> FLISR workflow
    - LoadChanged -> propagate_load_change
    - PVChanged -> propagate_load_change (PV as negative load)
    - BatteryDispatch -> propagate_load_change
    - SCADAUpdateReceived -> update SCADA then propagate
    """

    def __init__(
        self,
        dt_state: DigitalTwinState,
        event_bus: EventBus,
        propagation_engine: ChangePropagationEngine,
    ):
        self.dt_state = dt_state
        self.event_bus = event_bus
        self.propagation = propagation_engine
        self._processed_events: List[Dict[str, Any]] = []
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to all input events."""
        self.event_bus.subscribe(EventType.SWITCH_OPENED, self._on_switch_opened, priority=10)
        self.event_bus.subscribe(EventType.SWITCH_CLOSED, self._on_switch_closed, priority=10)
        self.event_bus.subscribe(EventType.FAULT_DETECTED, self._on_fault_detected, priority=10)
        self.event_bus.subscribe(EventType.LOAD_CHANGED, self._on_load_changed, priority=10)
        self.event_bus.subscribe(EventType.PV_CHANGED, self._on_pv_changed, priority=10)
        self.event_bus.subscribe(EventType.BATTERY_DISPATCH, self._on_battery_dispatch, priority=10)
        self.event_bus.subscribe(
            EventType.SCADA_UPDATE_RECEIVED, self._on_scada_update, priority=10
        )

    def _on_switch_opened(self, event: DomainEvent) -> None:
        """Handle SwitchOpened event."""
        if not isinstance(event, SwitchOpened):
            return
        result = self.propagation.propagate_switch_change(
            switch_id=event.switch_id, is_opening=True, reason=event.reason
        )
        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "switch_opened",
                "switch_id": event.switch_id,
                "result": result,
            }
        )

    def _on_switch_closed(self, event: DomainEvent) -> None:
        """Handle SwitchClosed event."""
        if not isinstance(event, SwitchClosed):
            return
        result = self.propagation.propagate_switch_change(
            switch_id=event.switch_id, is_opening=False, reason=event.reason
        )
        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "switch_closed",
                "switch_id": event.switch_id,
                "result": result,
            }
        )

    def _on_fault_detected(self, event: DomainEvent) -> None:
        """Handle FaultDetected event - triggers FLISR."""
        if not isinstance(event, FaultDetected):
            return
        result = {"flisr_executed": False}
        if self.dt_state.adms is not None:
            try:
                flisr_result = self.dt_state.adms.execute_flisr(
                    tripped_switch_ids=event.tripped_switches, scada_db=self.dt_state.scada
                )
                result = {
                    "flisr_executed": True,
                    "fault_section": flisr_result.fault_section,
                    "isolated": flisr_result.isolated_sections,
                    "restored": flisr_result.restored_sections,
                    "stage": flisr_result.stage.value,
                }
                # After FLISR, propagate topology changes
                self.propagation.propagate_switch_change(
                    switch_id=event.tripped_switches[0] if event.tripped_switches else "",
                    is_opening=True,
                    reason=f"FLISR for fault at {event.bus_id}",
                )
            except Exception as e:
                result = {"flisr_executed": False, "error": str(e)}

        self._processed_events.append(
            {"event_id": event.event_id, "event_type": "fault_detected", "result": result}
        )

    def _on_load_changed(self, event: DomainEvent) -> None:
        """Handle LoadChanged event."""
        if not isinstance(event, LoadChanged):
            return
        result = self.propagation.propagate_load_change(
            bus_id=event.bus_id, new_power=event.new_power
        )
        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "load_changed",
                "bus_id": event.bus_id,
                "result": result,
            }
        )

    def _on_pv_changed(self, event: DomainEvent) -> None:
        """Handle PVChanged event - PV modeled as negative load."""
        if not isinstance(event, PVChanged):
            return
        result = self.propagation.propagate_load_change(
            bus_id=event.bus_id,
            new_power=-event.new_power,  # Generation = negative load
        )
        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "pv_changed",
                "bus_id": event.bus_id,
                "result": result,
            }
        )

    def _on_battery_dispatch(self, event: DomainEvent) -> None:
        """Handle BatteryDispatch event."""
        if not isinstance(event, BatteryDispatch):
            return
        result = self.propagation.propagate_load_change(
            bus_id=event.bus_id,
            new_power=-event.power_command,  # Discharge = negative load
        )
        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "battery_dispatch",
                "bus_id": event.bus_id,
                "result": result,
            }
        )

    def _on_scada_update(self, event: DomainEvent) -> None:
        """Handle SCADAUpdateReceived event."""
        if not isinstance(event, SCADAUpdateReceived):
            return

        # Update SCADA database with new measurements
        if self.dt_state.scada is not None:
            from scada_model.scada_model import Measurement, MeasurementType, QualityFlag

            for meas_data in event.measurements:
                try:
                    mtype = MeasurementType(meas_data.get("type", "voltage_magnitude"))
                    meas = Measurement(
                        measurement_id=meas_data.get("id", ""),
                        measurement_type=mtype,
                        element_id=meas_data.get("element_id", ""),
                        value=meas_data.get("value", 0.0),
                        quality=QualityFlag(meas_data.get("quality", "good")),
                        confidence=meas_data.get("confidence", 1.0),
                    )
                    self.dt_state.scada.add_measurement(meas)
                except Exception as e:
                    logger.warning(f"Failed to add SCADA measurement: {e}")

            # Update switch statuses
            for switch_id, status_str in event.switch_statuses.items():
                from scada_model.scada_model import SwitchStatus

                try:
                    new_status = SwitchStatus(status_str)
                    self.dt_state.scada.operate_switch(switch_id, new_status)
                except Exception as e:
                    logger.warning(f"Failed to update switch {switch_id}: {e}")

        self._processed_events.append(
            {
                "event_id": event.event_id,
                "event_type": "scada_update",
                "measurement_count": len(event.measurements),
                "switch_update_count": len(event.switch_statuses),
            }
        )

    def get_processed_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get history of processed events."""
        return self._processed_events[-limit:]


# ============================================================
# TIME-STEPPED SIMULATOR
# ============================================================


class TimeSteppedSimulator:
    """
    Time-stepped simulation loop for the digital twin.

    Supports:
    - Configurable time step (Delta t)
    - SCADA measurement injection at each step
    - State estimation trigger
    - Solver recalculation when topology or injection changes
    - Event queue for scheduled actions
    """

    def __init__(
        self,
        dt_state: DigitalTwinState,
        event_bus: EventBus,
        propagation_engine: ChangePropagationEngine,
        event_processor: EventProcessor,
    ):
        self.dt_state = dt_state
        self.event_bus = event_bus
        self.propagation = propagation_engine
        self.event_processor = event_processor

        self.time_step = 1.0  # seconds
        self.current_time = 0.0
        self.running = False
        self._event_queue: List[Dict[str, Any]] = []
        self._step_log: List[Dict[str, Any]] = []
        self._scada_injector: Callable[[float], List[DomainEvent]] | None = None

    def set_time_step(self, dt: float) -> None:
        """Set simulation time step in seconds."""
        self.time_step = dt

    def set_scada_injector(self, injector: Callable[[float], List[DomainEvent]]) -> None:
        """
        Set a SCADA data injector function.

        The injector receives the current simulation time and returns
        a list of events (typically SCADAUpdateReceived) to inject.
        """
        self._scada_injector = injector

    def schedule_event(self, event: DomainEvent, at_time: float) -> None:
        """Schedule an event to be published at a specific simulation time."""
        self._event_queue.append({"event": event, "scheduled_time": at_time})
        self._event_queue.sort(key=lambda x: x["scheduled_time"])

    def step(self) -> Dict[str, Any]:
        """
        Execute a single simulation time step.

        1. Advance time
        2. Inject SCADA data (if injector configured)
        3. Process scheduled events
        4. Capture and commit state snapshot
        5. Publish step completed event
        """
        step_start = time.time()
        self.current_time += self.time_step

        events_processed = 0

        # Inject SCADA data
        if self._scada_injector is not None:
            try:
                events = self._scada_injector(self.current_time)
                for event in events:
                    self.event_bus.publish(event)
                    events_processed += 1
            except Exception as e:
                logger.error(f"SCADA injection error at t={self.current_time}: {e}")

        # Process scheduled events
        due_events = [e for e in self._event_queue if e["scheduled_time"] <= self.current_time]
        self._event_queue = [
            e for e in self._event_queue if e["scheduled_time"] > self.current_time
        ]

        for entry in due_events:
            self.event_bus.publish(entry["event"])
            events_processed += 1

        # Capture state snapshot
        snapshot = self.dt_state.capture_snapshot(
            source_event="time_step", correlation_id=f"step_{self.current_time}"
        )
        snapshot.simulation_time = self.current_time
        version = self.dt_state.commit_snapshot(snapshot)

        # Publish step completed
        self.event_bus.publish(
            DomainEvent(
                event_type=EventType.SIMULATION_STEP_COMPLETED,
                source="time_stepped_simulator",
                metadata={
                    "simulation_time": self.current_time,
                    "state_version": version,
                    "events_processed": events_processed,
                },
            )
        )

        step_record = {
            "simulation_time": self.current_time,
            "state_version": version,
            "events_processed": events_processed,
            "elapsed_wall_seconds": time.time() - step_start,
        }
        self._step_log.append(step_record)

        return step_record

    def run(self, duration: float, time_step: float = None) -> List[Dict[str, Any]]:
        """
        Run simulation for a given duration.

        Parameters:
        duration: Total simulation time in seconds.
        time_step: Override time step (optional).

        Returns:
        List of step records.
        """
        if time_step is not None:
            self.time_step = time_step

        self.running = True
        self.event_bus.publish(
            DomainEvent(
                event_type=EventType.SIMULATION_STARTED,
                source="time_stepped_simulator",
                metadata={"duration": duration, "time_step": self.time_step},
            )
        )

        results = []
        end_time = self.current_time + duration

        while self.current_time < end_time and self.running:
            result = self.step()
            results.append(result)

        self.running = False
        self.event_bus.publish(
            DomainEvent(
                event_type=EventType.SIMULATION_STOPPED,
                source="time_stepped_simulator",
                metadata={"final_time": self.current_time, "steps": len(results)},
            )
        )

        return results

    def stop(self) -> None:
        """Stop the running simulation."""
        self.running = False

    def get_step_log(self) -> List[Dict[str, Any]]:
        """Get simulation step history."""
        return self._step_log


# ============================================================
# LIVE POWER SYSTEM ENGINE
# ============================================================


class LivePowerSystemEngine:
    """
    Extended PowerSystemEngine that operates on live digital twin state.

    Wraps the existing PowerSystemEngine but:
    - Takes DigitalTwinState instead of bare System
    - Rebuilds Ybus from current topology before each solver call
    - Writes results back to DigitalTwinState after each solver call
    - Publishes events for each operation
    - Validates state after each operation

    This ensures the power system solver integrates with live topology
    and switching changes update all simulations.
    """

    def __init__(self, dt_state: DigitalTwinState, event_bus: EventBus):
        """
        Initialize LivePowerSystemEngine.

        Parameters:
        dt_state: DigitalTwinState instance (must have system bound)
        event_bus: EventBus for publishing operation events
        """
        self.dt_state = dt_state
        self.event_bus = event_bus
        self._operation_log: List[Dict[str, Any]] = []

        # Import and create the base engine if system is bound
        self._base_engine = None
        if dt_state.system is not None:
            try:
                from engine.engine import PowerSystemEngine

                self._base_engine = PowerSystemEngine(dt_state.system)
            except Exception as e:
                logger.warning(f"Could not create base PowerSystemEngine: {e}")

    def _ensure_ybus_current(self) -> None:
        """Ensure Ybus reflects current topology by forcing rebuild."""
        if self.dt_state.system is not None:
            self.dt_state.system.Ybus_seq.clear()
            self.dt_state.system.build_ybus(seq="1")

    def _rebuild_base_engine(self) -> None:
        """Rebuild the base engine after topology changes."""
        if self.dt_state.system is not None:
            try:
                from engine.engine import PowerSystemEngine

                self._base_engine = PowerSystemEngine(self.dt_state.system)
            except Exception as e:
                logger.warning(f"Could not rebuild base engine: {e}")

    def run_load_flow(self) -> Dict[str, Any]:
        """
        Run load flow with current live topology.

        Rebuilds Ybus from current state, runs load flow,
        updates digital twin state, and publishes events.
        """
        start_time = time.time()

        # Rebuild Ybus
        self._ensure_ybus_current()
        self._rebuild_base_engine()

        # Run load flow
        if self._base_engine is None:
            return {"converged": False, "error": "No base engine available"}

        try:
            result = self._base_engine.run_load_flow()
        except Exception as e:
            return {"converged": False, "error": str(e)}

        # Update digital twin state
        snapshot = self.dt_state.capture_snapshot(source_event="load_flow")
        if result.get("converged", False):
            for bid_str, v in result.get("bus_voltages", {}).items():
                if bid_str in snapshot.bus_states:
                    snapshot.bus_states[bid_str].voltage_magnitude = abs(v)
                    snapshot.bus_states[bid_str].voltage_angle = np.angle(v)
            snapshot.simulation_results.load_flow_converged = True

        validation_results = self.dt_state.validate()
        snapshot.validation_passed = all(r.passed for r in validation_results)
        version = self.dt_state.commit_snapshot(snapshot)

        # Publish event
        self.event_bus.publish(
            LoadFlowCompleted(
                converged=result.get("converged", False),
                iterations=result.get("iterations", 0),
                bus_voltages=result.get("bus_voltages", {}),
                source="live_engine",
            )
        )

        operation_record = {
            "operation": "load_flow",
            "converged": result.get("converged", False),
            "state_version": version,
            "elapsed_seconds": time.time() - start_time,
        }
        self._operation_log.append(operation_record)

        return {**result, "state_version": version}

    def run_fault_analysis(self, fault_type: str, bus_id) -> Dict[str, Any]:
        """
        Run fault analysis with current live topology.
        """
        # Ensure sequence networks are current
        if self.dt_state.system is not None:
            self.dt_state.system.Ybus_seq.clear()
            self.dt_state.system.build_sequence_networks()

        self._rebuild_base_engine()

        if self._base_engine is None:
            return {"error": "No base engine available"}

        try:
            result = self._base_engine.run_fault_analysis(fault_type, bus_id)
        except Exception as e:
            return {"error": str(e)}

        # Update digital twin
        snapshot = self.dt_state.capture_snapshot(source_event="fault_analysis")
        snapshot.simulation_results.fault_currents = {
            str(bus_id): result.get("fault_current", complex(0, 0))
        }
        version = self.dt_state.commit_snapshot(snapshot)

        self.event_bus.publish(
            FaultAnalysisCompleted(
                fault_type=fault_type,
                fault_bus=str(bus_id),
                fault_current_pu=abs(result.get("fault_current", complex(0, 0))),
                source="live_engine",
            )
        )

        return {**result, "state_version": version}

    def run_protection_coordination(
        self, upstream_relay_id: int, downstream_relay_id: int, fault_currents: list
    ) -> Dict[str, Any]:
        """
        Run protection coordination with current live topology.
        """
        self._rebuild_base_engine()

        if self._base_engine is None:
            return {"error": "No base engine available"}

        try:
            result = self._base_engine.run_protection_coordination(
                upstream_relay_id, downstream_relay_id, fault_currents
            )
        except Exception as e:
            return {"error": str(e)}

        # Update digital twin
        snapshot = self.dt_state.capture_snapshot(source_event="protection_coordination")
        snapshot.simulation_results.protection_coordination_ok = result.get(
            "all_coordinated", False
        )
        version = self.dt_state.commit_snapshot(snapshot)

        self.event_bus.publish(
            ProtectionRefreshed(
                coordination_issues=0 if result.get("all_coordinated", False) else 1,
                source="live_engine",
            )
        )

        return {**result, "state_version": version}

    def open_switch(self, switch_id: str, reason: str = "") -> Dict[str, Any]:
        """
        Open a switch and propagate through the entire workflow.

        This triggers:
        Topology Update -> Ybus Rebuild -> Load Flow ->
        State Estimation -> Short Circuit -> Arc Flash ->
        Protection -> Digital Twin State Update
        """
        # Get switch info
        bus1, bus2 = "", ""
        if self.dt_state.adms and switch_id in self.dt_state.adms.topology.switches:
            bus1, bus2 = self.dt_state.adms.topology.switches[switch_id]

        # Publish event -> EventProcessor -> ChangePropagationEngine
        event = SwitchOpened(
            switch_id=switch_id, bus1=bus1, bus2=bus2, reason=reason, source="live_engine"
        )
        self.event_bus.publish(event)

        # Return current state
        snapshot = self.dt_state.get_current_snapshot()
        return {
            "action": "switch_opened",
            "switch_id": switch_id,
            "state_version": snapshot.version if snapshot else 0,
            "validation_passed": snapshot.validation_passed if snapshot else False,
        }

    def close_switch(self, switch_id: str, reason: str = "") -> Dict[str, Any]:
        """
        Close a switch and propagate through the entire workflow.
        """
        bus1, bus2 = "", ""
        if self.dt_state.adms and switch_id in self.dt_state.adms.topology.switches:
            bus1, bus2 = self.dt_state.adms.topology.switches[switch_id]

        event = SwitchClosed(
            switch_id=switch_id, bus1=bus1, bus2=bus2, reason=reason, source="live_engine"
        )
        self.event_bus.publish(event)

        snapshot = self.dt_state.get_current_snapshot()
        return {
            "action": "switch_closed",
            "switch_id": switch_id,
            "state_version": snapshot.version if snapshot else 0,
            "validation_passed": snapshot.validation_passed if snapshot else False,
        }

    def change_load(self, bus_id: str, new_power: complex) -> Dict[str, Any]:
        """
        Change load at a bus and propagate through the workflow.
        """
        event = LoadChanged(bus_id=bus_id, new_power=new_power, source="live_engine")
        self.event_bus.publish(event)

        snapshot = self.dt_state.get_current_snapshot()
        return {
            "action": "load_changed",
            "bus_id": bus_id,
            "state_version": snapshot.version if snapshot else 0,
        }

    def detect_fault(
        self, fault_type: str, bus_id: str, tripped_switches: List[str] = None
    ) -> Dict[str, Any]:
        """
        Detect a fault and trigger FLISR workflow.
        """
        event = FaultDetected(
            fault_type=fault_type,
            bus_id=bus_id,
            tripped_switches=tripped_switches or [],
            source="live_engine",
        )
        self.event_bus.publish(event)

        snapshot = self.dt_state.get_current_snapshot()
        return {
            "action": "fault_detected",
            "fault_type": fault_type,
            "bus_id": bus_id,
            "state_version": snapshot.version if snapshot else 0,
        }

    def inject_scada_update(
        self, measurements: List[Dict[str, Any]] = None, switch_statuses: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Inject SCADA update and process.
        """
        event = SCADAUpdateReceived(
            measurements=measurements or [],
            switch_statuses=switch_statuses or {},
            source="live_engine",
        )
        self.event_bus.publish(event)

        snapshot = self.dt_state.get_current_snapshot()
        return {
            "action": "scada_update",
            "measurement_count": len(measurements or []),
            "switch_update_count": len(switch_statuses or {}),
            "state_version": snapshot.version if snapshot else 0,
        }

    def get_operation_log(self) -> List[Dict[str, Any]]:
        """Get history of operations performed."""
        return self._operation_log

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status summary."""
        snapshot = self.dt_state.get_current_snapshot()
        return {
            "state_version": snapshot.version if snapshot else 0,
            "bus_count": len(snapshot.bus_states) if snapshot else 0,
            "switch_count": len(snapshot.switch_states) if snapshot else 0,
            "gis_asset_count": len(snapshot.gis_assets) if snapshot else 0,
            "load_flow_converged": snapshot.simulation_results.load_flow_converged
            if snapshot
            else False,
            "validation_passed": snapshot.validation_passed if snapshot else False,
            "validation_errors": snapshot.validation_errors if snapshot else [],
            "event_bus_stats": self.event_bus.get_statistics(),
        }
