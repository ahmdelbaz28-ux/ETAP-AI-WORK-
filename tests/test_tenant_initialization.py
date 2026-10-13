"""tests/test_tenant_initialization.py — Tests for tenant initialization and schema provenance.

Verifies:
1. Default platform tenant is seeded idempotently on database initialization.
2. UserService.create distinguishes foreign key constraint violations (500) from
   unique constraint conflicts (409).
3. Alembic migration head revision matches migrations scripts.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.auth import UserService
from api.database import async_session, init_db
from api.database_migrations import check_schema_health, get_head_revision
from api.tenants import DEFAULT_TENANT_ID, Tenant, ensure_default_tenant


@pytest.mark.asyncio
async def test_default_tenant_seeded_by_init_db():
    """Ensure init_db guarantees the default tenant row exists in database."""
    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)
        )
        tenant = result.scalar_one_or_none()
        assert tenant is not None, "Default tenant must exist after init_db()"
        assert tenant.id == DEFAULT_TENANT_ID
        assert tenant.slug == "default"
        assert tenant.name == "Default Organization"
        assert tenant.is_active is True


@pytest.mark.asyncio
async def test_ensure_default_tenant_idempotent():
    """Calling ensure_default_tenant multiple times must be safely idempotent."""
    async with async_session() as session:
        t1 = await ensure_default_tenant(session)
        assert t1.id == DEFAULT_TENANT_ID

        t2 = await ensure_default_tenant(session)
        assert t2.id == DEFAULT_TENANT_ID
        assert t1.id == t2.id


@pytest.mark.asyncio
async def test_user_service_distinguishes_tenant_fk_error():
    """A ForeignKeyViolation on tenants must raise HTTP 500 with descriptive detail."""
    async with async_session() as session:
        orig_err = Exception(
            'insert or update on table "users" violates foreign key constraint "users_tenant_id_fkey"'
        )
        orig_err.sqlstate = "23503"
        orig_err.pgcode = "23503"
        fk_err = IntegrityError("INSERT INTO users ...", {}, orig_err)

        async def mock_flush():
            raise fk_err

        session.flush = mock_flush

        with pytest.raises(HTTPException) as exc_info:
            await UserService.create(
                db=session,
                username=f"fk_test_{uuid.uuid4().hex[:6]}",
                email=f"fk_test_{uuid.uuid4().hex[:6]}@example.com",
                password="StrongPassword123!",
                tenant_id=DEFAULT_TENANT_ID,
                role="viewer",
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Default tenant not initialized" in exc_info.value.detail


@pytest.mark.asyncio
async def test_user_service_distinguishes_unique_conflict():
    """A UniqueViolation (e.g., duplicate username) must raise HTTP 409."""
    async with async_session() as session:
        orig_err = Exception(
            'duplicate key value violates unique constraint "users_username_key"'
        )
        orig_err.sqlstate = "23505"
        orig_err.pgcode = "23505"
        unique_err = IntegrityError("INSERT INTO users ...", {}, orig_err)

        async def mock_flush():
            raise unique_err

        session.flush = mock_flush

        with pytest.raises(HTTPException) as exc_info:
            await UserService.create(
                db=session,
                username=f"dup_{uuid.uuid4().hex[:6]}",
                email=f"dup_{uuid.uuid4().hex[:6]}@example.com",
                password="StrongPassword123!",
                tenant_id=DEFAULT_TENANT_ID,
                role="viewer",
            )

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in exc_info.value.detail


@pytest.mark.asyncio
async def test_alembic_schema_health():
    """Verify that Alembic head revision is discovered and valid."""
    head_rev = get_head_revision()
    assert head_rev is not None, "Alembic head revision must be defined in migrations"
    assert len(head_rev) > 0

    health = await check_schema_health()
    assert health["status"] == "synchronized"
    assert health["head_revision"] == head_rev
