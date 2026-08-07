"""
scada_protocols.modbus.server
=============================
Modbus TCP server (slave) exposing the platform's measurements to external
Modbus masters.

Implementation notes:
- Uses ``pymodbus.server`` (pure-Python asyncio server).
- The register map is held in a ``RegisterMap`` instance; when a master reads,
  the server reads from that in-memory store.
- A background task periodically refreshes the register store from the
  registered ``MeasurementProvider`` callback so that live data is exposed.
- The server is started in a dedicated background asyncio task; ``stop_server``
  cancels it cleanly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus.register_map import RegisterMap

logger = logging.getLogger(__name__)


# A provider returns a dict {entry_name: float_value} for all entries it wants
# to push into the server's register store.
MeasurementProvider = Callable[[], Dict[str, float]]


class ModbusServerAdapter(ProtocolAdapter):
    """Modbus TCP slave that exposes the platform's measurements.

    This adapter is *server-only*. To ingest Modbus data from external masters
    into the SCADA database, use ``ModbusClientAdapter`` instead.
    """

    protocol = ProtocolType.MODBUS_TCP
    supports_server = True
    supports_client = False

    def __init__(
        self,
        config: ModbusConfig,
        role: AdapterRole = AdapterRole.SERVER,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[MeasurementProvider] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.SERVER:
            raise ValueError("ModbusServerAdapter is server-only")
        self._cfg = config
        self._register_map = RegisterMap(config.register_map)
        self._provider = provider
        self._server: Any = None
        self._task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[Any] = None
        self._latest_snapshot: Dict[int, float] = {}

    # -- public hooks -------------------------------------------------------

    @property
    def register_map(self) -> RegisterMap:
        return self._register_map

    def set_provider(self, provider: MeasurementProvider) -> None:
        self._provider = provider

    # -- lifecycle ----------------------------------------------------------

    def start_server(self) -> None:
        """Start the Modbus TCP server in a background asyncio task."""
        if self._task is not None:
            return
        # We lazily import pymodbus here so the package loads even when
        # pymodbus is not installed (the manager skips adapters whose
        # ``start_server`` raises ImportError).
        try:
            from pymodbus.server import StartAsyncTcpServer  # type: ignore
            from pymodbus.datastore import (  # type: ignore
                ModbusSequentialDataBlock,
                ModbusServerContext,
            )
        except Exception as exc:  # pragma: no cover - import-time check
            raise ImportError(f"pymodbus not available: {exc}") from exc

        # pymodbus 3.13 renamed ModbusSlaveContext -> ModbusDeviceContext
        # and changed ModbusServerContext(slaves=...) -> (devices=..., single=False).
        # Support both shapes for forward/backward compatibility.
        try:
            from pymodbus.datastore import ModbusDeviceContext  # type: ignore
            DeviceCtxCls = ModbusDeviceContext
            _NEW_API = True
        except ImportError:
            from pymodbus.datastore import ModbusSlaveContext  # type: ignore
            DeviceCtxCls = ModbusSlaveContext
            _NEW_API = False

        # Build the backing datastore from the register map.
        # We use ModbusSparseDataBlock which is a dict-based block and
        # tolerates address=0 (unlike ModbusSequentialDataBlock in 3.13).
        try:
            from pymodbus.datastore import ModbusSparseDataBlock  # type: ignore
            _USE_SPARSE = True
        except ImportError:  # pragma: no cover - very old pymodbus
            _USE_SPARSE = False

        max_addr = max(
            (e.address + e.register_count for e in self._register_map.entries),
            default=100,
        )

        if _USE_SPARSE:
            # Sparse block keyed by address. Initialize all addresses to 0.
            initial = {addr: 0 for addr in range(0, max_addr + 10)}
            block = ModbusSparseDataBlock(initial)
            # Seed the block with encoded current values.
            for entry in self._register_map.entries:
                words = self._register_map.encode_value(entry, 0.0)
                for i, w in enumerate(words):
                    block.setValues(entry.address + i, [w])
        else:  # pragma: no cover - legacy API
            block = ModbusSequentialDataBlock(1, [0] * (max_addr + 10))
            for entry in self._register_map.entries:
                words = self._register_map.encode_value(entry, 0.0)
                for i, w in enumerate(words):
                    block.setValues(entry.address + i + 1, [w])  # +1 offset

        if _NEW_API:
            # di/co can be sparse too — they only need a tiny address space.
            _di_co_initial = {addr: 0 for addr in range(1, 101)}
            try:
                _di_block = ModbusSparseDataBlock(_di_co_initial)
                _co_block = ModbusSparseDataBlock(_di_co_initial)
            except Exception:
                _di_block = ModbusSequentialDataBlock(1, [0] * 100)
                _co_block = ModbusSequentialDataBlock(1, [0] * 100)
            device = DeviceCtxCls(di=_di_block, co=_co_block, hr=block, ir=block)
            context = ModbusServerContext(devices={self._cfg.server_unit_id: device}, single=False)
        else:  # pragma: no cover - legacy API
            device = DeviceCtxCls(
                di=ModbusSequentialDataBlock(0, [0] * 100),
                co=ModbusSequentialDataBlock(0, [0] * 100),
                hr=block,
                ir=block,
            )
            context = ModbusServerContext(slaves={self._cfg.server_unit_id: device}, single=False)

        async def _run() -> None:
            logger.info(
                "Modbus TCP server starting on %s:%d (unit_id=%d, %d registers)",
                self._cfg.server_host,
                self._cfg.server_port,
                self._cfg.server_unit_id,
                max_addr,
            )
            self._server = StartAsyncTcpServer(
                context=context,
                address=(self._cfg.server_host, self._cfg.server_port),
            )
            await self._server

        async def _refresh() -> None:
            """Periodically refresh register store from the provider callback."""
            interval = max(self._cfg.scan_rate_ms / 1000.0, 0.1)
            while True:
                try:
                    await asyncio.sleep(interval)
                    if self._provider is None:
                        continue
                    snapshot = self._provider() or {}
                    for entry in self._register_map.entries:
                        val = snapshot.get(entry.name)
                        if val is None:
                            continue
                        words = self._register_map.encode_value(entry, float(val))
                        for i, w in enumerate(words):
                            self._register_map.write_registers(
                                entry.address + i, [w]
                            )
                        # Mirror into the datastore so external readers see it.
                        try:
                            device = context[self._cfg.server_unit_id]
                            # In 3.13 the function code for holding registers is 3.
                            device.setValues(3, entry.address, words)
                        except Exception:
                            pass
                        self._mark_served()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._mark_error(f"refresh loop: {exc}")
                    await asyncio.sleep(interval)

        # Run in a private event loop on a background thread.
        async def _main() -> None:
            self._refresh_task = asyncio.create_task(_refresh())
            try:
                await _run()
            finally:
                if self._refresh_task and not self._refresh_task.done():
                    self._refresh_task.cancel()

        def _thread_target() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_main())
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self._mark_error(f"server thread: {exc}")
            finally:
                loop.close()

        import threading

        self._thread = threading.Thread(
            target=_thread_target, name="modbus-server", daemon=True
        )
        self._thread.start()

    def stop_server(self) -> None:
        """Stop the server and the refresh task."""
        if self._loop is not None and self._loop.is_running():
            try:
                # Schedule shutdown on the loop.
                async def _shutdown() -> None:
                    if self._refresh_task and not self._refresh_task.done():
                        self._refresh_task.cancel()
                    # pymodbus 3.x StartAsyncTcpServer exposes no clean stop,
                    # so we cancel the loop's tasks; the thread exits.
                    tasks = [
                        t for t in asyncio.all_tasks(self._loop) if t is not asyncio.current_task()
                    ]
                    for t in tasks:
                        t.cancel()

                self._loop.call_soon_threadsafe(
                    lambda: self._loop.create_task(_shutdown())
                )
            except Exception as exc:
                self._mark_error(f"stop_server: {exc}")
        self._thread = None
        self._loop = None
        self._server = None

    # -- client stubs (server-only adapter) ---------------------------------

    def start_client(self) -> None:
        pass  # pragma: no cover

    def stop_client(self) -> None:
        pass  # pragma: no cover

    # -- health -------------------------------------------------------------

    def health_check(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )


__all__ = ["ModbusServerAdapter", "MeasurementProvider"]
