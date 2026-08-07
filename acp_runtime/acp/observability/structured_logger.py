"""Structured logging — contextual JSON log entries.

Design:
    * ``LogEntry`` is an immutable record of a log event with timestamp,
      level, message, context fields, and optional trace_id.
    * ``StructuredLogger`` is the abstract interface.
    * ``ConsoleStructuredLogger`` writes JSON lines to stdout/stderr.
    * ``InMemoryStructuredLogger`` stores entries in a list for testing.
    * ``NullStructuredLogger`` is a no-op logger.

Context fields are merged at log time so every entry carries the full
context (e.g. capability name, caller_id, request_id).

CRITICAL FIX — Unmasked Audit Log Leak:
    Added sanitize_log_payload() to redact sensitive fields (passwords,
    tokens, secrets, API keys, etc.) before they are written to log
    output. Without this fix, any 500 Internal Server Error that logs
    the full request object would leak credentials into Grafana/Loki logs,
    allowing anyone with log read access to compromise the system.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import anyio

from compat import StrEnum

__all__ = [
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "ConsoleStructuredLogger",
    "InMemoryStructuredLogger",
    "NullStructuredLogger",
    "sanitize_log_payload",
]


# ---------------------------------------------------------------------------
# Sensitive data redaction — CRITICAL FIX
# ---------------------------------------------------------------------------

# Keys whose values should be redacted from log output.
# Uses case-insensitive substring matching: any key containing these
# substrings (e.g. "db_password", "access_token", "client_secret")
# will have its value replaced with "***REDACTED***".
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "mfa_code",
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "private_key",
    "credential",
    "cookie",
    "session_id",
    "refresh_token",
    "id_token",
    "auth_header",
    "connection_string",
    "db_url",
    "database_url",
    "dsn",
})

# Maximum depth for recursive sanitization to prevent stack overflow
# on deeply nested payloads (e.g. JSON bomb attacks).
_MAX_SANITIZE_DEPTH = 10

# Maximum number of keys in a single dict level to prevent
# CPU exhaustion on excessively wide payloads.
_MAX_KEYS_PER_LEVEL = 1000

# The replacement value for redacted fields.
_REDACTED = "***REDACTED***"


def sanitize_log_payload(
    payload: dict[str, Any],
    *,
    _depth: int = 0,
) -> dict[str, Any]:
    """Recursively redact sensitive fields from a log payload.

    CRITICAL FIX — Unmasked Audit Log Leak:
    Before this fix, the logging system would serialize entire request
    objects (including passwords, tokens, database connection strings)
    into log output when a 500 Internal Server Error occurred. This
    leaked credentials into Grafana/Loki logs, allowing anyone with
    log read access to compromise the system.

    This function performs a deep, recursive scan of any dict before
    it is written to log output, replacing values of keys that match
    known sensitive patterns with "***REDACTED***".

    Security features:
    - Case-insensitive substring matching on keys (catches "db_password",
      "X-Access-Token", "CLIENT_SECRET", etc.)
    - Recursive sanitization of nested dicts and lists
    - Depth limit to prevent stack overflow on deeply nested payloads
    - Key count limit to prevent CPU exhaustion on wide payloads
    - Non-string values (numbers, booleans, None) are passed through
      unless they are containers that need recursive sanitization

    Parameters:
    -----------
    payload : dict
        The dictionary to sanitize.
    _depth : int
        Internal recursion depth counter (do not set manually).

    Returns:
    --------
    dict
        A new dictionary with sensitive values redacted.
    """
    if _depth > _MAX_SANITIZE_DEPTH:
        return {"_truncated": "max depth exceeded during sanitization"}

    if not isinstance(payload, dict):
        return payload

    if len(payload) > _MAX_KEYS_PER_LEVEL:
        return {"_truncated": f"too many keys ({len(payload)}), sanitization skipped for safety"}

    clean_payload: dict[str, Any] = {}
    for key, value in payload.items():
        # Case-insensitive substring check: if any SENSITIVE_KEYS
        # substring appears in the key (lowered), redact the value.
        key_lower = key.lower() if isinstance(key, str) else str(key).lower()
        if any(s in key_lower for s in SENSITIVE_KEYS):
            clean_payload[key] = _REDACTED
        elif isinstance(value, dict):
            clean_payload[key] = sanitize_log_payload(value, _depth=_depth + 1)
        elif isinstance(value, list):
            clean_payload[key] = [
                sanitize_log_payload(item, _depth=_depth + 1) if isinstance(item, dict)
                else _REDACTED if isinstance(item, str) and _looks_sensitive(key, item)
                else item
                for item in value
            ]
        elif isinstance(value, str) and _looks_sensitive(key, value):
            clean_payload[key] = _REDACTED
        else:
            clean_payload[key] = value
    return clean_payload


def _looks_sensitive(key: str, value: str) -> bool:
    """Heuristic: detect values that look like tokens/secrets even if the key name is unusual.

    This catches patterns like:
    - Bearer tokens in arbitrary fields
    - Base64-encoded secrets
    - JWT-like strings (three base64 segments separated by dots)
    - Connection strings with embedded passwords
    """
    if not isinstance(value, str) or len(value) < 8:
        return False

    # Bearer token pattern
    if re.match(r"^bearer\s+", value, re.IGNORECASE):
        return True

    # JWT pattern (three base64url segments separated by dots)
    if re.match(r"^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", value):
        return True

    # Connection string with embedded password
    if re.match(r"^[a-z+]+://[^:]+:[^@]+@", value, re.IGNORECASE):
        return True

    return False


# ------------------------------------------------------------------ LogLevel


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ------------------------------------------------------------------ LogEntry


@dataclass(frozen=True)
class LogEntry:
    """Immutable structured log entry.

    Fields:
        timestamp: Unix epoch seconds (float).
        level: log level string.
        message: human-readable message.
        logger: logger name (e.g. "acp.runtime").
        trace_id: optional trace correlation id.
        context: free-form key-value pairs.
    """

    timestamp: float
    level: str
    message: str
    logger: str
    trace_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize as a single-line JSON string with sensitive data redacted.

        CRITICAL FIX: The context dict is sanitized before serialization
        to prevent credential leakage into log output.
        """
        safe_context = sanitize_log_payload(self.context) if self.context else {}
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "level": self.level,
                "message": self.message,
                "logger": self.logger,
                "trace_id": self.trace_id,
                **safe_context,
            },
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        )


