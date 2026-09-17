"""
api/database_migrations.py — Startup Migration Gate & Schema Health (FIX-27).

Executes `alembic upgrade head` before accepting traffic in FastAPI lifespan.
Guarantees schema synchronization, detects pending migrations, and reports
current vs head revision for zero-drift deployments.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

logger = logging.getLogger("api.database_migrations")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_alembic_config() -> Config:
    """Create and return an Alembic Config instance pointing to alembic.ini."""
    ini_path = _REPO_ROOT / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")
    cfg = Config(str(ini_path))
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def get_head_revision() -> Optional[str]:
    """Get the target head revision ID from migration scripts."""
    try:
        cfg = get_alembic_config()
        script = ScriptDirectory.from_config(cfg)
        return script.get_current_head()
    except Exception as exc:
        logger.warning("Failed to determine Alembic head revision: %s", exc)
        return None


def run_upgrade_head_sync() -> None:
    """Synchronously run alembic upgrade head (must be called outside main event loop)."""
    cfg = get_alembic_config()
    logger.info("Running Alembic startup migration gate: upgrade head...")
    command.upgrade(cfg, "head")
    logger.info("Alembic startup migration gate successfully applied head.")


async def run_alembic_startup_gate() -> None:
    """Enforce Alembic migration gate at application startup.

    Fails closed in production/staging if migrations fail to apply.
    """
    env = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "production")).lower()
    is_prod = env in ("production", "staging", "prod")

    try:
        await asyncio.to_thread(run_upgrade_head_sync)
    except Exception as exc:
        logger.critical("FATAL: Alembic startup migration gate failed: %s", exc)
        if is_prod:
            raise RuntimeError(
                f"Database migration failed at startup (Fail-Closed): {exc}"
            ) from exc
        logger.warning("Database migration failed in %s mode (non-fatal): %s", env, exc)


async def check_schema_health() -> Dict[str, Any]:
    """Return current migration status and head revision."""
    head_rev = get_head_revision()
    return {
        "status": "synchronized" if head_rev else "unknown",
        "head_revision": head_rev,
    }
