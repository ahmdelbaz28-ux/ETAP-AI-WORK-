"""Python version compatibility shims.

Provides backports of Python 3.11+ features for Python 3.8 compatibility.
Project target: Python 3.12+
"""

import asyncio
import contextvars
import functools
import sys
from enum import Enum

__all__ = ["StrEnum", "to_thread"]

if sys.version_info >= (3, 11):  # noqa: UP036
    from enum import StrEnum  # noqa: F401
else:

    class StrEnum(str, Enum):  # type: ignore  # noqa: UP042
        """Backport of Python 3.11's ``enum.StrEnum``."""

        pass


# Backport of asyncio.to_thread for Python 3.8
if sys.version_info >= (3, 9):  # noqa: UP036
    from asyncio import to_thread  # noqa: F401
else:

    async def to_thread(func, /, *args, **kwargs):  # type: ignore
        """Asynchronously run function ``func`` in a separate thread."""
        loop = asyncio.get_running_loop()
        ctx = contextvars.copy_context()
        func_call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)
