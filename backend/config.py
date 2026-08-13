"""
backend/config.py — Centralized Configuration for Multi-Database Setup
========================================================

Configuration management for:
- PostgreSQL (primary database)
- Qdrant (vector database)
- Neo4j (graph database)
- Redis (cache/database)
"""

from __future__ import annotations

import os
from typing import Optional

# Load .env file before reading any configuration values.
# This ensures environment variables from .env are available to os.environ.get()
# throughout the Config class and any module that imports config.
# Falls back gracefully if python-dotenv is not installed.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)  # Never override real environment variables
except ImportError:
    pass


def _migrate_deprecated_env_vars() -> None:
    """Migrate FIREAI_* env vars to ETAP_* (one-way, idempotent).

    BACKWARD COMPATIBILITY (v2.x → v3.0 migration):
    Old FIREAI_* env vars are accepted but deprecated.
    They will be removed in v3.0. New code MUST use ETAP_* / ENVIRONMENT.

    This runs at module-import time so all subsequent ``os.environ.get``
    calls (in this module or downstream modules) see the migrated values.
    """
    import warnings

    migrations = [
        ("FIREAI_API_KEY", "ETAP_API_KEY"),
        ("FIREAI_SESSION_SECRET", "ETAP_SESSION_SECRET"),
        ("FIREAI_SESSION_SECRET_FILE", "ETAP_SESSION_SECRET_FILE"),
        ("FIREAI_AUTH_DISABLED", "ENGINEERING_SERVICE_AUTH_DISABLED"),
        ("FIREAI_API_KEY_ROLE", "ETAP_API_KEY_ROLE"),
        ("FIREAI_ALLOWED_UPLOAD_DIRS", "ETAP_ALLOWED_UPLOAD_DIRS"),
        ("FIREAI_EVIDENCE_HMAC_KEY", "ETAP_EVIDENCE_HMAC_KEY"),
        ("FIREAI_MEMORY_LLM_PROVIDER", "ETAP_MEMORY_LLM_PROVIDER"),
        ("FIREAI_MEMORY_LLM_MODEL", "ETAP_MEMORY_LLM_MODEL"),
    ]
    for old, new in migrations:
        if old in os.environ and new not in os.environ:
            warnings.warn(
                f"{old} is deprecated, use {new} instead. "
                f"Will be removed in v3.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            os.environ[new] = os.environ[old]

    # Special: FIREAI_ENV → ENVIRONMENT
    if "FIREAI_ENV" in os.environ and "ENVIRONMENT" not in os.environ:
        warnings.warn(
            "FIREAI_ENV is deprecated, use ENVIRONMENT instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        os.environ["ENVIRONMENT"] = os.environ["FIREAI_ENV"]


# Run migration before any Config class attribute is read.
_migrate_deprecated_env_vars()


class Config:
    """Centralized configuration for all database connections."""

    # PostgreSQL Configuration (Primary Database)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./db/digital_twin.db",  # Default fallback
    )

    # Digital Twin Database Path (for the existing system)
    DIGITAL_TWIN_DB_PATH: str = os.environ.get(
        "DIGITAL_TWIN_DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "digital_twin.db"),
    )

    # Qdrant Configuration (Vector Database)
    QDRANT_HOST: Optional[str] = os.environ.get("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.environ.get("QDRANT_PORT", 6333))
    QDRANT_API_KEY: Optional[str] = os.environ.get("QDRANT_API_KEY")
    QDRANT_URL: Optional[str] = os.environ.get("QDRANT_URL")  # For cloud instances

    # Neo4j Configuration (Graph Database)
    NEO4J_URI: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.environ.get("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.environ.get("NEO4J_DATABASE", "neo4j")

    # Redis Configuration (Cache/Temporary Storage)
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.environ.get("REDIS_PORT", 6379))
    REDIS_PASSWORD: Optional[str] = os.environ.get("REDIS_PASSWORD")
    REDIS_DB: int = int(os.environ.get("REDIS_DB", 0))

    # ── Akamai Edge Integration ────────────────────────────────────────────
    # When AKAMAI_ENABLED=true, the backend trusts Akamai headers
    # (True-Client-IP, Akamai-Internal, Akamai-Bot-Score, Akamai-Geo-Country)
    # and rejects direct origin access in production.
    # See backend/akamai_middleware.py for the full integration.
    AKAMAI_ENABLED: bool = os.environ.get("AKAMAI_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )
    # Shared secret injected by Akamai EdgeWorker / Property Manager.
    # When set, requests without this header are rejected in production.
    AKAMAI_REQUIRE_ORIGIN_TOKEN: str = os.environ.get("AKAMAI_REQUIRE_ORIGIN_TOKEN", "").strip()
    # Comma-separated ISO 3166-1 alpha-2 country codes to block (e.g. "CN,RU,IR,KP")
    AKAMAI_BLOCKED_COUNTRIES: str = os.environ.get("AKAMAI_BLOCKED_COUNTRIES", "")
    # Bot score threshold (0-100, 0=human, 100=bot) for sensitive endpoints.
    # Requests above this score on /api/v1/auth/* are rejected.
    AKAMAI_ALLOWED_BOT_SCORE: int = int(os.environ.get("AKAMAI_ALLOWED_BOT_SCORE", "30"))
    # Forward Akamai's X-RateLimit-* response headers to the client
    AKAMAI_RATE_LIMIT_HEADER: bool = os.environ.get("AKAMAI_RATE_LIMIT_HEADER", "true").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )

    # Security Keys
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    FERNET_ENCRYPTION_KEY: Optional[str] = os.environ.get("FERNET_ENCRYPTION_KEY")

    # SR-010/SR-011: known-insecure sample values. These are public knowledge
    # (committed in docker-compose.yml history and shipped docs) and must
    # never be accepted as real secrets — even when they pass length checks.
    INSECURE_SECRET_VALUES = frozenset(
        {
            "test-secret-32-bytes-long-aaaa-bbbb",
            "etap_dev_api_key_1234567890",
            "etap_redis_pass_change_in_prod",
            "etap_postgres_pass_change_in_prod",
            "super_secret_session_key_minimum_43_characters_long_entropy_12345",
            "gAAAAABk_sample_fernet_key_32bytes_base64_encoded=",
            "neo4j_dev_pass_change_in_prod",
            "qdrant_dev_key_1234567890",
            "admin_grafana_pass_change_in_prod",
        }
    )

    # Additional settings
    # ENVIRONMENT is the canonical env var. FIREAI_ENV is accepted as a
    # deprecated alias for backward compatibility (migrated by
    # _migrate_deprecated_env_vars above).
    ENVIRONMENT: str = os.environ.get(
        "ENVIRONMENT",
        os.environ.get("FIREAI_ENV", "development"),  # deprecated fallback
    )
    DEBUG: bool = ENVIRONMENT.lower() == "development"

    @classmethod
    def validate_config(cls) -> list[str]:
        """Validate configuration and return list of warnings/errors.

        SR-011: in production/staging, an unset, weak (<32 bytes), or
        known-insecure JWT_SECRET_KEY RAISES ValueError (hard fail) instead
        of appending a warning.
        """
        issues = []

        if cls.ENVIRONMENT in ("production", "staging"):
            if not cls.JWT_SECRET_KEY:
                raise ValueError("JWT_SECRET_KEY is not set in production/staging environment")
            if len(cls.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 bytes in production/staging")
            if cls.JWT_SECRET_KEY in cls.INSECURE_SECRET_VALUES:
                raise ValueError("JWT_SECRET_KEY is a known-insecure sample value")

        # Check if PostgreSQL connection string format is valid (if using PostgreSQL)
        if cls.DATABASE_URL.startswith(("postgres://", "postgresql://")):
            if not all(part in cls.DATABASE_URL for part in ["//", "@"]):
                issues.append("DATABASE_URL may have invalid PostgreSQL format")

        # Check if Neo4j has credentials when using remote server
        if not cls.NEO4J_URI.startswith("bolt://localhost") and not cls.NEO4J_PASSWORD:
            issues.append("Neo4j remote connection detected without password")

        return issues


# Singleton instance
config = Config()
