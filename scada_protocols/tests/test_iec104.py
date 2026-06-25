"""Tests for scada_protocols.iec104.asdu_mapper — pure data, no sockets."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.iec104.asdu_mapper import (
    DEFAULT_COT,
    IEC104Point,
    PointMap,
    decode_information,
    decode_quality,
    default_measurement_type_for,
    suggested_asdu_type,
)


# ---------------------------------------------------------------------------
# Fakes for c104.Information subclasses
# ---------------------------------------------------------------------------


@dataclass
class _FakeNormalizedInfo:
    actual: float
    quality: any = None


@dataclass
class _FakeShortInfo:
    value: float
    quality: any = None


@dataclass
class _FakeScaledInfo:
    value: int
    quality: any = None


@dataclass
class _FakeSingleInfo:
    on: bool
    quality: any = None


@dataclass
class _FakeQuality:
    Invalid: bool = False
    NonTopical: bool = False
    ElapsedTimeInvalid: bool = False
    Blocked: bool = False
    Substituted: bool = False
    Overflow: bool = False

    def is_good(self) -> bool:
        return not any(
            [
                self.Invalid,
                self.NonTopical,
                self.ElapsedTimeInvalid,
                self.Blocked,
                self.Substituted,
                self.Overflow,
            ]
        )


class TestPointMap:
    def test_add_entry(self) -> None:
        pm = PointMap(
            [
                {
                    "ca": 1,
                    "ioa": 1001,
                    "element_id": "BUS-1",
                    "measurement_type": "voltage_magnitude",
                    "type_id": "M_ME_NC_1",
                }
            ]
        )
        assert len(pm) == 1
        pt = pm.find_by_ioa(1001)
        assert pt is not None
        assert pt.element_id == "BUS-1"
        assert pt.type_id == "M_ME_NC_1"
        assert pt.cot == DEFAULT_COT

    def test_find_by_element_type(self) -> None:
        pm = PointMap(
            [
                {
                    "ca": 1,
                    "ioa": 1001,
                    "element_id": "BUS-1",
                    "measurement_type": "voltage_magnitude",
                }
            ]
        )
        pt = pm.find_by_element_type("BUS-1", "voltage_magnitude")
        assert pt is not None
        assert pt.ioa == 1001
        assert pm.find_by_element_type("BUS-X", "voltage_magnitude") is None

    def test_scale_offset_applied(self) -> None:
        pm = PointMap(
            [
                {
                    "ca": 1,
                    "ioa": 1,
                    "element_id": "B",
                    "measurement_type": "v",
                    "type_id": "M_ME_NC_1",
                    "scale": 100.0,
                    "offset": 1.0,
                }
            ]
        )
        pt = pm.find_by_ioa(1)
        assert pt is not None
        assert pt.scale == 100.0
        assert pt.offset == 1.0


class TestDecodeInformation:
    def test_normalized_info(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="B",
            measurement_type="voltage_magnitude", type_id="M_ME_NA_1",
            scale=1.0, offset=0.0,
        )
        info = _FakeNormalizedInfo(actual=0.95)
        val = decode_information(info, pt)
        assert val is not None
        assert abs(val - 0.95) < 1e-6

    def test_short_info(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="B",
            measurement_type="voltage_magnitude", type_id="M_ME_NC_1",
        )
        info = _FakeShortInfo(value=1.05)
        val = decode_information(info, pt)
        assert val is not None
        assert abs(val - 1.05) < 1e-6

    def test_scaled_info(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="B",
            measurement_type="active_power", type_id="M_ME_NB_1",
        )
        info = _FakeScaledInfo(value=100)
        val = decode_information(info, pt)
        assert val == 100.0

    def test_single_info(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="BRK",
            measurement_type="breaker_status", type_id="M_SP_NA_1",
        )
        info = _FakeSingleInfo(on=True)
        val = decode_information(info, pt)
        assert val == 1.0
        info2 = _FakeSingleInfo(on=False)
        val2 = decode_information(info2, pt)
        assert val2 == 0.0

    def test_scale_offset_applied(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="B",
            measurement_type="v", type_id="M_ME_NC_1",
            scale=10.0, offset=2.0,
        )
        info = _FakeShortInfo(value=1.0)
        # value = raw * scale + offset = 1.0 * 10 + 2 = 12.0
        val = decode_information(info, pt)
        assert val == 12.0

    def test_none_info_returns_none(self) -> None:
        pt = IEC104Point(
            ca=1, ioa=1, element_id="B",
            measurement_type="v", type_id="M_ME_NC_1",
        )
        assert decode_information(None, pt) is None


class TestDecodeQuality:
    def test_none_info(self) -> None:
        assert decode_quality(None) == "missing"

    def test_good_quality(self) -> None:
        info = _FakeShortInfo(value=1.0, quality=_FakeQuality())
        assert decode_quality(info) == "good"

    def test_invalid(self) -> None:
        q = _FakeQuality(Invalid=True)
        info = _FakeShortInfo(value=1.0, quality=q)
        assert decode_quality(info) == "invalid"

    def test_non_topical(self) -> None:
        q = _FakeQuality(NonTopical=True)
        info = _FakeShortInfo(value=1.0, quality=q)
        assert decode_quality(info) == "questionable"

    def test_blocked(self) -> None:
        q = _FakeQuality(Blocked=True)
        info = _FakeShortInfo(value=1.0, quality=q)
        assert decode_quality(info) == "questionable"

    def test_no_quality_attribute_returns_good(self) -> None:
        info = _FakeShortInfo(value=1.0, quality=None)
        assert decode_quality(info) == "good"


class TestAsduTypeDefaults:
    def test_default_measurement_type_for_known(self) -> None:
        assert default_measurement_type_for("M_SP_NA_1") == "breaker_status"
        assert default_measurement_type_for("M_ME_NC_1") == "voltage_magnitude"
        assert default_measurement_type_for("M_IT_NA_1") == "energy"

    def test_default_measurement_type_for_unknown(self) -> None:
        # Unknown types fall back to voltage_magnitude.
        assert default_measurement_type_for("X_X_X_1") == "voltage_magnitude"

    def test_suggested_asdu_type(self) -> None:
        assert suggested_asdu_type("voltage_magnitude") == "M_ME_NC_1"
        assert suggested_asdu_type("breaker_status") == "M_SP_NA_1"
        assert suggested_asdu_type("tap_position") == "M_ST_NA_1"
        assert suggested_asdu_type("unknown") == "M_ME_NC_1"
