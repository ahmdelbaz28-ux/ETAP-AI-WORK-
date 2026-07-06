"""
QGIS Provider — Fixed for QGIS 3.x
==================================
يحل المشاكل الحرجة في الإصدار القديم:
1. إضافة QgsApplication.setPrefixPath() + initQgis() قبل أي QgsProject
2. إضافة exitQgis() في cleanup
3. health_check() يفحص QgsProviderRegistry حقيقاً (لا يرجع True دائماً)
4. Auto-detect QGIS_PREFIX_PATH من env vars أو مسارات شائعة

Branch: fix/qgis-initqsis
Refs: PRODUCTION_PLAN/01_SELF_CRITICISM.md §3.3 #12-15
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from typing import Any

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISDataExtractionError, GISProviderUnavailableError
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict

logger = logging.getLogger(__name__)


def _detect_qgis_prefix() -> str | None:
    """Auto-detect QGIS installation prefix path.

    Priority:
    1. QGIS_PREFIX_PATH env var
    2. Common Windows path: C:\\Program Files\\QGIS 3.34
    3. Common Linux path: /usr
    4. Common macOS path: /Applications/QGIS.app/Contents/MacOS
    """
    # 1. Explicit env var
    env_prefix = os.environ.get("QGIS_PREFIX_PATH")
    if env_prefix and os.path.isdir(env_prefix):
        return env_prefix

    # 2. Auto-detect by platform
    candidates: list[str] = []
    if sys.platform == "win32":
        # Try common QGIS 3.x versions
        for ver in ("3.38", "3.36", "3.34", "3.32", "3.30", "3.28", "3.26"):
            candidates.append(rf"C:\Program Files\QGIS {ver}")
        # Generic fallback
        candidates.append(r"C:\Program Files\QGIS 3")
        candidates.append(r"C:\OSGeo4W64")
        candidates.append(r"C:\OSGeo4W")
    elif sys.platform == "darwin":
        candidates.append("/Applications/QGIS.app/Contents/MacOS")
        candidates.append("/usr/local")
    else:  # Linux
        candidates.append("/usr")
        candidates.append("/usr/local")
        candidates.append("/opt/QGIS")

    for path in candidates:
        if os.path.isdir(path):
            return path

    return None


class QGISProvider(GISProviderInterface):
    """
    QGIS provider مُصحَّح لـ QGIS 3.x.

    الاختلافات عن الإصدار القديم:
    1. يُهيِّئ QgsApplication.setPrefixPath() + initQgis() قبل أي عملية
    2. يُنظِّف exitQgis() عند الإغلاق (لو نحن من أنشأناها)
    3. health_check() يفحص QgsProviderRegistry حقيقاً
    4. Auto-detect QGIS_PREFIX_PATH من env vars أو مسارات شائعة

    متطلبات:
        - QGIS 3.x مُثبَّت
        - متغير البيئة QGIS_PREFIX_PATH (مثلاً: C:\\Program Files\\QGIS 3.34)
        - أو تشغيل من داخل QGIS Python Console
    """

    def __init__(self) -> None:
        self._loaded = False
        self._project_path: str | None = None
        self._crs: GeoCRSInfo = GeoCRSInfo()
        self._layers: list[str] = []
        self._layer_index: dict[str, str] = {}
        self._qgs_app: Any = None  # QgsApplication instance
        self._owns_qgs_app: bool = False  # هل نحن من أنشأناها؟
        self._project: Any = None  # QgsProject.instance()

    # ─── QGIS Application Lifecycle ────────────────────────────────

    def _ensure_qgs_application(self) -> None:
        """
        تهيئة QgsApplication مرة واحدة (singleton).

        لو QgsApplication.instance() موجود (تشغيل من QGIS console)، نستخدمه.
        وإلا، نُنشئ واحد جديد مع setPrefixPath + initQgis.
        """
        if self._qgs_app is not None:
            return  # already initialized

        try:
            from qgis.core import QgsApplication  # type: ignore
        except ImportError as exc:
            raise GISProviderUnavailableError(
                f"QGIS Python bindings unavailable: {exc}. "
                f"Set QGIS_PREFIX_PATH env var or run from QGIS Python Console."
            ) from exc

        # Check if already running inside QGIS (e.g., from QGIS Python Console)
        existing = QgsApplication.instance()
        if existing is not None:
            self._qgs_app = existing
            self._owns_qgs_app = False
            logger.debug("Using existing QgsApplication (running inside QGIS)")
            return

        # New initialization — need prefix path
        prefix_path = _detect_qgis_prefix()
        if not prefix_path:
            raise GISProviderUnavailableError(
                "QGIS prefix path not found. Set QGIS_PREFIX_PATH env var "
                "to your QGIS installation directory "
                "(e.g., C:\\Program Files\\QGIS 3.34 on Windows, "
                "/usr on Linux, /Applications/QGIS.app on macOS)."
            )

        # Set offscreen platform for headless rendering (no GUI needed)
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        # Initialize QgsApplication
        self._qgs_app = QgsApplication([], False)  # non-GUI mode
        self._qgs_app.setPrefixPath(prefix_path, True)
        self._qgs_app.initQgis()
        self._owns_qgs_app = True

        logger.info(
            "✅ QGIS initialized — version: %s, prefix: %s",
            self._qgs_app.version(),
            prefix_path,
        )

    def _cleanup_qgs_application(self) -> None:
        """تنظيف QgsApplication عند الإغلاق (لو نحن من أنشأناها)."""
        if self._qgs_app is not None and self._owns_qgs_app:
            try:
                self._qgs_app.exitQgis()
                logger.debug("QGIS application exited cleanly")
            except Exception as exc:
                logger.warning("Failed to exit QGIS cleanly: %s", exc)
            finally:
                self._qgs_app = None
                self._owns_qgs_app = False

    # ─── GISProviderInterface Implementation ───────────────────────

    def load_project(self, path: str) -> None:
        """
        تحميل مشروع QGIS (.qgs أو .qgz).

        Raises:
            GISProviderUnavailableError: لو QGIS غير متاح
            GISDataExtractionError: لو فشل تحميل المشروع
        """
        # Initialize QGIS application first (critical fix)
        self._ensure_qgs_application()

        # Import after initialization
        from qgis.core import QgsProject  # type: ignore

        self._project_path = path

        try:
            # Use the global instance (singleton)
            self._project = QgsProject.instance()
            self._project.clear()  # clear any previous state
            self._project.read(path)
            logger.info("✅ Loaded QGIS project: %s", path)
        except Exception as exc:
            raise GISDataExtractionError(
                f"Failed to load QGIS project '{path}': {exc}"
            ) from exc

        # List layers
        try:
            self._layers = [lyr.name() for lyr in self._project.mapLayers().values()]
            self._layer_index = {
                lyr.name(): lyr.id() for lyr in self._project.mapLayers().values()
            }
            logger.info("Project contains %d layers", len(self._layers))
        except Exception as exc:
            logger.exception("Failed to list layers: %s", exc)
            self._layers = []
            self._layer_index = {}

        self._loaded = True

    def list_layers(self) -> list[str]:
        if not self._loaded:
            return []
        return list(self._layers)

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        """استخراج features من layer معين."""
        if not self._loaded:
            raise GISDataExtractionError("QGIS project not loaded")

        from qgis.core import QgsProject  # type: ignore

        try:
            project = QgsProject.instance()
            layers = project.mapLayers().values()

            # Find layer by name
            layer = None
            for lyr in layers:
                if getattr(lyr, "name", lambda: None)() == layer_id:
                    layer = lyr
                    break

            if layer is None:
                logger.warning("Layer '%s' not found in project", layer_id)
                return iter(())

            # Iterate features
            for i, feat in enumerate(layer.getFeatures()):
                geom = feat.geometry()
                if geom is None:
                    logger.warning("Feature %d has no geometry, skipping", i)
                    continue

                geojson_geom_str = geom.asJson()
                geom_dict = safe_parse_geojson(geojson_geom_str)

                ok, reason = validate_geometry_dict(geom_dict)
                if not ok:
                    logger.warning("Feature %d invalid geometry: %s", i, reason)
                    continue

                # Extract attributes
                props = {}
                try:
                    attrs = feat.attributes()
                    fields = layer.fields()
                    for idx, val in enumerate(attrs):
                        if idx < len(fields):
                            key = fields[idx].name()
                            # Convert QGIS types to JSON-serializable
                            if hasattr(val, "toString"):
                                val = val.toString()
                            props[key] = val
                except Exception as exc:
                    logger.warning("Failed to extract attrs for feature %d: %s", i, exc)

                feature = GISFeature(
                    id=str(feat.id() if feat.id() is not None else i),
                    geometry=geom_dict,
                    properties=props,
                    layer_name=layer_id,
                    crs=self._crs.crs,
                )
                yield feature

        except GISDataExtractionError:
            raise
        except Exception as exc:
            raise GISDataExtractionError(
                f"Failed to extract features from QGIS layer '{layer_id}': {exc}"
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
                f"Failed to export GeoJSON from QGIS layer '{layer_id}': {exc}"
            ) from exc

    def get_crs(self, layer_id: str | None = None) -> GeoCRSInfo:
        """الحصول على CRS للـ layer أو للمشروع."""
        if self._loaded and self._project is not None and layer_id:
            try:
                layers = self._project.mapLayers().values()
                for lyr in layers:
                    if lyr.name() == layer_id:
                        crs = lyr.crs()
                        return GeoCRSInfo(
                            crs=crs.authid(),
                            normalized=True,
                        )
            except Exception as exc:
                logger.warning("Failed to get CRS for layer '%s': %s", layer_id, exc)
        return self._crs

    def health_check(self) -> bool:
        """
        فحص حقيقي لـ QGIS SDK.

        Returns True فقط لو:
        1. QGIS Python bindings متاحة
        2. QgsApplication مهيَّأ
        3. QgsProviderRegistry.instance() موجود
        """
        try:
            self._ensure_qgs_application()
            from qgis.core import QgsProviderRegistry  # type: ignore

            registry = QgsProviderRegistry.instance()
            return registry is not None
        except Exception as exc:
            logger.exception("QGIS health check failed: %s", exc)
            return False

    # ─── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
        """تنظيف الموارد."""
        self._loaded = False
        self._project = None
        self._cleanup_qgs_application()

    def __del__(self):
        """تنظيف عند garbage collection."""
        try:
            self._cleanup_qgs_application()
        except Exception:
            pass  # don't raise in __del__
