"""Make acceleration_factor nullable in project_solver_parameters.

Revision ID: 013_solver_accel_nullable
Revises: 012_study_version_unique
Create Date: 2026-09-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_solver_accel_nullable"
down_revision = "012_study_version_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "project_solver_parameters" in existing_tables:
        with op.batch_alter_table("project_solver_parameters") as batch_op:
            batch_op.alter_column(
                "acceleration_factor",
                existing_type=sa.Float(),
                nullable=True,
                server_default="1.6",
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "project_solver_parameters" in existing_tables:
        with op.batch_alter_table("project_solver_parameters") as batch_op:
            batch_op.alter_column(
                "acceleration_factor",
                existing_type=sa.Float(),
                nullable=False,
                server_default="1.6",
            )
