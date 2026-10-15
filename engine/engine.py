from __future__ import annotations

import math
from typing import Any, Callable, Dict, Tuple

import numpy as np

from coordination.coordination import CoordinationEngine
from core_model.system import System
from engine.interfaces import (
    ArcFlashEngineProtocol,
    CoordinationEngineProtocol,
    LoadFlowSolverProtocol,
    VisualizerProtocol,
)
from fault_analysis.arc_flash_engine import ArcFlashEngine, ElectrodeConfig, EnclosureType
from fault_analysis.fault import FaultAnalyzer
from load_flow.load_flow import LoadFlowSolver
from relays.relay import OvercurrentRelay
from visualization.visualization import Visualizer

# ---------------------------------------------------------------------------
# Internal study registry
# ---------------------------------------------------------------------------
# ``run_study`` is a thin JSON adapter at the external seam (HTTP API, MCP,
# AI agents, CLI, automation). It dispatches on ``study_type`` via this
# module-private registry and delegates to the typed study methods. The
# registry is an internal implementation detail and is NOT exported from
# ``engine/__init__.py``.
#
# Each entry maps a ``study_type`` string to a ``_StudySpec``:
# ``(required_kwargs, method_name)``.
#
#   - ``required_kwargs`` is the tuple of keyword names that must be present
#     in ``kwargs`` for that study type (mirroring the current inline
#     validation).
#   - ``method_name`` is the string name of the bound typed method to call
#     (e.g. ``"run_arc_flash"``), resolved via ``getattr(self, method_name)``
#     at call time to avoid module-level binding to ``self``.
#
# This is the single source of truth for the one-to-one study_type to
# typed-method mapping.

# NOTE: These aliases are evaluated at runtime (they are module-level
# assignments, not annotations), so they must use ``typing.Dict``/``typing.Tuple``
# rather than PEP 585 builtin generics (``dict[...]``/``tuple[...]``), which are
# only subscriptable at runtime on Python 3.9+. The project supports Python 3.8
# at runtime (see the CI/worker images), so runtime-safe generics are required.
_StudyHandler = Callable[..., Dict[str, Any]]
_StudySpec = Tuple[Tuple[str, ...], str]

_STUDY_REGISTRY: Dict[str, _StudySpec] = {
    "load_flow": ((), "run_load_flow"),
    "short_circuit": (("bus_id",), "run_fault_analysis"),
    "protection_coordination": (
        ("upstream_relay_id", "downstream_relay_id", "fault_currents"),
        "run_protection_coordination",
    ),
    "arc_flash": (
        ("voltage_kv", "bolted_fault_current_ka", "arc_duration_sec", "working_distance_mm"),
        "run_arc_flash",
    ),
}


def _validate_study_kwargs(
    required: tuple[str, ...], kwargs: dict[str, Any], study_type: str
) -> None:
    """Raise the exact ValueError messages the current inline validation
    produces, so the registry entries stay declarative and the messages stay
    byte-identical."""
    if study_type == "short_circuit":
        if kwargs.get("bus_id") is None:
            raise ValueError("bus_id must be provided for fault study")
    elif study_type == "protection_coordination":
        upstream_relay_id = kwargs.get("upstream_relay_id")
        downstream_relay_id = kwargs.get("downstream_relay_id")
        fault_currents = kwargs.get("fault_currents")
        if upstream_relay_id is None or downstream_relay_id is None or fault_currents is None:
            raise ValueError(
                "upstream_relay_id, downstream_relay_id, and fault_currents must be provided",
            )
    elif study_type == "arc_flash":
        missing = [k for k in required if k not in kwargs]
        if missing:
            raise ValueError(
                f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})",
            )


