"""
api/staging_guard.py — Staging Database and Environment Identity Guards.

Validates that Staging database targets are strictly isolated from production,
persistent PostgreSQL (no SQLite), non-ambiguous, and match the dedicated
Staging project reference without printing credentials or secrets.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import NamedTuple
from urllib.parse import unquote, urlparse

logger = logging.getLogger("api.staging_guard")

PROD_SUPABASE_PROJECT_REF = "kuqwgxzkscqqftcrcuqe"
DEFAULT_STAGING_PROJECT_REF = "guunodspzhcxpmdwwyjv"


class DatabaseTargetInfo(NamedTuple):
    scheme: str
    host: str | None
    port: int | None
    database: str | None
    project_ref: str | None
    is_staging: bool


class StagingGuardError(ValueError):
    """Raised when database or staging environment configuration fails validation."""


def extract_project_ref(parsed_url) -> str | None:
    """Extract Supabase project reference from username or hostname without credentials."""
    # 1. From hostname: db.<ref>.supabase.co or <ref>.supabase.co
    host = (parsed_url.hostname or "").lower()
    m_host = re.match(r"^(?:db\.)?([a-z0-9]{20})\.supabase\.co$", host)
    if m_host:
        return m_host.group(1)

    # 2. From username in pooler URL: postgres.<ref> or <user>.<ref>
    username = parsed_url.username or ""
    if username:
        unquoted_user = unquote(username)
        if "." in unquoted_user:
            ref_part = unquoted_user.split(".", 1)[1]
            if re.match(r"^[a-z0-9]{20}$", ref_part):
                return ref_part

    return None


def parse_and_validate_staging_db_url(
    db_url: str | None,
    expected_staging_ref: str = DEFAULT_STAGING_PROJECT_REF,
    prod_ref: str = PROD_SUPABASE_PROJECT_REF,
) -> DatabaseTargetInfo:
    """Validate that the given database URL is a valid, isolated Staging PostgreSQL database.

    Guards:
    1. Rejects missing or empty database URL.
    2. Rejects SQLite (schemes starting with sqlite).
    3. Rejects invalid/malformed database URLs.
    4. Extracts project reference from username or hostname.
    5. Rejects any database URL targeting the production project reference.
    6. Verifies that the URL matches the expected staging project reference (fail-closed if ambiguous).
    7. Never logs or prints passwords or credentials.
    """
    if not db_url or not str(db_url).strip():
        raise StagingGuardError("Missing database configuration: database URL is not set.")

    cleaned_url = str(db_url).strip()

    # Pre-parse check for SQLite
    lower_url = cleaned_url.lower()
    if lower_url.startswith("sqlite") or "sqlite" in lower_url.split("://")[0]:
        raise StagingGuardError(
            "SQLite is strictly forbidden in Staging. A persistent PostgreSQL database is required."
        )

    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise StagingGuardError(f"Malformed database URL: unparseable connection string ({type(exc).__name__}).") from exc

    scheme = (parsed.scheme or "").lower()
    valid_pg_schemes = (
        "postgresql",
        "postgres",
        "postgresql+asyncpg",
        "postgresql+psycopg2",
        "postgresql+pg8000",
    )
    if scheme not in valid_pg_schemes:
        raise StagingGuardError(
            f"Unsupported database scheme '{scheme}'. Staging strictly requires persistent PostgreSQL."
        )

    if not parsed.hostname:
        raise StagingGuardError("Malformed database URL: missing hostname in connection string.")

    project_ref = extract_project_ref(parsed)

    # Reject known production project reference
    if project_ref == prod_ref or prod_ref in cleaned_url:
        raise StagingGuardError(
            "CRITICAL: Database connection targets production Supabase instance! Aborting (Fail-Closed)."
        )

    # Check for expected staging project reference
    if not project_ref:
        raise StagingGuardError(
            "Ambiguous database identity: could not verify independent Staging Supabase project reference."
        )

    if project_ref != expected_staging_ref:
        raise StagingGuardError(
            f"Ambiguous database identity: target project ref '{project_ref[:4]}...{project_ref[-4:]}' "
            f"does not match expected staging reference '{expected_staging_ref[:4]}...{expected_staging_ref[-4:]}'."
        )

    db_name = (parsed.path or "").lstrip("/") or None

    return DatabaseTargetInfo(
        scheme=scheme,
        host=parsed.hostname,
        port=parsed.port,
        database=db_name,
        project_ref=project_ref,
        is_staging=True,
    )


def validate_staging_runtime_env() -> None:
    """Validate that the active runtime environment does not permit SQLite fallback."""
    allow_sqlite = os.getenv("ALLOW_SQLITE_IN_PROD", "").strip().lower()
    if allow_sqlite in ("1", "true", "yes"):
        raise StagingGuardError(
            "CRITICAL: ALLOW_SQLITE_IN_PROD is enabled in Staging! SQLite is strictly forbidden."
        )


def main() -> int:
    """CLI entrypoint for CI and pre-deployment verification."""
    validate_staging_runtime_env()
    db_url = os.getenv("STAGING_DATABASE_URL") or os.getenv("DATABASE_URL")
    try:
        info = parse_and_validate_staging_db_url(db_url)
        # Safe logging with ZERO secrets
        ref_masked = f"{info.project_ref[:4]}...{info.project_ref[-4:]}" if info.project_ref else "unknown"
        print(
            f"Staging PostgreSQL database verified successfully: host={info.host}, "
            f"port={info.port}, db={info.database}, project_ref={ref_masked} (isolated from production)."
        )
        return 0
    except StagingGuardError as err:
        print(f"::error::{err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
