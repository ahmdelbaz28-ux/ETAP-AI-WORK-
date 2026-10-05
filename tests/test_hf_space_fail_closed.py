"""
tests/test_hf_space_fail_closed.py — Tests for Fail-Closed authentication and database guards in HF Space.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Load hf-space/app.py dynamically due to hyphen in folder name
_app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
_spec = importlib.util.spec_from_file_location("hf_space_app", str(_app_path))
_mod = importlib.util.module_from_spec(_spec)
assert _spec
assert _spec.loader
_spec.loader.exec_module(_mod)

_startup_auth_fail_closed_check = _mod._startup_auth_fail_closed_check


@pytest.mark.asyncio
async def test_hf_space_fail_closed_production_raises_when_missing_key():
    """In production mode without an API key, startup check must raise RuntimeError."""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ENGINEERING_SERVICE_API_KEY": "",
            "HF_API_KEY": "",
            "JWT_SECRET_KEY": "valid-secret",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
        },
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="Fail-Closed Security Guard"):
            await _startup_auth_fail_closed_check()


@pytest.mark.asyncio
async def test_hf_space_fail_closed_production_sqlite_fails_immediately():
    """In production mode with SQLite and without ALLOW_SQLITE_IN_PROD, startup must fail immediately."""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ENGINEERING_SERVICE_API_KEY": "secret_key_123",
            "JWT_SECRET_KEY": "secret_jwt_456",
            "DATABASE_URL": "sqlite:///tmp/test.db",
            "ALLOW_SQLITE_IN_PROD": "false",
        },
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="SQLite is forbidden in production"):
            await _startup_auth_fail_closed_check()


@pytest.mark.asyncio
async def test_hf_space_production_logs_critical_warning_when_redis_missing(caplog):
    """In production mode without REDIS_URL, startup must log a critical warning."""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ENGINEERING_SERVICE_API_KEY": "secret_key_123",
            "JWT_SECRET_KEY": "secret_jwt_456",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            "REDIS_URL": "",
        },
        clear=True,
    ):
        with caplog.at_level(logging.CRITICAL):
            await _startup_auth_fail_closed_check()
        assert any("PRODUCTION DEPLOYMENT WITHOUT REDIS" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_hf_space_dev_mode_without_key_succeeds():
    """In development mode without an API key, startup check allows execution."""
    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "development", "ENGINEERING_SERVICE_API_KEY": "", "HF_API_KEY": ""},
        clear=True,
    ):
        # Should not raise
        await _startup_auth_fail_closed_check()
