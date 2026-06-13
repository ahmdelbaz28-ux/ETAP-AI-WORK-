"""Tests for the lightweight HTTP health server.

Covers:
    * GET /health returns the system.health JSON
    * GET /ready returns the system.ready JSON
    * GET /metrics returns Prometheus or OpenMetrics text
    * Unknown paths return 404
    * Non-GET methods return 405
    * Port binding and concurrent requests
"""
from __future__ import annotations

import json

import anyio
import pytest
from acp.health import HealthHandler
from acp.http_server import start_http_server

# ------------------------------------------------------------------ helpers

async def _http_get(host: str, port: int, path: str, accept: str | None = None) -> tuple[int, bytes, str]:
    """Make a simple HTTP/1.1 GET request and return (status, body, content_type)."""
    client = await anyio.connect_tcp(host, port)
    try:
        extra_headers = f"Accept: {accept}\r\n" if accept else ""
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"{extra_headers}"
            f"Connection: close\r\n\r\n"
        ).encode()
        await client.send(request)
        response = b""
        while True:
            try:
                chunk = await client.receive(4096)
            except anyio.EndOfStream:
                break
            if not chunk:
                break
            response += chunk
    finally:
        await client.aclose()

    # Parse status line, headers, and body
    header_end = response.find(b"\r\n\r\n")
    if header_end == -1:
        return 0, b"", ""
    headers = response[:header_end].decode("utf-8", errors="replace")
    body = response[header_end + 4 :]
    header_lines = headers.split("\r\n")
    status_line = header_lines[0]
    status_code = int(status_line.split()[1])
    content_type = ""
    for line in header_lines[1:]:
        if line.lower().startswith("content-type:"):
            content_type = line.split(":", 1)[1].strip()
            break
    return status_code, body, content_type


# ------------------------------------------------------------------ tests

@pytest.mark.anyio
async def test_http_health_endpoint():
    handler = HealthHandler(transport_name="test")
    port = 18980
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)  # let server bind
        status, body, ct = await _http_get("127.0.0.1", port, "/health")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "application/json" in ct
    data = json.loads(body)
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["transport"] == "test"


@pytest.mark.anyio
async def test_http_ready_endpoint():
    handler = HealthHandler(transport_name="test", user_handler_count=2)
    port = 18981
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/ready")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "application/json" in ct
    data = json.loads(body)
    assert data["ready"] is False  # runtime not set
    assert data["status"] == "runtime not available"


@pytest.mark.anyio
async def test_http_ready_with_runtime():
    from acp.runtime import AcpRuntime

    handler = HealthHandler(transport_name="test", user_handler_count=1)
    runtime = AcpRuntime([handler])
    handler.set_runtime(runtime)
    port = 18982
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/ready")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "application/json" in ct
    data = json.loads(body)
    assert data["ready"] is True
    assert data["status"] == "ok"
    assert data["handlers_loaded"] == 1
    assert "system.health" in data["capabilities"]
    assert "system.ready" in data["capabilities"]


@pytest.mark.anyio
async def test_http_metrics_endpoint_empty():
    """Without a registry, /metrics returns empty Prometheus text."""
    handler = HealthHandler(transport_name="test")
    port = 18983
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/metrics")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "text/plain" in ct
    assert body == b""


@pytest.mark.anyio
async def test_http_metrics_prometheus_format():
    """With a registry, /metrics returns Prometheus text exposition."""
    from acp.observability import InMemoryMetricsRegistry

    metrics = InMemoryMetricsRegistry()
    counter = metrics.get_or_create_counter("test.calls", "Test counter")
    counter.inc(5)
    gauge = metrics.get_or_create_gauge("test.active", "Active gauge")
    gauge.set(7)
    hist = metrics.get_or_create_histogram("test.latency", "Latency histogram")
    hist.observe(10)
    hist.observe(25)

    handler = HealthHandler(transport_name="test", metrics=metrics)
    port = 18987
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/metrics")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "text/plain" in ct
    text = body.decode()
    assert "# HELP test_calls Test counter" in text
    assert "# TYPE test_calls counter" in text
    assert "test_calls 5" in text
    assert "# HELP test_active Active gauge" in text
    assert "# TYPE test_active gauge" in text
    assert "test_active 7" in text
    assert "# HELP test_latency Latency histogram" in text
    assert "# TYPE test_latency histogram" in text
    # Verify cumulative histogram buckets
    assert "test_latency_bucket" in text
    assert "test_latency_sum" in text
    assert "test_latency_count" in text
    # Cumulative: observe(10) goes to bucket 10, observe(25) goes to bucket 25
    # +Inf should have count == 2
    assert 'test_latency_bucket{le="+Inf"} 2' in text


