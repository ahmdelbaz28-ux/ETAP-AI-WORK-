from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import (
    GISDataExtractionError,
    GISProviderUnavailableError,
    NotImplementedFeature,
)
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict

logger = logging.getLogger(__name__)

MSG_ARCGIS_ARCHIVED = "ArcGISProvider is archived; use QGISProvider or MockGISProvider"


def _redact_secrets(text: str) -> str:
    """Redact tokens and API keys from URLs, query strings, headers, and logs."""
    if not text or not isinstance(text, str):
        return text
    # Redact token / apiKey / api_key query parameters
    text = re.sub(
        r"((?:token|apiKey|api_key|key)=)[^&\s'\"]+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    # Redact Bearer tokens in headers
    text = re.sub(
        r"(Bearer\s+)[^\s'\"]+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    return text


class ArcGISProvider:
    """
    🗃️ ARCHIVED — Not implemented; raises NotImplementedFeature.

    This provider was archived as part of WP7 GIS surgery. Use QGISProvider or
    MockGISProvider instead. The factory (gis_integration/providers/__init__.py)
    will raise NotImplementedFeature when 'arcgis' is requested.
    """

    def health_check(self) -> bool:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def load_project(self, path: str) -> None:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def list_layers(self) -> list[str]:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def extract_features(self, layer_id: str):
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def export_geojson(self, layer_id: str) -> dict:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def get_crs(self, layer_id: str | None = None):
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)


class ArcGISOnlineProvider(GISProviderInterface):
    """Safe, cloud-native REST API provider for ArcGIS Online / Enterprise Portal.

    Connects directly to ArcGIS Online or Enterprise Portal via pure HTTP REST API.
    Zero arcpy or GUI automation dependencies. Fully compliant with GISProviderInterface
    and enforces fail-closed validation on all incoming spatial geometries.
    """

    def __init__(
        self,
        portal_url: str | None = None,
        token: str | None = None,
    ) -> None:
        raw_portal = portal_url or os.getenv("ARCGIS_PORTAL_URL", "https://www.arcgis.com")
        self._portal_url = raw_portal.rstrip("/")
        self._token = token or os.getenv("ARCGIS_API_KEY") or os.getenv("ARCGIS_TOKEN")
        self._loaded: bool = False
        self._project_path: str | None = None
        self._service_url: str | None = None
        self._layers: list[str] = []
        self._layer_catalog: dict[str, str] = {}
        self._timeout: float = 30.0
        self._max_retries: int = 3
        self._crs: GeoCRSInfo = GeoCRSInfo(crs="EPSG:4326", normalized=True)

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute HTTP request with token redaction and transient retry logic."""
        merged_headers = dict(headers or {})
        if self._token:
            merged_headers.setdefault("Authorization", f"Bearer {self._token}")

        merged_params = dict(params or {})
        if self._token and "token" not in merged_params:
            merged_params["token"] = self._token

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                safe_url = _redact_secrets(url)
                logger.debug(
                    "ArcGIS REST %s %s (attempt %d/%d)",
                    method,
                    safe_url,
                    attempt,
                    self._max_retries,
                )
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.request(
                        method=method,
                        url=url,
                        params=merged_params,
                        headers=merged_headers,
                    )
                    # Retry on 5xx transient errors
                    if resp.status_code in (500, 502, 503, 504):
                        if attempt < self._max_retries:
                            time.sleep(0.05 * (2 ** (attempt - 1)))
                            continue
                        safe_url = _redact_secrets(url)
                        raise GISProviderUnavailableError(
                            f"ArcGIS service request failed after {self._max_retries} attempts: HTTP {resp.status_code} at {safe_url}"
                        )
                    return resp
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    time.sleep(0.05 * (2 ** (attempt - 1)))
                    continue
                clean_err = _redact_secrets(str(exc))
                logger.error(
                    "ArcGIS REST request failed after %d retries: %s",
                    self._max_retries,
                    clean_err,
                )
                raise GISProviderUnavailableError(
                    f"ArcGIS service request failed after {self._max_retries} attempts: {clean_err}"
                ) from exc

        if last_exc:
            clean_err = _redact_secrets(str(last_exc))
            raise GISProviderUnavailableError(
                f"ArcGIS service request failed after {self._max_retries} attempts: {clean_err}"
            )
        raise GISProviderUnavailableError("ArcGIS service request failed")

    def health_check(self) -> bool:
        """Return True if the ArcGIS portal is reachable and responsive."""
        try:
            url = f"{self._portal_url}/sharing/rest/portals/self"
            resp = self._request("GET", url, params={"f": "json"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "error" not in data:
                    return True
            return False
        except Exception as exc:
            logger.debug("ArcGIS health check probe failed: %s", _redact_secrets(str(exc)))
            return False

    def load_project(self, item_id_or_service_url: str) -> None:
        """Load an ArcGIS FeatureService or Portal Item.

        Args:
            item_id_or_service_url: FeatureServer URL or 32-character Portal Item ID.

        Raises:
            ValueError: If project identifier is empty or not a string.
            GISDataExtractionError: If metadata extraction or layer catalog fails.
            GISProviderUnavailableError: If network connection to ArcGIS fails.
        """
        if not item_id_or_service_url or not isinstance(item_id_or_service_url, str):
            raise ValueError("Project identifier must be a non-empty string")

        self._project_path = item_id_or_service_url

        if item_id_or_service_url.startswith(("http://", "https://")):
            service_url = item_id_or_service_url.rstrip("/")
        else:
            # Portal Item ID: fetch item details to discover feature service URL
            item_url = f"{self._portal_url}/sharing/rest/content/items/{item_id_or_service_url}"
            resp = self._request("GET", item_url, params={"f": "json"})
            if resp.status_code != 200:
                raise GISDataExtractionError(
                    f"Failed to fetch ArcGIS item {item_id_or_service_url}: HTTP {resp.status_code}"
                )
            try:
                item_data = resp.json()
            except Exception as exc:
                raise GISDataExtractionError(
                    f"Invalid JSON from ArcGIS item {item_id_or_service_url}: {exc}"
                ) from exc

            if isinstance(item_data, dict) and "error" in item_data:
                err_msg = item_data["error"].get("message", str(item_data["error"]))
                raise GISDataExtractionError(f"ArcGIS item error: {err_msg}")

            service_url = item_data.get("url")
            if not service_url or not isinstance(service_url, str):
                raise GISDataExtractionError(
                    f"ArcGIS item {item_id_or_service_url} does not contain a feature service URL"
                )
            service_url = service_url.rstrip("/")

        self._service_url = service_url

        # Query layer catalog
        resp = self._request("GET", service_url, params={"f": "json"})
        if resp.status_code != 200:
            raise GISDataExtractionError(
                f"Failed to load layer catalog from {service_url}: HTTP {resp.status_code}"
            )
        try:
            catalog = resp.json()
        except Exception as exc:
            raise GISDataExtractionError(
                f"Invalid JSON in layer catalog from {service_url}: {exc}"
            ) from exc

        if isinstance(catalog, dict) and "error" in catalog:
            err_msg = catalog["error"].get("message", str(catalog["error"]))
            raise GISDataExtractionError(f"ArcGIS catalog error: {err_msg}")

        layers = catalog.get("layers", [])
        tables = catalog.get("tables", [])
        self._layers = []
        self._layer_catalog = {}

        for lyr in list(layers) + list(tables):
            if isinstance(lyr, dict):
                lid = str(lyr.get("id", ""))
                lname = str(lyr.get("name", lid))
                if lid:
                    self._layer_catalog[lid] = lid
                    self._layer_catalog[lid.lower()] = lid
                if lname:
                    self._layer_catalog[lname] = lid
                    self._layer_catalog[lname.lower()] = lid
                self._layers.append(lname if lname else lid)
            elif isinstance(lyr, (str, int)):
                lid = str(lyr)
                self._layer_catalog[lid] = lid
                self._layers.append(lid)

        self._loaded = True
        logger.info("Loaded ArcGIS project with %d layers", len(self._layers))

    def list_layers(self) -> list[str]:
        """Return the list of layer names or layer IDs."""
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")
        return list(self._layers)

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        """Extract normalized GIS features from a layer.

        Args:
            layer_id: Layer name or numeric layer ID.

        Yields:
            GISFeature instances with normalized EPSG:4326 GeoJSON geometries.

        Raises:
            RuntimeError: If load_project() was not called first.
            ValueError: If layer_id is empty or not a string.
            GISDataExtractionError: If feature extraction fails or invalid geometries are received.
            GISProviderUnavailableError: If network connection fails.
        """
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")
        if not layer_id or not isinstance(layer_id, str):
            raise ValueError("layer_id must be a non-empty string")

        resolved_id = (
            self._layer_catalog.get(layer_id)
            or self._layer_catalog.get(layer_id.lower())
            or layer_id
        )
        query_url = f"{self._service_url}/{resolved_id}/query"

        # 1. Primary attempt: f=geojson
        geojson_params = {"where": "1=1", "outFields": "*", "f": "geojson", "outSR": "4326"}
        features: list[dict[str, Any]] = []
        is_geojson_format = False

        try:
            resp = self._request("GET", query_url, params=geojson_params)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and "error" not in data and "features" in data:
                        features = data.get("features", [])
                        is_geojson_format = True
                except Exception:
                    features = []
        except GISProviderUnavailableError:
            raise
        except Exception as exc:
            logger.debug("GeoJSON query attempt failed, falling back to Esri JSON: %s", exc)

        # 2. Fallback attempt: f=json (Esri JSON)
        if not is_geojson_format:
            esri_params = {"where": "1=1", "outFields": "*", "f": "json", "outSR": "4326"}
            resp = self._request("GET", query_url, params=esri_params)
            if resp.status_code != 200:
                raise GISDataExtractionError(
                    f"Feature query failed for layer {layer_id} ({resolved_id}): HTTP {resp.status_code}"
                )
            try:
                data = resp.json()
            except Exception as exc:
                raise GISDataExtractionError(
                    f"Invalid JSON from query for layer {layer_id}: {exc}"
                ) from exc

            if isinstance(data, dict) and "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))
                raise GISDataExtractionError(f"ArcGIS query error for layer {layer_id}: {err_msg}")

            features = data.get("features", [])

        # Process and yield normalized GISFeature items
        for idx, feat in enumerate(features):
            if not isinstance(feat, dict):
                continue

            if is_geojson_format:
                props = feat.get("properties") or {}
                fid = str(
                    feat.get("id")
                    or props.get("OBJECTID")
                    or props.get("GlobalID")
                    or f"{resolved_id}_{idx}"
                )
                raw_geom = feat.get("geometry")
            else:
                attrs = feat.get("attributes") or {}
                fid = str(
                    attrs.get("OBJECTID")
                    or attrs.get("GlobalID")
                    or feat.get("id")
                    or f"{resolved_id}_{idx}"
                )
                props = attrs
                raw_geom = feat.get("geometry")

            if raw_geom is None:
                raise GISDataExtractionError(f"Feature {fid} has null geometry")

            try:
                parsed_geom = safe_parse_geojson(raw_geom)
            except Exception as exc:
                raise GISDataExtractionError(
                    f"Failed to parse geometry for feature {fid}: {exc}"
                ) from exc

            is_valid, reason = validate_geometry_dict(parsed_geom)
            if not is_valid:
                raise GISDataExtractionError(f"Feature {fid} has invalid geometry: {reason}")

            yield GISFeature(
                id=fid,
                geometry=parsed_geom,
                properties=dict(props),
                layer_name=layer_id,
                crs="EPSG:4326",
            )

    def export_geojson(self, layer_id: str) -> dict[str, Any]:
        """Export the specified layer as a GeoJSON FeatureCollection."""
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")

        features = list(self.extract_features(layer_id))
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f.id,
                    "geometry": f.geometry,
                    "properties": {**f.properties, "id": f.id, "layer": f.layer_name},
                }
                for f in features
            ],
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:4326"},
            },
        }

    def get_crs(self, layer_id: str | None = None) -> GeoCRSInfo:
        """Return CRS information for the given layer (normalized to EPSG:4326)."""
        return self._crs

