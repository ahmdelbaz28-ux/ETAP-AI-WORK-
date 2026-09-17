#!/usr/bin/env python3
"""CLI utility to create or promote an administrator account (FIX-24).

Usage:
    python scripts/create_admin.py --username admin --email admin@etap-ai.internal --password "StrongPass123!"
Or via environment variables:
    INITIAL_ADMIN_USERNAME=admin INITIAL_ADMIN_EMAIL=admin@etap-ai.internal INITIAL_ADMIN_PASSWORD=... python scripts/create_admin.py
"""

import argparse
import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from api.database import async_session_factory
from api.auth import User, UserService, _validate_password_strength


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed or promote an administrator user account.")
    parser.add_argument("--username", default=os.getenv("INITIAL_ADMIN_USERNAME", "admin"))
    parser.add_argument(
        "--email", default=os.getenv("INITIAL_ADMIN_EMAIL", "admin@etap-ai.internal")
    )
    parser.add_argument("--password", default=os.getenv("INITIAL_ADMIN_PASSWORD"))

    args = parser.parse_args()

    if not args.password:
        print(
            "ERROR: Password must be supplied via --password or INITIAL_ADMIN_PASSWORD env var.",
            file=sys.stderr,
        )
        return 1

    try:
        _validate_password_strength(args.password)
    except ValueError as exc:
        print(f"ERROR: Password does not meet security requirements: {exc}", file=sys.stderr)
        return 1

    async with async_session_factory() as session:
        # Check if user already exists
        norm_email = args.email.strip().lower()
        stmt = select(User).where(
            (User.username == args.username) | (func.lower(User.email) == norm_email)
        )
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user:
            if user.role != "admin":
                user.role = "admin"
                await session.commit()
                print(
                    f"SUCCESS: Promoted existing user '{user.username}' ({user.email}) to role 'admin'."
                )
            else:
                print(f"NOTICE: User '{user.username}' is already an admin.")
            return 0

        # Create new admin
        new_admin = await UserService.create(
            db=session,
            username=args.username,
            email=norm_email,
            password=args.password,
            role="admin",
        )
        await session.commit()
        print(
            f"SUCCESS: Created new administrator account '{new_admin.username}' ({new_admin.email}) with role 'admin'."
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