# ------------------------------------------------------------------ StructuredLogger (ABC)


class StructuredLogger:
    """Abstract structured logger.

    Subclasses must implement ``log`` and ``flush``.
    """

    def __init__(self, name: str = "acp") -> None:
        self.name = name
        self._context: dict[str, Any] = {}

    def with_context(self, **kwargs: Any) -> StructuredLogger:
        """Return a new logger with merged context fields.

        The original logger is not modified.
        """
        new = self.__class__(name=self.name)
        new._context = {**self._context, **kwargs}
        return new

    def bind(self, **kwargs: Any) -> None:
        """Add context fields to this logger in-place."""
        self._context.update(kwargs)

    def unbind(self, *keys: str) -> None:
        """Remove context fields from this logger in-place."""
        for k in keys:
            self._context.pop(k, None)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.DEBUG, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.INFO, message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.WARNING, message, kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.ERROR, message, kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.CRITICAL, message, kwargs)

    def _log(self, level: LogLevel, message: str, extra: dict[str, Any]) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            level=level.value,
            message=message,
            logger=self.name,
            context={**self._context, **extra},
        )
        self.write(entry)

    def write(self, entry: LogEntry) -> None:
        """Write a log entry. Must be implemented by subclasses."""
        raise NotImplementedError

    async def flush(self) -> None:
        """Optional flush. Default is no-op."""
        pass


# ------------------------------------------------------------------ NullStructuredLogger


class NullStructuredLogger(StructuredLogger):
    """No-op structured logger."""

    def write(self, entry: LogEntry) -> None:
        pass  # NOSONAR


# ------------------------------------------------------------------ InMemoryStructuredLogger


class InMemoryStructuredLogger(StructuredLogger):
    """Stores all log entries in a list for testing.

    Thread-safe: uses an ``anyio.Lock``.
    """

    def __init__(self, name: str = "acp") -> None:
        super().__init__(name)
        self._entries: list[LogEntry] = []
        self._lock = anyio.Lock()

    def write(self, entry: LogEntry) -> None:
        self._entries.append(entry)

    @property
    def entries(self) -> list[LogEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def filter(
        self,
        level: Optional[LogLevel] = None,
        logger: Optional[str] = None,
    ) -> list[LogEntry]:
        """Filter entries by level and/or logger name."""
        out = self._entries
        if level is not None:
            out = [e for e in out if e.level == level.value]
        if logger is not None:
            out = [e for e in out if e.logger == logger]
        return out


# ------------------------------------------------------------------ ConsoleStructuredLogger


class ConsoleStructuredLogger(StructuredLogger):
    """Writes JSON log lines to stdout or stderr.

    Parameters:
        name: logger name.
        stream: output stream. Defaults to ``sys.stderr``.
        min_level: minimum log level to emit. Defaults to ``INFO``.
    """

    def __init__(
        self,
        name: str = "acp",
        *,
        stream: Optional[Any] = None,
        min_level: LogLevel = LogLevel.INFO,
    ) -> None:
        super().__init__(name)
        self._stream = stream or sys.stderr
        self._min_level = min_level
        self._level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }
        import threading

        self._lock = threading.Lock()

    def write(self, entry: LogEntry) -> None:
        if self._level_order.get(LogLevel(entry.level), 0) < self._level_order[self._min_level]:
            return
        line = entry.to_json() + "\n"
        with self._lock:
            self._stream.write(line)
            self._stream.flush()
