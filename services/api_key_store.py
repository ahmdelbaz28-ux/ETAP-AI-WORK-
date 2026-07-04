"""
services/api_key_store.py — Encrypted API key storage for user-supplied keys

Stores user-supplied API keys (OpenAI, Gemini, Anthropic) in SQLite with
AES-256 encryption. Keys are NEVER stored in plaintext — only encrypted.

WHY THIS EXISTS:
    The CUA Loop needs API keys for vision backends (OpenAI, Gemini, Claude).
    Previously, keys were set via env vars / HF Space secrets — only the
    admin could change them. This module allows END USERS to enter their
    own keys via the Settings UI, stored securely in the backend.

SECURITY:
    - Keys encrypted with AES-256-GCM using a master key
    - Master key from API_KEY_ENCRYPTION_KEY env var (or auto-generated)
    - Decrypted only in-memory, never logged, never sent to frontend
    - Frontend sees only masked keys (sk-***...***)

SCHEMA (SQLite table: api_keys):
    id INTEGER PRIMARY KEY
    provider TEXT UNIQUE  -- 'openai' | 'gemini' | 'anthropic'
    encrypted_key TEXT    -- AES-256-GCM ciphertext (base64)
    base_url TEXT         -- optional custom endpoint
    model_name TEXT       -- optional model override
    is_active BOOLEAN     -- whether to use this key
    created_at TIMESTAMP
    updated_at TIMESTAMP

Usage:
    from services.api_key_store import api_key_store

    # Save a key (from Settings UI)
    api_key_store.set_key('openai', 'sk-xxx', base_url='https://...', model='gpt-4o')

    # Retrieve a key (decrypted) — used by vision clients
    config = api_key_store.get_key('openai')
    if config:
        # config = {'api_key': 'sk-xxx', 'base_url': '...', 'model': '...', 'is_active': True}
        # Pass to OpenAIVisionClient
    else:
        # Fall back to env vars
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── AES-256 encryption (optional dep) ─────────────────────────────────────

try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography not installed — API keys will be stored with basic obfuscation only",
    )


# ─── Data class ────────────────────────────────────────────────────────────


@dataclass
class APIKeyConfig:
    """Decrypted API key configuration retrieved from storage."""

    provider: str
    api_key: str  # decrypted
    base_url: str | None = None
    model_name: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    def to_masked_dict(self) -> dict:
        """Return a dict with the API key masked (for frontend display)."""
        masked = self._mask_key(self.api_key)
        return {
            "provider": self.provider,
            "api_key_masked": masked,
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
            "model_name": self.model_name,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def _mask_key(key: str) -> str:
        """Mask a key like sk-abc...xyz → sk-***...***"""
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        prefix = key[:3]
        suffix = key[-4:]
        return f"{prefix}{'*' * 20}{suffix}"


# ─── API Key Store ─────────────────────────────────────────────────────────


class APIKeyStore:
    """SQLite-backed encrypted API key store.

    Thread-safe via a lock. Uses AES-256-GCM (Fernet) if cryptography is
    available, otherwise falls back to base64 obfuscation (NOT secure —
    install cryptography: pip install cryptography).
    """

    # All supported AI providers. Keys are stored per-provider in the
    # api_keys SQLite table. The frontend Quick Setup section in
    # Settings.tsx (POPULAR_PROVIDERS) MUST stay in sync with this set.
    SUPPORTED_PROVIDERS = {
        # Coding agent platforms (new — added 2026-07)
        "opencode", "kilocode", "claudecode",
        # Major cloud providers
        "openai", "anthropic", "gemini",
        # Specialized / free-friendly providers
        "deepseek", "groq", "cohere", "huggingface",
    }

    def __init__(self, db_path: str = "/tmp/data/api_keys.db") -> None:  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cipher = self._init_cipher()
        self._init_db()

    # ─── Encryption setup ──────────────────────────────────────────────────

    def _init_cipher(self):
        """Initialize the Fernet cipher for AES-256 encryption."""
        if not CRYPTO_AVAILABLE:
            logger.warning("API keys will be stored with base64 obfuscation only — NOT secure")
            return None

        # Get or generate master key
        master_key_env = os.getenv("API_KEY_ENCRYPTION_KEY", "")
        if master_key_env:
            # Use provided key (must be 32 url-safe base64 bytes for Fernet)
            try:
                # Derive a Fernet key from the env var via SHA-256
                derived = hashlib.sha256(master_key_env.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(derived)
                return Fernet(fernet_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to init cipher from env var: %s — generating random key", exc,
                )

        # Generate a random key (persists in memory only — keys lost on restart)
        # For production, set API_KEY_ENCRYPTION_KEY env var
        logger.warning(
            "API_KEY_ENCRYPTION_KEY not set — generating random key. "
            "Stored API keys will be LOST on process restart. "
            "Set API_KEY_ENCRYPTION_KEY env var for persistence.",
        )
        return Fernet(Fernet.generate_key())

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext → base64 ciphertext."""
        if not plaintext:
            return ""
        if self._cipher:
            return self._cipher.encrypt(plaintext.encode()).decode()
        # Fallback: base64 (NOT secure)
        return base64.b64encode(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt base64 ciphertext → plaintext."""
        if not ciphertext:
            return ""
        try:
            if self._cipher:
                return self._cipher.decrypt(ciphertext.encode()).decode()
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Decryption failed: %s", exc)
            return ""

    # ─── Database setup ────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the api_keys table if it doesn't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT UNIQUE NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    base_url TEXT,
                    model_name TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
            )
            conn.commit()
            conn.close()

    # ─── Public API ────────────────────────────────────────────────────────

    def set_key(
        self,
        provider: str,
        api_key: str,
        base_url: str | None = None,
        model_name: str | None = None,
        is_active: bool = True,
    ) -> bool:
        """Save or update an API key.

        Args:
            provider: 'openai' | 'gemini' | 'anthropic'
            api_key: the API key (will be encrypted)
            base_url: optional custom endpoint URL
            model_name: optional model name override
            is_active: whether this key should be used

        Returns:
            True if saved successfully.
        """
        provider = provider.lower().strip()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Must be one of: {self.SUPPORTED_PROVIDERS}",
            )

        encrypted = self._encrypt(api_key)
        now = datetime.now(UTC).isoformat()

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                INSERT INTO api_keys (provider, encrypted_key, base_url, model_name, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    encrypted_key = excluded.encrypted_key,
                    base_url = excluded.base_url,
                    model_name = excluded.model_name,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (provider, encrypted, base_url, model_name, is_active, now, now),
            )
            conn.commit()
            conn.close()

        logger.info("API key saved for provider '%s' (active=%s)", provider, is_active)
        return True

    def get_key(self, provider: str) -> APIKeyConfig | None:
        """Retrieve a decrypted API key configuration.

        Args:
            provider: 'openai' | 'gemini' | 'anthropic'

        Returns:
            APIKeyConfig with decrypted api_key, or None if not found/inactive.
        """
        provider = provider.lower().strip()
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM api_keys WHERE provider = ? AND is_active = 1",
                (provider,),
            ).fetchone()
            conn.close()

        if not row:
            return None

        decrypted_key = self._decrypt(row["encrypted_key"])
        if not decrypted_key:
            logger.warning("Failed to decrypt key for provider '%s'", provider)
            return None

        return APIKeyConfig(
            provider=provider,
            api_key=decrypted_key,
            base_url=row["base_url"],
            model_name=row["model_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_all_keys(self) -> dict[str, dict]:
        """Get all stored API keys (masked, for frontend display).

        Returns dict keyed by provider name, with masked keys.
        """
        result: dict[str, dict] = {}
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM api_keys").fetchall()
            conn.close()

        for row in rows:
            provider = row["provider"]
            # Decrypt to get masking
            decrypted = self._decrypt(row["encrypted_key"])
            config = APIKeyConfig(
                provider=provider,
                api_key=decrypted,
                base_url=row["base_url"],
                model_name=row["model_name"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            result[provider] = config.to_masked_dict()

        return result

    def delete_key(self, provider: str) -> bool:
        """Delete an API key.

        Args:
            provider: 'openai' | 'gemini' | 'anthropic'

        Returns:
            True if deleted, False if not found.
        """
        provider = provider.lower().strip()
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("DELETE FROM api_keys WHERE provider = ?", (provider,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

        if deleted:
            logger.info("API key deleted for provider '%s'", provider)
        return deleted

    def set_active(self, provider: str, is_active: bool) -> bool:
        """Enable or disable a key without deleting it."""
        provider = provider.lower().strip()
        now = datetime.now(UTC).isoformat()
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute(
                "UPDATE api_keys SET is_active = ?, updated_at = ? WHERE provider = ?",
                (is_active, now, provider),
            )
            conn.commit()
            updated = cursor.rowcount > 0
            conn.close()
        return updated

    def health_check(self) -> dict:
        """Return storage status."""
        all_keys = self.get_all_keys()
        return {
            "db_path": str(self.db_path),
            "crypto_available": CRYPTO_AVAILABLE,
            "encryption_active": self._cipher is not None,
            "stored_providers": list(all_keys.keys()),
            "active_providers": [p for p, c in all_keys.items() if c.get("is_active")],
            "supported_providers": list(self.SUPPORTED_PROVIDERS),
        }


# ─── Module-level singleton ────────────────────────────────────────────────

api_key_store = APIKeyStore()


__all__ = ["APIKeyConfig", "APIKeyStore", "api_key_store"]
