"""
AhmedETAP - Anomaly Detection Agent
=======================================================
Anomaly detection, classification, and diagnosis in power system
operational data, equipment measurements, and engineering study results.

Capabilities:
- Statistical process control (control charts, CUSUM, EWMA)
- Threshold-based anomaly detection against equipment ratings
- Pattern-based detection for unusual load, voltage, or current profiles
- Cross-correlation analysis across related measurements
- Time-series decomposition for trend and seasonal anomaly detection

Standards:
- IEEE C37.118: Synchrophasor measurements for power systems
- IEC 61850: Substation communication and monitoring data
- IEC 62443: Industrial communication networks — IT security
- NERC CIP: Critical infrastructure monitoring
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

UTC = UTC
from typing import Any, Dict, List

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class AnomalyAgent(BaseAgent):
    """
    Anomaly Detection Agent for Electrical Power Systems.

    Provides comprehensive anomaly detection, classification, and
    root-cause diagnosis using statistical and rule-based methods:

    - Statistical Process Control (SPC): Control charts with 3-sigma
      limits, CUSUM for detecting mean shifts, and EWMA for detecting
      small persistent shifts in process parameters.
    - Threshold Detection: Comparison of measurements against equipment
      ratings, operational limits, and alarm thresholds.
    - Pattern Detection: Identification of unusual load, voltage, or
      current profiles using deviation from historical baselines.
    - Cross-Correlation: Analysis of relationships between related
      measurements to detect inconsistent behaviour.
    - Time-Series Decomposition: Trend, seasonal, and residual
      decomposition for detecting anomalies in the residual component.

    Severity Classification:
    - CRITICAL: Immediate safety risk or cascading failure potential
    - HIGH: Significant deviation requiring prompt investigation
    - MEDIUM: Notable deviation warranting monitoring
    - LOW: Minor deviation, likely within measurement uncertainty
    """

    prompt_handle = "anomaly_agent"

    def __init__(self) -> None:
        super().__init__("AnomalyAgent")
        self.standards = [
            "IEEE C37.118",
            "IEC 61850",
            "IEC 62443",
            "NERC CIP",
        ]

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def detect_spc_anomalies(
        self,
        data: np.ndarray,
        sigma_threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Detect anomalies using Statistical Process Control (3-sigma rule).

        Identifies data points that fall outside the control limits
        defined as mu ± k*sigma, where k is the sigma threshold.

        Parameters
        ----------
        data : np.ndarray
            1-D array of measurement values.
        sigma_threshold : float
            Number of standard deviations for control limits (default 3.0).

        Returns
        -------
        Dict[str, Any]
            Dictionary with keys 'mean', 'std', 'ucl', 'lcl',
            'anomaly_indices', 'anomaly_values', 'anomaly_count',
            'anomaly_percentage', 'severity'.
        """
        mu = float(np.mean(data))
        sigma = float(np.std(data, ddof=1)) if len(data) > 1 else 0.0

        ucl = mu + sigma_threshold * sigma
        lcl = mu - sigma_threshold * sigma

        anomaly_mask = (data > ucl) | (data < lcl)
        anomaly_indices = np.where(anomaly_mask)[0].tolist()
        anomaly_values = data[anomaly_mask].tolist()

        anomaly_pct = (len(anomaly_indices) / len(data) * 100.0) if len(data) > 0 else 0.0

        # Severity classification
        if anomaly_pct > 10.0:
            severity = "CRITICAL"
        elif anomaly_pct > 5.0:
            severity = "HIGH"
        elif anomaly_pct > 2.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "mean": mu,
            "std": sigma,
            "ucl": ucl,
            "lcl": lcl,
            "sigma_threshold": sigma_threshold,
            "anomaly_indices": anomaly_indices,
            "anomaly_values": anomaly_values,
            "anomaly_count": len(anomaly_indices),
            "anomaly_percentage": anomaly_pct,
            "severity": severity,
            "total_samples": len(data),
        }

    def detect_cusum(
        self,
        data: np.ndarray,
        target: float | None = None,
        k: float = 0.5,
        h: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Detect mean shifts using the CUSUM (Cumulative Sum) method.

        The CUSUM statistic tracks cumulative deviations from a target
        value.  A shift is flagged when the CUSUM exceeds the decision
        interval h.

        Parameters
        ----------
        data : np.ndarray
            1-D array of measurement values.
        target : Optional[float]
            Target value (defaults to mean of data).
        k : float
            Reference value (slack), typically 0.5*sigma (default 0.5).
        h : float
            Decision interval threshold (default 5.0).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 's_hi', 's_lo', 'shift_detected',
            'shift_indices', 'shift_direction'.
        """
        if target is None:
            target = float(np.mean(data))

        sigma = float(np.std(data, ddof=1)) if len(data) > 1 else 1.0
        k_val = k * sigma
        h_val = h * sigma

        n = len(data)
        s_hi = np.zeros(n)
        s_lo = np.zeros(n)

        for i in range(1, n):
            s_hi[i] = max(0.0, s_hi[i - 1] + (data[i] - target) - k_val)
            s_lo[i] = max(0.0, s_lo[i - 1] - (data[i] - target) - k_val)

        hi_shifts = np.where(s_hi > h_val)[0].tolist()
        lo_shifts = np.where(s_lo > h_val)[0].tolist()

        shift_detected = len(hi_shifts) > 0 or len(lo_shifts) > 0
        shift_direction = "none"
        if hi_shifts and not lo_shifts:
            shift_direction = "upward"
        elif lo_shifts and not hi_shifts:
            shift_direction = "downward"
        elif hi_shifts and lo_shifts:
            shift_direction = "both"

        return {
            "s_hi": s_hi.tolist(),
            "s_lo": s_lo.tolist(),
            "shift_detected": shift_detected,
            "hi_shift_indices": hi_shifts,
            "lo_shift_indices": lo_shifts,
            "shift_direction": shift_direction,
            "target": target,
            "k_sigma": k,
            "h_sigma": h,
        }

    def detect_ewma(
        self,
        data: np.ndarray,
        lam: float = 0.1,
        l_factor: float = 2.7,
    ) -> Dict[str, Any]:
        """
        Detect small persistent shifts using EWMA (Exponentially Weighted
        Moving Average) control chart.

        The EWMA statistic at time t is:
            z_t = λ * x_t + (1 - λ) * z_{t-1}

        Control limits narrow over time to detect persistent small shifts
        more quickly than Shewhart charts.

        Parameters
        ----------
        data : np.ndarray
            1-D array of measurement values.
        lam : float
            Smoothing parameter (0 < λ ≤ 1), default 0.1.
        l_factor : float
            Control limit width factor, default 2.7.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'ewma_values', 'ucl', 'lcl',
            'anomaly_indices', 'shift_detected'.
        """
        mu0 = float(np.mean(data))
        sigma = float(np.std(data, ddof=1)) if len(data) > 1 else 1.0

        n = len(data)
        z = np.zeros(n)
        z[0] = lam * data[0] + (1.0 - lam) * mu0

        for i in range(1, n):
            z[i] = lam * data[i] + (1.0 - lam) * z[i - 1]

        # Time-varying control limits
        ucl = np.zeros(n)
        lcl = np.zeros(n)
        for i in range(n):
            limit_factor = (
                l_factor
                * sigma
                * np.sqrt(lam * (1.0 - (1.0 - lam) ** (2.0 * (i + 1))) / (2.0 - lam))
            )
            ucl[i] = mu0 + limit_factor
            lcl[i] = mu0 - limit_factor

        anomaly_mask = (z > ucl) | (z < lcl)
        anomaly_indices = np.where(anomaly_mask)[0].tolist()

        return {
            "ewma_values": z.tolist(),
            "ucl": ucl.tolist(),
            "lcl": lcl.tolist(),
            "anomaly_indices": anomaly_indices,
            "anomaly_count": len(anomaly_indices),
            "shift_detected": len(anomaly_indices) > 0,
            "lambda": lam,
            "l_factor": l_factor,
        }

    def detect_threshold_violations(
        self,
        data: np.ndarray,
        upper_limit: float,
        lower_limit: float,
    ) -> Dict[str, Any]:
        """
        Detect violations of hard operational limits.

        Compares each measurement against explicit upper and lower
        thresholds (e.g., equipment ratings, alarm limits).

        Parameters
        ----------
        data : np.ndarray
            1-D array of measurement values.
        upper_limit : float
            Maximum allowable value.
        lower_limit : float
            Minimum allowable value.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'violation_indices', 'violation_values',
            'violation_count', 'violation_percentage', 'max_deviation',
            'severity'.
        """
        over_mask = data > upper_limit
        under_mask = data < lower_limit
        violation_mask = over_mask | under_mask

        violation_indices = np.where(violation_mask)[0].tolist()
        violation_values = data[violation_mask].tolist()

        violation_pct = (len(violation_indices) / len(data) * 100.0) if len(data) > 0 else 0.0

        # Maximum deviation from limits
        over_deviation = float(np.max(data - upper_limit)) if np.any(over_mask) else 0.0
        under_deviation = float(np.max(lower_limit - data)) if np.any(under_mask) else 0.0
        max_deviation = max(over_deviation, under_deviation)

        # Severity based on margin of violation
        limit_range = upper_limit - lower_limit
        relative_deviation = max_deviation / limit_range if limit_range > 0 else 0.0
        if relative_deviation > 0.2:
            severity = "CRITICAL"
        elif relative_deviation > 0.1:
            severity = "HIGH"
        elif relative_deviation > 0.05:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "upper_limit": upper_limit,
            "lower_limit": lower_limit,
            "violation_indices": violation_indices,
            "violation_values": violation_values,
            "over_limit_count": int(np.sum(over_mask)),
            "under_limit_count": int(np.sum(under_mask)),
            "violation_count": len(violation_indices),
            "violation_percentage": violation_pct,
            "max_deviation": max_deviation,
            "relative_deviation": relative_deviation,
            "severity": severity,
        }

    def cross_correlation_analysis(
        self,
        data_a: np.ndarray,
        data_b: np.ndarray,
        correlation_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Detect anomalies via cross-correlation between related measurements.

        Under normal conditions, two correlated measurements should
        maintain a stable relationship.  A sudden change in correlation
        indicates an anomaly in one or both signals.

        Parameters
        ----------
        data_a : np.ndarray
            First measurement series, 1-D.
        data_b : np.ndarray
            Second measurement series, 1-D (same length as data_a).
        correlation_threshold : float
            Minimum expected absolute correlation (default 0.7).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'correlation', 'correlation_anomaly',
            'expected_threshold', 'interpretation'.
        """
        min_len = min(len(data_a), len(data_b))
        a = data_a[:min_len]
        b = data_b[:min_len]

        if len(a) < 3:
            return {
                "correlation": 0.0,
                "correlation_anomaly": True,
                "expected_threshold": correlation_threshold,
                "interpretation": "Insufficient data for correlation analysis",
            }

        corr_matrix = np.corrcoef(a, b)
        corr = float(corr_matrix[0, 1])

        correlation_anomaly = abs(corr) < correlation_threshold

        if correlation_anomaly:
            interpretation = (
                f"Correlation ({corr:.3f}) below expected threshold "
                f"({correlation_threshold:.3f}). Possible decoupling "
                "of related measurements indicating an anomaly."
            )
        else:
            interpretation = (
                f"Correlation ({corr:.3f}) within expected range. Measurements are consistent."
            )

        return {
            "correlation": corr,
            "correlation_anomaly": correlation_anomaly,
            "expected_threshold": correlation_threshold,
            "interpretation": interpretation,
        }

    def detect_ml_anomaly(
        self,
        data: np.ndarray,
        method: str = "iforest",
        contamination: float = 0.05,
    ) -> Dict[str, Any]:
        """
        ML-based anomaly detection using Isolation Forest / PyOD.

        Parameters
        ----------
        data : np.ndarray
            2-D array of shape (n_samples, n_features) for multi-variate detection,
            or 1-D for single-feature detection.
        method : str
            Detection method: 'iforest', 'pyod_iforest', 'pyod_knn', or 'pyod_autoencoder'.
        contamination : float
            Expected proportion of anomalies (0, 0.5].

        Returns
        -------
        Dict[str, Any]
            Anomaly detection results with scores and classifications.
        """
        from ml.predictive import AnomalyDetector

        if data.ndim == 1:
            data = data.reshape(-1, 1)

        ad = AnomalyDetector(contamination=contamination, method=method)
        train_result = ad.train(data)
        detect_result = ad.detect(data)

        # Determine severity based on anomaly percentage
        anomaly_pct = (detect_result["n_anomalies"] / len(data) * 100) if len(data) > 0 else 0.0
        if anomaly_pct > 10.0:
            severity = "CRITICAL"
        elif anomaly_pct > 5.0:
            severity = "HIGH"
        elif anomaly_pct > 2.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            **detect_result,
            "contamination": contamination,
            "training_info": train_result,
            "anomaly_percentage": round(anomaly_pct, 2),
            "severity": severity,
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute anomaly detection task.

        Dispatches to the appropriate detection method based on
        ``task.parameters['detection_method']`` which must be one of:
        ``'spc'``, ``'cusum'``, ``'ewma'``, ``'threshold'``,
        ``'cross_correlation'``, ``'ml'``, or ``'full'`` (runs SPC + CUSUM + EWMA).
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting anomaly detection for task {task.task_id}")

            method = task.parameters.get("detection_method", "full")
            results: Dict[str, Any] = {}

            measurements = task.parameters.get("measurements")
            if measurements is None:
                raise ValueError("'measurements' parameter is required for anomaly detection")

            data = np.array(measurements, dtype=float)

            # --- SPC anomaly detection ---
            if method in ("spc", "full"):
                sigma_threshold = float(task.parameters.get("sigma_threshold", 3.0))
                results["spc"] = self.detect_spc_anomalies(
                    data=data,
                    sigma_threshold=sigma_threshold,
                )

            # --- CUSUM shift detection ---
            if method in ("cusum", "full"):
                target = task.parameters.get("target")
                target_val = float(target) if target is not None else None
                k = float(task.parameters.get("cusum_k", 0.5))
                h = float(task.parameters.get("cusum_h", 5.0))
                results["cusum"] = self.detect_cusum(
                    data=data,
                    target=target_val,
                    k=k,
                    h=h,
                )

            # --- EWMA detection ---
            if method in ("ewma", "full"):
                lam = float(task.parameters.get("ewma_lambda", 0.1))
                l_factor = float(task.parameters.get("ewma_l_factor", 2.7))
                results["ewma"] = self.detect_ewma(
                    data=data,
                    lam=lam,
                    l_factor=l_factor,
                )

            # --- Threshold violation detection ---
            if method in ("threshold", "full"):
                upper_limit = (
                    float(task.parameters.get("upper_limit", np.max(data) * 1.1))
                    if "upper_limit" in task.parameters
                    else None
                )
                lower_limit = (
                    float(task.parameters.get("lower_limit", np.min(data) * 0.9))
                    if "lower_limit" in task.parameters
                    else None
                )
                if upper_limit is None or lower_limit is None:
                    # Skip threshold detection if limits not explicitly provided
                    self.log_execution(
                        "Threshold detection skipped: upper_limit and lower_limit must be explicitly provided",
                        "WARNING",
                    )
                else:
                    results["threshold"] = self.detect_threshold_violations(
                        data=data,
                        upper_limit=upper_limit,
                        lower_limit=lower_limit,
                    )

            # --- Cross-correlation analysis ---
            if method == "cross_correlation":
                secondary = task.parameters.get("secondary_measurements")
                if secondary is None:
                    raise ValueError(
                        "'secondary_measurements' required for cross_correlation method"
                    )
                data_b = np.array(secondary, dtype=float)
                corr_threshold = float(task.parameters.get("correlation_threshold", 0.7))
                results["cross_correlation"] = self.cross_correlation_analysis(
                    data_a=data,
                    data_b=data_b,
                    correlation_threshold=corr_threshold,
                )

            # --- ML-based anomaly detection (PyOD) ---
            if method in ("ml", "full"):
                ml_method = task.parameters.get("ml_method", "iforest")
                contamination = float(task.parameters.get("contamination", 0.05))
                if data.ndim == 1:
                    ml_data = data.reshape(-1, 1)
                else:
                    ml_data = data
                results["ml_anomaly"] = self.detect_ml_anomaly(
                    data=ml_data,
                    method=ml_method,
                    contamination=contamination,
                )

            # Determine overall severity (worst case)
            severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            overall_severity = "LOW"
            for _key, val in results.items():
                sev = val.get("severity", "LOW")
                if severity_order.get(sev, 0) > severity_order.get(overall_severity, 0):
                    overall_severity = sev

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "overall_severity": overall_severity,
                    "detection_method": method,
                    "standards": self.standards,
                    "sample_count": len(data),
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Anomaly detection completed in {execution_time:.2f}s "
                f"(severity={overall_severity})"
            )
            return result

        except Exception as e:
            self.log_execution(f"Anomaly detection failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate anomaly detection results.

        Checks:
        - At least one detection method produced results
        - Anomaly counts are non-negative integers
        - Severity classification is valid
        """
        errors: List[str] = []

        if not result.data:
            errors.append("No anomaly detection results produced")
            result.validation_errors.extend(errors)
            return False

        valid_methods = {"spc", "cusum", "ewma", "threshold", "cross_correlation", "ml_anomaly"}
        found_methods = set(result.data.keys()) & valid_methods
        if not found_methods:
            errors.append("No valid detection method results found")

        for method_key in found_methods:
            method_data = result.data[method_key]
            if not isinstance(method_data, dict):
                errors.append(f"Results for '{method_key}' are not a dictionary")
                continue

            count = method_data.get("anomaly_count", method_data.get("violation_count", 0))
            if not isinstance(count, int) or count < 0:
                errors.append(f"Invalid anomaly count ({count}) for method '{method_key}'")

            severity = method_data.get("severity", "")
            if severity and severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                errors.append(f"Invalid severity '{severity}' for method '{method_key}'")

        result.validation_errors.extend(errors)
        return len(errors) == 0
