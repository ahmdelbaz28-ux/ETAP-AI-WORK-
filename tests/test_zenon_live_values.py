"""Unit and Integration Tests for Zenon Live Values SCADA Enrichment (Phase F).

Verifies:
1. Feature flag gating: disabled by default (fail-closed).
2. Unreachable live gateway reports BLOCKED with warning without failing network import.
3. Successful live measurement enrichment updates bus voltages, load power, and breaker states.
"""

from __future__ import annotations

import pytest

from core_model.bus import Bus
from core_model.load import Load
from core_model.system import System
from integrations.zenon_network_export.contract import (
    ZenonNetworkExport,
    ZenonProjectMetadata,
)
from integrations.zenon_network_export.live_values import (
    enrich_zenon_live_values,
    is_zenon_live_values_enabled,
)
from integrations.zenon_network_export.reader import ZenonImportResult


@pytest.fixture
def sample_import_result() -> ZenonImportResult:
    sys = System(base_mva=100.0)
    b1 = Bus(bus_id="BUS_1", base_kv=132.0, voltage_magnitude=1.0)
    b2 = Bus(bus_id="BUS_2", base_kv=33.0, voltage_magnitude=1.0)
    sys.add_bus(b1)
    sys.add_bus(b2)

    ld1 = Load(load_id="LOAD_1", bus=b2, load_power=complex(10.0, 5.0))
    sys.add_load(ld1)

    contract = ZenonNetworkExport(
        project=ZenonProjectMetadata(name="Test Project", source_system="zenon")
    )
    extra = {
        "breakers": [{"id": "BRK_1", "status": 0}],
        "switches": [{"id": "SW_1", "status": 0}],
    }
    return ZenonImportResult(
        system=sys,
        contract=contract,
        extra_elements=extra,
        warnings=[],
        errors=[],
        incomplete=[],
    )


def test_feature_flag_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FEATURE_FLAG_ZENON_LIVE_VALUES", raising=False)
    assert is_zenon_live_values_enabled() is False


@pytest.mark.asyncio
async def test_enrichment_skipped_when_flag_off(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "false")
    res = await enrich_zenon_live_values(sample_import_result)
    assert len(res.warnings) == 0
    assert len(res.incomplete) == 0
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.0


