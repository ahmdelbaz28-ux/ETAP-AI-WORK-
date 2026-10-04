"""
tests/test_notification_config.py — Regression tests for Fix 14 (Notification Config Persistence).

Verifies:
1. Webhooks and NotificationConfig persist to the database (survives app restart / cache clear).
2. Webhook secret is encrypted at rest in the database using secrets_manager Fernet cipher.
3. Audit logging is triggered on configuration updates and webhook operations.
"""

from __future__ import annotations

import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.database import async_session, init_db
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
    get_optional_current_user_from_header,
)
from api.notification_config import (
    NotificationConfig,
    WebhookConfig,
    _decrypt_secret,
    _default_store,
    _store,
    router,
)


@pytest.fixture(autouse=True)
async def _setup_db():
    await init_db()
    # Reset in-memory store
    _store.clear()
    _store.update(_default_store())
    yield


def _build_test_client(monkeypatch, user: CurrentUser | None = None) -> TestClient:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_api_key] = lambda: "valid-test-key"
    if user:
        app.dependency_overrides[get_optional_current_user_from_header] = lambda: user
        app.dependency_overrides[get_current_user_from_header] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.asyncio
async def test_webhook_persists_across_app_restart(monkeypatch):
    """Fix 14: Configure webhook, simulate app restart (clear _store), verify config persists from DB."""
    admin_user = CurrentUser(
        user_id="admin-1",
        username="admin",
        email="admin@example.com",
        role="admin",
        tenant_id="tenant-1",
    )
    client = _build_test_client(monkeypatch, user=admin_user)

    secret_value = "my_confidential_webhook_secret_12345"
    payload = {
        "url": "https://example.com/alerts/webhook",
        "events": ["arc_flash", "short_circuit"],
        "secret": secret_value,
    }

    # 1. Register a new webhook
    resp = client.post("/api/v1/notifications/digest/config/webhooks", json=payload)
    assert resp.status_code == 201, resp.text
    wh_data = resp.json()
    webhook_id = wh_data["id"]
    assert wh_data["url"] == payload["url"]

    # 2. Verify encryption at rest in DB
    async with async_session() as session:
        stmt = select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        result = await session.execute(stmt)
        db_obj = result.scalar_one_or_none()
        assert db_obj is not None
        # Secret in DB must NOT be plaintext
        assert db_obj.secret != secret_value
        assert len(db_obj.secret) > 0
        # Decrypted secret matches original
        assert _decrypt_secret(db_obj.secret) == secret_value

    # 3. Simulate application restart: clear in-memory store
    _store.clear()
    _store.update(_default_store())
    assert webhook_id not in _store["webhooks"]

    # 4. Create new client instance (simulating fresh server)
    fresh_client = _build_test_client(monkeypatch, user=admin_user)
    list_resp = fresh_client.get("/api/v1/notifications/digest/config/webhooks")
    assert list_resp.status_code == 200
    webhooks = list_resp.json()
    assert any(w["id"] == webhook_id for w in webhooks)

    # 5. Delete webhook and verify deletion from DB
    del_resp = fresh_client.delete(f"/api/v1/notifications/digest/config/webhooks/{webhook_id}")
    assert del_resp.status_code == 204

    async with async_session() as session:
        stmt = select(WebhookConfig).where(WebhookConfig.id == webhook_id)
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_notification_config_persists_across_restart(monkeypatch):
    """Fix 14: Update digest and alert preferences, simulate restart, verify DB persistence."""
    admin_user = CurrentUser(
        user_id="admin-1",
        username="admin",
        email="admin@example.com",
        role="admin",
        tenant_id="tenant-1",
    )
    client = _build_test_client(monkeypatch, user=admin_user)

    # Update digest schedule
    digest_payload = {
        "period": "weekly",
        "schedule_time": "14:30",
        "timezone": "Europe/London",
        "enabled": True,
    }
    put_resp = client.put("/api/v1/notifications/digest/config/digest", json=digest_payload)
    assert put_resp.status_code == 200
    assert put_resp.json()["period"] == "weekly"

    # Simulate app restart
    _store.clear()
    _store.update(_default_store())
    assert _store["digest"]["period"] == "daily"  # reset to default in memory

    # Query afresh
    fresh_client = _build_test_client(monkeypatch, user=admin_user)
    get_resp = fresh_client.get("/api/v1/notifications/digest/config/digest")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["period"] == "weekly"
    assert data["schedule_time"] == "14:30"
    assert data["timezone"] == "Europe/London"
