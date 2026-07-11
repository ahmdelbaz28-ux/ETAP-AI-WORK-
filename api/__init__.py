# API routers are imported explicitly by api/routes.py to avoid
# eager loading of all modules on any import of api.*

import datetime
import sys
import typing

# datetime.UTC and typing.Annotated are available in Python 3.11+.
# The project requires Python 3.12+ (pyproject.toml), so the legacy
# polyfill branches are no longer needed. They were left over from
# earlier Python 3.9/3.10 support and were flagged by ruff UP017
# (use datetime.UTC alias instead of datetime.timezone.utc).

if not hasattr(typing, "Annotated"):
    from typing_extensions import Annotated
    typing.Annotated = Annotated
    sys.modules['typing'].Annotated = Annotated

