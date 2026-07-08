"""Transport abstract base class.

All ACP transports implement the same interface so the ``Server``
can drive them uniformly. The transport layer is responsible for:

    * Framing (line-delimited JSON, WebSocket text frames, etc.)
    * JSON serialisation / deserialisation
    * Connection lifecycle (open, close, EOF detection)

The transport layer does NOT handle JSON-RPC validation — that is the
router's job.
"""
from typing import Optional, Union

from __future__ import annotations

from abc import ABC, abstractmethod

__all__ = ["Transport"]


class Transport(ABC):
    """Abstract base for all ACP transports.

    Implementations must be thread-safe for concurrent read/write
    operations (e.g. using ``anyio.Lock``).
    """

    @abstractmethod
    async def read_message(self) -> Optional[str]:
        """Read a complete raw JSON-RPC message.

        Returns:
            A JSON string, or ``None`` on EOF / connection close.
        """
        ...

    @abstractmethod
    async def write_message(self, message: str) -> None:
        """Write a complete raw JSON-RPC message.

        Args:
            message: a JSON string to send. The transport is responsible
                for framing (e.g. appending ``\\n`` for line-delimited).
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the transport and release any resources."""
        ...