@pytest.mark.anyio
async def test_http_metrics_custom_path():
    """Custom metrics_path serves metrics on a non-default path."""
    from acp.observability import InMemoryMetricsRegistry

    metrics = InMemoryMetricsRegistry()
    counter = metrics.get_or_create_counter("test.calls", "Test counter")
    counter.inc(3)

    handler = HealthHandler(transport_name="test", metrics=metrics)
    port = 18989
    custom_path = "/custom-metrics"
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port, custom_path)
        await anyio.sleep(0.1)
        # Custom path returns metrics
        status, body, ct = await _http_get("127.0.0.1", port, custom_path)
        assert status == 200
        assert "text/plain" in ct
        assert b"test_calls 3" in body
        # Default /metrics returns 404
        status404, body404, _ = await _http_get("127.0.0.1", port, "/metrics")
        assert status404 == 404
        assert b"Not found" in body404
        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_http_metrics_default_labels():
    """Default labels from the registry are included in Prometheus output."""
    from acp.observability import InMemoryMetricsRegistry

    metrics = InMemoryMetricsRegistry(default_labels={"transport": "stdio"})
    counter = metrics.get_or_create_counter("test.calls", "Test counter")
    counter.inc(5)

    handler = HealthHandler(transport_name="test", metrics=metrics)
    port = 18990
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/metrics")
        tg.cancel_scope.cancel()

    assert status == 200
    assert "text/plain" in ct
    text = body.decode()
    assert 'test_calls{transport="stdio"} 5' in text


@pytest.mark.anyio
async def test_http_metrics_openmetrics_format():
    """With Accept: application/openmetrics-text, /metrics returns OpenMetrics."""
    from acp.observability import InMemoryMetricsRegistry

    metrics = InMemoryMetricsRegistry()
    counter = metrics.get_or_create_counter("test.calls", "Test counter")
    counter.inc(5)
    gauge = metrics.get_or_create_gauge("test.active", "Active gauge")
    gauge.set(7)

    handler = HealthHandler(transport_name="test", metrics=metrics)
    port = 18988
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get(
            "127.0.0.1", port, "/metrics",
            accept="application/openmetrics-text",
        )
        tg.cancel_scope.cancel()

    assert status == 200
    assert "application/openmetrics-text" in ct
    text = body.decode()
    assert "# HELP test_calls Test counter" in text
    assert "# TYPE test_calls counter" in text
    assert "test_calls 5" in text
    assert "# HELP test_active Active gauge" in text
    assert "# TYPE test_active gauge" in text
    assert "test_active 7" in text
    assert "# EOF" in text


@pytest.mark.anyio
async def test_http_404():
    handler = HealthHandler(transport_name="test")
    port = 18984
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)
        status, body, ct = await _http_get("127.0.0.1", port, "/unknown")
        tg.cancel_scope.cancel()

    assert status == 404
    assert "application/json" in ct
    data = json.loads(body)
    assert data["error"] == "Not found"


@pytest.mark.anyio
async def test_http_405():
    handler = HealthHandler(transport_name="test")
    port = 18985
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)

        client = await anyio.connect_tcp("127.0.0.1", port)
        try:
            request = (
                f"POST /health HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode()
            await client.send(request)
            response = b""
            while True:
                try:
                    chunk = await client.receive(4096)
                except anyio.EndOfStream:
                    break
                if not chunk:
                    break
                response += chunk
        finally:
            await client.aclose()

        header_end = response.find(b"\r\n\r\n")
        headers = response[:header_end].decode("utf-8", errors="replace")
        status_line = headers.split("\r\n")[0]
        status = int(status_line.split()[1])
        body = response[header_end + 4 :]
        tg.cancel_scope.cancel()

    assert status == 405
    data = json.loads(body)
    assert data["error"] == "Method not allowed"


@pytest.mark.anyio
async def test_http_concurrent_requests():
    handler = HealthHandler(transport_name="test")
    port = 18986

    async with anyio.create_task_group() as tg:
        tg.start_soon(start_http_server, handler, port)
        await anyio.sleep(0.1)

        results = []

        async def fetch():
            status, body, ct = await _http_get("127.0.0.1", port, "/health")
            results.append((status, body))

        tg.start_soon(fetch)
        tg.start_soon(fetch)
        tg.start_soon(fetch)
        await anyio.sleep(0.2)
        tg.cancel_scope.cancel()

    assert len(results) == 3
    for status, body in results:
        assert status == 200
        data = json.loads(body)
        assert data["status"] == "ok"
