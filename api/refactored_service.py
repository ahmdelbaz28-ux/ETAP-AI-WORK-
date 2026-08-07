"""
api/refactored_service.py — DEPRECATED: use api.routes instead.

MEDIUM #17 (AhmedETAP_Error_Report_AR.pdf):
This file previously created a DUPLICATE FastAPI app (2237 lines) that ran
alongside the canonical ``api.routes:app``. Having two FastAPI apps made it
unclear which entry point was canonical and caused deployment confusion
(HF Space used hf-space/app.py, engineering-service used api/routes.py,
and this file was imported by nobody but still shipped in the image).

This file is now a thin DEPRECATED stub. It re-exports ``app`` from
``api.routes`` so any lingering imports still work, and emits a
DeprecationWarning directing callers to migrate.

New code MUST import from api.routes directly:
    from api.routes import app  # ✅ canonical

Old code that imported from here will still work but will see a warning:
    from api.refactored_service import app  # ❌ deprecated

The full original implementation (2237 lines) was removed in the
MEDIUM #17 cleanup. Its functionality is fully covered by api/routes.py
+ api/health.py + api/agents.py + api/studies.py + api/auth.py etc.
"""

from __future__ import annotations

import warnings

# Re-export the canonical app so any lingering imports still work.
from api.routes import app  # noqa: F401 — re-exported for backward compat

# Emit a DeprecationWarning so callers know to migrate.
warnings.warn(
    "api.refactored_service is DEPRECATED. Import from api.routes instead. "
    "See MEDIUM #17 in AhmedETAP_Error_Report_AR.pdf. "
    "The duplicate FastAPI app has been removed; this module now re-exports "
    "api.routes.app for backward compatibility.",
    DeprecationWarning,
    stacklevel=2,
)

# Explicit __all__ so `from api.refactored_service import *` only exposes `app`.
__all__ = ["app"]
