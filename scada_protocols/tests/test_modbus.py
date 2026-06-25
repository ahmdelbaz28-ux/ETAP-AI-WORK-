"""Tests for scada_protocols.modbus — RegisterMap codec (no sockets)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.modbus.register_map import RegisterMap


class TestRegisterMapCodec:
    def test_float32_round_trip(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "BUS1_V",
                "element_id": "BUS-1",
                "measurement_type": "voltage_magnitude",
                "address": 0,
                "data_type": "float32",
                "scale": 1.0,
                "offset": 0.0,
            }
        )
        rm.write_measurement(rm.entries[0], 1.05)
        words = rm.read_registers(0, 2)
        assert len(words) == 2
        # Re-decode.
        val = rm.decode_value(rm.entries[0])
        assert val is not None
        assert abs(val - 1.05) < 1e-6

    def test_float32_with_scale_offset(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "BUS1_V",
                "element_id": "BUS-1",
                "measurement_type": "voltage_magnitude",
                "address": 0,
                "data_type": "float32",
                "scale": 1000.0,  # stored = value * 1000
                "offset": 0.0,
            }
        )
        rm.write_measurement(rm.entries[0], 1.05)  # stored = 1050.0
        val = rm.decode_value(rm.entries[0])
        assert val is not None
        assert abs(val - 1.05) < 1e-6

    def test_uint16_round_trip(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "BRK1",
                "element_id": "BRK-1",
                "measurement_type": "breaker_status",
                "address": 0,
                "data_type": "uint16",
            }
        )
        rm.write_measurement(rm.entries[0], 1)
        val = rm.decode_value(rm.entries[0])
        assert val == 1.0

    def test_int16_negative_value(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "P",
                "element_id": "B",
                "measurement_type": "active_power",
                "address": 0,
                "data_type": "int16",
                "scale": 1.0,
                "offset": 0.0,
            }
        )
        rm.write_measurement(rm.entries[0], -100)
        val = rm.decode_value(rm.entries[0])
        assert val is not None
        assert abs(val - (-100.0)) < 1e-6

    def test_uint32_round_trip(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "E",
                "element_id": "B",
                "measurement_type": "energy",
                "address": 0,
                "data_type": "uint32",
            }
        )
        rm.write_measurement(rm.entries[0], 1_000_000)
        val = rm.decode_value(rm.entries[0])
        assert val == 1_000_000.0

    def test_int32_negative_value(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "Q",
                "element_id": "B",
                "measurement_type": "reactive_power",
                "address": 0,
                "data_type": "int32",
            }
        )
        rm.write_measurement(rm.entries[0], -500_000)
        val = rm.decode_value(rm.entries[0])
        assert val is not None
        assert abs(val - (-500_000.0)) < 1e-6

    def test_multiple_entries_non_overlapping(self) -> None:
        rm = RegisterMap(
            [
                {
                    "name": "A",
                    "element_id": "B1",
                    "measurement_type": "v",
                    "address": 0,
                    "data_type": "float32",
                },
                {
                    "name": "B",
                    "element_id": "B2",
                    "measurement_type": "v",
                    "address": 2,
                    "data_type": "float32",
                },
            ]
        )
        assert len(rm) == 2
        rm.write_measurement(rm.entries[0], 1.0)
        rm.write_measurement(rm.entries[1], 0.95)
        assert abs(rm.decode_value(rm.entries[0]) - 1.0) < 1e-6
        assert abs(rm.decode_value(rm.entries[1]) - 0.95) < 1e-6

    def test_unsupported_data_type_raises(self) -> None:
        rm = RegisterMap()
        with pytest.raises(ValueError):
            rm.add_entry(
                {
                    "name": "x",
                    "element_id": "B",
                    "measurement_type": "v",
                    "address": 0,
                    "data_type": "float64",  # unsupported
                }
            )

    def test_find_by_name_and_address(self) -> None:
        rm = RegisterMap(
            [
                {
                    "name": "A",
                    "element_id": "B1",
                    "measurement_type": "v",
                    "address": 0,
                    "data_type": "uint16",
                }
            ]
        )
        assert rm.find_by_name("A") is rm.entries[0]
        assert rm.find_by_address(0) is rm.entries[0]
        assert rm.find_by_name("X") is None
        assert rm.find_by_address(99) is None

    def test_direct_register_write(self) -> None:
        rm = RegisterMap()
        rm.add_entry(
            {
                "name": "A",
                "element_id": "B1",
                "measurement_type": "v",
                "address": 0,
                "data_type": "uint16",
            }
        )
        rm.write_registers(0, [42])
        assert rm.read_registers(0, 1) == [42]
