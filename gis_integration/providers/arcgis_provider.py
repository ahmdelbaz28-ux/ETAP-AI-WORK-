from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import (
    GISCapabilityError,
    GISDataExtractionError,
    GISProviderUnavailableError,
    GISWriteError,
    NotImplementedFeature,
)
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import (
    geojson_to_esri_json,
    safe_parse_geojson,
    validate_geometry_dict,
)

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
        self._token_refreshed: bool = False

    def _refresh_token_if_possible(self) -> bool:
        """Attempt to refresh authentication token using credentials once."""
        username = os.getenv("ARCGIS_USERNAME")
        password = os.getenv("ARCGIS_PASSWORD")
        if not username or not password:
            return False

        token_url = f"{self._portal_url}/sharing/rest/generateToken"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    token_url,
                    data={
                        "username": username,
                        "password": password,
                        "client": "referer",
                        "referer": "urn:esri:GEO",
                        "expiration": "60",
                        "f": "json",
                    },
                )
                if resp.status_code == 200:
                    token_data = resp.json()
                    new_token = token_data.get("token")
                    if new_token:
                        self._token = new_token
                        logger.info("Successfully refreshed ArcGIS token")
                        return True
        except Exception as exc:
            logger.warning("ArcGIS token refresh failed: %s", _redact_secrets(str(exc)))
        return False

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute HTTP request with token redaction, token-refresh, and transient retry logic."""
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
                        data=data,
                    )
                    # Check for token expiration / invalid token (498, 499)
                    is_token_error = resp.status_code in (498, 499)
                    if not is_token_error and resp.status_code == 200:
                        try:
                            peek = resp.json()
                            if isinstance(peek, dict) and peek.get("error", {}).get("code") in (498, 499):
                                is_token_error = True
                        except Exception:
                            pass

                    if is_token_error:
                        if not self._token_refreshed and self._refresh_token_if_possible():
                            self._token_refreshed = True
                            if self._token:
                                merged_headers["Authorization"] = f"Bearer {self._token}"
                                merged_params["token"] = self._token
                            continue
                        raise GISProviderUnavailableError(
                            f"ArcGIS service authentication failed: token expired or invalid (HTTP {resp.status_code})"
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

    def apply_edits(
        self,
        layer_id: str,
        adds: list[dict[str, Any]] | None = None,
        updates: list[dict[str, Any]] | None = None,
        deletes: list[str | int] | None = None,
    ) -> dict[str, Any]:
        """Apply transactional feature edits (add, update, delete) to a layer via Esri REST applyEdits.

        Enforces:
        - Layer capabilities validation (Create/Update/Delete or supportsApplyEdits)
        - Local geometry validation & GeoJSON->Esri JSON conversion
        - Transactional rollback on failure (rollbackOnFailure=true)
        - Max edit limit guard (GIS_MAX_FEATURES_PER_EDIT, default 100)
        - Verify-by-requery of affected OBJECTIDs
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

        max_features = int(os.getenv("GIS_MAX_FEATURES_PER_EDIT", "100"))
        adds_list = list(adds or [])
        updates_list = list(updates or [])
        deletes_list = list(deletes or [])
        total_features = len(adds_list) + len(updates_list) + len(deletes_list)

        if total_features == 0:
            return {
                "success": True,
                "addResults": [],
                "updateResults": [],
                "deleteResults": [],
                "readback_verified": True,
            }

        if total_features > max_features:
            raise GISWriteError(
                f"Edit batch of {total_features} features exceeds maximum allowed limit of {max_features}"
            )

        # 1. Capability check
        layer_meta_url = f"{self._service_url}/{resolved_id}"
        resp = self._request("GET", layer_meta_url, params={"f": "json"})
        if resp.status_code != 200:
            raise GISCapabilityError(
                f"Failed to fetch layer metadata for {layer_id}: HTTP {resp.status_code}"
            )
        layer_meta = resp.json()
        if isinstance(layer_meta, dict) and "error" in layer_meta:
            err_msg = layer_meta["error"].get("message", str(layer_meta["error"]))
            raise GISCapabilityError(f"Layer metadata error for {layer_id}: {err_msg}")

        caps_raw = str(layer_meta.get("capabilities", "")).lower()
        caps = {c.strip() for c in caps_raw.split(",") if c.strip()}
        supports_apply = bool(layer_meta.get("supportsApplyEdits", False))

        if adds_list and not (supports_apply or {"create", "creates", "editing"} & caps):
            raise GISCapabilityError(f"Layer {layer_id} lacks 'Create' capability")
        if updates_list and not (supports_apply or {"update", "updates", "editing"} & caps):
            raise GISCapabilityError(f"Layer {layer_id} lacks 'Update' capability")
        if deletes_list and not (supports_apply or {"delete", "deletes", "editing"} & caps):
            raise GISCapabilityError(f"Layer {layer_id} lacks 'Delete' capability")

        # 2. Local geometry validation and GeoJSON -> Esri conversion
        esri_adds: list[dict[str, Any]] = []
        for idx, feat in enumerate(adds_list):
            if not isinstance(feat, dict):
                raise GISWriteError(f"Add feature at index {idx} must be a dict")
            raw_geom = feat.get("geometry")
            if raw_geom is None:
                raise GISWriteError(f"Add feature at index {idx} missing geometry")
            parsed_geom = safe_parse_geojson(raw_geom)
            is_valid, reason = validate_geometry_dict(parsed_geom)
            if not is_valid:
                raise GISWriteError(f"Invalid geometry in add feature {idx}: {reason}")
            esri_geom = geojson_to_esri_json(parsed_geom)
            props = dict(feat.get("attributes") or feat.get("properties") or {})
            esri_adds.append({"attributes": props, "geometry": esri_geom})

        esri_updates: list[dict[str, Any]] = []
        for idx, feat in enumerate(updates_list):
            if not isinstance(feat, dict):
                raise GISWriteError(f"Update feature at index {idx} must be a dict")
            attrs = dict(feat.get("attributes") or feat.get("properties") or {})
            oid = attrs.get("OBJECTID") or attrs.get("ObjectId") or attrs.get("objectId") or feat.get("id")
            if oid is None:
                raise GISWriteError(f"Update feature at index {idx} missing required OBJECTID")
            attrs["OBJECTID"] = int(oid) if str(oid).isdigit() else oid

            up_item: dict[str, Any] = {"attributes": attrs}
            raw_geom = feat.get("geometry")
            if raw_geom is not None:
                parsed_geom = safe_parse_geojson(raw_geom)
                is_valid, reason = validate_geometry_dict(parsed_geom)
                if not is_valid:
                    raise GISWriteError(f"Invalid geometry in update feature {idx}: {reason}")
                up_item["geometry"] = geojson_to_esri_json(parsed_geom)
            esri_updates.append(up_item)

        clean_deletes: list[str] = []
        for idx, d in enumerate(deletes_list):
            s = str(d).strip()
            if not s or s in ("*", "1=1") or "where" in s.lower():
                raise GISWriteError("Mass delete is forbidden; explicit OBJECTIDs are required")
            clean_deletes.append(s)

        # 3. POST applyEdits
        apply_edits_url = f"{self._service_url}/{resolved_id}/applyEdits"
        post_data: dict[str, Any] = {
            "f": "json",
            "rollbackOnFailure": "true",
            "useGlobalIds": "false",
            "returnEditMoment": "true",
        }
        if esri_adds:
            post_data["adds"] = json.dumps(esri_adds)
        if esri_updates:
            post_data["updates"] = json.dumps(esri_updates)
        if clean_deletes:
            post_data["deletes"] = ",".join(clean_deletes)

        resp = self._request("POST", apply_edits_url, data=post_data)
        if resp.status_code != 200:
            raise GISWriteError(f"applyEdits HTTP request failed: HTTP {resp.status_code}")

        res_json = resp.json()
        if isinstance(res_json, list) and len(res_json) > 0:
            res_json = res_json[0]

        if isinstance(res_json, dict) and "error" in res_json:
            err_msg = res_json["error"].get("message", str(res_json["error"]))
            raise GISWriteError(f"ArcGIS applyEdits error: {err_msg}")

        add_results = res_json.get("addResults", [])
        update_results = res_json.get("updateResults", [])
        delete_results = res_json.get("deleteResults", [])

        # Check for individual item failure (fail-closed)
        all_results = list(add_results) + list(update_results) + list(delete_results)
        for r in all_results:
            if isinstance(r, dict) and (not r.get("success", False) or "error" in r):
                err = r.get("error", {})
                msg = err.get("description") or err.get("message") or f"Operation failed on item {r.get('objectId')}"
                raise GISWriteError(f"applyEdits operation failed (rolled back): {msg}")

        # 4. Verify-by-requery
        query_url = f"{self._service_url}/{resolved_id}/query"
        active_oids = [
            str(r.get("objectId")) for r in list(add_results) + list(update_results)
            if r.get("objectId") is not None
        ]
        if active_oids:
            q_resp = self._request(
                "GET",
                query_url,
                params={
                    "objectIds": ",".join(active_oids),
                    "outFields": "*",
                    "f": "geojson",
                    "outSR": "4326",
                },
            )
            if q_resp.status_code != 200:
                raise GISWriteError(f"Verify-by-requery failed: HTTP {q_resp.status_code}")
            q_data = q_resp.json()
            features_found = q_data.get("features", []) if isinstance(q_data, dict) else []
            if len(features_found) < len(active_oids):
                raise GISWriteError(
                    f"Verify-by-requery mismatch: expected {len(active_oids)} features, found {len(features_found)}"
                )

        del_oids = [
            str(r.get("objectId")) for r in delete_results
            if r.get("objectId") is not None
        ]
        if del_oids:
            d_resp = self._request(
                "GET",
                query_url,
                params={
                    "objectIds": ",".join(del_oids),
                    "outFields": "OBJECTID",
                    "f": "json",
                },
            )
            if d_resp.status_code == 200:
                d_data = d_resp.json()
                still_present = d_data.get("features", []) if isinstance(d_data, dict) else []
                if len(still_present) > 0:
                    raise GISWriteError(
                        f"Verify-by-requery mismatch: {len(still_present)} deleted features still found"
                    )

        return {
            "success": True,
            "addResults": add_results,
            "updateResults": update_results,
            "deleteResults": delete_results,
            "readback_verified": True,
        }

    def add_features(self, layer_id: str, features: list[dict[str, Any]]) -> dict[str, Any]:
        """Add new spatial features to a layer."""
        return self.apply_edits(layer_id=layer_id, adds=features)

    def update_features(self, layer_id: str, features: list[dict[str, Any]]) -> dict[str, Any]:
        """Update existing spatial features in a layer."""
        return self.apply_edits(layer_id=layer_id, updates=features)

    def delete_features(self, layer_id: str, object_ids: list[str | int]) -> dict[str, Any]:
        """Delete spatial features by OBJECTID from a layer."""
        return self.apply_edits(layer_id=layer_id, deletes=object_ids)

