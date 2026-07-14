"""Tests for security/secrets_manager.py utility functions."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from security.secrets_manager import _ensure_dir, _get_cipher


class TestUtilityFunctions:
    """Test standalone utility functions in secrets_manager."""

    def test_ensure_dir_creates_directory(self):
        """_ensure_dir should create the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "new_subdir" / "nested"
            result = _ensure_dir(test_dir)
            assert result == test_dir
            assert test_dir.exists()
            assert test_dir.is_dir()

    def test_ensure_dir_existing(self):
        """_ensure_dir should not fail if directory already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            result = _ensure_dir(test_dir)
            assert result == test_dir
            assert test_dir.exists()

    def test_get_cipher_generates_new_key(self):
        """_get_cipher should return a Fernet cipher with a new key when no key provided."""
        cipher, key = _get_cipher()
        assert key is not None
        assert len(key) > 0
        # Fernet keys are 32 URL-safe base64-encoded bytes
        assert isinstance(key, bytes)

    def test_get_cipher_with_provided_key(self):
        """_get_cipher should use the provided key."""
        from cryptography.fernet import Fernet

        pre_key = Fernet.generate_key()
        cipher, key = _get_cipher(pre_key)
        assert key == pre_key
        # Verify the cipher works
        test_data = b"test_secret_data"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == test_data
