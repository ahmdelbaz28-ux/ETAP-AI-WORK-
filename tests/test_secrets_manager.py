"""Comprehensive tests for security/secrets_manager.py.

Covers utility functions, LocalSecretsManager, EnvironmentValidator,
KeyAccessAuditor, and the singleton factory get_secrets_manager.
VaultSecretsManager tests are skipped when ``hvac`` is not installed.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from security.secrets_manager import (
    REQUIRED_SECRETS,
    EnvironmentValidator,
    KeyAccessAuditor,
    LocalSecretsManager,
    _ensure_dir,
    _get_cipher,
    get_secrets_manager,
)

# Suppress noisy loggers but keep audit logger functionality
logging.getLogger("security.secrets_manager").setLevel(logging.CRITICAL)
logging.getLogger("api.database").setLevel(logging.CRITICAL)
logging.getLogger("api").setLevel(logging.CRITICAL)


# =========================================================================
# Utility functions
# =========================================================================


class TestEnsureDir:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "a" / "b" / "c"
            result = _ensure_dir(test_dir)
            assert result == test_dir
            assert test_dir.is_dir()

    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _ensure_dir(Path(tmpdir))
            assert result == Path(tmpdir)
            assert Path(tmpdir).is_dir()


class TestGetCipher:
    def test_generates_new_key(self):
        cipher, key = _get_cipher()
        assert isinstance(key, bytes)
        assert len(key) > 0
        # Verify it can encrypt/decrypt
        data = b"hello"
        encrypted = cipher.encrypt(data)
        assert cipher.decrypt(encrypted) == data

    def test_with_provided_key(self):
        from cryptography.fernet import Fernet
        pre_key = Fernet.generate_key()
        cipher, key = _get_cipher(pre_key)
        assert key == pre_key
        data = b"test"
        assert cipher.decrypt(cipher.encrypt(data)) == data


# =========================================================================
# LocalSecretsManager
# =========================================================================


class TestLocalSecretsManager:
    @pytest.fixture
    def tmp_secrets_dir(self, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Redirect SECRETS_DIR to a temp directory and return it."""
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("security.secrets_manager.SECRETS_DIR", tmp)
        monkeypatch.setattr("security.secrets_manager.ENCRYPTION_KEY_FILE", tmp / ".encryption_key")
        return tmp

    def test_init_generates_key_file(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        key_file = tmp_secrets_dir / ".encryption_key"
        assert key_file.exists()
        assert mgr._key is not None
        assert mgr._cipher is not None

    def test_init_with_provided_key(self, tmp_secrets_dir: Path):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        mgr = LocalSecretsManager(encryption_key=key)
        assert mgr._key == key

    def test_set_and_get_api_key(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        assert mgr.set_api_key("test_service", "my-api-key-123")
        result = mgr.get_api_key("test_service")
        assert result == "my-api-key-123"

    def test_get_api_key_missing(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        result = mgr.get_api_key("nonexistent")
        assert result is None

    def test_delete_api_key(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        mgr.set_api_key("svc", "value")
        assert mgr.delete_api_key("svc")
        assert mgr.get_api_key("svc") is None

    def test_delete_api_key_missing(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        assert not mgr.delete_api_key("does_not_exist")

    def test_list_services(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        mgr.set_api_key("svc_a", "val_a")
        mgr.set_api_key("svc_b", "val_b")
        services = mgr.list_services()
        assert "svc_a" in services
        assert "svc_b" in services

    def test_rotate_key(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        old_key = mgr._key
        mgr.set_api_key("rotate_test", "secret_value")
        assert mgr.rotate_key()
        assert mgr._key != old_key
        # Old values should still be decryptable
        assert mgr.get_api_key("rotate_test") == "secret_value"

    def test_service_file_sanitises_name(self, tmp_secrets_dir: Path):
        mgr = LocalSecretsManager()
        # service names with special characters should be sanitised
        svc_file = mgr._service_file("my/test@service!")
        # The safe name replaces non-alnum chars with _
        assert "/" not in str(svc_file)
        assert svc_file.suffix == ".enc"


# =========================================================================
# KeyAccessAuditor
# =========================================================================


class TestKeyAccessAuditor:
    @pytest.fixture
    def tmp_audit_dir(self, monkeypatch: pytest.MonkeyPatch) -> Path:
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("security.secrets_manager.AUDIT_DIR", tmp)
        return tmp

    @staticmethod
    def _flush_logger(auditor: KeyAccessAuditor) -> None:
        """Force log handler to flush so files are written to disk."""
        if auditor._log_handler:
            auditor._log_handler.flush()
        import logging as _logging
        # Also flush the root file handlers if any
        for h in _logging.getLogger("key_access_audit").handlers:
            h.flush()

    @staticmethod
    def _read_and_parse(auditor: KeyAccessAuditor) -> list[dict]:
        """Read the audit log file and parse JSON entries."""
        if not auditor._log_file.exists():
            return []
        records: list[dict] = []
        for line in auditor._log_file.read_text(encoding="utf-8").strip().splitlines():
            try:
                records.append(json.loads(line.split(" - ", 2)[-1]))
            except (json.JSONDecodeError, IndexError):
                continue
        return records

    def test_log_access_creates_file(self, tmp_audit_dir: Path):
        auditor = KeyAccessAuditor(audit_logger=None)
        auditor.log_access(user_id="test_user", key_name="API_KEY", action="get", success=True)
        self._flush_logger(auditor)
        log_file = tmp_audit_dir / "key_access.log"
        assert log_file.exists()
        records = self._read_and_parse(auditor)
        assert len(records) == 1
        assert records[0]["user_id"] == "test_user"
        assert records[0]["key_name"] == "API_KEY"
        assert records[0]["action"] == "get"
        assert records[0]["success"] is True

    def test_log_access_failure(self, tmp_audit_dir: Path):
        auditor = KeyAccessAuditor(audit_logger=None)
        auditor.log_access(user_id="u1", key_name="SECRET", action="get", success=False)
        self._flush_logger(auditor)
        records = self._read_and_parse(auditor)
        assert len(records) == 1
        assert records[0]["success"] is False

    def test_get_access_logs_empty(self, tmp_audit_dir: Path):
        auditor = KeyAccessAuditor(audit_logger=None)
        self._flush_logger(auditor)
        logs = auditor.get_access_logs()
        assert logs == []

    def test_get_access_logs_filter(self, tmp_audit_dir: Path):
        auditor = KeyAccessAuditor(audit_logger=None)
        auditor.log_access("u1", "key_a", "get", True)
        auditor.log_access("u1", "key_b", "get", True)
        auditor.log_access("u2", "key_a", "set", True)
        self._flush_logger(auditor)

        # Filter by key_name
        only_key_a = auditor.get_access_logs(key_name="key_a")
        assert len(only_key_a) == 2
        assert all(r["key_name"] == "key_a" for r in only_key_a)

        # Filter by user_id
        only_u2 = auditor.get_access_logs(user_id="u2")
        assert len(only_u2) == 1
        assert only_u2[0]["user_id"] == "u2"

    def test_get_recent_access(self, tmp_audit_dir: Path):
        auditor = KeyAccessAuditor(audit_logger=None)
        for i in range(5):
            auditor.log_access("u1", f"key_{i}", "get", True)
        self._flush_logger(auditor)
        recent = auditor.get_recent_access(limit=3)
        assert len(recent) == 3
        # Most recent first
        timestamps = [r["timestamp"] for r in recent]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_framework_audit_integration(self, tmp_audit_dir: Path):
        """When a framework audit logger is provided, it should be called."""
        mock_audit = MagicMock()
        auditor = KeyAccessAuditor(audit_logger=mock_audit)
        auditor.log_access("u1", "k1", "delete", True)
        self._flush_logger(auditor)
        mock_audit.log_event.assert_called_once()


# =========================================================================
# EnvironmentValidator
# =========================================================================


class TestEnvironmentValidator:
    def test_check_missing_secrets_all_missing(self):
        validator = EnvironmentValidator(required_secrets=["MISSING_1", "MISSING_2"])
        with patch.dict(os.environ, {}, clear=True):
            missing = validator.check_missing_secrets()
        assert "MISSING_1" in missing
        assert "MISSING_2" in missing

    def test_check_missing_secrets_some_present(self):
        validator = EnvironmentValidator(required_secrets=["EXISTS", "MISSING"])
        with patch.dict(os.environ, {"EXISTS": "real_value"}, clear=True):
            missing = validator.check_missing_secrets()
        assert "MISSING" in missing
        assert "EXISTS" not in missing

    def test_check_missing_secrets_all_present(self):
        validator = EnvironmentValidator(required_secrets=["A", "B"])
        with patch.dict(os.environ, {"A": "a", "B": "b"}, clear=True):
            missing = validator.check_missing_secrets()
        assert missing == []

    def test_check_missing_skips_placeholder_values(self):
        validator = EnvironmentValidator(required_secrets=["VAL"])
        with patch.dict(os.environ, {"VAL": "your-value-here"}, clear=True):
            missing = validator.check_missing_secrets()
        assert "VAL" in missing

    def test_env_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = EnvironmentValidator(env_path=Path(tmpdir) / ".env.nonexistent")
            result = validator.check_file_permissions()
            assert not result

    def test_generate_env_template(self, tmp_path: Path):
        validator = EnvironmentValidator()
        out = tmp_path / ".env.example"
        content = validator.generate_env_template(output_path=out)
        assert out.exists()
        assert "JWT_SECRET_KEY" in content
        assert "DATABASE_URL" in content
        assert "ENVIRONMENT=development" in content

    def test_generate_env_template_default_path(self, monkeypatch: pytest.MonkeyPatch):
        # Run from tmpdir so cwd()/.env.example doesn't pollute repo
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.chdir(tmp)
        validator = EnvironmentValidator()
        content = validator.generate_env_template()
        assert (tmp / ".env.example").exists()
        assert "JWT_SECRET_KEY" in content

    def test_check_for_hardcoded_secrets_clean(self, tmp_path: Path):
        # Create a clean Python file
        clean_file = tmp_path / "safe_module.py"
        clean_file.write_text("x = 5\ny = 'hello'\n")
        validator = EnvironmentValidator()
        with patch.object(Path, "cwd", return_value=tmp_path):
            findings = validator.check_for_hardcoded_secrets(file_patterns=["*.py"])
        assert findings == []

    def test_check_for_hardcoded_secrets_finds_api_key(self, tmp_path: Path):
        risky_file = tmp_path / "config.py"
        risky_file.write_text(
            'api_key = "sk-abcdefghijklmnopqrstuvwxyz"\nsecret = "some_secret_value_here"\n'
        )
        validator = EnvironmentValidator()
        with patch.object(Path, "cwd", return_value=tmp_path):
            findings = validator.check_for_hardcoded_secrets(file_patterns=["*.py"])
        assert len(findings) >= 1
        assert any("API Key" in f["type"] for f in findings)

    def test_check_file_permissions_not_found(self):
        """When .env does not exist, check_file_permissions should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.nonexistent"
            validator = EnvironmentValidator(env_path=env_file)
            result = validator.check_file_permissions()
        assert not result


# =========================================================================
# get_secrets_manager singleton factory
# =========================================================================


class TestGetSecretsManager:
    def teardown_method(self) -> None:
        """Reset singleton between tests."""
        import security.secrets_manager as sm
        sm._secrets_manager_instance = None

    @patch("security.secrets_manager.LocalSecretsManager")
    def test_fallback_on_runtime_error(self, mock_local):
        with patch("security.secrets_manager.VaultSecretsManager", side_effect=RuntimeError):
            mgr = get_secrets_manager(use_mock_if_unavailable=True)
        assert mgr is not None

    @patch("security.secrets_manager.LocalSecretsManager")
    def test_fallback_on_generic_exception(self, mock_local):
        with patch("security.secrets_manager.VaultSecretsManager", side_effect=Exception("Boom")):
            mgr = get_secrets_manager(use_mock_if_unavailable=True)
        assert mgr is not None

    def test_singleton_returns_same_instance(self):
        import security.secrets_manager as sm
        sm._secrets_manager_instance = None
        with patch("security.secrets_manager.LocalSecretsManager") as mock_lsm:
            mock_instance = mock_lsm.return_value
            sm._secrets_manager_instance = mock_instance
            result = get_secrets_manager()
            assert result is mock_instance


# =========================================================================
# VaultSecretsManager (when hvac is available)
# =========================================================================

_hvac_available = False
try:
    import hvac  # noqa: F401
    _hvac_available = True
except ImportError:
    pass

pytestmark_vault = pytest.mark.skipif(
    not _hvac_available,
    reason="hvac not installed",
)


class TestVaultSecretsManager:
    """Tests for VaultSecretsManager. The suite-level skipif above skips
    all tests in this class if ``hvac`` is not installed."""
    pytestmark = pytestmark_vault

    @pytest.fixture(autouse=True)
    def setup_method_fixture(self, monkeypatch: pytest.MonkeyPatch):
        # Redirect file-system paths to tmp
        self.tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("security.secrets_manager.SECRETS_DIR", self.tmp)
        monkeypatch.setattr(
            "security.secrets_manager.ENCRYPTION_KEY_FILE", self.tmp / ".encryption_key"
        )

    @patch("hvac.Client")
    def test_init_vault_connected(self, mock_hvac):
        """When hvac client authenticates, _connected should be True."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.return_value = mock_client

        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager(vault_addr="http://vault:8200")
        assert mgr._connected
        assert mgr._client is not None
        assert mgr._fallback_store is None

    @patch("hvac.Client")
    def test_get_secret_vault_connected(self, mock_hvac):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"mykey": "myvalue"}},
        }
        mock_hvac.return_value = mock_client

        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager()
        result = mgr.get_secret("path", "mykey")
        assert result == "myvalue"

    @patch("hvac.Client")
    def test_set_secret_vault_connected(self, mock_hvac):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.return_value = mock_client

        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager()
        assert mgr.set_secret("path", "key", "value")
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    def test_fallback_service_name_sanitizes(self):
        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager()
        name = mgr._fallback_service_name("path/with/special!", "key$%^")
        # Should only contain alphanums, underscores, hyphens
        assert all(c.isalnum() or c in "_-" for c in name)

    @patch("hvac.Client")
    def test_delete_secret(self, mock_hvac):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"k1": "v1", "k2": "v2"}},
        }
        mock_hvac.return_value = mock_client

        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager()
        assert mgr.delete_secret("p", "k1")
        # Should update with remaining keys
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    @patch("hvac.Client")
    def test_list_secrets(self, mock_hvac):
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["a", "b", "c"]},
        }
        mock_hvac.return_value = mock_client

        from security.secrets_manager import VaultSecretsManager

        mgr = VaultSecretsManager()
        keys = mgr.list_secrets("some_path")
        assert keys == ["a", "b", "c"]
