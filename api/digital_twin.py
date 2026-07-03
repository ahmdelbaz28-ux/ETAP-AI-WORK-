"""
Digital Twin Endpoints API Router
=================================
Handles all digital twin synchronization endpoints.
Separated from main engineering service for better modularity.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/digital-twin", tags=["digital_twin"])

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
            },
        )
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("digital_twin_status_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )
