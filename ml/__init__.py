"""
ML / Predictive Analytics Module
=================================

Provides machine-learning models for power systems prediction:

- :class:`LoadForecaster`  – LSTM / linear-regression load forecasting
- :class:`FaultPredictor`  – Random Forest fault classification
- :class:`AnomalyDetector` – Isolation Forest anomaly detection

If ``numpy`` is not installed (e.g. on a minimal deployment), the imports below
will fail. We catch that and re-raise with a clear, actionable error message
instead of a cryptic ``No module named 'ml'``.
"""

try:
    from .predictive import AnomalyDetector, FaultPredictor, LoadForecaster
except ImportError as _exc:
    raise ImportError(
        "ml.predictive could not be imported — most likely numpy or another "
        "core dependency is missing. Install requirements with: "
        "pip install numpy scipy pandas scikit-learn. "
        f"Original error: {_exc}",
    ) from _exc

__all__ = ["LoadForecaster", "FaultPredictor", "AnomalyDetector"]
