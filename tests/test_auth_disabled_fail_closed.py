"""
Regression tests for C-02: ENGINEERING_SERVICE_AUTH_DISABLED fail-closed.

The bypass may only be honoured in explicit dev/test environments. Any other
value (``qa``, ``live``, typo, or unset ENVIRONMENT) must fail closed — at
startup (non-zero exit) and at request time (denied).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from api.environment import auth_disabled_allowed, is_dev_environment

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("env_value", ["development", "dev", "local", "test", "testing", "ci"])
def test_auth_disabled_allowed_in_dev_allowlist(monkeypatch, env_value: str) -> None:
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", env_value)
    assert auth_disabled_allowed() is True
    assert is_dev_environment() is True


@pytest.mark.parametrize("env_value", ["qa", "live", "preview", "staging-eu", "prod", "production"])
def test_auth_disabled_rejected_outside_dev_allowlist(monkeypatch, env_value: str) -> None:
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", env_value)
    assert auth_disabled_allowed() is False
    assert is_dev_environment() is False


def test_auth_disabled_rejected_when_environment_unset(monkeypatch) -> None:
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    assert auth_disabled_allowed() is False


def test_auth_disabled_var_unset_is_false(monkeypatch) -> None:
    monkeypatch.delenv("ENGINEERING_SERVICE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert auth_disabled_allowed() is False


def test_startup_exits_nonzero_when_auth_disabled_in_qa() -> None:
    """Importing api.routes with AUTH_DISABLED=true ENVIRONMENT=qa must exit(1)."""
    code = (
        "import os\n"
        'os.environ["ENGINEERING_SERVICE_AUTH_DISABLED"] = "true"\n'
        'os.environ["ENVIRONMENT"] = "qa"\n'
        "import api.routes\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode != 0, (
        f"expected non-zero exit, got {result.returncode}: {result.stderr}"
    )
    assert "NOT allowed" in result.stderr


def test_startup_accepts_auth_disabled_in_development() -> None:
    code = (
        "import os\n"
        'os.environ["ENGINEERING_SERVICE_AUTH_DISABLED"] = "true"\n'
        'os.environ["ENVIRONMENT"] = "development"\n'
        "import api.routes\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"expected success in development: {result.stderr}"
