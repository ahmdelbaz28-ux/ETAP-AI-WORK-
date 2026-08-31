"""Digital Twin Endpoints API Router — /api/v1/digital-twin/*

Modular home for the digital-twin synchronization endpoints. Migrated in P8
(Advanced Routes Migration) from the legacy inline handlers in ``api/routes.py``
(which remain available as a separate copy in ``hf-space/app.py`` for the HF
entry point).

Security: the router declares :func:`api.dependencies.get_api_key` as a
router-level dependency (SECURITY AUDIT R7-1). That is the repository-wide
canonical guard used by the other modular routers (equipment, export,
templates, ...): it validates the ``X-API-Key`` header and/or a valid JWT
bearer access token. P8 preserves the legacy S-15 requirement that this
endpoint is never public — missing credentials are rejected with HTTP 401.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api._messages import ISO_8601_UTC_FMT, MSG_INTERNAL_ERROR
from api.dependencies import get_api_key

logger = logging.getLogger("engineering_service")

router = APIRouter(
    prefix="/api/v1/digital-twin",
    tags=["Digital Twin"],
    dependencies=[Depends(get_api_key)],
)  # SECURITY AUDIT R7-1


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 'Z' timestamp."""
    return time.strftime(ISO_8601_UTC_FMT, time.gmtime())


@router.get("/status")
async def digital_twin_status(request: Request):
    """Return the digital-twin sync status.

    The digital twin is a logical mirror of the physical SCADA network.
    Without a real SCADA feed the twin is in `STANDBY` mode: schema loaded,
    no live measurements ingested.

    SECURITY AUDIT S-15: requires authentication (router-level ``get_api_key``).
    P8 migration: moved from the ``api/routes.py`` inline handler to this modular
    router; the HTTP contract actually served (path, response body consumed by
    ``ui/src/pages/DigitalTwin.tsx``, status codes) is preserved exactly.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        return {
            "success": True,
            "data": {
                "timestamp": _utc_now_iso(),
                "state": "STANDBY",
                "schema_version": "1.0.0",
                "nodes": 0,
                "edges": 0,
                "last_sync": None,
                "deployment_note": (
                    "Digital-twin live sync requires a real SCADA feed (Zenon / IEC 61850). "
                    "Without it the twin schema is loaded but no measurements are ingested."
                ),
            },
        }
    except Exception as exc:  # pragma: no cover - defensive parity with api/scada.py
        logger.exception("digital_twin_status_failed error=%s", exc, extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )
