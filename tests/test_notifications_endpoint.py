"""
tests/test_notifications_endpoint.py — Regression tests for Notifications CRUD endpoint.

Verifies:
1. GET /api/v1/notifications does NOT return 422 for DbDep query parameters.
2. GET /api/v1/notifications and GET /api/v1/notifications/ both resolve with 200 OK.
3. Query parameters unread_only and notification_type function correctly.
4. GET /api/v1/notifications/unread returns unread notification count.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.database import async_session, init_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.notifications import create_notification, router


@pytest.fixture(autouse=True)
async def _setup_db():
    await init_db()
    yield


def _build_test_client(user: CurrentUser) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_from_header] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.asyncio
async def test_get_notifications_no_422():
    """Verify GET /api/v1/notifications returns 200 without 422 query parameter error."""
    test_user = CurrentUser(
        user_id="user-notif-1",
        username="notif_tester",
        email="notif@example.com",
        role="engineer",
        tenant_id="tenant-notif",
    )
    client = _build_test_client(user=test_user)

    # 1. Bare path
    resp_bare = client.get("/api/v1/notifications")
    assert resp_bare.status_code == 200, f"Expected 200, got {resp_bare.status_code}: {resp_bare.text}"
    data_bare = resp_bare.json()
    assert "notifications" in data_bare
    assert "total" in data_bare
    assert "unread_count" in data_bare

    # 2. Path with trailing slash
    resp_slash = client.get("/api/v1/notifications/")
    assert resp_slash.status_code == 200, resp_slash.text

    # 3. Path with unread_only query param
    resp_unread = client.get("/api/v1/notifications/?unread_only=true")
    assert resp_unread.status_code == 200, resp_unread.text
    assert resp_unread.json()["notifications"] == []

    # 4. Path with notification_type query param
    resp_type = client.get("/api/v1/notifications/?notification_type=study_complete")
    assert resp_type.status_code == 200, resp_type.text


@pytest.mark.asyncio
async def test_notifications_unread_and_create():
    """Verify creating a notification and reading unread count."""
    test_user = CurrentUser(
        user_id="user-notif-2",
        username="notif_tester2",
        email="notif2@example.com",
        role="engineer",
        tenant_id="tenant-notif",
    )
    client = _build_test_client(user=test_user)

    # Create notification in database
    async with async_session() as session:
        await create_notification(
            db=session,
            user_id="user-notif-2",
            notification_type="system_alert",
            title="Transformer Overload Alert",
            message="Transformer T-1 loaded to 105%",
        )
        await session.commit()

    # Get notifications
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["unread_count"] >= 1
    assert any(n["title"] == "Transformer Overload Alert" for n in data["notifications"])

    # Get unread endpoint
    unread_resp = client.get("/api/v1/notifications/unread")
    assert unread_resp.status_code == 200
    assert unread_resp.json()["unread_count"] >= 1
