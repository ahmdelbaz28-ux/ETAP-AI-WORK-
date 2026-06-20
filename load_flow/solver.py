"""Load Flow Solver Integration with Sparse Matrix Support.

This module provides the primary load-flow solver interface with both
dense (existing) and sparse (new) solver paths.  The sparse solver
uses ``engine.sparse_solver.SparseYBus`` for memory-efficient
computation on large networks.

Functions
---------
solve_load_flow_sparse(buses, branches, options)
    Solve load flow using the sparse Y-bus / Newton-Raphson solver.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Union

import numpy as np

# Re-export the existing fixed solver for backward compatibility
from load_flow.load_flow_solver_fixed import LoadFlowSolver  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type aliases for flexible input formats
# ---------------------------------------------------------------------------

# A bus can be provided as a BusData object, a core_model.Bus object,
# or a plain dict with the required keys.
BusInput = Union[Dict[str, Any], Any]

# A branch can be provided as a BranchData object, a core_model.Line /
# Transformer object, or a plain dict.
BranchInput = Union[Dict[str, Any], Any]


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _bus_to_bus_data(bus: BusInput, index_map: Dict[int, int]) -> Any:
    """Convert various bus representations to ``BusData``.

    Parameters
    ----------
    bus : BusInput
        A dict, ``core_model.Bus``, or ``BusData`` instance.
    index_map : dict
        Mapping from bus_id → sequential index (populated in-place).

    Returns
    -------
    BusData
    """
    from engine.sparse_solver import BusData

    if isinstance(bus, BusData):
        return bus

    if isinstance(bus, dict):
        bus_id = bus.get("bus_id", bus.get("id", 0))
        return BusData(
            bus_id=bus_id,
            bus_type=bus.get("bus_type", "pq"),
            voltage_magnitude=bus.get("voltage_magnitude", bus.get("vm", 1.0)),
            voltage_angle=bus.get("voltage_angle", bus.get("va", 0.0)),
            p_generation=bus.get("p_generation", bus.get("pg", 0.0)),
            q_generation=bus.get("q_generation", bus.get("qg", 0.0)),
            p_load=bus.get("p_load", bus.get("pd", 0.0)),
            q_load=bus.get("q_load", bus.get("qd", 0.0)),
            q_min=bus.get("q_min", -999.0),
            q_max=bus.get("q_max", 999.0),
            v_scheduled=bus.get("v_scheduled", bus.get("vs", 1.0)),
        )

    # core_model.Bus object
    if hasattr(bus, "bus_id"):
        gen_power = getattr(bus, "generation_power", 0)
        load_power = getattr(bus, "load_power", 0)
        pg = gen_power.real if isinstance(gen_power, complex) else float(gen_power)
        qg = gen_power.imag if isinstance(gen_power, complex) else 0.0
        pd = load_power.real if isinstance(load_power, complex) else float(load_power)
        qd = load_power.imag if isinstance(load_power, complex) else 0.0

        return BusData(
            bus_id=bus.bus_id,
            bus_type=getattr(bus, "bus_type", "pq"),
            voltage_magnitude=getattr(bus, "voltage_magnitude", 1.0),
            voltage_angle=getattr(bus, "voltage_angle", 0.0),
            p_generation=pg,
            q_generation=qg,
            p_load=pd,
            q_load=qd,
            q_min=getattr(bus, "q_min", -999.0),
            q_max=getattr(bus, "q_max", 999.0),
            v_scheduled=getattr(bus, "voltage_magnitude", 1.0)
            if getattr(bus, "bus_type", "pq") == "pv" else 1.0,
        )

    raise TypeError(f"Unsupported bus type: {type(bus)}")


def _branch_to_branch_data(
    branch: BranchInput,
    index_map: Dict[int, int],
) -> Any:
    """Convert various branch representations to ``BranchData``.

    Parameters
    ----------
    branch : BranchInput
        A dict, ``core_model.Line``/``Transformer``, or ``BranchData``.
    index_map : dict
        Mapping from bus_id → sequential index.

    Returns
    -------
    BranchData
    """
    from engine.sparse_solver import BranchData

    if isinstance(branch, BranchData):
        return branch

    if isinstance(branch, dict):
        from_bus = index_map.get(branch.get("from_bus", -1), branch.get("from_bus", -1))
        to_bus = index_map.get(branch.get("to_bus", -1), branch.get("to_bus", -1))
        return BranchData(
            from_bus=from_bus,
            to_bus=to_bus,
            impedance=branch.get("impedance", branch.get("z", complex(0, 0.1))),
            shunt_admittance=branch.get("shunt_admittance", branch.get("y_shunt", complex(0, 0))),
            tap_ratio=branch.get("tap_ratio", 1.0),
            phase_shift=branch.get("phase_shift", 0.0),
        )

    # core_model.Line or Transformer
    if hasattr(branch, "from_bus") and hasattr(branch, "to_bus"):
        from_id = branch.from_bus.bus_id
        to_id = branch.to_bus.bus_id
        from_idx = index_map.get(from_id, from_id)
        to_idx = index_map.get(to_id, to_id)
        z = branch.get_impedance("1") if hasattr(branch, "get_impedance") else complex(0, 0.1)
        ys = branch.get_shunt_admittance("1") if hasattr(branch, "get_shunt_admittance") else complex(0, 0)
        tap = getattr(branch, "tap_ratio", 1.0)
        ps = getattr(branch, "phase_shift", 0.0)
        return BranchData(
            from_bus=from_idx,
            to_bus=to_idx,
            impedance=z,
            shunt_admittance=ys,
            tap_ratio=tap,
            phase_shift=ps,
        )

    raise TypeError(f"Unsupported branch type: {type(branch)}")


# ---------------------------------------------------------------------------
# Main sparse solver integration
# ---------------------------------------------------------------------------

def solve_load_flow_sparse(
    buses: List[BusInput],
    branches: List[BranchInput],
    options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Solve load flow using the sparse Y-bus Newton-Raphson solver.

    This is the primary integration point for the sparse solver.  It
    accepts flexible bus/branch data (dicts, ``core_model`` objects, or
    ``BusData``/``BranchData`` instances), builds the sparse admittance
    matrix, and runs Newton-Raphson.

    Parameters
    ----------
    buses : list
        Bus specifications.  Each element can be a ``dict``,
        ``core_model.Bus``, or ``BusData``.
    branches : list
        Branch specifications.  Each element can be a ``dict``,
        ``core_model.Line``/``Transformer``, or ``BranchData``.
    options : dict, optional
        Solver options:

        * ``max_iter`` (int) – Maximum Newton iterations (default 50).
        * ``tol`` (float) – Convergence tolerance in per-unit (default 1e-8).
        * ``use_gpu`` (bool) – If ``True``, attempt GPU acceleration
          via ``GPUSolver`` (default ``False``).
        * ``verbose`` (bool) – Log detailed iteration info (default ``False``).
        * ``voltage_limits`` (tuple) – (V_min, V_max) in per-unit
          (default ``(0.5, 1.5)``).

    Returns
    -------
    dict
        Result dictionary with keys:

        * ``converged`` (bool)
        * ``iterations`` (int)
        * ``max_mismatch`` (float)
        * ``voltages`` (dict) – ``{bus_id: complex_voltage}``
        * ``magnitudes`` (dict) – ``{bus_id: |V|}``
        * ``angles_deg`` (dict) – ``{bus_id: angle_degrees}``
        * ``active_power`` (dict) – ``{bus_id: P}``
        * ``reactive_power`` (dict) – ``{bus_id: Q}``
        * ``ybus_nnz`` (int) – Non-zero count in sparse Y-bus
        * ``solve_time_seconds`` (float)
        * ``solver_type`` (str)
        * ``iteration_log`` (list)
        * ``memory_comparison`` (dict)
    """
    from engine.sparse_solver import BranchData, BusData, SparseYBus

    opts = options or {}
    max_iter = opts.get("max_iter", 50)
    tol = opts.get("tol", 1e-8)
    use_gpu = opts.get("use_gpu", False)
    verbose = opts.get("verbose", False)

    # --- Convert inputs to standard BusData / BranchData ---
    # First pass: build bus_id → sequential index mapping
    bus_id_to_idx: Dict[int, int] = {}
    bus_data_list: List[BusData] = []

    for idx, bus in enumerate(buses):
        bd = _bus_to_bus_data(bus, bus_id_to_idx)
        bus_id_to_idx[bd.bus_id] = idx
        bus_data_list.append(bd)

    # Re-assign indices now that mapping is complete
    bus_id_to_idx = {bd.bus_id: i for i, bd in enumerate(bus_data_list)}

    branch_data_list: List[BranchData] = []
    for branch in branches:
        bd = _branch_to_branch_data(branch, bus_id_to_idx)
        branch_data_list.append(bd)

    if verbose:
        logger.info(
            "Sparse load-flow: %d buses, %d branches, max_iter=%d, tol=%.1e",
            len(bus_data_list), len(branch_data_list), max_iter, tol,
        )

    # --- Build sparse Y-bus ---
    builder = SparseYBus()
    ybus = builder.build_sparse_ybus(bus_data_list, branch_data_list)

    # --- Memory comparison ---
    mem = builder.compare_memory()

    # --- Solve ---
    if use_gpu:
        from engine.gpu_solver import GPUSolver
        solver = GPUSolver()
        result = solver.newton_raphson_gpu(ybus, bus_data_list, max_iter=max_iter, tol=tol)
    else:
        result = builder.sparse_newton_raphson(ybus, bus_data_list, max_iter=max_iter, tol=tol)

    if verbose:
        logger.info(
            "Sparse load-flow %s: converged=%s, iterations=%d, mismatch=%.2e",
            result.solver_type, result.converged, result.iterations,
            result.max_mismatch,
        )

    # --- Format results ---
    voltages_dict: Dict[int, complex] = {}
    magnitudes_dict: Dict[int, float] = {}
    angles_deg_dict: Dict[int, float] = {}
    p_dict: Dict[int, float] = {}
    q_dict: Dict[int, float] = {}

    for i, bd in enumerate(bus_data_list):
        if i < len(result.voltages):
            v = result.voltages[i]
            voltages_dict[bd.bus_id] = complex(v)
            magnitudes_dict[bd.bus_id] = float(abs(v))
            angles_deg_dict[bd.bus_id] = float(np.degrees(np.angle(v)))
        if i < len(result.active_power):
            p_dict[bd.bus_id] = float(result.active_power[i])
        if i < len(result.reactive_power):
            q_dict[bd.bus_id] = float(result.reactive_power[i])

    return {
        "converged": result.converged,
        "iterations": result.iterations,
        "max_mismatch": result.max_mismatch,
        "voltages": voltages_dict,
        "magnitudes": magnitudes_dict,
        "angles_deg": angles_deg_dict,
        "active_power": p_dict,
        "reactive_power": q_dict,
        "ybus_nnz": int(ybus.nnz),
        "solve_time_seconds": result.solve_time_seconds,
        "solver_type": result.solver_type,
        "iteration_log": result.iteration_log,
        "memory_comparison": mem,
    }
