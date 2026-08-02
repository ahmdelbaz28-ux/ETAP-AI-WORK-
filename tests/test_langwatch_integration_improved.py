"""
Unit tests for the hardened LangWatch integration.

Tests cover:
- Lazy client init (no env vars at import time)
- Retry with exponential backoff on transient failures
- Non-retryable errors fail fast
- Metrics counters (success/failure/retry)
- PII truncation (LANGWATCH_MAX_CAPTURE_CHARS)
- Explicit disable via LANGWATCH_ENABLED=false
- sync_wrapper captures output (original bug)
- Exception recording on traces
- health_check() includes metrics
"""

from __future__ import annotations

import asyncio
import importlib
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_langwatch_module(monkeypatch: pytest.MonkeyPatch):
    """Import a fresh copy of langwatch_integration with given env vars.

    This is necessary because the module creates a singleton at import
    time, and we need to test different configurations.
    """
    # Clear all LANGWATCH_* env vars to start clean
    for key in list(os.environ.keys()):
        if key.startswith("LANGWATCH_"):
            monkeypatch.delenv(key, raising=False)

    import integrations.langwatch_integration as lw_module

    importlib.reload(lw_module)
    yield lw_module
    # Cleanup
    importlib.reload(lw_module)


# ─── Tests: configuration ───────────────────────────────────────────────────


