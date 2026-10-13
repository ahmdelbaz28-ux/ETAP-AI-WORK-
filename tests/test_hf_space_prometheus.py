"""
tests/test_hf_space_prometheus.py — Test Prometheus metrics endpoint parity on hf-space/app.py.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def hf_client():
    """Load hf-space/app.py and yield a TestClient."""
    os.environ["ENVIRONMENT"] = "development"
    os.environ["ALLOW_SQLITE_IN_PROD"] = "true"
    app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    if not app_path.exists():
        pytest.skip(f"hf-space/app.py not found at {app_path}")

    spec = importlib.util.spec_from_file_location("hf_space_prometheus_app", app_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hf_space_prometheus_app"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        pytest.fail(f"Could not load hf-space/app.py: {exc}")

    client = TestClient(mod.app, raise_server_exceptions=False)
    return client


def test_hf_space_app_imports(hf_client):
    """Verify that hf-space/app.py imports cleanly without raising errors."""
    assert hf_client is not None
    assert hf_client.app is not None



def test_hf_space_prometheus_metrics_get(hf_client):
    """GET /prometheus/metrics returns 200 with Prometheus text exposition."""
    response = hf_client.get("/prometheus/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    # Core metrics must include standard Prometheus elements
    assert "app_info" in content or "skill_operations" in content or "executions_total" in content or "# HELP" in content


def test_hf_space_prometheus_metrics_head(hf_client):
    """HEAD /prometheus/metrics returns 200."""
    response = hf_client.head("/prometheus/metrics")
    assert response.status_code == 200


def test_hf_space_legacy_metrics_unchanged(hf_client):
    """GET /metrics remains unchanged and returns JSON metrics response."""
    response = hf_client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "platform" in data
    assert data["platform"] == "huggingface-spaces"
    assert "uptime_seconds" in data
