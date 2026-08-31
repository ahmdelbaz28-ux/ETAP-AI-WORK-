"""SCADA Endpoints API Router — /api/v1/scada/*

Modular home for the SCADA data endpoints. Migrated in P8 (Advanced Routes
Migration) from the legacy inline handlers in ``api/routes.py`` (which remain
available as a separate copy in ``hf-space/app.py`` for the HF entry point).

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
    prefix="/api/v1/scada",
    tags=["SCADA"],
    dependencies=[Depends(get_api_key)],
)  # SECURITY AUDIT R7-1


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 'Z' timestamp."""
    return time.strftime(ISO_8601_UTC_FMT, time.gmtime())


@router.get("/live")
async def scada_live(request: Request):
    """Return a snapshot of the latest SCADA telemetry.

    **WARNING**: This returns SIMULATED data unless a real Zenon/IEC 61850 feed is
    configured. On HF Space (cpu-basic, no Zenon runtime) this returns a deterministic
    synthetic snapshot. The ``is_simulated`` flag allows the frontend to display a
    red banner indicating non-production data. A real Zenon-backed deployment would
    replace this with ``scada_etap_consumer.get_live_snapshot()`` and set is_simulated=false.

    SECURITY AUDIT S-15: requires authentication (router-level ``get_api_key``).
    P8 migration: moved from the ``api/routes.py`` inline handler to this modular
    router; the HTTP contract actually served (path, response body consumed by
    ``ui/src/pages/ScadaIntegration.tsx``, status codes) is preserved exactly.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        return {
            "success": True,
            "is_simulated": True,
            "data": {
                "timestamp": _utc_now_iso(),
                "source": "synthetic",
                "points": [
                    {"tag": "BUS1.V", "value": 1.02, "unit": "pu", "quality": "GOOD"},
                    {"tag": "BUS1.F", "value": 50.0, "unit": "Hz", "quality": "GOOD"},
                    {"tag": "FEEDER1.I", "value": 412.5, "unit": "A", "quality": "GOOD"},
                    {"tag": "XF1.P", "value": 2.8, "unit": "MW", "quality": "GOOD"},
                    {"tag": "XF1.Q", "value": 0.9, "unit": "MVAR", "quality": "GOOD"},
                ],
            },
        }
    except Exception as exc:  # pragma: no cover - defensive parity with api/digital_twin.py
        logger.exception("scada_live_failed error=%s", exc, extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )
