from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from gis_integration.exceptions import (
    GISDataExtractionError,
    GISProviderUnavailableError,
    NotImplementedFeature,
)
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.providers import (
    ArcGISOnlineProvider,
    ArcGISProvider,
    get_gis_provider,
)
from gis_integration.providers.arcgis_provider import _redact_secrets

# =============================================================================
# Mock Router for ArcGIS Online HTTP tests (zero 3rd-party dependencies)
# =============================================================================


class MockRoute:
    """Mock route for intercepting httpx.Client requests without external dependencies."""

    def __init__(self, url_prefix: str, method: str = "GET") -> None:
        self.url_prefix = url_prefix
        self.method = method.upper()
        self.call_count: int = 0
        self.calls: list[httpx.Request] = []
        self._response_fn: Callable[[httpx.Request], httpx.Response] | None = None
        self.side_effect: Any = None

    def respond(
        self,
        status_code: int = 200,
        json: Any = None,
        text: str = "",
    ) -> MockRoute:
        def _fn(request: httpx.Request) -> httpx.Response:
            if json is not None:
                return httpx.Response(status_code, json=json, request=request)
            return httpx.Response(status_code, text=text, request=request)

        self._response_fn = _fn
        return self

    def mock(self, side_effect: Any) -> MockRoute:
        self.side_effect = side_effect
        return self

    def matches(self, request: httpx.Request) -> bool:
        if self.method and request.method.upper() != self.method:
            return False
        req_str = str(request.url)
        if "?" not in self.url_prefix:
            req_base = req_str.split("?")[0].rstrip("/")
            target_base = self.url_prefix.rstrip("/")
            return req_base == target_base or req_str.startswith(self.url_prefix)
        return self.url_prefix in req_str

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        self.calls.append(request)
        if self.side_effect is not None:
            if isinstance(self.side_effect, list):
                item = self.side_effect.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item
            elif callable(self.side_effect):
                return self.side_effect(request)
            elif isinstance(self.side_effect, Exception):
                raise self.side_effect
        if self._response_fn:
            return self._response_fn(request)
        return httpx.Response(200, json={}, request=request)


class MockArcGISRouter:
    """Router matching registered MockRoutes against outgoing httpx.Client calls."""

    def __init__(self) -> None:
        self.routes: list[MockRoute] = []

    def get(self, url: str) -> MockRoute:
        route = MockRoute(url, "GET")
        self.routes.append(route)
        return route

    def post(self, url: str) -> MockRoute:
        route = MockRoute(url, "POST")
        self.routes.append(route)
        return route

    def handle(self, request: httpx.Request) -> httpx.Response:
        for route in reversed(self.routes):
            if route.matches(request):
                return route.handle(request)
        return httpx.Response(
            404,
            text=f"Mock route not found for {request.method} {request.url}",
            request=request,
        )


@pytest.fixture
def mock_arcgis(monkeypatch):
    """Fixture providing a clean MockArcGISRouter that intercepts httpx.Client.send."""
    router = MockArcGISRouter()

    def _mock_send(client_self, request, **kwargs):
        return router.handle(request)

    monkeypatch.setattr(httpx.Client, "send", _mock_send)
    return router


# =============================================================================
# 1. Legacy ArcGISProvider Backward Compatibility Tests
# =============================================================================


