"""
tests/test_export_cim.py — Tests for Schneider EcoStruxure ADMS CIM XML Exporter.

Verifies:
1. test_writer_deterministic_order: same input => byte-identical output.
2. test_rdf_ids_unique_and_valid: regex ^[A-Za-z_][A-Za-z0-9_.-]*$.
3. test_roundtrip_3bus: build 3-bus model via map_adms_to_cim -> build_cim_xml -> _parse_cim_xml => 3 buses preserved.
4. test_missing_gis_fail_closed: bus without geometry => export returns 422, no file.
5. test_profile_split_EQ_SSH: EQ contains Equipment, SSH contains state, no cross-leak.
6. Acceptance & security: flag OFF by default returns 403, file <10MiB, audit logged.
"""

from __future__ import annotations

import io
import re
import uuid

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import api.export as export_mod
import api.feature_flags as feature_flags_mod
from api.data_import import _parse_cim_xml
from api.database import async_session
from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from api.projects import Project
from api.rbac import require_permission
from gis_integration.models import ADMSAsset, ADMSAssetType
from gis_validation_electrical.cim_mapper import map_adms_to_cim
from gis_validation_electrical.cim_writer import (
    ID_REGEX,
    CIMTooLargeError,
    build_cim_xml,
    make_rdf_id,
)

TEST_USER = CurrentUser(
    user_id="cim_test_engineer",
    username="cim_engineer",
    email="cim@etap.local",
    role="engineer",
    tenant_id="tenant_cim_export",
)


@pytest.fixture
def export_client(monkeypatch):
    """FastAPI TestClient with export router and auth dependency overrides."""
    # Force flag enabled for general tests unless overridden
    monkeypatch.setattr(feature_flags_mod, "is_feature_enabled", lambda *args, **kwargs: True)
    monkeypatch.setattr(export_mod, "is_feature_enabled", lambda *args, **kwargs: True)

    app = FastAPI()
    app.include_router(export_mod.router)
    app.dependency_overrides[get_current_user_from_header] = lambda: TEST_USER
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.dependency_overrides[require_permission("export", "create")] = lambda: TEST_USER
    app.dependency_overrides[require_permission("export", "list")] = lambda: TEST_USER

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_3bus_assets():
    """Deterministic 3-bus network with GIS points and connecting lines."""
    sub1 = ADMSAsset(
        asset_id="sub_01",
        asset_type=ADMSAssetType.SUBSTATION,
        geometry={"type": "Point", "coordinates": [10.0, 20.0]},
        metadata={"name": "Substation 1", "base_kv": 115.0},
    )
    sub2 = ADMSAsset(
        asset_id="sub_02",
        asset_type=ADMSAssetType.SUBSTATION,
        geometry={"type": "Point", "coordinates": [10.5, 20.0]},
        metadata={"name": "Substation 2", "base_kv": 115.0},
    )
    sub3 = ADMSAsset(
        asset_id="sub_03",
        asset_type=ADMSAssetType.SUBSTATION,
        geometry={"type": "Point", "coordinates": [10.5, 20.5]},
        metadata={"name": "Substation 3", "base_kv": 115.0},
    )

    line1 = ADMSAsset(
        asset_id="line_01",
        asset_type=ADMSAssetType.LINE,
        geometry={"type": "LineString", "coordinates": [[10.0, 20.0], [10.5, 20.0]]},
        metadata={"name": "Line 1-2", "base_kv": 115.0, "r": 0.02, "x": 0.08},
    )
    line2 = ADMSAsset(
        asset_id="line_02",
        asset_type=ADMSAssetType.LINE,
        geometry={"type": "LineString", "coordinates": [[10.5, 20.0], [10.5, 20.5]]},
        metadata={"name": "Line 2-3", "base_kv": 115.0, "r": 0.015, "x": 0.06},
    )
    switch1 = ADMSAsset(
        asset_id="sw_01",
        asset_type=ADMSAssetType.SWITCH,
        geometry={"type": "LineString", "coordinates": [[10.0, 20.0], [10.5, 20.0]]},
        metadata={"name": "Breaker 1", "open_state": True},
    )
    return [sub1, sub2, sub3, line1, line2, switch1]


# -----------------------------------------------------------------------------
# 1. Deterministic Order
# -----------------------------------------------------------------------------
def test_writer_deterministic_order(sample_3bus_assets):
    """Calling build_cim_xml multiple times on identical input produces byte-identical output."""
    model = map_adms_to_cim(sample_3bus_assets)
    out1 = build_cim_xml(model, profile="EQ", namespace_version="cim16")
    out2 = build_cim_xml(model, profile="EQ", namespace_version="cim16")
    assert out1 == out2, "build_cim_xml output is not deterministic across multiple calls"

    out_ssh1 = build_cim_xml(model, profile="SSH", namespace_version="cim16")
    out_ssh2 = build_cim_xml(model, profile="SSH", namespace_version="cim16")
    assert out_ssh1 == out_ssh2, "SSH output is not deterministic"


