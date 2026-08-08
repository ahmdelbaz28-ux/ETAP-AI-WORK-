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

api/refactored_service.py — Refactored Engineering Service with modular architecture.

This file demonstrates how the monolithic ``engineering_service.py`` should be
refactored into a properly modular FastAPI application. It imports and mounts
existing API routers, adds missing study-type dispatchers, removes duplicate
endpoints, wires up WebSocket with authentication, adds proper dependency
injection, OpenAPI tags, request/response logging middleware, and removes
dead code.

Key improvements over the monolithic version:
  1. Replace global mutable state with ``app.state`` management
  2. Add missing study-type dispatchers (motor_starting, harmonic_analysis, optimal_power_flow)
  3. Remove duplicate RASP stats endpoint
  4. Wire up the WebSocket endpoint with authentication
  5. Add proper dependency injection for cache, engine, and providers
  6. Add OpenAPI tags for documentation grouping
  7. Add request/response logging middleware
  8. Remove dead code (unreachable WebSocket ConnectionManager)

Run::

    uvicorn api.refactored_service:app --host 0.0.0.0 --port 8000
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
