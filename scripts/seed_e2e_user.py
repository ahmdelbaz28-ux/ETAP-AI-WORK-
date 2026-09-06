"""
scripts/seed_e2e_user.py — Seed idempotent E2E test user and tenant.

Ensures:
  - Fixed tenant exists: ID "00000000-0000-0000-0000-000000000001"
  - Test user exists: "e2e" / "e2e@test.local" bound to the tenant
  - Password hashed via bcrypt from env var E2E_USER_PASSWORD (default: Test123!)
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure repository root is in python path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

E2E_TENANT_ID = "00000000-0000-0000-0000-000000000001"
E2E_USERNAME = "e2e"
E2E_EMAIL = "e2e@test.local"


async def seed_e2e_user() -> None:
    from sqlalchemy import select

    from api.auth import User, _hash_password
    from api.database import async_session, init_db
    from api.tenants import Tenant

    await init_db()

    password = os.environ.get("E2E_USER_PASSWORD", "Test123!")

    async with async_session() as session:
        async with session.begin():
            # 1. Ensure Tenant exists
            tenant_res = await session.execute(
                select(Tenant).where(Tenant.id == E2E_TENANT_ID)
            )
            tenant = tenant_res.scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    id=E2E_TENANT_ID,
                    name="E2E Test Tenant",
                    slug="e2e-tenant",
                    is_active=True,
                    plan="enterprise",
                    max_projects=100,
                    max_users=50,
                )
                session.add(tenant)
                print(f"[E2E Seed] Created tenant {E2E_TENANT_ID}")
            else:
                print(f"[E2E Seed] Tenant {E2E_TENANT_ID} already exists")

            # 2. Ensure User exists
            user_res = await session.execute(
                select(User).where((User.username == E2E_USERNAME) | (User.email == E2E_EMAIL))
            )
            user = user_res.scalar_one_or_none()
            if not user:
                user = User(
                    username=E2E_USERNAME,
                    email=E2E_EMAIL,
                    password_hash=_hash_password(password),
                    role="engineer",
                    tenant_id=E2E_TENANT_ID,
                    is_active=True,
                )
                session.add(user)
                print(f"[E2E Seed] Created user {E2E_USERNAME} ({E2E_EMAIL})")
            else:
                user.tenant_id = E2E_TENANT_ID
                user.password_hash = _hash_password(password)
                user.is_active = True
                user.role = "engineer"
                print(f"[E2E Seed] Updated user {E2E_USERNAME} with current credentials and tenant")

    print("[E2E Seed] [OK] E2E user & tenant seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_e2e_user())
