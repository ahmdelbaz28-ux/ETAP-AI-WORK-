"""Audit logging — append-only, structured, and async-safe.

Every audit entry is a single line of JSON (NDJSON) written to a file.
The logger is designed to be lightweight: it uses ``anyio.to_thread.run_sync``
for disk I/O so the event loop is never blocked.

Features:
    * Structured JSON entries with timestamp, method, capability, caller_id,
      outcome, duration_ms, error_code, trace_id.
    * Async-safe file writes with a lock.
    * Optional log rotation by size or time (simple, no external deps).
    * Optional in-memory buffer for testing.
"""
from __future__ import annotations
from typing import Any
import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

import anyio

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "InMemoryAuditLogger",
    "NDJSONAuditLogger",
]


# ------------------------------------------------------------------ AuditEntry

@dataclass(frozen=True, slots=True)
class AuditEntry:
    """A single audit log entry.

    Fields:
        timestamp: Unix epoch seconds (float, from ``time.time()``).
        method: JSON-RPC method name.
        capability: ACP capability name.
        caller_id: authenticated caller identifier (or empty string).
        outcome: one of "success", "error", "denied", "notification".
        duration_ms: elapsed time in milliseconds (0 if unknown).
        error_code: JSON-RPC error code (or 0 for success / notifications).
        trace_id: opaque correlation id.
        metadata: free-form dict for extra fields (e.g. client_ip).
    """

    timestamp: float
    method: str
    capability: str
    caller_id: str
    outcome: str
    duration_ms: int = 0
    error_code: int = 0
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize as a single-line JSON string."""
        return json.dumps(asdict(self), default=str, separators=(",", ":"), sort_keys=True)


# ------------------------------------------------------------------ AuditLogger (ABC)

class AuditLogger:
    """Abstract base for audit loggers.

    Subclasses must implement ``write(entry: AuditEntry)``.
    """

    async def log(
        self,
        *,
        method: str,
        capability: str,
        caller_id: str = "",
        outcome: str,
        duration_ms: int = 0,
        error_code: int = 0,
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method: build an ``AuditEntry`` and write it."""
        entry = AuditEntry(
            timestamp=time.time(),
            method=method,
            capability=capability,
            caller_id=caller_id,
            outcome=outcome,
            duration_ms=duration_ms,
            error_code=error_code,
            trace_id=trace_id,
            metadata=metadata or {},
        )
        await self.write(entry)

    async def write(self, entry: AuditEntry) -> None:
        """Write a single audit entry. Must be implemented by subclasses."""
        raise NotImplementedError

    async def close(self) -> None:
        """Optional lifecycle hook. Default is no-op."""
        pass


# ------------------------------------------------------------------ InMemoryAuditLogger

class InMemoryAuditLogger(AuditLogger):
    """Audit logger that stores entries in a list for testing.

    Thread-safe: uses an ``anyio.Lock`` around append.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._lock = anyio.Lock()

    async def write(self, entry: AuditEntry) -> None:
        async with self._lock:
            self._entries.append(entry)

    @property
    def entries(self) -> list[AuditEntry]:
        """Snapshot of the current entries."""
        return list(self._entries)

    def clear(self) -> None:
        """Reset the buffer (sync, safe for tests)."""
        self._entries.clear()


# ------------------------------------------------------------------ NDJSONAuditLogger

class NDJSONAuditLogger(AuditLogger):
    """Append-only NDJSON audit logger to a file on disk.

    Parameters:
        path: file path. Parent directories are created automatically.
        max_bytes: optional rotation threshold. When the file exceeds
            this size, it is rotated to ``<path>.1``, ``<path>.2``, etc.
        max_backups: how many rotated files to keep (default 3).
        encoding: file encoding (default "utf-8").

    The logger is async-safe: a lock serializes all writes.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 0,
        max_backups: int = 3,
        encoding: str = "utf-8",
    ) -> None:
        self._path = Path(path)
        self._max_bytes = max_bytes
        self._max_backups = max_backups
        self._encoding = encoding
        self._lock = anyio.Lock()
        self._closed = False

    async def write(self, entry: AuditEntry) -> None:
        if self._closed:
            return
        async with self._lock:
            await anyio.to_thread.run_sync(self._rotate_if_needed)
            line = entry.to_json() + "\n"
            await anyio.to_thread.run_sync(
                self._append_line,
                line,
            )

    async def close(self) -> None:
        self._closed = True

    # ---------------------------------------------------------- internals

    def _append_line(self, line: str) -> None:
        """Append a line to the log file (sync, called via to_thread)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding=self._encoding) as f:
            f.write(line)

    def _rotate_if_needed(self) -> None:
        """Check size and rotate if necessary. Called under lock via to_thread."""
        if self._max_bytes <= 0:
            return
        if not self._path.exists():
            return
        if self._path.stat().st_size < self._max_bytes:
            return

        # Rotate: move <path>.N to <path>.N+1, then move <path> to <path>.1
        for i in range(self._max_backups, 0, -1):
            src = self._path.with_suffix(f"{self._path.suffix}.{i}")
            dst = self._path.with_suffix(f"{self._path.suffix}.{i + 1}")
            if src.exists():
                if i == self._max_backups:
                    src.unlink()
                else:
                    src.replace(dst)

        self._path.replace(self._path.with_suffix(f"{self._path.suffix}.1"))
