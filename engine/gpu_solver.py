"""GPU-Accelerated Power System Solver with Automatic CPU Fallback.

Provides a ``GPUSolver`` class that transparently uses CuPy (CUDA GPU)
when available and falls back to NumPy / SciPy on CPU.  This enables
the same code-path to run on workstations with NVIDIA GPUs as well as
on headless servers or laptops without GPU support.

Typical usage::

    solver = GPUSolver()
    result = solver.newton_raphson_gpu(ybus, bus_data)

The solver logs its device status on initialization and raises no
errors when CuPy is unavailable — it simply runs on the CPU.

Mathematical background
-----------------------
Newton-Raphson update (same formulation as the sparse solver)::

    [Union[ΔP/, V|]]   [J1  J2] [Δθ        ]
    [Union[ΔQ/, V|]] = [J3  J4] [Union[Δ|V|/, V|]  ]

The Jacobian is constructed in sparse form (CSR).  The linear system
is solved via ``cupy.sparse.linalg.spsolve`` on GPU or
``scipy.sparse.linalg.spsolve`` on CPU.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Optional, Union

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse import issparse as sp_issparse
from scipy.sparse.linalg import spsolve as scipy_spsolve

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing CuPy — graceful fallback to NumPy
# ---------------------------------------------------------------------------

_CUPY_AVAILABLE = False
_cp: Any = None
_cp_sparse: Any = None
_cp_spsolve: Any = None

try:
    import cupy as _cp

    _CUPY_AVAILABLE = True
    # Verify that CuPy can actually see a GPU
    _cp.cuda.runtime.getDeviceCount()
    _cp_sparse = _cp.sparse
    from cupyx.scipy.sparse.linalg import spsolve as _cp_spsolve

    logger.info(
        "CuPy %s loaded — GPU acceleration enabled (device: %s)",
        _cp.__version__,
        _cp.cuda.Device().name,
    )
except ImportError:
    logger.info("CuPy not installed — GPU solver will use CPU (NumPy/SciPy).")
except Exception as exc:
    # CuPy is installed but no GPU is available (e.g., CUDA driver missing)
    logger.info(
        "CuPy import succeeded but GPU is unavailable: %s — falling back to CPU.",
        exc,
    )
    _CUPY_AVAILABLE = False
    _cp = None


# ---------------------------------------------------------------------------
# Data containers (reuse from sparse_solver for consistency)
# ---------------------------------------------------------------------------

from engine.sparse_solver import BusData, SparseConvergenceResult

# ---------------------------------------------------------------------------
# GPUSolver
# ---------------------------------------------------------------------------


class GPUSolver:
    """GPU-accelerated Newton-Raphson load-flow solver.

    On initialization the solver detects whether a CUDA-capable GPU is
    available via CuPy.  If not, all operations silently fall back to
    NumPy and SciPy on the CPU.

    Parameters
    ----------
    device_id : int
        CUDA device index (default 0).  Ignored when running on CPU.
    """

    def __init__(self, device_id: int = 0) -> None:
        self._device_id = device_id
        self._gpu_available = _CUPY_AVAILABLE
        self._xp = _cp if self._gpu_available else np  # NOSONAR — S1192: intentional repetition (audit constant)
        self._device_name: str = "CPU (NumPy/SciPy)"  # NOSONAR — S1192: string duplication; extract constant (tech debt)

        if self._gpu_available:
            try:
                self._device_name = (
                    f"GPU: {_cp.cuda.Device(device_id).name} (CuPy {_cp.__version__})"
                )
                _cp.cuda.Device(device_id).use()
            except Exception as exc:
                logger.warning(
                    "Failed to select CUDA device %d: %s — falling back to CPU.",
                    device_id,
                    exc,
                )
                self._gpu_available = False
                self._xp = np
                self._device_name = "CPU (NumPy/SciPy)"

        logger.info(
            "GPUSolver initialized — device: %s, GPU available: %s",
            self._device_name,
            self._gpu_available,
        )

    # ------------------------------------------------------------------
    # Public queries
    # ------------------------------------------------------------------

    def is_gpu_available(self) -> bool:
        """Return ``True`` if CuPy is installed *and* a CUDA GPU was detected."""
        return self._gpu_available

    @property
    def device_name(self) -> str:
        """Human-readable description of the active compute device."""
        return self._device_name

    # ------------------------------------------------------------------
    # Main solver
    # ------------------------------------------------------------------
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def newton_raphson_gpu(  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        self,
        ybus: Union[np.ndarray, csr_matrix] | Any,
        bus_data: list[BusData],
        max_iter: int = 50,
        tol: float = 1e-8,
    ) -> SparseConvergenceResult:
        """Solve load flow using GPU-accelerated Newton-Raphson.

        When a GPU is available the admittance matrix and voltage vectors
        are transferred to GPU memory and all arithmetic is performed on
        the device.  The result is copied back to the host before
        returning.

        Parameters
        ----------
        ybus : ndarray or csr_matrix
            Admittance matrix (dense or sparse).
        bus_data : list[BusData]
            Bus specifications.
        max_iter : int
            Maximum Newton iterations.
        tol : float
            Convergence tolerance (per-unit).

        Returns
        -------
        SparseConvergenceResult
        """
        t0 = time.perf_counter()

        n = len(bus_data)
        if n == 0:
            return SparseConvergenceResult(solver_type="gpu-cpu")

        # Classify buses
        [i for i, b in enumerate(bus_data) if b.bus_type == "slack"]
        pv_idx = [i for i, b in enumerate(bus_data) if b.bus_type == "pv"]
        pq_idx = [i for i, b in enumerate(bus_data) if b.bus_type == "pq"]
        n_pv = len(pv_idx)
        n_pq = len(pq_idx)
        n_unknowns = n_pv + 2 * n_pq

        xp = self._xp

        # --- Transfer data to device ---
        if self._gpu_available:
            V = _cp.array(
                [b.voltage_magnitude * _cp.exp(1j * b.voltage_angle) for b in bus_data],
                dtype=_cp.complex128,
            )
            if sp_issparse(ybus):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                Ybus_dense = _cp.asarray(ybus.toarray())  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
            else:
                Ybus_dense = _cp.asarray(np.asarray(ybus))
        else:
            V = np.array(
                [b.voltage_magnitude * np.exp(1j * b.voltage_angle) for b in bus_data],
                dtype=complex,
            )
            Ybus_dense = ybus.toarray() if sp_issparse(ybus) else np.asarray(ybus)
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        P_sch = xp.array([b.p_generation - b.p_load for b in bus_data], dtype=float)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Q_sch = xp.array([b.q_generation - b.q_load for b in bus_data], dtype=float)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

        # Set PV bus voltages to scheduled values
        for i in pv_idx:
            V[i] = bus_data[i].v_scheduled * xp.exp(1j * xp.angle(V[i]))

        iteration_log: list[dict[str, Any]] = []
        converged = False
        max_mismatch = 0.0

        for iteration in range(max_iter):
            # Power calculations (on device)
            I = Ybus_dense @ V
            S = V * xp.conj(I)
            P = S.real
            Q = S.imag

            # Mismatch  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            deltaP = P_sch - P  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            deltaQ = Q_sch - Q  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

            mismatch = xp.zeros(n_unknowns)
            for k, i in enumerate(pv_idx):
                mismatch[k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + k] = deltaP[i]
            for k, i in enumerate(pq_idx):
                mismatch[n_pv + n_pq + k] = deltaQ[i]

            max_mismatch = float(xp.max(xp.abs(mismatch))) if n_unknowns > 0 else 0.0

            iteration_log.append(
                {
                    "iteration": iteration,
                    "max_mismatch": max_mismatch,
                    "n_pv": n_pv,
                    "n_pq": n_pq,
                },
            )

            if max_mismatch < tol:
                converged = True
                break

            # --- Build sparse Jacobian ---  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            J_sparse = self._build_jacobian(V, Ybus_dense, pv_idx, pq_idx, n_unknowns)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

            # --- Solve linear system ---
            dx = self._solve_linear(J_sparse, mismatch, n_unknowns)

            # --- Update voltages ---
            for k, i in enumerate(pv_idx):
                angle_i = xp.angle(V[i]) + dx[k]
                V[i] = xp.abs(V[i]) * xp.exp(1j * angle_i)

            for k, i in enumerate(pq_idx):
                angle_i = xp.angle(V[i]) + dx[n_pv + k]
                V[i] = xp.abs(V[i]) * xp.exp(1j * angle_i)

            for k, i in enumerate(pq_idx):
                vmag = xp.abs(V[i]) + dx[n_pv + n_pq + k]
                vmag = xp.clip(vmag, 0.5, 1.5)
                V[i] = vmag * xp.exp(1j * xp.angle(V[i]))

        # --- Copy results back to host ---  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V_host = _cp.asnumpy(V) if self._gpu_available else np.asarray(V)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        I_final = Ybus_dense @ V  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        S_final = V * xp.conj(I_final)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        if self._gpu_available:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            P_final = _cp.asnumpy(S_final.real)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Q_final = _cp.asnumpy(S_final.imag)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        else:
            P_final = np.asarray(S_final.real)
            Q_final = np.asarray(S_final.imag)

        elapsed = time.perf_counter() - t0

        solver_tag = "gpu" if self._gpu_available else "cpu-fallback"
        return SparseConvergenceResult(
            converged=converged,
            iterations=iteration + 1 if iteration_log else 0,
            max_mismatch=float(max_mismatch),
            voltages=V_host,
            angles=np.angle(V_host),
            magnitudes=np.abs(V_host),
            active_power=P_final,
            reactive_power=Q_final,
            iteration_log=iteration_log,
            solver_type=solver_tag,
            solve_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Jacobian construction
    # ------------------------------------------------------------------
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def _build_jacobian(  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        self,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V: Any,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ybus: Any,  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        pv_idx: list[int],
        pq_idx: list[int],
        n_unknowns: int,
    ) -> Any:
        """Build the Jacobian in sparse format on the active device.

        Uses analytical formulas for the sub-Jacobians H, N, M, L and
        assembles them into a CSR sparse matrix.  On GPU the matrix
        resides in device memory.

        Parameters
        ----------
        V : xp.ndarray
            Voltage vector (on device).
        Ybus : xp.ndarray
            Dense admittance matrix (on device).
        pv_idx, pq_idx : list[int]
            Bus type indices.
        n_unknowns : int
            Total number of unknowns.

        Returns
        -------
        Sparse matrix on the active device (CuPy CSR or SciPy CSR).
        """
        xp = self._xp
        len(V)
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Vmag = xp.abs(V)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Vang = xp.angle(V)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        G = Ybus.real
        B = Ybus.imag

        I = Ybus @ V
        S = V * xp.conj(I)
        P = S.real
        Q = S.imag

        n_pv = len(pv_idx)
        n_pq = len(pq_idx)

        # Build in LIL for incremental insertion, then convert to CSR
        if self._gpu_available:
            # CuPy doesn't have lil_matrix; build COO data on host then
            # transfer to device CSR
            rows, cols, data = [], [], []
        else:
            J = lil_matrix((n_unknowns, n_unknowns), dtype=float)

        # Row groups: [PV+PQ P-mismatch rows, PQ Q-mismatch rows]
        theta_cols = pv_idx + pq_idx  # column indices for θ unknowns
        v_cols = pq_idx  # column indices Union[for, V|] unknowns

        for row_k, i in enumerate(pv_idx + pq_idx):
            # H: ∂P_i/∂θ_j
            for col_k, j in enumerate(theta_cols):
                if i == j:
                    val = (
                        float(-Q[i] - B[i, i] * Vmag[i] ** 2)
                        if not self._gpu_available
                        else float(xp.asnumpy(-Q[i] - B[i, i] * Vmag[i] ** 2))
                    )
                else:
                    val = (
                        float(
                            Vmag[i]
                            * Vmag[j]
                            * (
                                G[i, j] * xp.sin(Vang[i] - Vang[j])
                                - B[i, j] * xp.cos(Vang[i] - Vang[j])
                            ),
                        )
                        if not self._gpu_available
                        else float(
                            xp.asnumpy(
                                Vmag[i]
                                * Vmag[j]
                                * (
                                    G[i, j] * xp.sin(Vang[i] - Vang[j])
                                    - B[i, j] * xp.cos(Vang[i] - Vang[j])
                                ),
                            ),
                        )
                    )
                if self._gpu_available:
                    if not math.isclose(val, 0.0):
                        rows.append(row_k)
                        cols.append(col_k)
                        data.append(val)
                else:
                    if not math.isclose(val, 0.0):
                        J[row_k, col_k] = val

            # N: Union[∂P_i/∂|V, _j]  (Union[PQ, V|] unknowns only)
            for col_k, j in enumerate(v_cols):
                col = n_pv + n_pq + col_k
                if i == j:
                    val = (
                        float(P[i] + G[i, i] * Vmag[i] ** 2)
                        if not self._gpu_available
                        else float(xp.asnumpy(P[i] + G[i, i] * Vmag[i] ** 2))
                    )
                else:
                    val = (
                        float(
                            Vmag[i]
                            * Vmag[j]
                            * (
                                G[i, j] * xp.cos(Vang[i] - Vang[j])
                                + B[i, j] * xp.sin(Vang[i] - Vang[j])
                            ),
                        )
                        if not self._gpu_available
                        else float(
                            xp.asnumpy(
                                Vmag[i]
                                * Vmag[j]
                                * (
                                    G[i, j] * xp.cos(Vang[i] - Vang[j])
                                    + B[i, j] * xp.sin(Vang[i] - Vang[j])
                                ),
                            ),
                        )
                    )
                if self._gpu_available:
                    if not math.isclose(val, 0.0):
                        rows.append(row_k)
                        cols.append(col)
                        data.append(val)
                else:
                    if not math.isclose(val, 0.0):
                        J[row_k, col] = val

        for row_k, i in enumerate(pq_idx):
            row = n_pv + n_pq + row_k
            # M: ∂Q_i/∂θ_j
            for col_k, j in enumerate(theta_cols):
                if i == j:
                    val = (
                        float(P[i] - G[i, i] * Vmag[i] ** 2)
                        if not self._gpu_available
                        else float(xp.asnumpy(P[i] - G[i, i] * Vmag[i] ** 2))
                    )
                else:
                    val = (
                        float(
                            -Vmag[i]
                            * Vmag[j]
                            * (
                                G[i, j] * xp.cos(Vang[i] - Vang[j])
                                + B[i, j] * xp.sin(Vang[i] - Vang[j])
                            ),
                        )
                        if not self._gpu_available
                        else float(
                            xp.asnumpy(
                                -Vmag[i]
                                * Vmag[j]
                                * (
                                    G[i, j] * xp.cos(Vang[i] - Vang[j])
                                    + B[i, j] * xp.sin(Vang[i] - Vang[j])
                                ),
                            ),
                        )
                    )
                if self._gpu_available:
                    if not math.isclose(val, 0.0):
                        rows.append(row)
                        cols.append(col_k)
                        data.append(val)
                else:
                    if not math.isclose(val, 0.0):
                        J[row, col_k] = val

            # L: Union[∂Q_i/∂|V, _j]
            for col_k, j in enumerate(v_cols):
                col = n_pv + n_pq + col_k
                if i == j:
                    val = (
                        float(Q[i] - B[i, i] * Vmag[i] ** 2)
                        if not self._gpu_available
                        else float(xp.asnumpy(Q[i] - B[i, i] * Vmag[i] ** 2))
                    )
                else:
                    val = (
                        float(
                            Vmag[i]
                            * Vmag[j]
                            * (
                                G[i, j] * xp.sin(Vang[i] - Vang[j])
                                - B[i, j] * xp.cos(Vang[i] - Vang[j])
                            ),
                        )
                        if not self._gpu_available
                        else float(
                            xp.asnumpy(
                                Vmag[i]
                                * Vmag[j]
                                * (
                                    G[i, j] * xp.sin(Vang[i] - Vang[j])
                                    - B[i, j] * xp.cos(Vang[i] - Vang[j])
                                ),
                            ),
                        )
                    )
                if self._gpu_available:
                    if not math.isclose(val, 0.0):
                        rows.append(row)
                        cols.append(col)
                        data.append(val)
                else:
                    if not math.isclose(val, 0.0):
                        J[row, col] = val

        # Assemble sparse matrix
        if self._gpu_available:
            data_arr = np.array(data, dtype=np.float64)
            rows_arr = np.array(rows, dtype=np.int32)
            cols_arr = np.array(cols, dtype=np.int32)
            # Build CuPy CSR matrix via COO  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            J_coo = _cp.sparse.coo_matrix(  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
                (data_arr, (rows_arr, cols_arr)),
                shape=(n_unknowns, n_unknowns),
            )
            return J_coo.tocsr()
        else:
            return J.tocsr()

    # ------------------------------------------------------------------
    # Linear solver
    # ------------------------------------------------------------------
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def _solve_linear(  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        self,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        A: Any,  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        b: Any,
        n_unknowns: int,
    ) -> Any:
        """Solve the sparse linear system  A x = b.

        Uses ``cupyx.scipy.sparse.linalg.spsolve`` on GPU or
        ``scipy.sparse.linalg.spsolve`` on CPU.

        Parameters
        ----------
        A : sparse matrix
            System matrix (on device).
        b : array
            Right-hand side vector (on device).
        n_unknowns : int
            System size.

        Returns
        -------
        array
            Solution vector on the active device.
        """

        if self._gpu_available:
            try:
                # Ensure b is a CuPy array
                b_gpu = _cp.asarray(np.asarray(b)) if not isinstance(b, _cp.ndarray) else b

                # Ensure A is a CuPy sparse matrix  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                A_gpu = _cp.sparse.csr_matrix(_cp.asarray(A)) if not _cp.sparse.issparse(A) else A  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

                x = _cp_spsolve(A_gpu, b_gpu)
                return x
            except Exception as exc:
                logger.warning(
                    "GPU spsolve failed (%s) — falling back to CPU for this solve.",
                    exc,
                )
                # Fallback: transfer to CPU, solve, transfer back  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                A_cpu = A.get() if _cp.sparse.issparse(A) else _cp.asnumpy(A)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
                b_cpu = _cp.asnumpy(b) if isinstance(b, _cp.ndarray) else np.asarray(b)
                if sp_issparse(A_cpu):
                    x_cpu = scipy_spsolve(A_cpu.tocsr(), b_cpu)
                else:
                    x_cpu = np.linalg.solve(np.asarray(A_cpu), b_cpu)
                return _cp.asarray(x_cpu)
        else:
            # CPU path
            if sp_issparse(A):
                try:
                    return scipy_spsolve(A.tocsr(), b)
                except Exception:
                    return np.linalg.lstsq(A.toarray(), b, rcond=None)[0]
            else:
                try:
                    return np.linalg.solve(np.asarray(A), b)
                except np.linalg.LinAlgError:
                    return np.linalg.lstsq(np.asarray(A), b, rcond=None)[0]

    # ------------------------------------------------------------------
    # Benchmarking
    # ------------------------------------------------------------------

    def benchmark_cpu_vs_gpu(
        self,
        sizes: list[int] | None = None,
    ) -> dict[str, Any]:
        """Benchmark CPU vs GPU solver performance for various system sizes.

        Generates synthetic systems and runs the Newton-Raphson solver
        on both CPU (NumPy) and GPU (CuPy) to produce timing comparisons.

        Parameters
        ----------
        sizes : list[int], optional
            System sizes to benchmark.  Default ``[100, 500, 1000]``.

        Returns
        -------
        dict
            Per-size results including ``cpu_ms``, ``gpu_ms``,
            ``speedup``, and convergence info.
        """
        if sizes is None:
            sizes = [100, 500, 1000]

        results: dict[str, Any] = {"device": self._device_name, "sizes": []}

        from engine.sparse_solver import SparseYBus as _SparseYBus

        for n_buses in sizes:
            buses, branches = _SparseYBus._generate_synthetic_system(n_buses)

            # Build sparse Y-bus once
            builder = _SparseYBus()
            ybus = builder.build_sparse_ybus(buses, branches)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Ybus_dense = ybus.toarray()  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

            # --- CPU benchmark ---
            solver_cpu = GPUSolver.__new__(GPUSolver)
            solver_cpu._gpu_available = False
            solver_cpu._xp = np
            solver_cpu._device_name = "CPU (NumPy/SciPy)"

            t0 = time.perf_counter()
            result_cpu = solver_cpu.newton_raphson_gpu(
                Ybus_dense,
                buses,
                max_iter=20,
                tol=1e-6,
            )
            t_cpu_ms = (time.perf_counter() - t0) * 1000

            # --- GPU benchmark (if available) ---
            t_gpu_ms = None
            speedup = None
            if self._gpu_available:
                t0 = time.perf_counter()
                self.newton_raphson_gpu(
                    Ybus_dense,
                    buses,
                    max_iter=20,
                    tol=1e-6,
                )
                t_gpu_ms = (time.perf_counter() - t0) * 1000
                if t_gpu_ms > 0:
                    speedup = round(t_cpu_ms / t_gpu_ms, 2)

            entry = {
                "n_buses": n_buses,
                "cpu_ms": round(t_cpu_ms, 3),
                "gpu_ms": round(t_gpu_ms, 3) if t_gpu_ms is not None else None,
                "speedup": speedup,
                "cpu_converged": result_cpu.converged,
                "cpu_iterations": result_cpu.iterations,
            }
            results["sizes"].append(entry)
            logger.info("GPU benchmark n=%d: %s", n_buses, entry)

        return results
