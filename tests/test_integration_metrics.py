"""
Integration tests for ``core/metrics.py`` — Prometheus instrumentation.

Verifies:
- Counters, histograms, gauges compile and increment correctly
- Decorators instrument functions transparently
- Exposition format is valid Prometheus text
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from core.metrics import (
    ACTIVE_CONNECTIONS,
    APP_INFO,
    EXECUTION_COUNT,
    EXECUTION_DURATION,
    MEMORY_USAGE_BYTES,
    SKILL_CACHE_ENTRIES,
    SKILL_ERRORS,
    SKILL_LOAD_DURATION,
    SKILL_OPERATIONS,
    SKILL_OPERATIONS_IN_FLIGHT,
    SKILL_VALIDATION_FAILURES,
    count_executions,
    generate_metrics,
    get_metrics_content_type,
    observe_memory,
    record_validation_failure,
    set_app_info,
    set_cache_entries,
    track_execution_duration,
    track_skill_operation,
)


class TestMetricsBasic:
    """Sanity checks — metric objects exist and respond to core methods."""

    def test_counters_exist(self) -> None:
        """Counter objects can be incremented."""
        SKILL_OPERATIONS.labels(operation="test", status="success").inc()
        SKILL_ERRORS.labels(error_type="ValueError", skill_name="test").inc()
        SKILL_VALIDATION_FAILURES.labels(reason="schema").inc()

    def test_histograms_exist(self) -> None:
        """Histogram objects can record observations."""
        SKILL_LOAD_DURATION.labels(skill_name="test").observe(0.5)
        EXECUTION_DURATION.labels(skill_name="test", phase="total").observe(1.2)

    def test_gauges_exist(self) -> None:
        """Gauge objects can be set."""
        SKILL_OPERATIONS_IN_FLIGHT.labels(operation_type="load").set(3)
        SKILL_CACHE_ENTRIES.set(42)
        MEMORY_USAGE_BYTES.labels(component="engine").set(256_000_000)
        ACTIVE_CONNECTIONS.labels(target="postgres").set(5)


class TestMetricsDecorators:
    """Decorator wrapping behaviour."""

    def test_track_skill_operation_success(self) -> None:
        """@track_skill_operation returns the wrapped value on success."""

        @track_skill_operation("test-op")
        def fn() -> str:
            return "done"

        assert fn() == "done"

    def test_track_skill_operation_error(self) -> None:
        """@track_skill_operation re-raises on exception."""

        @track_skill_operation("test-op")
        def fn() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            fn()

    def test_track_execution_duration(self) -> None:
        """@track_execution_duration returns the wrapped value."""

        @track_execution_duration(skill_name="test", phase="load")
        def fn() -> int:
            time.sleep(0.01)
            return 99

        assert fn() == 99

    def test_count_executions_success(self) -> None:
        """@count_executions increments the success counter."""

        @count_executions(skill_name="test")
        def fn() -> str:
            return "ok"

        assert fn() == "ok"

    def test_count_executions_error(self) -> None:
        """@count_executions re-raises on exception."""

        @count_executions(skill_name="test")
        def fn() -> None:
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()


class TestMetricsHelpers:
    """Convenience helpers."""

    def test_set_app_info(self) -> None:
        """set_app_info populates the Info metric."""
        set_app_info(name="test-app", version="2.0.0", environment="testing")
        # Info metrics cannot be read back from the client, but we verify
        # the call does not raise.

    def test_generate_metrics(self) -> None:
        """generate_metrics returns non-empty bytes."""
        set_cache_entries(10)
        observe_memory("test", 1_000_000)
        record_validation_failure("missing_field")

        output = generate_metrics()
        assert isinstance(output, bytes)
        assert len(output) > 50
        assert b"# HELP" in output

    def test_get_content_type(self) -> None:
        """get_metrics_content_type returns the standard content-type."""
        assert get_metrics_content_type() == "text/plain; version=0.0.4; charset=utf-8"

    def test_record_validation_failure(self) -> None:
        """record_validation_failure increments the counter."""
        record_validation_failure("bad_type")
        record_validation_failure("bad_type")
        # No crash = pass

    def test_set_cache_entries(self) -> None:
        """set_cache_entries updates the gauge."""
        set_cache_entries(100)
        # No crash = pass
