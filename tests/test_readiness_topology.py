"""
tests/test_readiness_topology.py — Tests for /readyz topology-aware readiness semantics.

Validates:
- ENVIRONMENT=production + single_replica (or unset) + REDIS_URL unset -> 200 OK
  with checks["redis"] == "not_configured_single_replica"
- ENVIRONMENT=production + cluster + REDIS_URL unset -> 503 Service Unavailable
  with checks["redis"] == "not_configured" (fail-closed multi-replica guard)
- ENVIRONMENT=production + unreachable REDIS_URL -> 503 Service Unavailable
  (fail-closed when configured but unreachable)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.health import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_db_and_schema():
    """Ensure database and schema checks report healthy so readiness isolates Redis."""
    with patch(
        "api.health._check_db_health",
        return_value=AsyncMock(return_value={"status": "healthy", "backend": "sqlite"}),
    ), patch(
        "api.database_migrations.get_head_revision",
        return_value="012_test_head",
    ):
        yield


def test_readyz_production_single_replica_redis_unconfigured(monkeypatch):
    """Production single_replica without Redis must pass (200 OK) with single_replica tag."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEPLOYMENT_TOPOLOGY", "single_replica")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with patch("api.health._get_redis_client_func", return_value=lambda: None):
        response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["checks"]["redis"] == "not_configured_single_replica"


def test_readyz_production_default_topology_redis_unconfigured(monkeypatch):
    """Production with unset DEPLOYMENT_TOPOLOGY defaults to single replica and passes."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEPLOYMENT_TOPOLOGY", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with patch("api.health._get_redis_client_func", return_value=lambda: None):
        response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["checks"]["redis"] == "not_configured_single_replica"


def test_readyz_production_cluster_topology_redis_unconfigured(monkeypatch):
    """Production cluster/multi_replica without Redis must fail closed (503)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEPLOYMENT_TOPOLOGY", "cluster")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with patch("api.health._get_redis_client_func", return_value=lambda: None):
        response = client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert data["checks"]["redis"] == "not_configured"


def test_readyz_production_unreachable_redis_fails_closed(monkeypatch):
    """When Redis is configured but unreachable, readiness fails closed (503) even in single replica."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEPLOYMENT_TOPOLOGY", "single_replica")
    monkeypatch.setenv("REDIS_URL", "redis://nonexistent-host:6379/0")

    mock_client = AsyncMock()
    mock_client.ping.side_effect = ConnectionRefusedError("Connection refused")

    with patch("api.health._get_redis_client_func", return_value=lambda: mock_client):
        response = client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert str(data["checks"]["redis"]).startswith("fail: ConnectionRefusedError")
