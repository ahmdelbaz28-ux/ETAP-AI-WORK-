"""
api/database.py — Async SQLAlchemy database configuration.

Provides the async engine, session factory, declarative base, and a
convenience ``init_db`` helper used by the FastAPI application at startup.

The database path is controlled via the ``DATABASE_URL`` environment variable
and defaults to an aiosqlite-backed file at ``./data/etap_platform.db``.

If ``DATABASE_URL`` is set but is not a valid SQLAlchemy connection string
(e.g. a ``file:`` URL intended for another system), the module falls back
to the default aiosqlite path so that importing never raises.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_DB_URL = "sqlite+aiosqlite:///./data/etap_platform.db"

_raw_db_url: str = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

# If the env var contains a non-SQLAlchemy URL (e.g. "file:/...") fall back
# to the default.  Valid SQLAlchemy URLs contain a driver scheme followed by
# a colon (e.g. "sqlite+aiosqlite:", "postgresql:").
try:
    make_url(_raw_db_url)
    DATABASE_URL: str = _raw_db_url
except Exception:
    DATABASE_URL = _DEFAULT_DB_URL

# Ensure the parent directory for the SQLite file exists before the engine
# attempts to open it.
_sqlite_file_prefix = "sqlite+aiosqlite:///"
if DATABASE_URL.startswith(_sqlite_file_prefix):
    _db_path = DATABASE_URL[len(_sqlite_file_prefix) :]
    _db_dir = os.path.dirname(_db_path)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Async engine & session
# ---------------------------------------------------------------------------

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    # SQLite-specific: allow multi-threaded access via check_same_thread=False
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all ORM models.

    All mapped classes should inherit from ``Base`` so that
    ``init_db`` can create their tables automatically.
    """


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically closed when the request finishes, even
    if an exception is raised inside the route handler.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables that do not yet exist in the database.

    This should be called once during application startup, e.g. inside a
    FastAPI lifespan handler.

    All ORM models are imported inside this function so that
    ``Base.metadata`` is aware of every mapped table before
    ``create_all`` is called.

    Example::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await init_db()
            yield

        app = FastAPI(lifespan=lifespan)
    """
    # Import all ORM models so Base.metadata knows about their tables.
    # This MUST happen before create_all is called.
    import api.auth  # noqa: F401  — registers User model
    import api.projects  # noqa: F401  — registers Project & StudyResult models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
