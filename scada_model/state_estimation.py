"""
State Estimation Engine - Weighted Least Squares (WLS) + GNN Enhancement
=======================================================================
Implements WLS state estimator with bad data detection
and measurement redundancy handling for ADMS.

Now includes GNN-enhanced state estimation when PyTorch Geometric
is available, providing neural-network-corrected estimates that
combine traditional WLS with graph-based predictions.

Reference: A. Abur and A.G. Exposito, "Power System State Estimation",
CRC Press, 2004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

# Optional GNN dependency
_HAS_TORCH_GEOMETRIC = False
try:
    import torch  # noqa: F401 — imported to check availability
    from torch_geometric.nn import GCNConv  # noqa: F401

    _HAS_TORCH_GEOMETRIC = True
except ImportError:
    pass


class StateEstimationStatus(Enum):
    CONVERGED = "converged"
    NOT_CONVERGED = "not_converged"
    INSUFFICIENT_MEASUREMENTS = "insufficient_measurements"
    SINGULAR_MATRIX = "singular_matrix"


@dataclass
class StateEstimationResult:
    """Result of state estimation run."""

    status: StateEstimationStatus
    voltage_magnitudes: np.ndarray  # Estimated voltage magnitudes
    voltage_angles: np.ndarray  # Estimated voltage angles (radians)
    iterations: int = 0
    max_residual: float = 0.0
    objective_value: float = 0.0
    bad_data_detected: List[int] = field(default_factory=list)
    measurement_residuals: Optional[np.ndarray] = None
    covariance_matrix: Optional[np.ndarray] = None


class WLSEstimator:
    """
    Weighted Least Squares State Estimator.

    Supports:
    - Voltage magnitude measurements (V)
    - Power injection measurements (P, Q)
    - Power flow measurements (Pij, Qij)
    - Bad data detection (largest normalized residual)
    - Measurement redundancy analysis
    """

    def __init__(
        self, tolerance: float = 1e-6, max_iterations: int = 50, bad_data_threshold: float = 3.0
    ):
        """
        Initialize WLS estimator.

        Parameters:
        tolerance: Convergence tolerance for state change.
        max_iterations: Maximum number of iterations.
        bad_data_threshold: Normalized residual threshold for bad data detection.
        """
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.bad_data_threshold = bad_data_threshold

    def estimate(
        self, Ybus: np.ndarray, measurements: dict, bus_ids: List[str], slack_bus_idx: int = 0
    ) -> StateEstimationResult:
        """
        Run WLS state estimation.

        Parameters:
        Ybus: Bus admittance matrix (n x n complex).
        measurements: Dict with keys:
            'voltage_mag': {bus_idx: (value, sigma)}
            'power_injection': {bus_idx: (P_value, Q_value, sigma_P, sigma_Q)}
            'power_flow': {(from_idx, to_idx): (P_value, Q_value, sigma_P, sigma_Q)}
        bus_ids: List of bus IDs.
        slack_bus_idx: Index of slack bus.

        Returns:
        StateEstimationResult
        """
        n = len(bus_ids)
        if n == 0:
            return StateEstimationResult(
                status=StateEstimationStatus.INSUFFICIENT_MEASUREMENTS,
                voltage_magnitudes=np.array([]),
                voltage_angles=np.array([]),
            )

        # Initialize state vector: [theta_1..theta_n, V_1..V_n]
        theta = np.zeros(n)
        V = np.ones(n)

        # Set slack bus angle to 0
        theta[slack_bus_idx] = 0.0

        # Build measurement vector and weight matrix
        z, h_indices, weights = self._build_measurement_vectors(measurements, n, slack_bus_idx)

        m = len(z)
        if m < 2 * n - 1:
            return StateEstimationResult(
                status=StateEstimationStatus.INSUFFICIENT_MEASUREMENTS,
                voltage_magnitudes=V,
                voltage_angles=theta,
            )

        W = np.diag(weights)

        # Iterative WLS
        converged = False
        iteration = 0
        x = np.concatenate([theta, V])

        # Mask to remove slack bus theta column from Jacobian (theta column
        # is linearly dependent on other theta columns at flat start since
        # Jacobian rows depend on angle differences only)
        keep_cols = [i for i in range(2 * n) if i != slack_bus_idx]

        for iteration in range(1, self.max_iterations + 1):
            # Compute estimated measurements and Jacobian
            h_x = self._compute_h(x, Ybus, h_indices, n)
            H = self._compute_jacobian(x, Ybus, h_indices, n)

            # Residual
            r = z - h_x

            # Remove slack bus theta column from H to avoid singular gain matrix
            H_reduced = H[:, keep_cols]

            # Gain matrix G = H^T W H
            try:
                G = H_reduced.T @ W @ H_reduced
                G_inv = np.linalg.inv(G)
            except np.linalg.LinAlgError:
                return StateEstimationResult(
                    status=StateEstimationStatus.SINGULAR_MATRIX,
                    voltage_magnitudes=x[n:],
                    voltage_angles=x[:n],
                    iterations=iteration,
                )

            # State update: dx = G^{-1} H^T W r
            dx_reduced = G_inv @ H_reduced.T @ W @ r

            # Expand dx to full dimension by inserting 0 at slack bus position
            dx = np.zeros(2 * n)
            dx[keep_cols] = dx_reduced

            x = x + dx

            # Check convergence
            if np.max(np.abs(dx)) < self.tolerance:
                converged = True
                break

        if not converged:
            return StateEstimationResult(
                status=StateEstimationStatus.NOT_CONVERGED,
                voltage_magnitudes=x[n:],
                voltage_angles=x[:n],
                iterations=iteration,
            )

        # Compute final residuals and bad data detection
        h_x_final = self._compute_h(x, Ybus, h_indices, n)
        H_final = self._compute_jacobian(x, Ybus, h_indices, n)
        r_final = z - h_x_final
        objective = float(r_final.T @ W @ r_final)

        # Covariance matrix (use reduced Jacobian to avoid singularity)
        try:
            H_final_reduced = H_final[:, keep_cols]
            G_final = H_final_reduced.T @ W @ H_final_reduced
            G_inv_final = np.linalg.inv(G_final)
            covariance = G_inv_final
        except np.linalg.LinAlgError:
            covariance = None

        # Normalized residuals for bad data detection
        bad_data = []
        norm_residuals = None
        if covariance is not None:
            S = H_final_reduced @ G_inv_final @ H_final_reduced.T @ W
            Omega = np.eye(m) - S
            try:
                Omega_inv = np.linalg.inv(np.diag(np.diag(Omega)) + np.eye(m) * 1e-10)
                norm_residuals = np.abs(Omega_inv @ r_final) / (np.sqrt(np.diag(Omega_inv)) + 1e-10)
                bad_data = [int(i) for i in range(m) if norm_residuals[i] > self.bad_data_threshold]
            except np.linalg.LinAlgError:
                norm_residuals = np.abs(r_final)

        return StateEstimationResult(
            status=StateEstimationStatus.CONVERGED,
            voltage_magnitudes=x[n:],
            voltage_angles=x[:n],
            iterations=iteration,
            max_residual=float(np.max(np.abs(r_final))) if len(r_final) > 0 else 0.0,
            objective_value=objective,
            bad_data_detected=bad_data,
            measurement_residuals=norm_residuals,
            covariance_matrix=covariance,
        )

    def _build_measurement_vectors(
        self, measurements: dict, n: int, slack_idx: int
    ) -> Tuple[np.ndarray, list, np.ndarray]:
        """Build measurement vector z, index list, and weight vector."""
        z_list = []
        h_indices = []
        w_list = []

        # Voltage magnitude measurements
        for bus_idx, (value, sigma) in measurements.get("voltage_mag", {}).items():
            z_list.append(value)
            h_indices.append(("V", bus_idx))
            w_list.append(1.0 / (sigma**2) if sigma > 0 else 1e6)

        # Power injection measurements
        for bus_idx, (P, Q, sigma_P, sigma_Q) in measurements.get("power_injection", {}).items():
            if bus_idx != slack_idx:
                z_list.append(P)
                h_indices.append(("P", bus_idx))
                w_list.append(1.0 / (sigma_P**2) if sigma_P > 0 else 1e6)
            z_list.append(Q)
            h_indices.append(("Q", bus_idx))
            w_list.append(1.0 / (sigma_Q**2) if sigma_Q > 0 else 1e6)

        # Power flow measurements
        for (i, j), (P, Q, sigma_P, sigma_Q) in measurements.get("power_flow", {}).items():
            z_list.append(P)
            h_indices.append(("Pij", i, j))
            w_list.append(1.0 / (sigma_P**2) if sigma_P > 0 else 1e6)
            z_list.append(Q)
            h_indices.append(("Qij", i, j))
            w_list.append(1.0 / (sigma_Q**2) if sigma_Q > 0 else 1e6)

        return np.array(z_list), h_indices, np.array(w_list)

    def _compute_h(self, x: np.ndarray, Ybus: np.ndarray, h_indices: list, n: int) -> np.ndarray:
        """Compute estimated measurement vector h(x)."""
        theta = x[:n]
        V = x[n:]
        h = np.zeros(len(h_indices))

        for k, idx_info in enumerate(h_indices):
            if idx_info[0] == "V":
                _, bus_idx = idx_info
                h[k] = V[bus_idx]
            elif idx_info[0] == "P":
                _, i = idx_info
                Pi = 0.0
                for j in range(n):
                    Pi += (
                        V[i]
                        * V[j]
                        * (
                            Ybus[i, j].real * np.cos(theta[i] - theta[j])
                            + Ybus[i, j].imag * np.sin(theta[i] - theta[j])
                        )
                    )
                h[k] = Pi
            elif idx_info[0] == "Q":
                _, i = idx_info
                Qi = 0.0
                for j in range(n):
                    Qi += (
                        V[i]
                        * V[j]
                        * (
                            Ybus[i, j].real * np.sin(theta[i] - theta[j])
                            - Ybus[i, j].imag * np.cos(theta[i] - theta[j])
                        )
                    )
                h[k] = Qi
            elif idx_info[0] == "Pij":
                _, i, j = idx_info
                Gij = Ybus[i, j].real
                Bij = Ybus[i, j].imag
                Pij = V[i] ** 2 * Gij - V[i] * V[j] * (
                    Gij * np.cos(theta[i] - theta[j]) + Bij * np.sin(theta[i] - theta[j])
                )
                h[k] = Pij
            elif idx_info[0] == "Qij":
                _, i, j = idx_info
                Gij = Ybus[i, j].real
                Bij = Ybus[i, j].imag
                Qij = -(V[i] ** 2) * Bij - V[i] * V[j] * (
                    Gij * np.sin(theta[i] - theta[j]) - Bij * np.cos(theta[i] - theta[j])
                )
                h[k] = Qij
        return h

    def _compute_jacobian(
        self, x: np.ndarray, Ybus: np.ndarray, h_indices: list, n: int
    ) -> np.ndarray:
        """Compute Jacobian matrix H = dh/dx."""
        m = len(h_indices)
        theta = x[:n]
        V = x[n:]
        H = np.zeros((m, 2 * n))

        for k, idx_info in enumerate(h_indices):
            if idx_info[0] == "V":
                _, i = idx_info
                H[k, n + i] = 1.0

            elif idx_info[0] == "P":
                _, i = idx_info
                for j in range(n):
                    if i == j:
                        continue
                    Gij = Ybus[i, j].real
                    Bij = Ybus[i, j].imag
                    # dPi/dtheta_j
                    H[k, j] = (
                        V[i]
                        * V[j]
                        * (Gij * np.sin(theta[i] - theta[j]) - Bij * np.cos(theta[i] - theta[j]))
                    )
                # dPi/dtheta_i
                H[k, i] = -sum(
                    V[i]
                    * V[j]
                    * (
                        Ybus[i, j].real * np.sin(theta[i] - theta[j])
                        - Ybus[i, j].imag * np.cos(theta[i] - theta[j])
                    )
                    for j in range(n)
                    if j != i
                )
                # dPi/dV_i
                H[k, n + i] = sum(
                    V[j]
                    * (
                        Ybus[i, j].real * np.cos(theta[i] - theta[j])
                        + Ybus[i, j].imag * np.sin(theta[i] - theta[j])
                    )
                    for j in range(n)
                )
                # dPi/dV_j
                for j in range(n):
                    if i == j:
                        continue
                    H[k, n + j] = V[i] * (
                        Ybus[i, j].real * np.cos(theta[i] - theta[j])
                        + Ybus[i, j].imag * np.sin(theta[i] - theta[j])
                    )

            elif idx_info[0] == "Q":
                _, i = idx_info
                for j in range(n):
                    if i == j:
                        continue
                    Gij = Ybus[i, j].real
                    Bij = Ybus[i, j].imag
                    H[k, j] = (
                        -V[i]
                        * V[j]
                        * (Gij * np.cos(theta[i] - theta[j]) + Bij * np.sin(theta[i] - theta[j]))
                    )
                H[k, i] = sum(
                    V[i]
                    * V[j]
                    * (
                        Ybus[i, j].real * np.cos(theta[i] - theta[j])
                        + Ybus[i, j].imag * np.sin(theta[i] - theta[j])
                    )
                    for j in range(n)
                    if j != i
                )
                H[k, n + i] = sum(
                    V[j]
                    * (
                        Ybus[i, j].real * np.sin(theta[i] - theta[j])
                        - Ybus[i, j].imag * np.cos(theta[i] - theta[j])
                    )
                    for j in range(n)
                )
                for j in range(n):
                    if i == j:
                        continue
                    H[k, n + j] = V[i] * (
                        Ybus[i, j].real * np.sin(theta[i] - theta[j])
                        - Ybus[i, j].imag * np.cos(theta[i] - theta[j])
                    )

            elif idx_info[0] == "Pij":
                _, i, j = idx_info
                Gij = Ybus[i, j].real
                Bij = Ybus[i, j].imag
                H[k, i] = (
                    V[i]
                    * V[j]
                    * (Gij * np.sin(theta[i] - theta[j]) + Bij * np.cos(theta[i] - theta[j]))
                )
                H[k, j] = (
                    -V[i]
                    * V[j]
                    * (Gij * np.sin(theta[i] - theta[j]) + Bij * np.cos(theta[i] - theta[j]))
                )
                H[k, n + i] = 2 * V[i] * Gij - V[j] * (
                    Gij * np.cos(theta[i] - theta[j]) + Bij * np.sin(theta[i] - theta[j])
                )
                H[k, n + j] = -V[i] * (
                    Gij * np.cos(theta[i] - theta[j]) + Bij * np.sin(theta[i] - theta[j])
                )

            elif idx_info[0] == "Qij":
                _, i, j = idx_info
                Gij = Ybus[i, j].real
                Bij = Ybus[i, j].imag
                H[k, i] = (
                    -V[i]
                    * V[j]
                    * (Gij * np.cos(theta[i] - theta[j]) - Bij * np.sin(theta[i] - theta[j]))
                )
                H[k, j] = (
                    V[i]
                    * V[j]
                    * (Gij * np.cos(theta[i] - theta[j]) - Bij * np.sin(theta[i] - theta[j]))
                )
                H[k, n + i] = -2 * V[i] * Bij - V[j] * (
                    Gij * np.sin(theta[i] - theta[j]) - Bij * np.cos(theta[i] - theta[j])
                )
                H[k, n + j] = -V[i] * (
                    Gij * np.sin(theta[i] - theta[j]) - Bij * np.cos(theta[i] - theta[j])
                )

        return H

    def check_redundancy(self, measurements: dict, n: int, slack_idx: int) -> dict:
        """
        Check measurement redundancy.

        Redundancy = m / (2n - 1)
        Minimum acceptable redundancy is typically 1.5-2.0
        """
        z, _, _ = self._build_measurement_vectors(measurements, n, slack_idx)
        m = len(z)
        required = 2 * n - 1
        redundancy = m / required if required > 0 else 0
        return {
            "measurement_count": m,
            "state_variables": required,
            "redundancy_ratio": redundancy,
            "sufficient": redundancy >= 1.5,
            "critical": redundancy < 1.0,
        }


class GNNStateEstimator:
    """
    GNN-Enhanced State Estimator for power grids.

    Combines traditional WLS with Graph Neural Network predictions
    to improve state estimation accuracy, especially when:
    - Measurement redundancy is low
    - Bad data is present
    - Real-time SCADA updates need fast approximation

    The power grid topology is modeled as a graph where buses are nodes
    and transmission lines are edges. The GNN learns spatial patterns
    in voltage and angle distributions across the network.

    Usage:
        estimator = GNNStateEstimator()
        result = estimator.estimate_with_gnn(Ybus, measurements, bus_ids, edge_list)
    """

    def __init__(self, hidden_dim: int = 64, num_layers: int = 3):
        """Initialize GNN State Estimator.

        Parameters
        ----------
        hidden_dim : int
            Hidden layer dimension for the GNN.
        num_layers : int
            Number of GCN layers.
        """
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self._gnn_model = None
        self._wls_estimator = WLSEstimator()
        self._is_trained = False

    def estimate_with_gnn(
        self,
        Ybus: np.ndarray,
        measurements: dict,
        bus_ids: List[str],
        edge_list: Optional[List[Tuple[int, int]]] = None,
        slack_bus_idx: int = 0,
    ) -> StateEstimationResult:
        """
        Run GNN-enhanced state estimation.

        First runs traditional WLS, then if GNN is trained,
        uses it to refine the estimates. Falls back to pure WLS
        if GNN is not available.

        Parameters
        ----------
        Ybus : np.ndarray
            Bus admittance matrix.
        measurements : dict
            Measurement data (same format as WLSEstimator).
        bus_ids : List[str]
            Bus ID list.
        edge_list : List[Tuple[int, int]], optional
            List of (from_bus_idx, to_bus_idx) for graph construction.
            If None, derived from Ybus non-zero off-diagonal entries.
        slack_bus_idx : int
            Slack bus index.

        Returns
        -------
        StateEstimationResult
            Enhanced state estimation result.
        """
        # Step 1: Run traditional WLS
        wls_result = self._wls_estimator.estimate(Ybus, measurements, bus_ids, slack_bus_idx)

        # Step 2: If GNN is not trained, return WLS result
        if not self._is_trained or not _HAS_TORCH_GEOMETRIC:
            return wls_result

        # Step 3: GNN refinement
        try:
            n = len(bus_ids)
            if edge_list is None:
                # Derive edges from Ybus
                edge_list = []
                for i in range(n):
                    for j in range(n):
                        if i != j and abs(Ybus[i, j]) > 1e-10:
                            edge_list.append((i, j))

            # Build node features: WLS estimates
            node_features = np.column_stack(
                [
                    wls_result.voltage_magnitudes,
                    wls_result.voltage_angles,
                ]
            )

            # Build edge index
            if len(edge_list) > 0:
                edge_index = np.array(edge_list, dtype=np.int64).T
            else:
                # Fallback: self-loops
                edge_index = np.array([[i, i] for i in range(n)], dtype=np.int64).T

            # Run GNN prediction
            from ml.predictive import PowerGridGNN

            gnn = PowerGridGNN(
                model_type="gcn", hidden_dim=self.hidden_dim, num_layers=self.num_layers
            )
            refined = gnn.predict(node_features, edge_index)

            # Blend: weighted average of WLS and GNN (80% WLS, 20% GNN)
            alpha = 0.8
            refined_magnitudes = alpha * wls_result.voltage_magnitudes + (1 - alpha) * refined[:, 0]
            refined_angles = alpha * wls_result.voltage_angles + (1 - alpha) * refined[:, 1]

            return StateEstimationResult(
                status=wls_result.status,
                voltage_magnitudes=refined_magnitudes,
                voltage_angles=refined_angles,
                iterations=wls_result.iterations,
                max_residual=wls_result.max_residual,
                objective_value=wls_result.objective_value,
                bad_data_detected=wls_result.bad_data_detected,
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"GNN refinement failed, using WLS only: {e}")
            return wls_result
