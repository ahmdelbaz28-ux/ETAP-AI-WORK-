"""
ETAP AI Engineering Platform - Digital Twin Agent
==================================================
Real-time synchronization between physical power system assets and
their digital twin representations.

Capabilities:
- Topological synchronization (one-line diagram ↔ physical connectivity)
- Parameter synchronization (model parameters ↔ as-built data)
- State synchronization (operating states ↔ real-time measurements)
- Behavioral synchronization (model response ↔ physical behavior)
- Model drift detection and calibration recommendations

Standards:
- ISO 23247: Digital Twin Framework for Manufacturing
- IEC 63278: Asset Administration Shell for Industrial Digital Twin
- IEC 61850: Real-time data exchange
- ISO 15926: Industrial data integration
- OPC UA (IEC 62541): Interoperability
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class DigitalTwinAgent(BaseAgent):
    """
    Digital Twin Synchronization Agent.

    Maintains real-time synchronization between physical power system
    assets and their digital twin representations, ensuring model
    accuracy, state consistency, and predictive capability.

    Synchronization aspects:
    - **Topological**: Ensures the one-line diagram matches physical
      connectivity. Detects topology changes (switching operations,
      maintenance outages) and updates the digital model accordingly.
    - **Parameter**: Validates model parameters (impedances, ratings,
      tap positions) against as-built data and manufacturer specs.
    - **State**: Maintains real-time alignment of operating states
      (voltages, currents, power flows, tap positions) using SCADA
      measurements and state estimation.
    - **Behavioral**: Verifies model response matches physical behavior
      by comparing simulated results against measured responses to
      known events (faults, switching, load changes).

    Drift detection uses statistical distance metrics (Mahalanobis
    distance) between model predictions and measurements to quantify
    model quality over time.

    Key metrics:
    - Model Deviation Index (MDI): Normalized distance between
      predicted and measured states
    - Data Quality Index (DQI): Percentage of measurements meeting
      quality criteria (completeness, consistency, timeliness)
    - Predictive Confidence Level (PCL): Confidence in model
      predictions based on historical accuracy
    """

    prompt_handle = "digital_twin_agent"

    def __init__(self) -> None:
        super().__init__("DigitalTwinAgent")
        self.standards = [
            "ISO 23247",
            "IEC 63278",
            "IEC 61850",
            "ISO 15926",
            "IEC 62541",
        ]

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def compute_model_deviation_index(
        self,
        predicted: np.ndarray,
        measured: np.ndarray,
        covariance: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Compute Model Deviation Index (MDI) between predicted and
        measured values.

        Uses the Mahalanobis distance when a covariance matrix is
        provided, or the Euclidean distance normalized by measurement
        magnitude otherwise.

        Parameters
        ----------
        predicted : np.ndarray
            Model-predicted values, 1-D array.
        measured : np.ndarray
            Measured (SCADA) values, 1-D array (same length).
        covariance : Optional[np.ndarray]
            Measurement covariance matrix. If provided, Mahalanobis
            distance is used; otherwise, normalized Euclidean.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'mdi', 'max_deviation', 'mean_deviation',
            'deviation_per_variable', 'status'.
        """
        diff = predicted - measured
        abs_diff = np.abs(diff)

        if covariance is not None and len(covariance.shape) == 2:
            try:
                cov_inv = np.linalg.inv(covariance)
                mdi = float(np.sqrt(diff @ cov_inv @ diff))
            except np.linalg.LinAlgError:
                # Singular covariance: fall back to Euclidean
                mdi = float(np.linalg.norm(diff) / (np.linalg.norm(measured) + 1e-10))
        else:
            # Normalized Euclidean distance
            norm_measured = np.linalg.norm(measured)
            mdi = float(np.linalg.norm(diff) / (norm_measured if norm_measured > 1e-10 else 1.0))

        max_dev = float(np.max(abs_diff)) if len(abs_diff) > 0 else 0.0
        mean_dev = float(np.mean(abs_diff))

        # Per-variable deviation (percentage if measured > 0)
        deviation_per_var = []
        for i in range(len(diff)):
            if abs(measured[i]) > 1e-10:
                deviation_per_var.append(
                    {"index": i, "absolute": float(abs_diff[i]), "percent": float(abs_diff[i] / abs(measured[i]) * 100.0)}
                )
            else:
                deviation_per_var.append(
                    {"index": i, "absolute": float(abs_diff[i]), "percent": None}
                )

        # Status classification
        if mdi < 0.05:
            status = "synchronized"
        elif mdi < 0.10:
            status = "minor_drift"
        elif mdi < 0.20:
            status = "moderate_drift"
        elif mdi < 0.50:
            status = "significant_drift"
        else:
            status = "critical_drift"

        return {
            "mdi": round(mdi, 6),
            "max_deviation": round(max_dev, 6),
            "mean_deviation": round(mean_dev, 6),
            "deviation_per_variable": deviation_per_var,
            "variable_count": len(diff),
            "status": status,
        }

    def compute_data_quality_index(
        self,
        measurements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute Data Quality Index (DQI) for SCADA measurements.

        Evaluates completeness, consistency, and timeliness of
        measurement data feeding the digital twin.

        Parameters
        ----------
        measurements : List[Dict[str, Any]]
            List of measurement records, each with keys:
            'tag', 'value', 'quality_code' (GOOD/BAD/UNCERTAIN),
            'timestamp' (ISO 8601), 'expected_update_s'.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'dqi_percent', 'completeness_percent',
            'consistency_percent', 'timeliness_percent', 'bad_tags'.
        """
        total = len(measurements)
        if total == 0:
            return {
                "dqi_percent": 0.0,
                "completeness_percent": 0.0,
                "consistency_percent": 0.0,
                "timeliness_percent": 0.0,
                "bad_tags": [],
            }

        now = datetime.now(timezone.utc)
        good_count = 0
        bad_tags: List[str] = []
        timely_count = 0
        valid_count = 0

        for m in measurements:
            quality = m.get("quality_code", "GOOD")
            value = m.get("value")

            # Completeness: value exists and is not None
            if value is not None and quality != "BAD":
                valid_count += 1
            else:
                bad_tags.append(m.get("tag", "unknown"))
                continue

            # Consistency: quality is GOOD
            if quality == "GOOD":
                good_count += 1

            # Timeliness: measurement is recent enough
            ts_str = m.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    age = (now - ts).total_seconds()
                    expected_s = m.get("expected_update_s", 10.0)
                    if age <= 3.0 * expected_s:
                        timely_count += 1
                except (ValueError, TypeError):
                    pass
            else:
                timely_count += 1  # No timestamp check possible

        completeness = valid_count / total * 100.0
        consistency = good_count / total * 100.0 if total > 0 else 0.0
        timeliness = timely_count / total * 100.0 if total > 0 else 0.0

        # DQI is a weighted average: 40% completeness, 30% consistency, 30% timeliness
        dqi = 0.4 * completeness + 0.3 * consistency + 0.3 * timeliness

        return {
            "dqi_percent": round(dqi, 2),
            "completeness_percent": round(completeness, 2),
            "consistency_percent": round(consistency, 2),
            "timeliness_percent": round(timeliness, 2),
            "total_measurements": total,
            "good_measurements": good_count,
            "bad_tags": bad_tags,
        }

    def compute_predictive_confidence(
        self,
        historical_mdi: List[float],
        recent_window: int = 10,
    ) -> Dict[str, Any]:
        """
        Compute Predictive Confidence Level (PCL) based on historical
        model deviation trends.

        Parameters
        ----------
        historical_mdi : List[float]
            Time-ordered list of Model Deviation Index values.
        recent_window : int
            Number of most recent MDI values to use for trend
            assessment (default 10).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'pcl_percent', 'trend', 'recent_mean_mdi',
            'overall_mean_mdi', 'recommendation'.
        """
        if not historical_mdi:
            return {
                "pcl_percent": 0.0,
                "trend": "unknown",
                "recent_mean_mdi": 0.0,
                "overall_mean_mdi": 0.0,
                "recommendation": "Insufficient historical data; collect more measurements",
            }

        mdi_arr = np.array(historical_mdi)
        overall_mean = float(np.mean(mdi_arr))
        recent = mdi_arr[-recent_window:] if len(mdi_arr) >= recent_window else mdi_arr
        recent_mean = float(np.mean(recent))

        # Trend: compare recent mean to overall mean
        if len(mdi_arr) >= recent_window:
            older_mean = float(np.mean(mdi_arr[:-recent_window]))
            if recent_mean > older_mean * 1.2:
                trend = "degrading"
            elif recent_mean < older_mean * 0.8:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # PCL: inverse of recent_mean_mdi, capped at 0-100%
        # PCL = max(0, 100 - recent_mean * 200)
        pcl = max(0.0, min(100.0, 100.0 - recent_mean * 200.0))

        # Recommendation
        if pcl >= 80:
            recommendation = "Model is well-calibrated; continue routine synchronization"
        elif pcl >= 60:
            recommendation = "Model quality is acceptable; schedule recalibration soon"
        elif pcl >= 40:
            recommendation = "Model drift detected; recalibration recommended"
        else:
            recommendation = "Significant model drift; immediate recalibration required"

        return {
            "pcl_percent": round(pcl, 2),
            "trend": trend,
            "recent_mean_mdi": round(recent_mean, 6),
            "overall_mean_mdi": round(overall_mean, 6),
            "recommendation": recommendation,
            "data_points": len(historical_mdi),
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute digital twin synchronization task.

        Dispatches to the appropriate method based on
        ``task.parameters['analysis_type']`` which must be one of:
        ``'model_deviation'``, ``'data_quality'``,
        ``'predictive_confidence'``, or ``'full'``.
        """
        start_time = datetime.now(timezone.utc)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(
                f"Starting digital twin synchronization for task {task.task_id}"
            )

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}

            # --- Model Deviation Index ---
            if analysis_type in ("model_deviation", "full"):
                predicted = task.parameters.get("predicted_values")
                measured = task.parameters.get("measured_values")
                if predicted is None or measured is None:
                    raise ValueError(
                        "'predicted_values' and 'measured_values' required "
                        "for model deviation analysis"
                    )
                pred_arr = np.array(predicted, dtype=float)
                meas_arr = np.array(measured, dtype=float)
                cov = task.parameters.get("covariance_matrix")
                cov_arr = np.array(cov, dtype=float) if cov is not None else None

                results["model_deviation"] = self.compute_model_deviation_index(
                    predicted=pred_arr,
                    measured=meas_arr,
                    covariance=cov_arr,
                )

            # --- Data Quality Index ---
            if analysis_type in ("data_quality", "full"):
                measurements = task.parameters.get("measurements", [])
                results["data_quality"] = self.compute_data_quality_index(
                    measurements=measurements,
                )

            # --- Predictive Confidence Level ---
            if analysis_type in ("predictive_confidence", "full"):
                historical_mdi = task.parameters.get("historical_mdi", [])
                recent_window = int(task.parameters.get("recent_window", 10))
                results["predictive_confidence"] = self.compute_predictive_confidence(
                    historical_mdi=historical_mdi,
                    recent_window=recent_window,
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "analysis_type": analysis_type,
                    "standards": self.standards,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(
                f"Digital twin synchronization completed in {execution_time:.2f}s"
            )
            return result

        except Exception as e:
            self.log_execution(
                f"Digital twin synchronization failed: {str(e)}", "ERROR"
            )
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
        Validate digital twin synchronization results.

        Checks:
        - MDI is non-negative and finite
        - DQI is between 0 and 100
        - PCL is between 0 and 100
        - Synchronization status is valid
        """
        errors: List[str] = []

        md_data = result.data.get("model_deviation")
        if md_data is not None:
            mdi = md_data.get("mdi", 0.0)
            if mdi < 0:
                errors.append(f"MDI is negative: {mdi:.6f}")
            if not np.isfinite(mdi):
                errors.append(f"MDI is not finite: {mdi}")
            status = md_data.get("status", "")
            valid_statuses = {
                "synchronized", "minor_drift", "moderate_drift",
                "significant_drift", "critical_drift",
            }
            if status and status not in valid_statuses:
                errors.append(f"Invalid synchronization status: {status}")

        dq_data = result.data.get("data_quality")
        if dq_data is not None:
            dqi = dq_data.get("dqi_percent", 0.0)
            if dqi < 0 or dqi > 100:
                errors.append(f"DQI out of range: {dqi:.2f}%")

        pcl_data = result.data.get("predictive_confidence")
        if pcl_data is not None:
            pcl = pcl_data.get("pcl_percent", 0.0)
            if pcl < 0 or pcl > 100:
                errors.append(f"PCL out of range: {pcl:.2f}%")

        result.validation_errors.extend(errors)
        return len(errors) == 0
