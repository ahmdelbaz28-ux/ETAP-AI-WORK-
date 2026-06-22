"""
Python version compatibility shims.

Provides backports of Python 3.11+ features for Python 3.8 compatibility.
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum  # noqa: F811
else:

    class StrEnum(str, Enum):  # type: ignore
        """Backport of Python 3.11's ``enum.StrEnum``.

        ``StrEnum`` is an ``Enum`` whose members are also ``str``\ s.
        """

        def __str__(self) -> str:
            return self.value

        @staticmethod
        def _generate_next_value_(name: str, *args: object) -> str:
            return name.lower()