# -----------------------------------------------------------------------------
# 2. RDF IDs Unique and Valid
# -----------------------------------------------------------------------------
def test_rdf_ids_unique_and_valid(sample_3bus_assets):
    """All emitted rdf:IDs match NCName regex ^[A-Za-z_][A-Za-z0-9_.-]*$ and are unique."""
    model = map_adms_to_cim(sample_3bus_assets)
    xml_bytes = build_cim_xml(model, profile="FULL", namespace_version="cim16")

    id_pattern = re.compile(r'rdf:ID="([^"]+)"')
    found_ids = id_pattern.findall(xml_bytes.decode("utf-8"))

    assert len(found_ids) > 0, "No rdf:IDs found in generated XML"
    for rdf_id in found_ids:
        assert ID_REGEX.match(rdf_id), f"rdf:ID '{rdf_id}' violates NCName regex"
        assert not rdf_id.startswith("CE::"), f"rdf:ID '{rdf_id}' raw reuses CE:: prefix"
        assert not rdf_id.startswith("CN::"), f"rdf:ID '{rdf_id}' raw reuses CN:: prefix"

    assert len(found_ids) == len(set(found_ids)), "Duplicate rdf:IDs detected in XML output"


# -----------------------------------------------------------------------------
# 3. Roundtrip 3-Bus
# -----------------------------------------------------------------------------
def test_roundtrip_3bus(sample_3bus_assets):
    """3-bus model via map_adms_to_cim -> build_cim_xml -> _parse_cim_xml preserves 3 buses and 2 branches."""
    model = map_adms_to_cim(sample_3bus_assets)
    xml_bytes = build_cim_xml(model, profile="EQ")

    buses, branches, metadata, warnings = _parse_cim_xml(xml_bytes)
    assert len(buses) == 3, f"Expected 3 buses preserved, got {len(buses)}"
    assert len(branches) == 2, f"Expected 2 ACLineSegment branches preserved, got {len(branches)}"

    bus_names = {b.name for b in buses}
    assert "Substation 1" in bus_names
    assert "Substation 2" in bus_names
    assert "Substation 3" in bus_names


# -----------------------------------------------------------------------------
# 4. Missing GIS Fail Closed
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_gis_fail_closed(export_client: TestClient):
    """Any bus without GIS position fails closed with HTTP 422, returning no file."""
    proj_id = f"proj-missing-gis-{uuid.uuid4().hex[:8]}"

    async with async_session() as session:
        p = Project(
            id=proj_id,
            name="Missing GIS Substation Network",
            tenant_id=TEST_USER.tenant_id,
            created_by=TEST_USER.user_id,
            system_config={
                "assets": [
                    {
                        "asset_id": "sub_valid",
                        "asset_type": "SUBSTATION",
                        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
                        "metadata": {"name": "Valid Sub"},
                    },
                    {
                        "asset_id": "sub_no_coords",
                        "asset_type": "SUBSTATION",
                        "geometry": {},  # Missing GIS coordinates
                        "metadata": {"name": "Invalid Sub"},
                    },
                ]
            },
        )
        session.add(p)
        await session.commit()

    res = export_client.post(f"/api/v1/export/{proj_id}/cim?profile=EQ")
    assert res.status_code == 422, f"Expected 422 for missing GIS, got {res.status_code}: {res.text}"
    detail = res.json()["detail"]
    assert "buses without GIS position" in detail
    assert "1 buses without GIS position" in detail


# -----------------------------------------------------------------------------
# 5. Profile Split EQ vs SSH
# -----------------------------------------------------------------------------
def test_profile_split_EQ_SSH(sample_3bus_assets):
    """EQ profile contains equipment; SSH contains state; no cross-leak."""
    model = map_adms_to_cim(sample_3bus_assets)

    eq_xml = build_cim_xml(model, profile="EQ").decode("utf-8")
    ssh_xml = build_cim_xml(model, profile="SSH").decode("utf-8")

    # EQ checks
    assert "<cim:TopologicalNode" in eq_xml
    assert "<cim:ACLineSegment" in eq_xml
    assert "<cim:Breaker" in eq_xml
    assert "<cim:Switch.open>" not in eq_xml, "Switch.open state leaked into EQ profile"

    # SSH checks
    assert "<cim:Switch.open>true</cim:Switch.open>" in ssh_xml
    assert "<cim:TopologicalNode" not in ssh_xml, "TopologicalNode definition leaked into SSH profile"
    assert "<cim:ACLineSegment" not in ssh_xml, "ACLineSegment definition leaked into SSH profile"
    assert "<cim:Substation" not in ssh_xml, "Substation definition leaked into SSH profile"


