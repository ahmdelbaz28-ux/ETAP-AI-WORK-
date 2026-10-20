"""
api/config_prod.py — Shared production configuration fail-closed validator.

Centralises fail-closed validation for production and staging environments across:
- hf-space/app.py (Hugging Face Spaces entrypoint)
- core/bootstrap.py (Canonical Engineering Service entrypoint)
- api/database.py (Database engine startup validation)

Ensures that in production/staging:
1. Persistent PostgreSQL is configured via DATABASE_URL. Ephemeral SQLite is strictly
   forbidden unless explicitly bypassed via ALLOW_SQLITE_IN_PROD=true.
2. Required security keys (JWT_SECRET_KEY, ENGINEERING_SERVICE_API_KEY/HF_API_KEY)
   are validated when require_auth_keys=True.
3. Missing REDIS_URL logs a CRITICAL operational warning regarding single-replica constraints,
   or raises if DEPLOYMENT_TOPOLOGY is explicitly multi-replica/cluster.
"""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


def validate_production_config(
    require_auth_keys: bool = False,
    default_environment: str = "development",
) -> List[str]:
    """Validate critical environment variables and database requirements for production.

    Parameters
    ----------
    require_auth_keys:
        If True, also validates that JWT_SECRET_KEY and ENGINEERING_SERVICE_API_KEY (or HF_API_KEY)
        are set (used by application-level lifespans such as hf-space/app.py).
        If False, focuses strictly on production database fail-closed enforcement (used by
        core/bootstrap.py and database initialization).
    default_environment:
        Default environment when neither ENVIRONMENT nor ENV is specified. Defaults to
        "development" for local/canonical core services. Callers deploying in production environments
        (such as hf-space/app.py) should pass "production" to prevent fail-open execution.

    Returns
    -------
    List of validated missing variable notices (empty if valid).

    Raises
    ------
    RuntimeError
        If running in production/staging mode with missing mandatory configuration or
        forbidden SQLite database without ALLOW_SQLITE_IN_PROD=true.
    """
    raw_env = os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or default_environment
    env = (raw_env or "development").strip().lower()
    is_prod = env in ("production", "staging", "prod")

    if not is_prod:
        return []

    missing_vars: List[str] = []

    # 1. Database validation (Fail-Closed)
    allow_sqlite = os.getenv("ALLOW_SQLITE_IN_PROD", "").strip().lower() in ("1", "true", "yes")
    db_url = os.environ.get("DATABASE_URL", "").strip()

    if env == "staging" and allow_sqlite:
        missing_vars.append(
            "ALLOW_SQLITE_IN_PROD is strictly forbidden in Staging. Staging requires persistent PostgreSQL."
        )

    if not db_url or db_url.startswith("sqlite"):
        if env == "staging" or not allow_sqlite:
            missing_vars.append(
                f"DATABASE_URL (Persistent PostgreSQL required; SQLite is forbidden in {env}"
                + (" unless ALLOW_SQLITE_IN_PROD=true" if env != "staging" else "")
                + ")"
            )
        else:
            logger.critical(
                "OPERATIONAL ESCAPE HATCH ACTIVE: Running in %s mode with SQLite database because "
                "ALLOW_SQLITE_IN_PROD=true is set. Ephemeral storage warning: data will be lost upon Space rebuild!",
                env,
            )

    # 2. Authentication keys validation (optional per caller)
    if require_auth_keys:
        eng_key = (
            os.environ.get("ENGINEERING_SERVICE_API_KEY", "").strip()
            or os.environ.get("HF_API_KEY", "").strip()
        )
        auth_disabled = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not eng_key and not auth_disabled:
            missing_vars.append("ENGINEERING_SERVICE_API_KEY (or HF_API_KEY)")

        jwt_key = os.environ.get("JWT_SECRET_KEY", "").strip()
        if not jwt_key:
            missing_vars.append("JWT_SECRET_KEY")

    # 3. Redis topology check
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        topo = os.getenv("DEPLOYMENT_TOPOLOGY", "").strip().lower()
        if topo in ("cluster", "multi_replica", "distributed"):
            missing_vars.append(
                f"REDIS_URL (Required for DEPLOYMENT_TOPOLOGY='{topo}' to coordinate rate limits and state across replicas)"
            )
        else:
            logger.critical(
                "PRODUCTION DEPLOYMENT WITHOUT REDIS: Rate limiting will fall back to in-memory! "
                "Operational constraint: must run single-replica pinned (replicas=1) to prevent "
                "multi-instance counter drift and race conditions. Configure REDIS_URL for distributed scale."
            )

    if missing_vars:
        msg = (
            f"FATAL STARTUP ERROR: Running in {env} mode with missing mandatory configuration: "
            + ", ".join(missing_vars)
            + ". Aborting startup (Fail-Closed Security Guard)."
        )
        logger.critical(msg)
        raise RuntimeError(msg)

    return missing_vars