@pytest.mark.asyncio
async def test_unreachable_server_reports_blocked_without_failing_import(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")
    # Point to closed local port to verify graceful failure
    res = await enrich_zenon_live_values(
        sample_import_result, endpoint="opc.tcp://127.0.0.1:59999/zenon/gateway"
    )
    # Network import did not crash
    assert res.is_valid
    assert any("BLOCKED" in w for w in res.warnings)
    assert any(inc.get("status") == "BLOCKED" for inc in res.incomplete)


@pytest.mark.asyncio
async def test_live_data_enrichment_updates_elements(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")
    mock_live_data = {
        "voltages": {"BUS_1": 1.025, "BUS_2": 0.985},
        "loads": {"LOAD_1": 12.5},
        "status": {"BRK_1": 1, "SW_1": 1},
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_live_data,
    )
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.025
    assert res.system.buses["BUS_2"].voltage_magnitude == 0.985
    assert res.system.loads[0].load_power.real == 12.5
    assert res.system.loads[0].load_power.imag == 5.0
    assert res.extra_elements["breakers"][0]["status"] == 1
    assert res.extra_elements["switches"][0]["status"] == 1


@pytest.mark.asyncio
async def test_tcp_connection_without_telemetry_reports_telemetry_unavailable(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Raw TCP socket connection must NOT claim successful telemetry enrichment."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    from unittest.mock import AsyncMock, patch

    mock_writer = AsyncMock()
    mock_writer.close = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    mock_reader = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        res = await enrich_zenon_live_values(
            sample_import_result, endpoint="opc.tcp://127.0.0.1:4840/zenon/gateway"
        )

    # Must report TELEMETRY_UNAVAILABLE rather than silently claiming success
    assert any("TELEMETRY_UNAVAILABLE" in inc.get("status", "") for inc in res.incomplete)
    assert any("live telemetry data reading is unavailable" in w for w in res.warnings)
    # Voltage should NOT be mutated on raw TCP connect
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.0


@pytest.mark.asyncio
async def test_empty_live_data_payload_reports_empty_telemetry(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Empty or missing variables in live_data must NOT silently succeed."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    # 1. Empty dict
    res_empty = await enrich_zenon_live_values(
        sample_import_result,
        live_data={},
    )
    assert any("EMPTY_TELEMETRY" in inc.get("status", "") for inc in res_empty.incomplete)
    assert any("empty" in w for w in res_empty.warnings)

    # 2. Dict with no readings
    res_no_vars = await enrich_zenon_live_values(
        sample_import_result,
        live_data={"voltages": {}, "loads": {}, "status": {}},
    )
    assert any("EMPTY_TELEMETRY" in inc.get("status", "") for inc in res_no_vars.incomplete)


@pytest.mark.asyncio
async def test_distinct_statuses_for_connection_fail_vs_no_telemetry_vs_empty(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Failure states must be distinct: BLOCKED (connect fail) vs TELEMETRY_UNAVAILABLE vs EMPTY_TELEMETRY."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    # A. Connection failure
    res_conn_fail = await enrich_zenon_live_values(
        sample_import_result, endpoint="opc.tcp://127.0.0.1:59998/zenon/gateway"
    )
    statuses_a = [inc.get("status") for inc in res_conn_fail.incomplete]
    assert "BLOCKED" in statuses_a

    # B. Empty data
    res_empty = await enrich_zenon_live_values(
        sample_import_result, live_data={}
    )
    statuses_b = [inc.get("status") for inc in res_empty.incomplete]
    assert "EMPTY_TELEMETRY" in statuses_b

    assert statuses_a != statuses_b


@pytest.mark.asyncio
async def test_non_empty_payload_with_unknown_tags_does_not_label_enriched(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Payload with non-matching tags must return NO_MATCHING_TAGS, never ENRICHED."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    mock_unmatched = {
        "voltages": {"UNKNOWN_BUS_999": 1.05},
        "loads": {"UNKNOWN_LOAD_888": 50.0},
        "status": {"UNKNOWN_SW_777": 1},
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_unmatched,
    )

    assert res.extra_elements.get("zenon_live_enrichment") == "NO_MATCHING_TAGS"
    assert res.extra_elements.get("zenon_live_enrichment") != "ENRICHED"
    counts = res.extra_elements.get("zenon_live_telemetry_counts", {})
    assert counts.get("voltages_updated") == 0
    assert counts.get("loads_updated") == 0
    assert counts.get("switches_updated") == 0
    assert any(inc.get("status") == "NO_MATCHING_TAGS" for inc in res.incomplete)
    # Bus 1 untouched
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.0


@pytest.mark.asyncio
async def test_malformed_readings_zero_updates_does_not_label_enriched(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Payload with invalid/unparseable values resulting in 0 updates returns NO_MATCHING_TAGS."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    mock_malformed = {
        "voltages": {"BUS_1": "not-a-number"},
        "loads": {"LOAD_1": "corrupt_data"},
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_malformed,
    )

    assert res.extra_elements.get("zenon_live_enrichment") == "NO_MATCHING_TAGS"
    assert res.extra_elements.get("zenon_live_enrichment") != "ENRICHED"
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.0


@pytest.mark.asyncio
async def test_nonfinite_numeric_values_rejected(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """NaN, +inf, -inf, and non-positive voltages/loads are rejected and not applied."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    mock_nonfinite = {
        "voltages": {
            "BUS_1": float("nan"),
            "BUS_2": float("inf"),
        },
        "loads": {
            "LOAD_1": float("-inf"),
        },
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_nonfinite,
    )
    # Neither bus voltage was mutated
    assert res.system.buses["BUS_1"].voltage_magnitude == 1.0
    assert res.system.buses["BUS_2"].voltage_magnitude == 1.0
    # Load was not mutated
    assert res.system.loads[0].load_power.real == 10.0
    assert res.extra_elements.get("zenon_live_enrichment") == "NO_MATCHING_TAGS"


@pytest.mark.asyncio
async def test_fractional_switch_states_rejected_without_truncation(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Fractional switch floats like 1.5 must NOT be truncated to 1; must be rejected."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    mock_fractional = {
        "status": {
            "BRK_1": 1.5,   # Must NOT truncate to 1
            "SW_1": 0.7,    # Must NOT truncate to 0
        },
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_fractional,
    )
    # Breaker and switch statuses remain at their original static values (0)
    assert res.extra_elements["breakers"][0]["status"] == 0
    assert res.extra_elements["switches"][0]["status"] == 0
    counts = res.extra_elements.get("zenon_live_telemetry_counts", {})
    assert counts.get("switches_updated") == 0


@pytest.mark.asyncio
async def test_valid_discrete_switch_states_succeed(
    sample_import_result: ZenonImportResult, monkeypatch: pytest.MonkeyPatch
):
    """Discrete values (0, 1, 'closed', 'open', True, False) correctly update status."""
    monkeypatch.setenv("FEATURE_FLAG_ZENON_LIVE_VALUES", "true")

    mock_discrete = {
        "status": {
            "BRK_1": "closed",
            "SW_1": 1.0,  # Exact integer float
        },
    }
    res = await enrich_zenon_live_values(
        sample_import_result,
        live_data=mock_discrete,
    )
    assert res.extra_elements["breakers"][0]["status"] == 1
    assert res.extra_elements["switches"][0]["status"] == 1
    counts = res.extra_elements.get("zenon_live_telemetry_counts", {})
    assert counts.get("switches_updated") == 2
