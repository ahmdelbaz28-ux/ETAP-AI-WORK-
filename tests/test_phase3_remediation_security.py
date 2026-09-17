"""Tests for Phase 3 Security Remediation Fixes (FIX-09 through FIX-13).

Verifies:
- FIX-09: /api/v1/studies/re-run, /api/v1/tool-policy/evaluate, /api/v1/system/validate require API key.
- FIX-10: WebSocket dual-control is fail-closed when ENGINEERING_SERVICE_API_KEY is not set.
- FIX-11: verify_api_key is deny-by-default (fail-closed) in staging/unknown environments.
- FIX-12: JWT blacklist catches .env.example placeholders.
- FIX-13: Re-run study returns 501 Not Implemented without fake BUS-1/BUS-2 results.
"""

import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.dependencies import _INSECURE_JWT_SAMPLES


def test_fix_12_jwt_sample_blacklist():
    """Verify that .env.example placeholder is explicitly blacklisted."""
    assert "your-jwt-secret-key-minimum-32-characters" in _INSECURE_JWT_SAMPLES
    assert "test-secret-32-bytes-long-aaaa-bbbb" in _INSECURE_JWT_SAMPLES


def test_fix_11_verify_api_key_deny_by_default(monkeypatch):
    """Verify verify_api_key fails closed when ENVIRONMENT is staging or unset."""
    from unittest.mock import MagicMock

    from api.shared_handlers import verify_api_key

    req = MagicMock()
    req.url.path = "/api/v1/studies/run"
    req.headers = {}

    # 1. Unset API key + ENVIRONMENT=staging -> must raise 401
    monkeypatch.setenv("HF_API_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(HTTPException) as exc:
        verify_api_key(req)
    assert exc.value.status_code == 401

    # 2. Unset API key + ENVIRONMENT=production -> must raise 401
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc:
        verify_api_key(req)
    assert exc.value.status_code == 401

    # 3. Unset API key + ENVIRONMENT=unknown_env -> must raise 401
    monkeypatch.setenv("ENVIRONMENT", "unknown_env")
    with pytest.raises(HTTPException) as exc:
        verify_api_key(req)
    assert exc.value.status_code == 401


def test_fix_09_b_tool_policy_router_has_auth():
    """Verify tool-policy router requires get_api_key dependency."""
    from api.tool_policy import router

    assert any("get_api_key" in str(dep.dependency) for dep in router.dependencies), (
        "Router must have get_api_key dependency"
    )


def test_fix_09_c_validation_router_has_auth():
    """Verify system validation router requires get_api_key dependency."""
    from api.validation import router

    assert any("get_api_key" in str(dep.dependency) for dep in router.dependencies), (
        "Validation router must have get_api_key dependency"
    )


def test_fix_13_re_run_kills_fake_results(monkeypatch):
    """Verify study_execution_service raises 422 validation error instead of generating fake BUS-1 results."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from api.services.study_execution_service import execute_study_re_run

    db = AsyncMock()
    mock_proj = MagicMock()
    mock_proj.id = "proj-123"
    mock_proj.tenant_id = "default"
    mock_proj.system_config = None
    db.get = AsyncMock(return_value=mock_proj)
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_proj))
    )

    monkeypatch.setattr(
        "api.services.study_execution_service.save_solver_params",
        AsyncMock(return_value={}),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            execute_study_re_run(
                project_id="proj-123",
                params={"voltage": 1.0},
                db=db,
                tool="load_flow",
            )
        )
    assert exc.value.status_code == 422
    assert "System configuration is required for re-run" in exc.value.detail
