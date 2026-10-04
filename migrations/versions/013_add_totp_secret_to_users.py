"""Add totp_secret column to users table.

Revision ID: 013_add_totp_secret_to_users
Revises: 012_study_version_unique
Create Date: 2026-10-04 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_add_totp_secret_to_users"
down_revision = "012_study_version_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "users" in existing_tables:
        existing_cols = [c.get("name") for c in inspector.get_columns("users")]
        if "totp_secret" not in existing_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column("totp_secret", sa.String(64), nullable=True)
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "users" in existing_tables:
        existing_cols = [c.get("name") for c in inspector.get_columns("users")]
        if "totp_secret" in existing_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("totp_secret")
