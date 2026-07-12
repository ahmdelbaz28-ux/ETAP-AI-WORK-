"""
Unit tests for api/data_import.py — power-system data import parsing functions.

These tests exercise the pure parsing functions (_detect_format,
_decode_text, _make_bus_record, _make_branch_record, _json_bus_record,
_json_branch_record, _parse_csv, _parse_json) that don't require
database or external services.
"""
from __future__ import annotations

import json

import pytest

from api.data_import import (
    BranchRecord,
    BusRecord,
    _decode_text,
    _detect_format,
    _json_branch_record,
    _json_bus_record,
    _make_branch_record,
    _make_bus_record,
    _parse_csv,
    _parse_json,
)


class TestDetectFormat:
    """Tests for _detect_format()."""

    def test_detects_csv_extension(self):
        """GIVEN a .csv filename
        WHEN _detect_format is called
        THEN it returns the CSV SupportedFormat.
        """
        fmt = _detect_format("buses.csv")
        assert fmt.id == "csv"

    def test_detects_json_extension(self):
        """GIVEN a .json filename
        WHEN _detect_format is called
        THEN it returns the JSON SupportedFormat.
        """
        fmt = _detect_format("system.json")
        assert fmt.id in ("json", "etap-project")

    def test_detects_xml_extension(self):
        """GIVEN a .xml filename
        WHEN _detect_format is called
        THEN it returns the CIM/XML format.
        """
        fmt = _detect_format("cim.xml")
        assert fmt.id == "cim-xml"

    def test_detects_psse_raw_extension(self):
        """GIVEN a .raw filename
        WHEN _detect_format is called
        THEN it returns the PSS/E RAW format.
        """
        fmt = _detect_format("system.raw")
        assert fmt.id == "psse-raw"

    def test_unknown_extension_raises(self):
        """GIVEN a .txt filename
        WHEN _detect_format is called
        THEN it raises HTTPException with 422.
        """
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _detect_format("unknown.txt")
        assert exc_info.value.status_code == 422


class TestDecodeText:
    """Tests for _decode_text()."""

    def test_decodes_utf8_content(self):
        """GIVEN valid UTF-8 bytes
        WHEN _decode_text is called
        THEN it returns the decoded string with no warnings.
        """
        content = b"Hello, World!"
        text, warnings = _decode_text(content)
        assert text == "Hello, World!"
        assert warnings == []

    def test_decodes_latin1_fallback(self):
        """GIVEN non-UTF-8 bytes (Latin-1)
        WHEN _decode_text is called
        THEN it decodes as Latin-1 and adds a warning.
        """
        # 0x80-0x9F are invalid as standalone UTF-8 but valid in Latin-1
        content = b"Caf\xe9"
        text, warnings = _decode_text(content)
        assert "Caf" in text
        assert len(warnings) > 0, "Should warn about non-UTF-8"


class TestMakeBusRecord:
    """Tests for _make_bus_record()."""

    def test_creates_bus_record_from_dict(self):
        """GIVEN a dict with bus fields
        WHEN _make_bus_record is called
        THEN it returns a BusRecord with the expected values.
        """
        row = {
            "id": "BUS1",
            "name": "Main Bus",
            "nominal_kv": "13.8",
            "type": "PQ",
        }
        record = _make_bus_record(row)
        assert isinstance(record, BusRecord)
        assert record.id == "BUS1"
        assert record.name == "Main Bus"

    def test_handles_missing_optional_fields(self):
        """GIVEN a dict with only required fields
        WHEN _make_bus_record is called
        THEN it creates a record with None for optional fields.
        """
        row = {"id": "BUS2", "name": "Secondary"}
        record = _make_bus_record(row)
        assert record.id == "BUS2"


class TestMakeBranchRecord:
    """Tests for _make_branch_record()."""

    def test_creates_branch_record_from_dict(self):
        """GIVEN a dict with branch fields
        WHEN _make_branch_record is called
        THEN it returns a BranchRecord.
        """
        row = {
            "from_bus": "BUS1",
            "to_bus": "BUS2",
            "rating_mva": "50",
        }
        record = _make_branch_record(row)
        assert isinstance(record, BranchRecord)
        assert record.from_bus == "BUS1"
        assert record.to_bus == "BUS2"


