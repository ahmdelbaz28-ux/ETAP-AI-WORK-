"""
scada_protocols.opcua.client
============================
OPC UA client adapter (asyncua-based).

Subscribes to one or more OPC UA endpoints. Each configured client endpoint
specifies a list of ``node_id`` values to monitor; on every publish cycle
the adapter decodes the value and pushes it into the SCADA bridge via the
``on_measurement`` callback.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import OpcUaConfig

logger = logging.getLogger(__name__)


class OpcUaClientAdapter(ProtocolAdapter):
    """OPC UA client (master) that subscribes to external OPC UA servers."""

    protocol = ProtocolType.OPC_UA
    supports_server = False
    supports_client = True

    def __init__(
        self,
        config: OpcUaConfig,
        role: AdapterRole = AdapterRole.CLIENT,
        on_measurement: Optional[MeasurementCallback] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.CLIENT:
            raise ValueError("OpcUaClientAdapter is client-only")
        self._cfg = config
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[threading.Event] = None
        # Build a lookup: (endpoint_url, node_id) -> (element_id, measurement_type)
        self._node_lookup: Dict[str, Dict[str, tuple]] = {}
        for entry in config.node_map:
            # group by "folder" not needed for client; use endpoint list.
            node_id = str(entry["node_id"])
            elem = str(entry["element_id"])
            mtype = str(entry["measurement_type"])
            # The lookup is keyed per endpoint; we attach it to "default"
            # since the YAML node_map doesn't carry an endpoint tag.
            self._node_lookup.setdefault("default", {})[node_id] = (elem, mtype)
        # Allow per-client node overrides.
        for cli in config.clients:
            endpoint = str(cli.get("endpoint", "default"))
            for entry in cli.get("node_map", []) or []:
                node_id = str(entry["node_id"])
                elem = str(entry["element_id"])
                mtype = str(entry["measurement_type"])
                self._node_lookup.setdefault(endpoint, {})[node_id] = (elem, mtype)

    # -- lifecycle ----------------------------------------------------------

    def start_client(self) -> None:
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
                loop.run_until_complete(self._poll_loop())
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self._mark_error(f"client thread: {exc}")
            finally:
                loop.close()

        self._thread = threading.Thread(
            target=_thread_target, name="opcua-client", daemon=True
        )
        self._thread.start()

    def stop_client(self) -> None:
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

    async def _poll_loop(self) -> None:
        from asyncua import Client  # type: ignore

        if not self._cfg.clients:
            # Nothing to poll; idle.
            while self._stop_event is None or not self._stop_event.is_set():
                await asyncio.sleep(1.0)
            return

        clients: Dict[str, Client] = {}
        # Track whether each client has been successfully connected at least
        # once; on failure we drop the entry so the next cycle retries.
        last_connect_attempt: Dict[str, float] = {}

        try:
            while self._stop_event is None or not self._stop_event.is_set():
                for cli_cfg in self._cfg.clients:
                    if self._stop_event is not None and self._stop_event.is_set():
                        break
                    name = str(cli_cfg.get("name", "endpoint"))
                    endpoint = str(cli_cfg.get("endpoint", ""))
                    if not endpoint:
                        continue
                    scan_ms = int(cli_cfg.get("publish_interval_ms", self._cfg.publish_interval_ms))

                    # Throttle reconnect attempts to once every 2s per client.
                    now = asyncio.get_event_loop().time()
                    last = last_connect_attempt.get(name, 0.0)

                    client = clients.get(name)
                    if client is None and (now - last) >= 2.0:
                        last_connect_attempt[name] = now
                        client = Client(endpoint)
                        try:
                            await client.connect()
                            clients[name] = client
                        except Exception as exc:
                            self._mark_error(f"connect {name}: {exc}")
                            client = None
                            # Don't continue — fall through to sleep so we
                            # don't hammer the endpoint.
                            await asyncio.sleep(min(0.5, scan_ms / 1000.0))
                            continue
                    elif client is None:
                        # Already tried recently; skip this cycle.
                        await asyncio.sleep(min(0.5, scan_ms / 1000.0))
                        continue

                    # Determine which nodes to read for this client.
                    lookup = self._node_lookup.get(name) or self._node_lookup.get("default", {})
                    if not lookup:
                        continue

                    for node_id, (elem, mtype) in lookup.items():
                        try:
                            node = client.get_node(node_id)
                            value = await node.read_value()
                            self._ingest(
                                elem,
                                mtype,
                                float(value),
                                quality="good",
                                source=f"opcua:{name}",
                            )
                        except Exception as exc:
                            self._mark_error(f"read {name}/{node_id}: {exc}")
                            # Drop the client so next cycle reconnects.
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                            clients.pop(name, None)
                            self._ingest(
                                elem,
                                mtype,
                                0.0,
                                quality="bad",
                                source=f"opcua:{name}",
                            )
                            break  # skip remaining nodes this cycle

                    # Sleep respecting scan rate, but bail early if stopped.
                    slept = 0.0
                    while slept < scan_ms / 1000.0:
                        if self._stop_event is not None and self._stop_event.is_set():
                            break
                        await asyncio.sleep(min(0.1, scan_ms / 1000.0 - slept))
                        slept += 0.1
        finally:
            for client in clients.values():
                try:
                    await client.disconnect()
                except Exception:
                    pass

    # -- server stubs (client-only adapter) ---------------------------------

    def start_server(self) -> None:
        pass  # pragma: no cover

    def stop_server(self) -> None:
        pass  # pragma: no cover

    # -- health -------------------------------------------------------------

    def health_check(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


__all__ = ["OpcUaClientAdapter"]
