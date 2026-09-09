"""tests/test_arcgis_edits.py — Comprehensive test suite for safe ArcGIS Online / Enterprise writes.

Verifies:
(a) adds success + readback verified
(b) partial failure with rollbackOnFailure=true => GISWriteError
(c) invalid geometry blocked locally (no HTTP)
(d) capability missing => GISCapabilityError
(e) token 498 then refresh success
(f) write flag OFF => 403 FEATURE_DISABLED
(g) self-approval => 403 MAKER_CHECKER_VIOLATION
(h) cross-tenant service => 403/404 CROSS_TENANT_FORBIDDEN
(i) mass-delete without IDs blocked => 422
(j) reverse geojson<->esri roundtrip and ADMS<->GISFeature transformation
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Generator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.feature_flags import is_feature_enabled
from api.gis_edits import router as gis_edits_router
from gis_integration.exceptions import (
    GISCapabilityError,
    GISDataExtractionError,
    GISWriteError,
)
from gis_integration.models import ADMSAsset, ADMSAssetType, GISFeature
from gis_integration.providers.arcgis_provider import ArcGISOnlineProvider
from gis_integration.transformer import GisToAdmsTransformer
from gis_integration.utils import esri_json_to_geojson, geojson_to_esri_json
from tests.test_arcgis_provider import MockArcGISRouter, MockRoute

UTC = timezone.utc

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SERVICE_URL = "https://services.arcgis.com/test_org/arcgis/rest/services/ElectricalGrid/FeatureServer"


# ---------------------------------------------------------------------------
# Database & FastAPI Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(gis_edits_router)
    return test_app


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_arcgis(monkeypatch):
    """Intercept httpx.Client.send with MockArcGISRouter, delegating testserver calls."""
    router = MockArcGISRouter()
    original_send = httpx.Client.send

    def _mock_send(client_self, request, **kwargs):
        url_str = str(request.url)
        if url_str.startswith(("http://testserver", "https://testserver")):
            return original_send(client_self, request, **kwargs)
        return router.handle(request)

    monkeypatch.setattr(httpx.Client, "send", _mock_send)
    return router


@pytest.fixture
def client(app: FastAPI, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-api-key")
    monkeypatch.setenv("GIS_SERVICE_ALLOWLIST", "https://services.arcgis.com/test_org/arcgis/rest/services")
    monkeypatch.setenv("GIS_MAX_FEATURES_PER_EDIT", "100")

    # Enable flags for testing
    monkeypatch.setenv("FEATURE_FLAG_GIS_WRITE", "true")
    monkeypatch.setenv("FEATURE_FLAG_ARCGIS_PROVIDER", "true")

    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-api-key")

    async def _override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db

    # Default to engineer role in tenant_alpha
    app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="user_eng_1",
        username="engineer1",
        email="eng1@grid.org",
        role="engineer",
        tenant_id="tenant_alpha",
    )

    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# (j) Unit Tests: GeoJSON <-> Esri JSON & ADMS <-> GISFeature
# ---------------------------------------------------------------------------


class TestGeometryAndTransformerRoundtrip:
    """Verify geometry conversion and deterministic transformer roundtrips."""

    def test_point_roundtrip(self):
        geojson_pt = {"type": "Point", "coordinates": [31.2357, 30.0444]}
        esri_pt = geojson_to_esri_json(geojson_pt)
        assert esri_pt == {"x": 31.2357, "y": 30.0444}
        back_to_geo = esri_json_to_geojson(esri_pt)
        assert back_to_geo == geojson_pt

    def test_multipoint_roundtrip(self):
        geojson_mp = {"type": "MultiPoint", "coordinates": [[10.0, 20.0], [30.0, 40.0]]}
        esri_mp = geojson_to_esri_json(geojson_mp)
        assert esri_mp == {"points": [[10.0, 20.0], [30.0, 40.0]]}
        back_to_geo = esri_json_to_geojson(esri_mp)
        assert back_to_geo == geojson_mp

    def test_linestring_roundtrip(self):
        geojson_line = {"type": "LineString", "coordinates": [[10.0, 20.0], [30.0, 40.0]]}
        esri_line = geojson_to_esri_json(geojson_line)
        assert esri_line == {"paths": [[[10.0, 20.0], [30.0, 40.0]]]}
        back_to_geo = esri_json_to_geojson(esri_line)
        assert back_to_geo == geojson_line

    def test_multilinestring_roundtrip(self):
        geojson_mls = {
            "type": "MultiLineString",
            "coordinates": [[[10.0, 20.0], [30.0, 40.0]], [[50.0, 60.0], [70.0, 80.0]]],
        }
        esri_mls = geojson_to_esri_json(geojson_mls)
        assert esri_mls == {"paths": [[[10.0, 20.0], [30.0, 40.0]], [[50.0, 60.0], [70.0, 80.0]]]}
        back_to_geo = esri_json_to_geojson(esri_mls)
        assert back_to_geo == geojson_mls

    def test_polygon_roundtrip(self):
        geojson_poly = {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        }
        esri_poly = geojson_to_esri_json(geojson_poly)
        assert esri_poly == {"rings": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]}
        back_to_geo = esri_json_to_geojson(esri_poly)
        assert back_to_geo == geojson_poly

    def test_multipolygon_conversion(self):
        geojson_mpoly = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                [[[2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 2.0]]],
            ],
        }
        esri_mpoly = geojson_to_esri_json(geojson_mpoly)
        assert len(esri_mpoly["rings"]) == 2

    def test_envelope_rejected(self):
        envelope_data = {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1}
        with pytest.raises(GISDataExtractionError, match="Esri JSON or Envelope"):
            geojson_to_esri_json(envelope_data)

    def test_adms_transformer_roundtrip(self):
        transformer = GisToAdmsTransformer()
        original_feature = GISFeature(
            id="sub_99",
            geometry={"type": "Point", "coordinates": [31.2, 30.0]},
            properties={"asset_role": "substation", "nominal_kv": 66.0},
            layer_name="substations",
            crs="EPSG:4326",
        )
        adms_asset = transformer.transform_feature(original_feature)
        assert adms_asset.asset_type == ADMSAssetType.SUBSTATION
        assert "sub_99" in adms_asset.asset_id

        restored_feature = transformer.transform_adms_to_feature(adms_asset)
        assert restored_feature.id == "sub_99"
        assert restored_feature.geometry == original_feature.geometry
        assert restored_feature.layer_name == "substations"
        assert restored_feature.crs == "EPSG:4326"


# ---------------------------------------------------------------------------
# (a) adds success + readback verified & (b) partial failure with rollback
# ---------------------------------------------------------------------------


class TestArcGISOnlineProviderWriteMethods:
    """Direct provider unit tests for apply_edits."""

    def test_apply_edits_success_and_requery(self, mock_arcgis):
        provider = ArcGISOnlineProvider(token="test-token")
        # 1. Mock service catalog
        mock_arcgis.get(TEST_SERVICE_URL).respond(
            json={"layers": [{"id": 0, "name": "Switches"}], "tables": []}
        )
        provider.load_project(TEST_SERVICE_URL)

        # 2. Mock layer capabilities
        mock_arcgis.get(f"{TEST_SERVICE_URL}/0").respond(
            json={"id": 0, "capabilities": "Create,Query,Update,Delete,Editing", "supportsApplyEdits": True}
        )

        # 3. Mock applyEdits POST
        mock_arcgis.post(f"{TEST_SERVICE_URL}/0/applyEdits").respond(
            json={
                "addResults": [{"objectId": 101, "success": True}],
                "updateResults": [],
                "deleteResults": [],
            }
        )

        # 4. Mock verify-by-requery GET
        mock_arcgis.get(f"{TEST_SERVICE_URL}/0/query").respond(
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": 101,
                        "properties": {"OBJECTID": 101, "name": "SW_1"},
                        "geometry": {"type": "Point", "coordinates": [31.0, 30.0]},
                    }
                ],
            }
        )

        res = provider.apply_edits(
            layer_id="0",
            adds=[{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}, "properties": {"name": "SW_1"}}],
        )
        assert res["success"] is True
        assert res["readback_verified"] is True
        assert res["addResults"][0]["objectId"] == 101

    def test_apply_edits_partial_failure_raises_write_error(self, mock_arcgis):
        provider = ArcGISOnlineProvider(token="test-token")
        mock_arcgis.get(TEST_SERVICE_URL).respond(
            json={"layers": [{"id": 0, "name": "Switches"}], "tables": []}
        )
        provider.load_project(TEST_SERVICE_URL)

        mock_arcgis.get(f"{TEST_SERVICE_URL}/0").respond(
            json={"id": 0, "capabilities": "Create,Update", "supportsApplyEdits": True}
        )

        # applyEdits reports failure on second item -> full rollback
        mock_arcgis.post(f"{TEST_SERVICE_URL}/0/applyEdits").respond(
            json={
                "addResults": [
                    {"objectId": 101, "success": True},
                    {"objectId": 102, "success": False, "error": {"description": "Field validation failed"}},
                ],
                "updateResults": [],
                "deleteResults": [],
            }
        )

        with pytest.raises(GISWriteError, match="rolled back"):
            provider.apply_edits(
                layer_id="0",
                adds=[
                    {"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}},
                    {"geometry": {"type": "Point", "coordinates": [31.1, 30.1]}},
                ],
            )

    def test_capability_missing_raises_capability_error(self, mock_arcgis):
        provider = ArcGISOnlineProvider(token="test-token")
        mock_arcgis.get(TEST_SERVICE_URL).respond(
            json={"layers": [{"id": 0, "name": "Switches"}], "tables": []}
        )
        provider.load_project(TEST_SERVICE_URL)

        # Capabilities is Query only, no Create/Update/Delete
        mock_arcgis.get(f"{TEST_SERVICE_URL}/0").respond(
            json={"id": 0, "capabilities": "Query", "supportsApplyEdits": False}
        )

        with pytest.raises(GISCapabilityError, match="lacks 'Create' capability"):
            provider.apply_edits(
                layer_id="0",
                adds=[{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            )

    def test_token_498_and_refresh_success(self, mock_arcgis, monkeypatch):
        monkeypatch.setenv("ARCGIS_USERNAME", "admin_user")
        # Generated placeholder (no static secret in repo): the refresh flow
        # only needs a non-empty password and the HTTP layer is fully mocked.
        # GitGuardian-clean by construction — nothing here can leak.
        monkeypatch.setenv("ARCGIS_PASSWORD", f"pw-{uuid.uuid4().hex[:12]}")

        provider = ArcGISOnlineProvider(portal_url="https://testportal.com", token="expired-token")

        # 1. First call to self returns 498
        route_self = mock_arcgis.get("https://testportal.com/sharing/rest/portals/self")
        route_self.mock([
            httpx.Response(498, json={"error": {"code": 498, "message": "Token Expired"}}, request=httpx.Request("GET", "https://testportal.com")),
            httpx.Response(200, json={"id": "portal_123"}, request=httpx.Request("GET", "https://testportal.com")),
        ])

        # 2. Token refresh endpoint returns valid token
        mock_arcgis.post("https://testportal.com/sharing/rest/generateToken").respond(
            json={"token": "new-fresh-token", "expires": 12345678}
        )

        healthy = provider.health_check()
        assert healthy is True
        assert provider._token == "new-fresh-token"


# ---------------------------------------------------------------------------
# API Gateway End-to-End Tests (Propose, Resolve, Status, RBAC, Dual-Control)
# ---------------------------------------------------------------------------


class TestGISEditsAPIGateway:
    """Full API router tests covering Maker-Checker, tenant isolation, and gating."""

    def test_propose_and_resolve_success_dual_control(self, client: TestClient, app: FastAPI, mock_arcgis):
        # 1. Setup mock routes
        mock_arcgis.get(TEST_SERVICE_URL).respond(
            json={"layers": [{"id": 0, "name": "Switches"}], "tables": []}
        )
        mock_arcgis.get(f"{TEST_SERVICE_URL}/0").respond(
            json={"id": 0, "capabilities": "Create,Query", "supportsApplyEdits": True}
        )
        mock_arcgis.post(f"{TEST_SERVICE_URL}/0/applyEdits").respond(
            json={"addResults": [{"objectId": 501, "success": True}], "updateResults": [], "deleteResults": []}
        )
        mock_arcgis.get(f"{TEST_SERVICE_URL}/0/query").respond(
            json={
                "type": "FeatureCollection",
                "features": [{"id": 501, "properties": {"OBJECTID": 501}, "geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            }
        )

        # Maker: Engineer proposes edit
        headers = {"x-api-key": "test-api-key"}
        propose_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}, "properties": {"name": "CB_NEW"}}],
            "reason": "Expanding Bay 4 feeder network",
        }
        res = client.post("/api/v1/gis/edits/propose", json=propose_payload, headers=headers)
        assert res.status_code == 202
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "pending_approval"
        action_id = data["action_id"]

        # List pending
        res_list = client.get("/api/v1/gis/edits/pending", headers=headers)
        assert res_list.status_code == 200
        assert any(item["action_id"] == action_id for item in res_list.json()["data"])

        # Checker: Independent Admin resolves
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="user_admin_checker",
            username="admin2",
            email="admin2@grid.org",
            role="admin",
            tenant_id="tenant_alpha",
        )

        res_resolve = client.post(
            f"/api/v1/gis/edits/{action_id}/resolve",
            json={"decision": "approve", "reason": "Verified single-line drawing"},
            headers=headers,
        )
        assert res_resolve.status_code == 200
        resolve_data = res_resolve.json()
        assert resolve_data["success"] is True
        assert resolve_data["status"] == "completed"
        assert resolve_data["result"]["readback_verified"] is True

        # Check status
        res_status = client.get(f"/api/v1/gis/edits/{action_id}/status", headers=headers)
        assert res_status.status_code == 200
        assert res_status.json()["data"]["status"] == "completed"

    def test_maker_checker_violation_self_approval_blocked(self, client: TestClient, app: FastAPI):
        headers = {"x-api-key": "test-api-key"}
        # Admin proposes
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_solo",
            username="admin_solo",
            email="solo@grid.org",
            role="admin",
            tenant_id="tenant_alpha",
        )

        propose_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            "reason": "Routine substation switch addition",
        }
        res_prop = client.post("/api/v1/gis/edits/propose", json=propose_payload, headers=headers)
        assert res_prop.status_code == 202
        action_id = res_prop.json()["action_id"]

        # Same admin attempts approval -> 403 MAKER_CHECKER_VIOLATION
        res_resolve = client.post(
            f"/api/v1/gis/edits/{action_id}/resolve",
            json={"decision": "approve", "reason": "Self-authorizing"},
            headers=headers,
        )
        assert res_resolve.status_code == 403
        err = res_resolve.json()["detail"]
        assert err["code"] == "MAKER_CHECKER_VIOLATION"

    def test_feature_flag_off_returns_403(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        headers = {"x-api-key": "test-api-key"}
        monkeypatch.setenv("FEATURE_FLAG_GIS_WRITE", "false")

        propose_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            "reason": "Test flag off",
        }
        res = client.post("/api/v1/gis/edits/propose", json=propose_payload, headers=headers)
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "FEATURE_DISABLED"

    def test_service_not_allowlisted_returns_403(self, client: TestClient):
        headers = {"x-api-key": "test-api-key"}
        unauthorized_url = "https://malicious-server.com/arcgis/rest/services/Fake"

        propose_payload = {
            "service_url": unauthorized_url,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            "reason": "Unapproved destination",
        }
        res = client.post("/api/v1/gis/edits/propose", json=propose_payload, headers=headers)
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "SERVICE_NOT_ALLOWLISTED"

    def test_invalid_geometry_blocked_locally(self, client: TestClient):
        headers = {"x-api-key": "test-api-key"}
        bad_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point"}}],  # missing coordinates
            "reason": "Invalid shape check",
        }
        res = client.post("/api/v1/gis/edits/propose", json=bad_payload, headers=headers)
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "INVALID_GEOMETRY"

    def test_mass_delete_without_ids_blocked(self, client: TestClient):
        headers = {"x-api-key": "test-api-key"}
        bad_delete_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "deletes": ["*"],  # wildcard forbidden
            "reason": "Dangerous mass wipe",
        }
        res = client.post("/api/v1/gis/edits/propose", json=bad_delete_payload, headers=headers)
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "INVALID_DELETE"

    def test_cross_tenant_access_forbidden(self, client: TestClient, app: FastAPI):
        headers = {"x-api-key": "test-api-key"}
        # Tenant A proposes
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="user_tenant_a",
            username="eng_a",
            email="eng@tenantA.com",
            role="engineer",
            tenant_id="tenant_A",
        )
        propose_payload = {
            "service_url": TEST_SERVICE_URL,
            "layer_id": "0",
            "adds": [{"geometry": {"type": "Point", "coordinates": [31.0, 30.0]}}],
            "reason": "Tenant A assets",
        }
        res_prop = client.post("/api/v1/gis/edits/propose", json=propose_payload, headers=headers)
        assert res_prop.status_code == 202
        action_id = res_prop.json()["action_id"]

        # Admin of Tenant B attempts resolve -> 403 CROSS_TENANT_FORBIDDEN
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_tenant_b",
            username="admin_b",
            email="admin@tenantB.com",
            role="admin",
            tenant_id="tenant_B",
        )
        res_res = client.post(
            f"/api/v1/gis/edits/{action_id}/resolve",
            json={"decision": "approve", "reason": "Unauthorized cross-tenant attempt"},
            headers=headers,
        )
        assert res_res.status_code == 403
        assert res_res.json()["detail"]["code"] == "CROSS_TENANT_FORBIDDEN"
