"""Add input_hash and output_hash columns to study_versions table.

Revision ID: e8b91a2c3d4e
Revises: 014_fix_notifications_schema
Create Date: 2026-10-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e8b91a2c3d4e"
down_revision = "014_fix_notifications_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "study_versions" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("study_versions")}
        with op.batch_alter_table("study_versions") as batch_op:
            if "input_hash" not in existing_cols:
                batch_op.add_column(
                    sa.Column("input_hash", sa.String(64), nullable=True)
                )
            if "output_hash" not in existing_cols:
                batch_op.add_column(
                    sa.Column("output_hash", sa.String(64), nullable=True)
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "study_versions" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("study_versions")}
        with op.batch_alter_table("study_versions") as batch_op:
            if "output_hash" in existing_cols:
                batch_op.drop_column("output_hash")
            if "input_hash" in existing_cols:
                batch_op.drop_column("input_hash")
