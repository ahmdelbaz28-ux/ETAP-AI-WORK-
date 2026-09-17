"""Add unique constraint to study_versions for project_id and version_number.

Revision ID: 012_add_study_version_unique_constraint
Revises: 011_add_hardening_tables
Create Date: 2026-09-17 00:00:00.000000

Guarantees data integrity and prevents duplicate version numbers for the same project
under concurrent study execution requests.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "012_study_version_unique"
down_revision = "011_add_hardening_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "study_versions" in existing_tables:
        existing_constraints = [
            c.get("name") for c in inspector.get_unique_constraints("study_versions")
        ]
        if "uq_study_version_project_num" not in existing_constraints:
            with op.batch_alter_table("study_versions") as batch_op:
                batch_op.create_unique_constraint(
                    "uq_study_version_project_num",
                    ["project_id", "version_number"],
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "study_versions" in existing_tables:
        existing_constraints = [
            c.get("name") for c in inspector.get_unique_constraints("study_versions")
        ]
        if "uq_study_version_project_num" in existing_constraints:
            with op.batch_alter_table("study_versions") as batch_op:
                batch_op.drop_constraint("uq_study_version_project_num", type_="unique")
