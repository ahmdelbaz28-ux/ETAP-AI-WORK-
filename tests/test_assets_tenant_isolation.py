"""tests/test_assets_tenant_isolation.py — Verify IDOR prevention & tenant isolation on /api/v1/assets."""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.assets import Asset
from api.database import get_db
from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from api.routes import app


@pytest.fixture
def override_auth():
    pass

@pytest.mark.asyncio
async def test_asset_tenant_isolation_idor(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "false")
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-api-key")

    # Create test assets for tenant-A and tenant-B
    asset_a_id = str(uuid.uuid4())
    asset_b_id = str(uuid.uuid4())

    from api.database import async_session
    async with async_session() as db:
        asset_a = Asset(
            id=asset_a_id,
            tenant_id="tenant-A",
            name="Transformer-A",
            type="transformer",
            rating=100.0,
            voltage=11.0,
            status="active",
            created_by="user-a",
        )
        asset_b = Asset(
            id=asset_b_id,
            tenant_id="tenant-B",
            name="Transformer-B",
            type="transformer",
            rating=200.0,
            voltage=33.0,
            status="active",
            created_by="user-b",
        )
        db.add(asset_a)
        db.add(asset_b)
        await db.commit()

    # User in Tenant A
    user_a = CurrentUser(
        user_id="user-a",
        username="alice",
        email="alice@example.com",
        role="engineer",
        tenant_id="tenant-A",
    )
    # Admin user
    user_admin = CurrentUser(
        user_id="admin-1",
        username="admin",
        email="admin@example.com",
        role="admin",
        tenant_id="tenant-A",
    )

    app.dependency_overrides[get_api_key] = lambda: "test-api-key"

    from api.csrf import generate_csrf_token
    csrf_token = generate_csrf_token()
    headers = {"x-csrf-token": csrf_token}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            # 1. User A accesses their own asset -> 200
            app.dependency_overrides[get_current_user_from_header] = lambda: user_a
            res = await client.get(f"/api/v1/assets/{asset_a_id}")
            assert res.status_code == 200
            assert res.json()["name"] == "Transformer-A"

            # 2. User A accesses Tenant B's asset -> 404 (IDOR prevention)
            res = await client.get(f"/api/v1/assets/{asset_b_id}")
            assert res.status_code == 404

            # 3. User A tries to update Tenant B's asset -> 404
            res = await client.put(f"/api/v1/assets/{asset_b_id}", json={"name": "Hacked"})
            assert res.status_code == 404

            # 4. User A tries to delete Tenant B's asset -> 404
            res = await client.delete(f"/api/v1/assets/{asset_b_id}")
            assert res.status_code == 404

            # 5. Admin accesses Tenant B's asset -> 200
            app.dependency_overrides[get_current_user_from_header] = lambda: user_admin
            res = await client.get(f"/api/v1/assets/{asset_b_id}")
            assert res.status_code == 200

    finally:
        app.dependency_overrides.clear()
        # Clean up database records
        async with async_session() as db:
            a1 = await db.scalar(select(Asset).where(Asset.id == asset_a_id))
            if a1:
                await db.delete(a1)
            b1 = await db.scalar(select(Asset).where(Asset.id == asset_b_id))
            if b1:
                await db.delete(b1)
            await db.commit()
