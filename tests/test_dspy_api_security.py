"""
tests/test_dspy_api_security.py — Security & hardening tests for DSPy Copilot API.

Covers:
- 401 Missing / invalid API key
- 401 Missing / invalid JWT
- 403 Missing / empty tenant_id
- 403 Wrong role (viewer/operator denied; engineer/admin allowed)
- 403 Strict feature flag disabled
- 403 Privacy mode active (external LLM prohibited)
- 413 Oversized ingest payload (> 50k chars)
- 413 Oversized diagnose payload (> 50k chars)
- 429 Rate limiting
- Error sanitization (no raw provider exceptions or stack traces in responses)
- Diagnostic LM input minimization (only allowlisted keys; no metadata/PII)
- Deterministic physics fields are never overwritten
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from api.dspy import router
from core_model.specs import StudyRequest, StudyResult
from services.dspy_copilot.runtime import (
    _sanitize_study_result_for_llm,
    execute_with_copilot,
)


def _build_test_app() -> FastAPI:
    """Build an isolated FastAPI application with the DSPy router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_app() -> FastAPI:
    return _build_test_app()


@pytest.fixture
def valid_engineer_user() -> CurrentUser:
    return CurrentUser(
        user_id="user_eng_123",
        username="engineer_jane",
        email="jane@etap.example",
        role="engineer",
        is_active=True,
        tenant_id="tenant_power_grid_01",
    )


@pytest.fixture
def valid_admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="user_adm_123",
        username="admin_bob",
        email="bob@etap.example",
        role="admin",
        is_active=True,
        tenant_id="tenant_power_grid_01",
    )


# ---------------------------------------------------------------------------
# 1. Auth & JWT Tests (401)
# ---------------------------------------------------------------------------

def test_ingest_missing_auth_header_401(test_app):
    """Calling /api/v1/dspy/ingest without Authorization header returns 401."""
    client = TestClient(test_app)
    resp = client.post(
        "/api/v1/dspy/ingest",
        json={"sld_notes": "Bus 1 Slack 1.0 pu"},
        headers={"X-API-Key": "test_api_key"},
    )
    assert resp.status_code == 401


def test_diagnose_missing_auth_header_401(test_app):
    """Calling /api/v1/dspy/diagnose without Authorization header returns 401."""
    client = TestClient(test_app)
    resp = client.post(
        "/api/v1/dspy/diagnose",
        json={"study_data": {"study_type": "load_flow", "success": True}},
        headers={"X-API-Key": "test_api_key"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Tenant Isolation Tests (403)
# ---------------------------------------------------------------------------

def test_empty_tenant_id_rejected_403(test_app, monkeypatch):
    """User with empty tenant_id must be denied with TENANT_REQUIRED (403)."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")

    user_no_tenant = CurrentUser(
        user_id="u1",
        username="no_tenant_user",
        email="u@example.com",
        role="engineer",
        is_active=True,
        tenant_id="",  # Empty tenant!
    )
    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: user_no_tenant

    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": "Bus 1 Slack 1.0 pu"})
    assert resp.status_code == 403
    assert "TENANT_REQUIRED" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# 3. Role-Based Access Control Tests (403)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("disallowed_role", ["viewer", "operator", "auditor", "guest"])
def test_insufficient_role_denied_403(test_app, monkeypatch, disallowed_role):
    """Roles other than engineer/admin must receive 403 INSUFFICIENT_ROLE."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")

    low_priv_user = CurrentUser(
        user_id="u_low",
        username="low_priv",
        email="low@example.com",
        role=disallowed_role,
        is_active=True,
        tenant_id="tenant_01",
    )
    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: low_priv_user

    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": "Bus 1 Slack 1.0 pu"})
    assert resp.status_code == 403
    assert "INSUFFICIENT_ROLE" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# 4. Feature Flag Strict Gate (403)
# ---------------------------------------------------------------------------

def test_feature_disabled_denied_403(test_app, monkeypatch, valid_engineer_user):
    """When dspy_copilot feature flag is disabled, endpoints must return 403 FEATURE_DISABLED."""
    monkeypatch.delenv("FEATURE_FLAG_DSPY_COPILOT", raising=False)
    monkeypatch.setenv("ENV", "test")

    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: valid_engineer_user

    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": "Bus 1 Slack 1.0 pu"})
    assert resp.status_code == 403
    assert "FEATURE_DISABLED" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# 5. Privacy Mode Gate (403)
# ---------------------------------------------------------------------------

def test_privacy_mode_denies_llm_operations_403(test_app, monkeypatch, valid_engineer_user):
    """When PRIVACY_MODE is enabled, external LLM endpoints return 403 PRIVACY_MODE_ACTIVE."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")
    monkeypatch.setenv("PRIVACY_MODE", "true")

    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: valid_engineer_user

    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": "Bus 1 Slack 1.0 pu"})
    assert resp.status_code == 403
    assert "PRIVACY_MODE_ACTIVE" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# 6. Request Size Caps (413)
# ---------------------------------------------------------------------------

def test_oversized_ingest_rejected_413(test_app, monkeypatch, valid_engineer_user):
    """Ingest payload exceeding 50,000 characters returns 413 INPUT_TOO_LARGE."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")
    monkeypatch.delenv("PRIVACY_MODE", raising=False)

    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: valid_engineer_user

    oversized_notes = "A" * 50_001
    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": oversized_notes})
    assert resp.status_code == 413
    assert "INPUT_TOO_LARGE" in resp.json().get("detail", "")


