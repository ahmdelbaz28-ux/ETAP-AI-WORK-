"""
scripts/seed_rbac.py — Seed default RBAC roles and permissions.

Run this script to initialize the database with:
- Core permissions (read, write, delete, manage for each resource)
- Default system roles (admin, engineer, viewer, guest)
- Admin role assigned ONLY to a specified user (NOT all users)

SECURITY (LAUNCH-BLOCKER): The previous version assigned admin role to
ALL existing users — a critical privilege escalation. Now admin is
assigned only to:
1. A user specified via --admin-username or --admin-email CLI arg
2. Or the first user in the database (if no arg given)
3. Or no user (if database is empty — admin must be created separately)

Usage:
    python scripts/seed_rbac.py                          # assigns admin to first user
    python scripts/seed_rbac.py --admin-username admin   # assigns admin to 'admin' user
    python scripts/seed_rbac.py --admin-email admin@example.com  # by email

Requires:
    - DATABASE_URL environment variable (or defaults to SQLite)
    - ENGINEERING_SERVICE_API_KEY for API auth (optional in dev)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC

UTC = UTC

# Add parent directory to path so we can import api modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def seed_rbac() -> None:
    """Seed the database with default RBAC roles and permissions."""
    from sqlalchemy import select

    from api.auth import User
    from api.database import async_session, init_db
    from api.rbac import (
        Permission,
        Role,
        UserRole,
        role_permissions,
    )

    # Initialize tables
    await init_db()

    async with async_session() as session:
        async with session.begin():
            # Check if already seeded
            existing = await session.execute(select(Role).where(Role.name == "admin"))
            if existing.scalar_one_or_none() is not None:
                print("[RBAC Seed] Roles already seeded — skipping.")
                return

            print("[RBAC Seed] Creating default permissions...")

            # ── Define all resources ──────────────────────────────────────
            resources = [
                "studies",
                "projects",
                "users",
                "roles",
                "permissions",
                "equipment",
                "reports",
                "settings",
                "notifications",
                "dashboard",
                "templates",
                "batch",
                "export",
                "import",
                "logs",
                "audit",
            ]

            # ── Define default actions ─────────────────────────────────────
            actions = ["list", "read", "create", "update", "delete", "manage"]

            # ── Create all permissions ─────────────────────────────────────
            all_permissions: dict[str, Permission] = {}
            for resource in resources:
                for action in actions:
                    perm_key = f"{resource}:{action}"
                    perm = Permission(
                        id=str(uuid.uuid4()),
                        resource=resource,
                        action=action,
                        description=f"Can {action} {resource}",
                    )
                    session.add(perm)
                    all_permissions[perm_key] = perm

            await session.flush()
            print(f"[RBAC Seed] Created {len(all_permissions)} permissions.")

            # ── Create system roles ────────────────────────────────────────
            print("[RBAC Seed] Creating system roles...")

            # Admin: all permissions
            admin_role = Role(
                id=str(uuid.uuid4()),
                name="admin",
                description="System administrator with full access",
                is_system=True,
            )
            session.add(admin_role)

            # Engineer: most permissions except admin-only
            engineer_role = Role(
                id=str(uuid.uuid4()),
                name="engineer",
                description="Power systems engineer with study and project access",
                is_system=True,
            )
            session.add(engineer_role)

            # Viewer: read-only permissions
            viewer_role = Role(
                id=str(uuid.uuid4()),
                name="viewer",
                description="Read-only access to studies and projects",
                is_system=True,
            )
            session.add(viewer_role)

            # Guest: minimal access
            guest_role = Role(
                id=str(uuid.uuid4()),
                name="guest",
                description="Guest with minimal access",
                is_system=True,
            )
            session.add(guest_role)

            await session.flush()
            print("[RBAC Seed] Created 4 system roles (admin, engineer, viewer, guest).")

            # ── Assign permissions to roles ────────────────────────────────

            # Admin gets ALL permissions
            admin_perm_ids = [p.id for p in all_permissions.values()]
            for perm_id in admin_perm_ids:
                await session.execute(
                    role_permissions.insert().values(
                        role_id=admin_role.id,
                        permission_id=perm_id,
                    )
                )

            # Engineer gets read/write on studies, projects, equipment, etc.
            engineer_resources = [
                "studies", "projects", "equipment", "reports",
                "templates", "batch", "export", "import",
                "dashboard", "notifications",
            ]
            engineer_actions = ["list", "read", "create", "update"]
            for resource in engineer_resources:
                for action in engineer_actions:
                    key = f"{resource}:{action}"
                    perm = all_permissions.get(key)
                    if perm:
                        await session.execute(
                            role_permissions.insert().values(
                                role_id=engineer_role.id,
                                permission_id=perm.id,
                            )
                        )
            # Also add engineer read/update for settings
            for action in ["list", "read"]:
                key = f"settings:{action}"
                perm = all_permissions.get(key)
                if perm:
                    await session.execute(
                        role_permissions.insert().values(
                            role_id=engineer_role.id,
                            permission_id=perm.id,
                        )
                    )

            # Viewer gets read-only on studies, projects, dashboard
            viewer_resources = ["studies", "projects", "dashboard", "reports"]
            viewer_actions = ["list", "read"]
            for resource in viewer_resources:
                for action in viewer_actions:
                    key = f"{resource}:{action}"
                    perm = all_permissions.get(key)
                    if perm:
                        await session.execute(
                            role_permissions.insert().values(
                                role_id=viewer_role.id,
                                permission_id=perm.id,
                            )
                        )

            # Guest gets only dashboard read
            for action in ["list", "read"]:
                key = f"dashboard:{action}"
                perm = all_permissions.get(key)
                if perm:
                    await session.execute(
                        role_permissions.insert().values(
                            role_id=guest_role.id,
                            permission_id=perm.id,
                        )
                    )

            print("[RBAC Seed] Permissions assigned to roles.")

            # ── Assign admin role to ONE specified user (NOT all users) ──
            # SECURITY (LAUNCH-BLOCKER): Previous version gave admin to
            # ALL users. Now admin is assigned to only one user:
            # 1. --admin-username arg if provided
            # 2. --admin-email arg if provided
            # 3. First user in DB (if no arg)
            # 4. No one (if DB is empty)
            import argparse as _ap
            _parser = _ap.ArgumentParser(description="Seed RBAC")
            _parser.add_argument("--admin-username", default=None,
                                 help="Username to assign admin role")
            _parser.add_argument("--admin-email", default=None,
                                 help="Email to assign admin role")
            _args, _ = _parser.parse_known_args()

            target_user = None
            if _args.admin_username:
                user_result = await session.execute(
                    select(User).where(User.username == _args.admin_username)
                )
                target_user = user_result.scalar_one_or_none()
                if target_user is None:
                    print(f"[RBAC Seed] ⚠️  User '{_args.admin_username}' not found — no admin assigned.")
            elif _args.admin_email:
                user_result = await session.execute(
                    select(User).where(User.email == _args.admin_email)
                )
                target_user = user_result.scalar_one_or_none()
                if target_user is None:
                    print(f"[RBAC Seed] ⚠️  User '{_args.admin_email}' not found — no admin assigned.")
            else:
                # Default: assign to first user (oldest account)
                user_result = await session.execute(
                    select(User).order_by(User.created_at.asc()).limit(1)
                )
                target_user = user_result.scalar_one_or_none()
                if target_user:
                    print(f"[RBAC Seed] No --admin-username specified. Assigning admin to first user: '{target_user.username}'")

            if target_user is not None:
                # Check if already assigned
                existing_ur = await session.execute(
                    select(UserRole).where(
                        UserRole.user_id == target_user.id,
                        UserRole.role_id == admin_role.id,
                    )
                )
                if existing_ur.scalar_one_or_none() is None:
                    user_role = UserRole(
                        id=str(uuid.uuid4()),
                        user_id=target_user.id,
                        role_id=admin_role.id,
                        assigned_by="system",
                    )
                    session.add(user_role)
                    print(f"[RBAC Seed] ✅ Assigned admin role to user: '{target_user.username}'")
                else:
                    print(f"[RBAC Seed] User '{target_user.username}' already has admin role.")
            else:
                print("[RBAC Seed] ⚠️  No users in database. Create a user first, then re-run with --admin-username.")

            await session.commit()

    print("[RBAC Seed] ✅ RBAC seeding complete!")


def main() -> None:
    """Entry point for the seed script."""
    asyncio.run(seed_rbac())


if __name__ == "__main__":
    main()
