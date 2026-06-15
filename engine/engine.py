from typing import Any, Dict, List, Optional

from coordination.coordination import CoordinationEngine
from engine.interfaces import (
    ArcFlashEngineProtocol,
    CoordinationEngineProtocol,
    FaultAnalyzerProtocol,
    LoadFlowSolverProtocol,
    VisualizerProtocol,
)
from fault_analysis.arc_flash_engine import ArcFlashEngine, ElectrodeConfig, EnclosureType
from fault_analysis.fault import FaultAnalyzer
from load_flow.load_flow_solver_fixed import LoadFlowSolver
from relays.relay import OvercurrentRelay
from visualization.visualization import Visualizer


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
        system=None,
        *,
        load_flow_solver: Optional[LoadFlowSolverProtocol] = None,
        arc_flash_engine: Optional[ArcFlashEngineProtocol] = None,
        coordination_engine: Optional[CoordinationEngineProtocol] = None,
        visualizer: Optional[VisualizerProtocol] = None,
    ):
        self.system = system

        # Injected or default solvers
        self.load_flow_solver = (
            load_flow_solver
            if load_flow_solver is not None
            else (LoadFlowSolver(system) if system is not None else None)
        )
        self.arc_flash_engine = arc_flash_engine if arc_flash_engine is not None else ArcFlashEngine()
        self.coordination_engine = coordination_engine if coordination_engine is not None else CoordinationEngine()
        self.visualizer = visualizer if visualizer is not None else Visualizer()
        # Fault analyzer is created lazily in run_fault_analysis with sequence networks

    def run_load_flow(self):
        """
        Run load flow analysis.

        Returns:
        dict: Results including bus voltages, power flows, and convergence status.
        """
        if self.load_flow_solver is None:
            raise RuntimeError("No system model loaded — cannot run load flow")
        converged = self.load_flow_solver.solve(max_iter=100, tol=1e-6)
        # Extract results
        bus_voltages = {}
        for bid in self.load_flow_solver.bus_ids:
            bus_voltages[bid] = self.load_flow_solver.V[self.load_flow_solver.bus_index[bid]]
        return {
            'converged': converged,
            'bus_voltages': bus_voltages,
            'Ybus': self.load_flow_solver.Ybus
        }

    def run_fault_analysis(self, fault_type, bus_id):
        """
        Run fault analysis for a given fault type and bus.

        Parameters:
        fault_type (str): Type of fault: 'three_phase', 'line_to_ground', 'line_to_line', 'double_line_to_ground'.
        bus_id (int): Bus ID where fault occurs.

        Returns:
        dict: Fault analysis results.
        """
        if self.load_flow_solver is None:
            raise RuntimeError("No system model loaded — cannot run fault analysis")
        # Build sequence networks with generator impedances for fault analysis
        self.system.build_sequence_networks(for_fault=True)
        Ybus_pos = self.system.get_ybus(seq='1')
        Ybus_neg = self.system.get_ybus(seq='2')
        Ybus_zero = self.system.get_ybus(seq='0')
        # Create fault analyzer
        fault_analyzer = FaultAnalyzer(Ybus_pos, Ybus_neg, Ybus_zero)
        # Get bus index
        bus_index = self.load_flow_solver.bus_index[bus_id]
        # Calculate fault
        if fault_type == 'three_phase':
            result = fault_analyzer.three_phase_fault(bus_index)
        elif fault_type == 'line_to_ground':
            result = fault_analyzer.line_to_ground_fault(bus_index)
        elif fault_type == 'line_to_line':
            result = fault_analyzer.line_to_line_fault(bus_index)
        elif fault_type == 'double_line_to_ground':
            result = fault_analyzer.double_line_to_ground_fault(bus_index)
        else:
            raise ValueError(f"Unsupported fault type: {fault_type}")
        return result

    def run_arc_flash(
        self,
        voltage_kv,
        bolted_fault_current_ka,
        arc_duration_sec,
        working_distance_mm,
        electrode_config="VCB",
        enclosure_type="box",
        enclosure_width_mm=508.0,
        enclosure_height_mm=508.0,
        enclosure_depth_mm=508.0,
    ):
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
            electrode_enum = ElectrodeConfig.VCB
        try:
            enclosure_enum = EnclosureType(enclosure_type)
        except ValueError:
            enclosure_enum = EnclosureType.BOX

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

    def run_protection_coordination(self, upstream_relay_id, downstream_relay_id, fault_currents):
        """
        Run protection coordination check between two relays.

        Note: This method assumes that the relays are already defined and accessible.
        In a full implementation, we would retrieve relays from a protection system database.

        For demonstration, we will create dummy relays.

        Parameters:
        upstream_relay_id (int): ID of upstream relay.
        downstream_relay_id (int): ID of downstream relay.
        fault_currents (list): List of fault currents in per-unit.

        Returns:
        dict: Coordination results.
        """
        # In a real system, we would fetch the relay objects from a protection database.
        # For now, we create example relays.
        upstream_relay = OvercurrentRelay(relay_id=upstream_relay_id, name=f'Upstream_{upstream_relay_id}', TMS=0.5, Ip=1.0)
        downstream_relay = OvercurrentRelay(relay_id=downstream_relay_id, name=f'Downstream_{downstream_relay_id}', TMS=0.2, Ip=1.0)
        # Check coordination
        results = self.coordination_engine.check_coordination_range(upstream_relay, downstream_relay, fault_currents)
        # Determine if coordinated for all faults
        all_coordinated = all(r['coordinated'] for r in results)
        return {
            'all_coordinated': all_coordinated,
            'results': results,
            'upstream_relay': upstream_relay,
            'downstream_relay': downstream_relay
        }

    def run_study(self, study_type, **kwargs):
        """
        Run a study based on study type.

        Parameters:
        study_type (str): Type of study: 'load_flow', 'fault', 'coordination'.
        **kwargs: Additional arguments specific to the study type.

        Returns:
        dict: Study results.
        """
        if study_type == 'load_flow':
            return self.run_load_flow()
        elif study_type == 'fault':
            fault_type = kwargs.get('fault_type', 'three_phase')
            bus_id = kwargs.get('bus_id')
            if bus_id is None:
                raise ValueError("bus_id must be provided for fault study")
            return self.run_fault_analysis(fault_type, bus_id)
        elif study_type == 'coordination':
            upstream_relay_id = kwargs.get('upstream_relay_id')
            downstream_relay_id = kwargs.get('downstream_relay_id')
            fault_currents = kwargs.get('fault_currents')
            if upstream_relay_id is None or downstream_relay_id is None or fault_currents is None:
                raise ValueError("upstream_relay_id, downstream_relay_id, and fault_currents must be provided")
            return self.run_protection_coordination(upstream_relay_id, downstream_relay_id, fault_currents)
        elif study_type == 'arc_flash':
            required = ('voltage_kv', 'bolted_fault_current_ka', 'arc_duration_sec', 'working_distance_mm')
            missing = [k for k in required if k not in kwargs]
            if missing:
                raise ValueError(
                    f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})"
                )
            return self.run_arc_flash(
                voltage_kv=kwargs['voltage_kv'],
                bolted_fault_current_ka=kwargs['bolted_fault_current_ka'],
                arc_duration_sec=kwargs['arc_duration_sec'],
                working_distance_mm=kwargs['working_distance_mm'],
                electrode_config=kwargs.get('electrode_config', 'VCB'),
                enclosure_type=kwargs.get('enclosure_type', 'box'),
                enclosure_width_mm=kwargs.get('enclosure_width_mm', 508.0),
                enclosure_height_mm=kwargs.get('enclosure_height_mm', 508.0),
                enclosure_depth_mm=kwargs.get('enclosure_depth_mm', 508.0),
            )
        else:
            raise ValueError(f"Unsupported study type: {study_type}")

    def visualize_tcc(self, relays, current_range=(0.5, 20), points=100):
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

    def visualize_coordination(self, upstream_relay, downstream_relay, fault_currents):
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
        self.visualizer.plot_coordination_margin(upstream_relay, downstream_relay, fault_currents, ax=ax)
        return fig
