"""
scada_protocols.modbus.register_map
====================================
Two-way mapping between Modbus holding/input registers and the platform's
``Measurement`` objects.

A register map entry looks like::

    {
        "name": "BUS1_V",
        "element_id": "BUS-1",
        "measurement_type": "voltage_magnitude",
        "address": 0,            # Modbus register address
        "function_code": 3,      # 3=holding, 4=input
        "data_type": "float32",  # float32|uint16|int16|uint32|int32
        "scale": 1.0,            # multiply raw value
        "offset": 0.0,           # add to scaled value
        "unit": "p.u."
    }

The mapper handles:
- byte-order / word-order for 32-bit values (default big-endian, big-word)
- int16 vs uint16 vs float32 decode
- scale + offset application
- inverse encode for the server path (Measurement -> register bytes)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RegisterEntry:
    name: str
    element_id: str
    measurement_type: str
    address: int
    function_code: int = 3  # 3=holding, 4=input
    data_type: str = "float32"  # float32|uint16|int16|uint32|int32
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    # Number of 16-bit registers this entry occupies.
    register_count: int = 2

    def __post_init__(self) -> None:
        dt = self.data_type.lower()
        if dt in ("float32", "uint32", "int32"):
            self.register_count = 2
        elif dt in ("uint16", "int16"):
            self.register_count = 1
        else:
            raise ValueError(f"unsupported data_type {self.data_type!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "element_id": self.element_id,
            "measurement_type": self.measurement_type,
            "address": self.address,
            "function_code": self.function_code,
            "data_type": self.data_type,
            "scale": self.scale,
            "offset": self.offset,
            "unit": self.unit,
            "register_count": self.register_count,
        }


# ---------------------------------------------------------------------------
# Codec helpers
# ---------------------------------------------------------------------------


def _pack_uint16(value: int) -> bytes:
    return struct.pack(">H", value & 0xFFFF)


def _unpack_uint16(data: bytes) -> int:
    if len(data) < 2:
        raise ValueError("need at least 2 bytes for uint16")
    return struct.unpack(">H", data[:2])[0]


def _pack_int16(value: int) -> bytes:
    return struct.pack(">h", value & 0xFFFF if value >= 0 else value)


def _unpack_int16(data: bytes) -> int:
    return struct.unpack(">h", data[:2])[0]


def _pack_uint32(value: int, word_swap: bool = False) -> bytes:
    hi, lo = (value >> 16) & 0xFFFF, value & 0xFFFF
    if word_swap:
        return _pack_uint16(lo) + _pack_uint16(hi)
    return _pack_uint16(hi) + _pack_uint16(lo)


def _unpack_uint32(data: bytes, word_swap: bool = False) -> int:
    if len(data) < 4:
        raise ValueError("need at least 4 bytes for uint32")
    hi = _unpack_uint16(data[0:2])
    lo = _unpack_uint16(data[2:4])
    if word_swap:
        hi, lo = lo, hi
    return (hi << 16) | lo


def _pack_int32(value: int, word_swap: bool = False) -> bytes:
    return _pack_uint32(value & 0xFFFFFFFF, word_swap=word_swap)


def _unpack_int32(data: bytes, word_swap: bool = False) -> int:
    raw = _unpack_uint32(data, word_swap=word_swap)
    if raw & 0x80000000:
        raw -= 0x100000000
    return raw


def _pack_float32(value: float, word_swap: bool = False) -> bytes:
    packed = struct.pack(">f", value)
    if word_swap:
        return packed[2:4] + packed[0:2]
    return packed


def _unpack_float32(data: bytes, word_swap: bool = False) -> float:
    if len(data) < 4:
        raise ValueError("need at least 4 bytes for float32")
    if word_swap:
        data = data[2:4] + data[0:2]
    return struct.unpack(">f", data[:4])[0]


# ---------------------------------------------------------------------------
# RegisterMap
# ---------------------------------------------------------------------------


class RegisterMap:
    """In-memory register store with bidirectional Measurement <-> bytes codec."""

    def __init__(self, entries: Optional[List[Dict[str, Any]]] = None) -> None:
        self.entries: List[RegisterEntry] = []
        # address -> (entry, register_offset_within_entry)
        self._address_index: Dict[int, Tuple[RegisterEntry, int]] = {}
        # name -> entry
        self._name_index: Dict[str, RegisterEntry] = {}
        # The backing store: address -> uint16 register value.
        self._registers: Dict[int, int] = {}
        if entries:
            for raw in entries:
                self.add_entry(raw)

    # -- mutation -----------------------------------------------------------

    def add_entry(self, raw: Dict[str, Any]) -> RegisterEntry:
        entry = RegisterEntry(
            name=str(raw["name"]),
            element_id=str(raw["element_id"]),
            measurement_type=str(raw["measurement_type"]),
            address=int(raw["address"]),
            function_code=int(raw.get("function_code", 3)),
            data_type=str(raw.get("data_type", "float32")),
            scale=float(raw.get("scale", 1.0)),
            offset=float(raw.get("offset", 0.0)),
            unit=str(raw.get("unit", "")),
        )
        self.entries.append(entry)
        self._name_index[entry.name] = entry
        for offset in range(entry.register_count):
            self._address_index[entry.address + offset] = (entry, offset)
        # Initialise backing registers to 0.
        for offset in range(entry.register_count):
            self._registers.setdefault(entry.address + offset, 0)
        return entry

    # -- write side (Measurement -> registers) ------------------------------

    def encode_value(self, entry: RegisterEntry, value: float) -> List[int]:
        """Apply scale/offset and pack to a list of uint16 register values."""
        scaled = value * entry.scale + entry.offset
        dt = entry.data_type.lower()
        if dt == "float32":
            packed = _pack_float32(scaled, word_swap=False)
        elif dt == "uint16":
            packed = _pack_uint16(int(round(scaled)) & 0xFFFF)
        elif dt == "int16":
            packed = _pack_int16(int(round(scaled)))
        elif dt == "uint32":
            packed = _pack_uint32(int(round(scaled)) & 0xFFFFFFFF)
        elif dt == "int32":
            packed = _pack_int32(int(round(scaled)))
        else:
            raise ValueError(f"unsupported data_type {entry.data_type!r}")
        # Split packed bytes (len 2 or 4) into list of uint16, big-endian.
        return [struct.unpack(">H", packed[i : i + 2])[0] for i in range(0, len(packed), 2)]

    def write_measurement(self, entry: RegisterEntry, value: float) -> None:
        words = self.encode_value(entry, value)
        for i, w in enumerate(words):
            self._registers[entry.address + i] = w & 0xFFFF

    def write_registers(self, address: int, values: List[int]) -> None:
        """Direct write of raw uint16 values (server-side write FC=6/16)."""
        for i, v in enumerate(values):
            self._registers[address + i] = int(v) & 0xFFFF

    # -- read side (registers -> Measurement) -------------------------------

    def read_registers(self, address: int, count: int) -> List[int]:
        """Read raw uint16 register values (server-side read FC=3/4)."""
        return [self._registers.get(address + i, 0) & 0xFFFF for i in range(count)]

    def decode_value(self, entry: RegisterEntry) -> Optional[float]:
        """Decode the current register state of ``entry`` into a measurement value."""
        words = self.read_registers(entry.address, entry.register_count)
        packed = b"".join(_pack_uint16(w) for w in words)
        dt = entry.data_type.lower()
        if dt == "float32":
            raw = _unpack_float32(packed, word_swap=False)
        elif dt == "uint16":
            raw = float(_unpack_uint16(packed))
        elif dt == "int16":
            raw = float(_unpack_int16(packed))
        elif dt == "uint32":
            raw = float(_unpack_uint32(packed))
        elif dt == "int32":
            raw = float(_unpack_int32(packed))
        else:
            return None
        # Reverse scale/offset: stored = value*scale + offset  -> value = (stored - offset) / scale
        if entry.scale == 0:
            return raw
        return (raw - entry.offset) / entry.scale

    # -- lookup helpers -----------------------------------------------------

    def find_by_address(self, address: int) -> Optional[RegisterEntry]:
        hit = self._address_index.get(address)
        return hit[0] if hit else None

    def find_by_name(self, name: str) -> Optional[RegisterEntry]:
        return self._name_index.get(name)

    def all_entries(self) -> List[RegisterEntry]:
        return list(self.entries)

    def __len__(self) -> int:
        return len(self.entries)


__all__ = [
    "RegisterEntry",
    "RegisterMap",
]
