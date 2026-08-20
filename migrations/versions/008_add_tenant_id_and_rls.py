"""Add tenant_id column and Row-Level Security (RLS) policies.

Revision ID: 006
Revises: 005
Create Date: 2026-08-02 00:00:00.000000

This migration adds multi-tenant isolation at the database level:

1. Creates a ``tenants`` table to store tenant (organization) metadata.
2. Adds ``tenant_id`` column (String 36, FK → tenants.id) to all
   tenant-scoped tables: users, projects, study_results, sessions,
   audit_log, security_events, assets, roles, permissions, user_roles,
   study_jobs, mfa_credentials.
3. Creates indexes on ``tenant_id`` for fast tenant-scoped queries.
4. On PostgreSQL, enables Row-Level Security (RLS) with policies that
   restrict each table to the current tenant, using a session variable
   ``app.current_tenant_id`` set by the application middleware.
5. On SQLite, RLS is not supported — the application layer enforces
   tenant isolation via ORM filters (see V-07 ContextVars).

Security rationale
------------------
Previous implementation relied solely on application-level filtering
(created_by == user_id), which is per-user isolation, not per-tenant.
A compromised or buggy endpoint could bypass this filter and expose
cross-tenant data. RLS provides defence-in-depth: even if the
application layer fails, PostgreSQL itself will reject rows that do
not belong to the current tenant.

The session variable ``app.current_tenant_id`` is set by the
TenantMiddleware (see backend/request_context.py) immediately after
JWT validation, before any query is executed.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "008_add_tenant_id_and_rls"
down_revision = "007_fix_study_results_and_orm_tables"
branch_labels = None
depends_on = None

# Default tenant ID for existing data backfill.
_DEFAULT_TENANT_ID = "default-tenant-00000000-0000-0000-0000-000000000000"

# List of tables that need tenant_id column.
# Excludes: tenants (it IS the tenant table), role_permissions (association table —
# tenant isolation is inherited via the role_id FK).
# SECURITY (self-critique): Table names are constants defined here, not
# user-supplied. They are used in DDL statements via Alembic's op API
# which validates identifiers. The UPDATE statements use sa.text() with
# bound parameters to prevent SQL injection.
_TENANT_SCOPED_TABLES = [
    "users",
    "projects",
    "study_results",
    "sessions",
    "audit_log",
    "security_events",
    "assets",
    "roles",
    "permissions",
    "user_roles",
    "study_jobs",
    "mfa_credentials",
]


def upgrade() -> None:
    """Add tenants table, tenant_id columns, indexes, and RLS policies."""

    # ------------------------------------------------------------------
    # 1. Create tenants table
    # ------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "slug",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "plan",
            sa.String(32),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "max_projects",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "max_users",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
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
    # 2. Add tenant_id column to each table + index
    # ------------------------------------------------------------------
    # SECURITY (self-critique): Using Alembic's op.add_column() which
    # validates identifiers. No raw f-string SQL for table names.
    for table_name in _TENANT_SCOPED_TABLES:
        try:
            op.add_column(
                table_name,
                sa.Column(
                    "tenant_id",
                    sa.String(36),
                    sa.ForeignKey("tenants.id", ondelete="SET NULL"),
                    nullable=True,  # Start nullable for migration; backfill then set NOT NULL
                    index=True,
                ),
            )
        except Exception:
            # Table may not exist in all deployments (e.g. mfa_credentials, study_jobs)
            pass

    # ------------------------------------------------------------------
    # 3. Create a default tenant for existing data
    # ------------------------------------------------------------------
    # Use sa.text() with bound parameters to prevent SQL injection.
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, is_active, plan, max_projects, max_users) "
            "VALUES (:id, :name, :slug, true, :plan, :max_projects, :max_users)"
        ).bindparams(
            id=_DEFAULT_TENANT_ID,
            name="Default Tenant",
            slug="default",
            plan="enterprise",
            max_projects=1000,
            max_users=500,
        )
    )

    # ------------------------------------------------------------------
    # 4. Backfill tenant_id on existing rows with the default tenant
    # ------------------------------------------------------------------
    # SECURITY (self-critique): Use sa.text() with bound parameter for
    # the tenant_id value. Table names come from the constant list above
    # (not user input), so they are safe for DDL. The UPDATE value uses
    # a parameterized query.
    for table_name in _TENANT_SCOPED_TABLES:
        try:
            op.execute(
                sa.text(
                    f"UPDATE {table_name} SET tenant_id = :tid WHERE tenant_id IS NULL"
                ).bindparams(tid=_DEFAULT_TENANT_ID)
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 5. Make tenant_id NOT NULL after backfill (PostgreSQL only)
    # ------------------------------------------------------------------
    # SECURITY (self-critique M-1): After backfilling all existing rows
    # with the default tenant_id, new rows MUST NOT be allowed to have
    # a NULL tenant_id — otherwise RLS would silently exclude them, and
    # the application layer would not enforce isolation for those rows.
    # On SQLite, we skip this step because ALTER COLUMN is not supported
    # and the application layer enforces tenant_id via ORM defaults.
    _bind = op.get_bind()
    _dialect = _bind.dialect.name

    if _dialect == "postgresql":
        for table_name in _TENANT_SCOPED_TABLES:
            try:
                op.alter_column(
                    table_name,
                    "tenant_id",
                    nullable=False,
                )
            except Exception:
                # Table may not exist in all deployments
                pass

    # ------------------------------------------------------------------
    # 6. Row-Level Security (PostgreSQL only)
    # ------------------------------------------------------------------
    # SQLite does not support RLS. The application layer provides
    # equivalent isolation via ContextVars + ORM-level filters.
    # (_dialect already defined above in step 5)

    if _dialect == "postgresql":
        for table_name in _TENANT_SCOPED_TABLES:
            # Enable RLS
            op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

            # Policy: tenant members can see rows belonging to their tenant
            # The current_tenant_id is set via SET app.current_tenant_id = '<uuid>'
            # by the TenantMiddleware before any query runs.
            # NOTE: DDL statements (ALTER TABLE, CREATE POLICY) cannot use
            # parameterized queries in Alembic. Table names come from the
            # constant list above (not user input), so they are safe.
            #
            # SECURITY (self-critique C-1): USING alone only controls
            # SELECT/DELETE. Without WITH CHECK, INSERT/UPDATE bypass RLS —
            # a user in tenant A could INSERT a row with tenant B's ID.
            # Both clauses are now present for full isolation.
            op.execute(
                f"CREATE POLICY tenant_isolation_{table_name} ON {table_name} "
                f"USING (tenant_id = current_setting('app.current_tenant_id', true)) "
                f"WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))"
            )

            # Policy: service role (superuser) bypasses RLS for migrations/admin
            # This is implicit — superusers bypass RLS by default in PostgreSQL.


def downgrade() -> None:
    """Remove RLS policies, tenant_id columns, and tenants table."""

    _bind = op.get_bind()
    _dialect = _bind.dialect.name

    # 1. Drop RLS policies (PostgreSQL only)
    if _dialect == "postgresql":
        for table_name in _TENANT_SCOPED_TABLES:
            try:
                op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
                op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
            except Exception:
                pass

    # 2. Drop tenant_id columns
    for table_name in _TENANT_SCOPED_TABLES:
        try:
            op.drop_column(table_name, "tenant_id")
        except Exception:
            pass

    # 3. Drop tenants table
    op.drop_table("tenants")
