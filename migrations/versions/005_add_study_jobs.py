"""Add study_jobs table for persistent task queue.

Revision ID: 005
Revises: 004
Create Date: 2026-06-25 00:00:00.000000

Why this migration exists
--------------------------
The ``ChiefEngineeringOrchestrator`` previously stored its task queue in
process-local Python lists (``task_queue`` and ``completed_tasks``).

On any pod restart or horizontal scale-out event all queued or in-flight
engineering studies were silently discarded — no error was raised and no
client was notified.

This migration introduces the ``study_jobs`` table which provides:

* Durable task queue — tasks survive restarts.
* Status tracking — PENDING, QUEUED, RUNNING, COMPLETED, FAILED.
* Celery task association — links to Celery ``AsyncResult`` via ``celery_task_id``.
* Result storage — raw JSON result stored on completion.
* Retry support — ``attempt`` counter + ``max_attempts``.
* Full audit trail — ``created_at``, ``started_at``, ``completed_at``.
* Multi-tenant support — ``created_by`` links to the ``users`` table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the ``study_jobs`` table and its indexes."""
    op.create_table(
        "study_jobs",
        # Primary key
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # Study identity
        sa.Column("study_type", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        # Status lifecycle
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        # Payload (request body stored as JSON)
        sa.Column("payload", sa.Text(), nullable=True),
        # Celery integration
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        # Result storage
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        # Retry tracking
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Ownership
        sa.Column("created_by", sa.String(36), nullable=False, server_default="system"),
        # Worker routing
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
    )

    # Index for polling pending jobs
    op.create_index(
        "ix_study_jobs_status_created_at",
        "study_jobs",
        ["status", sa.text("created_at ASC")],
    )

    # Index for fast project-scoped queries
    op.create_index(
        "ix_study_jobs_project_id",
        "study_jobs",
        ["project_id"],
    )

    # Index for Celery task lookups
    op.create_index(
        "ix_study_jobs_celery_task_id",
        "study_jobs",
        ["celery_task_id"],
    )

    # Index for user-scoped queries
    op.create_index(
        "ix_study_jobs_created_by",
        "study_jobs",
        ["created_by"],
    )


def downgrade() -> None:
    """Drop the ``study_jobs`` table and all its indexes."""
    op.drop_index("ix_study_jobs_created_by", table_name="study_jobs")
    op.drop_index("ix_study_jobs_celery_task_id", table_name="study_jobs")
    op.drop_index("ix_study_jobs_project_id", table_name="study_jobs")
    op.drop_index("ix_study_jobs_status_created_at", table_name="study_jobs")
    op.drop_table("study_jobs")
