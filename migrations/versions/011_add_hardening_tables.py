"""Add project_solver_parameters, study_versions, and export_history tables.

Revision ID: 011_add_hardening_tables
Revises: 010_add_results_store
Create Date: 2026-09-16 00:00:00.000000

Creates:
1. ``project_solver_parameters`` — persisted solver configuration per project.
2. ``study_versions`` — study revision history and snapshots.
3. ``export_history`` — audit log of generated report exports.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "011_add_hardening_tables"
down_revision = "010_add_results_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. project_solver_parameters
    if "project_solver_parameters" not in existing_tables:
        op.create_table(
            "project_solver_parameters",
            sa.Column("project_id", sa.String(64), primary_key=True),
            sa.Column("convergence_tolerance", sa.Float(), nullable=False, server_default="1e-5"),
            sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("acceleration_factor", sa.Float(), nullable=False, server_default="1.6"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_solver_parameters_project_id", "project_solver_parameters", ["project_id"]
        )

    # 2. study_versions
    if "study_versions" not in existing_tables:
        op.create_table(
            "study_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("study_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("config_snapshot", sa.JSON(), nullable=False),
            sa.Column("results_snapshot", sa.JSON(), nullable=True),
            sa.Column("diff_summary", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_study_versions_tenant_id", "study_versions", ["tenant_id"])
        op.create_index("ix_study_versions_study_id", "study_versions", ["study_id"])
        op.create_index("ix_study_versions_project_id", "study_versions", ["project_id"])
        op.create_index("ix_study_versions_version_number", "study_versions", ["version_number"])

    # 3. export_history
    if "export_history" not in existing_tables:
        op.create_table(
            "export_history",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("study_id", sa.String(36), nullable=True),
            sa.Column("export_type", sa.String(16), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_export_history_project_id", "export_history", ["project_id"])
        op.create_index("ix_export_history_study_id", "export_history", ["study_id"])
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("export_history")}
        with op.batch_alter_table("export_history") as batch_op:
            if "study_id" not in existing_cols:
                batch_op.add_column(sa.Column("study_id", sa.String(36), nullable=True))
                batch_op.create_index("ix_export_history_study_id", ["study_id"])
            if "export_type" not in existing_cols:
                if "format" in existing_cols:
                    batch_op.alter_column("format", new_column_name="export_type")
                else:
                    batch_op.add_column(
                        sa.Column(
                            "export_type", sa.String(16), nullable=False, server_default="pdf"
                        )
                    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "export_history" in existing_tables:
        op.drop_table("export_history")

    if "study_versions" in existing_tables:
        op.drop_table("study_versions")

    if "project_solver_parameters" in existing_tables:
        op.drop_table("project_solver_parameters")
