"""
tests/test_staging_db_guards.py — Automated Unit Tests for Staging Database Guards.

Covers Gate 2 requirements:
- Valid Staging identity (Pooler & Direct URL formats)
- Rejection of SQLite schemes
- Rejection of missing/empty database configuration
- Rejection of production identity collision (Pooler & Direct URL formats)
- Rejection of malformed URLs
- Rejection of ambiguous/unverified project references
- Rejection of ALLOW_SQLITE_IN_PROD in Staging runtime
- Non-exposure of credentials in error messages
"""

import re
from pathlib import Path

import pytest

from api.staging_guard import (
    DEFAULT_STAGING_PROJECT_REF,
    PROD_SUPABASE_PROJECT_REF,
    DatabaseTargetInfo,
    StagingGuardError,
    extract_project_ref,
    parse_and_validate_staging_db_url,
    validate_staging_runtime_env,
)


class TestStagingDatabaseGuards:
    """Test suite verifying Staging database isolation and validation rules."""

    def test_valid_staging_pooler_url(self):
        """Pooler URL with postgres.<staging_ref> username must be accepted."""
        url = (
            f"postgresql+asyncpg://postgres.{DEFAULT_STAGING_PROJECT_REF}:secretpassword"
            "@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?ssl=require"
        )
        info = parse_and_validate_staging_db_url(url)
        assert isinstance(info, DatabaseTargetInfo)
        assert info.scheme == "postgresql+asyncpg"
        assert info.host == "aws-1-eu-central-1.pooler.supabase.com"
        assert info.port == 5432
        assert info.database == "postgres"
        assert info.project_ref == DEFAULT_STAGING_PROJECT_REF
        assert info.is_staging is True

    def test_valid_staging_direct_url(self):
        """Direct connection URL db.<staging_ref>.supabase.co must be accepted."""
        url = (
            f"postgresql://postgres:secretpassword"
            f"@db.{DEFAULT_STAGING_PROJECT_REF}.supabase.co:5432/postgres"
        )
        info = parse_and_validate_staging_db_url(url)
        assert info.project_ref == DEFAULT_STAGING_PROJECT_REF
        assert info.host == f"db.{DEFAULT_STAGING_PROJECT_REF}.supabase.co"
        assert info.is_staging is True

    def test_reject_sqlite_plain(self):
        """sqlite:/// must be rejected."""
        with pytest.raises(StagingGuardError, match="SQLite is strictly forbidden"):
            parse_and_validate_staging_db_url("sqlite:///data/test.db")

    def test_reject_sqlite_async(self):
        """sqlite+aiosqlite:/// must be rejected."""
        with pytest.raises(StagingGuardError, match="SQLite is strictly forbidden"):
            parse_and_validate_staging_db_url("sqlite+aiosqlite:////tmp/data/etap.db")

    def test_reject_missing_configuration_none(self):
        """None must be rejected as missing configuration."""
        with pytest.raises(StagingGuardError, match="Missing database configuration"):
            parse_and_validate_staging_db_url(None)

    def test_reject_missing_configuration_empty(self):
        """Empty string must be rejected."""
        with pytest.raises(StagingGuardError, match="Missing database configuration"):
            parse_and_validate_staging_db_url("   ")

    def test_reject_production_pooler_collision(self):
        """Pooler URL with production project ref must fail closed."""
        prod_url = (
            f"postgresql+asyncpg://postgres.{PROD_SUPABASE_PROJECT_REF}:supersecret"
            "@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
        )
        with pytest.raises(StagingGuardError, match="targets production Supabase instance"):
            parse_and_validate_staging_db_url(prod_url)

    def test_reject_production_direct_collision(self):
        """Direct URL with production project ref must fail closed."""
        prod_url = (
            f"postgresql://postgres:supersecret"
            f"@db.{PROD_SUPABASE_PROJECT_REF}.supabase.co:5432/postgres"
        )
        with pytest.raises(StagingGuardError, match="targets production Supabase instance"):
            parse_and_validate_staging_db_url(prod_url)

    def test_reject_malformed_url_no_host(self):
        """URL missing hostname must be rejected as malformed."""
        with pytest.raises(StagingGuardError, match="missing hostname"):
            parse_and_validate_staging_db_url("postgresql://")

    def test_reject_unsupported_scheme(self):
        """Non-PostgreSQL schemes must be rejected."""
        with pytest.raises(StagingGuardError, match="Unsupported database scheme"):
            parse_and_validate_staging_db_url("mysql://root:pass@localhost:3306/db")

    def test_reject_ambiguous_generic_host(self):
        """Generic host without valid staging project ref must fail closed."""
        with pytest.raises(StagingGuardError, match="Ambiguous database identity"):
            parse_and_validate_staging_db_url("postgresql://postgres:pass@localhost:5432/mydb")

    def test_reject_unknown_project_ref(self):
        """Unknown 20-char project ref must fail closed against expected staging ref."""
        unknown_ref = "abcdefghijklmnopqrst"
        url = f"postgresql+asyncpg://postgres.{unknown_ref}:pass@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
        with pytest.raises(StagingGuardError, match="does not match expected staging reference"):
            parse_and_validate_staging_db_url(url)

    def test_no_credential_leak_in_error_message(self):
        """Error messages must never include the password."""
        super_secret_pw = "UltraSecretPassword99812!"
        url = f"postgresql+asyncpg://postgres.unknownref99182371:{super_secret_pw}@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
        try:
            parse_and_validate_staging_db_url(url)
            pytest.fail("Should have raised StagingGuardError")
        except StagingGuardError as exc:
            assert super_secret_pw not in str(exc)

    def test_staging_runtime_rejects_allow_sqlite(self, monkeypatch):
        """ALLOW_SQLITE_IN_PROD in Staging runtime must raise error."""
        monkeypatch.setenv("ALLOW_SQLITE_IN_PROD", "true")
        with pytest.raises(StagingGuardError, match="ALLOW_SQLITE_IN_PROD is enabled in Staging"):
            validate_staging_runtime_env()

    def test_staging_runtime_accepts_clean_env(self, monkeypatch):
        """Absence or disabled ALLOW_SQLITE_IN_PROD must pass."""
        monkeypatch.delenv("ALLOW_SQLITE_IN_PROD", raising=False)
        validate_staging_runtime_env()
        monkeypatch.setenv("ALLOW_SQLITE_IN_PROD", "false")
        validate_staging_runtime_env()


