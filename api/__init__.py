# API routers are imported explicitly by api/routes.py to avoid
# eager loading of all modules on any import of api.*

import datetime
import sys
import typing

if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc

if not hasattr(typing, "Annotated"):
    from typing_extensions import Annotated
    typing.Annotated = Annotated
    sys.modules['typing'].Annotated = Annotated

