"""
Tests for Supabase integration (Postgres + Storage + Auth).

Tests cover:
- Storage: MIME-type validation, size limits, filename sanitisation
- Storage: upload/list/delete/signed-URL flow
- Auth: token verification, OAuth URL generation, magic-link
- Auth: enabled/disabled toggle
- Database: DATABASE_URL detection for Supabase
- Health checks
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Storage safety validation
# ---------------------------------------------------------------------------


class TestStorageSafetyValidation:
    """Storage uploads must enforce MIME-type and size guardrails."""

    def test_valid_pdf_upload_passes_validation(self):
        from integrations.supabase_integration import _validate_upload

        # Should not raise
        _validate_upload(b"fake pdf content", "application/pdf")

    def test_valid_image_upload_passes_validation(self):
        from integrations.supabase_integration import _validate_upload

        _validate_upload(b"\x89PNG\r\n\x1a\n" + b"x" * 100, "image/png")

    def test_executable_upload_rejected(self):
        """Executable MIME types must be refused (anti-malware safety)."""
        from integrations.supabase_integration import (
            SupabaseUploadError,
            _validate_upload,
        )

        with pytest.raises(SupabaseUploadError, match="Disallowed MIME type"):
            _validate_upload(b"MZ\x90\x00", "application/x-msdownload")

        with pytest.raises(SupabaseUploadError, match="Disallowed MIME type"):
            _validate_upload(b"#!/bin/sh", "application/x-sh")

    def test_empty_upload_rejected(self):
        from integrations.supabase_integration import (
            SupabaseUploadError,
            _validate_upload,
        )

        with pytest.raises(SupabaseUploadError, match="Empty upload"):
            _validate_upload(b"", "application/pdf")

    def test_oversized_upload_rejected(self):
        """Uploads > 50MB must be refused (resource-exhaustion protection)."""
        from integrations.supabase_integration import (
            SupabaseUploadError,
            _validate_upload,
        )

        # 60 MB
        huge = b"x" * (60 * 1024 * 1024)
        with pytest.raises(SupabaseUploadError, match="Upload too large"):
            _validate_upload(huge, "application/pdf")

    def test_allowed_mime_types_includes_critical_formats(self):
        from integrations.supabase_integration import _ALLOWED_MIME_TYPES

        # PDF (manuals)
        assert "application/pdf" in _ALLOWED_MIME_TYPES
        # Excel (reports)
        assert (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            in _ALLOWED_MIME_TYPES
        )
        # PNG (ETAP screenshots)
        assert "image/png" in _ALLOWED_MIME_TYPES


# ---------------------------------------------------------------------------
# Filename sanitisation (anti path-traversal)
# ---------------------------------------------------------------------------


class TestFilenameSanitisation:
    """Filenames must be sanitised to prevent path-traversal attacks."""

    def test_path_traversal_stripped(self):
        """``../../etc/passwd`` must be neutralised."""
        from integrations.supabase_integration import _sanitise_filename

        result = _sanitise_filename("../../etc/passwd")
        # Path components stripped
        assert "/" not in result or result.split("/", 1)[0].isalnum()
        assert "passwd" in result
        # No parent-dir traversal
        assert ".." not in result

    def test_windows_path_stripped(self):
        from integrations.supabase_integration import _sanitise_filename

        result = _sanitise_filename(r"..\..\windows\system32\config")
        assert ".." not in result

    def test_special_chars_replaced(self):
        from integrations.supabase_integration import _sanitise_filename

        result = _sanitise_filename("file with spaces & special!@#.pdf")
        # Spaces and special chars replaced with underscores
        assert " " not in result.split("/", 1)[1]
        assert all(c.isalnum() or c in "-_./" for c in result)

    def test_uuid_prefix_added(self):
        """Each upload gets a unique UUID prefix (collision prevention)."""
        from integrations.supabase_integration import _sanitise_filename

        r1 = _sanitise_filename("report.pdf")
        r2 = _sanitise_filename("report.pdf")
        assert r1 != r2  # different UUIDs
        # Both end with /report.pdf
        assert r1.endswith("/report.pdf")
        assert r2.endswith("/report.pdf")

    def test_empty_filename_handled(self):
        from integrations.supabase_integration import _sanitise_filename

        result = _sanitise_filename("")
        # Should not raise; uses fallback name
        assert "upload" in result


# ---------------------------------------------------------------------------
# Storage operations (mocked — no real Supabase calls)
# ---------------------------------------------------------------------------


class TestStorageOperations:
    """Storage upload/list/delete operations (with mocked client)."""

    def test_upload_returns_path_and_metadata(self, monkeypatch):
        """Successful upload returns a dict with path + size + content_type."""
        from integrations import supabase_integration

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.upload.return_value = MagicMock(error=None)

        # Mock get_bucket to return a private bucket
        mock_client.storage.get_bucket.return_value = MagicMock(public=False)

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        result = supabase_integration.upload_bytes(
            bucket="reports",
            filename="arc_flash_report.pdf",
            content=b"fake pdf content",
            content_type="application/pdf",
            user_id="eng_42",
        )
        assert result["bucket"] == "reports"
        assert result["size"] == len(b"fake pdf content")
        assert result["content_type"] == "application/pdf"
        assert "path" in result
        # Private bucket → no public URL
        assert result["public_url"] is None
        # Upload was called
        mock_bucket.upload.assert_called_once()

    def test_upload_to_public_bucket_returns_public_url(self, monkeypatch):
        from integrations import supabase_integration

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.upload.return_value = MagicMock(error=None)
        mock_bucket.get_public_url.return_value = "https://example.com/public/file.pdf"

        # Public bucket
        mock_client.storage.get_bucket.return_value = MagicMock(public=True)

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        result = supabase_integration.upload_bytes(
            bucket="manuals",
            filename="etap_guide.pdf",
            content=b"fake pdf",
            content_type="application/pdf",
        )
        assert result["public_url"] == "https://example.com/public/file.pdf"

    def test_get_signed_url_returns_url(self, monkeypatch):
        from integrations import supabase_integration

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.create_signed_url.return_value = {
            "signedURL": "https://example.com/signed/abc?token=xyz"
        }

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        url = supabase_integration.get_signed_url(
            bucket="reports", path="abc/report.pdf", expires_in=3600
        )
        assert url == "https://example.com/signed/abc?token=xyz"
        mock_bucket.create_signed_url.assert_called_once_with("abc/report.pdf", 3600)

    def test_delete_file_returns_true_on_success(self, monkeypatch):
        from integrations import supabase_integration

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        result = supabase_integration.delete_file(bucket="reports", path="abc/report.pdf")
        assert result is True
        mock_bucket.remove.assert_called_once_with(["abc/report.pdf"])

    def test_list_files_returns_list(self, monkeypatch):
        from integrations import supabase_integration

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket
        mock_bucket.list.return_value = [
            {"name": "file1.pdf", "metadata": {"size": 1000}},
            {"name": "file2.pdf", "metadata": {"size": 2000}},
        ]

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        files = supabase_integration.list_files(bucket="reports")
        assert len(files) == 2
        assert files[0]["name"] == "file1.pdf"

    def test_upload_raises_when_client_unavailable(self, monkeypatch):
        """When Supabase client is None, upload raises RuntimeError."""
        from integrations import supabase_integration

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: None)

        with pytest.raises(RuntimeError, match="Supabase client not available"):
            supabase_integration.upload_bytes(
                bucket="reports",
                filename="x.pdf",
                content=b"data",
                content_type="application/pdf",
            )


# ---------------------------------------------------------------------------
# Bucket management
# ---------------------------------------------------------------------------


class TestBucketManagement:
    """ensure_buckets_exist is idempotent."""

    def test_ensure_buckets_creates_missing_buckets(self, monkeypatch):
        from integrations import supabase_integration

        mock_client = MagicMock()
        # Buckets that already exist
        mock_client.storage.list_buckets.return_value = [
            {"name": "manuals"},  # already exists
        ]

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        result = supabase_integration.ensure_buckets_exist()
        # 'manuals' was NOT created (already existed)
        assert result["manuals"] is False
        # Other 3 buckets WERE created
        assert result["reports"] is True
        assert result["screenshots"] is True
        assert result["user-uploads"] is True

    def test_ensure_buckets_handles_errors_gracefully(self, monkeypatch):
        """When both list_buckets AND create_bucket fail, all buckets return False."""
        from integrations import supabase_integration

        mock_client = MagicMock()
        # Both list_buckets AND create_bucket fail
        mock_client.storage.list_buckets.side_effect = Exception("network error")
        mock_client.storage.create_bucket.side_effect = Exception("create failed")

        monkeypatch.setattr(supabase_integration, "_get_client", lambda: mock_client)

        result = supabase_integration.ensure_buckets_exist()
        # All buckets fail → False
        assert all(v is False for v in result.values())


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestSupabaseAuth:
    """Supabase Auth (token verification, OAuth, magic-link)."""

    def test_disabled_by_default(self, monkeypatch):
        """Supabase Auth is OFF by default."""
        import importlib

        monkeypatch.delenv("SUPABASE_AUTH_ENABLED", raising=False)
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "")

        import integrations.supabase_auth as auth_mod

        importlib.reload(auth_mod)
        assert auth_mod.SUPABASE_AUTH_ENABLED is False

        from integrations.supabase_auth import SupabaseAuthError, verify_supabase_token

        with pytest.raises(SupabaseAuthError, match="disabled"):
            verify_supabase_token("any-token")

    def test_verify_token_returns_user_info(self, monkeypatch):
        """verify_supabase_token calls the Supabase Auth API."""
        import importlib

        monkeypatch.setenv("SUPABASE_AUTH_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-key")

        import integrations.supabase_auth as auth_mod

        importlib.reload(auth_mod)

        # Mock httpx.get to return a fake user
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "id": "user-123",
            "email": "engineer@example.com",
            "user_metadata": {"full_name": "Test Engineer"},
        }

        with patch("httpx.get", return_value=fake_response):
            user_info = auth_mod.verify_supabase_token("access-token")

        assert user_info["id"] == "user-123"
        assert user_info["email"] == "engineer@example.com"

    def test_verify_token_raises_on_invalid_token(self, monkeypatch):
        """Invalid tokens raise SupabaseAuthError."""
        import importlib

        monkeypatch.setenv("SUPABASE_AUTH_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-key")

        import integrations.supabase_auth as auth_mod

        importlib.reload(auth_mod)

        fake_response = MagicMock()
        fake_response.status_code = 401
        fake_response.text = "Invalid token"

        with patch("httpx.get", return_value=fake_response):
            from integrations.supabase_auth import SupabaseAuthError

            with pytest.raises(SupabaseAuthError, match="Invalid Supabase token"):
                auth_mod.verify_supabase_token("bad-token")

    def test_get_oauth_url_returns_valid_url(self, monkeypatch):
        """get_oauth_url returns a properly-formatted OAuth URL."""
        import importlib

        monkeypatch.setenv("SUPABASE_AUTH_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-key")

        import integrations.supabase_auth as auth_mod

        importlib.reload(auth_mod)

        url = auth_mod.get_oauth_url(
            provider="google", redirect_to="https://app.example.com/callback"
        )
        assert "https://example.supabase.co/auth/v1/authorize" in url
        assert "provider=google" in url
        assert "redirect_to=" in url

    def test_send_magic_link_returns_true_on_success(self, monkeypatch):
        """send_magic_link POSTs to Supabase and returns True on success."""
        import importlib

        monkeypatch.setenv("SUPABASE_AUTH_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-key")

        import integrations.supabase_auth as auth_mod

        importlib.reload(auth_mod)

        fake_response = MagicMock(status_code=200)
        with patch("httpx.post", return_value=fake_response):
            result = auth_mod.send_magic_link(
                email="engineer@example.com",
                redirect_to="https://app.example.com/verify",
            )
        assert result is True


# ---------------------------------------------------------------------------
# Database URL detection
# ---------------------------------------------------------------------------


class TestDatabaseUrlDetection:
    """_is_supabase_database correctly identifies Supabase Postgres URLs."""

    def test_supabase_pooled_url_detected(self, monkeypatch):
        from integrations import supabase_integration

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres.abc:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
        )
        assert supabase_integration._is_supabase_database() is True

    def test_supabase_direct_url_detected(self, monkeypatch):
        from integrations import supabase_integration

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:pass@db.abc.supabase.co:5432/postgres",
        )
        assert supabase_integration._is_supabase_database() is True

    def test_local_postgres_not_detected(self, monkeypatch):
        from integrations import supabase_integration

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/etap_db",
        )
        assert supabase_integration._is_supabase_database() is False

    def test_sqlite_not_detected(self, monkeypatch):
        from integrations import supabase_integration

        monkeypatch.setenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./data/etap_platform.db"
        )
        assert supabase_integration._is_supabase_database() is False


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


class TestHealthChecks:
    """Both modules expose a health_check function."""

    def test_storage_health_check_structure(self):
        from integrations.supabase_integration import health_check

        info = health_check()
        assert "enabled" in info
        assert "url" in info
        assert "anon_key_set" in info
        assert "service_role_key_set" in info
        assert "buckets" in info
        assert "max_upload_mb" in info
        assert info["max_upload_mb"] == 50
        assert isinstance(info["buckets"], list)
        assert "manuals" in info["buckets"]
        assert "reports" in info["buckets"]
        assert "screenshots" in info["buckets"]
        assert "user-uploads" in info["buckets"]

    def test_auth_health_check_structure(self):
        from integrations.supabase_auth import health_check

        info = health_check()
        assert "enabled" in info
        assert "url" in info
        assert "anon_key_set" in info


# ---------------------------------------------------------------------------
# Database URL normalisation (api/database.py)
# ---------------------------------------------------------------------------


class TestDatabaseUrlNormalisation:
    """api/database.py should accept bare postgres:// and convert to asyncpg."""

    def test_bare_postgres_url_converted_to_asyncpg(self):
        # Re-test the _normalise_url function from api/database.py
        import sys

        sys.path.insert(0, "/home/z/my-project/ETAP-AI-WORK-")
        from api.database import _normalise_url

        # postgres:// → postgresql+asyncpg://
        result = _normalise_url("postgres://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

        # postgresql:// → postgresql+asyncpg://
        result = _normalise_url("postgresql://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

        # Already-correct URL passes through
        result = _normalise_url("postgresql+asyncpg://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

        # SQLite passes through
        result = _normalise_url("sqlite+aiosqlite:///./data/etap.db")
        assert result == "sqlite+aiosqlite:///./data/etap.db"