class TestLegacyArcGISProviderArchived:
    """Verify legacy ArcGISProvider continues to raise NotImplementedFeature."""

    def test_legacy_health_check(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            provider.health_check()

    def test_legacy_load_project(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            provider.load_project("https://example.com/arcgis")

    def test_legacy_list_layers(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            provider.list_layers()

    def test_legacy_extract_features(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            list(provider.extract_features("0"))

    def test_legacy_export_geojson(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            provider.export_geojson("0")

    def test_legacy_get_crs(self):
        provider = ArcGISProvider()
        with pytest.raises(NotImplementedFeature, match="archived"):
            provider.get_crs()


# =============================================================================
# 2. ArcGISOnlineProvider Initialization & Defaults
# =============================================================================


class TestArcGISOnlineProviderInit:
    def test_default_portal_url(self, monkeypatch):
        monkeypatch.delenv("ARCGIS_PORTAL_URL", raising=False)
        monkeypatch.delenv("ARCGIS_API_KEY", raising=False)
        monkeypatch.delenv("ARCGIS_TOKEN", raising=False)
        provider = ArcGISOnlineProvider()
        assert provider._portal_url == "https://www.arcgis.com"
        assert provider._token is None
        assert provider._loaded is False

    def test_custom_portal_url_and_token(self):
        provider = ArcGISOnlineProvider(
            portal_url="https://gis.enterprise.example.com/portal/",
            token="custom-token-xyz",
        )
        assert provider._portal_url == "https://gis.enterprise.example.com/portal"
        assert provider._token == "custom-token-xyz"

    def test_env_credentials(self, monkeypatch):
        monkeypatch.setenv("ARCGIS_PORTAL_URL", "https://portal.local/arcgis/")
        monkeypatch.setenv("ARCGIS_API_KEY", "env-api-key-123")
        provider = ArcGISOnlineProvider()
        assert provider._portal_url == "https://portal.local/arcgis"
        assert provider._token == "env-api-key-123"

    def test_token_from_arcgis_token_env(self, monkeypatch):
        monkeypatch.delenv("ARCGIS_API_KEY", raising=False)
        monkeypatch.setenv("ARCGIS_TOKEN", "token-from-arcgis-token-env")
        provider = ArcGISOnlineProvider()
        assert provider._token == "token-from-arcgis-token-env"


# =============================================================================
# 3. Health Check Probe Tests
# =============================================================================


class TestArcGISOnlineProviderHealthCheck:
    def test_health_check_success(self, mock_arcgis):
        mock_arcgis.get("https://www.arcgis.com/sharing/rest/portals/self").respond(
            status_code=200,
            json={"id": "0123456789ABCDEF", "isPortal": True, "name": "ArcGIS Online"},
        )
        provider = ArcGISOnlineProvider()
        assert provider.health_check() is True

    def test_health_check_failure_http_500(self, mock_arcgis):
        mock_arcgis.get("https://www.arcgis.com/sharing/rest/portals/self").respond(
            status_code=500,
            text="Internal Server Error",
        )
        provider = ArcGISOnlineProvider()
        assert provider.health_check() is False

    def test_health_check_portal_error_response(self, mock_arcgis):
        mock_arcgis.get("https://www.arcgis.com/sharing/rest/portals/self").respond(
            status_code=200,
            json={"error": {"code": 498, "message": "Invalid token"}},
        )
        provider = ArcGISOnlineProvider()
        assert provider.health_check() is False

    def test_health_check_network_timeout(self, mock_arcgis):
        mock_arcgis.get("https://www.arcgis.com/sharing/rest/portals/self").mock(
            side_effect=httpx.TimeoutException("Read timed out")
        )
        provider = ArcGISOnlineProvider()
        assert provider.health_check() is False


# =============================================================================
# 4. Project Loading Tests (Service URL & Item ID)
# =============================================================================


class TestArcGISOnlineProviderLoadProject:
    def test_load_project_empty_raises(self):
        provider = ArcGISOnlineProvider()
        with pytest.raises(ValueError, match="non-empty string"):
            provider.load_project("")
        with pytest.raises(ValueError, match="non-empty string"):
            provider.load_project(None)  # type: ignore

    def test_load_project_direct_feature_service_url(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/arcgis/rest/services/Grid/FeatureServer"
        catalog_payload = {
            "currentVersion": 11.1,
            "layers": [
                {"id": 0, "name": "Substations"},
                {"id": 1, "name": "Lines"},
            ],
            "tables": [{"id": 2, "name": "InspectionLogs"}],
        }
        mock_arcgis.get(service_url).respond(status_code=200, json=catalog_payload)

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        assert provider._loaded is True
        assert provider._service_url == service_url
        layers = provider.list_layers()
        assert "Substations" in layers
        assert "Lines" in layers
        assert "InspectionLogs" in layers
        assert len(layers) == 3

    def test_load_project_from_item_id(self, mock_arcgis):
        item_id = "e9123456789abcdef0123456789abcde"
        portal_url = "https://www.arcgis.com"
        service_url = (
            "https://services.arcgis.com/org/arcgis/rest/services/Electrical/FeatureServer"
        )

        # Item info endpoint
        mock_arcgis.get(f"{portal_url}/sharing/rest/content/items/{item_id}").respond(
            status_code=200,
            json={
                "id": item_id,
                "title": "Cairo Electrical Grid",
                "type": "Feature Service",
                "url": service_url,
            },
        )
        # Service catalog endpoint
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={
                "layers": [{"id": 0, "name": "Buses"}],
                "tables": [],
            },
        )

        provider = ArcGISOnlineProvider(portal_url=portal_url)
        provider.load_project(item_id)

        assert provider._loaded is True
        assert provider._service_url == service_url
        assert provider.list_layers() == ["Buses"]

    def test_load_project_item_id_without_service_url_raises(self, mock_arcgis):
        item_id = "item-without-url"
        mock_arcgis.get(f"https://www.arcgis.com/sharing/rest/content/items/{item_id}").respond(
            status_code=200,
            json={"id": item_id, "title": "Static Web Map", "type": "Web Map"},
        )
        provider = ArcGISOnlineProvider()
        with pytest.raises(GISDataExtractionError, match="does not contain a feature service URL"):
            provider.load_project(item_id)

    def test_load_project_catalog_error_raises(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"error": {"code": 403, "message": "Service requires subscription"}},
        )
        provider = ArcGISOnlineProvider()
        with pytest.raises(GISDataExtractionError, match="requires subscription"):
            provider.load_project(service_url)

    def test_list_layers_before_load_raises(self):
        provider = ArcGISOnlineProvider()
        with pytest.raises(RuntimeError, match="No GIS project loaded"):
            provider.list_layers()


# =============================================================================
# 5. Extract Features Tests (GeoJSON, Esri JSON, Validation)
# =============================================================================


class TestArcGISOnlineProviderExtractFeatures:
    def test_extract_features_before_load_raises(self):
        provider = ArcGISOnlineProvider()
        with pytest.raises(RuntimeError, match="No GIS project loaded"):
            list(provider.extract_features("0"))

    def test_extract_features_invalid_layer_id_raises(self):
        provider = ArcGISOnlineProvider()
        provider._loaded = True
        with pytest.raises(ValueError, match="non-empty string"):
            list(provider.extract_features(""))

    def test_extract_features_geojson_format(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"layers": [{"id": 0, "name": "Buses"}]},
        )
        geojson_resp = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "bus_101",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [31.2357, 30.0444],
                    },
                    "properties": {
                        "OBJECTID": 101,
                        "name": "Cairo East Bus",
                        "voltage_kv": 220.0,
                    },
                }
            ],
        }
        mock_arcgis.get(f"{service_url}/0/query").respond(
            status_code=200,
            json=geojson_resp,
        )

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        features = list(provider.extract_features("Buses"))
        assert len(features) == 1
        f = features[0]
        assert isinstance(f, GISFeature)
        assert f.id == "bus_101"
        assert f.geometry == {"type": "Point", "coordinates": [31.2357, 30.0444]}
        assert f.properties["name"] == "Cairo East Bus"
        assert f.properties["voltage_kv"] == 220.0
        assert f.crs == "EPSG:4326"

    def test_extract_features_esri_json_fallback(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"layers": [{"id": 1, "name": "Lines"}]},
        )

        def query_matcher(request: httpx.Request) -> httpx.Response:
            if "f=geojson" in str(request.url):
                return httpx.Response(
                    400,
                    json={"error": {"code": 400, "message": "Format geojson unsupported"}},
                    request=request,
                )
            # Esri JSON query
            return httpx.Response(
                200,
                json={
                    "features": [
                        {
                            "attributes": {
                                "OBJECTID": 202,
                                "name": "East-Helwan Feeder",
                                "rated_amps": 1200,
                            },
                            "geometry": {
                                "paths": [[[31.2357, 30.0444], [31.3357, 29.8444]]],
                            },
                        }
                    ]
                },
                request=request,
            )

        mock_arcgis.get(f"{service_url}/1/query").mock(side_effect=query_matcher)

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        features = list(provider.extract_features("1"))
        assert len(features) == 1
        f = features[0]
        assert isinstance(f, GISFeature)
        assert f.id == "202"
        assert f.geometry == {
            "type": "LineString",
            "coordinates": [[31.2357, 30.0444], [31.3357, 29.8444]],
        }
        assert f.properties["name"] == "East-Helwan Feeder"
        assert f.crs == "EPSG:4326"

    def test_extract_features_invalid_geometry_fails_closed(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"layers": [{"id": 0, "name": "FaultyLayer"}]},
        )
        mock_arcgis.get(f"{service_url}/0/query").respond(
            status_code=200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "bad_1",
                        "geometry": {"type": "Point"},  # missing coordinates!
                        "properties": {},
                    }
                ],
            },
        )

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        with pytest.raises(GISDataExtractionError, match="invalid geometry"):
            list(provider.extract_features("0"))

    def test_extract_features_null_geometry_raises(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"layers": [{"id": 0, "name": "NullGeomLayer"}]},
        )
        mock_arcgis.get(f"{service_url}/0/query").respond(
            status_code=200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "null_1",
                        "geometry": None,
                        "properties": {},
                    }
                ],
            },
        )

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        with pytest.raises(GISDataExtractionError, match="null geometry"):
            list(provider.extract_features("0"))


