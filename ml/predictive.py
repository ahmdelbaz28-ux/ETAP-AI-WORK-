"""
Predictive Analytics Module for AhmedETAP Engineering Platform
============================================================

Provides ML-based predictive capabilities for power systems:

- LoadForecaster: LSTM-based (or linear regression fallback) load forecasting
- FaultPredictor: Random Forest fault type classification
- AnomalyDetector: Isolation Forest anomaly detection for SCADA data

All models gracefully handle missing optional dependencies (tensorflow, sklearn)
and provide informative errors when unavailable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_HAS_SKLEARN = False
_HAS_TENSORFLOW = False

try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: F401
    from sklearn.preprocessing import MinMaxScaler

    _HAS_SKLEARN = True
except ImportError:
    logger.info("scikit-learn not available — FaultPredictor and AnomalyDetector will be limited")

try:
    from tensorflow import keras  # type: ignore

    _HAS_TENSORFLOW = True
except ImportError:
    logger.info(
        "TensorFlow/Keras not available — LoadForecaster will use linear regression fallback"
    )


# ---------------------------------------------------------------------------
# LoadForecaster
# ---------------------------------------------------------------------------


class LoadForecaster:
    """LSTM-based load forecasting model.

    Uses a Keras LSTM when TensorFlow is available; otherwise falls back to
    a simple autoregressive linear regression approach.
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.scaler: Optional[Any] = None
        self._is_lstm: bool = False
        self._window_size: int = 24
        self._fallback_weights: Optional[np.ndarray] = None
        self._fallback_bias: float = 0.0
        self._fallback_mean: float = 0.0
        self._fallback_std: float = 1.0

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, historical_data: np.ndarray, epochs: int = 50) -> Dict[str, Any]:
        """Train the forecasting model on historical load data.

        Parameters
        ----------
        historical_data : np.ndarray
            1-D array of historical load values (e.g., hourly MW readings).
        epochs : int
            Number of training epochs (only used for LSTM).

        Returns
        -------
        dict
            Training summary with ``method``, ``epochs``, and ``samples`` keys.
        """
        if historical_data.ndim != 1:
            raise ValueError("historical_data must be a 1-D array")

        if len(historical_data) < self._window_size * 2:
            raise ValueError(
                f"Need at least {self._window_size * 2} data points, got {len(historical_data)}"
            )

        if _HAS_TENSORFLOW:
            return self._train_lstm(historical_data, epochs)
        else:
            return self._train_linear(historical_data)

    def _train_lstm(self, data: np.ndarray, epochs: int) -> Dict[str, Any]:
        """Train an LSTM model using Keras."""
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = self.scaler.fit_transform(data.reshape(-1, 1)).flatten()

        X, y = self._create_sequences(scaled)

        model = keras.Sequential(
            [
                keras.layers.LSTM(64, input_shape=(self._window_size, 1), return_sequences=True),
                keras.layers.Dropout(0.2),
                keras.layers.LSTM(32),
                keras.layers.Dropout(0.2),
                keras.layers.Dense(1),
            ]
        )
        model.compile(optimizer="adam", loss="mse")
        model.fit(X, y, epochs=epochs, batch_size=32, verbose=0)

        self.model = model
        self._is_lstm = True
        return {"method": "lstm", "epochs": epochs, "samples": len(data)}

    def _train_linear(self, data: np.ndarray) -> Dict[str, Any]:
        """Fallback: train an autoregressive linear model (least-squares)."""
        self._fallback_mean = float(np.mean(data))
        self._fallback_std = float(np.std(data)) if np.std(data) > 0 else 1.0
        normalized = (data - self._fallback_mean) / self._fallback_std

        X, y = self._create_sequences(normalized)
        # Flatten X from (samples, window, 1) to (samples, window)
        X_flat = X.reshape(X.shape[0], X.shape[1])

        # Least-squares: w = (X^T X)^-1 X^T y
        XtX = X_flat.T @ X_flat
        Xty = X_flat.T @ y
        try:
            self._fallback_weights = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            self._fallback_weights = np.linalg.lstsq(X_flat, y, rcond=None)[0]
        self._fallback_bias = 0.0  # data is already centered
        self._is_lstm = False

        return {"method": "linear_regression", "epochs": 0, "samples": len(data)}

    def _create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sliding-window sequences for supervised learning."""
        X: List[np.ndarray] = []
        y: List[float] = []
        for i in range(len(data) - self._window_size):
            X.append(data[i : i + self._window_size])
            y.append(data[i + self._window_size])
        X_arr = np.array(X)
        y_arr = np.array(y)
        if self._is_lstm or _HAS_TENSORFLOW:
            X_arr = X_arr.reshape(X_arr.shape[0], X_arr.shape[1], 1)
        return X_arr, y_arr

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, horizon_hours: int = 24) -> np.ndarray:
        """Predict load for the next *horizon_hours* hours.

        Parameters
        ----------
        horizon_hours : int
            Number of hours to forecast ahead.

        Returns
        -------
        np.ndarray
            1-D array of forecasted load values.
        """
        if self.model is None and self._fallback_weights is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        if self._is_lstm and self.model is not None:
            return self._predict_lstm(horizon_hours)
        else:
            return self._predict_linear(horizon_hours)

    def _predict_lstm(self, horizon_hours: int) -> np.ndarray:
        """Autoregressive LSTM prediction."""
        # Use last window from scaler data
        scaled_recent = self.scaler.data_min_ + (
            self.scaler.data_max_ - self.scaler.data_min_
        ) * np.random.rand(self._window_size)  # placeholder for real recent data
        # In production, the caller should provide recent data
        input_seq = scaled_recent.reshape(1, self._window_size, 1)
        predictions: List[float] = []
        for _ in range(horizon_hours):
            pred = float(self.model.predict(input_seq, verbose=0)[0, 0])
            predictions.append(pred)
            input_seq = np.roll(input_seq, -1, axis=1)
            input_seq[0, -1, 0] = pred

        result = self.scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()
        return result

    def _predict_linear(self, horizon_hours: int) -> np.ndarray:
        """Autoregressive linear regression prediction."""
        # Start with zeros (normalized); in production, use real recent data
        window = np.zeros(self._window_size)
        predictions: List[float] = []
        for _ in range(horizon_hours):
            next_val = float(window @ self._fallback_weights + self._fallback_bias)
            predictions.append(next_val)
            window = np.roll(window, -1)
            window[-1] = next_val

        # Denormalize
        result = np.array(predictions) * self._fallback_std + self._fallback_mean
        return result

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, test_data: np.ndarray) -> Dict[str, float]:
        """Evaluate model accuracy on test data.

        Parameters
        ----------
        test_data : np.ndarray
            1-D array of actual load values to compare against.

        Returns
        -------
        dict
            Dictionary with ``mae``, ``rmse``, and ``mape`` metrics.
        """
        if len(test_data) < self._window_size + 1:
            raise ValueError(
                f"Need at least {self._window_size + 1} test data points"
            )

        # Generate one-step-ahead predictions for the test window
        actuals: List[float] = []
        preds: List[float] = []

        for i in range(self._window_size, len(test_data)):
            actuals.append(float(test_data[i]))
            # Use the preceding window to predict the next value
            window_data = test_data[i - self._window_size : i]
            if self._is_lstm and self.model is not None and self.scaler is not None:
                scaled_win = self.scaler.transform(window_data.reshape(-1, 1)).flatten()
                inp = scaled_win.reshape(1, self._window_size, 1)
                pred_scaled = float(self.model.predict(inp, verbose=0)[0, 0])
                pred = float(self.scaler.inverse_transform([[pred_scaled]])[0, 0])
            elif self._fallback_weights is not None:
                norm_win = (window_data - self._fallback_mean) / self._fallback_std
                pred_norm = float(norm_win @ self._fallback_weights + self._fallback_bias)
                pred = pred_norm * self._fallback_std + self._fallback_mean
            else:
                raise RuntimeError("Model has not been trained yet")
            preds.append(pred)

        actuals_arr = np.array(actuals)
        preds_arr = np.array(preds)

        mae = float(np.mean(np.abs(actuals_arr - preds_arr)))
        rmse = float(np.sqrt(np.mean((actuals_arr - preds_arr) ** 2)))
        # MAPE — avoid division by zero
        nonzero_mask = actuals_arr != 0
        if np.any(nonzero_mask):
            mape = float(np.mean(np.abs((actuals_arr[nonzero_mask] - preds_arr[nonzero_mask]) / actuals_arr[nonzero_mask])) * 100)
        else:
            mape = float("inf")

        return {"mae": mae, "rmse": rmse, "mape": mape}


# ---------------------------------------------------------------------------
# FaultPredictor
# ---------------------------------------------------------------------------


class FaultPredictor:
    """Random Forest fault prediction model.

    Classifies fault types from electrical measurements:
    - 0: No fault
    - 1: Short circuit
    - 2: Ground fault
    - 3: Open circuit
    """

    FAULT_LABELS: Dict[int, str] = {
        0: "none",
        1: "short_circuit",
        2: "ground_fault",
        3: "open_circuit",
    }

    FEATURE_NAMES: List[str] = [
        "voltage",
        "current",
        "temperature",
        "frequency",
        "load",
    ]

    def __init__(self) -> None:
        self.model: Any = None
        self._is_trained: bool = False

    def train(self, features: np.ndarray, labels: np.ndarray) -> Dict[str, Any]:
        """Train Random Forest on fault features.

        Parameters
        ----------
        features : np.ndarray
            2-D array of shape ``(n_samples, n_features)``.
            Expected features: voltage, current, temperature, frequency, load.
        labels : np.ndarray
            1-D array of fault type labels (0–3).

        Returns
        -------
        dict
            Training summary with ``n_samples``, ``n_features``, and ``n_classes``.
        """
        if not _HAS_SKLEARN:
            raise RuntimeError(
                "scikit-learn is required for FaultPredictor. "
                "Install it with: pip install scikit-learn"
            )

        if features.ndim != 2:
            raise ValueError("features must be a 2-D array (n_samples, n_features)")
        if labels.ndim != 1:
            raise ValueError("labels must be a 1-D array")
        if features.shape[0] != labels.shape[0]:
            raise ValueError("Number of feature rows must match number of labels")

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(features, labels)
        self._is_trained = True

        return {
            "n_samples": int(features.shape[0]),
            "n_features": int(features.shape[1]),
            "n_classes": len(np.unique(labels)),
        }

    def predict(self, features: np.ndarray) -> Dict[str, Any]:
        """Predict fault probability and type.

        Parameters
        ----------
        features : np.ndarray
            2-D array of shape ``(n_samples, n_features)`` or 1-D for a single sample.

        Returns
        -------
        dict
            Dictionary with ``fault_type``, ``fault_label``, ``probabilities``,
            and ``confidence`` keys.
        """
        if not self._is_trained or self.model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        # Allow single-sample 1-D input
        if features.ndim == 1:
            features = features.reshape(1, -1)

        predictions = self.model.predict(features)
        probabilities = self.model.predict_proba(features)

        results: Dict[str, Any] = {
            "fault_type": int(predictions[0]),
            "fault_label": self.FAULT_LABELS.get(int(predictions[0]), "unknown"),
            "probabilities": {
                self.FAULT_LABELS.get(i, f"class_{i}"): float(probabilities[0][i])
                for i in range(probabilities.shape[1])
            },
            "confidence": float(np.max(probabilities[0])),
        }
        return results

    def feature_importance(self) -> Dict[str, float]:
        """Return feature importance scores.

        Returns
        -------
        dict
            Mapping of feature name to importance score.
        """
        if not self._is_trained or self.model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        importances = self.model.feature_importances_
        n_features = min(len(self.FEATURE_NAMES), len(importances))
        result: Dict[str, float] = {}
        for i in range(n_features):
            result[self.FEATURE_NAMES[i]] = float(importances[i])
        # Include any extra features beyond the named ones
        for i in range(n_features, len(importances)):
            result[f"feature_{i}"] = float(importances[i])
        return result


# ---------------------------------------------------------------------------
# AnomalyDetector
# ---------------------------------------------------------------------------


class AnomalyDetector:
    """Isolation Forest anomaly detection for SCADA data.

    Detects anomalous behaviour in real-time power system telemetry by
    learning the distribution of normal operating data.
    """

    def __init__(self, contamination: float = 0.01) -> None:
        """Initialise the detector.

        Parameters
        ----------
        contamination : float
            Expected proportion of anomalies in the data (0, 0.5].
        """
        if not 0 < contamination <= 0.5:
            raise ValueError("contamination must be in (0, 0.5]")
        self.model: Any = None
        self.contamination = contamination
        self._threshold: Optional[float] = None
        self._is_trained: bool = False

    def train(self, normal_data: np.ndarray) -> Dict[str, Any]:
        """Train on normal operating data.

        Parameters
        ----------
        normal_data : np.ndarray
            2-D array of shape ``(n_samples, n_features)`` representing
            normal operating conditions.

        Returns
        -------
        dict
            Training summary with ``n_samples``, ``n_features``, and
            ``contamination`` keys.
        """
        if not _HAS_SKLEARN:
            raise RuntimeError(
                "scikit-learn is required for AnomalyDetector. "
                "Install it with: pip install scikit-learn"
            )

        if normal_data.ndim != 2:
            raise ValueError("normal_data must be a 2-D array (n_samples, n_features)")

        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(normal_data)
        self._is_trained = True

        # Compute anomaly score threshold from training data
        scores = self.model.decision_function(normal_data)
        self._threshold = float(np.percentile(scores, self.contamination * 100))

        return {
            "n_samples": int(normal_data.shape[0]),
            "n_features": int(normal_data.shape[1]),
            "contamination": self.contamination,
        }

    def detect(self, data: np.ndarray) -> Dict[str, Any]:
        """Detect anomalies in real-time data.

        Parameters
        ----------
        data : np.ndarray
            2-D array of shape ``(n_samples, n_features)`` or 1-D for a
            single sample.

        Returns
        -------
        dict
            Dictionary with:
            - ``anomalies``: list of booleans (True = anomaly)
            - ``scores``: list of anomaly scores (lower = more anomalous)
            - ``threshold``: the score threshold
            - ``n_anomalies``: count of detected anomalies
        """
        if not self._is_trained or self.model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        # Allow single-sample 1-D input
        if data.ndim == 1:
            data = data.reshape(1, -1)

        predictions = self.model.predict(data)  # 1 = normal, -1 = anomaly
        scores = self.model.decision_function(data)

        anomalies = [int(p) == -1 for p in predictions]
        scores_list = [float(s) for s in scores]

        return {
            "anomalies": anomalies,
            "scores": scores_list,
            "threshold": self._threshold if self._threshold is not None else 0.0,
            "n_anomalies": sum(anomalies),
        }

    def get_threshold(self) -> float:
        """Get the anomaly score threshold.

        Returns
        -------
        float
            The score below which a sample is considered anomalous.
        """
        if self._threshold is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")
        return self._threshold
