"""Align notifications table columns with Notification ORM model.

Revision ID: 014_fix_notifications_schema
Revises: 013_add_totp_secret_to_users
Create Date: 2026-10-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014_fix_notifications_schema"
down_revision = "013_add_totp_secret_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "notifications" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("notifications")}

        with op.batch_alter_table("notifications") as batch_op:
            if "notification_type" not in existing_cols:
                if "type" in existing_cols:
                    batch_op.alter_column("type", new_column_name="notification_type")
                else:
                    batch_op.add_column(
                        sa.Column("notification_type", sa.String(64), nullable=False, server_default="system_alert")
                    )

            if "priority" not in existing_cols:
                batch_op.add_column(
                    sa.Column("priority", sa.String(16), nullable=False, server_default="normal")
                )

            if "is_archived" not in existing_cols:
                batch_op.add_column(
                    sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false"))
                )

            if "requires_email" not in existing_cols:
                batch_op.add_column(
                    sa.Column("requires_email", sa.Boolean(), nullable=False, server_default=sa.text("false"))
                )

            if "email_sent" not in existing_cols:
                batch_op.add_column(
                    sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.text("false"))
                )

            if "read_at" not in existing_cols:
                batch_op.add_column(
                    sa.Column("read_at", sa.DateTime(timezone=True), nullable=True)
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "notifications" in existing_tables:
        existing_cols = {c.get("name") for c in inspector.get_columns("notifications")}
        with op.batch_alter_table("notifications") as batch_op:
            if "notification_type" in existing_cols and "type" not in existing_cols:
                batch_op.alter_column("notification_type", new_column_name="type")
            for col in ("priority", "is_archived", "requires_email", "email_sent", "read_at"):
                if col in existing_cols:
                    batch_op.drop_column(col)