# =============================================================================
# 6. Export GeoJSON and Get CRS Tests
# =============================================================================


class TestArcGISOnlineProviderExportAndCRS:
    def test_export_geojson_success(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=200,
            json={"layers": [{"id": 0, "name": "Transformers"}]},
        )
        mock_arcgis.get(f"{service_url}/0/query").respond(
            status_code=200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "tx_1",
                        "geometry": {"type": "Point", "coordinates": [31.2, 30.0]},
                        "properties": {"rating_mva": 50},
                    }
                ],
            },
        )

        provider = ArcGISOnlineProvider()
        provider.load_project(service_url)

        fc = provider.export_geojson("0")
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1
        assert fc["features"][0]["geometry"] == {"type": "Point", "coordinates": [31.2, 30.0]}
        assert fc["features"][0]["properties"]["rating_mva"] == 50

    def test_export_geojson_before_load_raises(self):
        provider = ArcGISOnlineProvider()
        with pytest.raises(RuntimeError, match="No GIS project loaded"):
            provider.export_geojson("0")

    def test_get_crs(self):
        provider = ArcGISOnlineProvider()
        crs_info = provider.get_crs()
        assert isinstance(crs_info, GeoCRSInfo)
        assert crs_info.crs == "EPSG:4326"
        assert crs_info.normalized is True


