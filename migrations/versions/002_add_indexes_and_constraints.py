"""Add performance indexes and check constraints.

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000

This migration adds:

* **Composite indexes** for common multi-column query patterns:
  - ``projects (status, created_by)`` — dashboard filtering
  - ``study_results (project_id, study_type)`` — study listing by type
  - ``sessions (user_id, is_revoked)`` — active session lookup
  - ``audit_log (user_id, timestamp)`` — user activity timeline

* **Check constraints** to enforce column value domains:
  - ``users.role`` IN ('admin', 'engineer', 'analyst', 'viewer', 'guest')
  - ``projects.status`` IN ('active', 'archived', 'deleted')

Note: SQLite has limited ALTER TABLE support, so check constraints are
applied via batch mode (table recreation behind the scenes).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite indexes and check constraints."""

    # ------------------------------------------------------------------
    # Composite indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_projects_status_created_by",
        "projects",
        ["status", "created_by"],
    )

    op.create_index(
        "ix_study_results_project_id_study_type",
        "study_results",
        ["project_id", "study_type"],
    )

    op.create_index(
        "ix_sessions_user_id_is_revoked",
        "sessions",
        ["user_id", "is_revoked"],
    )

    op.create_index(
        "ix_audit_log_user_id_timestamp",
        "audit_log",
        ["user_id", "timestamp"],
    )

    # ------------------------------------------------------------------
    # Check constraints — SQLite requires batch mode for ALTER operations
    # ------------------------------------------------------------------

    # users.role check constraint
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint(
            "ck_users_role",
            sa.text("role IN ('admin', 'engineer', 'analyst', 'viewer', 'guest')"),
        )

    # projects.status check constraint
    with op.batch_alter_table("projects") as batch_op:
        batch_op.create_check_constraint(
            "ck_projects_status",
            sa.text("status IN ('active', 'archived', 'deleted')"),
        )


def downgrade() -> None:
    """Remove composite indexes and check constraints."""

    # ------------------------------------------------------------------
    # Drop check constraints (batch mode for SQLite)
    # ------------------------------------------------------------------
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("ck_projects_status", type_="check")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")

    # ------------------------------------------------------------------
    # Drop composite indexes
    # ------------------------------------------------------------------
    op.drop_index("ix_audit_log_user_id_timestamp", table_name="audit_log")
    op.drop_index("ix_sessions_user_id_is_revoked", table_name="sessions")
    op.drop_index("ix_study_results_project_id_study_type", table_name="study_results")
    op.drop_index("ix_projects_status_created_by", table_name="projects")
