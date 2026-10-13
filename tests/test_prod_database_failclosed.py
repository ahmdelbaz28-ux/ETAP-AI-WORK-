"""
tests/test_prod_database_failclosed.py — Tests for production database fail-closed enforcement.

Validates that:
- ENVIRONMENT=production + no DATABASE_URL -> raises RuntimeError
- ENVIRONMENT=production + SQLite DATABASE_URL without ALLOW_SQLITE_IN_PROD -> raises RuntimeError
- ENVIRONMENT=production + SQLite DATABASE_URL with ALLOW_SQLITE_IN_PROD=true -> passes (operational escape hatch)
- ENVIRONMENT=production + PostgreSQL DATABASE_URL -> passes
- ENVIRONMENT=development + SQLite DATABASE_URL -> passes without raising (dev compatibility)
"""

from __future__ import annotations

import pytest

from api.config_prod import validate_production_config


def test_production_no_database_url_raises(monkeypatch):
    """Production without DATABASE_URL must fail closed and raise RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_config(require_auth_keys=False)

    assert "DATABASE_URL" in str(exc_info.value)
    assert "Persistent PostgreSQL required" in str(exc_info.value)


def test_production_sqlite_without_escape_hatch_raises(monkeypatch):
    """Production with SQLite and without ALLOW_SQLITE_IN_PROD must raise RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./x.db")
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_config(require_auth_keys=False)

    assert "DATABASE_URL" in str(exc_info.value)
    assert "SQLite is forbidden in production" in str(exc_info.value)


def test_production_sqlite_with_allow_sqlite_in_prod_passes(monkeypatch):
    """Production with SQLite and ALLOW_SQLITE_IN_PROD=true passes (explicit escape hatch)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./x.db")
    monkeypatch.setenv("ALLOW_SQLITE_IN_PROD", "true")

    result = validate_production_config(require_auth_keys=False)
    assert result == []


def test_production_postgresql_passes(monkeypatch):
    """Production with persistent PostgreSQL passes validation."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://etap:secret@db.internal:5432/etap_platform",
    )
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    result = validate_production_config(require_auth_keys=False)
    assert result == []


def test_development_sqlite_passes(monkeypatch):
    """Development environment with SQLite passes without error."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/dev.db")
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    result = validate_production_config(require_auth_keys=False)
    assert result == []


def test_hf_space_default_environment_unset_fails_closed(monkeypatch):
    """When ENVIRONMENT and ENV are unset, HF space path (default_environment='production') fails closed."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/dev.db")
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_config(require_auth_keys=True, default_environment="production")

    assert "DATABASE_URL" in str(exc_info.value)
    assert "Persistent PostgreSQL required" in str(exc_info.value)


def test_core_bootstrap_default_environment_unset_stays_development(monkeypatch):
    """When ENVIRONMENT and ENV are unset, canonical core/bootstrap (default_environment='development') stays dev."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/dev.db")
    monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)

    # Core bootstrap uses default (default_environment="development")
    result = validate_production_config(require_auth_keys=False)
    assert result == []

