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
import math
import time
from typing import Any, Callable, Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    AdapterState,
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
        self._latest_snapshot: Dict[str, float] = {}
        self._last_successful_refresh_ts: Optional[float] = None
        self._point_freshness: Dict[str, float] = {}
        self._point_quality: Dict[str, str] = {}
        self._mirror_degraded: bool = False
        self._server_device: Any = None
        self._server_context: Any = None

    # -- public hooks -------------------------------------------------------

    @property
    def register_map(self) -> RegisterMap:
        return self._register_map

    @property
    def point_freshness(self) -> Dict[str, float]:
        return dict(self._point_freshness)

    @property
    def point_quality(self) -> Dict[str, str]:
        return dict(self._point_quality)

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
            from pymodbus.datastore import (  # type: ignore
                ModbusSequentialDataBlock,
                ModbusServerContext,
            )
            from pymodbus.server import StartAsyncTcpServer  # type: ignore
        except Exception as exc:  # pragma: no cover - import-time check
            raise ImportError(f"pymodbus not available: {exc}") from exc

        # pymodbus 3.13 renamed ModbusSlaveContext -> ModbusDeviceContext
        # and changed ModbusServerContext(slaves=...) -> (devices=..., single=False).
        # Support both shapes for forward/backward compatibility.
        try:
            from pymodbus.datastore import ModbusDeviceContext  # type: ignore

            device_ctx_cls = ModbusDeviceContext
            _NEW_API = True
        except ImportError:
            from pymodbus.datastore import ModbusSlaveContext  # type: ignore

            device_ctx_cls = ModbusSlaveContext
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

        # Authoritative address->word store maintained by the refresh loop.
        # Seeding goes through the block constructor because pymodbus >=3.9
        # removed the legacy mutators (setValues) and newer 3.x releases made
        # sparse blocks immutable after construction.
        store: Dict[int, int] = {}
        initial_snapshot: Dict[str, float] = {}
        initial_ok = False
        if self._provider is not None:
            try:
                res = self._provider()
                if res is not None and isinstance(res, dict):
                    initial_snapshot = res
                    initial_ok = True
            except Exception as snap_err:
                logger.warning("ModbusServerAdapter initial provider snapshot failed: %s", snap_err)
                self._mark_error(f"initial snapshot failed: {snap_err}")

        # DO NOT seed with synthetic zeros when provider is unavailable!
        # Only populate verified valid measurements from initial_snapshot.
        initial: Dict[int, int] = {}
        if initial_ok and initial_snapshot:
            for entry in self._register_map.entries:
                if entry.name in initial_snapshot and initial_snapshot[entry.name] is not None:
                    try:
                        val = float(initial_snapshot[entry.name])
                        if math.isfinite(val):
                            words = self._register_map.encode_value(entry, val)
                            for i, w in enumerate(words):
                                self._register_map.write_registers(entry.address + i, [w])
                                store[entry.address + i] = w
                                initial[entry.address + i] = w
                            self._latest_snapshot[entry.name] = val
                            self._point_freshness[entry.name] = time.time()
                            self._point_quality[entry.name] = "GOOD"
                    except Exception as enc_err:
                        logger.warning("Failed encoding initial value for %s: %s", entry.name, enc_err)
                        self._point_quality[entry.name] = "ERROR"

        if _USE_SPARSE:
            # pymodbus 3.13 simdevice __check_block requires at least one register to compute last_address
            # without raising IndexError: list index out of range.
            # Populating a base word at address 0 satisfies the block constructor without
            # affecting server.latest_snapshot or freshness state.
            sparse_init = dict(initial) if initial else {0: 0}
            block = ModbusSparseDataBlock(sparse_init)
        else:  # pragma: no cover - legacy API
            block = ModbusSequentialDataBlock(1, [store.get(i, 0) for i in range(1, max_addr + 11)])

        if (
            initial_ok
            and self._latest_snapshot
            and len(self._latest_snapshot) == len(self._register_map.entries)
        ):
            self._last_successful_refresh_ts = time.time()

        if _NEW_API:
            # di/co can be sparse too — they only need a tiny address space.
            _di_co_initial = dict.fromkeys(range(1, 101), 0)
            try:
                _di_block = ModbusSparseDataBlock(_di_co_initial)
                _co_block = ModbusSparseDataBlock(_di_co_initial)
            except Exception:
                _di_block = ModbusSequentialDataBlock(1, [0] * 100)
                _co_block = ModbusSequentialDataBlock(1, [0] * 100)
            device = device_ctx_cls(di=_di_block, co=_co_block, hr=block, ir=block)
            context = ModbusServerContext(devices={self._cfg.server_unit_id: device}, single=False)
        else:  # pragma: no cover - legacy API
            device = device_ctx_cls(
                di=ModbusSequentialDataBlock(0, [0] * 100),
                co=ModbusSequentialDataBlock(0, [0] * 100),
                hr=block,
                ir=block,
            )
            context = ModbusServerContext(slaves={self._cfg.server_unit_id: device}, single=False)

        self._server_device = device
        self._server_context = context

        def _mirror_words(entry_addr: int, words: list[int]) -> bool:
            """Mirror refreshed words into the datastore so external
            Modbus readers observe provider updates.

            Strategy (most canonical first):
            1. Device-level ``set_values``/``setValues(func_code, addr,
               values)`` — the context applies fx decoding and any internal
               address shifting itself. This is the only path whose
               addressing is guaranteed correct across pymodbus 3.x.
            2. Direct block mutators on the device's store blocks.
            3. Last resort: swap the store blocks with freshly constructed
               sparse blocks (pymodbus >=3.13 immutable-block builds).

            Returns True if write succeeded, False otherwise.
            """
            for i, w in enumerate(words):
                store[entry_addr + i] = w

            dev_set = getattr(device, "set_values", None)
            if dev_set is None:
                dev_set = getattr(device, "setValues", None)
            if callable(dev_set):
                try:
                    # Function code 3 == holding registers.
                    dev_set(3, entry_addr, list(words))
                    return True
                except Exception as ex:
                    logger.debug("Device set_values failed at %d: %s", entry_addr, ex)

            candidates: list[Any] = []
            ctx_store = getattr(device, "store", None)
            if isinstance(ctx_store, dict):
                candidates.extend(ctx_store[k] for k in ("h", "i") if k in ctx_store)
            for attr in ("hr", "ir"):
                blk = getattr(device, attr, None)
                if blk is not None:
                    candidates.append(blk)
            for blk in candidates:
                blk_set = getattr(blk, "set_values", None) or getattr(blk, "setValues", None)
                if callable(blk_set):
                    try:
                        blk_set(entry_addr, list(words))
                        return True
                    except Exception as ex:
                        logger.debug("Block set_values failed at %d: %s", entry_addr, ex)
                        continue

            if _USE_SPARSE and not getattr(self, "_mirror_degraded", False):
                try:
                    new_block = ModbusSparseDataBlock(dict(store))
                    ctx_store2 = getattr(device, "store", None)
                    replaced = False
                    if isinstance(ctx_store2, dict):
                        for key in ("h", "i"):
                            if key in ctx_store2:
                                ctx_store2[key] = new_block
                                replaced = True
                    else:
                        device.ir = new_block
                        device.hr = new_block
                        replaced = True
                    if replaced:
                        return True
                except Exception as exc:
                    self._mirror_degraded = True
                    logger.warning("Modbus datastore mirroring degraded: %s", exc)
                    return False

            return False

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
                    if self._provider is not None:
                        snapshot = self._provider()
                        if snapshot is None or not isinstance(snapshot, dict):
                            self._mark_error("refresh loop: provider returned None or invalid snapshot")
                            for e in self._register_map.entries:
                                self._point_quality[e.name] = "UNAVAILABLE"
                        else:
                            all_ok = True
                            now = time.time()
                            for entry in self._register_map.entries:
                                if entry.name not in snapshot or snapshot[entry.name] is None:
                                    all_ok = False
                                    self._point_quality[entry.name] = "UNAVAILABLE"
                                    # Evict missing point so stale data is not preserved
                                    self._latest_snapshot.pop(entry.name, None)
                                    continue

                                raw_val = snapshot[entry.name]
                                try:
                                    val = float(raw_val)
                                    if not math.isfinite(val):
                                        raise ValueError(f"Non-finite value {val}")
                                except Exception as conv_err:
                                    all_ok = False
                                    self._point_quality[entry.name] = "ERROR"
                                    self._latest_snapshot.pop(entry.name, None)
                                    self._mark_error(f"conversion error for '{entry.name}': {conv_err}")
                                    continue

                                try:
                                    words = self._register_map.encode_value(entry, val)
                                except Exception as enc_err:
                                    all_ok = False
                                    self._point_quality[entry.name] = "ERROR"
                                    self._latest_snapshot.pop(entry.name, None)
                                    self._mark_error(f"encoding error for '{entry.name}': {enc_err}")
                                    continue

                                for i, w in enumerate(words):
                                    self._register_map.write_registers(entry.address + i, [w])

                                mirror_ok = False
                                try:
                                    mirror_ok = _mirror_words(entry.address, words)
                                except Exception as m_err:
                                    logger.warning("Error mirroring words at addr %d: %s", entry.address, m_err)
                                    mirror_ok = False

                                if mirror_ok:
                                    self._mark_served(1)
                                    self._latest_snapshot[entry.name] = val
                                    self._point_freshness[entry.name] = now
                                    self._point_quality[entry.name] = "GOOD"
                                else:
                                    all_ok = False
                                    self._latest_snapshot.pop(entry.name, None)
                                    self._point_quality[entry.name] = "ERROR"
                                    self._mark_error(
                                        f"datastore write failed for entry '{entry.name}' at address {entry.address}"
                                    )

                            if all_ok and self._latest_snapshot:
                                self._last_successful_refresh_ts = now
                    await asyncio.sleep(interval)
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

        self._thread = threading.Thread(target=_thread_target, name="modbus-server", daemon=True)
        self._thread.start()

    def stop_server(self) -> None:
        """Stop the server and the refresh task."""
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                # Schedule shutdown on the loop.
                async def _shutdown() -> None:
                    if self._refresh_task and not self._refresh_task.done():
                        self._refresh_task.cancel()
                    # pymodbus 3.x StartAsyncTcpServer exposes no clean stop,
                    # so we cancel the loop's tasks; the thread exits.
                    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
                    for t in tasks:
                        t.cancel()

                def _schedule(current_loop: asyncio.AbstractEventLoop = loop) -> None:
                    if not current_loop.is_closed():
                        current_loop.create_task(_shutdown())

                loop.call_soon_threadsafe(_schedule)
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

    # -- health & freshness -------------------------------------------------

    def read_holding_registers(self, address: int, count: int = 1) -> list[int]:
        """Direct inspection helper to read registers from the active Modbus datastore."""
        dev = self._server_device
        if dev is not None:
            dev_get = getattr(dev, "get_values", None) or getattr(dev, "getValues", None)
            if callable(dev_get):
                try:
                    vals = dev_get(3, address, count)
                    if vals is not None:
                        return list(vals)
                except Exception as ex:
                    logger.debug("Device get_values failed at %d: %s", address, ex)
            ctx_store = getattr(dev, "store", None)
            candidates = []
            if isinstance(ctx_store, dict):
                candidates.extend(ctx_store[k] for k in ("h", "i") if k in ctx_store)
            for attr in ("hr", "ir"):
                blk = getattr(dev, attr, None)
                if blk is not None:
                    candidates.append(blk)
            for blk in candidates:
                blk_get = getattr(blk, "get_values", None) or getattr(blk, "getValues", None)
                if callable(blk_get):
                    try:
                        vals = blk_get(address, count)
                        if vals is not None:
                            return list(vals)
                    except Exception as ex:
                        logger.debug("Block get_values failed at %d: %s", address, ex)
                        continue
        return self._register_map.read_registers(address, count)

    def is_point_stale(self, entry_name: str) -> bool:
        """Check if an individual telemetry point is stale or unavailable."""
        if entry_name not in self._point_freshness:
            return True
        ts = self._point_freshness[entry_name]
        max_stale_sec = max((self._cfg.scan_rate_ms / 1000.0) * 3, 3.0)
        return (time.time() - ts) > max_stale_sec

    @property
    def is_stale(self) -> bool:
        """Indicate whether telemetry data is stale due to missed or failing refresh cycles."""
        if self._last_successful_refresh_ts is None:
            return True
        if not self._register_map.entries:
            return False
        for entry in self._register_map.entries:
            if self.is_point_stale(entry.name):
                return True
        max_stale_sec = max((self._cfg.scan_rate_ms / 1000.0) * 3, 3.0)
        return (time.time() - self._last_successful_refresh_ts) > max_stale_sec

    @property
    def latest_snapshot(self) -> Dict[str, float]:
        """Return the dictionary of latest verified telemetry values."""
        return dict(self._latest_snapshot)

    def health_check(self) -> bool:
        """Check if server thread is alive and telemetry mirroring is non-degraded."""
        if self._thread is None or not self._thread.is_alive():
            return False
        if getattr(self, "_mirror_degraded", False):
            return False
        if self._state == AdapterState.ERROR:
            return False
        if self._provider is not None and self._last_successful_refresh_ts is not None:
            max_stale_sec = max((self._cfg.scan_rate_ms / 1000.0) * 10, 10.0)
            if (time.time() - self._last_successful_refresh_ts) > max_stale_sec:
                return False
        return True


__all__ = ["ModbusServerAdapter", "MeasurementProvider"]
