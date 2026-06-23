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
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

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
        self._ybus_sparse: csr_matrix | None = None
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
            self._buses.append(
                BusData(
                    bus_id=bid,
                    bus_type=b.bus_type,
                    voltage_magnitude=b.voltage_magnitude,
                    voltage_angle=b.voltage_angle,
                    p_generation=b.generation_power.real
                    if isinstance(b.generation_power, complex)
                    else b.generation_power,
                    q_generation=b.generation_power.imag
                    if isinstance(b.generation_power, complex)
                    else 0.0,
                    p_load=b.load_power.real if isinstance(b.load_power, complex) else b.load_power,
                    q_load=b.load_power.imag if isinstance(b.load_power, complex) else 0.0,
                    q_min=getattr(b, "q_min", -999.0),
                    q_max=getattr(b, "q_max", 999.0),
                    v_scheduled=b.voltage_magnitude if b.bus_type == "pv" else 1.0,
                )
            )

        self._branches = []
        for line in getattr(system, "lines", []):
            self._branches.append(
                BranchData(
                    from_bus=self._bus_index[line.from_bus.bus_id],
                    to_bus=self._bus_index[line.to_bus.bus_id],
                    impedance=line.get_impedance("1"),
                    shunt_admittance=line.get_shunt_admittance("1"),
                )
            )
        for xf in getattr(system, "transformers", []):
            self._branches.append(
                BranchData(
                    from_bus=self._bus_index[xf.from_bus.bus_id],
                    to_bus=self._bus_index[xf.to_bus.bus_id],
                    impedance=xf.get_impedance("1"),
                    shunt_admittance=xf.get_shunt_admittance("1"),
                    tap_ratio=xf.tap_ratio,
                    phase_shift=xf.phase_shift,
                )
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_sparse_ybus(
        self,
        buses: List[BusData] | None = None,
        branches: List[BranchData] | None = None,
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
        for _idx, _bus in enumerate(self._buses):
            # Any bus-level shunt can be added here in future extensions
            pass

        self._ybus_sparse = Y.tocsr()
        logger.info(
            "Built sparse Y-bus: %d buses, %d branches, %d non-zeros (%.1f%% fill)",
            n,
            len(self._branches),
            self._ybus_sparse.nnz,
            100.0 * self._ybus_sparse.nnz / (n * n) if n > 0 else 0,
        )
        return self._ybus_sparse

    def sparse_newton_raphson(
        self,
        ybus: csr_matrix | None = None,
        bus_data: List[BusData] | None = None,
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
        [i for i, b in enumerate(self._buses) if b.bus_type == "slack"]
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
        P_sch = np.array([b.p_generation - b.p_load for b in self._buses], dtype=float)
        Q_sch = np.array([b.q_generation - b.q_load for b in self._buses], dtype=float)

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

            iteration_log.append(
                {
                    "iteration": iteration,
                    "max_mismatch": float(max_mismatch),
                    "n_pv": n_pv,
                    "n_pq": n_pq,
                }
            )

            if max_mismatch < tol:
                converged = True
                break

            # --- Build Jacobian (sparse) ---
            # The analytical Jacobian computes d(mismatch)/dx where
            # mismatch = [\u0394P, \u0394Q] = [P_sch - P_calc, Q_sch - Q_calc].
            # The Newton-Raphson step is J * \u0394x = -mismatch, so
            # we negate the RHS to match the d(mismatch)/dx formulation.
            J = self._build_sparse_jacobian(V, Ybus_dense, pv_idx, pq_idx, n_unknowns)

            # --- Solve linear system ---
            try:
                dx = spsolve(J.tocsr(), -mismatch)
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
        """Construct the sparse Jacobian matrix analytically.

        Uses the closed-form Newton-Raphson Jacobian formulas directly from
        the Y-bus elements, avoiding the O(n·n_unknowns) mismatch evaluations
        required by the previous finite-difference approach.

        The Jacobian has the block structure (mismatch formulation):

            [ \u0394P_pv ]   [ J1  J2 ] [ \u0394\u03b8 ]
            [ \u0394P_pq ] = [ J1  J2 ] [ \u0394\u03b8 ]
            [ \u0394Q_pq ]   [ J3  J4 ] [ \u0394|V| ]

        where all submatrices are derivatives of the **mismatch**
        m = [\u0394P, \u0394Q] = [P_sch \u2212 P_calc, Q_sch \u2212 Q_calc],
        not of P_calc / Q_calc directly.

        Formulas (from Grainger & Stevenson, Kundur):

            J1 diag:    Q_i + B_ii|V_i|\u00b2
            J1 off:    \u2212|V_i||V_j|(G_ij sin \u03b8_ij \u2212 B_ij cos \u03b8_ij)

            J2 diag:   \u2212P_i/|V_i| \u2212 G_ii|V_i|
            J2 off:    \u2212|V_i|(G_ij cos \u03b8_ij + B_ij sin \u03b8_ij)

            J3 diag:   \u2212P_i + G_ii|V_i|\u00b2
            J3 off:     |V_i||V_j|(G_ij cos \u03b8_ij + B_ij sin \u03b8_ij)

            J4 diag:   \u2212Q_i/|V_i| + B_ii|V_i|
            J4 off:    \u2212|V_i|(G_ij sin \u03b8_ij \u2212 B_ij cos \u03b8_ij)

        Returns
        -------
        lil_matrix  (float, n_unknowns \u00d7 n_unknowns)
        """
        n_pv = len(pv_idx)
        n_pq = len(pq_idx)

        n = len(V)
        J = lil_matrix((n_unknowns, n_unknowns), dtype=float)

        # Precompute intermediates for the analytical formulas
        Vmag = np.abs(V)
        Vang = np.angle(V)
        G = Ybus.real
        B = Ybus.imag

        # Angle differences (n x n matrix)
        theta = Vang[:, np.newaxis] - Vang[np.newaxis, :]
        sin_theta = np.sin(theta)
        cos_theta = np.cos(theta)

        # Voltage products
        V_i = Vmag[:, np.newaxis]  # (n, 1)
        V_j = Vmag[np.newaxis, :]  # (1, n)
        V_i_V_j = V_i * V_j  # (n, n)

        # Current power injections
        I = Ybus @ V
        S = V * np.conj(I)
        P = S.real
        Q = S.imag

        # Column indexing helpers
        n_th_cols = n_pv + n_pq
        row_buses = pv_idx + pq_idx  # \u0394P rows
        th_col_buses = pv_idx + pq_idx  # \u0394\u03b8 columns
        vm_col_buses = pq_idx  # \u0394|V| columns

        # Precomputed products (vectorised, no Python loops over n\u00b2)
        GS_minus_BC = G * sin_theta - B * cos_theta  # G_ij sin theta_ij - B_ij cos theta_ij
        GS_minus_BC[np.arange(n), np.arange(n)] = 0.0  # zero diagonal for off-diag formulas

        GC_plus_BS = G * cos_theta + B * sin_theta  # G_ij cos theta_ij + B_ij sin theta_ij
        GC_plus_BS[np.arange(n), np.arange(n)] = 0.0

        # Diagonals
        B_diag = B.diagonal()
        G_diag = G.diagonal()
        V2 = Vmag**2

        # ---- J1: d\u0394P/d\u03b8 ----
        # Row indices: 0..n_pv+n_pq-1  (all \u0394P rows)
        # Col indices: 0..n_pv+n_pq-1  (all \u03b8 unknowns)
        for ri, bus_i in enumerate(row_buses):
            for ci, bus_k in enumerate(th_col_buses):
                if bus_i == bus_k:
                    J[ri, ci] = Q[bus_i] + B_diag[bus_i] * V2[bus_i]
                else:
                    J[ri, ci] = -V_i_V_j[bus_i, bus_k] * GS_minus_BC[bus_i, bus_k]

        # ---- J2: d\u0394P/d|V| ----
        # Col offset: n_pv + n_pq
        for ri, bus_i in enumerate(row_buses):
            for ci, bus_k in enumerate(vm_col_buses):
                col = n_th_cols + ci
                if bus_i == bus_k:
                    J[ri, col] = -P[bus_i] / Vmag[bus_i] - G_diag[bus_i] * Vmag[bus_i]
                else:
                    J[ri, col] = -V_i[bus_i, 0] * GC_plus_BS[bus_i, bus_k]

        # ---- J3: d\u0394Q/d\u03b8 ----
        # Row offset: n_pv + n_pq
        q_row_offset = n_pv + n_pq
        for ri, bus_i in enumerate(pq_idx):
            row = q_row_offset + ri
            for ci, bus_k in enumerate(th_col_buses):
                if bus_i == bus_k:
                    J[row, ci] = -P[bus_i] + G_diag[bus_i] * V2[bus_i]
                else:
                    J[row, ci] = V_i_V_j[bus_i, bus_k] * GC_plus_BS[bus_i, bus_k]

        # ---- J4: d\u0394Q/d|V| ----
        for ri, bus_i in enumerate(pq_idx):
            row = q_row_offset + ri
            for ci, bus_k in enumerate(vm_col_buses):
                col = n_th_cols + ci
                if bus_i == bus_k:
                    J[row, col] = -Q[bus_i] / Vmag[bus_i] + B_diag[bus_i] * Vmag[bus_i]
                else:
                    J[row, col] = -V_i[bus_i, 0] * GS_minus_BC[bus_i, bus_k]

        return J

    # ------------------------------------------------------------------
    # Memory comparison
    # ------------------------------------------------------------------

    def compare_memory(
        self,
        buses: List[BusData] | None = None,
        branches: List[BranchData] | None = None,
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
            ybus.data.nbytes  # complex128 values
            + ybus.indices.nbytes  # int32 column indices
            + ybus.indptr.nbytes  # int32 row pointers
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
            sparse_result = self.sparse_newton_raphson(ybus, buses, max_iter=20, tol=1e-6)
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
        len(bus_data)
        [i for i, b in enumerate(bus_data) if b.bus_type == "slack"]
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
        for _iteration in range(max_iter):
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
            iterations=_iteration + 1,
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
                pq_buses.append(
                    BusData(
                        bus_id=i,
                        bus_type="pq",
                        p_load=0.3 + 0.05 * (i % 10),
                        q_load=0.1 + 0.02 * (i % 10),
                    )
                )

        total_p_load = sum(b.p_load for b in pq_buses)
        total_q_load = sum(b.q_load for b in pq_buses)
        p_gen_per_pv = total_p_load / n_pv if n_pv > 0 else 0
        q_gen_per_pv = total_q_load / n_pv if n_pv > 0 else 0

        for i in range(1, n_buses):
            if i in pv_set:
                buses.append(
                    BusData(
                        bus_id=i,
                        bus_type="pv",
                        voltage_magnitude=1.02,
                        v_scheduled=1.02,
                        p_generation=p_gen_per_pv + 0.01 * (i % 3),
                        q_generation=q_gen_per_pv * 0.3,
                    )
                )
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
            branches.append(
                BranchData(from_bus=i, to_bus=j, impedance=z, shunt_admittance=complex(0, 0.02))
            )

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
    len(V)
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
    unknown_buses_v = pq_idx  # columns for |V| unknowns

    for row_k, i in enumerate(pv_idx + pq_idx):
        # H: ∂P_i/∂θ_j  (column over θ unknowns)
        for col_k, j in enumerate(unknown_buses_theta):
            if i == j:
                J[row_k, col_k] = -Q[i] - B[i, i] * Vmag[i] ** 2
            else:
                J[row_k, col_k] = (
                    Vmag[i]
                    * Vmag[j]
                    * (G[i, j] * np.sin(Vang[i] - Vang[j]) - B[i, j] * np.cos(Vang[i] - Vang[j]))
                )

        # N: ∂P_i/∂|V|_j  (column over |V| unknowns, PQ only)
        for col_k, j in enumerate(unknown_buses_v):
            col = n_pv + n_pq + col_k
            if i == j:
                J[row_k, col] = P[i] + G[i, i] * Vmag[i] ** 2
            else:
                J[row_k, col] = (
                    Vmag[i]
                    * Vmag[j]
                    * (G[i, j] * np.cos(Vang[i] - Vang[j]) + B[i, j] * np.sin(Vang[i] - Vang[j]))
                )

    for row_k, i in enumerate(pq_idx):
        row = n_pv + n_pq + row_k
        # M: ∂Q_i/∂θ_j
        for col_k, j in enumerate(unknown_buses_theta):
            if i == j:
                J[row, col_k] = P[i] - G[i, i] * Vmag[i] ** 2
            else:
                J[row, col_k] = (
                    -Vmag[i]
                    * Vmag[j]
                    * (G[i, j] * np.cos(Vang[i] - Vang[j]) + B[i, j] * np.sin(Vang[i] - Vang[j]))
                )

        # L: ∂Q_i/∂|V|_j
        for col_k, j in enumerate(unknown_buses_v):
            col = n_pv + n_pq + col_k
            if i == j:
                J[row, col] = Q[i] - B[i, i] * Vmag[i] ** 2
            else:
                J[row, col] = (
                    Vmag[i]
                    * Vmag[j]
                    * (G[i, j] * np.sin(Vang[i] - Vang[j]) - B[i, j] * np.cos(Vang[i] - Vang[j]))
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
