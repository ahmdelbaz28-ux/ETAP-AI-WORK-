"""Add `results` and `result_files` tables for the P5 ResultStore.

Revision ID: 010_add_results_store
Revises: 009_pending_actions_idem
Create Date: 2026-08-26 00:00:00.000000

Creates:

1. ``results`` — one row per stored study/BEMS result. Owner-scoped by
   ``tenant_id`` with a ``created_by`` user reference and an ``expires_at``
   TTL. ``summary_json`` holds metadata only — heavy content is stored as
   physical files on disk and referenced from ``result_files``.
2. ``result_files`` — one row per physical file stored for a result
   (``result_id`` FK with CASCADE delete), with path/mime/size metadata.

The tables are also created by ``Base.metadata.create_all()`` at app startup
(models live in ``api/results_store.py``); this migration keeps Alembic-managed
environments in sync.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "010_add_results_store"
down_revision = "009_pending_actions_idem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "results" not in inspector.get_table_names():
        op.create_table(
            "results",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("project_id", sa.String(64), nullable=True),
            sa.Column("created_by", sa.String(128), nullable=True),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_results_tenant_id", "results", ["tenant_id"])
        op.create_index("ix_results_project_id", "results", ["project_id"])
        op.create_index("ix_results_expires_at", "results", ["expires_at"])

    if "result_files" not in inspector.get_table_names():
        op.create_table(
            "result_files",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "result_id",
                sa.String(36),
                sa.ForeignKey("results.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("path", sa.String(512), nullable=False),
            sa.Column("mime", sa.String(128), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        )
        op.create_index("ix_result_files_result_id", "result_files", ["result_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "result_files" in inspector.get_table_names():
        op.drop_index("ix_result_files_result_id", table_name="result_files")
        op.drop_table("result_files")

    if "results" in inspector.get_table_names():
        op.drop_index("ix_results_tenant_id", table_name="results")
        op.drop_index("ix_results_project_id", table_name="results")
        op.drop_index("ix_results_expires_at", table_name="results")
        op.drop_table("results")