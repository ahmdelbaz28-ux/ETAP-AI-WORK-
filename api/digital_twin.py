"""
Digital Twin Endpoints API Router
=================================
Handles all digital twin synchronization endpoints.
Separated from main engineering service for better modularity.
"""

<<<<<<< HEAD
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api._messages import MSG_INTERNAL_ERROR
from api.dependencies import get_api_key

router = APIRouter(
    prefix="/api/v1/digital-twin", tags=["digital_twin"], dependencies=[Depends(get_api_key)]
)  # SECURITY AUDIT R7-1

# ─── Coverage note (audit 2026-08-01) ───────────────────────────────────────
# Status: PLACEHOLDER — single GET /status endpoint exposing the shared state
# store / event bus / validation gateway. Full digital-twin CRUD (PUT /state,
# POST /events, DELETE /snapshots/{id}) lives in the upstream digital_twin/
# Python package and is invoked from the engineering service, NOT exposed
# via this router. Registering here so the UI status probe works.
=======
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/digital-twin", tags=["digital_twin"])
>>>>>>> origin/fix/scenario-tests-properly

# Global state stores for digital twin
_shared_state_store = None
_shared_event_bus = None
_shared_validation_gateway = None


@router.get("/status")
async def get_digital_twin_status(request: Request):
    """Return Digital Twin synchronization status and state store info."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from digital_twin.event_bus import EventBus
        from digital_twin.state_store import StateStore
        from digital_twin.validation_gateway import ValidationGateway

        global _shared_state_store, _shared_event_bus, _shared_validation_gateway
        if _shared_state_store is None:
            _shared_state_store = StateStore()
            _shared_event_bus = EventBus()
            _shared_validation_gateway = ValidationGateway()
        store = _shared_state_store

        # Get state store info
        state_info = {}
        if hasattr(store, "get_state"):
            state = store.get_state()
            state_info = {"entities": len(state) if isinstance(state, dict) else 0}
        elif hasattr(store, "state"):
            state_info = {"entities": len(store.state) if isinstance(store.state, dict) else 0}
        else:
            state_info = {"available": True}

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "state_store": state_info,
                    "event_bus": {"available": True},
                    "validation_gateway": {"available": True},
                    "sync_protocols": ["AWS IoT TwinMaker", "Azure Digital Twins"],
                    "supported_models": ["Substation", "Bus", "Line", "Transformer", "Generator"],
                },
                "trace_id": trace_id,
<<<<<<< HEAD
            },
=======
            }
>>>>>>> origin/fix/scenario-tests-properly
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
<<<<<<< HEAD
        logger.exception(
            "digital_twin_status_failed error=%s", str(e), extra={"trace_id": trace_id}
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
=======
        logger.error("digital_twin_status_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
>>>>>>> origin/fix/scenario-tests-properly
        )