class PowerSystemEngine:
    """
    Power system simulation engine with dependency injection.

    All solvers can be injected via the constructor, enabling unit testing
    with mock/stub implementations.  When a solver is omitted, a default
    concrete instance is created (maintaining full backward compatibility).

    Parameters
    ----------
    system : System, optional
        The power system object. May be None for studies that do not
        require a network model (e.g. arc flash from bolted-fault current).
    load_flow_solver : LoadFlowSolverProtocol, optional
        Injected load-flow solver.  Defaults to ``LoadFlowSolver(system)``.
    arc_flash_engine : ArcFlashEngineProtocol, optional
        Injected arc-flash engine.  Defaults to ``ArcFlashEngine()``.
    coordination_engine : CoordinationEngineProtocol, optional
        Injected coordination engine.  Defaults to ``CoordinationEngine()``.
    visualizer : VisualizerProtocol, optional
        Injected visualizer.  Defaults to ``Visualizer()``.
    """

    def __init__(
        self,
        system: System | None = None,
        *,
        load_flow_solver: LoadFlowSolverProtocol | None = None,
        arc_flash_engine: ArcFlashEngineProtocol | None = None,
        coordination_engine: CoordinationEngineProtocol | None = None,
        visualizer: VisualizerProtocol | None = None,
    ) -> None:
        self.system = system

        # Injected or default solvers
        if load_flow_solver is not None:
            self.load_flow_solver = load_flow_solver
        elif system is not None:
            self.load_flow_solver = LoadFlowSolver(system)
        else:
            self.load_flow_solver = None
        self.arc_flash_engine = (
            arc_flash_engine if arc_flash_engine is not None else ArcFlashEngine()
        )
        self.coordination_engine = (
            coordination_engine if coordination_engine is not None else CoordinationEngine()
        )
        self.visualizer = visualizer if visualizer is not None else Visualizer()
        # Fault analyzer is created lazily in run_fault_analysis with sequence networks

    def run_load_flow(
        self,
        tol: float = 1e-6,
        max_iter: int = 100,
        mode: str = "engineering",
        solver_type: str = "newton_raphson",
    ) -> dict[str, Any]:
        """
        Run load flow analysis.

        Parameters:
        tol (float): Convergence tolerance. Default 1e-6.
        max_iter (int): Maximum iterations. Default 100.
        mode (str): Solver mode ('engineering' or 'high_accuracy').
        solver_type (str): Solver method ('newton_raphson', 'fast_decoupled', 'dc_flow').

        Returns:
        dict: Results including bus voltages, power flows, and convergence status.
        """
        if self.system is None and self.load_flow_solver is None:
            raise RuntimeError("No system model loaded — cannot run load flow")

        stype = str(solver_type).lower().strip()
        if stype in ("fast_decoupled", "fdlf"):
            from load_flow.fast_decoupled import FastDecoupledSolver, FDLFFormulation
            solver = FastDecoupledSolver(self.system, formulation=FDLFFormulation.XB)
            converged = solver.solve(max_iter=max_iter, tol=tol)
            res = solver.get_results()
            res["Ybus"] = solver.Ybus
            return res

        elif stype in ("dc_flow", "dc", "dc_load_flow"):
            from load_flow.dc_flow import DCLoadFlowSolver
            solver = DCLoadFlowSolver(self.system)
            converged = solver.solve()
            res = solver.get_results()
            res["Ybus"] = self.system.get_ybus(seq="1")
            return res

        # Default Newton-Raphson solver
        if self.load_flow_solver is None and self.system is not None:
            self.load_flow_solver = LoadFlowSolver(self.system)

        base_mva = float(getattr(self.system, "base_mva", 100.0) or 100.0)
        converged = self.load_flow_solver.solve(max_iter=max_iter, tol=tol, mode=mode)
        bus_voltages = {}
        for bid in self.load_flow_solver.bus_ids:
            bus_voltages[bid] = self.load_flow_solver.V[self.load_flow_solver.bus_index[bid]]

        if not converged or getattr(self.load_flow_solver, "error_code", None) == "DEGENERATE_SOLUTION":
            err_code = getattr(self.load_flow_solver, "error_code", None)
            err_msg = getattr(self.load_flow_solver, "error_message", "Load flow solver did not converge")
            return {
                "converged": False,
                "error_code": err_code,
                "error_message": err_msg,
                "bus_voltages": bus_voltages,
                "ybus": self.load_flow_solver.Ybus,
                "Ybus": self.load_flow_solver.Ybus,
                "base_mva": base_mva,
                "warnings": [err_msg] if err_msg else [],
            }

        from network_solver.zbus import zbus_full

        ybus = self.load_flow_solver.Ybus
        zbus = zbus_full(ybus)

        # Injections
        p_inj, q_inj = self.load_flow_solver._calculate_power(self.load_flow_solver.V)
        bus_injections = {}
        for i, bid in enumerate(self.load_flow_solver.bus_ids):
            bus_obj = self.system.buses[bid]
            v_val = self.load_flow_solver.V[i]
            bus_injections[bid] = {
                "bus_id": bid,
                "p_inj_pu": float(p_inj[i]),
                "q_inj_pu": float(q_inj[i]),
                "p_inj_mw": float(p_inj[i] * base_mva),
                "q_inj_mvar": float(q_inj[i] * base_mva),
                "p_gen_pu": float(bus_obj.generation_power.real),
                "q_gen_pu": float(bus_obj.generation_power.imag),
                "p_gen_mw": float(bus_obj.generation_power.real * base_mva),
                "q_gen_mvar": float(bus_obj.generation_power.imag * base_mva),
                "p_load_pu": float(bus_obj.load_power.real),
                "q_load_pu": float(bus_obj.load_power.imag),
                "p_load_mw": float(bus_obj.load_power.real * base_mva),
                "q_load_mvar": float(bus_obj.load_power.imag * base_mva),
                "voltage_magnitude": float(abs(v_val)),
                "voltage_angle_deg": float(math.degrees(np.angle(v_val))),
            }

        # Line flows
        line_flows = {}
        for line in getattr(self.system, "lines", []):
            fb = line.from_bus.bus_id
            tb = line.to_bus.bus_id
            v_f = bus_voltages[fb]
            v_t = bus_voltages[tb]
            z = line.z1
            y = 1.0 / z if abs(z) > 1e-12 else 0.0
            y_sh = line.yshunt1 / 2.0
            i_ft = (v_f - v_t) * y + v_f * y_sh
            i_tf = (v_t - v_f) * y + v_t * y_sh
            s_ft = v_f * np.conj(i_ft)
            s_tf = v_t * np.conj(i_tf)
            line_flows[line.line_id] = {
                "line_id": line.line_id,
                "from_bus_id": fb,
                "to_bus_id": tb,
                "p_from_pu": float(s_ft.real),
                "q_from_pu": float(s_ft.imag),
                "p_from_mw": float(s_ft.real * base_mva),
                "q_from_mvar": float(s_ft.imag * base_mva),
                "p_to_pu": float(s_tf.real),
                "q_to_pu": float(s_tf.imag),
                "p_to_mw": float(s_tf.real * base_mva),
                "q_to_mvar": float(s_tf.imag * base_mva),
                "p_loss_pu": float((s_ft + s_tf).real),
                "q_loss_pu": float((s_ft + s_tf).imag),
                "p_loss_mw": float((s_ft + s_tf).real * base_mva),
                "q_loss_mvar": float((s_ft + s_tf).imag * base_mva),
                "current_from_pu": float(abs(i_ft)),
                "current_from_angle_deg": float(math.degrees(np.angle(i_ft))),
                "current_to_pu": float(abs(i_tf)),
                "current_to_angle_deg": float(math.degrees(np.angle(i_tf))),
            }

        # Transformer flows
        transformer_flows = {}
        for xf in getattr(self.system, "transformers", []):
            fb = xf.from_bus.bus_id
            tb = xf.to_bus.bus_id
            v_f = bus_voltages[fb]
            v_t = bus_voltages[tb]
            z = xf.z1
            y = 1.0 / z if abs(z) > 1e-12 else 0.0
            tap = xf.tap_ratio
            ps = getattr(xf, "phase_shift", 0.0)
            a = tap * np.exp(1j * ps)
            y_sh = xf.yshunt1 / 2.0
            i_ft = (v_f / (abs(a) ** 2) - v_t / np.conj(a)) * y + (v_f / (abs(a) ** 2)) * y_sh
            i_tf = (v_t - v_f / a) * y + v_t * y_sh
            s_ft = v_f * np.conj(i_ft)
            s_tf = v_t * np.conj(i_tf)
            transformer_flows[xf.transformer_id] = {
                "transformer_id": xf.transformer_id,
                "from_bus_id": fb,
                "to_bus_id": tb,
                "p_from_pu": float(s_ft.real),
                "q_from_pu": float(s_ft.imag),
                "p_from_mw": float(s_ft.real * base_mva),
                "q_from_mvar": float(s_ft.imag * base_mva),
                "p_to_pu": float(s_tf.real),
                "q_to_pu": float(s_tf.imag),
                "p_to_mw": float(s_tf.real * base_mva),
                "q_to_mvar": float(s_tf.imag * base_mva),
                "p_loss_pu": float((s_ft + s_tf).real),
                "q_loss_pu": float((s_ft + s_tf).imag),
                "p_loss_mw": float((s_ft + s_tf).real * base_mva),
                "q_loss_mvar": float((s_ft + s_tf).imag * base_mva),
            }

        iterations = (
            len(self.load_flow_solver.iteration_log)
            if hasattr(self.load_flow_solver, "iteration_log")
            else 0
        )
        last_mismatch = (
            float(self.load_flow_solver.iteration_log[-1]["max_mismatch"])
            if iterations > 0 and "max_mismatch" in self.load_flow_solver.iteration_log[-1]
            else 0.0
        )

        return {
            "converged": True,
            "bus_voltages": bus_voltages,
            "ybus": ybus,
            "Ybus": ybus,
            "zbus": zbus,
            "Zbus": zbus,
            "line_flows": line_flows,
            "transformer_flows": transformer_flows,
            "bus_injections": bus_injections,
            "base_mva": base_mva,
            "iterations": iterations,
            "max_mismatch": last_mismatch,
            "warnings": [],
        }

    def run_fault_analysis(self, fault_type: str, bus_id: int) -> dict[str, Any]:
        """
        Run fault analysis for a given fault type and bus.

        Parameters:
        fault_type (str): Type of fault: 'three_phase', 'line_to_ground', 'line_to_line', 'double_line_to_ground'.
        bus_id (int): Bus ID where fault occurs.

        Returns:
        dict: Fault analysis results.
        """
        if self.load_flow_solver is None:
            if self.system is not None:
                self.load_flow_solver = LoadFlowSolver(self.system)
            else:
                raise RuntimeError("No system model loaded — cannot run fault analysis")
        # Build sequence networks with generator impedances for fault analysis
        self.system.build_sequence_networks(for_fault=True)
        ybus_pos = self.system.get_ybus(
            seq="1"
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ybus_neg = self.system.get_ybus(
            seq="2"
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        ybus_zero = self.system.get_ybus(
            seq="0"
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        # Determine slack bus index
        slack_index = None
        slack_bus_id = getattr(self.load_flow_solver, "slack_bus_id", None)
        if slack_bus_id is not None and slack_bus_id in self.load_flow_solver.bus_index:
            slack_index = self.load_flow_solver.bus_index[slack_bus_id]
        elif hasattr(self.system, "buses"):
            for bid, b in self.system.buses.items():
                if getattr(b, "bus_type", "") == "slack":
                    slack_index = self.load_flow_solver.bus_index.get(bid, 0)
                    break

        base_mva = 100.0
        if getattr(self.system, "base_mva", None) is not None:
            base_mva = float(self.system.base_mva)

        bus_obj = self.system.buses.get(bus_id) if hasattr(self.system, "buses") else None
        if bus_obj and getattr(bus_obj, "base_kv", None) is not None:
            base_kv = float(bus_obj.base_kv)
        elif getattr(self.system, "base_kv", None) is not None:
            base_kv = float(self.system.base_kv)
        else:
            raise ValueError(
                f"base_kv missing for bus '{bus_id}' and system (fail-closed: no default base voltage permitted per IEC 60909)"
            )

        # Create fault analyzer
        fault_analyzer = FaultAnalyzer(
            ybus_pos,
            ybus_neg,
            ybus_zero,
            base_mva=base_mva,
            base_kv=base_kv,
            slack_bus_index=slack_index,
        )
        # Get bus index fail-closed
        if bus_id not in self.load_flow_solver.bus_index:
            valid_buses = sorted(self.load_flow_solver.bus_index.keys())
            raise ValueError(
                f"bus_id {bus_id} not found in system buses {valid_buses} for fault analysis"
            )
        bus_index = self.load_flow_solver.bus_index[bus_id]
        # Normalize and validate fault type
        ft = str(fault_type).lower().strip()
        alias_ft = {
            "slg": "line_to_ground",
            "ll": "line_to_line",
            "llg": "double_line_to_ground",
            "3phase": "three_phase",
            "3p": "three_phase",
        }
        fault_type = alias_ft.get(ft, ft)
        # Calculate fault
        if fault_type == "three_phase":
            result = fault_analyzer.three_phase_fault(bus_index)
        elif fault_type == "line_to_ground":
            result = fault_analyzer.line_to_ground_fault(bus_index)
        elif fault_type == "line_to_line":
            result = fault_analyzer.line_to_line_fault(bus_index)
        elif fault_type == "double_line_to_ground":
            result = fault_analyzer.double_line_to_ground_fault(bus_index)
        else:
            raise ValueError(f"Unsupported fault type: {fault_type}")
        return result

    def run_arc_flash(
        self,
        voltage_kv: float,
        bolted_fault_current_ka: float,
        arc_duration_sec: float,
        working_distance_mm: float,
        electrode_config: str = "VCB",
        enclosure_type: str = "box",
        enclosure_width_mm: float = 508.0,
        enclosure_height_mm: float = 508.0,
        enclosure_depth_mm: float = 508.0,
        arc_gap_mm: float | None = None,
    ) -> dict[str, Any]:
        """
        Run arc flash analysis per IEEE 1584-2018.

        Parameters
        ----------
        voltage_kv : float
            System voltage in kV (0.208–15 kV; outside this range the
            ``ArcFlashEngine`` falls back to Ralph Lee).
        bolted_fault_current_ka : float
            Bolted fault current in kA (0.7–106 kA per IEEE 1584-2018).
        arc_duration_sec : float
            Arc duration in seconds.
        working_distance_mm : float
            Working distance in mm.
        electrode_config : str
            One of "VCB", "VCBB", "HCB", "VOA", "HOA".
        enclosure_type : str
            "open" or "box".
        enclosure_width_mm, enclosure_height_mm, enclosure_depth_mm : float
            Enclosure dimensions (default 508 mm ≈ 20 in cube).

        Returns
        -------
        dict
            Arc flash result with keys matching the legacy ``arc_flash_calculator``
            tool output (incident_energy_cal_per_cm2, arc_flash_boundary_mm,
            ppe_level, …) so callers can migrate transparently.
        """
        try:
            electrode_enum = ElectrodeConfig(electrode_config)
        except ValueError:
            valid_configs = [e.value for e in ElectrodeConfig]
            raise ValueError(
                f"Invalid electrode_config '{electrode_config}'. Allowed values: {valid_configs}"
            )
        try:
            enclosure_enum = EnclosureType(enclosure_type)
        except ValueError:
            valid_types = [e.value for e in EnclosureType]
            raise ValueError(
                f"Invalid enclosure_type '{enclosure_type}'. Allowed values: {valid_types}"
            )

        result = self.arc_flash_engine.calculate(
            voltage_kv=voltage_kv,
            bolted_fault_current_ka=bolted_fault_current_ka,
            arc_duration_sec=arc_duration_sec,
            working_distance_mm=working_distance_mm,
            electrode_config=electrode_enum,
            enclosure_type=enclosure_enum,
            enclosure_width_mm=enclosure_width_mm,
            enclosure_height_mm=enclosure_height_mm,
            enclosure_depth_mm=enclosure_depth_mm,
            arc_gap_mm=arc_gap_mm,
        )

        return {
            "incident_energy_cal_per_cm2": result.incident_energy_cal_cm2,
            "incident_energy_at_full_arc_current": result.incident_energy_at_full_arc_current,
            "incident_energy_at_reduced_arc_current": result.incident_energy_at_reduced_arc_current,
            "arc_flash_boundary_mm": result.arc_flash_boundary_mm,
            "arc_flash_boundary_in": result.arc_flash_boundary_in,
            "arc_current_ka": result.arc_current_ka,
            "reduced_arc_current_ka": result.reduced_arc_current_ka,
            "method": result.method,
            "electrode_configuration": result.electrode_configuration,
            "enclosure_type": result.enclosure_type,
            "ppe_level": result.ppe_level,
            "ppe_description": result.ppe_description,
            "voltage_kv": result.voltage_kv,
            "bolted_fault_current_ka": result.bolted_fault_current_ka,
            "arc_duration_sec": result.arc_duration_sec,
            "working_distance_mm": result.working_distance_mm,
        }

    def run_protection_coordination(
        self,
        upstream_relay_id: int,
        downstream_relay_id: int,
        fault_currents: list[float],
        relays_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run protection coordination check between two relays.

        **IMPORTANT — Life-Safety Warning:**
        This method requires real relay parameters (TMS, Ip, curve_type) to produce
        meaningful results. When ``relays_config`` is provided with the required fields,
        those values are used. Without them this method returns an error —
        it MUST NOT silently fall back to dummy relays, as the resulting coordination
        analysis would be dangerously misleading in a real protection system.

        Parameters
        ----------
        upstream_relay_id : int
            ID of upstream relay.
        downstream_relay_id : int
            ID of downstream relay.
        fault_currents : list[float]
            List of fault currents in per-unit.
        relays_config : dict, optional
            Relay parameter dictionary with the following schema::

                {
                    "upstream": {"tms": float, "pickup_current_a": float, "curve_type": str},
                    "downstream": {"tms": float, "pickup_current_a": float, "curve_type": str},
                }

            If omitted or incomplete, the method returns an error with
            ``is_simulated: true`` rather than fabricating relay values.

        Returns
        -------
        dict
            Coordination results with ``is_simulated`` flag.
        """
        # ── Validate relay configuration ───────────────────────────────────
        if not relays_config or not isinstance(relays_config, dict):
            return {
                "all_coordinated": False,
                "is_simulated": True,
                "error": (
                    "Protection coordination requires real relay parameters "
                    "(relays_config with upstream/downstream TMS, pickup_current, curve_type). "
                    "No relay database is configured — see docs/ARCHITECTURE.md for setup."
                ),
                "results": [],
            }

        up_conf = relays_config.get("upstream")
        down_conf = relays_config.get("downstream")

        if not up_conf or not down_conf:
            return {
                "all_coordinated": False,
                "is_simulated": True,
                "error": (
                    "Both upstream and downstream relay configurations are required. "
                    "Received: upstream={}, downstream={}".format(
                        "present" if up_conf else "missing", "present" if down_conf else "missing"
                    )
                ),
                "results": [],
            }

        # ── Build relay objects from real config ────────────────────────────
        upstream_relay = OvercurrentRelay(
            relay_id=upstream_relay_id,
            name=up_conf.get("name", f"Upstream_{upstream_relay_id}"),
            TMS=up_conf["tms"],
            Ip=up_conf["pickup_current_a"],
            curve_type=up_conf.get("curve_type", "standard_inverse"),
        )
        downstream_relay = OvercurrentRelay(
            relay_id=downstream_relay_id,
            name=down_conf.get("name", f"Downstream_{downstream_relay_id}"),
            TMS=down_conf["tms"],
            Ip=down_conf["pickup_current_a"],
            curve_type=down_conf.get("curve_type", "standard_inverse"),
        )

        # Check coordination
        results = self.coordination_engine.check_coordination_range(
            upstream_relay,
            downstream_relay,
            fault_currents,
        )

        # Determine if coordinated for all faults
        all_coordinated = all(r["coordinated"] for r in results)
        return {
            "all_coordinated": all_coordinated,
            "is_simulated": False,
            "results": results,
            "upstream_relay": {
                "id": upstream_relay_id,
                "tms": up_conf["tms"],
                "pickup_current_a": up_conf["pickup_current_a"],
                "curve_type": up_conf.get("curve_type", "standard_inverse"),
            },
            "downstream_relay": {
                "id": downstream_relay_id,
                "tms": down_conf["tms"],
                "pickup_current_a": down_conf["pickup_current_a"],
                "curve_type": down_conf.get("curve_type", "standard_inverse"),
            },
        }

    def run_study(self, study_type: str, **kwargs: Any) -> dict[str, Any]:
        """
        Run a study based on study type.

        Parameters:
        study_type (str): Type of study: 'load_flow', 'short_circuit', 'protection_coordination'.
        **kwargs: Additional arguments specific to the study type.

        Returns:
        dict: Study results.
        """
        if study_type == "load_flow":
            return self.run_load_flow()
        elif study_type == "short_circuit":
            fault_type = kwargs.get("fault_type", "three_phase")
            bus_id = kwargs.get("bus_id")
            if bus_id is None:
                raise ValueError("bus_id must be provided for fault study")
            return self.run_fault_analysis(fault_type, bus_id)
        elif study_type == "protection_coordination":
            upstream_relay_id = kwargs.get("upstream_relay_id")
            downstream_relay_id = kwargs.get("downstream_relay_id")
            fault_currents = kwargs.get("fault_currents")
            if upstream_relay_id is None or downstream_relay_id is None or fault_currents is None:
                raise ValueError(
                    "upstream_relay_id, downstream_relay_id, and fault_currents must be provided",
                )
            return self.run_protection_coordination(
                upstream_relay_id,
                downstream_relay_id,
                fault_currents,
            )
        elif study_type == "arc_flash":
            required = (
                "voltage_kv",
                "bolted_fault_current_ka",
                "arc_duration_sec",
                "working_distance_mm",
            )
            missing = [k for k in required if k not in kwargs]
            if missing:
                raise ValueError(
                    f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})",
                )
            return self.run_arc_flash(
                voltage_kv=kwargs["voltage_kv"],
                bolted_fault_current_ka=kwargs["bolted_fault_current_ka"],
                arc_duration_sec=kwargs["arc_duration_sec"],
                working_distance_mm=kwargs["working_distance_mm"],
                electrode_config=kwargs.get("electrode_config", "VCB"),
                enclosure_type=kwargs.get("enclosure_type", "box"),
                enclosure_width_mm=kwargs.get("enclosure_width_mm", 508.0),
                enclosure_height_mm=kwargs.get("enclosure_height_mm", 508.0),
                enclosure_depth_mm=kwargs.get("enclosure_depth_mm", 508.0),
                arc_gap_mm=kwargs.get("arc_gap_mm"),
            )
        else:
            try:
                from engine.dispatch import STUDY_DISPATCH

                if study_type in STUDY_DISPATCH:
                    from core.exceptions import SpecializedExecutionUnavailableError

                    raise SpecializedExecutionUnavailableError(
                        study_type, "not supported in native engine shim"
                    )
            except ImportError:
                pass
            raise ValueError(f"Unsupported study type: {study_type}")

    def visualize_tcc(
        self,
        relays: list[OvercurrentRelay],
        current_range: tuple[float, float] = (0.5, 20),
        points: int = 100,
    ) -> Any:
        """
        Visualize TCC curves for a list of relays.

        Parameters:
        relays (list): List of OvercurrentRelay objects.
        current_range (tuple): Min and max current in multiples of pickup.
        points (int): Number of points.

        Returns:
        matplotlib.figure.Figure: The figure object.
        """
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots()
        self.visualizer.plot_multiple_tcc(relays, current_range=current_range, points=points, ax=ax)
        return fig

    def visualize_coordination(
        self,
        upstream_relay: OvercurrentRelay,
        downstream_relay: OvercurrentRelay,
        fault_currents: list[float],
    ) -> Any:
        """
        Visualize coordination margin.

        Parameters:
        upstream_relay (OvercurrentRelay): Upstream relay.
        downstream_relay (OvercurrentRelay): Downstream relay.
        fault_currents (list): Fault currents.

        Returns:
        matplotlib.figure.Figure: The figure object.
        """
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots()
        self.visualizer.plot_coordination_margin(
            upstream_relay,
            downstream_relay,
            fault_currents,
            ax=ax,
        )
        return fig