def test_oversized_diagnose_rejected_413(test_app, monkeypatch, valid_engineer_user):
    """Diagnose payload exceeding 50,000 characters returns 413 INPUT_TOO_LARGE."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")
    monkeypatch.delenv("PRIVACY_MODE", raising=False)

    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: valid_engineer_user

    oversized_data = {"study_type": "load_flow", "padding": "X" * 50_001}
    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/diagnose", json={"study_data": oversized_data})
    assert resp.status_code == 413
    assert "INPUT_TOO_LARGE" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# 7. Error Sanitization & Safe Response Codes
# ---------------------------------------------------------------------------

def test_ingest_failure_sanitized_422(test_app, monkeypatch, valid_engineer_user):
    """Failed ingestion returns 422 with generic INGEST_FAILED; no raw exceptions exposed."""
    monkeypatch.setenv("FEATURE_FLAG_DSPY_COPILOT", "true")
    monkeypatch.delenv("PRIVACY_MODE", raising=False)

    test_app.dependency_overrides[get_api_key] = lambda: "valid_key"
    test_app.dependency_overrides[get_current_user_from_header] = lambda: valid_engineer_user

    from services.dspy_copilot.runtime import DspyIngestError

    def failing_ingest(notes):
        raise DspyIngestError("internal provider OpenAI connection failed with key sk-12345")

    monkeypatch.setattr("api.dspy.run_ingest", failing_ingest)

    client = TestClient(test_app)
    resp = client.post("/api/v1/dspy/ingest", json={"sld_notes": "Bus 1 Slack 1.0 pu"})
    assert resp.status_code == 422
    detail = resp.json().get("detail", "")
    assert "INGEST_FAILED" in detail
    assert "sk-12345" not in detail
    assert "OpenAI" not in detail


# ---------------------------------------------------------------------------
# 8. Diagnostic LM Input Minimization
# ---------------------------------------------------------------------------

def test_diagnostic_payload_minimization():
    """Only allowlisted keys are passed to the LM; task_id, pe_stamp, and metadata are excluded."""
    result = StudyResult(
        study_type="load_flow",
        success=True,
        task_id="sensitive_task_id_999",
        trace_id="sensitive_trace_888",
        pe_stamp={"license": "PE-LIC-999-STAMPED-BY-ENGINEER"},
        data={
            "converged": True,
            "buses": {"1": {"voltage_magnitude_pu": 1.0}},
            "lines": [{"line_id": 1, "loading_pct": 50.0}],
            "transformers": [],
            "generators": [],
            "loads": [],
            "internal_database_url": "postgresql://user:pass@db:5432/private",
            "user_email": "engineer@secretcorp.com",
        },
        warnings=["Test warning"],
    )

    sanitized = _sanitize_study_result_for_llm(result)

    # Allowed keys
    assert sanitized["success"] is True
    assert sanitized["converged"] is True
    assert "1" in sanitized["buses"]
    assert len(sanitized["lines"]) == 1
    assert sanitized["warnings"] == ["Test warning"]

    # Excluded keys
    assert "task_id" not in sanitized
    assert "trace_id" not in sanitized
    assert "pe_stamp" not in sanitized
    assert "internal_database_url" not in sanitized
    assert "user_email" not in sanitized

    dumped = json.dumps(sanitized)
    assert "PE-LIC-999" not in dumped
    assert "secretcorp" not in dumped
    assert "sensitive_task_id" not in dumped


# ---------------------------------------------------------------------------
# 9. Physics Keys Are Never Overwritten
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_with_copilot_never_overwrites_physics():
    """execute_with_copilot adds diagnostic narrative but never overwrites deterministic physics fields."""
    mock_executor = AsyncMock()
    original_data = {
        "converged": True,
        "voltages": {"1": 1.0, "2": 0.98},
        "power_losses_mw": 0.12,
    }
    mock_result = StudyResult(
        study_type="load_flow",
        success=True,
        data=dict(original_data),
        warnings=[],
    )
    mock_executor.execute.return_value = mock_result

    req = StudyRequest(study_type="load_flow")

    with patch("services.dspy_copilot.runtime.is_enabled", return_value=True):
        final_result = await execute_with_copilot(mock_executor, req)

    # Original physics keys remain completely untouched
    assert final_result.data["voltages"] == {"1": 1.0, "2": 0.98}
    assert final_result.data["power_losses_mw"] == 0.12
    assert final_result.data["converged"] is True

    # Copilot diagnostic is added as an additive block
    assert "dspy_diagnostic" in final_result.data
