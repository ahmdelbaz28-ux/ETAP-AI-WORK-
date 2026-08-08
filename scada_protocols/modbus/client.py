"""
scada_protocols.modbus.client
=============================
Modbus TCP client (master) that polls remote slaves and pushes decoded
measurements into the SCADA bridge.

Each entry in ``ModbusConfig.clients`` describes one remote slave::

    {
        "name": "feeder-rtu-1",
        "host": "192.168.10.5",
        "port": 502,
        "unit_id": 1,
        "scan_rate_ms": 1000,
        "timeout_sec": 3.0
    }

The same ``ModbusConfig.register_map`` is reused to decode registers; each
entry is polled on every cycle for its ``address`` and ``register_count``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus.register_map import RegisterMap

logger = logging.getLogger(__name__)


class ModbusClientAdapter(ProtocolAdapter):
    """Modbus TCP master that polls one or more remote slaves."""

    protocol = ProtocolType.MODBUS_TCP
    supports_server = False
    supports_client = True

    def __init__(
        self,
        config: ModbusConfig,
        role: AdapterRole = AdapterRole.CLIENT,
        on_measurement: Optional[MeasurementCallback] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.CLIENT:
            raise ValueError("ModbusClientAdapter is client-only")
        self._cfg = config
        # Shared register map (decoded locally per poll cycle).
        self._register_map = RegisterMap(config.register_map)
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[threading.Event] = None

    # -- lifecycle ----------------------------------------------------------

    def start_client(self) -> None:
        if self._thread is not None:
            return
        try:
            from pymodbus.client import AsyncModbusTcpClient  # type: ignore
        except Exception as exc:
            try:
                from pymodbus.client.asynchronous.async_io import (
                    AsyncModbusTCPClient as AsyncModbusTcpClient,  # type: ignore
                )
            except Exception as exc2:
                raise ImportError(
                    f"pymodbus not available: {exc} / {exc2}"
                ) from exc2

        self._stop_event = threading.Event()
        self._AsyncModbusTcpClient = AsyncModbusTcpClient

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
            target=_thread_target, name="modbus-client", daemon=True
        )
        self._thread.start()

    def stop_client(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        # Wake up the loop so it can exit promptly.
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

    # -- polling loop -------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Poll every configured slave at its scan_rate_ms."""
        # One async client per slave; lazily (re)created on demand.
        clients: Dict[str, Any] = {}

        async def _get_client(name: str, host: str, port: int, timeout: float) -> Any:
            cli = clients.get(name)
            if cli is None:
                cli = self._AsyncModbusTcpClient(host=host, port=port, timeout=timeout)
                try:
                    await cli.connect()
                except Exception as exc:
                    self._mark_error(f"connect {name}: {exc}")
                    cli = None
                clients[name] = cli
            return cli

        # pymodbus 3.13 changed read_holding_registers signature:
        #   old: read_holding_registers(address, count, slave=unit_id)
        #   new: read_holding_registers(address, *, count=1, device_id=1)
        # Detect which form to use on first call.
        async def _read_holding(cli: Any, address: int, count: int, unit_id: int) -> Any:
            try:
                # Try new API first.
                return await cli.read_holding_registers(address, count=count, device_id=unit_id)
            except TypeError:
                # Fall back to old API.
                return await cli.read_holding_registers(address, count, slave=unit_id)

        async def _read_input(cli: Any, address: int, count: int, unit_id: int) -> Any:
            try:
                return await cli.read_input_registers(address, count=count, device_id=unit_id)
            except TypeError:
                return await cli.read_input_registers(address, count, slave=unit_id)

        try:
            while self._stop_event is None or not self._stop_event.is_set():
                if not self._cfg.clients:
                    await asyncio.sleep(1.0)
                    continue
                for slave in self._cfg.clients:
                    if self._stop_event is not None and self._stop_event.is_set():
                        break
                    name = str(slave.get("name", "slave"))
                    host = str(slave.get("host", "127.0.0.1"))
                    port = int(slave.get("port", 502))
                    unit_id = int(slave.get("unit_id", 1))
                    scan_ms = int(slave.get("scan_rate_ms", self._cfg.scan_rate_ms))
                    timeout = float(slave.get("timeout_sec", 3.0))

                    cli = await _get_client(name, host, port, timeout)
                    if cli is None:
                        # Re-try next cycle.
                        clients.pop(name, None)
                        continue

                    # Group register-map entries by address block to read
                    # efficiently. For simplicity here we read each entry.
                    for entry in self._register_map.entries:
                        try:
                            fc = entry.function_code
                            if fc == 3:
                                rr = await _read_holding(cli, entry.address, entry.register_count, unit_id)
                            elif fc == 4:
                                rr = await _read_input(cli, entry.address, entry.register_count, unit_id)
                            else:
                                continue
                            if rr is None or getattr(rr, "isError", lambda: True)():
                                self._ingest(
                                    entry.element_id,
                                    entry.measurement_type,
                                    0.0,
                                    quality="bad",
                                    source=f"modbus:{name}",
                                )
                                continue
                            # Decode using the register map.
                            words = list(rr.registers)
                            # Stash into a transient RegisterMap to decode.
                            self._register_map.write_registers(entry.address, words)
                            value = self._register_map.decode_value(entry)
                            if value is None:
                                continue
                            self._ingest(
                                entry.element_id,
                                entry.measurement_type,
                                float(value),
                                quality="good",
                                source=f"modbus:{name}",
                            )
                        except Exception as exc:
                            self._mark_error(f"read {name}/{entry.name}: {exc}")
                            # Force reconnect on next cycle.
                            try:
                                await cli.close()
                            except Exception:
                                pass
                            clients.pop(name, None)
                            self._ingest(
                                entry.element_id,
                                entry.measurement_type,
                                0.0,
                                quality="bad",
                                source=f"modbus:{name}",
                            )

                    # Sleep for this slave's scan interval, but bail early if stopped.
                    slept = 0.0
                    while slept < scan_ms / 1000.0:
                        if self._stop_event is not None and self._stop_event.is_set():
                            break
                        await asyncio.sleep(min(0.1, scan_ms / 1000.0 - slept))
                        slept += 0.1
        finally:
            for cli in clients.values():
                if cli is None:
                    continue
                try:
                    await cli.close()
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


__all__ = ["ModbusClientAdapter"]
