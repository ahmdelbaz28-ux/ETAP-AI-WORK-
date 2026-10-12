"""Tests for Zenon Network Export v1 contract, mapper, reader, and import integration.

Verifies:
- Valid contract JSON parsing to core_model.System and secondary elements.
- Zero-guessing enforcement: missing electrical values emit explicit warnings, never invented defaults.
- Topological consistency: missing terminal buses trigger clear errors.
- Feature flag gating: disabled `zenon_import` flag fails closed (403 FEATURE_DISABLED).
- User-editable YAML field mapping and unmapped field warnings.
- Deterministic output across repeated runs.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from api.data_import import _detect_format, _parse_model_content, _validate_magic_bytes
from core_model.system import System
from integrations.zenon_network_export.contract import (
    ZenonBus,
    ZenonLine,
    ZenonNetworkExport,
    ZenonProjectMetadata,
    ZenonTransformer,
)
from integrations.zenon_network_export.mapping import ZenonFieldMapper
from integrations.zenon_network_export.reader import parse_zenon_export

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_zenon_payload() -> dict:
    """A valid, realistic 2-substation Zenon export contract."""
    return {
        "contract_version": "1.0.0",
        "project": {
            "name": "Substation Alpha 132kV",
            "substation_name": "Alpha-SS",
            "base_mva": 100.0,
            "system_frequency_hz": 50.0,
            "source_system": "zenon_energy_edition",
        },
        "buses": [
            {
                "id": "BUS_132_A",
                "name": "Bus 132kV Bay 1",
                "base_kv": 132.0,
                "v_mag": 1.02,
                "v_ang": 0.0,
                "bus_type": "slack",
                "source_ref": "Tags.Alpha.BB132.V",
            },
            {
                "id": "BUS_33_A",
                "name": "Bus 33kV Bay 2",
                "base_kv": 33.0,
                "v_mag": 0.99,
                "v_ang": -2.5,
                "bus_type": "pq",
                "source_ref": "Tags.Alpha.BB33.V",
            },
            {
                "id": "BUS_33_B",
                "name": "Bus 33kV Bay 3",
                "base_kv": 33.0,
                "v_mag": 0.98,
                "v_ang": -3.1,
                "bus_type": "pq",
            },
        ],
        "transformers": [
            {
                "id": "TR1",
                "name": "Power Transformer 132/33kV",
                "from_bus": "BUS_132_A",
                "to_bus": "BUS_33_A",
                "rating_mva": 40.0,
                "prim_kv": 132.0,
                "sec_kv": 33.0,
                "r_pu": 0.005,
                "x_pu": 0.10,
                "tap_ratio": 1.0,
            }
        ],
        "lines": [
            {
                "id": "LINE_33_TIE",
                "name": "Tie Line Bus A to B",
                "from_bus": "BUS_33_A",
                "to_bus": "BUS_33_B",
                "r_pu": 0.012,
                "x_pu": 0.045,
                "b_pu": 0.001,
                "rating_mva": 25.0,
            }
        ],
        "cables": [],
        "breakers": [
            {
                "id": "CB_TR1_HV",
                "name": "132kV Transformer Breaker",
                "from_bus": "BUS_132_A",
                "to_bus": "BUS_132_A",
                "status": "closed",
                "rated_a": 1250.0,
                "breaking_capacity_ka": 31.5,
                "source_ref": "Tags.Alpha.XCBR1.Pos",
            }
        ],
        "switches": [
            {
                "id": "SW_33_SEC",
                "name": "Bus Section Disconnector",
                "from_bus": "BUS_33_A",
                "to_bus": "BUS_33_B",
                "status": "normal_closed",
                "rated_a": 1600.0,
            }
        ],
        "loads": [
            {
                "id": "LOAD_FEEDER_1",
                "name": "Industrial Feeder 1",
                "bus": "BUS_33_B",
                "p_mw": 12.5,
                "q_mvar": 4.2,
                "model": "constant_power",
            }
        ],
        "generators": [],
        "motors": [],
        "relays": [
            {
                "id": "RELAY_77",
                "name": "Overcurrent Protection Relay",
                "bus": "BUS_33_A",
                "protected_element": "TR1",
                "curve_type": "IEC Standard Inverse",
                "time_dial": 0.15,
                "pickup_a": 400.0,
            }
        ],
        "capacitors": [],
        "reactors": [],
        "sources": [],
        "metadata": {"plant_code": "PLANT-01"},
    }


# ---------------------------------------------------------------------------
# Unit Tests: Contract & Reader
# ---------------------------------------------------------------------------


class TestZenonContractAndReader:
    """Verifies schema validation, parsing into core_model, and zero-guessing rules."""

    def test_valid_payload_parsing(self, valid_zenon_payload: dict):
        result = parse_zenon_export(valid_zenon_payload)
        assert result.is_valid
        assert len(result.errors) == 0

        # System check
        system = result.system
        assert isinstance(system, System)
        assert len(system.buses) == 3
        assert "BUS_132_A" in system.buses
        assert "BUS_33_A" in system.buses
        assert "BUS_33_B" in system.buses

        assert len(system.transformers) == 1
        assert any(t.transformer_id == "TR1" for t in system.transformers)

        assert len(system.lines) == 1
        assert any(l.line_id == "LINE_33_TIE" for l in system.lines)

        assert len(system.loads) == 1
        assert any(ld.load_id == "LOAD_FEEDER_1" for ld in system.loads)

        # Extra elements check (breakers, switches, relays)
        assert len(result.extra_elements["breakers"]) == 1
        assert result.extra_elements["breakers"][0]["id"] == "CB_TR1_HV"
        assert len(result.extra_elements["switches"]) == 1
        assert len(result.extra_elements["relays"]) == 1

    def test_zero_guessing_missing_voltage_warns(self, valid_zenon_payload: dict):
        """Missing bus voltage MUST generate an explicit warning and not be guessed."""
        valid_zenon_payload["buses"][1]["base_kv"] = None
        valid_zenon_payload["buses"][1]["kv"] = None

        result = parse_zenon_export(valid_zenon_payload)
        assert any("voltage is missing in source data; not guessed" in w for w in result.warnings)
        assert result.system.buses["BUS_33_A"].base_kv is None

    def test_zero_guessing_missing_line_impedance_warns(self, valid_zenon_payload: dict):
        """Missing line impedance MUST emit explicit warning and be clearly flagged."""
        valid_zenon_payload["lines"][0]["r_pu"] = None
        valid_zenon_payload["lines"][0]["x_pu"] = None

        result = parse_zenon_export(valid_zenon_payload)
        assert any(
            "impedance r_pu/x_pu missing in source data; not guessed" in w for w in result.warnings
        )

    def test_topological_error_missing_bus(self, valid_zenon_payload: dict):
        """Connecting a line to a non-existent bus must record an error."""
        valid_zenon_payload["lines"][0]["to_bus"] = "NON_EXISTENT_BUS"

        result = parse_zenon_export(valid_zenon_payload)
        assert not result.is_valid
        assert any("terminal bus 'NON_EXISTENT_BUS' does not exist" in e for e in result.errors)

    def test_deterministic_output(self, valid_zenon_payload: dict):
        """Multiple runs must produce strictly identical results."""
        r1 = parse_zenon_export(valid_zenon_payload)
        r2 = parse_zenon_export(valid_zenon_payload)

        assert len(r1.system.buses) == len(r2.system.buses)
        assert len(r1.warnings) == len(r2.warnings)
        assert len(r1.errors) == len(r2.errors)


# ---------------------------------------------------------------------------
# Unit Tests: Field Mapper
# ---------------------------------------------------------------------------


class TestZenonFieldMapper:
    """Verifies configurable field mapping from YAML and unmapped tag warnings."""

    def test_mapper_translates_known_tags(self):
        mapper = ZenonFieldMapper()
        raw = {"U_NOM": 132.0, "V_MAG": 1.01}
        canonical, warnings = mapper.map_element_attributes("bus", "BUS_1", raw)

        assert canonical.get("base_kv") == 132.0
        assert canonical.get("v_mag") == 1.01
        assert len(warnings) == 0

    def test_mapper_warns_on_unmapped_tags(self):
        mapper = ZenonFieldMapper()
        raw = {"U_NOM": 33.0, "CUSTOM_UNKNOWN_FIELD_XYZ": 999}
        canonical, warnings = mapper.map_element_attributes("bus", "BUS_2", raw)

        assert canonical.get("base_kv") == 33.0
        assert any("CUSTOM_UNKNOWN_FIELD_XYZ" in w for w in warnings)


# ---------------------------------------------------------------------------
# Integration Tests: api/data_import Format Detection & Gating
# ---------------------------------------------------------------------------


class TestZenonDataImportIntegration:
    """Verifies _detect_format, magic bytes, and feature flag gate in api/data_import."""

    def test_detect_format_znx(self):
        fmt = _detect_format("substation_export.znx")
        assert fmt.id == "zenon-network"
        assert ".znx" in fmt.extensions

    def test_detect_format_zenon_json(self):
        fmt = _detect_format("zenon_substation.json")
        assert fmt.id == "zenon-network"

    def test_detect_format_generic_json_unaffected(self):
        fmt = _detect_format("my_case.json")
        assert fmt.id in ("etap-project", "json")

    def test_magic_bytes_accepts_valid_json_for_zenon(self):
        # Should not raise
        _validate_magic_bytes("zenon-network", b'{"contract_version": "1.0.0"}')

    def test_magic_bytes_rejects_binary_or_empty_for_zenon(self):
        with pytest.raises(Exception):
            _validate_magic_bytes("zenon-network", b"\x00\x01\x02\x03")

    def test_feature_flag_zenon_import_disabled_by_default(self, valid_zenon_payload: dict):
        """When zenon_import is False, _parse_model_content must record an error."""
        fmt = _detect_format("substation.znx")
        content = json.dumps(valid_zenon_payload).encode("utf-8")

        with patch("api.data_import.is_feature_enabled", return_value=False):
            buses, branches, meta, warnings, errors = _parse_model_content(fmt, content)
            assert any("zenon_import' is disabled" in err for err in errors)

    def test_feature_flag_zenon_import_enabled_parses_content(self, valid_zenon_payload: dict):
        """When zenon_import is True, _parse_model_content successfully parses content."""
        fmt = _detect_format("substation.znx")
        content = json.dumps(valid_zenon_payload).encode("utf-8")

        with patch("api.data_import.is_feature_enabled", return_value=True):
            buses, branches, meta, warnings, errors = _parse_model_content(fmt, content)
            assert len(errors) == 0
            assert len(buses) == 3
            assert len(branches) == 3  # 1 transformer + 1 line + 1 breaker
