"""
scada_protocols.wiring
======================
Additive wiring of the scada_protocols package into the AhmedETAP app.

This module is the ONLY integration point you need to call from your
existing codebase. It does NOT modify any existing file — you just call
``wire_into_app(app)`` from your FastAPI startup (typically in
``api/routes.py`` near the other ``include_router`` calls, or from
``core/bootstrap.py``'s lifespan).

What it does:
1. Constructs a SCADAProtocolManager (loads YAML config from
   ``$SCADA_PROTOCOLS_CONFIG`` or falls back to defaults).
2. Wires the manager's bridge to the platform's existing
   ``SCADADatabase`` and ``EventBus`` instances (looked up lazily).
3. Starts the manager (all configured protocols).
4. Mounts the SCADA protocols API router at ``/api/v1/scada/protocols``.
5. Registers a shutdown handler so the manager stops cleanly on app exit.

Usage in ``api/routes.py``::

    from scada_protocols.wiring import wire_into_app
    wire_into_app(app, scada_db=my_scada_database, event_bus=my_event_bus)

Usage in ``core/bootstrap.py`` lifespan::

    from scada_protocols.wiring import wire_into_app
    async def lifespan(app):
        # ... existing setup ...
        wire_into_app(app)
        yield
        # ... existing teardown ...
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI

from scada_protocols.api import build_router, set_manager
from scada_protocols.common.config import load_config
from scada_protocols.manager import SCADAProtocolManager

logger = logging.getLogger(__name__)

# Module-level singleton — holds the manager so the router can find it.
_WIRED_MANAGER: Optional[SCADAProtocolManager] = None


def wire_into_app(
    app: FastAPI,
    scada_db: Any = None,
    event_bus: Any = None,
    measurement_provider: Any = None,
    system: Any = None,
    config_path: Optional[str] = None,
    prefix: str = "/api/v1/scada/protocols",
    autostart: bool = True,
) -> SCADAProtocolManager:
    """Wire the SCADA protocols package into a FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The host FastAPI application.
    scada_db : optional
        An existing ``scada_model.scada_model.SCADADatabase`` instance. If
        None, the bridge will lazily create one on first ingest.
    event_bus : optional
        An existing ``digital_twin.event_bus.EventBus`` instance. If None,
        no events are published (the bridge still updates SCADADatabase).
    measurement_provider : optional
        A callable returning a dict of measurements for the server-side
        adapters. Used when the platform wants to expose its live state
        to external Modbus/OPC UA/IEC 104 masters.
    system : optional
        A ``core_model.system.System`` instance — used to auto-build the
        OPC UA address space when ``opcua.node_map`` is empty in the YAML.
    config_path : optional
        Path to a YAML config file. Defaults to ``$SCADA_PROTOCOLS_CONFIG``
        env var, or built-in defaults.
    prefix : str
        URL prefix for the SCADA protocols API router.
    autostart : bool
        If True, the manager is started immediately. Set to False if you
        want to start it later via the API endpoint.

    Returns
    -------
    SCADAProtocolManager
        The constructed (and possibly started) manager singleton.
    """
    global _WIRED_MANAGER

    if _WIRED_MANAGER is not None:
        logger.warning("scada_protocols already wired — returning existing manager")
        return _WIRED_MANAGER

    # Resolve config path.
    if config_path is None:
        config_path = os.environ.get("SCADA_PROTOCOLS_CONFIG")

    # Load config (None falls back to defaults inside load_config).
    cfg = load_config(config_path)

    # Build the manager.
    mgr = SCADAProtocolManager(
        config=cfg,
        scada_db=scada_db,
        event_bus=event_bus,
        measurement_provider=measurement_provider,
        system=system,
    )
    _WIRED_MANAGER = mgr
    set_manager(mgr)

    # Mount the router.
    app.include_router(build_router(), prefix=prefix)
    logger.info("scada_protocols API router mounted at %s", prefix)

    # Register shutdown handler via lifespan-compatible context manager.
    # FastAPI 0.93+ deprecates on_event("shutdown") in favour of lifespan
    # handlers, but we can't easily add to an existing app's lifespan here.
    # We use a starlette-compatible approach via add_event_handler, which
    # works on both old and new FastAPI.
    from contextlib import asynccontextmanager

    # Try the modern lifespan approach first.
    try:
        # Save the original lifespan so we don't clobber existing setup.
        original_lifespan = getattr(app.router, "lifespan_context", None)

        @asynccontextmanager
        async def _scada_protocols_lifespan(_app: FastAPI):
            try:
                yield
            finally:
                if _WIRED_MANAGER is not None and _WIRED_MANAGER.is_started():
                    logger.info("Stopping SCADA protocols on app shutdown")
                    _WIRED_MANAGER.stop()

        # Compose with the existing lifespan if present.
        if original_lifespan is not None:
            _original = original_lifespan

            @asynccontextmanager
            async def _combined_lifespan(_app: FastAPI):
                async with _original(_app):
                    async with _scada_protocols_lifespan(_app):
                        yield

            app.router.lifespan_context = _combined_lifespan
        else:
            app.router.lifespan_context = _scada_protocols_lifespan
    except Exception as exc:
        # Fallback: deprecated on_event handler (still works in FastAPI).
        logger.debug("falling back to on_event shutdown handler: %s", exc)

        @app.on_event("shutdown")
        async def _shutdown_scada_protocols() -> None:  # type: ignore
            if _WIRED_MANAGER is not None and _WIRED_MANAGER.is_started():
                logger.info("Stopping SCADA protocols on app shutdown")
                _WIRED_MANAGER.stop()

    # Optionally start the manager immediately.
    if autostart:
        try:
            mgr.start()
            logger.info(
                "SCADAProtocolManager started — %d adapter(s) active",
                sum(1 for a in mgr.list_adapters() if a["health"]),
            )
        except Exception as exc:
            logger.error("Failed to start SCADAProtocolManager: %s", exc)

    return mgr


def get_wired_manager() -> Optional[SCADAProtocolManager]:
    """Return the manager wired into the app, or None if not yet wired."""
    return _WIRED_MANAGER


__all__ = ["wire_into_app", "get_wired_manager"]
