"""
api/database.py — Async SQLAlchemy database configuration.

Supports two backends:
  • PostgreSQL (production)  — asyncpg driver, connection pooling
  • SQLite    (dev / HF)     — aiosqlite driver, single-file

The backend is chosen automatically from DATABASE_URL:
  postgresql://...  → asyncpg  (production)
  sqlite:///...     → aiosqlite (development / HF Space)

Environment variables
---------------------
DATABASE_URL
    Full SQLAlchemy async connection string.
    Default: ``sqlite+aiosqlite:///./data/etap_platform.db``

DB_POOL_SIZE          (PostgreSQL only) — default 10
DB_MAX_OVERFLOW       (PostgreSQL only) — default 20
DB_POOL_TIMEOUT       (PostgreSQL only) — default 30 (seconds)
DB_POOL_RECYCLE       (PostgreSQL only) — default 1800 (seconds)
DB_ECHO               set to "true" to log all SQL statements
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_DB_URL = "sqlite+aiosqlite:///./data/etap_platform.db"

_raw_db_url: str = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)


# Normalise plain postgres:// / postgresql:// → asyncpg driver
def _normalise_url(raw: str) -> str:
    """Convert bare postgres URLs to the correct async driver string."""
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    return raw


try:
    make_url(_raw_db_url)
    DATABASE_URL: str = _normalise_url(_raw_db_url)
except Exception:
    DATABASE_URL = _DEFAULT_DB_URL

_IS_POSTGRES = DATABASE_URL.startswith("postgresql+asyncpg")
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ---------------------------------------------------------------------------
# SQLite parent directory — ensure it exists before engine creation
# ---------------------------------------------------------------------------

if _IS_SQLITE:
    _sqlite_prefix = "sqlite+aiosqlite:///"
    _db_path = DATABASE_URL[len(_sqlite_prefix) :]
    _db_dir = os.path.dirname(_db_path)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Connection pool configuration (PostgreSQL only)
# ---------------------------------------------------------------------------

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))
_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Async engine
# ---------------------------------------------------------------------------

if _IS_POSTGRES:
    engine = create_async_engine(
        DATABASE_URL,
        echo=_ECHO,
        future=True,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_timeout=_POOL_TIMEOUT,
        pool_recycle=_POOL_RECYCLE,
        pool_pre_ping=True,  # detect stale connections
        connect_args={
            "server_settings": {"application_name": "etap-engineering-service"},
        },
    )
    logger.info(
        "PostgreSQL engine created (pool_size=%d, max_overflow=%d)",
        _POOL_SIZE,
        _MAX_OVERFLOW,
    )
else:
    # SQLite — lightweight, no connection pool
    engine = create_async_engine(
        DATABASE_URL,
        echo=_ECHO,
        future=True,
        connect_args={"check_same_thread": False},
    )
    logger.info("SQLite engine created at %s", DATABASE_URL)

# ---------------------------------------------------------------------------
# Async session factory
# ---------------------------------------------------------------------------

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
# Health check helper
# ---------------------------------------------------------------------------


async def check_db_health() -> dict:
    """Ping the database and return a health status dict."""
    try:
        from sqlalchemy import text

        async with async_session() as session:
            if _IS_POSTGRES:
                await session.execute(text("SELECT 1"))
            else:
                await session.execute(text("SELECT 1"))
        return {"status": "healthy", "backend": "postgresql" if _IS_POSTGRES else "sqlite"}
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


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

    # StudyJob table for persistent task queue
    try:
        from core import models as _models  # noqa: F401
    except ImportError:
        pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created/verified successfully")
