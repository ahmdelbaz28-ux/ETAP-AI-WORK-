# API routers are imported explicitly by api/routes.py to avoid
# eager loading of all modules on any import of api.*

import datetime
import sys
import typing

# datetime.UTC and typing.Annotated are available in Python 3.11+.
# The project requires Python 3.12+ (pyproject.toml) in production, but local
# testing may run on Python <3.11. The polyfill is restored with a noqa comment
# to suppress Ruff UP017 checks.
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc  # type: ignore  # noqa: UP017


if not hasattr(typing, "Annotated"):
    from typing_extensions import Annotated
    typing.Annotated = Annotated
    sys.modules['typing'].Annotated = Annotated

