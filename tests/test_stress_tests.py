"""Tests for gis_validation/stress_tests.py.

Tests incremental_validate, stress_transform_and_validate, and
run_large_scale_simulation functions with mocked dependencies.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gis_validation.stress_tests import (
    StressResult,
    incremental_validate,
    run_large_scale_simulation,
    stress_transform_and_validate,
)

# =========================================================================
# StressResult dataclass
# =========================================================================


class TestStressResult:
    def test_default_construction(self):
        result = StressResult(scenario_id="test123", status="PASS", metrics={"elapsed": 1.0})
        assert result.scenario_id == "test123"
        assert result.status == "PASS"
        assert result.metrics == {"elapsed": 1.0}
        assert result.failure_classification is None

    def test_failure_classification(self):
        result = StressResult(
            scenario_id="f1",
            status="FAIL",
            metrics={},
            failure_classification={"error": "Something broke", "type": "ValueError"},
        )
        assert result.status == "FAIL"
        assert result.failure_classification["error"] == "Something broke"


# =========================================================================
# incremental_validate
# =========================================================================


class TestIncrementalValidate:
    def test_validates_all_items(self):
        calls: list[int] = []

        def validate_fn(item: int) -> None:
            calls.append(item)

        items = [1, 2, 3]
        incremental_validate(items, validate_fn=validate_fn)
        assert calls == [1, 2, 3]

    def test_max_items_stops_early(self):
        calls: list[int] = []

        def validate_fn(item: int) -> None:
            calls.append(item)

        items = [1, 2, 3, 4, 5]
        incremental_validate(items, validate_fn=validate_fn, max_items=3)
        assert calls == [1, 2, 3]

    def test_empty_items(self):
        calls: list[int] = []

        def validate_fn(item: int) -> None:
            calls.append(item)

        incremental_validate([], validate_fn=validate_fn)
        assert calls == []

    def test_max_items_zero_stops_after_first(self):
        """Implementation processes at least 1 item before checking the limit."""
        calls: list[int] = []

        def validate_fn(item: int) -> None:
            calls.append(item)

        incremental_validate([1, 2, 3], validate_fn=validate_fn, max_items=0)
        # The check is 'count >= max_items', so count=1 >= 0 → stop after first
        assert calls == [1]


# =========================================================================
# stress_transform_and_validate
# =========================================================================


class TestStressTransformAndValidate:
    def test_success_path(self):
        """When validation passes, status should be PASS with metrics."""

        def asset_gen() -> list[Any]:
            return [{"id": 1}, {"id": 2}]

        def validate_fn(assets: list[Any]) -> None:
            pass  # No-op validation

        result = stress_transform_and_validate(
            scenario_id="happy_path",
            asset_generator=asset_gen,
            validate_assets_fn=validate_fn,
            max_seconds=5.0,
        )
        assert result.status == "PASS"
        assert result.scenario_id == "happy_path"
        assert "elapsed_seconds" in result.metrics
        assert "asset_count" in result.metrics
        assert result.metrics["asset_count"] == 2
        assert result.failure_classification is None

    def test_max_items_truncates(self):
        def asset_gen() -> list[Any]:
            return [{"n": i} for i in range(100)]

        def validate_fn(assets: list[Any]) -> None:
            pass

        result = stress_transform_and_validate(
            scenario_id="truncated",
            asset_generator=asset_gen,
            validate_assets_fn=validate_fn,
            max_items=5,
        )
        assert result.status == "PASS"
        assert result.metrics["asset_count"] == 5

    def test_failure_path(self):
        """When validation raises, status should be FAIL with error info."""

        def asset_gen() -> list[Any]:
            return [{"bad": "data"}]

        def validate_fn(assets: list[Any]) -> None:
            raise ValueError("Invalid asset data")

        result = stress_transform_and_validate(
            scenario_id="fail_path",
            asset_generator=asset_gen,
            validate_assets_fn=validate_fn,
            max_seconds=5.0,
        )
        assert result.status == "FAIL"
        assert result.failure_classification is not None
        assert "Invalid asset data" in result.failure_classification["error"]
        assert result.failure_classification["type"] == "ValueError"

    def test_asset_generator_exception(self):
        """When the generator raises, should catch and return FAIL."""

        def asset_gen() -> list[Any]:
            raise RuntimeError("Generator crashed")

        def validate_fn(assets: list[Any]) -> None:
            pass

        result = stress_transform_and_validate(
            scenario_id="gen_fail",
            asset_generator=asset_gen,
            validate_assets_fn=validate_fn,
        )
        assert result.status == "FAIL"
        assert "Generator crashed" in result.failure_classification["error"]

    @patch("gis_validation.stress_tests.generate_synthetic_grid")
    @patch("gis_validation.stress_tests.ADMSAsset")
    def test_run_large_scale_simulation(
        self,
        mock_adms_asset: MagicMock,
        mock_generate: MagicMock,
    ):
        """run_large_scale_simulation should produce a StressResult with PASS/FAIL."""
        mock_generate.return_value = [MagicMock() for _ in range(3)]
        # Set attributes needed by validate_fn
        for item in mock_generate.return_value:
            item.asset_id = "asset-001"
            item.geometry = {"type": "Point", "coordinates": [0, 0]}

        result = run_large_scale_simulation(scenario_id="integration_test")
        assert isinstance(result, StressResult)
        assert result.scenario_id == "integration_test"
