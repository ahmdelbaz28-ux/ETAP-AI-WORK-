"""Tests for the built-in health & status handler.

Covers:
    * HealthHandler returns correct shape for system.health
    * Metrics snapshot via system.metrics
    * CLI auto-registers health handler
    * --no-health flag disables it
    * End-to-end stdio request for system.health
"""
from __future__ import annotations

import io
import json
import time

import pytest
from acp.health import HealthHandler
from acp.observability import InMemoryMetricsRegistry


class TestHealthHandler:
    @pytest.mark.anyio
    async def test_health_shape(self):
        t0 = time.time()
        handler = HealthHandler(transport_name="stdio", start_time=t0)
        result = await handler.health()
        assert result["status"] == "ok"
        assert result["version"] == "0.1.0"
        assert result["transport"] == "stdio"
        assert result["timestamp"] >= round(t0, 3) - 0.001
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0

    @pytest.mark.anyio
    async def test_health_with_runtime(self):
        from acp.runtime import AcpRuntime
        t0 = time.time()
        handler = HealthHandler(transport_name="stdio", start_time=t0)
        runtime = AcpRuntime([handler])
        handler.set_runtime(runtime)
        result = await handler.health()
        assert result["status"] == "ok"
        assert "capabilities_count" in result
        assert result["capabilities_count"] >= 1

    @pytest.mark.anyio
    async def test_health_uptime_increases(self):
        t0 = time.time()
        handler = HealthHandler(transport_name="uds", start_time=t0)
        time.sleep(0.02)
        result = await handler.health()
        assert result["uptime_seconds"] > 0

    @pytest.mark.anyio
    async def test_metrics_without_registry(self):
        handler = HealthHandler()
        result = await handler.metrics()
        assert result == {"metrics": {}}

    @pytest.mark.anyio
    async def test_metrics_with_registry(self):
        metrics = InMemoryMetricsRegistry()
        counter = metrics.get_or_create_counter("test.calls", "Test calls")
        counter.inc(5)
        handler = HealthHandler(metrics=metrics)
        result = await handler.metrics()
        assert "metrics" in result
        snapshot = result["metrics"]
        assert "counters" in snapshot
        # New snapshot format: values is a list of {"labels": {}, "value": N}
        assert snapshot["counters"]["test.calls"]["values"][0]["value"] == 5

    @pytest.mark.anyio
    async def test_ready_without_runtime(self):
        handler = HealthHandler()
        result = await handler.ready()
        assert result["ready"] is False
        assert result["status"] == "runtime not available"
        assert result["handlers_loaded"] == 0
        assert result["capabilities"] == []

    @pytest.mark.anyio
    async def test_ready_with_runtime(self):
        from acp.runtime import AcpRuntime, capability

        class DummyHandler:
            @capability("dummy.test")
            async def test(self) -> str:
                return "ok"

        handler = HealthHandler(transport_name="stdio", user_handler_count=1)
        runtime = AcpRuntime([handler, DummyHandler()])
        handler.set_runtime(runtime)
        result = await handler.ready()
        assert result["ready"] is True
        assert result["status"] == "ok"
        assert result["handlers_loaded"] == 1
        assert "system.health" in result["capabilities"]
        assert "system.ready" in result["capabilities"]
        assert "dummy.test" in result["capabilities"]
        assert "uptime_seconds" in result


class TestHealthCliIntegration:
    def test_health_capability_auto_registered(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        from acp.cli import _build_observability, _build_parser, _build_runtime
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "tests.test_cli"])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
        assert "system.health" in runtime.capability_names
        assert "system.metrics" in runtime.capability_names
        assert "system.ready" in runtime.capability_names

    def test_no_health_flag(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        from acp.cli import _build_observability, _build_parser, _build_runtime
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "tests.test_cli", "--no-health"])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
        assert "system.health" not in runtime.capability_names
        assert "system.metrics" not in runtime.capability_names
        assert "system.ready" not in runtime.capability_names


@pytest.mark.anyio
async def test_stdio_health_request():
    """End-to-end: request system.health over stdio transport."""
    request = json.dumps({
        "jsonrpc": "2.0",
        "id": "h1",
        "method": "system.health",
        "capability": "system.health",
    }) + "\n"
    stdin = io.StringIO(request)
    stdout = io.StringIO()

    from acp.cli import _build_observability, _build_parser, _build_router, _build_runtime
    from acp.transport import StdioTransport

    parser = _build_parser()
    args = parser.parse_args(["stdio", "--handlers", "tests.test_cli"])
    tracer, metrics, logger = _build_observability(args)
    runtime, _ = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
    router = _build_router(args, runtime, tracer, metrics, logger)

    transport = StdioTransport(stdin, stdout)
    raw = await transport.read_message()
    assert raw is not None
    envelope = json.loads(raw)
    resp = await router.handle(envelope)
    assert resp is not None
    assert resp["result"]["status"] == "ok"
    assert resp["result"]["transport"] == "stdio"
    assert "version" in resp["result"]
    assert "uptime_seconds" in resp["result"]


@pytest.mark.anyio
async def test_stdio_metrics_request():
    """End-to-end: request system.metrics over stdio transport with metrics enabled."""
    request = json.dumps({
        "jsonrpc": "2.0",
        "id": "m1",
        "method": "system.metrics",
        "capability": "system.metrics",
    }) + "\n"
    stdin = io.StringIO(request)
    stdout = io.StringIO()

    from acp.cli import _build_observability, _build_parser, _build_router, _build_runtime
    from acp.transport import StdioTransport

    parser = _build_parser()
    args = parser.parse_args(["stdio", "--handlers", "tests.test_cli", "--metrics"])
    tracer, metrics, logger = _build_observability(args)
    runtime, _ = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
    router = _build_router(args, runtime, tracer, metrics, logger)

    transport = StdioTransport(stdin, stdout)
    raw = await transport.read_message()
    assert raw is not None
    envelope = json.loads(raw)
    resp = await router.handle(envelope)
    assert resp is not None
    assert "metrics" in resp["result"]


@pytest.mark.anyio
async def test_stdio_ready_request():
    """End-to-end: request system.ready over stdio transport."""
    request = json.dumps({
        "jsonrpc": "2.0",
        "id": "r1",
        "method": "system.ready",
        "capability": "system.ready",
    }) + "\n"
    stdin = io.StringIO(request)
    stdout = io.StringIO()

    from acp.cli import _build_observability, _build_parser, _build_router, _build_runtime
    from acp.transport import StdioTransport

    parser = _build_parser()
    args = parser.parse_args(["stdio", "--handlers", "tests.test_cli"])
    tracer, metrics, logger = _build_observability(args)
    runtime, _ = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
    router = _build_router(args, runtime, tracer, metrics, logger)

    transport = StdioTransport(stdin, stdout)
    raw = await transport.read_message()
    assert raw is not None
    envelope = json.loads(raw)
    resp = await router.handle(envelope)
    assert resp is not None
    assert resp["result"]["ready"] is True
    assert resp["result"]["status"] == "ok"
    assert resp["result"]["handlers_loaded"] == 1
    assert "capabilities" in resp["result"]
    assert "system.health" in resp["result"]["capabilities"]
    assert "system.ready" in resp["result"]["capabilities"]
