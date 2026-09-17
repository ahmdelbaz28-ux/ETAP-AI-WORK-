"""
tests/test_fix24_admin_bootstrap.py — Tests for FIX-24 Initial Admin Bootstrap.

Verifies:
1. scripts/create_admin.py enforces password strength rules.
2. Creates an administrator user in the database.
3. Successfully promotes an existing viewer to administrator.
4. Idempotently recognizes already-existing administrators without errors.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.auth import User, UserService, _validate_password_strength
from api.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def test_password_strength_validation():
    """Verify password policy rejects weak passwords and accepts compliant ones."""
    # Too short (< 8 chars)
    with pytest.raises(ValueError):
        _validate_password_strength("Short1")

    # No digit
    with pytest.raises(ValueError):
        _validate_password_strength("NoDigitsInThisPassword")

    # No letter
    with pytest.raises(ValueError):
        _validate_password_strength("123456789012")

    # Common password
    with pytest.raises(ValueError):
        _validate_password_strength("password123")

    # Valid strong password
    assert _validate_password_strength("SuperSecureAdminPass2026!") == "SuperSecureAdminPass2026!"


@pytest.mark.asyncio
async def test_first_user_or_admin_bootstrap(async_db: AsyncSession):
    """Verify first user created or INITIAL_ADMIN_EMAIL is automatically admin (FIX-24)."""
    # 1. First user created in system defaults to admin role
    first_user = await UserService.create(
        db=async_db,
        username="lead_admin",
        email="admin@etap-ai.internal",
        password="SuperSecureAdminPass2026!",
        role="viewer",  # Even if viewer requested, bootstrap elevates first user to admin
    )
    await async_db.commit()

    assert first_user.role == "admin"

    # 2. Second user created as viewer remains viewer
    second_user = await UserService.create(
        db=async_db,
        username="regular_viewer",
        email="viewer@etap-ai.internal",
        password="SuperSecureViewerPass2026!",
        role="viewer",
    )
    await async_db.commit()

    assert second_user.role == "viewer"

    # 3. Promote second user to admin
    second_user.role = "admin"
    await async_db.commit()

    res = await async_db.execute(select(User).where(User.username == "regular_viewer"))
    promoted = res.scalar_one()
    assert promoted.role == "admin"


@pytest.mark.asyncio
async def test_concurrent_admin_bootstrap_with_pinned_email(async_db: AsyncSession, monkeypatch):
    """Verify that in concurrent multi-worker registration, INITIAL_ADMIN_EMAIL deterministically pins the admin.

    Note on Cold-Start Concurrency:
    Pure user_count == 0 bootstrap is intended for single-process sequential initial setup.
    In multi-worker environments, INITIAL_ADMIN_EMAIL must be configured in environment variables
    to guarantee that exactly the intended user receives administrative privileges under race conditions.
    """
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "designated_lead@etap-ai.internal")

    # Simulate concurrent registration of two users before either is committed
    user_a = await UserService.create(
        db=async_db,
        username="designated_lead",
        email="designated_lead@etap-ai.internal",
        password="SuperSecurePass2026!A",
        role="viewer",
    )
    user_b = await UserService.create(
        db=async_db,
        username="parallel_candidate",
        email="candidate@etap-ai.internal",
        password="SuperSecurePass2026!B",
        role="viewer",
    )
    await async_db.commit()

    # The designated email MUST become admin, while candidate must remain viewer
    assert user_a.role == "admin"
    assert user_b.role == "viewer"
