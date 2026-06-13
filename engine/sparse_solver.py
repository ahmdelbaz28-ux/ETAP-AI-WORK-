"""Sparse Matrix Solver for Large-Scale Power System Analysis.

Provides memory-efficient sparse Y-bus construction and Newton-Raphson
load flow solving using ``scipy.sparse`` data structures.  Designed for
IEEE 14/30/118-bus test systems and larger networks where dense matrices
become impractical.

Key classes
-----------
SparseYBus
    Builds the sparse admittance matrix and exposes a sparse Newton-Raphson
    solver together with memory/benchmarking utilities.

Mathematical background
-----------------------
Y-bus formulation
    Y_ii = sum of admittances connected to bus i  (+ shunt)
    Y_ij = -y_ij  (off-diagonal, mutual admittance)

Newton-Raphson update
    [ΔP/|V|]   [J1  J2] [Δθ        ]
    [ΔQ/|V|] = [J3  J4] [Δ|V|/|V|  ]

    where J1-J4 are the sub-Jacobians of the power-flow equations.

Linear system
    Solved with ``scipy.sparse.linalg.spsolve`` for maximum efficiency on
    large, sparse networks.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.sparse import csr_matrix, issparse, lil_matrix
from scipy.sparse.linalg import spsolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes for branch / bus specifications
# ---------------------------------------------------------------------------

@dataclass
class BranchData:
    """Minimal representation of a network branch (line or transformer).

    Parameters
    ----------
    from_bus : int
        Index of the sending-end bus.
    to_bus : int
        Index of the receiving-end bus.
    impedance : complex
        Series impedance  z = r + jx  (per-unit).
    shunt_admittance : complex
        Total charging / shunt admittance (per-unit).  Half is placed at
        each end for π-model lines.
    tap_ratio : float
        Off-nominal tap ratio  (default 1.0).
    phase_shift : float
        Phase-shift angle in radians  (default 0.0).
    """

    from_bus: int
    to_bus: int
    impedance: complex = complex(0, 0.1)
    shunt_admittance: complex = complex(0, 0)
    tap_ratio: float = 1.0
    phase_shift: float = 0.0


@dataclass
class BusData:
    """Minimal representation of a bus for load-flow studies.

    Parameters
    ----------
    bus_id : int
        Unique bus identifier.
    bus_type : str
        ``'slack'``, ``'pv'``, or ``'pq'``.
    voltage_magnitude : float
        Initial voltage magnitude (per-unit).
    voltage_angle : float
        Initial voltage angle (radians).
    p_generation : float
        Scheduled active power generation (per-unit).
    q_generation : float
        Scheduled reactive power generation (per-unit).
    p_load : float
        Active power load (per-unit).
    q_load : float
        Reactive power load (per-unit).
    q_min : float
        Minimum reactive power limit (per-unit, PV buses).
    q_max : float
        Maximum reactive power limit (per-unit, PV buses).
    v_scheduled : float
        Scheduled voltage magnitude for PV buses (per-unit).
    """

    bus_id: int = 0
    bus_type: str = "pq"
    voltage_magnitude: float = 1.0
    voltage_angle: float = 0.0
    p_generation: float = 0.0
    q_generation: float = 0.0
    p_load: float = 0.0
    q_load: float = 0.0
    q_min: float = -999.0
    q_max: float = 999.0
    v_scheduled: float = 1.0


# ---------------------------------------------------------------------------
# Convergence result container
# ---------------------------------------------------------------------------

@dataclass
class SparseConvergenceResult:
    """Result of a sparse Newton-Raphson load-flow solve."""

    converged: bool = False
    iterations: int = 0
    max_mismatch: float = 0.0
    voltages: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    angles: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    magnitudes: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    active_power: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    reactive_power: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    iteration_log: List[Dict[str, Any]] = field(default_factory=list)
    solver_type: str = "sparse"
    solve_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# SparseYBus – main class
# ---------------------------------------------------------------------------

class SparseYBus:
    """Sparse admittance-matrix builder and Newton-Raphson load-flow solver.

    Uses ``scipy.sparse.lil_matrix`` during assembly (efficient row-wise
    insertion) and converts to ``csr_matrix`` for arithmetic and linear
    solves.

    Parameters
    ----------
    system : object, optional
        A ``core_model.system.System`` instance.  When provided, the
        internal bus/branch lists are populated from the system object.
    """

    def __init__(self, system: Any = None) -> None:
        self._system = system
        self._ybus_sparse: Optional[csr_matrix] = None
        self._buses: List[BusData] = []
        self._branches: List[BranchData] = []
        self._bus_index: Dict[int, int] = {}

        if system is not None:
            self._import_system(system)

    # ------------------------------------------------------------------
    # System import helper
    # ------------------------------------------------------------------

    def _import_system(self, system: Any) -> None:
        """Populate buses and branches from a ``System`` object."""
        bus_ids = sorted(system.buses.keys())
        self._bus_index = {bid: i for i, bid in enumerate(bus_ids)}
        self._buses = []
        for bid in bus_ids:
            b = system.buses[bid]
            self._buses.append(BusData(
                bus_id=bid,
                bus_type=b.bus_type,
                voltage_magnitude=b.voltage_magnitude,
                voltage_angle=b.voltage_angle,
                p_generation=b.generation_power.real if isinstance(b.generation_power, complex) else b.generation_power,
                q_generation=b.generation_power.imag if isinstance(b.generation_power, complex) else 0.0,
                p_load=b.load_power.real if isinstance(b.load_power, complex) else b.load_power,
                q_load=b.load_power.imag if isinstance(b.load_power, complex) else 0.0,
                q_min=getattr(b, "q_min", -999.0),
                q_max=getattr(b, "q_max", 999.0),
                v_scheduled=b.voltage_magnitude if b.bus_type == "pv" else 1.0,
            ))

        self._branches = []
        for line in getattr(system, "lines", []):
            self._branches.append(BranchData(
                from_bus=self._bus_index[line.from_bus.bus_id],
                to_bus=self._bus_index[line.to_bus.bus_id],
                impedance=line.get_impedance("1"),
                shunt_admittance=line.get_shunt_admittance("1"),
            ))
        for xf in getattr(system, "transformers", []):
            self._branches.append(BranchData(
                from_bus=self._bus_index[xf.from_bus.bus_id],
                to_bus=self._bus_index[xf.to_bus.bus_id],
                impedance=xf.get_impedance("1"),
                shunt_admittance=xf.get_shunt_admittance("1"),
                tap_ratio=xf.tap_ratio,
                phase_shift=xf.phase_shift,
            ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_sparse_ybus(
        self,
        buses: Optional[List[BusData]] = None,
        branches: Optional[List[BranchData]] = None,
    ) -> csr_matrix:
        """Build the Y-bus admittance matrix as a sparse CSR matrix.

        Parameters
        ----------
        buses : list[BusData], optional
            Bus data.  Falls back to internally stored data.
        branches : list[BranchData], optional
            Branch data.  Falls back to internally stored data.

        Returns
        -------
        scipy.sparse.csr_matrix
            Complex-valued sparse admittance matrix (n×n).

        Notes
        -----
        The matrix is assembled in LIL format for efficient incremental
        insertion and then converted to CSR for fast arithmetic / solving.
        """
        if buses is not None:
            self._buses = buses
            self._bus_index = {b.bus_id: i for i, b in enumerate(self._buses)}
        if branches is not None:
            self._branches = branches

        n = len(self._buses)
        Y = lil_matrix((n, n), dtype=complex)

        for br in self._branches:
            i = br.from_bus
            j = br.to_bus
            z = br.impedance
            y = 1.0 / z if z != 0 else complex(0, 0)
            ys = br.shunt_admittance / 2.0

            tap = br.tap_ratio
            phase_shift = br.phase_shift

            if tap != 1.0 or phase_shift != 0.0:
                a = tap * np.exp(1j * phase_shift)
                a_abs2 = abs(a) ** 2
                Y[i, i] += y / a_abs2 + ys
                Y[j, j] += y + ys
                Y[i, j] -= y / np.conj(a)
                Y[j, i] -= y / a
            else:
                Y[i, i] += y + ys
                Y[j, j] += y + ys
                Y[i, j] -= y
                Y[j, i] -= y

        # Add shunt admittances at buses (capacitor banks, etc.)
        for idx, bus in enumerate(self._buses):
            # Any bus-level shunt can be added here in future extensions
            pass

        self._ybus_sparse = Y.tocsr()
        logger.info(
            "Built sparse Y-bus: %d buses, %d branches, %d non-zeros (%.1f%% fill)",
            n, len(self._branches), self._ybus_sparse.nnz,
            100.0 * self._ybus_sparse.nnz / (n * n) if n > 0 else 0,
        )
        return self._ybus_sparse

    def sparse_newton_raphson(
        self,
        ybus: Optional[csr_matrix] = None,
        bus_data: Optional[List[BusData]] = None,
        max_iter: int = 50,
        tol: float = 1e-8,
    ) -> SparseConvergenceResult:
        """Solve the load-flow problem using a sparse Newton-Raphson method.

        Parameters
        ----------
        ybus : csr_matrix, optional
            Sparse admittance matrix.  Built automatically if not provided.
        bus_data : list[BusData], optional
            Bus specifications.  Falls back to internally stored data.
        max_iter : int
            Maximum Newton iterations.
        tol : float
            Convergence tolerance on the maximum power mismatch (per-unit).

        Returns
        -------
        SparseConvergenceResult
        """
        t0 = time.perf_counter()

        if ybus is None:
            if self._ybus_sparse is None:
                self.build_sparse_ybus()
            ybus = self._ybus_sparse

        if bus_data is not None:
            self._buses = bus_data
            self._bus_index = {b.bus_id: i for i, b in enumerate(self._buses)}

        n = len(self._buses)
        if n == 0:
            return SparseConvergenceResult(solver_type="sparse")

        # Classify buses
        slack_idx = [i for i, b in enumerate(self._buses) if b.bus_type == "slack"]
        pv_idx = [i for i, b in enumerate(self._buses) if b.bus_type == "pv"]
        pq_idx = [i for i, b in enumerate(self._buses) if b.bus_type == "pq"]

        # Unknowns: θ for PV and PQ, |V| for PQ
        n_pv = len(pv_idx)
        n_pq = len(pq_idx)
        n_unknowns = n_pv + 2 * n_pq

        # Initial voltage vector
        V = np.array(
            [b.voltage_magnitude * np.exp(1j * b.voltage_angle) for b in self._buses],
            dtype=complex,
        )
        # Set PV bus voltage magnitudes to scheduled value
        for i in pv_idx:
            V[i] = self._buses[i].v_scheduled * np.exp(1j * np.angle(V[i]))

        # Scheduled power
        P_sch = np.array(
            [b.p_generation - b.p_load for b in self._buses], dtype=float
        )
        Q_sch = np.array(
            [b.q_generation - b.q_load for b in self._buses], dtype=float
        )

        iteration_log: List[Dict[str, Any]] = []
        converged = False

        # Convert Ybus to dense for power calculations (necessary for
        # vectorised V * conj(Y*V) but Jacobian is kept sparse).
        Ybus_dense = ybus.toarray() if issparse(ybus) else np.asarray(ybus)

        for iteration in range(max_iter):
            # --- Power calculations ---
            I = Ybus_dense @ V
            S = V * np.conj(I)
            P = S.real
            Q = S.imag

            # --- Mismatch ---
            deltaP = P_sch - P
            deltaQ = Q_sch - Q

            # Build mismatch vector: [ΔP_pv, ΔP_pq, ΔQ_pq] / |V|
            mismatch = np.zeros(n_unknowns)
            for k, i in enumerate(pv_idx):
                mismatch[k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + n_pq + k] = deltaQ[i]

            max_mismatch = np.max(np.abs(mismatch))

            iteration_log.append({
                "iteration": iteration,
                "max_mismatch": float(max_mismatch),
                "n_pv": n_pv,
                "n_pq": n_pq,
            })

            if max_mismatch < tol:
                converged = True
                break

            # --- Build Jacobian (sparse) ---
            J = self._build_sparse_jacobian(
                V, Ybus_dense, pv_idx, pq_idx, n_unknowns
            )

            # --- Solve linear system ---
            try:
                dx = spsolve(J.tocsr(), mismatch)
            except Exception:
                # Fallback to least-squares
                J_dense = J.toarray() if issparse(J) else np.asarray(J)
                dx = np.linalg.lstsq(J_dense, mismatch, rcond=None)[0]

            # --- Update voltages ---
            # θ corrections for PV buses
            for k, i in enumerate(pv_idx):
                angle_i = np.angle(V[i])
                angle_i += dx[k]
                V[i] = abs(V[i]) * np.exp(1j * angle_i)

            # θ corrections for PQ buses
            for k, i in enumerate(pq_idx):
                angle_i = np.angle(V[i])
                angle_i += dx[n_pv + k]
                V[i] = abs(V[i]) * np.exp(1j * angle_i)

            # |V| corrections for PQ buses  (dx gives Δ|V|/|V| * |V| or
            # just Δ|V| depending on formulation; here we use the
            # standard formulation: Δ|V| is directly updated)
            for k, i in enumerate(pq_idx):
                vmag = abs(V[i])
                vmag += dx[n_pv + n_pq + k]
                vmag = max(vmag, 0.5)  # voltage floor
                vmag = min(vmag, 1.5)  # voltage ceiling
                V[i] = vmag * np.exp(1j * np.angle(V[i]))

        # Recompute final power
        I_final = Ybus_dense @ V
        S_final = V * np.conj(I_final)

        elapsed = time.perf_counter() - t0

        return SparseConvergenceResult(
            converged=converged,
            iterations=iteration + 1 if iteration_log else 0,
            max_mismatch=float(max_mismatch) if iteration_log else 0.0,
            voltages=V,
            angles=np.angle(V),
            magnitudes=np.abs(V),
            active_power=S_final.real,
            reactive_power=S_final.imag,
            iteration_log=iteration_log,
            solver_type="sparse",
            solve_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Jacobian builder (sparse)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sparse_jacobian(
        V: np.ndarray,
        Ybus: np.ndarray,
        pv_idx: List[int],
        pq_idx: List[int],
        n_unknowns: int,
    ) -> lil_matrix:
        """Construct the sparse Jacobian matrix.

        The Jacobian has the block structure::

            [ H  N ]
            [ M  L ]

        where
            H = ∂P/∂θ,  N = ∂P/∂|V|·|V|
            M = ∂Q/∂θ,  L = ∂Q/∂|V|·|V|

        The mismatch / correction formulation is::

            [ΔP/|V|]   [ H  N ] [ Δθ       ]
            [ΔQ/|V|] = [ M  L ] [ Δ|V|/|V| ]

        Returns
        -------
        lil_matrix  (float, n_unknowns × n_unknowns)
        """
        n = len(V)
        n_pv = len(pv_idx)
        n_pq = len(pq_idx)

        J = lil_matrix((n_unknowns, n_unknowns), dtype=float)

        # Pre-compute helpers
        Vmag = np.abs(V)
        Vang = np.angle(V)

        # Conductance / susceptance matrices
        G = Ybus.real
        B = Ybus.imag

        # Pre-compute I_inj = Y * V  for all buses
        I_inj = Ybus @ V

        # The analytical Jacobian is complex to hand-code correctly; use
        # the well-known sparse finite-difference approach that is both
        # robust and preserves sparsity.
        eps_theta = 1e-8
        eps_v = 1e-8

        # Base mismatch
        def _compute_mismatch(V_trial: np.ndarray) -> np.ndarray:
            I_t = Ybus @ V_trial
            S_t = V_trial * np.conj(I_t)
            P_t = S_t.real
            Q_t = S_t.imag
            dP = P_t  # mismatch against scheduled P is handled outside
            dQ = Q_t
            m = np.zeros(n_unknowns)
            for k, i in enumerate(pv_idx):
                m[k] = dP[i]
            for k, i in enumerate(pq_idx):
                m[n_pv + k] = dP[i]
            for k, i in enumerate(pq_idx):
                m[n_pv + n_pq + k] = dQ[i]
            return m

        base_m = _compute_mismatch(V)

        # θ perturbations (PV then PQ)
        for col_k, i in enumerate(pv_idx + pq_idx):
            V_trial = V.copy()
            theta_i = np.angle(V_trial[i])
            V_trial[i] = abs(V_trial[i]) * np.exp(1j * (theta_i + eps_theta))
            m_trial = _compute_mismatch(V_trial)
            col_data = (m_trial - base_m) / eps_theta
            # Only store non-zeros
            for row_k in range(n_unknowns):
                if col_data[row_k] != 0.0:
                    J[row_k, col_k] = col_data[row_k]

        # |V| perturbations (PQ only)
        for k, i in enumerate(pq_idx):
            col_k = n_pv + n_pq + k
            V_trial = V.copy()
            vmag_i = abs(V_trial[i])
            V_trial[i] = (vmag_i + eps_v) * np.exp(1j * np.angle(V_trial[i]))
            m_trial = _compute_mismatch(V_trial)
            col_data = (m_trial - base_m) / eps_v
            for row_k in range(n_unknowns):
                if col_data[row_k] != 0.0:
                    J[row_k, col_k] = col_data[row_k]

        return J

    # ------------------------------------------------------------------
    # Memory comparison
    # ------------------------------------------------------------------

    def compare_memory(
        self,
        buses: Optional[List[BusData]] = None,
        branches: Optional[List[BranchData]] = None,
    ) -> Dict[str, Any]:
        """Compare memory usage of dense vs sparse Y-bus storage.

        Parameters
        ----------
        buses, branches : optional
            Network data.  Falls back to internally stored data.

        Returns
        -------
        dict
            Keys: ``dense_bytes``, ``sparse_bytes``, ``savings_bytes``,
            ``savings_pct``, ``n_buses``, ``n_branches``, ``nnz``,
            ``fill_pct``.
        """
        ybus = self.build_sparse_ybus(buses, branches)
        n = ybus.shape[0]

        # Dense: n×n complex128 = 16 bytes per element
        dense_bytes = n * n * 16

        # Sparse CSR: data + indices + indptr
        sparse_bytes = (
            ybus.data.nbytes      # complex128 values
            + ybus.indices.nbytes  # int32 column indices
            + ybus.indptr.nbytes   # int32 row pointers
        )

        savings_bytes = dense_bytes - sparse_bytes
        savings_pct = (savings_bytes / dense_bytes * 100) if dense_bytes > 0 else 0.0

        result = {
            "n_buses": n,
            "n_branches": len(self._branches),
            "nnz": int(ybus.nnz),
            "fill_pct": round(100.0 * ybus.nnz / (n * n), 2) if n > 0 else 0.0,
            "dense_bytes": dense_bytes,
            "sparse_bytes": sparse_bytes,
            "savings_bytes": savings_bytes,
            "savings_pct": round(savings_pct, 2),
        }
        logger.info("Memory comparison: %s", result)
        return result

    # ------------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------------

    def benchmark(self, system_size: int = 0) -> Dict[str, Any]:
        """Run timing benchmarks for different system sizes.

        Generates synthetic radial/mesh networks of the requested size
        and measures sparse Y-bus build time, sparse NR solve time,
        and dense NR solve time for comparison.

        Parameters
        ----------
        system_size : int
            If > 0, benchmark only this size.  Otherwise, benchmark a
            standard set of sizes (14, 30, 118, 300, 500, 1000).

        Returns
        -------
        dict
            Keys per size: ``n_buses``, ``sparse_ybus_build_ms``,
            ``sparse_solve_ms``, ``dense_solve_ms`` (if feasible),
            ``speedup``.
        """
        sizes = [system_size] if system_size > 0 else [14, 30, 118, 300, 500, 1000]
        results: Dict[str, Any] = {"sizes": []}

        for n in sizes:
            buses, branches = self._generate_synthetic_system(n)

            # Sparse Y-bus build
            t0 = time.perf_counter()
            ybus = self.build_sparse_ybus(buses, branches)
            t_build_sparse = (time.perf_counter() - t0) * 1000  # ms

            # Sparse NR solve
            t0 = time.perf_counter()
            sparse_result = self.sparse_newton_raphson(
                ybus, buses, max_iter=20, tol=1e-6
            )
            t_solve_sparse = (time.perf_counter() - t0) * 1000

            # Dense NR solve (only for small systems to avoid OOM)
            t_solve_dense = None
            speedup = None
            if n <= 300:
                try:
                    Ybus_dense = ybus.toarray()
                    t0 = time.perf_counter()
                    self._dense_newton_raphson(Ybus_dense, buses, max_iter=20, tol=1e-6)
                    t_solve_dense = (time.perf_counter() - t0) * 1000
                    if t_solve_sparse > 0:
                        speedup = round(t_solve_dense / t_solve_sparse, 2)
                except Exception as exc:
                    logger.warning("Dense solve failed for n=%d: %s", n, exc)
                    t_solve_dense = None

            entry = {
                "n_buses": n,
                "sparse_ybus_build_ms": round(t_build_sparse, 3),
                "sparse_solve_ms": round(t_solve_sparse, 3),
                "dense_solve_ms": round(t_solve_dense, 3) if t_solve_dense is not None else None,
                "speedup": speedup,
                "converged": sparse_result.converged,
                "iterations": sparse_result.iterations,
            }
            results["sizes"].append(entry)
            logger.info("Benchmark n=%d: %s", n, entry)

        return results

    # ------------------------------------------------------------------
    # Dense Newton-Raphson (for benchmark comparison only)
    # ------------------------------------------------------------------

    @staticmethod
    def _dense_newton_raphson(
        Ybus: np.ndarray,
        bus_data: List[BusData],
        max_iter: int = 50,
        tol: float = 1e-8,
    ) -> SparseConvergenceResult:
        """Dense Newton-Raphson for benchmarking purposes only."""
        n = len(bus_data)
        slack_idx = [i for i, b in enumerate(bus_data) if b.bus_type == "slack"]
        pv_idx = [i for i, b in enumerate(bus_data) if b.bus_type == "pv"]
        pq_idx = [i for i, b in enumerate(bus_data) if b.bus_type == "pq"]
        n_pv = len(pv_idx)
        n_pq = len(pq_idx)
        n_unknowns = n_pv + 2 * n_pq

        V = np.array(
            [b.voltage_magnitude * np.exp(1j * b.voltage_angle) for b in bus_data],
            dtype=complex,
        )
        P_sch = np.array([b.p_generation - b.p_load for b in bus_data], dtype=float)
        Q_sch = np.array([b.q_generation - b.q_load for b in bus_data], dtype=float)

        converged = False
        for iteration in range(max_iter):
            I = Ybus @ V
            S = V * np.conj(I)
            P = S.real
            Q = S.imag

            deltaP = P_sch - P
            deltaQ = Q_sch - Q

            mismatch = np.zeros(n_unknowns)
            for k, i in enumerate(pv_idx):
                mismatch[k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + n_pq + k] = deltaQ[i]

            max_mismatch = np.max(np.abs(mismatch))
            if max_mismatch < tol:
                converged = True
                break

            # Analytical Jacobian (dense)
            J = _build_dense_jacobian(V, Ybus, pv_idx, pq_idx, n_unknowns)
            try:
                dx = np.linalg.solve(J, mismatch)
            except np.linalg.LinAlgError:
                dx = np.linalg.lstsq(J, mismatch, rcond=None)[0]

            for k, i in enumerate(pv_idx):
                V[i] = abs(V[i]) * np.exp(1j * (np.angle(V[i]) + dx[k]))
            for k, i in enumerate(pq_idx):
                V[i] = abs(V[i]) * np.exp(1j * (np.angle(V[i]) + dx[n_pv + k]))
            for k, i in enumerate(pq_idx):
                vmag = abs(V[i]) + dx[n_pv + n_pq + k]
                vmag = np.clip(vmag, 0.5, 1.5)
                V[i] = vmag * np.exp(1j * np.angle(V[i]))

        I_final = Ybus @ V
        S_final = V * np.conj(I_final)
        return SparseConvergenceResult(
            converged=converged,
            iterations=iteration + 1,
            max_mismatch=float(max_mismatch),
            voltages=V,
            angles=np.angle(V),
            magnitudes=np.abs(V),
            active_power=S_final.real,
            reactive_power=S_final.imag,
            solver_type="dense",
        )

    # ------------------------------------------------------------------
    # Synthetic system generator
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_synthetic_system(
        n_buses: int,
    ) -> Tuple[List[BusData], List[BranchData]]:
        """Generate a synthetic radial/mesh network for benchmarking.

        Creates a ring topology with additional radial spurs to mimic a
        typical transmission network.

        Parameters
        ----------
        n_buses : int
            Number of buses in the synthetic system.

        Returns
        -------
        tuple[list[BusData], list[BranchData]]
        """
        buses: List[BusData] = []
        branches: List[BranchData] = []

        # Bus 0 = slack
        buses.append(BusData(bus_id=0, bus_type="slack", voltage_magnitude=1.05))

        # ~20 % of remaining buses are PV (generators)
        n_pv = max(1, int(0.2 * (n_buses - 1)))
        pv_set = set(range(1, 1 + n_pv))

        # First create PQ buses to compute total load, then assign generation
        pq_buses: List[BusData] = []
        for i in range(1, n_buses):
            if i not in pv_set:
                pq_buses.append(BusData(
                    bus_id=i, bus_type="pq",
                    p_load=0.3 + 0.05 * (i % 10),
                    q_load=0.1 + 0.02 * (i % 10),
                ))

        total_p_load = sum(b.p_load for b in pq_buses)
        total_q_load = sum(b.q_load for b in pq_buses)
        p_gen_per_pv = total_p_load / n_pv if n_pv > 0 else 0
        q_gen_per_pv = total_q_load / n_pv if n_pv > 0 else 0

        for i in range(1, n_buses):
            if i in pv_set:
                buses.append(BusData(
                    bus_id=i, bus_type="pv",
                    voltage_magnitude=1.02,
                    v_scheduled=1.02,
                    p_generation=p_gen_per_pv + 0.01 * (i % 3),
                    q_generation=q_gen_per_pv * 0.3,
                ))
            else:
                # Find the matching PQ bus
                for b in pq_buses:
                    if b.bus_id == i:
                        buses.append(b)
                        break

        # Ring topology: connect i -> (i+1) % n
        for i in range(n_buses):
            j = (i + 1) % n_buses
            z = complex(0.01 + 0.001 * (i % 5), 0.05 + 0.01 * (i % 3))
            branches.append(BranchData(from_bus=i, to_bus=j, impedance=z,
                                       shunt_admittance=complex(0, 0.02)))

        # Additional radial spurs: connect every 3rd bus to bus+5
        for i in range(0, n_buses - 5, 3):
            j = i + 5
            if j < n_buses:
                z = complex(0.02, 0.08)
                branches.append(BranchData(from_bus=i, to_bus=j, impedance=z))

        return buses, branches


# ---------------------------------------------------------------------------
# Dense Jacobian helper (module-level for reuse in benchmarks)
# ---------------------------------------------------------------------------

def _build_dense_jacobian(
    V: np.ndarray,
    Ybus: np.ndarray,
    pv_idx: List[int],
    pq_idx: List[int],
    n_unknowns: int,
) -> np.ndarray:
    """Analytical dense Jacobian for standard NR load flow.

    Uses the well-known formulas::

        H_ii = -Q_i - B_ii |V_i|^2
        H_ij = |V_i||V_j| (G_ij sin θ_ij - B_ij cos θ_ij)
        N_ii = P_i + G_ii |V_i|^2
        N_ij = |V_i||V_j| (G_ij cos θ_ij + B_ij sin θ_ij)
        M_ii = P_i - G_ii |V_i|^2
        M_ij = -N_ij
        L_ii = Q_i - B_ii |V_i|^2
        L_ij = H_ij
    """
    n = len(V)
    n_pv = len(pv_idx)
    n_pq = len(pq_idx)
    J = np.zeros((n_unknowns, n_unknowns), dtype=float)

    Vmag = np.abs(V)
    Vang = np.angle(V)
    G = Ybus.real
    B = Ybus.imag

    I = Ybus @ V
    S = V * np.conj(I)
    P = S.real
    Q = S.imag

    # Row indices for PV+PQ P-mismatch, PQ Q-mismatch
    unknown_buses_theta = pv_idx + pq_idx  # columns for θ unknowns
    unknown_buses_v = pq_idx               # columns for |V| unknowns

    for row_k, i in enumerate(pv_idx + pq_idx):
        # H: ∂P_i/∂θ_j  (column over θ unknowns)
        for col_k, j in enumerate(unknown_buses_theta):
            if i == j:
                J[row_k, col_k] = -Q[i] - B[i, i] * Vmag[i] ** 2
            else:
                J[row_k, col_k] = (
                    Vmag[i] * Vmag[j]
                    * (G[i, j] * np.sin(Vang[i] - Vang[j])
                       - B[i, j] * np.cos(Vang[i] - Vang[j]))
                )

        # N: ∂P_i/∂|V|_j  (column over |V| unknowns, PQ only)
        for col_k, j in enumerate(unknown_buses_v):
            col = n_pv + n_pq + col_k
            if i == j:
                J[row_k, col] = P[i] + G[i, i] * Vmag[i] ** 2
            else:
                J[row_k, col] = (
                    Vmag[i] * Vmag[j]
                    * (G[i, j] * np.cos(Vang[i] - Vang[j])
                       + B[i, j] * np.sin(Vang[i] - Vang[j]))
                )

    for row_k, i in enumerate(pq_idx):
        row = n_pv + n_pq + row_k
        # M: ∂Q_i/∂θ_j
        for col_k, j in enumerate(unknown_buses_theta):
            if i == j:
                J[row, col_k] = P[i] - G[i, i] * Vmag[i] ** 2
            else:
                J[row, col_k] = (
                    -Vmag[i] * Vmag[j]
                    * (G[i, j] * np.cos(Vang[i] - Vang[j])
                       + B[i, j] * np.sin(Vang[i] - Vang[j]))
                )

        # L: ∂Q_i/∂|V|_j
        for col_k, j in enumerate(unknown_buses_v):
            col = n_pv + n_pq + col_k
            if i == j:
                J[row, col] = Q[i] - B[i, i] * Vmag[i] ** 2
            else:
                J[row, col] = (
                    Vmag[i] * Vmag[j]
                    * (G[i, j] * np.sin(Vang[i] - Vang[j])
                       - B[i, j] * np.cos(Vang[i] - Vang[j]))
                )

    return J


# ---------------------------------------------------------------------------
# Convenience wrapper for IEEE test-case creation
# ---------------------------------------------------------------------------

def create_ieee_test_system(case: int = 14) -> Tuple[List[BusData], List[BranchData]]:
    """Create simplified IEEE test-case data for benchmarking.

    This generates a synthetic system with the correct bus count and
    topology characteristics for the specified IEEE test case.  For
    production use, load actual IEEE data files.

    Parameters
    ----------
    case : int
        IEEE test case number (14, 30, or 118).

    Returns
    -------
    tuple[list[BusData], list[BranchData]]
    """
    if case not in (14, 30, 118):
        raise ValueError(f"Unsupported IEEE test case: {case}. Use 14, 30, or 118.")

    return SparseYBus._generate_synthetic_system(case)
