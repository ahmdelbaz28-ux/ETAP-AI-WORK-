"""
tests/test_fix27_alembic_startup_gate.py — Verification for FIX-27 (Alembic Startup Gate).

Tests:
1. Alembic configuration loading and head revision resolution.
2. Schema health check endpoint and payload structure.
3. Fail-closed behavior on startup migration error in production.
4. Graceful handling of migration warnings in development mode.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from api.database_migrations import (
    check_schema_health,
    get_alembic_config,
    get_head_revision,
    run_alembic_startup_gate,
)
from api.routes import app


def test_alembic_config_and_head_revision() -> None:
    """Verify alembic.ini is parsed and head revision is resolved."""
    cfg = get_alembic_config()
    assert cfg is not None
    assert cfg.config_file_name is not None
    assert "alembic.ini" in cfg.config_file_name

    head_rev = get_head_revision()
    assert head_rev is not None
    # Verify matches latest migration revision ID
    assert head_rev == "011_add_hardening_tables"


@pytest.mark.asyncio
async def test_schema_health_reporting() -> None:
    """Verify check_schema_health returns head revision."""
    health = await check_schema_health()
    assert health["status"] == "synchronized"
    assert health["head_revision"] == "011_add_hardening_tables"


@pytest.mark.asyncio
async def test_alembic_startup_gate_fails_closed_in_production() -> None:
    """In production mode, a migration failure MUST raise RuntimeError (Fail-Closed)."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        with patch(
            "api.database_migrations.run_upgrade_head_sync",
            side_effect=Exception("DB connection dropped"),
        ):
            with pytest.raises(RuntimeError, match="Database migration failed at startup"):
                await run_alembic_startup_gate()


@pytest.mark.asyncio
async def test_alembic_startup_gate_tolerates_warning_in_development() -> None:
    """In development mode, migration failures log a warning without aborting startup."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        with patch(
            "api.database_migrations.run_upgrade_head_sync",
            side_effect=Exception("Dev migration warning"),
        ):
            # Should NOT raise RuntimeError
            await run_alembic_startup_gate()


def test_schema_health_endpoint() -> None:
    """Verify GET /api/v1/health/schema endpoint."""
    client = TestClient(app)
    resp = client.get("/api/v1/health/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert "head_revision" in data
    assert data["head_revision"] == "011_add_hardening_tables"
