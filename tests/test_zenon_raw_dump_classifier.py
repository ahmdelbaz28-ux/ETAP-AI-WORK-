"""Tests for Zenon Raw Dump model, Classifier, and Reader integration.

Verifies:
- Raw dump v1 JSON parsing into ZenonRawDump model.
- Classification of raw variables and screens into canonical ZenonNetworkExport contract.
- Conversion of classified contract into core_model.System with slack infeed.
- Tracking of unmapped variables in unmapped[] with explicit warnings (zero guessing).
- Tracking of incomplete topology in incomplete[] with explicit reasons.
- Strict deterministic output across multiple classification runs.
- Loading and parsing of tests/fixtures/zenon_export_sample.znx.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core_model.system import System
from integrations.zenon_network_export.classifier import ClassifyResult, ZenonClassifier
from integrations.zenon_network_export.raw_dump import ZenonRawDump
from integrations.zenon_network_export.reader import parse_zenon_export

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_dump_sample() -> dict:
    file_path = FIXTURES_DIR / "zenon_raw_dump_sample.json"
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def export_znx_sample() -> str:
    file_path = FIXTURES_DIR / "zenon_export_sample.znx"
    with open(file_path, encoding="utf-8") as f:
        return f.read()


class TestZenonRawDumpClassifier:
    """Verifies raw dump ingestion and classification rules."""

    def test_raw_dump_classification_to_contract_and_system(self, raw_dump_sample: dict):
        """Test full pipeline: raw dump -> classifier -> contract -> core_model.System."""
        # 1. Direct classifier verification
        raw_model = ZenonRawDump.model_validate(raw_dump_sample)
        classifier = ZenonClassifier()
        classify_res: ClassifyResult = classifier.classify_raw_dump(raw_model)

        assert isinstance(classify_res, ClassifyResult)
        contract = classify_res.contract

        # Contract checks
        assert len(contract.buses) == 3
        bus_ids = {b.id for b in contract.buses}
        assert bus_ids == {"BB01", "BB02", "BB03"}

        assert len(contract.transformers) == 1
        assert contract.transformers[0].id == "TR_BB01_BB02"
        assert contract.transformers[0].from_bus == "BB01"
        assert contract.transformers[0].to_bus == "BB02"
        assert contract.transformers[0].rating_mva == 45.0

        assert len(contract.lines) == 2
        line_ids = {l.id for l in contract.lines}
        assert "LINE_BB02_BB03" in line_ids
        assert "LINE_BB01_BB03" in line_ids

        assert len(contract.breakers) == 3
        breaker_ids = {b.id for b in contract.breakers}
        assert {"XCBR_01", "XCBR_02", "XCBR_03"}.issubset(breaker_ids)

        assert len(contract.loads) == 2
        load_ids = {ld.id for ld in contract.loads}
        assert {"LOAD_FDR1", "LOAD_FDR2"}.issubset(load_ids)

        assert len(contract.generators) == 1
        assert contract.generators[0].id == "GEN_SOLAR1"

        assert len(contract.sources) == 1
        assert contract.sources[0].id == "GRID_SOURCE"

        # 2. Reader end-to-end auto-detecting raw dump
        result = parse_zenon_export(raw_dump_sample)
        assert result.is_valid
        assert isinstance(result.system, System)
        assert len(result.system.buses) == 3
        assert len(result.system.transformers) == 1
        assert len(result.system.lines) == 2
        assert len(result.system.loads) == 2

        # Grid source was converted into slack bus + infeed generator
        assert result.system.buses["BB01"].bus_type == "slack"
        # Total generators in system: 1 solar PV + 1 grid source slack generator
        assert len(result.system.generators) == 2

    def test_unmapped_elements_recorded_with_warnings(self, raw_dump_sample: dict):
        """Unrecognized variables/sensors must be recorded in unmapped[] with warnings."""
        raw_model = ZenonRawDump.model_validate(raw_dump_sample)
        classifier = ZenonClassifier()
        classify_res = classifier.classify_raw_dump(raw_model)

        # WEATHER_STATION_TEMP_AMBIENT has no electrical type
        unmapped_ids = {u["id"] for u in classify_res.unmapped}
        assert "WEATHER_STATION_TEMP_AMBIENT" in unmapped_ids
        assert any(
            "WEATHER_STATION_TEMP_AMBIENT" in w and "could not be classified" in w
            for w in classify_res.warnings
        )

    def test_incomplete_topology_recorded(self, raw_dump_sample: dict):
        """Elements with missing topology must be isolated in incomplete[] instead of guessed."""
        # Inject an ambiguous line without from_bus / to_bus
        raw_dump_sample["variables"].append(
            {
                "name": "LINE_FLOATING.R",
                "identification": "Floating line with unknown endpoints",
                "value": 0.02,
            }
        )
        raw_model = ZenonRawDump.model_validate(raw_dump_sample)
        classifier = ZenonClassifier()
        classify_res = classifier.classify_raw_dump(raw_model)

        incomplete_ids = {inc["id"] for inc in classify_res.incomplete}
        assert "LINE_FLOATING" in incomplete_ids
        assert any(inc["reason"] == "missing_terminal_buses" for inc in classify_res.incomplete)

    def test_deterministic_output(self, raw_dump_sample: dict):
        """Repeated classification runs on identical data must return identical outputs."""
        r1 = parse_zenon_export(raw_dump_sample)
        r2 = parse_zenon_export(raw_dump_sample)

        assert len(r1.system.buses) == len(r2.system.buses)
        assert len(r1.contract.buses) == len(r2.contract.buses)
        assert len(r1.contract.lines) == len(r2.contract.lines)
        assert len(r1.warnings) == len(r2.warnings)
        assert len(r1.errors) == len(r2.errors)

    def test_zenon_export_sample_znx_parsing(self, export_znx_sample: str):
        """Verifies parsing of the sample .znx file."""
        result = parse_zenon_export(export_znx_sample)
        assert result.is_valid
        assert len(result.errors) == 0

        # Verifies topology
        assert len(result.contract.buses) == 3
        assert len(result.contract.lines) == 1
        assert len(result.contract.transformers) == 1
        assert len(result.contract.breakers) == 2
        assert len(result.contract.switches) == 1
        assert len(result.contract.loads) == 2
        assert len(result.contract.generators) == 1
        assert len(result.contract.sources) == 1

        # Verifies system electrical IR
        system = result.system
        assert "BUS_132_HV" in system.buses
        assert system.buses["BUS_132_HV"].bus_type == "slack"
        assert len(system.transformers) == 1
        assert len(system.lines) == 1
        assert len(system.loads) == 2
        # Generators: 1 PV farm + 1 grid slack source
        assert len(system.generators) == 2

    def test_source_without_bus_records_error(self, raw_dump_sample: dict):
        """A source pointing to an invalid bus must record an error."""
        contract_dict = {
            "contract_version": "1.0.0",
            "project": {"name": "Test Project"},
            "buses": [{"id": "BUS1", "name": "Bus 1", "base_kv": 11.0, "v_ang": 0.0}],
            "sources": [{"id": "SRC1", "name": "Source 1", "bus": "MISSING_BUS"}],
        }
        res = parse_zenon_export(contract_dict)
        assert not res.is_valid
        assert any("connected bus 'MISSING_BUS' does not exist" in e for e in res.errors)

    def test_missing_source_warns(self):
        """Export without any source must emit an explicit warning."""
        contract_dict = {
            "contract_version": "1.0.0",
            "project": {"name": "Islanded Grid"},
            "buses": [{"id": "BUS1", "name": "Bus 1", "base_kv": 11.0, "v_ang": 0.0}],
            "sources": [],
        }
        res = parse_zenon_export(contract_dict)
        assert any("slack bus not defined" in w or "No utility source" in w for w in res.warnings)
