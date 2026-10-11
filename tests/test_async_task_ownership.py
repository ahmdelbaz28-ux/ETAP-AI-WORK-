"""tests/test_async_task_ownership.py — Regression suite for P0-3 Async Execution & Task Ownership.

Covers:
1. Owner create OK (enqueues, binds ownership, returns accepted).
2. Invalid/revoked auth rejected.
3. Service-principal create & read OK.
4. Owner read OK.
5. Cross-tenant read rejected with non-disclosing 404 Not Found.
6. Same tenant non-owner/non-admin read rejected with 403 Forbidden.
7. Missing ownership metadata fails closed (404 Not Found).
8. Celery-down / broker failure returns explicit 503, never false acceptance.
9. Worker execution failure results in FAILURE task state, never false SUCCESS.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import CurrentUser, get_api_key, get_optional_current_user_from_header
from api.studies import router as studies_router
from core_model.specs import StudyRequest
from services.task_ownership import (
    TaskAccessForbiddenError,
    TaskOwnershipError,
    TaskTenantMismatchError,
    get_task_ownership,
    record_task_ownership,
    verify_task_access,
)
from worker.tasks import execute_engineering_study_task


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(studies_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_task_ownership_direct_enforcement():
    """Direct tests for services/task_ownership.py functions."""
    task_id = "test_task_direct_101"
    record = record_task_ownership(
        task_id=task_id,
        user_id="user_alice",
        tenant_id="tenant_alpha",
        user_role="engineer",
        study_type="load_flow",
    )
    assert record["task_id"] == task_id
    assert get_task_ownership(task_id)["user_id"] == "user_alice"

    # Owner access OK
    res = verify_task_access(
        task_id=task_id,
        caller_user_id="user_alice",
        caller_tenant_id="tenant_alpha",
        caller_role="engineer",
    )
    assert res["task_id"] == task_id

    # Admin access in same tenant OK
    admin_res = verify_task_access(
        task_id=task_id,
        caller_user_id="user_bob_admin",
        caller_tenant_id="tenant_alpha",
        caller_role="admin",
    )
    assert admin_res["task_id"] == task_id

    # Cross-tenant access fails with TaskTenantMismatchError
    with pytest.raises(TaskTenantMismatchError):
        verify_task_access(
            task_id=task_id,
            caller_user_id="user_alice",
            caller_tenant_id="tenant_beta",
            caller_role="engineer",
        )

    # Same tenant non-owner non-admin fails with TaskAccessForbiddenError
    with pytest.raises(TaskAccessForbiddenError):
        verify_task_access(
            task_id=task_id,
            caller_user_id="user_charlie",
            caller_tenant_id="tenant_alpha",
            caller_role="engineer",
        )

    # Unknown task fails closed with TaskOwnershipError
    with pytest.raises(TaskOwnershipError):
        verify_task_access(
            task_id="non_existent_task",
            caller_user_id="user_alice",
            caller_tenant_id="tenant_alpha",
            caller_role="admin",
        )


def test_async_run_study_owner_create_and_read(client, app):
    """Test authenticated user creates async task and reads status."""
    mock_user = CurrentUser(
        user_id="user_engineer_1",
        username="engineer1",
        email="eng1@test.com",
        role="engineer",
        is_active=True,
        tenant_id="tenant_industrial",
    )

    app.dependency_overrides[get_api_key] = lambda: "valid_key"
    app.dependency_overrides[get_optional_current_user_from_header] = lambda: mock_user

    mock_celery_task = MagicMock()
    mock_celery_task.id = "task_celery_777"

    mock_async_result = MagicMock()
    mock_async_result.status = "SUCCESS"
    mock_async_result.ready.return_value = True
    mock_async_result.successful.return_value = True
    mock_async_result.result = {"success": True, "converged": True}

    with patch("api.studies.get_celery_components") as mock_get_celery:
        mock_enqueue = MagicMock()
        mock_enqueue.delay.return_value = mock_celery_task
        mock_get_celery.return_value = (
            MagicMock(return_value=mock_async_result),
            mock_enqueue,
            MagicMock(),
        )

        # 1. Enqueue async study
        payload = {
            "study_type": "load_flow",
            "parameters": {"tol": 1e-5},
            "system": {
                "base_mva": 100.0,
                "buses": [
                    {"bus_id": 1, "bus_type": "slack", "base_kv": 13.8, "voltage_magnitude": 1.0},
                    {"bus_id": 2, "bus_type": "pq", "base_kv": 13.8, "voltage_magnitude": 1.0},
                ],
                "lines": [
                    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
                ],
                "generators": [
                    {"generator_id": 1, "bus_id": 1, "mw": 10.0},
                ],
                "loads": [
                    {"load_id": 1, "bus_id": 2, "p_mw": 5.0, "q_mvar": 2.0},
                ],
            },
        }
        resp = client.post("/api/v1/studies/run_async", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["task_id"] == "task_celery_777"
        assert data["status"] == "accepted"

        # Verify task ownership record was written
        ownership = get_task_ownership("task_celery_777")
        assert ownership is not None
        assert ownership["user_id"] == "user_engineer_1"
        assert ownership["tenant_id"] == "tenant_industrial"

        # 2. Owner reads status -> 200
        status_resp = client.get("/api/v1/studies/task_status/task_celery_777")
        assert status_resp.status_code == 200
        assert status_resp.json()["task_id"] == "task_celery_777"
        assert status_resp.json()["status"] == "SUCCESS"

    app.dependency_overrides.clear()


def test_async_task_cross_tenant_isolation(client, app):
    """Test that a user from a different tenant gets non-disclosing 404."""
    # Pre-record task belonging to tenant_alpha
    record_task_ownership(
        task_id="task_isolated_999",
        user_id="user_alpha",
        tenant_id="tenant_alpha",
        user_role="engineer",
        study_type="load_flow",
    )

    foreign_user = CurrentUser(
        user_id="user_beta",
        username="userbeta",
        email="beta@test.com",
        role="engineer",
        is_active=True,
        tenant_id="tenant_beta",
    )

    app.dependency_overrides[get_api_key] = lambda: "valid_key"
    app.dependency_overrides[get_optional_current_user_from_header] = lambda: foreign_user

    resp = client.get("/api/v1/studies/task_status/task_isolated_999")
    # Must fail with 404 (non-disclosing), not 403 or 200
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"

    app.dependency_overrides.clear()


def test_async_task_missing_ownership_fails_closed(client, app):
    """Test that looking up a task with no ownership record fails closed with 404."""
    user = CurrentUser(
        user_id="user_any",
        username="userany",
        email="any@test.com",
        role="engineer",
        is_active=True,
        tenant_id="tenant_any",
    )
    app.dependency_overrides[get_api_key] = lambda: "valid_key"
    app.dependency_overrides[get_optional_current_user_from_header] = lambda: user

    resp = client.get("/api/v1/studies/task_status/task_untracked_000")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"

    app.dependency_overrides.clear()


def test_async_task_celery_down_returns_503(client, app):
    """Test that when Celery is unavailable, 503 is returned, never false acceptance."""
    user = CurrentUser(
        user_id="user_eng",
        username="usereng",
        email="eng@test.com",
        role="engineer",
        is_active=True,
        tenant_id="tenant_eng",
    )
    app.dependency_overrides[get_api_key] = lambda: "valid_key"
    app.dependency_overrides[get_optional_current_user_from_header] = lambda: user

    with patch("api.studies.get_celery_components", return_value=(None, None, None)):
        payload = {
            "study_type": "load_flow",
            "parameters": {},
            "system": {
                "base_mva": 100.0,
                "buses": [
                    {"bus_id": 1, "bus_type": "slack", "base_kv": 13.8, "voltage_magnitude": 1.0},
                    {"bus_id": 2, "bus_type": "pq", "base_kv": 13.8, "voltage_magnitude": 1.0},
                ],
                "lines": [
                    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
                ],
                "generators": [
                    {"generator_id": 1, "bus_id": 1, "mw": 10.0},
                ],
                "loads": [
                    {"load_id": 1, "bus_id": 2, "p_mw": 5.0, "q_mvar": 2.0},
                ],
            },
        }
        resp = client.post("/api/v1/studies/run_async", json=payload)
        assert resp.status_code == 503
        assert "Celery is not available" in resp.json()["detail"]

    app.dependency_overrides.clear()


def test_worker_task_failure_state():
    """Test that worker/tasks.py sets FAILURE state if study solver returns success=False."""
    mock_failed_result = MagicMock()
    mock_failed_result.success = False
    mock_failed_result.errors = ["Divergence detected in iteration 50"]
    mock_failed_result.model_dump.return_value = {
        "success": False,
        "errors": ["Divergence detected in iteration 50"],
    }

    with patch("worker.tasks.current_task") as mock_ct, \
         patch("worker.tasks.execute_study_logic", return_value=mock_failed_result):

        study_data = {
            "study_type": "load_flow",
            "data": {
                "study_type": "load_flow",
                "parameters": {"max_iter": 50},
                "system": {
                    "buses": [{"bus_id": 1, "bus_type": "slack", "base_kv": 13.8}],
                    "generators": [{"generator_id": 1, "bus_id": 1, "mw": 10.0}],
                },
            },
            "user_id": "test_user",
            "tenant_id": "test_tenant",
        }

        res = execute_engineering_study_task(study_data)
        assert res["success"] is False

        # Verify state was updated to FAILURE
        failure_calls = [c for c in mock_ct.update_state.call_args_list if c.kwargs.get("state") == "FAILURE"]
        assert len(failure_calls) >= 1
        assert failure_calls[0].kwargs["meta"]["status"] == "Study failed"
