from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.dependencies import CurrentUser, get_api_key
from api.rbac import require_permission
from api.storage_management import StoragePurgeRequest, router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def tenant_a_user():
    return CurrentUser(
        user_id="user_a",
        username="user_a",
        tenant_id="tenant_a",
        email="a@example.com",
        role="admin",
    )


@pytest.fixture
def tenant_b_user():
    return CurrentUser(
        user_id="user_b",
        username="user_b",
        tenant_id="tenant_b",
        email="b@example.com",
        role="admin",
    )


@pytest.fixture
def unprivileged_user():
    return CurrentUser(
        user_id="user_viewer",
        username="user_viewer",
        tenant_id="tenant_a",
        email="viewer@example.com",
        role="viewer",
    )


@pytest.mark.asyncio
async def test_storage_metrics_tenant_scoping(tenant_a_user, tenant_b_user):
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"
    app.dependency_overrides[require_permission("storage", "manage")] = lambda: tenant_b_user

    mock_objects = [
        {"key": "tenant_a/reports/r1.pdf", "size": 100, "last_modified": "2026-09-01T00:00:00Z"},
        {"key": "tenant_b/reports/r2.pdf", "size": 200, "last_modified": "2026-09-01T00:00:00Z"},
    ]

    with patch("api.storage_management.is_r2_enabled", return_value=True), \
         patch("api.storage_management.list_objects", new_callable=AsyncMock) as mock_list:
        # Mock list_objects to only return tenant_b items when queried with tenant_b/
        async def mock_list_side_effect(prefix="", limit=100, tenant_id=None):
            return [o for o in mock_objects if o["key"].startswith(prefix)]
        mock_list.side_effect = mock_list_side_effect

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/storage/metrics", headers={"X-API-Key": "test-api-key"})
            assert resp.status_code == 200
            data = resp.json()
            # Tenant B should only see 200 bytes, not Tenant A's 100 bytes
            assert data["total_size_bytes"] == 200
            assert data["total_objects"] == 1


@pytest.mark.asyncio
async def test_storage_purge_tenant_isolation(tenant_a_user):
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"
    app.dependency_overrides[require_permission("storage", "manage")] = lambda: tenant_a_user

    with patch("api.storage_management.is_r2_enabled", return_value=True), \
         patch("api.storage_management.list_objects", new_callable=AsyncMock) as mock_list, \
         patch("api.storage_management.delete_many", new_callable=AsyncMock) as mock_delete:
        mock_list.return_value = [
            {"key": "tenant_a/reports/r1.pdf", "size": 100, "last_modified": "2026-01-01T00:00:00Z"}
        ]
        mock_delete.return_value = 1

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/storage/purge",
                json={"prefix": "reports/", "dry_run": False, "older_than_days": 30},
                headers={"X-API-Key": "test-api-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted_count"] == 1
            assert data["freed_bytes"] == 100
