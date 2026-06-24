"""
Python version compatibility shims.

Provides backports of Python 3.11+ features for Python 3.8 compatibility.
Project target: Python 3.12+
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):  # noqa: UP036
    from enum import StrEnum  # noqa: F401
else:

    class StrEnum(str, Enum):  # type: ignore  # noqa: UP042
        """Backport of Python 3.11's ``enum.StrEnum``."""

        pass
