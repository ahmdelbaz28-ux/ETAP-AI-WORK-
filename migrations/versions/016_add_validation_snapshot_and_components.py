"""Add validation_snapshot to pending_actions and create components table.

Revision ID: 016_snapshot_components
Revises: e8b91a2c3d4e
Create Date: 2026-10-14 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016_snapshot_components"
down_revision = "e8b91a2c3d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Add validation_snapshot to pending_actions
    if "pending_actions" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("pending_actions")}
        if "validation_snapshot" not in existing_cols:
            with op.batch_alter_table("pending_actions") as batch_op:
                batch_op.add_column(
                    sa.Column("validation_snapshot", sa.JSON(), nullable=True)
                )

    # 2. Create components table if not exists
    if "components" not in existing_tables:
        op.create_table(
            "components",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("type", sa.String(50), nullable=False, index=True),
            sa.Column("category", sa.String(128), nullable=False, index=True),
            sa.Column("subcategory", sa.String(128), nullable=True, index=True),
            sa.Column("name", sa.String(255), nullable=False, index=True),
            sa.Column("manufacturer", sa.String(255), nullable=True, index=True),
            sa.Column("model_number", sa.String(255), nullable=True),
            sa.Column("specs", sa.JSON(), nullable=True),
            sa.Column("standards", sa.JSON(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("is_verified", sa.Boolean(), default=True, index=True),
            sa.Column("source", sa.String(50), default="iec-standard"),
            sa.Column("contributor_id", sa.String(64), nullable=True),
            sa.Column("tenant_id", sa.String(64), nullable=True, index=True),
            sa.Column("review_status", sa.String(30), default="approved", index=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("reviewed_by", sa.String(64), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "components" in existing_tables:
        op.drop_table("components")

    if "pending_actions" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("pending_actions")}
        if "validation_snapshot" in existing_cols:
            with op.batch_alter_table("pending_actions") as batch_op:
                batch_op.drop_column("validation_snapshot")
