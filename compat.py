import asyncio
from enum import Enum

try:
    from asyncio import to_thread  # noqa: F401
except ImportError:
    import functools
    async def to_thread(func, /, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

try:
    from enum import StrEnum  # noqa: F401
except ImportError:
    class StrEnum(str, Enum):
        """Fallback StrEnum for Python < 3.11."""
        def __str__(self) -> str:
            return str(self.value)

__all__ = ["StrEnum", "to_thread"]

