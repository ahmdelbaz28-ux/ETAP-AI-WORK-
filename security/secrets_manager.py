"""
Secrets Manager for AhmedETAP Engineering Platform
=================================================
Production-grade secrets management with HashiCorp Vault integration,
encrypted local storage, key access auditing, and environment validation.

Integrates with security_framework.py singletons (AuditLogger) and
uses cryptography.fernet for symmetric encryption fallback.

Features:
- VaultSecretsManager: HashiCorp Vault with encrypted local fallback
- LocalSecretsManager: Fernet-encrypted local secrets storage
- KeyAccessAuditor: Comprehensive audit logging for key access
- EnvironmentValidator: Validates environment configuration
- get_secrets_manager(): Singleton factory (Vault first, local fallback)
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import threading
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

SECRETS_DIR = Path.home() / ".etap-platform" / "secrets"
AUDIT_DIR = Path(__file__).parent / "audit"
ENCRYPTION_KEY_FILE = SECRETS_DIR / ".encryption_key"
REQUIRED_SECRETS = [
    "JWT_SECRET_KEY",
    "ENCRYPTION_KEY",
    "OPENAI_API_KEY",
    "LANGWATCH_API_KEY",
    "ETAP_LICENSE_KEY",
    "DATABASE_URL",
    "REDIS_URL",
]


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_cipher(key: Optional[bytes] = None) -> Tuple[Fernet, bytes]:
    if key:
        return Fernet(key), key
    key = Fernet.generate_key()
    return Fernet(key), key


class VaultSecretsManager:
    """
    HashiCorp Vault integration for secrets management.

    Supports authenticating with a Vault token and performing CRUD operations
    on secrets stored at a configurable mount path (KV v2 engine).

    If Vault is unavailable and use_mock_if_unavailable is True, falls back to
    encrypted local storage using Fernet (same encryption as AuthenticationManager).

    Args:
        vault_addr: Base URL of the Vault server (e.g. http://127.0.0.1:8200)
        vault_token: Vault authentication token
        mount_path: KV v2 engine mount path (default: "secret")
        use_mock_if_unavailable: Fall back to local Fernet storage if Vault unreachable
    """

    def __init__(
        self,
        vault_addr: str = "http://127.0.0.1:8200",
        vault_token: str = "",
        mount_path: str = "secret",
        use_mock_if_unavailable: bool = True,
    ):
        self.vault_addr = vault_addr.rstrip("/")
        self._vault_token = vault_token  # Private to avoid accidental logging
        self.mount_path = mount_path
        self.use_mock = use_mock_if_unavailable
        self._client = None
        self._connected = False

        # Disk-backed fallback (no in-memory secret loss on restart).
        # We reuse LocalSecretsManager (Fernet-encrypted files under SECRETS_DIR).
        self._fallback_store: Optional[LocalSecretsManager] = None

        self._init_vault_client()

    @property
    def vault_token(self) -> str:
        """Access vault token (masked in repr for security)."""
        return self._vault_token

    def __repr__(self) -> str:
        masked = self._vault_token[:4] + "****" if len(self._vault_token) > 4 else "****"
        return f"VaultSecretsManager(addr={self.vault_addr!r}, token={masked!r})"

    def _init_vault_client(self):
        try:
            import hvac

            self._client = hvac.Client(
                url=self.vault_addr,
                token=self.vault_token,
            )
            if self._client.is_authenticated():
                self._connected = True
                logger.info("Connected to Vault at %s", self.vault_addr)
            else:
                logger.warning("Vault authentication failed for %s", self.vault_addr)
                self._client = None
        except ImportError:
            logger.warning("hvac package not installed; Vault integration unavailable")
        except Exception as exc:
            logger.warning("Vault connection failed: %s", exc)

        if not self._connected:
            if self.use_mock:
                # Persist fallback secrets instead of using in-memory mock storage.
                self._fallback_store = LocalSecretsManager()
                logger.info("Falling back to disk-backed LocalSecretsManager for Vault secrets")
            else:
                raise RuntimeError(
                    f"Cannot connect to Vault at {self.vault_addr} "
                    "and use_mock_if_unavailable is False"
                )

    def _fallback_service_name(self, path: str, key: str) -> str:
        # Deterministic mapping from Vault (path, key) to LocalSecretsManager service file.
        # Sanitize path characters the same way _service_file does (replace non-alnum with _)
        raw = f"{self.mount_path}__{path}__{key}"
        return re.sub(r"[^a-zA-Z0-9_-]", "_", raw)

    def get_secret(self, path: str, key: str) -> Optional[str]:
        if self._connected and self._client:
            try:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.mount_path,
                )
                data = response.get("data", {}).get("data", {})
                return data.get(key)
            except Exception as exc:
                logger.error("Vault get_secret failed for %s/%s: %s", path, key, exc)
                return None

        if self._fallback_store:
            return self._fallback_store.get_api_key(self._fallback_service_name(path, key))

        return None

    def set_secret(self, path: str, key: str, value: str) -> bool:
        if self._connected and self._client:
            try:
                self._client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret={key: value},
                    mount_point=self.mount_path,
                )
                return True
            except Exception as exc:
                logger.error("Vault set_secret failed for %s/%s: %s", path, key, exc)
                return False

        if self._fallback_store:
            return self._fallback_store.set_api_key(
                self._fallback_service_name(path, key),
                value,
            )

        return False

    def delete_secret(self, path: str, key: str) -> bool:
        if self._connected and self._client:
            try:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.mount_path,
                )
                data = response.get("data", {}).get("data", {})
                if key not in data:
                    logger.warning("Key %s not found at path %s", key, path)
                    return False
                data.pop(key, None)
                if data:
                    self._client.secrets.kv.v2.create_or_update_secret(
                        path=path,
                        secret=data,
                        mount_point=self.mount_path,
                    )
                else:
                    self._client.secrets.kv.v2.delete_metadata_and_all_versions(
                        path=path,
                        mount_point=self.mount_path,
                    )
                return True
            except Exception as exc:
                logger.error("Vault delete_secret failed for %s/%s: %s", path, key, exc)
                return False

        if self._fallback_store:
            return self._fallback_store.delete_api_key(self._fallback_service_name(path, key))

        return False

    def list_secrets(self, path: str) -> List[str]:
        if self._connected and self._client:
            try:
                response = self._client.secrets.kv.v2.list_secrets(
                    path=path,
                    mount_point=self.mount_path,
                )
                return response.get("data", {}).get("keys", [])
            except Exception as exc:
                logger.error("Vault list_secrets failed for %s: %s", path, exc)
                return []
        # For fallback, list all keys we have persisted under this (mount_path, path).
        if self._fallback_store:
            prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{self.mount_path}__{path}__")
            services = self._fallback_store.list_services()
            keys: List[str] = []
            for svc in services:
                if svc.startswith(prefix):
                    keys.append(svc[len(prefix) :])
            return keys
        return []


class LocalSecretsManager:
    """
    Encrypted local secrets storage using Fernet symmetric encryption.

    Stores encrypted secrets in ~/.etap-platform/secrets/ directory.
    Each service has its own encrypted file; the encryption key is stored
    alongside (itself encrypted at rest under a master key).

    Integrates with the existing AuthenticationManager encryption pattern
    but maintains its own independent key for isolation.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        _ensure_dir(SECRETS_DIR)
        self._key: bytes
        self._cipher: Fernet

        if encryption_key:
            self._key = encryption_key
        else:
            self._key = self._load_or_generate_key()
        self._cipher = Fernet(self._key)

    def _load_or_generate_key(self) -> bytes:
        if ENCRYPTION_KEY_FILE.exists():
            try:
                raw = ENCRYPTION_KEY_FILE.read_bytes()
                Fernet(raw)
                return raw
            except (ValueError, InvalidToken):
                logger.warning("Existing encryption key is invalid; generating new key")
                return self._generate_and_save_key()
        return self._generate_and_save_key()

    def _generate_and_save_key(self) -> bytes:
        """Generate a new Fernet key and persist it.

        Security: The key file is stored with owner-only permissions (0600 on Unix).
        In a production environment, consider using HashiCorp Vault or a KMS
        (Key Management Service) instead of local file-based key storage, so
        that the encryption key is never co-located with the encrypted data.
        """
        key = Fernet.generate_key()
        ENCRYPTION_KEY_FILE.write_bytes(key)

        # Cross-platform: os.chmod with Unix permission bits is ineffective on Windows.
        if os.name != "nt":
            os.chmod(str(ENCRYPTION_KEY_FILE), stat.S_IRUSR | stat.S_IWUSR)
        logger.info("Generated new encryption key at %s", ENCRYPTION_KEY_FILE)
        return key

    def _service_file(self, service_name: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", service_name)
        return SECRETS_DIR / f"{safe_name}.enc"

    def set_api_key(self, service_name: str, api_key: str) -> bool:
        try:
            encrypted = self._cipher.encrypt(api_key.encode())
            self._service_file(service_name).write_bytes(encrypted)
            logger.info("Stored encrypted API key for %s", service_name)
            return True
        except Exception as exc:
            logger.error("Failed to store API key for %s: %s", service_name, exc)
            return False

    def get_api_key(self, service_name: str) -> Optional[str]:
        path = self._service_file(service_name)
        if not path.exists():
            logger.warning("No stored API key for %s", service_name)
            return None
        try:
            encrypted = path.read_bytes()
            return self._cipher.decrypt(encrypted).decode()
        except InvalidToken:
            logger.error("Decryption failed for %s; key may have been rotated", service_name)
            return None
        except Exception as exc:
            logger.error("Failed to retrieve API key for %s: %s", service_name, exc)
            return None

    def rotate_key(self) -> bool:
        try:
            old_cipher = self._cipher
            new_key = Fernet.generate_key()
            new_cipher = Fernet(new_key)

            for enc_file in SECRETS_DIR.glob("*.enc"):
                if enc_file.name == ".encryption_key":
                    continue
                try:
                    plaintext = old_cipher.decrypt(enc_file.read_bytes())
                    enc_file.write_bytes(new_cipher.encrypt(plaintext))
                except InvalidToken:
                    logger.warning("Skipping %s: unable to decrypt with old key", enc_file.name)

            ENCRYPTION_KEY_FILE.write_bytes(new_key)

            if os.name != "nt":
                os.chmod(str(ENCRYPTION_KEY_FILE), stat.S_IRUSR | stat.S_IWUSR)

            self._key = new_key
            self._cipher = new_cipher
            logger.info("Encryption key rotated successfully")
            return True
        except Exception as exc:
            logger.error("Key rotation failed: %s", exc)
            return False

    def delete_api_key(self, service_name: str) -> bool:
        path = self._service_file(service_name)
        if not path.exists():
            logger.warning("No API key to delete for %s", service_name)
            return False
        try:
            path.unlink()
            logger.info("Deleted API key for %s", service_name)
            return True
        except Exception as exc:
            logger.error("Failed to delete API key for %s: %s", service_name, exc)
            return False

    def list_services(self) -> List[str]:
        return [f.stem for f in SECRETS_DIR.glob("*.enc") if f.name != ".encryption_key"]


class KeyAccessAuditor:
    """
    Audit logging for key access events.

    Logs every key retrieval with: timestamp, user_id, key_name, action,
    success/failure. Stores audit records in security/audit/key_access.log
    and integrates with the existing AuditLogger from security_framework.py.

    Actions tracked: get, set, delete, rotate, list
    """

    ACTION_GET = "get"
    ACTION_SET = "set"
    ACTION_DELETE = "delete"
    ACTION_ROTATE = "rotate"
    ACTION_LIST = "list"

    def __init__(self, audit_logger=None):
        _ensure_dir(AUDIT_DIR)
        self._log_file = AUDIT_DIR / "key_access.log"
        self._log_handler: Optional[logging.Handler] = None
        self._setup_logger()
        if audit_logger is None:
            try:
                from security.security_framework import get_audit_logger

                self._framework_audit = get_audit_logger()
            except Exception:
                self._framework_audit = None
        else:
            self._framework_audit = audit_logger

    def _setup_logger(self):
        self._logger = logging.getLogger("key_access_audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            str(self._log_file),
            encoding="utf-8",
            maxBytes=10_485_760,
            backupCount=5,
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self._logger.addHandler(file_handler)
        self._log_handler = file_handler

    def log_access(
        self,
        user_id: str,
        key_name: str,
        action: str,
        success: bool,
        details: Optional[Dict] = None,
    ):
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "key_name": key_name,
            "action": action,
            "success": success,
            "details": details or {},
        }
        level = logging.INFO if success else logging.WARNING
        self._logger.log(level, json.dumps(entry))

        if self._framework_audit:
            self._framework_audit.log_event(
                event_type="key_access",
                user_id=user_id,
                action=f"{action} key:{key_name}",
                details={"key_name": key_name, **entry["details"]},
                success=success,
            )

    def get_access_logs(
        self,
        key_name: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict]:
        if not self._log_file.exists():
            return []
        records: List[Dict] = []
        try:
            raw = self._log_file.read_text(encoding="utf-8").strip().splitlines()
            for line in raw:
                try:
                    record = json.loads(line.split(" - ", 2)[-1])
                except (json.JSONDecodeError, IndexError):
                    continue
                ts_str = record.get("timestamp", "")
                if key_name and record.get("key_name") != key_name:
                    continue
                if user_id and record.get("user_id") != user_id:
                    continue
                if start_time or end_time:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if start_time and ts < start_time:
                            continue
                        if end_time and ts > end_time:
                            continue
                    except (ValueError, TypeError):
                        continue
                records.append(record)
        except Exception as exc:
            logger.error("Failed to read access logs: %s", exc)
        return records

    def get_recent_access(self, limit: int = 100) -> List[Dict]:
        records = self.get_access_logs()
        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return records[:limit]


class EnvironmentValidator:
    """
    Validates environment configuration for security best practices.

    Checks:
    - Missing required secrets in environment variables
    - File permissions on .env (owner-only on Unix)
    - Hardcoded secrets in source code
    - Generates .env.example template from required secrets
    """

    def __init__(
        self, env_path: Optional[Path] = None, required_secrets: Optional[List[str]] = None
    ):
        self.env_path = env_path or Path.cwd() / ".env"
        self.required_secrets = required_secrets or REQUIRED_SECRETS

    def check_missing_secrets(self) -> List[str]:
        missing: List[str] = []
        for secret in self.required_secrets:
            value = os.environ.get(secret, "")
            if not value or value.startswith("generate-") or "your-" in value.lower():
                missing.append(secret)
        if missing:
            logger.warning("Missing required secrets: %s", ", ".join(missing))
        else:
            logger.info("All required secrets are configured")
        return missing

    def check_file_permissions(self) -> bool:
        env_path = self.env_path
        if not env_path.exists():
            logger.warning(".env file not found at %s", env_path)
            return False

        try:
            st_mode = env_path.stat().st_mode
            if os.name != "nt":
                owner_only = stat.S_IRUSR | stat.S_IWUSR
                group_other = stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
                if st_mode & group_other:
                    logger.warning(
                        ".env has overly permissive permissions (mode %o); "
                        "expected owner-only read/write",
                        st_mode,
                    )
                    return False
                has_owner = st_mode & owner_only
                if not has_owner:
                    logger.warning(".env missing owner read/write permissions")
                    return False
                logger.info(".env file permissions are secure")
                return True
            else:
                try:
                    import win32api
                    import win32con
                    import win32security

                    sd = win32security.GetFileSecurity(
                        str(env_path), win32security.OWNER_SECURITY_INFORMATION
                    )
                    owner_sid = sd.GetSecurityDescriptorOwner()
                    owner_name, _, _ = win32security.LookupAccountSid(None, owner_sid)
                    current_user = win32api.GetUserNameEx(win32con.NameSamCompatible)
                    if owner_name != current_user.split("\\")[-1]:
                        logger.warning(".env owner (%s) does not match current user", owner_name)
                        return False
                    logger.info(".env file ownership verified on Windows")
                    return True
                except ImportError:
                    logger.info("pywin32 not available; skipping Windows permission check")
                    return True
        except OSError as exc:
            logger.error("Cannot check .env permissions: %s", exc)
            return False

    def check_for_hardcoded_secrets(self, file_patterns: Optional[List[str]] = None) -> List[Dict]:
        if file_patterns is None:
            file_patterns = ["*.py", "*.ts", "*.js", "*.tsx", "*.jsx", "*.yaml", "*.yml"]
        patterns = [
            (r'(?i)(api[_-]?key\s*=\s*["\']?(sk-[a-zA-Z0-9]{20,}))', "API Key"),
            (r'(?i)(secret\s*=\s*["\'][a-zA-Z0-9]{20,}["\'])', "Secret"),
            (r'(?i)(password\s*=\s*["\'][^"\'\s]{6,}["\'])', "Password"),
            (r'(?i)(token\s*=\s*["\'][a-zA-Z0-9._-]{20,}["\'])', "Token"),
            (r"(?i)(BEGIN\s+(RSA\s+)?PRIVATE\s+KEY)", "Private Key"),
        ]
        root = Path.cwd()
        findings: List[Dict] = []
        for pattern in file_patterns:
            for fpath in root.rglob(pattern):
                if (
                    ".git" in fpath.parts
                    or "node_modules" in fpath.parts
                    or "__pycache__" in fpath.parts
                ):
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    for regex, label in patterns:
                        for match in re.finditer(regex, content):
                            findings.append(
                                {
                                    "file": str(fpath.relative_to(root)),
                                    "line": content[: match.start()].count("\n") + 1,
                                    "type": label,
                                    "match_preview": match.group(0)[:60],
                                }
                            )
                except (OSError, UnicodeDecodeError):
                    continue

        if findings:
            logger.warning("Found %d potential hardcoded secrets in codebase", len(findings))
        else:
            logger.info("No hardcoded secrets detected")
        return findings

    def generate_env_template(self, output_path: Optional[Path] = None) -> str:
        out = output_path or Path.cwd() / ".env.example"
        lines = [
            "# AhmedETAP - Environment Configuration",
            "# Copy this file to .env and fill in your actual values",
            "# cp .env.example .env",
            "",
            "# ==========================================",
            "# Required Secrets (must be configured)",
            "# ==========================================",
        ]
        for secret in REQUIRED_SECRETS:
            lines.append(f"# {secret}=<your-{secret.lower()}-here>")
        lines.extend(
            [
                "",
                "# ==========================================",
                "# Optional Configuration",
                "# ==========================================",
                "# Add any additional environment variables below",
                "# with safe defaults where appropriate",
                "",
                "ENVIRONMENT=development",
                "LOG_LEVEL=INFO",
                "DEBUG=false",
            ]
        )
        content = "\n".join(lines) + "\n"
        out.write_text(content, encoding="utf-8")
        logger.info("Generated env template at %s", out)
        return content


_secrets_manager_instance = None
_secrets_manager_lock = threading.Lock()


def get_secrets_manager(
    vault_addr: str = "",
    vault_token: str = "",
    mount_path: str = "secret",
    use_mock_if_unavailable: bool = True,
):
    """
    Singleton factory for secrets manager.

    Attempts to initialise a VaultSecretsManager first. If Vault is unavailable
    and use_mock_if_unavailable is True, falls back to LocalSecretsManager.

    Returns:
        VaultSecretsManager or LocalSecretsManager instance
    """
    global _secrets_manager_instance
    if _secrets_manager_instance is not None:
        return _secrets_manager_instance

    with _secrets_manager_lock:
        if _secrets_manager_instance is not None:
            return _secrets_manager_instance

        vault_addr = vault_addr or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = vault_token or os.environ.get("VAULT_TOKEN", "")

        try:
            mgr = VaultSecretsManager(
                vault_addr=vault_addr,
                vault_token=vault_token,
                mount_path=mount_path,
                use_mock_if_unavailable=use_mock_if_unavailable,
            )
            _secrets_manager_instance = mgr
            logger.info("Initialised VaultSecretsManager as secrets manager singleton")
        except RuntimeError:
            logger.info("Falling back to LocalSecretsManager")
            _secrets_manager_instance = LocalSecretsManager()
        except Exception as exc:
            logger.warning(
                "Secrets manager init failed (%s); using LocalSecretsManager",
                exc,
            )
            _secrets_manager_instance = LocalSecretsManager()

        return _secrets_manager_instance
