"""
Chain of Responsibility — Change Propagation Handlers
=====================================================

Decomposes the monolithic ``propagate_switch_change`` method into discrete,
composable handler classes.  Each handler is responsible for one step in the
propagation workflow:

    Topology Update → Ybus Rebuild → Load Flow → State Estimation →
    Short Circuit Refresh → Arc Flash Refresh → Protection Refresh →
    Digital Twin State Update

Adding or removing steps now requires only defining a new handler class and
registering it in the chain — no changes to the propagation method itself.

Usage::

    chain = PropagationChain(handlers=[
        TopologyUpdateHandler(),
        YbusRebuildHandler(),
        LoadFlowHandler(),
        ...
    ])
    result = chain.execute(context)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Propagation Context
# ============================================================================


@dataclass
class PropagationContext:
    """Carries state through the handler chain.

    Each handler reads from and writes to this context.  If ``stop`` is set
    to ``True`` by any handler, the chain halts immediately and subsequent
    handlers are skipped.
    """

    # --- Trigger info ---
    propagation_id: str = ""
    trigger_type: str = ""  # e.g. "switch_change", "load_change"
    switch_id: str = ""
    is_opening: bool = True
    reason: str = ""
    bus_id: str = ""
    new_power: complex = complex(0, 0)

    # --- Runtime state ---
    dt_state: Any = None
    event_bus: Any = None
    sync_engine: Any = None
    validation_gateway: Any = None
    load_flow_solver: Any = None
    state_estimator: Any = None

    # --- Accumulated results ---
    steps: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    stop: bool = False  # Set to True to abort the chain
    start_time: float = field(default_factory=time.time)
    elapsed_seconds: float = 0.0

    # --- Short-circuit cache (set by YbusRebuildHandler, read by LoadFlowHandler etc.) ---
    ybus_sequences: dict[str, Any] = field(default_factory=dict)

    def record_step(
        self, step_name: str, step_success: bool, details: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append(
            {
                "step": step_name,
                "success": step_success,
                "timestamp": time.time(),
                "details": details or {},
            },
        )
        if not step_success:
            self.success = False


# ============================================================================
# Base Handler
# ============================================================================


class PropagationHandler(ABC):
    """Abstract base for a single step in the change-propagation chain."""

    # Non-fatal steps continue the chain even on failure; fatal steps halt it.
    fatal: bool = False

    @abstractmethod
    def handle(self, ctx: PropagationContext) -> PropagationContext:
        """Execute this handler's step and return the (possibly mutated) context.

        To signal a failure::

            ctx.record_step("my_step", False, {"error": str(e)})
            if self.fatal:
                ctx.stop = True

        To halt the chain unconditionally::

            ctx.stop = True

        Return ``ctx`` so the next handler can receive it.
        """
        ...


# ============================================================================
# Concrete Handlers
# ============================================================================


class TopologyUpdateHandler(PropagationHandler):
    """Step 1 — Apply switch state change to the ADMS topology."""

    fatal = True  # Topology must succeed — everything else depends on it

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        try:
            if ctx.dt_state is not None and ctx.dt_state.adms is not None:
                if ctx.is_opening:
                    ctx.dt_state.adms.topology.open_switch(ctx.switch_id)
                else:
                    ctx.dt_state.adms.topology.close_switch(ctx.switch_id)
                ctx.dt_state.adms.topology.identify_sections()

            ctx.record_step(
                "topology_update", True, {"switch_id": ctx.switch_id, "opened": ctx.is_opening},
            )

            if ctx.event_bus is not None:
                from .event_bus import TopologyChanged

                ctx.event_bus.publish(
                    TopologyChanged(
                        change_description=(
                            f"Switch {ctx.switch_id} {'opened' if ctx.is_opening else 'closed'}"
                        ),
                        affected_switches=[ctx.switch_id],
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            ctx.record_step("topology_update", False, {"error": str(e)})
            ctx.stop = True
        return ctx


class YbusRebuildHandler(PropagationHandler):
    """Step 2 — Invalidate and rebuild the Ybus matrix."""

    fatal = True  # Ybus must succeed — load flow needs it

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        try:
            if ctx.dt_state is not None and ctx.dt_state.system is not None:
                ctx.dt_state.system.Ybus_seq.clear()
                Y = ctx.dt_state.system.build_ybus(seq="1")
                ctx.record_step("ybus_rebuild", True, {"matrix_size": Y.shape[0]})
                if ctx.event_bus is not None:
                    from .event_bus import YbusRebuilt

                    ctx.event_bus.publish(
                        YbusRebuilt(
                            matrix_size=Y.shape[0],
                            sequences_rebuilt=["1"],
                            source="change_propagation",
                            correlation_id=ctx.propagation_id,
                        ),
                    )
            else:
                ctx.record_step("ybus_rebuild", False, {"error": "No electrical model bound"})  # NOSONAR — S1192: intentional repetition (audit constant)
                ctx.stop = True
        except Exception as e:
            ctx.record_step("ybus_rebuild", False, {"error": str(e)})
            ctx.stop = True
        return ctx


class LoadFlowHandler(PropagationHandler):
    """Step 3 — Run load flow on the current topology."""

    fatal = True  # Load flow convergence gates downstream studies

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        if ctx.dt_state is None or ctx.dt_state.system is None:
            ctx.record_step("load_flow", False, {"error": "No system bound"})
            ctx.stop = True
            return ctx

        try:
            from load_flow.load_flow import LoadFlowSolver

            solver = (
                ctx.load_flow_solver
                if ctx.load_flow_solver is not None
                else LoadFlowSolver(ctx.dt_state.system)
            )
            converged = solver.solve(max_iter=100, tol=1e-6)

            bus_voltages = {}
            for bid in solver.bus_ids:
                bus_voltages[str(bid)] = solver.V[solver.bus_index[bid]]

            result = {
                "converged": converged,
                "iterations": len(solver.iteration_log) if hasattr(solver, "iteration_log") else 0,
                "bus_voltages": bus_voltages,
            }
            ctx.record_step("load_flow", converged, result)

            if ctx.event_bus is not None:
                from .event_bus import LoadFlowCompleted

                ctx.event_bus.publish(
                    LoadFlowCompleted(
                        converged=converged,
                        iterations=result["iterations"],
                        bus_voltages=bus_voltages,
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )

            if not converged:
                ctx.stop = True
        except Exception as e:
            ctx.record_step("load_flow", False, {"error": str(e)})
            ctx.stop = True
        return ctx


class StateEstimationHandler(PropagationHandler):
    """Step 4 — Validate state estimation after load flow."""

    fatal = False  # State-estimation failure is non-fatal

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        if ctx.dt_state is None or ctx.dt_state.system is None or ctx.dt_state.scada is None:
            ctx.record_step(
                "state_estimation",
                True,
                {"status": "skipped", "reason": "System or SCADA not bound"},
            )
            return ctx

        try:
            from scada_model.state_estimation import WLSEstimator

            estimator = ctx.state_estimator if ctx.state_estimator is not None else WLSEstimator()
            bus_ids = sorted(ctx.dt_state.system.buses.keys())

            measurements: dict[str, Any] = {
                "voltage_mag": {},
                "power_injection": {},
                "power_flow": {},
            }
            for i, bid in enumerate(bus_ids):
                vmag = ctx.dt_state.scada.get_latest_voltage(str(bid))
                if vmag is not None:
                    measurements["voltage_mag"][i] = (vmag, 0.01)
                pq = ctx.dt_state.scada.get_latest_power(str(bid))
                if pq is not None:
                    measurements["power_injection"][i] = (pq[0], pq[1], 0.02, 0.02)

            Ybus = ctx.dt_state.system.get_ybus(seq="1")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            result = estimator.estimate(Ybus, measurements, [str(bid) for bid in bus_ids])

            ctx.record_step(
                "state_estimation",
                result.status.value == "converged",
                {
                    "bad_data_count": len(result.bad_data_detected),
                    "max_residual": result.max_residual,
                },
            )

            if ctx.event_bus is not None:
                from .event_bus import StateEstimationCompleted

                ctx.event_bus.publish(
                    StateEstimationCompleted(
                        converged=result.status.value == "converged",
                        bad_data_count=len(result.bad_data_detected),
                        max_residual=result.max_residual,
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            logger.warning("State estimation failed (non-fatal): %s", e)
            ctx.record_step("state_estimation", False, {"error": str(e)})
        return ctx


class ShortCircuitRefreshHandler(PropagationHandler):
    """Step 5 — Rebuild sequence networks for short-circuit analysis."""

    fatal = False

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        if ctx.dt_state is None or ctx.dt_state.system is None:
            ctx.record_step(
                "short_circuit_refresh", True, {"status": "skipped", "reason": "No system bound"},
            )
            return ctx
        try:
            ctx.dt_state.system.build_sequence_networks()
            ctx.record_step(
                "short_circuit_refresh", True, {"status": "refreshed", "sequences_built": True},
            )
            if ctx.event_bus is not None:
                from .event_bus import FaultAnalysisCompleted

                ctx.event_bus.publish(
                    FaultAnalysisCompleted(
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            logger.warning("Short-circuit refresh failed (non-fatal): %s", e)
            ctx.record_step("short_circuit_refresh", False, {"error": str(e)})
        return ctx


class ArcFlashRefreshHandler(PropagationHandler):
    """Step 6 — Refresh arc flash analysis using current fault currents.

    Delegates all IEEE 1584-2018 calculations to the real
    ``fault_analysis.ArcFlashEngine`` so that the digital-twin arc flash
    numbers are guaranteed to match what ``PowerSystemEngine.run_arc_flash()``
    returns (single-source-of-truth for the IEEE 1584 coefficients).
    """

    fatal = False

    def handle(self, ctx: PropagationContext) -> PropagationContext:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        if ctx.dt_state is None or ctx.dt_state.system is None:
            ctx.record_step(
                "arc_flash_refresh",
                True,
                {"status": "skipped", "reason": "No electrical model bound"},
            )
            return ctx
        try:
            from fault_analysis.arc_flash_engine import (
                ArcFlashEngine,
                ElectrodeConfig,
                EnclosureType,
            )
            from fault_analysis.fault import FaultAnalyzer

            ctx.dt_state.system.build_sequence_networks(for_fault=True)
            Ybus_pos = ctx.dt_state.system.get_ybus(seq="1")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Ybus_neg = ctx.dt_state.system.get_ybus(seq="2")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Ybus_zero = ctx.dt_state.system.get_ybus(seq="0")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

            analyzer = FaultAnalyzer(
                Ybus_pos, Ybus_neg, Ybus_zero, base_mva=ctx.dt_state.system.base_mva,
            )

            af_engine = ArcFlashEngine()
            results: dict[str, Any] = {}
            bus_ids = sorted(ctx.dt_state.system.buses.keys())
            bus_index = {bid: idx for idx, bid in enumerate(ctx.dt_state.system.buses.keys())}
            system_base_kv = getattr(ctx.dt_state.system, "base_kv", None) or 115.0  # kV

            for bus_id in bus_ids:
                bus_idx = bus_index[bus_id]
                fault = analyzer.three_phase_fault(bus_idx)
                fault_ka = fault.get("fault_current_ka", 0.0)

                if fault_ka <= 0:
                    continue

                # Compute the bus voltage in kV.  bus.voltage is in per-unit,
                # system.base_kv is the system-wide kV base (e.g. 115 kV).
                bus = ctx.dt_state.system.buses.get(bus_id)
                bus_kv = abs(bus.voltage) * system_base_kv if bus is not None else system_base_kv

                # IEEE 1584-2018 valid range: 0.208–15 kV.
                # Buses above 15 kV (transmission) use Ralph Lee fallback.
                # Buses below 0.208 kV also use Ralph Lee.
                use_ieee = 0.208 <= bus_kv <= 15.0

                arc_duration = 0.2  # 200 ms typical clearing time
                working_distance_mm = 610.0  # 24 inches

                if use_ieee:
                    try:
                        result = af_engine.calculate(
                            voltage_kv=bus_kv,
                            bolted_fault_current_ka=fault_ka,
                            arc_duration_sec=arc_duration,
                            working_distance_mm=working_distance_mm,
                            electrode_config=ElectrodeConfig.VCB,
                            enclosure_type=EnclosureType.BOX,
                        )
                        results[str(bus_id)] = {
                            "incident_energy_cal_cm2": result.incident_energy_cal_cm2,
                            "incident_energy_at_full_arc_current": result.incident_energy_at_full_arc_current,
                            "incident_energy_at_reduced_arc_current": result.incident_energy_at_reduced_arc_current,
                            "arc_flash_boundary_mm": result.arc_flash_boundary_mm,
                            "arc_flash_boundary_in": result.arc_flash_boundary_in,
                            "arc_current_ka": result.arc_current_ka,
                            "reduced_arc_current_ka": result.reduced_arc_current_ka,
                            "ppe_level": result.ppe_level,
                            "ppe_description": result.ppe_description,
                            "method": result.method,
                            "fault_current_ka": round(fault_ka, 4),
                        }
                        continue
                    except ValueError:
                        # IEEE validation range check failed (shouldn't happen
                        # since we already checked 0.208–15.0, but handle it)
                        pass

                # Fallback: Ralph Lee method for out-of-range voltages
                try:
                    lee_result = af_engine.ralph_lee_method(
                        voltage_kv=bus_kv,
                        bolted_fault_current_ka=fault_ka,
                        arc_duration_sec=arc_duration,
                        working_distance_mm=working_distance_mm,
                    )
                    results[str(bus_id)] = {
                        "incident_energy_cal_cm2": lee_result.incident_energy_cal_cm2,
                        "arc_flash_boundary_mm": lee_result.arc_flash_boundary_mm,
                        "arc_flash_boundary_in": lee_result.arc_flash_boundary_in,
                        "ppe_level": lee_result.ppe_level,
                        "ppe_description": lee_result.ppe_description,
                        "method": lee_result.method,
                        "fault_current_ka": round(fault_ka, 4),
                    }
                except Exception as lee_err:
                    logger.warning(
                        "Ralph Lee fallback failed for bus %s: %s",
                        bus_id,
                        lee_err,
                    )

            ctx.record_step(
                "arc_flash_refresh",
                True,
                {
                    "bus_count": len(results),
                    "buses_skipped": len(bus_ids) - len(results),
                }
                if results
                else {
                    "status": "skipped",
                    "reason": "No buses with valid fault current",
                },
            )
            if ctx.event_bus is not None:
                from .event_bus import ArcFlashRefreshed

                ctx.event_bus.publish(
                    ArcFlashRefreshed(
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            logger.warning("Arc flash refresh failed (non-fatal): %s", e)
            ctx.record_step("arc_flash_refresh", False, {"error": str(e)})
        return ctx


class ProtectionRefreshHandler(PropagationHandler):
    """Step 7 — Refresh protection coordination using fault-current data."""

    fatal = False

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        if ctx.dt_state is None or ctx.dt_state.system is None:
            ctx.record_step(
                "protection_refresh",
                True,
                {"status": "skipped", "reason": "No electrical model bound"},
            )
            return ctx
        try:
            from coordination.coordination import CoordinationEngine
            from fault_analysis.fault import FaultAnalyzer
            from relays.relay import OvercurrentRelay

            ctx.dt_state.system.build_sequence_networks(for_fault=True)
            Ybus_pos = ctx.dt_state.system.get_ybus(seq="1")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Ybus_neg = ctx.dt_state.system.get_ybus(seq="2")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Ybus_zero = ctx.dt_state.system.get_ybus(seq="0")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

            analyzer = FaultAnalyzer(
                Ybus_pos, Ybus_neg, Ybus_zero, base_mva=ctx.dt_state.system.base_mva,
            )

            fault_currents: list[float] = []
            bus_ids = sorted(ctx.dt_state.system.buses.keys())
            bus_index = {bid: idx for idx, bid in enumerate(ctx.dt_state.system.buses.keys())}
            for bus_id in bus_ids:
                bus_idx = bus_index[bus_id]
                fault = analyzer.three_phase_fault(bus_idx)
                fc_pu = abs(fault.get("fault_current", complex(0, 0)))
                if fc_pu > 0:
                    fault_currents.append(fc_pu)

            representative_faults = sorted({round(fc, 0) for fc in fault_currents if fc > 1.0})[:10]
            if not representative_faults:
                representative_faults = [2.0, 5.0, 10.0, 20.0]

            coord_engine = CoordinationEngine()
            relay1 = OvercurrentRelay(relay_id=1, name="Upstream", TMS=0.5, Ip=1.0)
            relay2 = OvercurrentRelay(relay_id=2, name="Downstream", TMS=0.2, Ip=1.0)

            coord_results = coord_engine.check_coordination_range(
                relay1, relay2, representative_faults,
            )
            all_coordinated = all(r["coordinated"] for r in coord_results)
            min_margin = min(r["margin"] for r in coord_results) if coord_results else 0.0

            ctx.record_step(
                "protection_refresh",
                True,
                {
                    "all_coordinated": all_coordinated,
                    "min_margin_sec": round(min_margin, 4),
                    "fault_levels_checked": len(representative_faults),
                },
            )
            if ctx.event_bus is not None:
                from .event_bus import ProtectionRefreshed

                ctx.event_bus.publish(
                    ProtectionRefreshed(
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            logger.warning("Protection refresh failed (non-fatal): %s", e)
            ctx.record_step("protection_refresh", False, {"error": str(e)})
        return ctx


class DigitalTwinUpdateHandler(PropagationHandler):
    """Step 8 — Capture snapshot, validate, and commit state."""

    fatal = False

    def handle(self, ctx: PropagationContext) -> PropagationContext:
        if ctx.dt_state is None:
            ctx.record_step("digital_twin_update", False, {"error": "DigitalTwinState not bound"})
            return ctx
        try:
            snapshot = ctx.dt_state.capture_snapshot(
                source_event=f"switch_{'opened' if ctx.is_opening else 'closed'}",
                correlation_id=ctx.propagation_id,
            )
            validation_results = ctx.dt_state.validate()
            snapshot.validation_passed = all(r.passed for r in validation_results)
            snapshot.validation_errors = [r.message for r in validation_results if not r.passed]

            if ctx.dt_state.system is not None and ctx.load_flow_solver is not None:
                # NOSONAR — python:S7504: list() is intentional — creates a
                # snapshot so we can mutate snapshot.bus_states during iteration.
                for bid_str in list(snapshot.bus_states.keys()):
                    try:
                        bid_int = int(bid_str)
                    except (ValueError, TypeError):
                        continue
                    bus = ctx.dt_state.system.buses.get(bid_int)
                    if bus is not None:
                        snapshot.simulation_results.load_flow_bus_voltages[bid_str] = bus.voltage

            version = ctx.dt_state.commit_snapshot(snapshot)
            ctx.record_step("digital_twin_update", True, {"version": version})

            if ctx.event_bus is not None:
                from .event_bus import DigitalTwinStateUpdated

                ctx.event_bus.publish(
                    DigitalTwinStateUpdated(
                        state_version=version,
                        layers_synchronized=snapshot.validation_passed,
                        validation_passed=snapshot.validation_passed,
                        source="change_propagation",
                        correlation_id=ctx.propagation_id,
                    ),
                )
        except Exception as e:
            ctx.record_step("digital_twin_update", False, {"error": str(e)})
        return ctx


# ============================================================================
# Chain
# ============================================================================


class PropagationChain:
    """Composite that runs a sequence of ``PropagationHandler`` instances.

    The chain stops early if any handler sets ``ctx.stop = True``.
    After all handlers run (or the chain is halted), the elapsed time is
    recorded and a ``ValidationErrorEvent`` is published if any step failed.
    """

    def __init__(self, handlers: list[PropagationHandler] | None = None):
        self.handlers = list(handlers) if handlers is not None else list(_DEFAULT_HANDLERS)

    def execute(self, ctx: PropagationContext) -> PropagationContext:
        """Run the handler chain sequentially."""
        for handler in self.handlers:
            if ctx.stop:
                break
            ctx = handler.handle(ctx)

        ctx.elapsed_seconds = time.time() - ctx.start_time

        # Publish validation error event on failure
        if not ctx.success and ctx.event_bus is not None:
            from .event_bus import ValidationErrorEvent

            errors = [
                s["details"].get("error", "Unknown error") for s in ctx.steps if not s["success"]
            ]
            ctx.event_bus.publish(
                ValidationErrorEvent(
                    errors=errors,
                    layer="propagation",
                    source="change_propagation",
                    correlation_id=ctx.propagation_id,
                ),
            )

        return ctx


# ============================================================================
# Default chain — used by ChangePropagationEngine when no custom chain given
# ============================================================================

_DEFAULT_HANDLERS: list[PropagationHandler] = [
    TopologyUpdateHandler(),
    YbusRebuildHandler(),
    LoadFlowHandler(),
    StateEstimationHandler(),
    ShortCircuitRefreshHandler(),
    ArcFlashRefreshHandler(),
    ProtectionRefreshHandler(),
    DigitalTwinUpdateHandler(),
]
