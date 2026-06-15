from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional

from gis_integration.models import GeoCRSInfo, GISFeature


class GISProviderInterface(ABC):
    """
    Dependency-free abstraction for GIS providers (QGIS / ArcGIS).

    Rules:
    - No eager GIS SDK imports
    - Strict return types
    - Must raise provider-specific unavailability/extraction errors
      (see gis_integration.exceptions)
    """

    @abstractmethod
    def load_project(self, path: str) -> None:
        """
        Load a GIS project from a local filesystem path.

        Default implementation records the project path. Concrete
        providers (ArcGIS, QGIS) override this to actually open the
        backend project file. Callers should always invoke
        :meth:`health_check` first to confirm the backend is up.
        """
        if not path or not isinstance(path, str):
            raise ValueError("Project path must be a non-empty string")
        self._project_path = path
        self._loaded = True

    def list_layers(self) -> List[str]:
        """
        List layer identifiers available in the currently loaded project.

        Default implementation returns an empty list. Providers must
        override to expose their layer catalog.
        """
        if not getattr(self, "_loaded", False):
            raise RuntimeError("No GIS project loaded; call load_project() first")
        return []

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        """
        Extract normalized GIS features from a layer.

        Default implementation yields no features. Providers must
        override to stream features from the backend.
        """
        if not getattr(self, "_loaded", False):
            raise RuntimeError("No GIS project loaded; call load_project() first")
        if not layer_id or not isinstance(layer_id, str):
            raise ValueError("layer_id must be a non-empty string")
        return iter(())

    def export_geojson(self, layer_id: str) -> Dict:
        """
        Export the specified layer as GeoJSON FeatureCollection or geometry dicts.

        Default implementation returns a minimal empty FeatureCollection
        with the requested layer_id recorded for traceability.
        """
        if not getattr(self, "_loaded", False):
            raise RuntimeError("No GIS project loaded; call load_project() first")
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {
                "layer_id": layer_id,
                "source_provider": self.__class__.__name__,
                "note": "empty (default implementation; override in subclass)",
            },
        }

    def get_crs(self, layer_id: Optional[str] = None) -> GeoCRSInfo:
        """
        Return CRS information for the given layer (or project default).

        Default implementation reports WGS84 (EPSG:4326), which is the
        most common interchange CRS. Providers should override to
        report the actual project / layer CRS.
        """
        return GeoCRSInfo(epsg=4326, name="WGS84", wkt="")

    def health_check(self) -> bool:
        """
        Return True if the provider backend is operational.

        Default implementation returns False (no backend wired up).
        Providers override to probe their SDK / service.
        """
        return False
