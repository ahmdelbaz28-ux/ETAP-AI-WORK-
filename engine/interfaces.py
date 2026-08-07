"""
Engine Interfaces — Abstract protocols for solver dependency injection.

Defines the contracts that all solvers must satisfy so ``PowerSystemEngine``
can accept them via constructor injection rather than instantiating concrete
classes.  This enables:

- Unit testing with mock/stub solvers
- Swapping implementations without modifying engine code
- Lazy / optional solvers (e.g. arc flash does not need a network model)

Usage::

    from engine.interfaces import LoadFlowSolverProtocol
    from engine.engine import PowerSystemEngine

    class MyMockSolver(LoadFlowSolverProtocol):
        def solve(self, max_iter=100, tol=1e-6):
            return True
        ...

    engine = PowerSystemEngine(system, load_flow_solver=MyMockSolver())
"""

from __future__ import annotations

<<<<<<< HEAD
from typing import Any, Optional, Protocol
=======
from typing import Any, Dict, List, Protocol, Tuple
>>>>>>> origin/fix/scenario-tests-properly

# ============================================================================
# Load Flow Solver
# ============================================================================


class LoadFlowSolverProtocol(Protocol):
    """Protocol for load-flow solvers consumed by ``PowerSystemEngine``.

    The Newton-Raphson implementation in ``load_flow.LoadFlowSolver``
    satisfies this protocol.
    """

<<<<<<< HEAD
    bus_ids: list[Any]
    bus_index: dict[Any, int]
=======
    bus_ids: List[Any]
    bus_index: Dict[Any, int]
>>>>>>> origin/fix/scenario-tests-properly
    V: Any  # numpy.ndarray of complex bus voltages
    Ybus: Any  # numpy.ndarray — the bus admittance matrix

    def solve(self, max_iter: int = 100, tol: float = 1e-6, mode: str = "engineering") -> bool:
        """Run the load-flow solution.  Returns ``True`` on convergence."""
        ...


# ============================================================================
# Fault Analyzer
# ============================================================================


class FaultAnalyzerProtocol(Protocol):
    """Protocol for fault analyzers consumed by ``PowerSystemEngine``.

    The implementation in ``fault_analysis.FaultAnalyzer`` accepts Ybus
    matrices for all three sequences and calculates fault currents for
    each fault type.
    """

<<<<<<< HEAD
    def three_phase_fault(self, bus_index: int) -> dict[str, Any]: ...

    def line_to_ground_fault(self, bus_index: int) -> dict[str, Any]: ...

    def line_to_line_fault(self, bus_index: int) -> dict[str, Any]: ...

    def double_line_to_ground_fault(self, bus_index: int) -> dict[str, Any]: ...
=======
    def three_phase_fault(self, bus_index: int) -> Dict[str, Any]: ...

    def line_to_ground_fault(self, bus_index: int) -> Dict[str, Any]: ...

    def line_to_line_fault(self, bus_index: int) -> Dict[str, Any]: ...

    def double_line_to_ground_fault(self, bus_index: int) -> Dict[str, Any]: ...
>>>>>>> origin/fix/scenario-tests-properly


# ============================================================================
# Arc Flash Engine
# ============================================================================


class ArcFlashEngineProtocol(Protocol):
    """Protocol for arc-flash engines consumed by ``PowerSystemEngine``.

    The implementation in ``fault_analysis.ArcFlashEngine`` follows
    IEEE 1584-2018.
    """

    def calculate(
        self,
        voltage_kv: float,
        bolted_fault_current_ka: float,
        arc_duration_sec: float,
        working_distance_mm: float,
        electrode_config: Any = None,
        enclosure_type: Any = None,
        enclosure_width_mm: float = 508.0,
        enclosure_height_mm: float = 508.0,
        enclosure_depth_mm: float = 508.0,
    ) -> Any:
        """Return an object with arc-flash result attributes."""
        ...


# ============================================================================
# Coordination Engine
# ============================================================================


class CoordinationEngineProtocol(Protocol):
    """Protocol for protection-coordination engines.

    The implementation in ``coordination.CoordinationEngine`` checks
    time-grading margins between upstream and downstream overcurrent relays.
    """

    def check_coordination(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
        fault_current: float,
<<<<<<< HEAD
    ) -> dict[str, Any]: ...
=======
    ) -> Dict[str, Any]: ...
>>>>>>> origin/fix/scenario-tests-properly

    def check_coordination_range(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
<<<<<<< HEAD
        fault_currents: list[float],
    ) -> list[dict[str, Any]]: ...
=======
        fault_currents: List[float],
    ) -> List[Dict[str, Any]]: ...
>>>>>>> origin/fix/scenario-tests-properly

    def suggest_tms_adjustment(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
<<<<<<< HEAD
        fault_currents: list[float],
        target_margin: float = 0.2,
    ) -> Optional[float]: ...
=======
        fault_currents: List[float],
        target_margin: float = 0.2,
    ) -> float | None: ...
>>>>>>> origin/fix/scenario-tests-properly


# ============================================================================
# Visualizer (matplotlib-based)
# ============================================================================


class VisualizerProtocol(Protocol):
    """Protocol for visualization helpers.

    The implementation in ``visualization.Visualizer`` creates TCC curves
    and coordination-margin plots.
    """

    def plot_multiple_tcc(
        self,
<<<<<<< HEAD
        relays: list[Any],
        current_range: tuple[float, float] = (0.5, 20),
=======
        relays: List[Any],
        current_range: Tuple[float, float] = (0.5, 20),
>>>>>>> origin/fix/scenario-tests-properly
        points: int = 100,
        ax: Any = None,
    ) -> None: ...

    def plot_coordination_margin(
        self,
        upstream_relay: Any,
        downstream_relay: Any,
<<<<<<< HEAD
        fault_currents: list[float],
=======
        fault_currents: List[float],
>>>>>>> origin/fix/scenario-tests-properly
        ax: Any = None,
    ) -> None: ...
