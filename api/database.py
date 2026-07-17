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

import contextlib
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
    logger.warning(
        "Using SQLite database (%s). "
        "This is suitable for local development but NOT for production. "
        "On HF Space with multiple replicas, each replica has its own "
        "SQLite file — data created on one replica is invisible to others. "
        "Set DATABASE_URL to a shared PostgreSQL instance in production.",
        _db_path,
    )
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

def _build_postgres_engine(url: str):
    """Create an async PostgreSQL engine with sensible pool defaults."""
    return create_async_engine(
        url,
        echo=_ECHO,
        future=True,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_timeout=_POOL_TIMEOUT,
        pool_recycle=_POOL_RECYCLE,
        pool_pre_ping=True,  # detect stale connections
        connect_args={
            "server_settings": {"application_name": "etap-engineering-service"},
            # Hard timeout for the initial TCP+TLS+auth handshake.
            # Without this, a dead/paused Supabase project causes the
            # register/login endpoints to hang for the default 60s before
            # returning 500 — far too long for a usable UX.
            "timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        },
    )


def _build_sqlite_engine(url: str):
    """Create an async SQLite engine (no connection pool)."""
    return create_async_engine(
        url,
        echo=_ECHO,
        future=True,
        connect_args={"check_same_thread": False},
    )


# Fallback SQLite URL used when the primary Postgres instance is unreachable.
# Lives under /tmp so it is writable on HF Spaces and other container runtimes.
_FALLBACK_SQLITE_URL = "sqlite+aiosqlite:////tmp/data/etap_platform_fallback.db"

# Whether we have permanently fallen back to SQLite during this process.
# Mutated by init_db() if the primary engine cannot reach its database.
_FELL_BACK_TO_SQLITE: bool = False


if _IS_POSTGRES:
    engine = _build_postgres_engine(DATABASE_URL)
    logger.info(
        "PostgreSQL engine created (pool_size=%d, max_overflow=%d)",
        _POOL_SIZE,
        _MAX_OVERFLOW,
    )
else:
    engine = _build_sqlite_engine(DATABASE_URL)
    logger.info("SQLite engine created at %s", DATABASE_URL)

# ---------------------------------------------------------------------------
# Async session factory
# ---------------------------------------------------------------------------

# NOTE: async_session binds to the *current* engine at call time via the
# global below. When init_db() falls back from Postgres to SQLite, we
# re-bind async_session so subsequent requests use the working engine.
# This indirection is required because async_sessionmaker captures the
# engine reference at construction time.

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _rebind_session(new_engine) -> None:
    """Re-create the async_session factory bound to *new_engine*.

    Called when init_db() falls back from Postgres to SQLite so that
    subsequent get_db() calls use the working engine.
    """
    global async_session, engine, _FELL_BACK_TO_SQLITE
    engine = new_engine
    async_session = async_sessionmaker(
        new_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    _FELL_BACK_TO_SQLITE = True


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
            # "SELECT 1" works on both PostgreSQL and SQLite — no need to
            # branch on _IS_POSTGRES. (SonarCloud S3923 flagged the
            # identical-branches if/else as redundant.)
            await session.execute(text("SELECT 1"))
        backend = "sqlite-fallback" if _FELL_BACK_TO_SQLITE else ("postgresql" if _IS_POSTGRES else "sqlite")  # NOSONAR
        return {
            "status": "healthy" if not _FELL_BACK_TO_SQLITE else "degraded",
            "backend": backend,
            "fallback_active": _FELL_BACK_TO_SQLITE,
        }
    except Exception as exc:
        logger.exception("Database health check failed: %s", exc)
        return {"status": "unhealthy", "error": "Database connection failed"}


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

    If the primary engine targets PostgreSQL but the database is
    unreachable (e.g. Supabase project paused, network partition, wrong
    credentials), this function automatically falls back to a local
    SQLite file under ``/tmp/data/etap_platform_fallback.db`` so the
    platform stays operational in a degraded mode. A loud warning is
    logged so operators know to fix the Postgres connection.

    Example::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await init_db()
            yield

        app = FastAPI(lifespan=lifespan)
    """
    # Import all ORM models so Base.metadata knows about their tables.
    # This MUST happen before create_all is called.
    import api.assets  # noqa: F401  — registers Asset model
    import api.auth  # noqa: F401  — registers User model
    import api.projects  # noqa: F401  — registers Project & StudyResult models
    import api.rbac  # noqa: F401  — registers Role, Permission, UserRole models

    # StudyJob table for persistent task queue — optional import (core.models
    # may not be available in stripped-down deployments).
    with contextlib.suppress(ImportError):
        from core import models as _models  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified successfully")
        return
    except Exception as exc:
        if not _IS_POSTGRES:
            # SQLite has no fallback — re-raise so callers know.
            raise
        logger.exception(
            "Primary PostgreSQL database unreachable: %s. "
            "Falling back to local SQLite at %s. The platform will run "
            "in DEGRADED MODE: data will NOT persist across container "
            "restarts. Fix DATABASE_URL (e.g. resume the Supabase project) "
            "and restart the Space to restore production-grade storage.",
            exc,
            _FALLBACK_SQLITE_URL,
        )

    # Fall back to SQLite — make sure /tmp/data exists, then rebind.
    _fallback_dir = os.path.dirname(_FALLBACK_SQLITE_URL.replace("sqlite+aiosqlite:///", ""))
    if _fallback_dir:
        os.makedirs(_fallback_dir, exist_ok=True)
    fallback_engine = _build_sqlite_engine(_FALLBACK_SQLITE_URL)
    _rebind_session(fallback_engine)
    async with fallback_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.warning(
        "Fallback SQLite engine bound. Subsequent DB operations will use %s",
        _FALLBACK_SQLITE_URL,
    )