# =============================================================================
# 7. Security & Secret Redaction Tests
# =============================================================================


class TestArcGISOnlineProviderSecurity:
    def test_redact_secrets_url_query_param(self):
        raw = "https://arcgis.com/query?where=1=1&token=SUPER_SECRET_TOKEN_XYZ&f=json"
        redacted = _redact_secrets(raw)
        assert "SUPER_SECRET_TOKEN_XYZ" not in redacted
        assert "token=***" in redacted

    def test_redact_secrets_bearer_header(self):
        raw = "Headers: Authorization: Bearer SECRET_BEARER_KEY_123 in request"
        redacted = _redact_secrets(raw)
        assert "SECRET_BEARER_KEY_123" not in redacted
        assert "Bearer ***" in redacted

    def test_token_redacted_in_exception_on_network_failure(self, mock_arcgis, caplog):
        secret_token = "TOP_SECRET_AUTH_TOKEN_9999"
        mock_arcgis.get("https://www.arcgis.com/sharing/rest/portals/self").mock(
            side_effect=httpx.ConnectError(
                "Connection failed to https://www.arcgis.com?token=TOP_SECRET_AUTH_TOKEN_9999"
            )
        )

        provider = ArcGISOnlineProvider(token=secret_token)
        with caplog.at_level(logging.DEBUG):
            provider.health_check()

        # Verify raw secret was never logged
        for record in caplog.records:
            assert secret_token not in record.message
            assert secret_token not in str(record.exc_info or "")


# =============================================================================
# 8. Retries & Resilience Tests
# =============================================================================


class TestArcGISOnlineProviderRetries:
    def test_retry_on_transient_503_success(self, mock_arcgis):
        url = "https://www.arcgis.com/sharing/rest/portals/self"
        route = mock_arcgis.get(url)
        # First 2 attempts return 503, 3rd returns 200
        route.side_effect = [
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(200, json={"id": "portal_ok"}),
        ]

        provider = ArcGISOnlineProvider()
        assert provider.health_check() is True
        assert route.call_count == 3

    def test_retry_exhausted_raises_provider_unavailable(self, mock_arcgis):
        service_url = "https://services.arcgis.com/org/FeatureServer"
        mock_arcgis.get(service_url).respond(
            status_code=503,
            text="Service Unavailable",
        )

        provider = ArcGISOnlineProvider()
        with pytest.raises(GISProviderUnavailableError, match="failed after 3 attempts"):
            provider.load_project(service_url)


# =============================================================================
# 9. Factory & Feature Flag Gating Tests
# =============================================================================


class TestArcGISProviderFactoryGating:
    def test_factory_legacy_arcgis_raises_not_implemented(self):
        with pytest.raises(NotImplementedFeature, match="archived"):
            get_gis_provider("arcgis")

    def test_factory_arcgis_online_dev_environment(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("FEATURE_FLAG_ARCGIS_PROVIDER", raising=False)
        provider = get_gis_provider("arcgis_online")
        assert isinstance(provider, ArcGISOnlineProvider)

    def test_factory_arcgis_online_production_disabled_raises(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("FEATURE_FLAG_ARCGIS_PROVIDER", raising=False)
        with pytest.raises(
            RuntimeError, match="disabled in production by feature flag 'arcgis_provider'"
        ):
            get_gis_provider("arcgis_online")

    def test_factory_arcgis_online_production_enabled(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("FEATURE_FLAG_ARCGIS_PROVIDER", "true")
        provider = get_gis_provider("arcgis_online")
        assert isinstance(provider, ArcGISOnlineProvider)