class TestLangWatchConfiguration:
    """Test that the tracker reads env vars correctly."""

    def test_disabled_when_no_api_key(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("LANGWATCH_API_KEY", raising=False)
        importlib.reload(fresh_langwatch_module)
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.enabled is False
        assert tracker.api_key == ""

    def test_enabled_when_api_key_present(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Skip if SDK not installed — we just test the config logic
        if not fresh_langwatch_module.LANGWATCH_AVAILABLE:
            pytest.skip("LangWatch SDK not installed")
        monkeypatch.setenv("LANGWATCH_API_KEY", "sk-lw-test-key-1234567890")
        importlib.reload(fresh_langwatch_module)
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.enabled is True
        assert tracker.api_key == "sk-lw-test-key-1234567890"

    def test_explicit_disable(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        if not fresh_langwatch_module.LANGWATCH_AVAILABLE:
            pytest.skip("LangWatch SDK not installed")
        monkeypatch.setenv("LANGWATCH_API_KEY", "sk-lw-test-key-1234567890")
        monkeypatch.setenv("LANGWATCH_ENABLED", "false")
        importlib.reload(fresh_langwatch_module)
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.enabled is False

    def test_custom_endpoint(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("LANGWATCH_ENDPOINT", "https://custom.example.com")
        importlib.reload(fresh_langwatch_module)
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.endpoint == "https://custom.example.com"

    def test_timeout_parses_float_string(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # This was a bug in early versions: int("5.0") raises ValueError
        monkeypatch.setenv("LANGWATCH_TIMEOUT", "5.0")
        importlib.reload(fresh_langwatch_module)
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.timeout == 5

    def test_max_capture_chars_default(
        self,
        fresh_langwatch_module: Any,
    ) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        assert tracker.max_capture_chars == 4096


# ─── Tests: PII truncation ──────────────────────────────────────────────────


class TestPIITruncation:
    """Test that the _truncate_for_capture helper works correctly."""

    def test_returns_none_for_none_input(self, fresh_langwatch_module: Any) -> None:
        result = fresh_langwatch_module._truncate_for_capture(None, max_chars=100)
        assert result is None

    def test_returns_none_when_capture_disabled(self, fresh_langwatch_module: Any) -> None:
        result = fresh_langwatch_module._truncate_for_capture("hello", max_chars=0)
        assert result is None

    def test_truncates_long_text(self, fresh_langwatch_module: Any) -> None:
        long_text = "x" * 5000
        result = fresh_langwatch_module._truncate_for_capture(long_text, max_chars=100)
        assert result is not None
        assert len(result) < 200  # 100 chars + truncation suffix
        assert "truncated" in result

    def test_preserves_short_text(self, fresh_langwatch_module: Any) -> None:
        short_text = "hello world"
        result = fresh_langwatch_module._truncate_for_capture(short_text, max_chars=100)
        assert result == "hello world"


# ─── Tests: retry classification ────────────────────────────────────────────


class TestRetryClassification:
    """Test the _is_retryable_exception classifier."""

    def test_connection_error_is_retryable(self, fresh_langwatch_module: Any) -> None:
        assert fresh_langwatch_module._is_retryable_exception(ConnectionError("refused"))

    def test_timeout_error_is_retryable(self, fresh_langwatch_module: Any) -> None:
        assert fresh_langwatch_module._is_retryable_exception(TimeoutError("timed out"))

    def test_oserror_is_retryable(self, fresh_langwatch_module: Any) -> None:
        assert fresh_langwatch_module._is_retryable_exception(OSError("network down"))

    def test_value_error_is_not_retryable(self, fresh_langwatch_module: Any) -> None:
        assert not fresh_langwatch_module._is_retryable_exception(ValueError("bad input"))

    def test_type_error_is_not_retryable(self, fresh_langwatch_module: Any) -> None:
        assert not fresh_langwatch_module._is_retryable_exception(TypeError("wrong type"))

    def test_5xx_http_error_is_retryable(self, fresh_langwatch_module: Any) -> None:
        exc = Exception("server error")
        # Simulate httpx.HTTPStatusError shape
        mock_response = MagicMock()
        mock_response.status_code = 503
        exc.response = mock_response  # type: ignore[attr-defined]
        assert fresh_langwatch_module._is_retryable_exception(exc)

    def test_4xx_http_error_is_not_retryable(self, fresh_langwatch_module: Any) -> None:
        exc = Exception("not found")
        mock_response = MagicMock()
        mock_response.status_code = 404
        exc.response = mock_response  # type: ignore[attr-defined]
        assert not fresh_langwatch_module._is_retryable_exception(exc)


# ─── Tests: metrics ─────────────────────────────────────────────────────────


class TestMetrics:
    """Test that metrics counters work correctly."""

    def test_initial_metrics_are_zero(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        metrics = tracker._get_metrics()
        assert metrics["total_calls"] == 0
        assert metrics["success_calls"] == 0
        assert metrics["failure_calls"] == 0
        assert metrics["retry_attempts"] == 0
        assert metrics["avg_latency_ms"] == 0.0

    def test_record_success_increments_counters(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker._record_call(success=True, latency_ms=10.5)
        tracker._record_call(success=True, latency_ms=20.5)
        metrics = tracker._get_metrics()
        assert metrics["total_calls"] == 2
        assert metrics["success_calls"] == 2
        assert metrics["failure_calls"] == 0
        assert metrics["avg_latency_ms"] == 15.5

    def test_record_failure_increments_counters(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker._record_call(success=False, latency_ms=5.0, retries=2)
        metrics = tracker._get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["success_calls"] == 0
        assert metrics["failure_calls"] == 1
        assert metrics["retry_attempts"] == 2


# ─── Tests: retry wrapper ───────────────────────────────────────────────────


class TestRetryWrapper:
    """Test the _call_with_retry wrapper."""

    def test_succeeds_on_first_attempt(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        call_count = [0]

        def op() -> str:
            call_count[0] += 1
            return "ok"

        result = tracker._call_with_retry(op, op_name="test")
        assert result == "ok"
        assert call_count[0] == 1

    def test_retries_on_connection_error(self, fresh_langwatch_module: Any) -> None:
        # Disable sleep to keep test fast
        fresh_langwatch_module.time.sleep = lambda _: None  # type: ignore[attr-defined]
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.max_retries = 3
        call_count = [0]

        def op() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = tracker._call_with_retry(op, op_name="test")
        assert result == "recovered"
        assert call_count[0] == 3

    def test_fails_fast_on_value_error(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.max_retries = 5
        call_count = [0]

        def op() -> str:
            call_count[0] += 1
            raise ValueError("non-retryable")

        result = tracker._call_with_retry(op, op_name="test")
        assert result is None
        assert call_count[0] == 1  # no retries

    def test_returns_none_after_max_retries(self, fresh_langwatch_module: Any) -> None:
        fresh_langwatch_module.time.sleep = lambda _: None  # type: ignore[attr-defined]
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.max_retries = 2
        call_count = [0]

        def op() -> str:
            call_count[0] += 1
            raise ConnectionError("persistent")

        result = tracker._call_with_retry(op, op_name="test")
        assert result is None
        assert call_count[0] == 3  # initial + 2 retries


# ─── Tests: health_check ────────────────────────────────────────────────────


class TestHealthCheck:
    """Test that health_check returns the expected shape."""

    def test_health_check_includes_metrics(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker._record_call(success=True, latency_ms=10.0)
        tracker._record_call(success=False, latency_ms=20.0)
        health = tracker.health_check()
        assert "metrics" in health
        assert health["metrics"]["total_calls"] == 2
        assert health["metrics"]["success_calls"] == 1
        assert health["metrics"]["failure_calls"] == 1

    def test_health_check_includes_provider_name(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        health = tracker.health_check()
        assert health["provider"] == "LangWatch"

    def test_health_check_includes_endpoint(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        health = tracker.health_check()
        assert "endpoint" in health
        assert isinstance(health["endpoint"], str)


# ─── Tests: sync_wrapper output capture (regression test) ──────────────────


class TestSyncWrapperFix:
    """Regression test: the original sync_wrapper did not capture output.

    The fix ensures both async and sync wrappers consistently capture
    input/output (subject to truncation).
    """

    def test_sync_wrapper_captures_output_when_enabled(
        self,
        fresh_langwatch_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Force-enable the tracker by mocking _get_client to return True
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.enabled = True
        tracker.max_capture_chars = 4096

        # Mock _get_client to bypass SDK requirement
        tracker._get_client = lambda: True  # type: ignore

        # Mock the context manager
        captured: dict[str, Any] = {}
        mock_trace = MagicMock()
        mock_trace.update = lambda **kw: captured.update(kw)
        mock_trace.__enter__ = lambda self: self  # type: ignore
        mock_trace.__exit__ = lambda *a: False  # type: ignore
        tracker.get_context_manager = lambda name, metadata=None, **kw: mock_trace  # type: ignore

        @fresh_langwatch_module.track_llm_call(name="test_op")
        def my_func(prompt: str) -> str:
            return "result: " + prompt

        result = my_func("hello")
        assert result == "result: hello"
        # Verify output was captured (the bug: original sync_wrapper did NOT do this)
        assert "output" in captured
        assert "result: hello" in captured["output"]

    def test_sync_wrapper_captures_input(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.enabled = True
        tracker.max_capture_chars = 4096
        tracker._get_client = lambda: True  # type: ignore

        captured: dict[str, Any] = {}
        mock_trace = MagicMock()
        mock_trace.update = lambda **kw: captured.update(kw)
        mock_trace.__enter__ = lambda self: self  # type: ignore
        mock_trace.__exit__ = lambda *a: False  # type: ignore
        tracker.get_context_manager = lambda name, metadata=None, **kw: mock_trace  # type: ignore

        @fresh_langwatch_module.track_llm_call(name="test_op")
        def my_func(prompt: str) -> str:
            return "result"

        my_func("hello input")
        assert "input" in captured
        assert "hello input" in captured["input"]


# ─── Tests: exception recording ─────────────────────────────────────────────


class TestExceptionRecording:
    """Test that exceptions are recorded on the trace and re-raised."""

    def test_exception_recorded_and_reraised(self, fresh_langwatch_module: Any) -> None:
        tracker = fresh_langwatch_module.LangWatchTracker()
        tracker.enabled = True
        tracker.max_capture_chars = 4096
        tracker._get_client = lambda: True  # type: ignore

        recorded_exc: list[Any] = []
        mock_trace = MagicMock()
        mock_trace.record_exception = lambda exc: recorded_exc.append(exc)
        mock_trace.__enter__ = lambda self: self  # type: ignore
        mock_trace.__exit__ = lambda *a: False  # type: ignore
        tracker.get_context_manager = lambda name, metadata=None, **kw: mock_trace  # type: ignore

        @fresh_langwatch_module.track_llm_call(name="failing_op")
        def my_func(prompt: str) -> str:
            raise RuntimeError("intentional failure")

        with pytest.raises(RuntimeError, match="intentional failure"):
            my_func("input")

        # Verify exception was recorded on the trace
        assert len(recorded_exc) == 1
        assert isinstance(recorded_exc[0], RuntimeError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
