from __future__ import annotations

from dataclasses import dataclass
from typing import List

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import (
    GISProviderUnavailableError,
    GISDataExtractionError,
)


class GISRuntimeError(Exception):
    """Raised when real GIS runtime operations fail."""


@dataclass(frozen=True)
class RealGISProject:
    provider_name: str
    project_path: str
    provider: GISProviderInterface


def load_real_gis_project(
    *,
    qgis_project_path: str | None = None,
    arcgis_project_path: str | None = None,
) -> List[RealGISProject]:
    """
    Real GIS loader with lazy provider imports.
    No GIS SDK import at module-load time (only inside this function).

    Returns list of loaded projects depending on inputs provided.

    Raises:
      - GISProviderUnavailableError / GISDataExtractionError wrapped as GISRuntimeError
    """
    projects: List[RealGISProject] = []

    if qgis_project_path:
        try:
            from gis_integration.providers.qgis_provider import QGISProvider  # lazy import
        except Exception as exc:
            raise GISRuntimeError(f"QGIS provider unavailable: {exc}") from exc

        provider = QGISProvider()
        try:
            provider.load_project(qgis_project_path)
        except (GISProviderUnavailableError, GISDataExtractionError) as exc:
            raise GISRuntimeError(f"Failed to load QGIS project: {exc}") from exc
        projects.append(RealGISProject("qgis", qgis_project_path, provider))

    if arcgis_project_path:
        try:
            from gis_integration.providers.arcgis_provider import ArcGISProvider  # lazy import
        except Exception as exc:
            raise GISRuntimeError(f"ArcGIS provider unavailable: {exc}") from exc

        provider = ArcGISProvider()
        try:
            provider.load_project(arcgis_project_path)
        except (GISProviderUnavailableError, GISDataExtractionError) as exc:
            raise GISRuntimeError(f"Failed to load ArcGIS project: {exc}") from exc
        projects.append(RealGISProject("arcgis", arcgis_project_path, provider))

    return projects
