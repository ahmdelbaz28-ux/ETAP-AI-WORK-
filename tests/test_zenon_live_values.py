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