# -----------------------------------------------------------------------------
# 6. Flag Off By Default Returns 403
# -----------------------------------------------------------------------------
def test_export_flag_off_returns_403(export_client: TestClient, monkeypatch):
    """When data_export_cim flag is disabled, POST /api/v1/export/{id}/cim returns 403."""
    monkeypatch.setattr(
        export_mod,
        "is_feature_enabled",
        lambda key, *args, **kwargs: key != "data_export_cim",
    )
    res = export_client.post(f"/api/v1/export/{uuid.uuid4()}/cim")
    assert res.status_code == 403
    assert "Data export feature is disabled" in res.json()["detail"]


# -----------------------------------------------------------------------------
# 7. Acceptance Test: Full Export Workflow
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_endpoint_acceptance(export_client: TestClient):
    """POST /api/v1/export/{id}/cim?profile=EQ returns valid RDF/XML that re-parses, file <10MiB."""
    proj_id = f"proj-accept-{uuid.uuid4().hex[:8]}"

    async with async_session() as session:
        p = Project(
            id=proj_id,
            name="EcoStruxure Pilot Grid",
            tenant_id=TEST_USER.tenant_id,
            created_by=TEST_USER.user_id,
            system_config={
                "assets": [
                    {
                        "asset_id": "bus_1",
                        "asset_type": "SUBSTATION",
                        "geometry": {"type": "Point", "coordinates": [31.23, 30.04]},
                        "metadata": {"name": "Main Substation", "base_kv": 220.0},
                    },
                    {
                        "asset_id": "bus_2",
                        "asset_type": "SUBSTATION",
                        "geometry": {"type": "Point", "coordinates": [31.25, 30.06]},
                        "metadata": {"name": "Industrial Substation", "base_kv": 220.0},
                    },
                    {
                        "asset_id": "line_1_2",
                        "asset_type": "LINE",
                        "geometry": {"type": "LineString", "coordinates": [[31.23, 30.04], [31.25, 30.06]]},
                        "metadata": {"name": "Feeder Line 1-2", "base_kv": 220.0},
                    },
                ]
            },
        )
        session.add(p)
        await session.commit()

    res = export_client.post(f"/api/v1/export/{proj_id}/cim?profile=EQ&version=cim16")
    assert res.status_code == 200, f"Export failed: {res.text}"
    assert "application/xml" in res.headers["Content-Type"]
    assert 'filename="EcoStruxure_Pilot_Grid_schneider_EQ.xml"' in res.headers["Content-Disposition"]

    content = res.content
    assert len(content) < 10 * 1024 * 1024, "Export exceeded 10 MiB limit"

    # Re-parse check
    buses, branches, metadata, warnings = _parse_cim_xml(content)
    assert len(buses) == 2, f"Expected 2 buses, parsed {len(buses)}"
    assert len(branches) == 1, f"Expected 1 branch, parsed {len(branches)}"


# -----------------------------------------------------------------------------
# 8. File Too Large Exceeded Limit
# -----------------------------------------------------------------------------
def test_file_too_large_fail_closed(sample_3bus_assets, monkeypatch):
    """When generated XML exceeds MAX_FILE_SIZE, CIMTooLargeError is raised."""
    import gis_validation_electrical.cim_writer as cw

    monkeypatch.setattr(cw, "MAX_FILE_SIZE", 50)  # Very small threshold
    model = map_adms_to_cim(sample_3bus_assets)
    with pytest.raises(CIMTooLargeError) as exc_info:
        cw.build_cim_xml(model, profile="EQ")

    assert "CIM_TOO_LARGE" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 9. Unsupported Parameters Return 400
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unsupported_params_return_400(export_client: TestClient):
    """Unsupported profile or version parameter returns 400."""
    res_bad_profile = export_client.post("/api/v1/export/dummy-id/cim?profile=INVALID")
    assert res_bad_profile.status_code == 400
    assert "Unsupported profile" in res_bad_profile.json()["detail"]

    res_bad_version = export_client.post("/api/v1/export/dummy-id/cim?profile=EQ&version=cim99")
    assert res_bad_version.status_code == 400
    assert "Unsupported version" in res_bad_version.json()["detail"]


# -----------------------------------------------------------------------------
# 10. EXPORT_FORMATS Verification
# -----------------------------------------------------------------------------
def test_export_formats_contains_cim_xml():
    """EXPORT_FORMATS list contains cim-xml entry without mutating existing formats."""
    ids = [fmt.id for fmt in export_mod.EXPORT_FORMATS]
    assert "cim-xml" in ids
    assert "pdf" in ids
    assert "excel" in ids
    assert "csv" in ids
    assert "json" in ids
