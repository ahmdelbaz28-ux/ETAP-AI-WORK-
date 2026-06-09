import numpy as np
import matplotlib.pyplot as plt
from core_model.system import System
from load_flow.load_flow_solver_fixed import LoadFlowSolver
from fault_analysis.fault import FaultAnalyzer
from coordination.coordination import CoordinationEngine
from visualization.visualization import Visualizer
from relays.relay import OvercurrentRelay

class PowerSystemEngine:
    def __init__(self, system):
        """
        Initialize the power system engine.

        Parameters:
        system (System): The power system object.
        """
        self.system = system
        self.load_flow_solver = LoadFlowSolver(system)
        self.coordination_engine = CoordinationEngine()
        self.visualizer = Visualizer()
        # Fault analyzer will be created when needed with sequence networks

    def run_load_flow(self):
        """
        Run load flow analysis.

        Returns:
        dict: Results including bus voltages, power flows, and convergence status.
        """
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
        fig, ax = plt.subplots()
        self.visualizer.plot_coordination_margin(upstream_relay, downstream_relay, fault_currents, ax=ax)
        return fig
