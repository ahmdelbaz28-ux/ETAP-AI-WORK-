"""
Tests for ML predictive analytics — LoadForecaster, FaultPredictor, AnomalyDetector.
"""

import numpy as np
import pytest

from ml.predictive import _HAS_SKLEARN, AnomalyDetector, FaultPredictor, LoadForecaster

# Skip FaultPredictor tests if sklearn is not available
_skip_no_sklearn = pytest.mark.skipif(
    not _HAS_SKLEARN,
    reason="scikit-learn not installed — required for FaultPredictor",
)


# ===========================================================================
# LoadForecaster
# ===========================================================================


class TestLoadForecaster:
    def test_train_linear_fallback(self):
        """Train with linear fallback (no LSTM/Prophet installed)."""
        forecaster = LoadForecaster(method="linear")
        # Need at least 2 * window_size (48) data points
        data = np.arange(60, dtype=float)
        result = forecaster.train(data)
        assert result["method"] == "linear_regression"
        assert result["samples"] == len(data)

    def test_predict_linear(self):
        forecaster = LoadForecaster(method="linear")
        data = np.arange(50, dtype=float)
        forecaster.train(data)
        forecast = forecaster.predict(horizon_hours=5)
        assert len(forecast) == 5
        assert np.all(forecast >= 0)

    def test_predict_positive(self):
        forecaster = LoadForecaster(method="linear")
        data = np.arange(50, dtype=float)
        forecaster.train(data)
        forecast = forecaster.predict(horizon_hours=3)
        assert np.all(forecast >= 0)

    def test_predict_short_horizon(self):
        forecaster = LoadForecaster(method="linear")
        data = np.arange(50, dtype=float)
        forecaster.train(data)
        forecast = forecaster.predict(horizon_hours=1)
        assert len(forecast) == 1

    def test_predict_raises_before_train(self):
        forecaster = LoadForecaster()
        with pytest.raises(RuntimeError, match="trained"):
            forecaster.predict(horizon_hours=5)

    def test_train_raises_insufficient_data(self):
        forecaster = LoadForecaster()
        data = np.array([1.0, 2.0])
        with pytest.raises(ValueError, match="at least"):
            forecaster.train(data)

    def test_train_raises_non_1d(self):
        forecaster = LoadForecaster()
        data = np.array([[1.0, 2.0], [3.0, 4.0]])
        with pytest.raises(ValueError):
            forecaster.train(data)

    def test_evaluate(self):
        forecaster = LoadForecaster(method="linear")
        train_data = np.arange(60, dtype=float)
        forecaster.train(train_data)
        # evaluate needs at least window_size + 1 = 25 points
        test_data = np.arange(55, 85, dtype=float)  # 30 points
        metrics = forecaster.evaluate(test_data)
        assert "mae" in metrics
        assert "rmse" in metrics
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0


# ===========================================================================
# FaultPredictor
# ===========================================================================


@_skip_no_sklearn
class TestFaultPredictor:
    def test_predict_after_train(self):
        predictor = FaultPredictor()
        features = np.random.randn(50, 4)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        labels = np.random.randint(0, 4, size=50)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        predictor.train(features, labels)
        result = predictor.predict(np.array([[0.5, 0.1, 1.0, 0.2]]))
        assert "fault_type" in result
        assert "fault_label" in result
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 1
        assert result["fault_type"] in [0, 1, 2, 3]

    def test_train_raises_bad_shape(self):
        predictor = FaultPredictor()
        with pytest.raises(ValueError):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            predictor.train(np.array([1, 2, 3]), np.array([0, 1, 0]))

    def test_predict_raises_before_train(self):
        predictor = FaultPredictor()
        with pytest.raises(RuntimeError, match="trained"):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            predictor.predict(np.array([[0.5, 0.1]]))

    def test_feature_importance_after_train(self):
        predictor = FaultPredictor()
        features = np.random.randn(50, 4)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        labels = np.random.randint(0, 4, size=50)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        predictor.train(features, labels)
        importance = predictor.feature_importance()
        assert len(importance) > 0
        for v in importance.values():
            assert v >= 0

    def test_explain_no_shap(self):
        """SHAP may not be installed, so explain should handle gracefully."""
        predictor = FaultPredictor()
        features = np.random.randn(50, 4)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        labels = np.random.randint(0, 4, size=50)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        predictor.train(features, labels)
        explanation = predictor.explain(np.array([[0.5, 0.1, 1.0, 0.2]]))
        # Should either have shap_values or error message
        assert "shap_values" in explanation or "error" in explanation


# ===========================================================================
# AnomalyDetector
# ===========================================================================


@_skip_no_sklearn
class TestAnomalyDetector:
    def test_train_and_detect(self):
        detector = AnomalyDetector(contamination=0.1)
        normal_data = np.random.randn(100, 3)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        detector.train(normal_data)
        result = detector.detect(np.random.randn(10, 3))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        assert "anomalies" in result
        assert "scores" in result
        assert "threshold" in result
        assert "n_anomalies" in result
        assert len(result["anomalies"]) == 10
        assert len(result["scores"]) == 10
        assert result["threshold"] > -np.inf

    def test_detect_obvious_anomaly(self):
        detector = AnomalyDetector(contamination=0.3)
        normal = np.array(
            [
                [1.0, 1.0],
                [1.1, 1.0],
                [0.9, 1.0],
                [1.0, 1.1],
                [1.05, 0.95],
                [0.95, 1.05],
                [1.02, 0.98],
                [0.98, 1.02],
                [1.1, 1.1],
                [0.9, 0.9],
                [1.0, 0.9],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 1.0],
            ]
        )
        detector.train(normal)
        test_data = np.array([[1.0, 1.0], [100.0, 100.0]])
        result = detector.detect(test_data)
        # The extreme value should be detected as anomaly
        assert result["n_anomalies"] >= 1

    def test_detect_single_sample(self):
        detector = AnomalyDetector(contamination=0.1)
        normal_data = np.random.randn(50, 3)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        detector.train(normal_data)
        result = detector.detect(np.array([[0.5, 0.1, 0.2]]))
        assert len(result["anomalies"]) == 1

    def test_detect_1d_input(self):
        detector = AnomalyDetector(contamination=0.1)
        normal_data = np.random.randn(50, 3)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        detector.train(normal_data)
        # 1-D input should be reshaped
        result = detector.detect(np.array([0.5, 0.1, 0.2]))
        assert len(result["anomalies"]) == 1

    def test_get_threshold(self):
        detector = AnomalyDetector(contamination=0.1)
        normal_data = np.random.randn(50, 3)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        detector.train(normal_data)
        thresh = detector.get_threshold()
        assert isinstance(thresh, float)

    def test_get_threshold_raises_before_train(self):
        detector = AnomalyDetector()
        with pytest.raises(RuntimeError, match="trained"):
            detector.get_threshold()

    def test_detect_raises_before_train(self):
        detector = AnomalyDetector()
        with pytest.raises(RuntimeError, match="trained"):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            detector.detect(np.array([[1.0, 2.0]]))

    def test_train_raises_non_2d(self):
        detector = AnomalyDetector()
        with pytest.raises(ValueError, match="2-D"):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            detector.train(np.array([1.0, 2.0, 3.0]))

    def test_invalid_contamination(self):
        with pytest.raises(ValueError):
            AnomalyDetector(contamination=0)
        with pytest.raises(ValueError):
            AnomalyDetector(contamination=1.0)
