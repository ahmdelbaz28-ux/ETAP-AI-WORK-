"""
core/security_logging.py — Tamper-evident Security Audit Logging System.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
from pathlib import Path
import re
import threading
from typing import Any
import uuid

UTC = timezone.utc

_LOG_DIR = Path("logs")
_SECURITY_GENESIS = "0" * 64


class SecurityEventType(str, Enum):
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    AUTH_KEY_ROTATION = "AUTH_KEY_ROTATION"
    CORS_VIOLATION = "CORS_VIOLATION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INPUT_VALIDATION_FAILURE = "INPUT_VALIDATION_FAILURE"
    HMAC_INTEGRITY_FAILURE = "HMAC_INTEGRITY_FAILURE"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    SUBPROCESS_EXECUTION = "SUBPROCESS_EXECUTION"
    EVIDENCE_PACKAGE_CREATED = "EVIDENCE_PACKAGE_CREATED"
    EVIDENCE_PACKAGE_VERIFIED = "EVIDENCE_PACKAGE_VERIFIED"
    SECURITY_SCAN_RESULT = "SECURITY_SCAN_RESULT"
    PLACEHOLDER_KEY_DETECTED = "PLACEHOLDER_KEY_DETECTED"
    WILDCARD_ORIGIN_REJECTED = "WILDCARD_ORIGIN_REJECTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


# Patterns for mask_sensitive
_SENSITIVE_KEY_NAMES = {
    "api_key",
    "token",
    "password",
    "auth_key",
    "secret",
    "current_password",
    "jwt",
    "access_token",
    "refresh_token",
    "private_key",
}

_SENSITIVE_KEY_PATTERNS = [
    # Key-value redaction patterns (e.g. credentials and tokens)
    (
        re.compile(
            r'(?i)\b(api_key|token|password|auth_key|secret|credential|access_token|refresh_token)\s*=\s*["\']([A-Za-z0-9_\-\.]{8,})["\']'
        ),
        r'\1="***REDACTED***"',
    ),
    # Bearer token
    (
        re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_\-\.]{8,})"),
        r"Bearer ***REDACTED***",
    ),
]

_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-\.]{8,}\b"),
]


def mask_sensitive(text: Any, mask: str = "***REDACTED***") -> str:
    """Mask sensitive credentials in text while preserving non-sensitive hashes and fields."""
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    if not text:
        return ""

    result = text
    for pattern, repl in _SENSITIVE_KEY_PATTERNS:
        custom_repl = repl.replace("***REDACTED***", mask)
        result = pattern.sub(custom_repl, result)

    for val_pattern in _SENSITIVE_VALUE_PATTERNS:
        result = val_pattern.sub(mask, result)

    return result


def _sanitize_value(val: Any, mask: str = "***REDACTED***") -> Any:
    """Recursively mask sensitive keys and patterns in nested data structures."""
    if isinstance(val, dict):
        sanitized_dict: dict[str, Any] = {}
        for k, v in val.items():
            key_str = str(k)
            if key_str.lower() in _SENSITIVE_KEY_NAMES:
                sanitized_dict[key_str] = mask
            else:
                sanitized_dict[key_str] = _sanitize_value(v, mask)
        return sanitized_dict
    if isinstance(val, list):
        return [_sanitize_value(item, mask) for item in val]
    if isinstance(val, tuple):
        return tuple(_sanitize_value(item, mask) for item in val)
    if isinstance(val, set):
        return {_sanitize_value(item, mask) for item in val}
    if isinstance(val, str):
        return mask_sensitive(val, mask)
    return val


class SensitiveDataFilter(logging.Filter):
    """Logging filter that masks sensitive credentials in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive(record.msg)
        elif isinstance(record.msg, (dict, list, tuple, set)):
            record.msg = _sanitize_value(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _sanitize_value(v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _sanitize_value(v) for v in record.args
                )
        return True


def _compute_chain_hash(event_json: str) -> str:
    """Compute deterministic chain hash (truncated to 32 hex chars)."""
    hmac_key = os.environ.get("AUDIT_HMAC_KEY")
    if hmac_key:
        digest = hmac.new(
            hmac_key.encode("utf-8"),
            event_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    else:
        digest = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
    return digest[:32]


class SecurityAuditLogger:
    """Tamper-evident append-only security audit logger."""

    def __init__(self, log_dir: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        if log_dir is None:
            self._log_dir = Path(_LOG_DIR)
        else:
            self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "security_audit.log"
        self._chain_hash = self._recover_chain_hash()

    def _recover_chain_hash(self) -> str:
        """Recover last chain hash from log file or return genesis in O(1) memory."""
        if not self._log_path.exists():
            return _SECURITY_GENESIS
        try:
            last_line = ""
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
            if not last_line:
                return _SECURITY_GENESIS
            json.loads(last_line)
            return _compute_chain_hash(last_line)
        except Exception:
            return _SECURITY_GENESIS

    def log_event(self, event_type: str | SecurityEventType, **kwargs: Any) -> str:
        """Log a security event to the audit log."""
        event_type_str = str(event_type.value if isinstance(event_type, Enum) else event_type)
        with self._lock:
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(UTC).isoformat()
            # Recursively mask sensitive values in details
            masked_details: dict[str, Any] = {}
            for k, v in kwargs.items():
                if k.lower() in _SENSITIVE_KEY_NAMES:
                    masked_details[k] = "***REDACTED***"
                else:
                    masked_details[k] = _sanitize_value(v)

            event_record = {
                "event_id": event_id,
                "timestamp": timestamp,
                "event_type": event_type_str,
                "chain_hash": self._chain_hash,
                "details": masked_details,
            }
            json_str = json.dumps(event_record, sort_keys=True)
            self._chain_hash = _compute_chain_hash(json_str)

            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json_str + "\n")

            return event_id

    def verify_chain(self) -> dict[str, Any]:
        """Verify the cryptographic integrity of the audit log chain via streaming."""
        with self._lock:
            if not self._log_path.exists():
                return {"valid": True, "entries_checked": 0, "first_break": None}

            entries_count = 0
            expected_chain_hash = _SECURITY_GENESIS
            with open(self._log_path, "r", encoding="utf-8") as f:
                for idx, raw_line in enumerate(f):
                    line = raw_line.strip()
                    if not line:
                        continue
                    entries_count += 1
                    try:
                        data = json.loads(line)
                        if data.get("chain_hash") != expected_chain_hash:
                            return {"valid": False, "entries_checked": entries_count, "first_break": idx}
                        expected_chain_hash = _compute_chain_hash(line)
                    except Exception:
                        return {"valid": False, "entries_checked": entries_count, "first_break": idx}

            return {"valid": True, "entries_checked": entries_count, "first_break": None}


def configure_log_rotation(logger: logging.Logger, log_file: str = "etap.log") -> None:
    """Configure rotating file handler, skipping security_audit.log."""
    if log_file == "security_audit.log":
        return
    log_path = Path(_LOG_DIR) / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for existing_handler in logger.handlers:
        if isinstance(existing_handler, RotatingFileHandler) and getattr(existing_handler, "baseFilename", None) == str(log_path.resolve()):
            return
    handler = RotatingFileHandler(log_path, maxBytes=500 * 1024 * 1024, backupCount=10, encoding="utf-8")
    logger.addHandler(handler)


def configure_timed_rotation(logger: logging.Logger, log_file: str = "etap.log") -> None:
    """Configure timed rotating file handler, skipping security_audit.log."""
    if log_file == "security_audit.log":
        return
    log_path = Path(_LOG_DIR) / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for existing_handler in logger.handlers:
        if isinstance(existing_handler, TimedRotatingFileHandler) and getattr(existing_handler, "baseFilename", None) == str(log_path.resolve()):
            return
    handler = TimedRotatingFileHandler(log_path, when="D", interval=1, backupCount=30, encoding="utf-8")
    logger.addHandler(handler)
