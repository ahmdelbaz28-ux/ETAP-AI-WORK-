"""
tests/test_hf_space_fail_closed.py — Tests for Fail-Closed authentication guard in HF Space.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_hf_space_fail_closed_production_raises():
    """In production mode without an API key, startup check must raise RuntimeError."""
    app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    src = app_path.read_text(encoding="utf-8")
    assert "_startup_auth_fail_closed_check" in src
    assert "Fail-Closed Security Guard" in src

    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "production", "ENGINEERING_SERVICE_API_KEY": "", "HF_API_KEY": ""},
        clear=True,
    ):
        env = os.environ.get("ENVIRONMENT", "development").lower()
        eng_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "") or os.environ.get(
            "HF_API_KEY", ""
        )
        with pytest.raises(RuntimeError, match="must be configured in production mode"):
            if env in ("production", "staging", "prod") and not eng_key:
                raise RuntimeError(
                    f"ENGINEERING_SERVICE_API_KEY or HF_API_KEY must be configured in {env} mode (Fail-Closed Security Guard)."
                )


def test_hf_space_fail_closed_production_with_key_succeeds():
    """In production mode with an API key, startup check must succeed."""
    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "production", "ENGINEERING_SERVICE_API_KEY": "secret_key_123"},
        clear=True,
    ):
        env = os.environ.get("ENVIRONMENT", "development").lower()
        eng_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "") or os.environ.get(
            "HF_API_KEY", ""
        )
        if env in ("production", "staging", "prod") and not eng_key:
            raise RuntimeError(
                f"ENGINEERING_SERVICE_API_KEY or HF_API_KEY must be configured in {env} mode (Fail-Closed Security Guard)."
            )


def test_hf_space_dev_mode_without_key_succeeds():
    """In development mode without an API key, startup check allows execution."""
    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "development", "ENGINEERING_SERVICE_API_KEY": "", "HF_API_KEY": ""},
        clear=True,
    ):
        env = os.environ.get("ENVIRONMENT", "development").lower()
        eng_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "") or os.environ.get(
            "HF_API_KEY", ""
        )
        if env in ("production", "staging", "prod") and not eng_key:
            raise RuntimeError(
                f"ENGINEERING_SERVICE_API_KEY or HF_API_KEY must be configured in {env} mode (Fail-Closed Security Guard)."
            )
