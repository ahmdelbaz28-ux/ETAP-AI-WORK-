"""Numerical stability and safety utilities for power system calculation engines."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any, Tuple, Union

import numpy as np
from numpy.linalg import LinAlgError, cholesky, cond, inv, lstsq, matrix_rank, norm, solve

logger = logging.getLogger(__name__)

__all__ = [
    "NumericalBounds",
    "NumericalGuard",
    "ConvergenceMonitor",
    "ConsistencyCheck",
    "MatrixStabilizer",
    "wrap_solver",
    "safe_calculation",
]


class NumericalBounds(Enum):
    """Defines safe numerical ranges for all power system parameters.

    Each member stores a (min, max) tuple representing the physically
    plausible range. Values outside these bounds indicate measurement errors,
    model faults, or solver divergence.
    """

    VOLTAGE_PU: Tuple[float, float] = (0.0, 2.0)
    CURRENT_PU: Tuple[float, float] = (0.0, 100.0)
    POWER_MW: Tuple[float, float] = (-1e6, 1e6)
    POWER_MVAR: Tuple[float, float] = (-1e6, 1e6)
    ANGLE_DEG: Tuple[float, float] = (-360.0, 360.0)
    IMPEDANCE_PU: Tuple[float, float] = (1e-10, 1e6)
    ADMITTANCE_PU: Tuple[float, float] = (1e-10, 1e6)
    FREQUENCY_HZ: Tuple[float, float] = (0.0, 1000.0)
    RATIO: Tuple[float, float] = (1e-6, 1e6)
    ITERATIONS: Tuple[int, int] = (1, 100000)

    @classmethod
    def get_bounds(cls, name: str) -> Tuple[float, float]:
        """Retrieve bounds by parameter name.

        Parameters
        ----------
        name : str
            Uppercase parameter name, e.g. ``"VOLTAGE_PU"``.

        Returns
        -------
        Tuple[float, float]
            (min, max) tuple.

        Raises
        ------
        ValueError
            If the parameter name is not recognised.
        """
        try:
            return cls[name].value
        except KeyError as err:
            raise ValueError(f"Unknown parameter '{name}'. Available: {[e.name for e in cls]}") from err


class NumericalGuard:
    """Guards against numerical issues in power system calculations.

    Provides detection and safe handling of NaN, Inf, division by zero,
    logarithm/root of non-positive numbers, and out-of-bounds values.
    """

    def __init__(self, warn_on_clamp: bool = True, logger_instance: logging.Logger | None = None):
        self.warn_on_clamp = warn_on_clamp
        self.log = logger_instance or logger

    def check_inf_nan(self, value: Union[float, np.ndarray], name: str = "value") -> np.ndarray:
        """Detect and replace NaN (→0.0) and Inf (→±1e300) values."""
        arr = np.asarray(value, dtype=float)
        if np.any(np.isnan(arr)):
            self.log.warning("NaN detected in '%s' — replacing with 0.0", name)
            arr = np.nan_to_num(arr, nan=0.0)
        if np.any(np.isinf(arr)):
            self.log.warning("Inf detected in '%s' — replacing with finite bounds", name)
            arr = np.nan_to_num(arr, posinf=1e300, neginf=-1e300)
        return arr

    def check_divergence(self, history: Sequence[float], threshold: float = 1e10) -> bool:
        """Check if a sequence of values is diverging (step changes or magnitude exceed threshold)."""
        arr = np.asarray(history, dtype=float)
        if len(arr) < 2:
            return False
        diffs = np.abs(np.diff(arr))
        return bool(np.any(diffs > threshold) or np.any(np.abs(arr[-3:]) > threshold))

    def safe_log(self, value: Union[float, np.ndarray], epsilon: float = 1e-300) -> np.ndarray:
        """Safe natural logarithm: clips value to epsilon before taking log."""
        arr = np.asarray(value, dtype=float)
        return np.log(np.maximum(arr, epsilon))

    def safe_sqrt(self, value: Union[float, np.ndarray], epsilon: float = 0.0) -> np.ndarray:
        """Safe square root: clips value to epsilon before taking sqrt."""
        arr = np.asarray(value, dtype=float)
        return np.sqrt(np.maximum(arr, epsilon))

    def safe_division(
        self,
        numerator: Union[float, np.ndarray],
        denominator: Union[float, np.ndarray],
        default: float = 0.0,
        epsilon: float = 1e-300,
    ) -> np.ndarray:
        """Safe division: replaces near-zero denominators with default value."""
        num = np.asarray(numerator, dtype=float)
        den = np.asarray(denominator, dtype=float)
        mask = np.abs(den) < epsilon
        if np.any(mask):
            self.log.warning("Division by near-zero denominator detected — using default %s", default)
        safe_den = np.where(mask, np.inf, den)
        return np.divide(num, safe_den, out=np.full_like(num, default, dtype=float), where=~mask)

    def safe_angle(self, complex_val: Union[complex, np.ndarray]) -> np.ndarray:
        """Compute phase angle safely: zero-magnitude values return 0.0 radians."""
        arr = np.asarray(complex_val, dtype=complex)
        mask = np.abs(arr) < 1e-300
        if np.any(mask):
            self.log.warning("Zero-magnitude complex value in angle computation — returning 0.0")
        return np.where(mask, 0.0, np.angle(arr))

    def clamp_to_bounds(
        self,
        value: Union[float, np.ndarray],
        min_val: float,
        max_val: float,
        name: str = "value",
    ) -> np.ndarray:
        """Clamp value(s) to [min_val, max_val] with optional log warning."""
        arr = np.asarray(value, dtype=float)
        below = arr < min_val
        above = arr > max_val
        if self.warn_on_clamp and (np.any(below) or np.any(above)):
            self.log.warning(
                "'%s' clamped: %d below min=%s, %d above max=%s",
                name, int(np.sum(below)), min_val, int(np.sum(above)), max_val,
            )
        return np.clip(arr, min_val, max_val)

    def is_within_bounds(self, value: Union[float, np.ndarray], min_val: float, max_val: float) -> bool:
        """Check whether all elements lie within [min_val, max_val]."""
        arr = np.asarray(value, dtype=float)
        return bool(np.all((arr >= min_val) & (arr <= max_val)))

    def validate_matrix(
        self,
        matrix: np.ndarray,
        expected_shape: Tuple[int, ...] | None = None,
    ) -> np.ndarray:
        """Sanitise a matrix by replacing NaN/Inf and verifying shape.

        Raises ValueError if expected_shape is provided and does not match.
        """
        mat = np.asarray(matrix, dtype=float)
        if np.any(np.isnan(mat)):
            self.log.warning("NaN values found in matrix — replacing with 0.0")
            mat = np.nan_to_num(mat, nan=0.0)
        if np.any(np.isinf(mat)):
            self.log.warning("Inf values found in matrix — replacing with large finite values")
            mat = np.nan_to_num(mat, posinf=1e300, neginf=-1e300)
        if expected_shape is not None and mat.shape != expected_shape:
            raise ValueError(f"Matrix shape {mat.shape} does not match expected {expected_shape}")
        return mat

    def condition_number(self, matrix: np.ndarray) -> float:
        """Compute condition number for singularity detection. Returns inf on failure."""
        mat = np.asarray(matrix, dtype=float)
        if mat.size == 0:
            return float("inf")
        try:
            return float(cond(mat))
        except LinAlgError:
            self.log.warning("Failed to compute condition number — returning inf")
            return float("inf")


class ConvergenceMonitor:
    """Monitors solver convergence with divergence detection and statistics.

    Parameters
    ----------
    max_iterations : int
        Maximum allowed iterations before forced termination.
    tolerance : float
        Mismatch threshold below which the solution is considered converged.
    divergence_threshold : float
        Mismatch magnitude above which the solution is considered diverging.
    """

    def __init__(
        self,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        divergence_threshold: float = 1e10,
    ):
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.divergence_threshold = divergence_threshold
        self._history: list[float] = []
        self._iterations: int = 0

    def add_iteration(self, value: float, iteration: int | None = None) -> None:
        """Record an iteration mismatch value."""
        self._history.append(float(value))
        self._iterations = iteration if iteration is not None else len(self._history)

    def is_converged(self, current_value: float) -> bool:
        """Check whether |current_value| <= tolerance."""
        return bool(abs(current_value) <= self.tolerance)

    def is_diverging(self, current_value: float) -> bool:
        """Check for divergence: values exceeding threshold or anomalous step growth."""
        if len(self._history) < 2:
            return False
        recent = self._history[-3:] + [float(current_value)]
        abs_vals = np.abs(recent)
        diffs = np.abs(np.diff(abs_vals))
        # Check absolute magnitude and anomalous growth
        absolute_exceeded = bool(np.any(abs_vals[-3:] > self.divergence_threshold))
        step_exceeded = bool(
            diffs[-1] > self.divergence_threshold
            or (
                len(diffs) >= 2
                and diffs[-1] > self.divergence_threshold
                and diffs[-1] > np.mean(diffs[:-1]) * 10
            )
        ) if len(diffs) >= 1 else False
        return absolute_exceeded or step_exceeded

    def get_convergence_rate(self, window: int = 5) -> float:
        """Mean ratio |x_k / x_{k-1}| over last *window* iterations (<1 = converging)."""
        if len(self._history) < 2:
            return 0.0
        recent = np.array(self._history[-window:], dtype=float)
        if len(recent) < 2:
            return 0.0
        ratios = np.abs(recent[1:] / np.maximum(np.abs(recent[:-1]), 1e-300))
        filtered = ratios[ratios < 1e6]
        return float(np.mean(filtered)) if len(filtered) > 0 else float('inf')

    def reset(self) -> None:
        """Clear iteration history and reset counter."""
        self._history.clear()
        self._iterations = 0

    def get_statistics(self) -> dict[str, Any]:
        """Return convergence summary: iterations, final_mismatch, converged, rate, history."""
        final_mismatch = self._history[-1] if self._history else 0.0
        rate = self.get_convergence_rate()
        return {
            "iterations": self._iterations,
            "final_mismatch": final_mismatch,
            "converged": final_mismatch <= self.tolerance if self._history else False,
            "rate": rate,
            "history": list(self._history),
        }


class ConsistencyCheck:
    """Result consistency verification for power system calculations.

    Provides physical-law and engineering-rule checks including power balance,
    voltage profile limits, Kirchhoff's laws, and energy conservation.
    Each check appends a result dict to an internal log.
    """

    def __init__(self, logger_instance: logging.Logger | None = None):
        self.log = logger_instance or logger
        self._results: list[dict[str, Any]] = []

    @staticmethod
    def _to_array(value: Any) -> np.ndarray:
        return np.atleast_1d(np.asarray(value, dtype=float))

    def check_power_balance(
        self,
        total_gen: Union[float, np.ndarray],
        total_load: Union[float, np.ndarray],
        total_losses: Union[float, np.ndarray],
        tolerance_mw: float = 1.0,
    ) -> dict[str, Any]:
        """Verify that generation = load + losses within tolerance_mw."""
        gen = self._to_array(total_gen)
        load = self._to_array(total_load)
        losses = self._to_array(total_losses)
        mismatch = float(np.sum(gen) - np.sum(load) - np.sum(losses))
        passed = bool(abs(mismatch) <= tolerance_mw)
        result = {"check": "power_balance", "passed": passed, "mismatch_mw": mismatch, "tolerance_mw": tolerance_mw}
        if not passed:
            self.log.warning("Power balance check failed: mismatch=%.4f MW", mismatch)
        self._results.append(result)
        return result

    def check_voltage_profile(
        self,
        voltages: Union[Sequence[float], np.ndarray],
        vmin: float = 0.95,
        vmax: float = 1.05,
    ) -> dict[str, Any]:
        """Verify bus voltage magnitudes stay within [vmin, vmax]."""
        v = self._to_array(voltages)
        n_total = v.size
        n_violations = int(np.sum((v < vmin) | (v > vmax)))
        passed = n_violations == 0
        result = {
            "check": "voltage_profile", "passed": passed,
            "n_violations": n_violations, "n_total": n_total,
            "violation_pct": float(n_violations / n_total * 100) if n_total > 0 else 0.0,
            "vmin": vmin, "vmax": vmax,
        }
        if not passed:
            self.log.warning("Voltage profile: %d/%d buses out of bounds", n_violations, n_total)
        self._results.append(result)
        return result

    def check_kirchhoff_current_law(
        self,
        bus_currents: Union[Sequence[float], np.ndarray],
        tolerance: float = 1e-6,
    ) -> dict[str, Any]:
        """Check KCL: sum of currents at each bus should be near zero."""
        currents = self._to_array(bus_currents)
        if currents.ndim == 1:
            residual = float(np.abs(np.sum(currents)))
        else:
            residual = float(np.max(np.abs(np.sum(currents, axis=1))))
        passed = residual <= tolerance
        result = {"check": "kcl", "passed": passed, "residual": residual, "tolerance": tolerance}
        if not passed:
            self.log.warning("KCL check failed: max residual=%.6e", residual)
        self._results.append(result)
        return result

    def check_kirchhoff_voltage_law(
        self,
        loop_voltages: Union[Sequence[float], np.ndarray],
        tolerance: float = 1e-6,
    ) -> dict[str, Any]:
        """Check KVL: sum of voltages around any loop should be near zero."""
        voltages = self._to_array(loop_voltages)
        if voltages.ndim == 1:
            residual = float(np.abs(np.sum(voltages)))
        else:
            residual = float(np.max(np.abs(np.sum(voltages, axis=1))))
        passed = residual <= tolerance
        result = {"check": "kvl", "passed": passed, "residual": residual, "tolerance": tolerance}
        if not passed:
            self.log.warning("KVL check failed: max residual=%.6e", residual)
        self._results.append(result)
        return result

    def check_energy_conservation(
        self,
        energy_in: Union[float, np.ndarray],
        energy_out: Union[float, np.ndarray],
        losses: Union[float, np.ndarray],
        tolerance: float = 0.01,
    ) -> dict[str, Any]:
        """Verify energy_in = energy_out + losses within tolerance."""
        e_in = float(np.sum(self._to_array(energy_in)))
        e_out = float(np.sum(self._to_array(energy_out)))
        e_losses = float(np.sum(self._to_array(losses)))
        mismatch = abs(e_in - e_out - e_losses)
        passed = mismatch <= tolerance
        result = {
            "check": "energy_conservation", "passed": passed, "mismatch": mismatch,
            "tolerance": tolerance, "energy_in": e_in, "energy_out": e_out, "losses": e_losses,
        }
        if not passed:
            self.log.warning("Energy conservation check failed: mismatch=%.4f", mismatch)
        self._results.append(result)
        return result

    def get_all_results(self) -> list[dict[str, Any]]:
        """Return all stored consistency check results."""
        return list(self._results)

    def clear_results(self) -> None:
        """Clear all stored result history."""
        self._results.clear()


class MatrixStabilizer:
    """Matrix operation safety — regularization, inversion, and system solving.

    Provides robust alternatives to raw linear algebra by detecting singular
    or ill-conditioned matrices and applying fallback strategies such as
    Tikhonov diagonal regularisation and pseudo-inverses.

    Parameters
    ----------
    default_tolerance : float
        Default tolerance for rank estimation and symmetry checks.
    """

    def __init__(self, default_tolerance: float = 1e-12):
        self.default_tolerance = default_tolerance
        self.log = logger

    def regularize_matrix(self, matrix: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
        """Add epsilon to the diagonal (Tikhonov regularisation).

        Raises ValueError if the matrix is not square.
        """
        mat = np.asarray(matrix, dtype=float)
        if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
            raise ValueError(f"Expected square matrix, got shape {mat.shape}")
        return mat + epsilon * np.eye(mat.shape[0], dtype=float)

    def safe_inverse(self, matrix: np.ndarray, method: str = "pinv") -> np.ndarray:
        """Invert a matrix with fallback to Moore-Penrose pseudo-inverse."""
        mat = np.asarray(matrix, dtype=float)
        eye = np.eye(mat.shape[0], dtype=float)
        if method == "pinv":
            return lstsq(mat, eye, rcond=self.default_tolerance)[0]
        try:
            return inv(mat)
        except LinAlgError:
            self.log.warning("Matrix inversion failed — falling back to pseudo-inverse")
            return lstsq(mat, eye, rcond=self.default_tolerance)[0]

    def safe_solve(self, A: np.ndarray, b: np.ndarray, method: str = "lu") -> np.ndarray:
        """Solve Ax = b with fallback to least-squares on singular systems."""
        A_arr = np.asarray(A, dtype=float)
        b_arr = np.asarray(b, dtype=float)
        try:
            return solve(A_arr, b_arr)
        except LinAlgError:
            self.log.warning("Linear solve failed — falling back to least-squares")
            return lstsq(A_arr, b_arr, rcond=self.default_tolerance)[0]

    def is_symmetric(self, matrix: np.ndarray, tolerance: float | None = None) -> bool:
        """Check if matrix is square and ||A - A^T||_inf <= tolerance."""
        mat = np.asarray(matrix, dtype=float)
        tol = tolerance if tolerance is not None else self.default_tolerance
        if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
            return False
        return bool(norm(mat - mat.T, ord=np.inf) <= tol)

    def is_positive_definite(self, matrix: np.ndarray) -> bool:
        """Check positive definiteness via Cholesky decomposition."""
        mat = np.asarray(matrix, dtype=float)
        try:
            cholesky(mat)
            return True
        except LinAlgError:
            return False

    def estimate_rank(self, matrix: np.ndarray, tolerance: float | None = None) -> int:
        """Estimate numerical rank using SVD."""
        mat = np.asarray(matrix, dtype=float)
        tol = tolerance if tolerance is not None else self.default_tolerance
        return int(matrix_rank(mat, tol=tol))


def wrap_solver(
    solver_fn: Callable[..., Any],
    numerical_guard: NumericalGuard,
    convergence_monitor: ConvergenceMonitor,
) -> Callable[..., Any]:
    """Wrap a solver function with convergence monitoring.

    Injects ``_numerical_converged``, ``_numerical_diverging``, and
    ``_numerical_stats`` keys into the solver result dict.
    """
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        convergence_monitor.reset()
        result = solver_fn(*args, **kwargs)
        if isinstance(result, dict):
            mismatch = result.get("mismatch", result.get("residual", None))
            if mismatch is not None:
                convergence_monitor.add_iteration(mismatch)
                result["_numerical_converged"] = convergence_monitor.is_converged(mismatch)
                result["_numerical_diverging"] = convergence_monitor.is_diverging(mismatch)
                result["_numerical_stats"] = convergence_monitor.get_statistics()
        return result
    return wrapped


def safe_calculation(
    component_name: str,
    fn: Callable[..., Any],
    *args: Any,
    error_handler: Callable[[Exception], Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute a function with numerical safety and optional error handling.

    Post-processes numpy array return values through :meth:`NumericalGuard.check_inf_nan`.
    If *error_handler* is provided, exceptions are passed to it instead of re-raising.
    """
    guard = NumericalGuard()
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, np.ndarray):
            result = guard.check_inf_nan(result, name=component_name)
        return result
    except Exception as exc:
        logger.exception("Numerical safety failure in '%s': %s", component_name, exc)
        if error_handler is not None:
            return error_handler(exc)
        raise
