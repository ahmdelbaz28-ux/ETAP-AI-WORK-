from __future__ import annotations

"""GIS Integration Providers - Concrete GIS provider implementations.

Provides provider implementations for ESRI ArcGIS and QGIS, implementing
the GISProviderInterface for spatial data extraction and transformation.

🗃️ GIS Provider Architecture
- QGISProvider: Primary production provider (requires QGIS SDK on target machine)
- MockGISProvider: Development/test only (gated by mock_gis_provider feature flag)
- ArcGISProvider: ARCHIVED — raises NotImplementedFeature; use QGISProvider instead

SECURITY NOTE on MockGISProvider:
    The mock provider is gated by the ``mock_gis_provider`` feature flag
    (see ``api.feature_flags.DEFAULT_FEATURE_FLAGS``). In development/test
    environments the flag auto-enables, so the mock remains available for
    unit tests and local dev. In staging/production the flag defaults to
    disabled, meaning:

      * ``USE_MOCK_GIS=true`` env var alone is NOT enough to use the mock.
      * ``provider_type='mock'`` requests will raise ``RuntimeError``.
      * Auto-fallback when QGIS fails will raise the original exception instead
        of silently serving mock spatial data.
      * ArcGIS requests will always raise NotImplementedFeature (no mock fallback).

    To enable the mock in production (e.g., for a HF Space without desktop
    GIS SDKs), toggle the flag via the admin API or the
    ``.feature-flags.json`` file.
"""

import logging
import os

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import NotImplementedFeature
from gis_integration.providers.arcgis_provider import ArcGISProvider
from gis_integration.providers.mock_gis import MockGISProvider
from gis_integration.providers.qgis_provider import QGISProvider

logger = logging.getLogger(__name__)


def _mock_gis_allowed() -> bool:
    """Return True if MockGISProvider may be used in the current env.

    Honors the ``mock_gis_provider`` feature flag. ``is_feature_enabled``
    auto-returns True in dev/test envs, so the mock is always available
    there. In prod/staging it returns True only if the flag has been
    explicitly toggled on.
    """
    try:
        from api.feature_flags import is_feature_enabled

        return bool(is_feature_enabled("mock_gis_provider"))
    except Exception:
        logger.warning("feature_flags subsystem unavailable; falling back to USE_MOCK_GIS env var")
        return os.getenv("USE_MOCK_GIS", "false").lower() == "true"


def get_gis_provider(provider_type: str | None = None) -> GISProviderInterface:
    """
    Factory to resolve the appropriate GIS provider.

    Priority:
    1. If USE_MOCK_GIS=true or provider_type='mock' AND mock_gis_allowed()
       -> MockGISProvider
    2. arcgis -> raise NotImplementedFeature (archived)
    3. qgis -> QGISProvider (with mock fallback if unavailable and mock allowed)

    Raises:
        NotImplementedFeature: if arcgis provider type is requested (archived).
        RuntimeError: if mock is requested or required as fallback but the
            ``mock_gis_provider`` feature flag is disabled in the current
            environment.
    """
    use_mock = os.getenv("USE_MOCK_GIS", "false").lower() == "true"
    mock_allowed = _mock_gis_allowed()

    if (use_mock or provider_type == "mock") and mock_allowed:
        return MockGISProvider()
    if (use_mock or provider_type == "mock") and not mock_allowed:
        raise RuntimeError(
            "MockGISProvider requested but the 'mock_gis_provider' feature "
            "flag is disabled in this environment. Enable the flag via the "
            "admin API or .feature-flags.json, or run in dev/test env."
        )

    p_type = (provider_type or os.getenv("GIS_PROVIDER", "qgis")).lower()

    if p_type == "arcgis":
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    if p_type == "qgis":
        p = QGISProvider()
        if not p.health_check() and mock_allowed:
            logger.warning("QGIS health_check failed; falling back to MockGISProvider")
            return MockGISProvider()
        if not p.health_check() and not mock_allowed:
            raise RuntimeError(
                "QGIS provider is not operational and mock fallback is "
                "disabled by the 'mock_gis_provider' feature flag."
            )
        return p

    if mock_allowed:
        return MockGISProvider()
    raise RuntimeError(
        f"Unknown GIS provider type {p_type!r} and mock fallback is disabled "
        "by the 'mock_gis_provider' feature flag."
    )


__all__ = [
    "ArcGISProvider",
    "QGISProvider",
    "MockGISProvider",
    "get_gis_provider",
]
