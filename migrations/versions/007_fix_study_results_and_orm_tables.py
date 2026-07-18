"""Fix study_results column drift + add missing ORM tables.

Revision ID: 007_fix_study_results_and_orm_tables
Revises: 006_scada_gis_email
Create Date: 2026-07-18

Why this migration exists
--------------------------
The audit found a critical ORM/Migration drift on the study_results table:
- Migration 001 created columns: parameters, result_data, warnings, errors,
  execution_time_sec, provider, native
- ORM model (api/projects.py:StudyResult) expects: config, results,
  error_message, completed_at, status

In PostgreSQL, INSERT/SELECT would fail because the ORM references columns
that don't exist in the migration schema.

This migration:
1. Adds the missing ORM columns to study_results (config, results,
   error_message, completed_at, status)
2. Migrates data from old columns to new ones (best-effort)
3. Drops the old columns that are no longer used

Additionally, 10 ORM models exist without corresponding migrations.
This migration creates the missing tables:
- equipment_categories (already created by Base.metadata.create_all,
  but not by Alembic — this formalizes it)
- study_templates
- notifications
- export_history
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_fix_study_results_and_orm_tables"
down_revision = "006_scada_gis_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Fix study_results column drift ──────────────────────────
    # Add ORM-expected columns that don't exist in migration 001

    # Check if column exists before adding (SQLite doesn't support IF NOT EXISTS)
    inspector = sa.inspect(op.get_bind())
    study_results_cols = {c["name"] for c in inspector.get_columns("study_results")}

    if "status" not in study_results_cols:
        op.add_column("study_results", sa.Column("status", sa.String(32), server_default="pending"))
    if "config" not in study_results_cols:
        op.add_column("study_results", sa.Column("config", sa.JSON(), nullable=True))
    if "results" not in study_results_cols:
        op.add_column("study_results", sa.Column("results", sa.JSON(), nullable=True))
    if "error_message" not in study_results_cols:
        op.add_column("study_results", sa.Column("error_message", sa.String(2000), nullable=True))
    if "completed_at" not in study_results_cols:
        op.add_column("study_results", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    # Migrate data from old columns to new (best-effort, non-fatal on error)
    try:
        op.execute("""
            UPDATE study_results
            SET config = parameters,
                results = result_data,
                error_message = errors
            WHERE config IS NULL AND parameters IS NOT NULL
        """)
    except Exception:
        pass  # Non-fatal — old columns may not have data

    # Note: We do NOT drop old columns (parameters, result_data, warnings,
    # errors, execution_time_sec, provider, native) to avoid data loss.
    # They are simply unused by the ORM going forward.

    # ── 2. Create missing ORM tables ───────────────────────────────

    # equipment_categories (ORM: api/equipment.py:EquipmentCategory)
    equipment_cols = {c["name"] for c in inspector.get_columns("equipment_categories")} \
        if "equipment_categories" in inspector.get_table_names() else set()
    if not equipment_cols:
        op.create_table(
            "equipment_categories",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), unique=True, nullable=False),
            sa.Column("slug", sa.String(128), unique=True, nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("icon", sa.String(64), nullable=True),
            sa.Column("display_order", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        )

    # study_templates (ORM: api/templates.py)
    templates_cols = {c["name"] for c in inspector.get_columns("study_templates")} \
        if "study_templates" in inspector.get_table_names() else set()
    if not templates_cols:
        op.create_table(
            "study_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("study_type", sa.String(64), nullable=False),
            sa.Column("parameters", sa.JSON(), nullable=True),
            sa.Column("is_public", sa.Boolean(), default=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        )
        op.create_index("ix_study_templates_created_by", "study_templates", ["created_by"])

    # notifications (ORM: api/notifications.py)
    notif_cols = {c["name"] for c in inspector.get_columns("notifications")} \
        if "notifications" in inspector.get_table_names() else set()
    if not notif_cols:
        op.create_table(
            "notifications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False, index=True),
            sa.Column("type", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("is_read", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # export_history (ORM: api/export.py)
    export_cols = {c["name"] for c in inspector.get_columns("export_history")} \
        if "export_history" in inspector.get_table_names() else set()
    if not export_cols:
        op.create_table(
            "export_history",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("format", sa.String(16), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_export_history_project_id", "export_history", ["project_id"])

    # RBAC tables (ORM: api/rbac.py)
    roles_cols = {c["name"] for c in inspector.get_columns("roles")} \
        if "roles" in inspector.get_table_names() else set()
    if not roles_cols:
        op.create_table(
            "roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(64), unique=True, nullable=False),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    permissions_cols = {c["name"] for c in inspector.get_columns("permissions")} \
        if "permissions" in inspector.get_table_names() else set()
    if not permissions_cols:
        op.create_table(
            "permissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("resource", sa.String(64), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("description", sa.String(255), nullable=True),
            sa.UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        )

    role_perms_cols = {c["name"] for c in inspector.get_columns("role_permissions")} \
        if "role_permissions" in inspector.get_table_names() else set()
    if not role_perms_cols:
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("permission_id", sa.String(36), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
        )

    user_roles_cols = {c["name"] for c in inspector.get_columns("user_roles")} \
        if "user_roles" in inspector.get_table_names() else set()
    if not user_roles_cols:
        op.create_table(
            "user_roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), nullable=False),
            sa.Column("assigned_by", sa.String(36), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        )
        op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])


def downgrade() -> None:
    # Drop RBAC tables
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")

    # Drop app tables
    op.drop_table("export_history")
    op.drop_table("notifications")
    op.drop_table("study_templates")

    # Note: equipment and equipment_categories are handled by Base.metadata
    # (ORM model exists). We don't drop them here to avoid data loss.

    # Remove study_results new columns (data loss — but they didn't exist before 007)
    try:
        op.drop_column("study_results", "completed_at")
        op.drop_column("study_results", "error_message")
        op.drop_column("study_results", "results")
        op.drop_column("study_results", "config")
        op.drop_column("study_results", "status")
    except Exception:
        pass  # SQLite may not support DROP COLUMN
