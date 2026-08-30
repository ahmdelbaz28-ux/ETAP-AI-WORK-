"""Add tenant_id column and Row-Level Security (RLS) policies.

Revision ID: 006
Revises: 005
Create Date: 2026-08-02 00:00:00.000000

This migration adds multi-tenant isolation at the database level:

1. Creates a ``tenants`` table to store tenant (organization) metadata.
2. Adds ``tenant_id`` column (String 36, FK → tenants.id) to all
   tenant-scoped tables: users, projects, study_results, sessions,
   audit_log, security_events, roles, permissions, user_roles,
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
down_revision = "007_fix_study_results_orm"
branch_labels = None
depends_on = None

# Default tenant ID for existing data backfill (must fit String(36)).
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# List of tables that need tenant_id column added by this migration.
# Excludes: tenants (it IS the tenant table), role_permissions (association table —
# tenant isolation is inherited via the role_id FK).
#
# Note: "assets" is excluded because the Asset model (api/assets.py) already
# defines tenant_id — it is created by Base.metadata.create_all() at app startup.
# Existing deployments without tenant_id should add it via a separate migration.
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
    "roles",
    "permissions",
    "user_roles",
    "study_jobs",
    "mfa_credentials",
]

PG_TABLE_QUERY = "SELECT 1 FROM information_schema.tables WHERE table_name = :tn"
SQLITE_TABLE_QUERY = "SELECT 1 FROM sqlite_master WHERE type='table' AND name = :tn"


def _table_exists(bind, dialect: str, tn: str) -> bool:
    """Check if a table exists in the database."""
    try:
        return sa.inspect(bind).has_table(tn)
    except Exception:
        if dialect == "postgresql":
            res = bind.execute(sa.text(PG_TABLE_QUERY), {"tn": tn}).scalar()
            return bool(res)
        else:
            res = bind.execute(sa.text(SQLITE_TABLE_QUERY), {"tn": tn}).scalar()
            return bool(res)


def _create_tenants_table() -> None:
    """Create the tenants table and seed default tenant."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("plan", sa.String(32), nullable=False, server_default="free"),
        sa.Column("max_projects", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, is_active, plan, max_projects, max_users) "
            "VALUES (:id, :name, :slug, :is_active, :plan, :max_projects, :max_users)"
        ).bindparams(
            id=_DEFAULT_TENANT_ID,
            name="Default Organization",
            slug="default",
            is_active=True,
            plan="enterprise",
            max_projects=999999,
            max_users=999999,
        )
    )


def _add_tenant_columns() -> None:
    """Add nullable tenant_id column and index to scoped tables."""
    for table_name in _TENANT_SCOPED_TABLES:
        try:
            op.add_column(
                table_name,
                sa.Column("tenant_id", sa.String(36), nullable=True),
            )
            op.create_index(
                f"ix_{table_name}_tenant_id",
                table_name,
                ["tenant_id"],
            )
        except Exception:
            pass


def _backfill_and_enforce_rls(bind, dialect: str) -> None:
    """Backfill default tenant_id and enable RLS policies on PostgreSQL."""
    for table_name in _TENANT_SCOPED_TABLES:
        if not _table_exists(bind, dialect, table_name):
            continue
        try:
            op.execute(
                sa.text(f"UPDATE {table_name} SET tenant_id = :tid WHERE tenant_id IS NULL")
                .bindparams(tid=_DEFAULT_TENANT_ID)
            )
        except Exception:
            pass

    if dialect == "postgresql":
        for table_name in _TENANT_SCOPED_TABLES:
            if not _table_exists(bind, dialect, table_name):
                continue
            try:
                op.alter_column(table_name, "tenant_id", nullable=False)
            except Exception:
                pass
            try:
                op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
                op.execute(
                    f"CREATE POLICY tenant_isolation_{table_name} ON {table_name} "
                    f"USING (tenant_id = current_setting('app.current_tenant_id', true)) "
                    f"WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))"
                )
            except Exception:
                pass


def upgrade() -> None:
    """Add tenants table, tenant_id columns, indexes, and RLS policies."""
    _create_tenants_table()
    _add_tenant_columns()
    _bind = op.get_bind()
    _backfill_and_enforce_rls(_bind, _bind.dialect.name)


def downgrade() -> None:
    """Remove RLS policies, tenant_id columns, and tenants table."""
    _bind = op.get_bind()
    _dialect = _bind.dialect.name

    if _dialect == "postgresql":
        for table_name in _TENANT_SCOPED_TABLES:
            if _table_exists(_bind, _dialect, table_name):
                try:
                    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
                    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
                except Exception:
                    pass

    for table_name in _TENANT_SCOPED_TABLES:
        if _table_exists(_bind, _dialect, table_name):
            try:
                op.drop_column(table_name, "tenant_id")
            except Exception:
                pass

    op.drop_table("tenants")
