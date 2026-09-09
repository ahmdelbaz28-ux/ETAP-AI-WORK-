from __future__ import annotations


class GISIntegrationError(Exception):
    """Base exception for gis_integration subsystem."""


class GISProviderUnavailableError(GISIntegrationError):
    """Raised when a GIS provider dependency (QGIS/ArcGIS SDK) is unavailable."""


class GISDataExtractionError(GISIntegrationError):
    """Raised when GIS data extraction fails or returns invalid data."""


class GISTransformationError(GISIntegrationError):
    """Raised when transforming GIS data into ADMS-compatible structures fails."""


class NotImplementedFeature(GISIntegrationError):
    """Raised when a GIS provider feature (e.g., ArcGIS) is not implemented."""


class GISWriteError(GISIntegrationError):
    """Raised when a GIS write or edit operation fails or is rolled back."""


class GISCapabilityError(GISIntegrationError):
    """Raised when a GIS service or layer lacks required capabilities (e.g. Create/Update/Delete)."""
