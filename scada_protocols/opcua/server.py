"""
scada_protocols.opcua.server
============================
OPC UA server adapter (asyncua-based).

Exposes the platform's measurements to OPC UA clients. The address space is
either:
- taken from the YAML ``opcua.node_map`` list, or
- auto-built from a ``core_model.system.System`` instance passed via
  ``OpcUaServerAdapter.set_system(system)``.

A background task refreshes the variable values from a registered
``MeasurementProvider`` callback so live data is exposed.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable, Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import OpcUaConfig
from scada_protocols.opcua.address_space import (
    AddressSpacePlan,
    build_plan_from_node_map,
    build_plan_from_system,
)

logger = logging.getLogger(__name__)


MeasurementProvider = Callable[[], Dict[str, float]]


class OpcUaServerAdapter(ProtocolAdapter):
    """OPC UA server (slave) adapter — exposes platform measurements."""

    protocol = ProtocolType.OPC_UA
    supports_server = True
    supports_client = False

    def __init__(
        self,
        config: OpcUaConfig,
        role: AdapterRole = AdapterRole.SERVER,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[MeasurementProvider] = None,
        system: Any = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.SERVER:
            raise ValueError("OpcUaServerAdapter is server-only")
        self._cfg = config
        self._provider = provider
        self._system = system
        # Build initial plan from node_map OR from the system object.
        if config.node_map:
            self._plan: AddressSpacePlan = build_plan_from_node_map(
                config.node_map, namespace=config.server_namespace
            )
        elif system is not None:
            self._plan = build_plan_from_system(system, namespace=config.server_namespace)
        else:
            # Empty plan; variables can be added dynamically.
            self._plan = AddressSpacePlan(namespace=config.server_namespace)
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[threading.Event] = None
        self._instance: Any = None
        self._var_nodes: Dict[str, Any] = {}  # node_id_hint -> ua node

    # -- mutation -----------------------------------------------------------

    def set_provider(self, provider: MeasurementProvider) -> None:
        self._provider = provider

    def set_system(self, system: Any) -> None:
        self._system = system
        self._plan = build_plan_from_system(system, namespace=self._cfg.server_namespace)

    @property
    def plan(self) -> AddressSpacePlan:
        return self._plan

    # -- lifecycle ----------------------------------------------------------

    def start_server(self) -> None:
        if self._thread is not None:
            return
        try:
            pass  # type: ignore
        except Exception as exc:
            raise ImportError(f"asyncua not available: {exc}") from exc

        self._stop_event = threading.Event()

        def _thread_target() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._serve())
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self._mark_error(f"server thread: {exc}")
            finally:
                loop.close()

        self._thread = threading.Thread(
            target=_thread_target, name="opcua-server", daemon=True
        )
        self._thread.start()

    def stop_server(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    lambda: [t.cancel() for t in asyncio.all_tasks(self._loop)]
                )
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._loop = None
        self._stop_event = None
        self._instance = None
        self._var_nodes.clear()

    async def _serve(self) -> None:
        from asyncua import Server  # type: ignore

        server = Server()
        self._instance = server
        await server.init()
        server.set_endpoint(self._cfg.server_endpoint)
        server.set_server_name(self._cfg.server_name)

        # Set up namespace.
        uri = f"http://ahmd-etap/opcua/{self._cfg.server_namespace}"
        nsidx = await server.register_namespace(uri)

        # Build address space.
        objects = server.nodes.objects
        for folder in self._plan.folders:
            folder_obj = await objects.add_folder(nsidx, folder.browse_name)
            for var in folder.variables:
                node = await folder_obj.add_variable(
                    nsidx,
                    var.browse_name,
                    float(var.initial_value),
                )
                await node.set_writable(writable=True)
                # asyncua 2.0 dropped Node.set_description in favour of
                # write_attribute(AttributeId.Description, ...). We use
                # write_attribute when available, otherwise skip silently.
                if hasattr(node, "set_description"):
                    try:
                        await node.set_description(var.description or var.browse_name)
                    except Exception:
                        pass
                elif hasattr(node, "write_attribute"):
                    try:
                        from asyncua.ua import AttributeId, LocalizedText  # type: ignore

                        await node.write_attribute(
                            AttributeId.Description,
                            LocalizedText(var.description or var.browse_name),
                        )
                    except Exception:
                        pass
                self._var_nodes[var.node_id_hint] = node

        logger.info(
            "OPC UA server starting at %s (ns=%d, %d variables)",
            self._cfg.server_endpoint,
            nsidx,
            len(self._var_nodes),
        )

        # Background refresh task.
        async def _refresh() -> None:
            interval = max(self._cfg.publish_interval_ms / 1000.0, 0.1)
            while True:
                try:
                    await asyncio.sleep(interval)
                    if self._provider is None:
                        continue
                    snapshot = self._provider() or {}
                    # snapshot keys are node_id_hints
                    for hint, node in self._var_nodes.items():
                        val = snapshot.get(hint)
                        if val is None:
                            continue
                        try:
                            await node.write_value(float(val))
                            self._mark_served()
                        except Exception as exc:
                            self._mark_error(f"write {hint}: {exc}")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._mark_error(f"refresh loop: {exc}")
                    await asyncio.sleep(interval)

        # asyncua 2.0 split Server.run() into Server.start() (non-blocking)
        # + Server.stop(). We start the server, run the refresh task, and
        # sleep forever until cancelled.
        refresh_task = asyncio.create_task(_refresh())
        try:
            await server.start()
            # Block forever (until cancelled) so the server keeps serving.
            while True:
                await asyncio.sleep(3600)
        finally:
            try:
                await server.stop()
            except Exception:
                pass
            refresh_task.cancel()
            try:
                await refresh_task
            except Exception:
                pass

    # -- client stubs (server-only adapter) ---------------------------------

    def start_client(self) -> None:
        pass  # pragma: no cover

    def stop_client(self) -> None:
        pass  # pragma: no cover

    # -- health -------------------------------------------------------------

    def health_check(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


__all__ = ["OpcUaServerAdapter", "MeasurementProvider"]
