"""Add pending_actions and idempotency_keys tables for the Approval Gateway.

Revision ID: 009_pending_actions_idem
Revises: 008_add_tenant_id_and_rls
Create Date: 2026-08-25 00:00:00.000000

Creates:

1. ``pending_actions`` — one row per proposed tool action awaiting (or past)
   approval, with maker-checker identity columns and a TTL deadline.
2. ``idempotency_keys`` — stored responses keyed by ``Idempotency-Key`` so
   client retries never execute an operation twice.

Both tables are also created by ``Base.metadata.create_all()`` at app startup
(models live in ``api/approvals.py``); this migration keeps Alembic-managed
environments in sync.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "009_pending_actions_idem"
down_revision = "008_add_tenant_id_and_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "pending_actions" not in inspector.get_table_names():
        op.create_table(
            "pending_actions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("tool", sa.String(128), nullable=False),
            sa.Column("args_hash", sa.String(64), nullable=False),
            sa.Column("risk_class", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("requested_by_user_id", sa.String(64), nullable=False),
            sa.Column("requested_by_role", sa.String(32), nullable=False),
            sa.Column("decided_by_user_id", sa.String(64), nullable=True),
            sa.Column("decided_by_role", sa.String(32), nullable=True),
            sa.Column("args", sa.JSON(), nullable=True),
        )
        op.create_index("ix_pending_actions_tenant_id", "pending_actions", ["tenant_id"])
        op.create_index("ix_pending_actions_session_id", "pending_actions", ["session_id"])
        op.create_index("ix_pending_actions_status", "pending_actions", ["status"])
        op.create_index(
            "ix_pending_actions_session_status",
            "pending_actions",
            ["session_id", "status"],
        )

    if "idempotency_keys" not in inspector.get_table_names():
        op.create_table(
            "idempotency_keys",
            sa.Column("key", sa.String(128), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("endpoint", sa.String(255), nullable=False),
            sa.Column("response_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_idempotency_keys_tenant_id", "idempotency_keys", ["tenant_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "idempotency_keys" in inspector.get_table_names():
        op.drop_index("ix_idempotency_keys_tenant_id", table_name="idempotency_keys")
        op.drop_table("idempotency_keys")

    if "pending_actions" in inspector.get_table_names():
        op.drop_index("ix_pending_actions_session_status", table_name="pending_actions")
        op.drop_index("ix_pending_actions_status", table_name="pending_actions")
        op.drop_index("ix_pending_actions_session_id", table_name="pending_actions")
        op.drop_index("ix_pending_actions_tenant_id", table_name="pending_actions")
        op.drop_table("pending_actions")
