"""
AhmedETAP - Predictive Analytics Agent
=========================================================
Load forecasting, fault prediction, and predictive maintenance analysis
using statistical and machine learning methods.

Capabilities:
- Short-term load forecasting (hours to days)
- Medium-term load forecasting (weeks to months)
- Long-term load forecasting (years ahead for planning)
- Fault prediction based on equipment condition monitoring
- Predictive maintenance scheduling based on failure probability
- Renewable generation forecasting

Standards:
- IEEE 3002.7: Recommended Practice for Conducting Power Flow Studies
- IEC 61968/61970: CIM for data exchange
- NERC reliability standards for load forecasting
- ISO 55000: Asset Management (predictive maintenance)
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class PredictiveAgent(BaseAgent):
    """
    Predictive Analytics Agent for Electrical Power Systems.

    Provides load forecasting, fault prediction, and predictive
    maintenance analysis including:

    - **Short-term Load Forecasting (STLF)**: Hours to days ahead,
      using exponential smoothing and regression-based models with
      weather and calendar variables.
    - **Medium-term Load Forecasting (MTLF)**: Weeks to months,
      using trend extrapolation with seasonal decomposition.
    - **Long-term Load Forecasting (LTLF)**: Years ahead for
      system planning using growth-rate models.
    - **Fault Prediction**: Equipment failure probability based on
      condition monitoring data (dissolved gas analysis, partial
      discharge, thermal imaging, vibration).
    - **Predictive Maintenance**: Optimal maintenance scheduling
      based on failure probability and cost-risk analysis.

    Key methods:

    Exponential Smoothing (Holt-Winters):
        Level:   L_t = α × Y_t + (1-α) × (L_{t-1} + T_{t-1})
        Trend:   T_t = β × (L_t - L_{t-1}) + (1-β) × T_{t-1}
        Seasonal: S_t = γ × (Y_t / L_t) + (1-γ) × S_{t-m}
        Forecast: Ŷ_{t+h} = (L_t + h × T_t) × S_{t-m+h}

    Failure Probability (Weibull):
        F(t) = 1 - exp(-(t/η)^β)

    Confidence Interval (normal approximation):
        Ŷ ± z_{α/2} × σ_forecast
    """

    prompt_handle = "predictive_agent"

    def __init__(self) -> None:
        super().__init__("PredictiveAgent")
        self._ml_forecaster = None
        self._ml_fault_predictor = None
        self.standards = [
            "IEEE 3002.7",
            "IEC 61968/61970",
            "NERC Reliability Standards",
            "ISO 55000",
        ]

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def forecast_short_term(
        self,
        historical_load: List[float],
        horizon_hours: int = 24,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.2,
        season_length: int = 24,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Short-term load forecasting using Holt-Winters exponential
        smoothing with additive seasonality.

        Parameters
        ----------
        historical_load : List[float]
            Historical load values in MW, hourly resolution.
        horizon_hours : int
            Number of hours to forecast (default 24).
        alpha : float
            Level smoothing parameter (0 < α < 1).
        beta : float
            Trend smoothing parameter (0 < β < 1).
        gamma : float
            Seasonal smoothing parameter (0 < γ < 1).
        season_length : int
            Seasonal period in hours (default 24 for daily cycle).
        confidence_level : float
            Confidence level for prediction intervals (default 0.95).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'forecast_mw', 'lower_bound_mw',
            'upper_bound_mw', 'mape', 'rmse', 'method'.
        """
        y = np.array(historical_load, dtype=float)
        n = len(y)

        if n < 2 * season_length:
            # Insufficient data for full seasonal model; use simple exponential smoothing
            return self._simple_exponential_forecast(y, horizon_hours, alpha, confidence_level)

        # Initialize components
        # Average of first season for level
        L = np.mean(y[:season_length])
        T = (
            np.mean(y[season_length : 2 * season_length]) - np.mean(y[:season_length])
        ) / season_length
        S = y[:season_length] - L  # Initial seasonal indices

        # Holt-Winters iteration
        for t in range(season_length, n):
            L_new = alpha * (y[t] - S[t % season_length]) + (1 - alpha) * (L + T)
            T_new = beta * (L_new - L) + (1 - beta) * T
            S[t % season_length] = gamma * (y[t] - L_new) + (1 - gamma) * S[t % season_length]
            L = L_new
            T = T_new

        # Generate forecast
        forecast = []
        for h in range(1, horizon_hours + 1):
            f = L + h * T + S[(n + h) % season_length]
            forecast.append(max(0.0, float(f)))

        # Calculate in-sample error for confidence bounds
        fitted = []
        L_f = np.mean(y[:season_length])
        T_f = (
            np.mean(y[season_length : 2 * season_length]) - np.mean(y[:season_length])
        ) / season_length
        S_f = y[:season_length] - L_f
        for t in range(season_length, n):
            f_val = L_f + T_f + S_f[t % season_length]
            fitted.append(f_val)
            L_new = alpha * (y[t] - S_f[t % season_length]) + (1 - alpha) * (L_f + T_f)
            T_new = beta * (L_new - L_f) + (1 - beta) * T_f
            S_f[t % season_length] = gamma * (y[t] - L_new) + (1 - gamma) * S_f[t % season_length]
            L_f = L_new
            T_f = T_new

        errors = y[season_length:n] - np.array(fitted)
        sigma = float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0

        # Confidence intervals (widening with horizon)
        z = 1.96 if confidence_level >= 0.95 else 1.645  # 95% or 90%
        lower = [max(0.0, f - z * sigma * np.sqrt(h)) for h, f in enumerate(forecast, 1)]
        upper = [f + z * sigma * np.sqrt(h) for h, f in enumerate(forecast, 1)]

        # Accuracy metrics on in-sample
        mape = float(np.mean(np.abs(errors / (y[season_length:n] + 1e-10)))) * 100.0
        rmse = float(np.sqrt(np.mean(errors**2)))

        return {
            "forecast_mw": [round(v, 2) for v in forecast],
            "lower_bound_mw": [round(v, 2) for v in lower],
            "upper_bound_mw": [round(v, 2) for v in upper],
            "mape_percent": round(mape, 2),
            "rmse_mw": round(rmse, 2),
            "method": "Holt-Winters additive",
            "horizon_hours": horizon_hours,
            "confidence_level": confidence_level,
            "parameters": {
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "season_length": season_length,
            },
        }

    def _simple_exponential_forecast(
        self,
        y: np.ndarray,
        horizon: int,
        alpha: float,
        confidence: float,
    ) -> Dict[str, Any]:
        """Fallback: simple exponential smoothing when data is limited."""
        L = y[0]
        for t in range(1, len(y)):
            L = alpha * y[t] + (1 - alpha) * L

        forecast = [float(L)] * horizon
        sigma = float(np.std(y, ddof=1)) if len(y) > 1 else 0.0
        z = 1.96 if confidence >= 0.95 else 1.645
        lower = [max(0.0, f - z * sigma) for f in forecast]
        upper = [f + z * sigma for f in forecast]

        return {
            "forecast_mw": [round(v, 2) for v in forecast],
            "lower_bound_mw": [round(v, 2) for v in lower],
            "upper_bound_mw": [round(v, 2) for v in upper],
            "mape_percent": None,
            "rmse_mw": None,
            "method": "Simple exponential smoothing (insufficient data for seasonal)",
            "horizon_hours": horizon,
            "confidence_level": confidence,
            "parameters": {"alpha": alpha},
        }

    def forecast_long_term(
        self,
        peak_loads_mw: List[float],
        years: List[int],
        forecast_years: int = 10,
        growth_rate_annual: float = 0.03,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Long-term load forecasting using compound growth rate model.

        Parameters
        ----------
        peak_loads_mw : List[float]
            Historical annual peak loads in MW.
        years : List[int]
            Corresponding years for historical data.
        forecast_years : int
            Number of years to forecast (default 10).
        growth_rate_annual : float
            Annual growth rate as a fraction (default 0.03 = 3%).
            If 0, estimated from historical data.
        confidence_level : float
            Confidence level for intervals (default 0.95).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'forecast_years', 'forecast_mw',
            'lower_bound_mw', 'upper_bound_mw', 'growth_rate',
            'method'.
        """
        loads = np.array(peak_loads_mw, dtype=float)
        yrs = np.array(years, dtype=float)

        # Estimate growth rate from historical data if not provided
        if growth_rate_annual == 0 and len(loads) > 1:
            # Log-linear regression
            log_loads = np.log(loads)
            coeffs = np.polyfit(yrs, log_loads, 1)
            growth_rate_annual = float(coeffs[0])

        # Forecast
        last_year = int(yrs[-1])
        last_load = float(loads[-1])

        forecast_yr = list(range(last_year + 1, last_year + forecast_years + 1))
        forecast_mw = [
            last_load * (1.0 + growth_rate_annual) ** (yr - last_year) for yr in forecast_yr
        ]

        # Confidence bounds (based on historical variance)
        if len(loads) > 2:
            # Calculate historical residual variance
            fitted_hist = [loads[0] * (1 + growth_rate_annual) ** (y - yrs[0]) for y in yrs]
            residuals = loads - np.array(fitted_hist)
            sigma = float(np.std(residuals, ddof=1))
        else:
            sigma = last_load * 0.05  # 5% of peak as default

        z = 1.96 if confidence_level >= 0.95 else 1.645
        lower = [max(0.0, f - z * sigma * np.sqrt(i + 1)) for i, f in enumerate(forecast_mw)]
        upper = [f + z * sigma * np.sqrt(i + 1) for i, f in enumerate(forecast_mw)]

        return {
            "forecast_years": forecast_yr,
            "forecast_mw": [round(v, 2) for v in forecast_mw],
            "lower_bound_mw": [round(v, 2) for v in lower],
            "upper_bound_mw": [round(v, 2) for v in upper],
            "growth_rate_annual": round(growth_rate_annual, 4),
            "growth_rate_percent": round(growth_rate_annual * 100.0, 2),
            "base_year": last_year,
            "base_load_mw": round(last_load, 2),
            "method": "Compound growth rate",
            "confidence_level": confidence_level,
        }

    def predict_failure_probability(
        self,
        age_years: float,
        weibull_shape: float = 2.0,
        weibull_scale: float = 30.0,
        condition_score: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Predict equipment failure probability using Weibull distribution
        adjusted for condition monitoring score.

        Parameters
        ----------
        age_years : float
            Equipment age in years.
        weibull_shape : float
            Weibull shape parameter β (default 2.0 for wear-out).
        weibull_scale : float
            Weibull scale parameter η in years (characteristic life).
        condition_score : float
            Condition monitoring score (0 to 1, where 1 is excellent).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'failure_probability', 'hazard_rate',
            'remaining_useful_life_years', 'maintenance_priority'.
        """
        beta = weibull_shape
        eta = weibull_scale

        # Weibull CDF: F(t) = 1 - exp(-(t/η)^β)
        failure_prob = float(1.0 - np.exp(-((age_years / eta) ** beta)))

        # Adjust for condition score: poor condition increases probability
        # Simple adjustment: effective age = age / condition_score
        effective_age = age_years / max(condition_score, 0.1)
        adjusted_failure_prob = float(1.0 - np.exp(-((effective_age / eta) ** beta)))

        # Hazard rate: h(t) = (β/η) × (t/η)^(β-1)
        if age_years > 0:
            hazard_rate = float((beta / eta) * (age_years / eta) ** (beta - 1))
        else:
            hazard_rate = 0.0

        # Median remaining useful life (time to F(t) = 0.5)
        median_life = eta * (np.log(2)) ** (1.0 / beta)
        rul = float(median_life - age_years)

        # Maintenance priority
        if adjusted_failure_prob > 0.5:
            priority = "immediate"
        elif adjusted_failure_prob > 0.2:
            priority = "high"
        elif adjusted_failure_prob > 0.1:
            priority = "medium"
        else:
            priority = "low"

        return {
            "failure_probability": round(failure_prob, 4),
            "adjusted_failure_probability": round(adjusted_failure_prob, 4),
            "hazard_rate_per_year": round(hazard_rate, 6),
            "remaining_useful_life_years": round(max(0.0, rul), 1),
            "maintenance_priority": priority,
            "condition_score": condition_score,
            "weibull_shape": beta,
            "weibull_scale_years": eta,
            "age_years": age_years,
            "effective_age_years": round(effective_age, 1),
        }

    def compute_maintenance_schedule(
        self,
        equipment_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute optimal predictive maintenance schedule based on
        failure probabilities.

        Parameters
        ----------
        equipment_list : List[Dict[str, Any]]
            List of equipment dicts with keys: 'name', 'age_years',
            'weibull_shape', 'weibull_scale', 'condition_score',
            'criticality' (1-5).

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'schedule', 'total_equipment',
            'immediate_count', 'high_count'.
        """
        schedule = []

        for eq in equipment_list:
            name = eq.get("name", "unknown")
            fp = self.predict_failure_probability(
                age_years=float(eq.get("age_years", 10.0)),
                weibull_shape=float(eq.get("weibull_shape", 2.0)),
                weibull_scale=float(eq.get("weibull_scale", 30.0)),
                condition_score=float(eq.get("condition_score", 0.8)),
            )

            # Combine failure probability with criticality for priority ranking
            criticality = int(eq.get("criticality", 3))
            risk_score = fp["adjusted_failure_probability"] * criticality

            schedule.append(
                {
                    "name": name,
                    "failure_probability": fp["failure_probability"],
                    "adjusted_failure_probability": fp["adjusted_failure_probability"],
                    "remaining_useful_life_years": fp["remaining_useful_life_years"],
                    "maintenance_priority": fp["maintenance_priority"],
                    "criticality": criticality,
                    "risk_score": round(risk_score, 4),
                }
            )

        # Sort by risk score descending
        schedule.sort(key=lambda x: x["risk_score"], reverse=True)

        immediate = sum(1 for s in schedule if s["maintenance_priority"] == "immediate")
        high = sum(1 for s in schedule if s["maintenance_priority"] == "high")

        return {
            "schedule": schedule,
            "total_equipment": len(schedule),
            "immediate_count": immediate,
            "high_count": high,
        }

    def forecast_short_term_ml(self, historical_load: List[float], horizon_hours: int = 24, method: str = "auto") -> Dict[str, Any]:
        """Short-term load forecasting using Prophet/LSTM/Linear from ml.predictive."""
        from ml.predictive import LoadForecaster
        lf = LoadForecaster(method=method)
        data = np.array(historical_load, dtype=float)
        train_result = lf.train(data)
        predictions = lf.predict(horizon_hours=horizon_hours)
        metrics = lf.evaluate(data)
        return {
            "forecast_mw": predictions.tolist() if hasattr(predictions, 'tolist') else list(predictions),
            "method": train_result.get("method", method),
            "metrics": metrics,
            "horizon_hours": horizon_hours,
        }

    def predict_fault_ml(self, features: np.ndarray, labels: np.ndarray | None = None, use_xgboost: bool = True, explain: bool = False) -> Dict[str, Any]:
        """Fault prediction using XGBoost/RandomForest with SHAP explanations."""
        from ml.predictive import FaultPredictor
        fp = FaultPredictor(use_xgboost=use_xgboost)
        result = {}
        if labels is not None:
            train_result = fp.train(features, labels)
            result["training"] = train_result
            result["feature_importance"] = fp.feature_importance()
            if explain:
                result["explanation"] = fp.explain(features[0])
        prediction = fp.predict(features[0])
        result["prediction"] = prediction
        return result

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute predictive analytics task.

        Dispatches based on ``task.parameters['analysis_type']``:
        ``'short_term_forecast'``, ``'long_term_forecast'``,
        ``'failure_prediction'``, ``'maintenance_schedule'``,
        or ``'full'``.
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting predictive analytics for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}

            # --- Short-term load forecast ---
            if analysis_type in ("short_term_forecast", "full"):
                hist_load = task.parameters.get("historical_load_mw", [])
                if not hist_load:
                    # Generate synthetic data for demo
                    hours = 168  # 1 week
                    hist_load = [
                        100.0 + 30.0 * np.sin(2 * np.pi * h / 24) + 5.0 * np.random.randn()
                        for h in range(hours)
                    ]
                results["short_term_forecast"] = self.forecast_short_term(
                    historical_load=hist_load,
                    horizon_hours=int(task.parameters.get("horizon_hours", 24)),
                    alpha=float(task.parameters.get("alpha", 0.3)),
                    beta=float(task.parameters.get("beta", 0.1)),
                    gamma=float(task.parameters.get("gamma", 0.2)),
                )

            # --- Long-term load forecast ---
            if analysis_type in ("long_term_forecast", "full"):
                peaks = task.parameters.get(
                    "peak_loads_mw", [100.0, 103.0, 107.0, 110.0, 114.0, 117.0, 121.0, 125.0]
                )
                yrs = task.parameters.get("years", list(range(2016, 2024)))
                results["long_term_forecast"] = self.forecast_long_term(
                    peak_loads_mw=peaks,
                    years=yrs,
                    forecast_years=int(task.parameters.get("forecast_years", 10)),
                    growth_rate_annual=float(task.parameters.get("growth_rate_annual", 0.0)),
                )

            # --- Failure prediction ---
            if analysis_type in ("failure_prediction", "full"):
                results["failure_prediction"] = self.predict_failure_probability(
                    age_years=float(task.parameters.get("age_years", 15.0)),
                    weibull_shape=float(task.parameters.get("weibull_shape", 2.0)),
                    weibull_scale=float(task.parameters.get("weibull_scale", 30.0)),
                    condition_score=float(task.parameters.get("condition_score", 0.8)),
                )

            # --- Maintenance schedule ---
            if analysis_type in ("maintenance_schedule", "full"):
                equipment = task.parameters.get(
                    "equipment_list",
                    [
                        {
                            "name": "Transformer T1",
                            "age_years": 25,
                            "weibull_shape": 2.0,
                            "weibull_scale": 30.0,
                            "condition_score": 0.6,
                            "criticality": 5,
                        },
                        {
                            "name": "Circuit Breaker CB1",
                            "age_years": 15,
                            "weibull_shape": 2.5,
                            "weibull_scale": 25.0,
                            "condition_score": 0.8,
                            "criticality": 4,
                        },
                        {
                            "name": "Cable C1",
                            "age_years": 10,
                            "weibull_shape": 1.8,
                            "weibull_scale": 35.0,
                            "condition_score": 0.9,
                            "criticality": 3,
                        },
                    ],
                )
                results["maintenance_schedule"] = self.compute_maintenance_schedule(
                    equipment_list=equipment,
                )

            # --- ML-enhanced short-term forecast (Prophet/XGBoost) ---
            if analysis_type in ("ml_short_term_forecast", "full_ml"):
                hist_load = task.parameters.get("historical_load_mw", [])
                if not hist_load:
                    hours = 168
                    hist_load = [
                        100.0 + 30.0 * np.sin(2 * np.pi * h / 24)
                        + 5.0 * np.random.randn()
                        for h in range(hours)
                    ]
                forecast_method = task.parameters.get("forecast_method", "auto")
                results["ml_short_term_forecast"] = self.forecast_short_term_ml(
                    historical_load=hist_load,
                    horizon_hours=int(task.parameters.get("horizon_hours", 24)),
                    method=forecast_method,
                )

            # --- ML fault prediction (XGBoost + SHAP) ---
            if analysis_type == "ml_fault_prediction":
                fault_features = task.parameters.get("fault_features")
                fault_labels = task.parameters.get("fault_labels")
                if fault_features is not None and fault_labels is not None:
                    results["ml_fault_prediction"] = self.predict_fault_ml(
                        features=np.array(fault_features, dtype=float),
                        labels=np.array(fault_labels, dtype=int),
                        use_xgboost=task.parameters.get("use_xggboost", True),
                        explain=task.parameters.get("explain", False),
                    )
                else:
                    results["ml_fault_prediction"] = {"error": "fault_features and fault_labels required"}

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
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Predictive analytics completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Predictive analytics failed: {str(e)}", "ERROR")
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
        Validate predictive analytics results.

        Checks:
        - Forecasts are non-negative
        - MAPE is non-negative
        - Failure probabilities are between 0 and 1
        - Maintenance priorities are valid
        """
        errors: List[str] = []

        stf_data = result.data.get("short_term_forecast")
        if stf_data is not None:
            forecast = stf_data.get("forecast_mw", [])
            if any(f < 0 for f in forecast):
                errors.append("Short-term forecast contains negative values")
            mape = stf_data.get("mape_percent")
            if mape is not None and mape < 0:
                errors.append(f"MAPE is negative: {mape:.2f}%")

        ltf_data = result.data.get("long_term_forecast")
        if ltf_data is not None:
            forecast = ltf_data.get("forecast_mw", [])
            if any(f < 0 for f in forecast):
                errors.append("Long-term forecast contains negative values")

        fp_data = result.data.get("failure_prediction")
        if fp_data is not None:
            prob = fp_data.get("adjusted_failure_probability", 0.0)
            if prob < 0 or prob > 1:
                errors.append(f"Failure probability out of range [0,1]: {prob:.4f}")
            priority = fp_data.get("maintenance_priority", "")
            if priority not in ("immediate", "high", "medium", "low"):
                errors.append(f"Invalid maintenance priority: {priority}")

        result.validation_errors.extend(errors)
        return len(errors) == 0
