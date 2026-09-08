"""tests/test_fail_closed_infra.py — Tests for fail-closed infrastructure startup (A6)."""

from __future__ import annotations

import os

import pytest

from engine.scalability import DistributedTaskQueue
from gis_integration.providers.postgis_provider import PostGISProvider, _get_default_dsn


def test_postgis_provider_prod_fail_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("POSTGIS_DSN", raising=False)

    with pytest.raises(RuntimeError, match="POSTGIS_DSN required in production"):
        _get_default_dsn()

    with pytest.raises(RuntimeError, match="POSTGIS_DSN required in production"):
        PostGISProvider()


def test_postgis_provider_staging_fail_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("POSTGIS_DSN", raising=False)

    with pytest.raises(RuntimeError, match="POSTGIS_DSN required in production"):
        PostGISProvider()


def test_postgis_provider_prod_with_dsn_allowed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGIS_DSN", "postgresql://prod-user:pass@prod-host:5432/etap_gis")

    dsn = _get_default_dsn()
    assert dsn == "postgresql://prod-user:pass@prod-host:5432/etap_gis"

    # Initializing with explicit dsn
    provider = PostGISProvider(dsn="postgresql://prod-user:pass@prod-host:5432/etap_gis")
    assert provider.dsn == "postgresql://prod-user:pass@prod-host:5432/etap_gis"


def test_postgis_provider_dev_fallback_allowed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("POSTGIS_DSN", raising=False)

    dsn = _get_default_dsn()
    assert "localhost" in dsn


def test_rabbitmq_prod_fail_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RABBITMQ_URL", raising=False)

    with pytest.raises(RuntimeError, match="RABBITMQ_URL required in production"):
        DistributedTaskQueue(queue_type="rabbitmq")


def test_redis_prod_fail_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(RuntimeError, match="REDIS_URL required in production"):
        DistributedTaskQueue(queue_type="redis")


def test_memory_queue_always_works_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    queue = DistributedTaskQueue(queue_type="memory")
    assert queue.queue_type == "memory"
