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
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import anyio

from compat import StrEnum

__all__ = [
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "ConsoleStructuredLogger",
    "InMemoryStructuredLogger",
    "NullStructuredLogger",
]


# ------------------------------------------------------------------ LogLevel


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ------------------------------------------------------------------ LogEntry


@dataclass(frozen=True, slots=True)
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
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "level": self.level,
                "message": self.message,
                "logger": self.logger,
                "trace_id": self.trace_id,
                **self.context,
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
        pass


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

    def filter(self, level: LogLevel | None = None, logger: str | None = None) -> list[LogEntry]:
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
        stream: Any | None = None,
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
