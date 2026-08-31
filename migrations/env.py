"""
migrations/env.py — Alembic environment configuration for async migrations.

This module configures Alembic to run migrations asynchronously using
``aiosqlite`` as the SQLite driver.  It is designed to work with the
AhmedETAP Engineering Platform's async SQLAlchemy 2.0 stack.

Key features:
* Asynchronous migration execution via ``run_async_migrations``
* Automatic detection of ORM models from ``api.database.Base.metadata``
* SQLite-compatible migration configuration (e.g., ``render_as_batch=True``)
* Support for both online (connected) and offline (SQL-script) migration modes
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Ensure the project root is on ``sys.path`` so that imports like
# ``api.database`` resolve correctly regardless of the working directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in ``alembic.ini``.
# ---------------------------------------------------------------------------
config = context.config

# ---------------------------------------------------------------------------
# Interpret the config file for Python logging.  This line sets up loggers
# according to the ``[loggers]``, ``[handlers]`` and ``[formatters]``
# sections in ``alembic.ini``.
# ---------------------------------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import the shared declarative base so that ``autogenerate`` can detect
# model changes.  This must happen *after* the project root is on the path.
# ---------------------------------------------------------------------------
from api.database import Base  # noqa: E402

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override the ``sqlalchemy.url`` from ``alembic.ini`` with the value from
# the ``DATABASE_URL`` environment variable, if set.  This allows the same
# ``alembic.ini`` to be used across environments (dev / CI / prod) without
# modification.
#
# If ``DATABASE_URL`` contains a non-SQLAlchemy URL (e.g. a ``file:`` URL
# intended for another system), we fall back to the default aiosqlite path
# so that the migration environment never fails to start.
# ---------------------------------------------------------------------------
_DEFAULT_DB_URL = "sqlite+aiosqlite:///./data/etap_platform.db"
_raw_db_url: str = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

try:
    make_url(_raw_db_url)
    _database_url: str = _raw_db_url
except Exception:
    _database_url = _DEFAULT_DB_URL

config.set_main_option("sqlalchemy.url", _database_url)


# ---------------------------------------------------------------------------
# Online migration — async engine
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine.

    In this mode the engine is connected to the database and migrations
    are executed within a real transaction.  The actual migration work
    is delegated to :func:`_run_async`, which is scheduled on the
    event loop via ``asyncio.run``.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    asyncio.run(_run_async(connectable))


async def _run_async(connectable) -> None:
    """Coroutine that acquires a connection and runs migrations.

    Args:
        connectable: An :class:`~sqlalchemy.ext.asyncio.AsyncEngine` instance.
    """
    async with connectable.connect() as connection:
        await connection.run_sync(
            _do_run_migrations,
        )

    await connectable.dispose()


def _do_run_migrations(connection: Connection) -> None:
    """Synchronous callback executed inside ``run_sync``.

    This is where Alembic's ``MigrationContext`` and ``Operations`` are
    actually instantiated and the migration scripts are applied.

    Args:
        connection: A synchronous :class:`~sqlalchemy.engine.Connection`
            obtained from the async engine via ``run_sync``.
    """
    # Detect backend — SQLite needs batch mode (no ALTER TABLE); Postgres
    # supports ALTER natively and batch mode would be unnecessary overhead.
    _is_sqlite = _database_url.startswith("sqlite")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite does not support ALTER TABLE directly; Alembic's batch
        # mode recreates the table behind the scenes when ALTER is needed.
        # For PostgreSQL we disable batch mode (it's unnecessary and slower).
        render_as_batch=_is_sqlite,
        # Compare types so that column-type changes are detected by
        # ``autogenerate``.
        compare_type=True,
        # Compare server defaults so that default-value changes are
        # detected by ``autogenerate``.
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Offline migration — SQL script generation
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an engine.  Calls
    to ``context.execute()`` emit the given string to the script output.
    The generated SQL script can be reviewed before being applied to a
    production database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
