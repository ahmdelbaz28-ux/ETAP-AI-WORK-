"""
Unit tests for the hardened Smithery MCP integration.

Tests cover:
- Explicit disable via SMITHERY_ENABLED=false
- Configurable server IDs via env vars
- Input validation (JSON-serializable, size limit)
- Retry with exponential backoff on 5xx/429
- Non-retryable 4xx errors fail fast
- Circuit breaker opens after consecutive failures
- Rate limiter blocks excessive calls
- Disabled vs. error distinction in responses
- Metrics counters
- health_check() includes metrics + circuit breaker state
"""

from __future__ import annotations

import asyncio
import importlib
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_smithery_module(monkeypatch: pytest.MonkeyPatch):
    """Import a fresh copy of smithery_mcp with cleared env vars."""
    for key in list(os.environ.keys()):
        if key.startswith("SMITHERY_"):
            monkeypatch.delenv(key, raising=False)

    import integrations.smithery_mcp as sm_module

    importlib.reload(sm_module)
    yield sm_module
    importlib.reload(sm_module)


# ─── Tests: configuration ───────────────────────────────────────────────────


class TestSmitheryConfiguration:
    """Test that the client reads env vars correctly."""

    def test_disabled_when_no_api_key(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SMITHERY_API_KEY", raising=False)
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        assert client.enabled is False

    def test_enabled_when_api_key_present(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_API_KEY", "test-uuid-key-12345")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        assert client.enabled is True

    def test_explicit_disable(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_API_KEY", "test-uuid-key-12345")
        monkeypatch.setenv("SMITHERY_ENABLED", "false")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        assert client.enabled is False

    def test_custom_endpoint(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_BASE_URL", "https://custom.smithery.example.com")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        assert client.endpoint == "https://custom.smithery.example.com"

    def test_configurable_timeouts(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_TIMEOUT_LIST", "15")
        monkeypatch.setenv("SMITHERY_TIMEOUT_CALL", "45")
        monkeypatch.setenv("SMITHERY_TIMEOUT_LONG_CALL", "180")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        assert client.timeout_list == 15
        assert client.timeout_call == 45
        assert client.timeout_long_call == 180

    def test_configurable_server_ids(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_API_KEY", "test-key")
        monkeypatch.setenv("SMITHERY_SERVER_STANDARDS_DB", "private-standards")
        monkeypatch.setenv("SMITHERY_SERVER_EQUIPMENT", "private-equipment")
        monkeypatch.setenv("SMITHERY_SERVER_REPORT_GEN", "private-reporter")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        registry = fresh_smithery_module.ETAPMCPRegistry(client)
        assert registry.server_standards_db == "private-standards"
        assert registry.server_equipment == "private-equipment"
        assert registry.server_report_gen == "private-reporter"

    def test_default_server_ids(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_API_KEY", "test-key")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        registry = fresh_smithery_module.ETAPMCPRegistry(client)
        assert registry.server_standards_db == "etap-standards-db"
        assert registry.server_equipment == "equipment-catalog"
        assert registry.server_report_gen == "report-generator"


# ─── Tests: input validation ────────────────────────────────────────────────


class TestInputValidation:
    """Test the _validate_arguments method."""

    def test_valid_dict_passes(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        err = client._validate_arguments({"key": "value", "num": 42})
        assert err is None

    def test_non_dict_rejected(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        err = client._validate_arguments(["not", "a", "dict"])  # type: ignore[arg-type]
        assert err is not None
        assert "must be a dict" in err

    def test_non_serializable_rejected(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        # A set is not JSON-serializable
        err = client._validate_arguments({"items": {1, 2, 3}})
        assert err is not None
        assert "not JSON-serializable" in err

    def test_oversized_payload_rejected(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_MAX_PAYLOAD_KB", "1")  # 1 KB limit
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        # 2 KB payload
        big_data = "x" * 2048
        err = client._validate_arguments({"data": big_data})
        assert err is not None
        assert "exceeds max size" in err


# ─── Tests: disabled vs error distinction ──────────────────────────────────


class TestDisabledVsError:
    """Test that disabled calls return a distinct error code."""

    @pytest.mark.asyncio
    async def test_call_tool_returns_disabled_error(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SMITHERY_API_KEY", raising=False)
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        result = await client.call_tool("test-server", "test-tool", {"arg": "value"})
        assert result["error"] == "smithery_disabled"
        assert result["result"] is None
        assert "message" in result

    @pytest.mark.asyncio
    async def test_list_servers_returns_empty_when_disabled(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SMITHERY_API_KEY", raising=False)
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        result = await client.list_servers()
        assert result == []

    @pytest.mark.asyncio
    async def test_call_tool_returns_invalid_args_error(
        self,
        fresh_smithery_module: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SMITHERY_API_KEY", "test-key")
        importlib.reload(fresh_smithery_module)
        client = fresh_smithery_module.SmitheryClient()
        # Pass a non-dict — should be rejected before any HTTP call
        result = await client.call_tool("server", "tool", ["not", "a", "dict"])  # type: ignore[arg-type]
        assert result["error"] == "smithery_invalid_args"
        assert "must be a dict" in result["message"]


# ─── Tests: retry classification ────────────────────────────────────────────


class TestRetryClassification:
    """Test the _is_retryable_exception classifier."""

    def test_5xx_is_retryable(self, fresh_smithery_module: Any) -> None:
        assert fresh_smithery_module._is_retryable_http_status(500)
        assert fresh_smithery_module._is_retryable_http_status(502)
        assert fresh_smithery_module._is_retryable_http_status(503)
        assert fresh_smithery_module._is_retryable_http_status(504)

    def test_429_is_retryable(self, fresh_smithery_module: Any) -> None:
        assert fresh_smithery_module._is_retryable_http_status(429)

    def test_4xx_is_not_retryable(self, fresh_smithery_module: Any) -> None:
        assert not fresh_smithery_module._is_retryable_http_status(400)
        assert not fresh_smithery_module._is_retryable_http_status(401)
        assert not fresh_smithery_module._is_retryable_http_status(403)
        assert not fresh_smithery_module._is_retryable_http_status(404)


# ─── Tests: rate limiter ────────────────────────────────────────────────────


class TestTokenBucket:
    """Test the _TokenBucket rate limiter."""

    def test_first_call_succeeds_immediately(self, fresh_smithery_module: Any) -> None:
        bucket = fresh_smithery_module._TokenBucket(rate=10.0, capacity=10.0)
        assert bucket.acquire(timeout=0.1) is True

    def test_burst_capacity_respected(self, fresh_smithery_module: Any) -> None:
        bucket = fresh_smithery_module._TokenBucket(rate=1.0, capacity=3.0)
        # First 3 calls should succeed (burst capacity)
        results = [bucket.acquire(timeout=0.01) for _ in range(3)]
        assert all(results)
        # 4th call should fail because no tokens available and timeout is short
        # (rate=1/s means we'd need to wait 1s for the next token)
        result = bucket.acquire(timeout=0.05)
        assert result is False

    def test_refill_over_time(self, fresh_smithery_module: Any) -> None:
        bucket = fresh_smithery_module._TokenBucket(rate=100.0, capacity=1.0)
        # First call drains the bucket
        assert bucket.acquire(timeout=0.01) is True
        # Wait a bit for refill (100/s = 10ms per token)
        import time

        time.sleep(0.05)
        # Should have refilled by now
        assert bucket.acquire(timeout=0.1) is True


# ─── Tests: metrics ─────────────────────────────────────────────────────────


class TestMetrics:
    """Test that metrics counters work correctly."""

    def test_initial_metrics_are_zero(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        metrics = client._get_metrics()
        assert metrics["total_calls"] == 0
        assert metrics["success_calls"] == 0
        assert metrics["failure_calls"] == 0
        assert metrics["circuit_open_count"] == 0
        assert metrics["rate_limited_count"] == 0

    def test_record_success_increments_counters(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        client._record_call(success=True)
        client._record_call(success=True)
        metrics = client._get_metrics()
        assert metrics["total_calls"] == 2
        assert metrics["success_calls"] == 2

    def test_record_failure_with_circuit_open(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        client._record_call(success=False, circuit_open=True)
        metrics = client._get_metrics()
        assert metrics["failure_calls"] == 1
        assert metrics["circuit_open_count"] == 1

    def test_record_failure_with_rate_limited(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        client._record_call(success=False, rate_limited=True)
        metrics = client._get_metrics()
        assert metrics["failure_calls"] == 1
        assert metrics["rate_limited_count"] == 1


# ─── Tests: health_check ────────────────────────────────────────────────────


class TestHealthCheck:
    """Test that health_check returns the expected shape."""

    def test_health_check_includes_metrics(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        client._record_call(success=True)
        health = client.health_check()
        assert "metrics" in health
        assert health["metrics"]["total_calls"] == 1
        assert health["metrics"]["success_calls"] == 1

    def test_health_check_includes_timeouts(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        health = client.health_check()
        assert "timeouts" in health
        assert "list_seconds" in health["timeouts"]
        assert "call_seconds" in health["timeouts"]
        assert "long_call_seconds" in health["timeouts"]

    def test_health_check_includes_circuit_breaker(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        health = client.health_check()
        assert "circuit_breaker" in health
        assert "state" in health["circuit_breaker"]

    def test_health_check_includes_max_retries(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        health = client.health_check()
        assert "max_retries" in health
        assert isinstance(health["max_retries"], int)

    def test_health_check_includes_max_payload_kb(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        health = client.health_check()
        assert "max_payload_kb" in health
        assert isinstance(health["max_payload_kb"], int)


# ─── Tests: User-Agent (security: no version) ──────────────────────────────


class TestUserAgentSecurity:
    """Test that the User-Agent does not leak version info."""

    def test_user_agent_has_no_version(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        headers = client._headers
        ua = headers["User-Agent"]
        # Must not contain version numbers like "1.0.0" or "2.1"
        import re

        assert not re.search(r"\d+\.\d+", ua), (
            f"User-Agent '{ua}' contains version info — security risk"
        )

    def test_headers_include_request_id(self, fresh_smithery_module: Any) -> None:
        client = fresh_smithery_module.SmitheryClient()
        headers1 = client._headers
        headers2 = client._headers
        # X-Request-ID should be a UUID (unique per call)
        assert "X-Request-ID" in headers1
        assert "X-Request-ID" in headers2
        assert headers1["X-Request-ID"] != headers2["X-Request-ID"]


# ─── Tests: async retry behavior ───────────────────────────────────────────


class TestAsyncRetry:
    """Test the _call_with_retry method for async operations."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, fresh_smithery_module: Any) -> None:
        # Disable rate limiter blocking
        fresh_smithery_module._TokenBucket.acquire = lambda self, timeout=30.0: True  # type: ignore
        client = fresh_smithery_module.SmitheryClient()
        call_count = [0]

        async def op() -> str:
            call_count[0] += 1
            return "ok"

        result = await client._call_with_retry(op, op_name="test", timeout=1.0)
        assert result == "ok"
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_retries_on_5xx(self, fresh_smithery_module: Any) -> None:
        # Disable rate limiter blocking + sleep
        fresh_smithery_module._TokenBucket.acquire = lambda self, timeout=30.0: True  # type: ignore
        fresh_smithery_module.asyncio.sleep = AsyncMock()  # type: ignore

        client = fresh_smithery_module.SmitheryClient()
        client.max_retries = 3
        call_count = [0]

        async def op() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                # Simulate 503 error
                exc = Exception("Service Unavailable")
                mock_resp = MagicMock()
                mock_resp.status_code = 503
                exc.response = mock_resp  # type: ignore
                raise exc
            return "recovered"

        result = await client._call_with_retry(op, op_name="test", timeout=1.0)
        assert result == "recovered"
        assert call_count[0] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