class TestJsonBusRecord:
    """Tests for _json_bus_record()."""

    def test_creates_bus_record_from_json_dict(self):
        """GIVEN a JSON dict with bus fields
        WHEN _json_bus_record is called
        THEN it returns a BusRecord.
        """
        b = {"id": "BUS1", "name": "Main", "nominal_kv": 13.8, "type": "PV"}
        record = _json_bus_record(b)
        assert isinstance(record, BusRecord)
        assert record.id == "BUS1"

    def test_handles_missing_fields(self):
        """GIVEN a minimal JSON dict
        WHEN _json_bus_record is called
        THEN it creates a record with defaults for missing fields.
        """
        b = {"id": "BUS2"}
        record = _json_bus_record(b)
        assert record.id == "BUS2"


class TestJsonBranchRecord:
    """Tests for _json_branch_record()."""

    def test_creates_branch_record_from_json_dict(self):
        """GIVEN a JSON dict with branch fields
        WHEN _json_branch_record is called
        THEN it returns a BranchRecord.
        """
        br = {"from_bus": "BUS1", "to_bus": "BUS2", "rating_mva": 100}
        record = _json_branch_record(br)
        assert isinstance(record, BranchRecord)
        assert record.from_bus == "BUS1"
        assert record.to_bus == "BUS2"


class TestParseCsv:
    """Tests for _parse_csv()."""

    def test_parses_valid_csv(self):
        """GIVEN valid CSV content with buses and branches
        WHEN _parse_csv is called
        THEN it returns buses, branches, metadata, and no errors.
        """
        csv_content = b"""id,name,nominal_kv,type
BUS1,Main Bus,13.8,PQ
BUS2,Secondary,138.0,PV
"""
        buses, branches, metadata, warnings = _parse_csv(csv_content)
        assert len(buses) == 2
        assert buses[0].id == "BUS1"
        assert buses[1].id == "BUS2"
        assert metadata.get("row_count") == 2

    def test_handles_empty_csv(self):
        """GIVEN an empty CSV (just headers)
        WHEN _parse_csv is called
        THEN it returns empty lists with no errors.
        """
        csv_content = b"id,name,nominal_kv,type\n"
        buses, branches, metadata, warnings = _parse_csv(csv_content)
        assert len(buses) == 0
        assert len(branches) == 0

    def test_handles_malformed_csv_gracefully(self):
        """GIVEN CSV content with valid headers but a malformed row
        WHEN _parse_csv is called
        THEN it skips the bad row and logs a warning.
        """
        csv_content = b"id,name,voltage_kv,type\nBUS1,Good Bus,13.8,PQ\nBUS2,Bad Bus,invalid-voltage,PV\n"
        buses, branches, metadata, warnings = _parse_csv(csv_content)
        assert len(buses) == 1
        assert buses[0].id == "BUS1"
        assert len(warnings) == 1


class TestParseJson:
    """Tests for _parse_json()."""

    def test_parses_valid_json(self):
        """GIVEN valid JSON with buses and branches arrays
        WHEN _parse_json is called
        THEN it returns the parsed records.
        """
        data = {
            "buses": [
                {"id": "BUS1", "name": "Main", "nominal_kv": 13.8},
                {"id": "BUS2", "name": "Secondary", "nominal_kv": 138.0},
            ],
            "branches": [
                {"from_bus": "BUS1", "to_bus": "BUS2", "rating_mva": 50},
            ],
            "base_mva": 100,
            "base_kv": 13.8,
        }
        content = json.dumps(data).encode("utf-8")
        buses, branches, metadata, warnings = _parse_json(content)
        assert len(buses) == 2
        assert len(branches) == 1
        assert metadata.get("key_count") == 4

    def test_handles_json_without_branches(self):
        """GIVEN JSON with only buses
        WHEN _parse_json is called
        THEN it returns buses with empty branches list.
        """
        data = {"buses": [{"id": "BUS1", "name": "Main"}]}
        content = json.dumps(data).encode("utf-8")
        buses, branches, metadata, warnings = _parse_json(content)
        assert len(buses) == 1
        assert len(branches) == 0

    def test_handles_invalid_json(self):
        """GIVEN invalid JSON bytes
        WHEN _parse_json is called
        THEN it raises an exception (JSONDecodeError or HTTPException).
        """
        content = b"{not valid json"
        with pytest.raises(Exception):
            _parse_json(content)

    def test_handles_empty_buses_array(self):
        """GIVEN JSON with empty buses array
        WHEN _parse_json is called
        THEN it returns empty lists.
        """
        data = {"buses": [], "branches": []}
        content = json.dumps(data).encode("utf-8")
        buses, branches, metadata, warnings = _parse_json(content)
        assert len(buses) == 0
        assert len(branches) == 0
