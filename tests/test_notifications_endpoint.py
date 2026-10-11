"""
tests/test_notifications_endpoint.py — Regression tests for Notifications CRUD endpoint.

Verifies:
1. GET /api/v1/notifications does NOT return 422 for DbDep query parameters.
2. GET /api/v1/notifications and GET /api/v1/notifications/ both resolve with 200 OK.
3. Query parameters unread_only and notification_type function correctly.
4. GET /api/v1/notifications/unread returns unread notification count.
"""

from __future__ import annotations

from typing import AsyncGenerator
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.notifications import create_notification, router

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
async def _setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _build_test_app(user: CurrentUser) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_from_header] = lambda: user
    app.dependency_overrides[get_db] = _override_get_db
    return app


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
    app = _build_test_app(user=test_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Bare path
        resp_bare = await client.get("/api/v1/notifications")
        assert resp_bare.status_code == 200, f"Expected 200, got {resp_bare.status_code}: {resp_bare.text}"
        data_bare = resp_bare.json()
        assert "notifications" in data_bare
        assert "total" in data_bare
        assert "unread_count" in data_bare

        # 2. Path with trailing slash
        resp_slash = await client.get("/api/v1/notifications/")
        assert resp_slash.status_code == 200, resp_slash.text

        # 3. Path with unread_only query param
        resp_unread = await client.get("/api/v1/notifications/?unread_only=true")
        assert resp_unread.status_code == 200, resp_unread.text
        assert resp_unread.json()["notifications"] == []

        # 4. Path with notification_type query param
        resp_type = await client.get("/api/v1/notifications/?notification_type=study_complete")
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
    app = _build_test_app(user=test_user)

    # Create notification in database
    async with test_session_factory() as session:
        await create_notification(
            db=session,
            user_id="user-notif-2",
            notification_type="system_alert",
            title="Transformer Overload Alert",
            message="Transformer T-1 loaded to 105%",
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Get notifications
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["unread_count"] >= 1
        assert any(n["title"] == "Transformer Overload Alert" for n in data["notifications"])

        # Get unread endpoint
        unread_resp = await client.get("/api/v1/notifications/unread")
        assert unread_resp.status_code == 200
        assert unread_resp.json()["unread_count"] >= 1
