"""tests/test_predictive_hardening.py — Tests for B4, B5, B6 ML forecasting hardening."""

from __future__ import annotations

import numpy as np
import pytest

from agents.orchestrator import EngineeringTask
from agents.predictive_agent import PredictiveAgent
from ml.predictive import LoadForecaster


def test_load_forecaster_window_size_validation():
    with pytest.raises(ValueError, match="window_size must be positive"):
        LoadForecaster(window_size=0)

    with pytest.raises(ValueError, match="window_size must be positive"):
        LoadForecaster(window_size=-10)

    lf = LoadForecaster(window_size=12)
    assert lf._window_size == 12
    assert lf.forecast_status() == "untrained"


def test_load_forecaster_status_transitions():
    lf = LoadForecaster(method="linear", window_size=4)
    assert lf.is_trained is False
    assert lf.forecast_status() == "untrained"

    data = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])
    lf.train(data)
    assert lf.is_trained is True
    assert lf.forecast_status() == "trained"

    preds = lf.predict(horizon_hours=3)
    assert len(preds) == 3


@pytest.mark.asyncio
async def test_predictive_agent_untrained_without_historical_data():
    agent = PredictiveAgent()
    task = EngineeringTask(
        task_id="pred-1",
        description="Forecast load",
        study_types=[],
        parameters={"analysis_type": "short_term_forecast"},
    )

    result = await agent.execute(task)
    assert result.status.value == "completed"
    st_result = result.data.get("short_term_forecast", {})
    assert st_result.get("status") == "untrained"
    assert st_result.get("forecast_mw") == []
    assert "Real historical SCADA data required" in st_result.get("error", "")


@pytest.mark.asyncio
async def test_predictive_agent_allows_explicit_synthetic_demo():
    agent = PredictiveAgent()
    task = EngineeringTask(
        task_id="pred-2",
        description="Forecast load demo",
        study_types=[],
        parameters={"analysis_type": "short_term_forecast", "allow_synthetic": True},
    )

    result = await agent.execute(task)
    st_result = result.data.get("short_term_forecast", {})
    assert st_result.get("status") == "synthetic_demo"
    assert len(st_result.get("forecast_mw", [])) > 0


@pytest.mark.asyncio
async def test_predictive_agent_trained_with_data():
    agent = PredictiveAgent()
    sample_load = [100.0 + 10.0 * (i % 24) for i in range(168)]
    task = EngineeringTask(
        task_id="pred-3",
        description="Forecast load real",
        study_types=[],
        parameters={"analysis_type": "short_term_forecast", "historical_load_mw": sample_load},
    )

    result = await agent.execute(task)
    st_result = result.data.get("short_term_forecast", {})
    assert st_result.get("status") == "trained"
    assert len(st_result.get("forecast_mw", [])) == 24


def test_load_forecaster_window_mismatch_and_history():
    """Verify w != window_size behavior and actual historical slice usage."""
    # window_size is 10, but sample is 8 (< 2 * 10 = 20)
    # Expected: shrinks w to max(1, 8 // 2) = 4
    lf = LoadForecaster(method="linear", window_size=10)
    history = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0])
    lf.train(history)

    assert lf._window_size == 10
    assert lf._trained_window_size == 4
    assert lf._trained_window_size != lf._window_size

    # Verify predictions run with the shrunk window
    preds = lf.predict(horizon_hours=2)
    assert len(preds) == 2
    assert lf.is_synthetic is False

    # Verify evaluate also uses _trained_window_size
    metrics = lf.evaluate(history)
    assert "mae" in metrics
    assert "rmse" in metrics


def test_load_forecaster_is_synthetic_flag():
    """Verify is_synthetic becomes True if historical data is missing or truncated."""
    lf = LoadForecaster(method="linear", window_size=4)
    history = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    lf.train(history)
    assert lf.is_synthetic is False

    # Force empty training data to simulate missing history during prediction
    lf._training_data = None
    lf.predict(horizon_hours=2)
    assert lf.is_synthetic is True

