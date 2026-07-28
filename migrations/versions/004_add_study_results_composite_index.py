"""Add composite index (project_id, created_at DESC) on study_results.

Revision ID: 004
Revises: 003
Create Date: 2025-06-15 00:00:00.000000

This migration adds a composite index on ``study_results`` that covers the
most common query pattern — filtering by ``project_id`` and ordering by
``created_at DESC`` — used by ``list_studies`` and ``GET /projects/{id}/studies``.

Before this index, the query required an in-memory sort because the existing
``ix_study_results_project_id_study_type`` index could not satisfy the
``ORDER BY created_at DESC`` clause.

See: ``api/projects.py`` — ``list_studies()``
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite index ``ix_study_results_project_id_created_at``.

    The index uses ``(project_id, created_at DESC)`` so that the
    ``WHERE project_id = ? ORDER BY created_at DESC`` pattern in
    ``list_studies`` can be served as a single index scan without
    an in-memory sort.
    """
    op.create_index(
        "ix_study_results_project_id_created_at",
        "study_results",
        [sa.text("project_id"), sa.text("created_at DESC")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Drop the composite index."""
    op.drop_index(
        "ix_study_results_project_id_created_at",
        table_name="study_results",
    )
