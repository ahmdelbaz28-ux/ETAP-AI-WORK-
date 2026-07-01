"""Initial schema — core platform tables.

Revision ID: 001
Revises: —
Create Date: 2025-01-01 00:00:00.000000

This migration creates the foundational tables for the AhmedETAP Engineering
Platform:

* **users** — Authentication and role-based access control
* **projects** — Power-system project storage with full system configuration
* **study_results** — Persisted output from power-system study runs
* **sessions** — JWT refresh-token sessions for authenticated users
* **audit_log** — Tamper-evident audit trail for compliance
* **security_events** — Security monitoring and incident tracking

All tables use UUID string primary keys (36-char) and are designed for
async SQLite (aiosqlite) compatibility.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all initial platform tables."""

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "username",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "password_hash",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "reset_token",
            sa.String(128),
            nullable=True,
        ),
        sa.Column(
            "reset_token_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_login",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "description",
            Text(),
            nullable=True,
        ),
        sa.Column(
            "system_config",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # study_results
    # ------------------------------------------------------------------
    op.create_table(
        "study_results",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "study_type",
            sa.String(64),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parameters",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "result_data",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "errors",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "execution_time_sec",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.String(64),
            nullable=False,
            server_default="native",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="completed",
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "token_hash",
            sa.String(128),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "refresh_token_hash",
            sa.String(128),
            unique=True,
            index=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "action",
            sa.String(128),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "resource_type",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            sa.String(36),
            nullable=True,
        ),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )

    # ------------------------------------------------------------------
    # security_events
    # ------------------------------------------------------------------
    op.create_table(
        "security_events",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "event_type",
            sa.String(64),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "severity",
            sa.String(32),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Drop all initial platform tables in reverse dependency order."""

    op.drop_table("security_events")
    op.drop_table("audit_log")
    op.drop_table("sessions")
    op.drop_table("study_results")
    op.drop_table("projects")
    op.drop_table("users")
