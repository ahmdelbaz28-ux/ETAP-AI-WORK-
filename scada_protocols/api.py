"""
scada_protocols.api
===================
FastAPI router exposing SCADA protocol management endpoints.

Mount into the host FastAPI app::

    from scada_protocols.api import build_router, set_manager
    from scada_protocols.manager import SCADAProtocolManager

    manager = SCADAProtocolManager(config_path="scada_protocols/config/scada.yaml")
    manager.start()
    set_manager(manager)
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from scada_protocols.common.base import ProtocolType, probe_all

logger = logging.getLogger(__name__)

# Module-level singleton — set via ``set_manager``.
_manager_lock = threading.RLock()
_manager_singleton: Any = None


def set_manager(manager: Any) -> None:
    """Register the global SCADAProtocolManager used by the router."""
    global _manager_singleton
    with _manager_lock:
        _manager_singleton = manager


def get_manager() -> Any:
    with _manager_lock:
        return _manager_singleton


def build_router() -> APIRouter:
    """Build a fresh APIRouter. Call once per FastAPI app."""
    from fastapi import Depends

    from api.dependencies import get_api_key, get_optional_current_user_from_header

    async def _require_admin(
        user: Any = Depends(get_optional_current_user_from_header),
    ) -> None:
        if user is not None and getattr(user, "role", "") != "admin":
            raise HTTPException(
                status_code=403,
                detail="Admin role required for SCADA protocol control operations",
            )

    router = APIRouter(
        tags=["scada-protocols"],
        dependencies=[Depends(get_api_key)],
    )

    # ---------------------------------------------------------------------
    # Library probes
    # ---------------------------------------------------------------------

    @router.get("/libraries")
    def list_libraries() -> Dict[str, Any]:
        """Report which SCADA protocol libraries are importable in this runtime."""
        return probe_all()

    # ---------------------------------------------------------------------
    # Manager status
    # ---------------------------------------------------------------------

    @router.get("/status")
    def get_status() -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            return {
                "started": False,
                "manager_registered": False,
                "libraries": probe_all(),
            }
        result = mgr.status()
        result["manager_registered"] = True
        return result

    @router.get("/adapters")
    def list_adapters() -> List[Dict[str, Any]]:
        mgr = get_manager()
        if mgr is None:
            return []
        return mgr.list_adapters()

    @router.post("/start", dependencies=[Depends(_require_admin)])
    def start_manager() -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            raise HTTPException(status_code=503, detail="No manager registered")
        mgr.start()
        return {"ok": True, "started": mgr.is_started()}

    @router.post("/stop", dependencies=[Depends(_require_admin)])
    def stop_manager() -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            raise HTTPException(status_code=503, detail="No manager registered")
        mgr.stop()
        return {"ok": True, "started": mgr.is_started()}

    # ---------------------------------------------------------------------
    # Per-protocol endpoints
    # ---------------------------------------------------------------------

    @router.get("/{protocol}/status")
    def protocol_status(protocol: str) -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            raise HTTPException(status_code=503, detail="No manager registered")
        try:
            ptype = ProtocolType(protocol)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown protocol {protocol!r}; expected one of "
                f"{[p.value for p in ProtocolType]}",
            ) from None
        adapter = mgr.get_adapter(ptype)
        if adapter is None:
            return {"protocol": ptype.value, "configured": False}
        return {
            "protocol": ptype.value,
            "configured": True,
            "describe": adapter.describe(),
            "metric": adapter.metric.to_dict(),
            "health": adapter.health_check(),
        }

    @router.post("/{protocol}/start", dependencies=[Depends(_require_admin)])
    def start_protocol(protocol: str) -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            raise HTTPException(status_code=503, detail="No manager registered")
        try:
            ptype = ProtocolType(protocol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown protocol {protocol!r}") from None
        adapter = mgr.get_adapter(ptype)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"{protocol} adapter not configured")
        try:
            adapter.start()
            return {"ok": True, "state": adapter.state.value}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post("/{protocol}/stop", dependencies=[Depends(_require_admin)])
    def stop_protocol(protocol: str) -> Dict[str, Any]:
        mgr = get_manager()
        if mgr is None:
            raise HTTPException(status_code=503, detail="No manager registered")
        try:
            ptype = ProtocolType(protocol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown protocol {protocol!r}") from None
        adapter = mgr.get_adapter(ptype)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"{protocol} adapter not configured")
        adapter.stop()
        return {"ok": True, "state": adapter.state.value}

    return router


__all__ = ["build_router", "set_manager", "get_manager"]