class TestStagingDockerContract:
    """Verifies Docker revision identity contract for Staging."""

    def test_dockerfile_staging_enforces_40_char_sha(self):
        """Dockerfile.staging must strictly fail closed if DEPLOY_SHA is invalid."""
        from pathlib import Path
        dockerfile = Path("Dockerfile.staging")
        assert dockerfile.exists(), "Dockerfile.staging must exist"
        content = dockerfile.read_text(encoding="utf-8")
        assert "ARG DEPLOY_SHA=\"\"" in content
        assert "grep -Eq '^[0-9a-fA-F]{40}$'" in content
        assert "FATAL: DEPLOY_SHA must be a valid 40-character git commit SHA" in content

    def test_docker_compose_staging_requires_deploy_sha(self):
        """docker-compose.staging.yml must require DEPLOY_SHA parameter."""
        compose_file = Path("docker-compose.staging.yml")
        assert compose_file.exists(), "docker-compose.staging.yml must exist"
        raw_text = compose_file.read_text(encoding="utf-8")
        assert "${DEPLOY_SHA:?DEPLOY_SHA must be set to a 40-char git commit SHA}" in raw_text

    def test_deploy_sha_file_is_valid_sha(self):
        """DEPLOY_SHA file in repository must contain a 40-char hex commit SHA or be handled dynamically."""
        sha_file = Path("DEPLOY_SHA")
        assert sha_file.exists(), "DEPLOY_SHA file must exist"
        content = sha_file.read_text(encoding="utf-8").strip()
        assert content not in ("unspecified", "unknown", "")
        assert re.match(r"^[0-9a-fA-F]{40}$", content) is not None, f"Expected 40-char hex SHA, got: {content}"
