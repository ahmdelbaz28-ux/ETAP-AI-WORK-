"""Abstract External ADMS and GIS Feeder Connector Interfaces.

Provides fail-closed abstract placeholders for enterprise utility integrations:
- Schneider Electric EcoStruxure ADMS & Geographic Real-time Reliability (GRR)
- Schneider Electric / Telvent ArcFM & Feeder Services

ARCHITECTURAL PRINCIPLES:
1. No Synthetic / Guessed API Contracts:
   Proprietary Schneider EcoStruxure and ArcFM SDK protocols are not invented.
2. Fail-Closed BLOCKED Status:
   Any invocation of these connectors explicitly returns BLOCKED with code
   `CONNECTOR_NOT_IMPLEMENTED`. Mocking success in production is strictly forbidden.
3. Feature-Flag Gating:
   Gated behind feature flags `arcfm_connector` and `adms_ecostruxure_connector`
   (both disabled by default in api/feature_flags.py).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from api.feature_flags import is_feature_enabled
from etap_integration.etap_rest import ETAPRestError

logger = logging.getLogger(__name__)


class BaseADMSConnector(ABC):
    """Abstract interface for external ADMS / GIS feeder network synchronizers."""

    def __init__(self, endpoint_url: Optional[str] = None) -> None:
        self.endpoint_url = endpoint_url

    @abstractmethod
    async def connect(self) -> None:
        """Establish session or COM/WCF connection to the ADMS gateway."""

    @abstractmethod
    async def fetch_feeder_topology(self, feeder_id: str) -> dict[str, Any]:
        """Retrieve feeder single-line connectivity and asset parameters."""

    @abstractmethod
    async def sync_switch_states(self, switch_updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Push switch status operations to ADMS state estimator."""


class ArcFMFeederConnector(BaseADMSConnector):
    """Placeholder interface for Schneider / Telvent ArcFM and Feeder Services.

    Always reports BLOCKED. Not field-validated against live ArcFM deployments.
    """

    async def connect(self) -> None:
        if not is_feature_enabled("arcfm_connector", default=False):
            raise ETAPRestError(
                code="FEATURE_DISABLED",
                message="ArcFM connector is disabled (flag arcfm_connector OFF).",
            )
        logger.warning("ArcFMFeederConnector invoked: connector is abstract placeholder.")
        raise ETAPRestError(
            code="BLOCKED",
            message="ArcFM Feeder Services connector is not implemented. Report BLOCKED instead of mocking success.",
            details={"provider": "ArcFM", "status": "BLOCKED"},
        )

    async def fetch_feeder_topology(self, feeder_id: str) -> dict[str, Any]:
        await self.connect()
        return {}

    async def sync_switch_states(self, switch_updates: list[dict[str, Any]]) -> dict[str, Any]:
        await self.connect()
        return {}


class EcoStruxureADMSConnector(BaseADMSConnector):
    """Placeholder interface for Schneider Electric EcoStruxure ADMS & GRR.

    Always reports BLOCKED. Not field-validated against live Schneider deployments.
    """

    async def connect(self) -> None:
        if not is_feature_enabled("adms_ecostruxure_connector", default=False):
            raise ETAPRestError(
                code="FEATURE_DISABLED",
                message="EcoStruxure ADMS connector is disabled (flag adms_ecostruxure_connector OFF).",
            )
        logger.warning("EcoStruxureADMSConnector invoked: connector is abstract placeholder.")
        raise ETAPRestError(
            code="BLOCKED",
            message="EcoStruxure ADMS / GRR connector is not implemented. Report BLOCKED instead of mocking success.",
            details={"provider": "EcoStruxure ADMS", "status": "BLOCKED"},
        )

    async def fetch_feeder_topology(self, feeder_id: str) -> dict[str, Any]:
        await self.connect()
        return {}

    async def sync_switch_states(self, switch_updates: list[dict[str, Any]]) -> dict[str, Any]:
        await self.connect()
        return {}
