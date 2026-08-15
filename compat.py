"""Python version compatibility shims.

Project target: Python 3.12+ (declared in pyproject.toml).
All backports have been removed since the minimum Python version
guarantees availability of StrEnum (3.11+) and asyncio.to_thread (3.9+).
"""

from asyncio import to_thread  # noqa: F401
from enum import StrEnum  # noqa: F401

__all__ = ["StrEnum", "to_thread"]
