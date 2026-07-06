"""
ArcGIS Provider — Fixed for ArcGIS Pro 3.x
==========================================
يحل المشاكل الحرجة في الإصدار القديم:
1. load_project() يستخدم arcpy.mp.ArcGISProject(path) فعلياً
2. list_layers() يرجع الطبقات الحقيقية من المشروع
3. extract_features() يقرأ attributes من feature class
4. health_check() يفحص arcpy.GetInstallInfo()['Version']

Branch: fix/arcgis-load-aprx-real
Refs: PRODUCTION_PLAN/01_SELF_CRITICISM.md §3.4 #16-19
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import Any

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISDataExtractionError, GISProviderUnavailableError
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict

logger = logging.getLogger(__name__)


class ArcGISProvider(GISProviderInterface):
    """
    ArcGIS Pro provider مُصحَّح لـ ArcGIS Pro 3.x.

    الاختلافات عن الإصدار القديم:
    1. load_project() يستخدم arcpy.mp.ArcGISProject(path) فعلياً
       (الإصدار القديم كان يعين _loaded=True بدون فتح أي ملف)
    2. list_layers() يرجع الطبقات الحقيقية من project.listMaps()[0].listLayers()
    3. extract_features() يقرأ attributes من feature class عبر SearchCursor
    4. health_check() يفحص arcpy.GetInstallInfo()['Version'] يبدأ بـ '3.'
    5. get_crs() يقرأ CRS من layer عبر arcpy.Describe(layer).spatialReference

    متطلبات:
        - ArcGIS Pro 3.x مُثبَّت + license فعّالة
        - تشغيل من ArcGIS Pro Python environment
          (C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3)
    """

    def __init__(self) -> None:
        self._loaded = False
        self._crs: GeoCRSInfo = GeoCRSInfo()
        self._project_path: str | None = None
        self._project: Any = None  # arcpy.mp.ArcGISProject instance

    # ─── Helper: Import arcpy safely ───────────────────────────────

    def _import_arcpy(self) -> Any:
        """استيراد arcpy مع رسالة خطأ واضحة لو غير متاح."""
        try:
            import arcpy  # type: ignore
            return arcpy
        except ImportError as exc:
            raise GISProviderUnavailableError(
                f"ArcGIS Pro (arcpy) is unavailable: {exc}. "
                f"Run from ArcGIS Pro Python environment: "
                f"C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3"
            ) from exc

    # ─── GISProviderInterface Implementation ───────────────────────

    def load_project(self, path: str) -> None:
        """
        فتح مشروع ArcGIS Pro (.aprx).

        Args:
            path: مسار ملف .aprx (مطلق أو نسبي)

        Raises:
            GISProviderUnavailableError: لو arcpy غير متاح
            GISDataExtractionError: لو فشل فتح المشروع
        """
        arcpy = self._import_arcpy()

        # Validate path
        if not os.path.isabs(path):
            path = os.path.abspath(path)

        if not path.endswith((".aprx", ".mxd")):
            raise GISDataExtractionError(
                f"Expected .aprx file (ArcGIS Pro format), got: {path}. "
                f"Note: ArcGIS Pro uses .aprx, not .mxd (ArcMap)."
            )

        if not os.path.exists(path):
            raise GISDataExtractionError(f"ArcGIS Pro project not found: {path}")

        # Import arcpy.mp (separate module in ArcGIS Pro)
        try:
            import arcpy.mp as mp  # type: ignore
        except ImportError as exc:
            raise GISProviderUnavailableError(
                f"arcpy.mp unavailable (ArcGIS Pro required, not ArcMap): {exc}"
            ) from exc

        # Open the project (critical fix — was a no-op before)
        try:
            self._project = mp.ArcGISProject(path)
            self._project_path = path
            self._loaded = True
            logger.info("✅ Loaded ArcGIS Pro project: %s", path)
        except Exception as exc:
            raise GISDataExtractionError(
                f"Failed to open ArcGIS Pro project '{path}': {exc}. "
                f"Verify the file is not corrupted and you have ArcGIS Pro license."
            ) from exc

    def list_layers(self) -> list[str]:
        """إرجاع أسماء كل الـ layers في كل الـ maps."""
        if not self._loaded or self._project is None:
            return []

        try:
            layers: list[str] = []
            maps = self._project.listMaps()
            for m in maps:
                for lyr in m.listLayers():
                    layers.append(lyr.name)
            logger.info(
                "Found %d layers across %d maps", len(layers), len(maps)
            )
            return layers
        except Exception as exc:
            logger.exception("Failed to list layers: %s", exc)
            return []

    def _find_layer(self, layer_name: str) -> Any | None:
        """البحث عن layer بالاسم في كل الـ maps."""
        if self._project is None:
            return None
        for m in self._project.listMaps():
            for lyr in m.listLayers():
                if lyr.name == layer_name:
                    return lyr
        return None

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        """استخراج features من layer معين مع attributes."""
        if not self._loaded or self._project is None:
            raise GISDataExtractionError("ArcGIS provider not loaded")

        arcpy = self._import_arcpy()

        # Find layer in project
        layer = self._find_layer(layer_id)
        if layer is None:
            raise GISDataExtractionError(
                f"Layer '{layer_id}' not found in project '{self._project_path}'"
            )

        # Get layer fields
        try:
            field_names = [f.name for f in arcpy.ListFields(layer)]
            # Ensure OBJECTID is included
            if "OBJECTID" not in field_names and "OID@" not in field_names:
                field_names.insert(0, "OID@")
        except Exception as exc:
            logger.warning("Failed to list fields for '%s': %s", layer_id, exc)
            field_names = ["OID@"]

        # Build cursor fields: SHAPE@JSON for geometry + all attributes
        cursor_fields = ["SHAPE@JSON"] + field_names

        try:
            with arcpy.da.SearchCursor(layer, cursor_fields) as cursor:
                for idx, row in enumerate(cursor):
                    geom_json_str = row[0]
                    attrs = dict(zip(field_names, row[1:]))

                    # Parse geometry (SHAPE@JSON returns Esri JSON, not GeoJSON)
                    try:
                        geom_dict = safe_parse_geojson(geom_json_str)
                    except Exception as exc:
                        logger.warning(
                            "Feature OID=%s geometry parse failed: %s",
                            attrs.get("OBJECTID", idx), exc,
                        )
                        continue

                    # Validate geometry
                    ok, reason = validate_geometry_dict(geom_dict)
                    if not ok:
                        logger.warning(
                            "Feature OID=%s invalid geometry: %s",
                            attrs.get("OBJECTID", idx), reason,
                        )
                        continue

                    feature = GISFeature(
                        id=str(attrs.get("OBJECTID", idx)),
                        geometry=geom_dict,
                        properties=attrs,
                        layer_name=layer_id,
                        crs=self._crs.crs,
                    )
                    yield feature

        except Exception as exc:
            raise GISDataExtractionError(
                f"Failed to extract features from ArcGIS layer '{layer_id}': {exc}"
            ) from exc

    def export_geojson(self, layer_id: str) -> dict:
        """تصدير layer كـ GeoJSON dict."""
        try:
            features = list(self.extract_features(layer_id))
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": f.geometry,
                        "properties": f.properties | {"id": f.id, "layer": f.layer_name},
                    }
                    for f in features
                ],
                "crs": self._crs.crs,
            }
        except Exception as exc:
            raise GISDataExtractionError(
                f"Failed to export GeoJSON from ArcGIS layer '{layer_id}': {exc}"
            ) from exc

    def get_crs(self, layer_id: str | None = None) -> GeoCRSInfo:
        """الحصول على CRS للـ layer."""
        if self._loaded and layer_id:
            try:
                arcpy = self._import_arcpy()
                layer = self._find_layer(layer_id)
                if layer:
                    desc = arcpy.Describe(layer)
                    sr = desc.spatialReference
                    if sr:
                        crs_id = (
                            f"EPSG:{sr.factoryCode}"
                            if sr.factoryCode and sr.factoryCode > 0
                            else sr.exportToString()
                        )
                        return GeoCRSInfo(crs=crs_id, normalized=True)
            except Exception as exc:
                logger.warning("Failed to get CRS for '%s': %s", layer_id, exc)
        return self._crs

    def health_check(self) -> bool:
        """
        فحص حقيقي لـ ArcGIS Pro + arcpy.

        Returns True فقط لو:
        1. arcpy متاح
        2. ArcGIS Pro version يبدأ بـ '3.'
        3. License متاحة
        """
        try:
            arcpy = self._import_arcpy()
            info = arcpy.GetInstallInfo()
            version = info.get("Version", "")

            # Require ArcGIS Pro 3.x
            if not version.startswith("3."):
                logger.warning(
                    "ArcGIS Pro version %s not supported (requires 3.x)", version
                )
                return False

            # Check license
            if arcpy.CheckProduct("ArcInfo") == "Available":
                return True

            logger.warning("ArcGIS Pro license not available")
            return False

        except Exception as exc:
            logger.exception("ArcGIS health check failed: %s", exc)
            return False

    # ─── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
        """إغلاق المشروع (لو مفتوح)."""
        if self._project is not None:
            try:
                # ArcGISProject doesn't have explicit close, but we can release
                self._project = None
                self._loaded = False
                logger.debug("ArcGIS project released")
            except Exception as exc:
                logger.warning("Failed to close ArcGIS project: %s", exc)
