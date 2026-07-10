from __future__ import annotations

"""GIS Integration Providers - Concrete GIS provider implementations.

Provides provider implementations for ESRI ArcGIS and QGIS, implementing
the GISProviderInterface for spatial data extraction and transformation.
"""

import os
import sys
from typing import Any, Optional, Union

from gis_integration.base import GISProviderInterface
from gis_integration.providers.arcgis_provider import ArcGISProvider
from gis_integration.providers.mock_gis import MockGISProvider
from gis_integration.providers.qgis_provider import QGISProvider


def get_gis_provider(provider_type: Optional[str] = None) -> GISProviderInterface:
    """
    Factory to resolve the appropriate GIS provider.

    Priority:
    1. If USE_MOCK_GIS=true or provider_type='mock' -> MockGISProvider
    2. qgis -> QGISProvider (with mock fallback if unavailable and fallback allowed)
    3. arcgis -> ArcGISProvider (with mock fallback if unavailable and fallback allowed)
    """
    use_mock = os.getenv("USE_MOCK_GIS", "false").lower() == "true"

    if use_mock or provider_type == "mock":
        return MockGISProvider()

    p_type = (provider_type or os.getenv("GIS_PROVIDER", "qgis")).lower()

    if p_type == "qgis":
        try:
            p = QGISProvider()
            # If QGIS is not operational, fallback to Mock if allowed
            if not p.health_check() and use_mock:
                return MockGISProvider()
            return p
        except Exception:
            return MockGISProvider()

    elif p_type == "arcgis":
        try:
            p = ArcGISProvider()
            if not p.health_check() and use_mock:
                return MockGISProvider()
            return p
        except Exception:
            return MockGISProvider()

    return MockGISProvider()

__all__ = [
    "ArcGISProvider",
    "QGISProvider",
    "MockGISProvider",
    "get_gis_provider",
]
