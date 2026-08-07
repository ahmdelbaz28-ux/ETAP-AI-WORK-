"""
Autodesk Connector Health & Test API Router
=============================================
Provides endpoints for monitoring the health status of Autodesk connectors
(AutoCAD and Revit) and testing pipe connections to their C# plugins.

Connectors:
    - AutoCAD (AutoCADPluginClient on port 4820)
    - Revit   (RevitPluginClient   on port 4830)

Endpoints:
    GET  /status            — aggregated health of all Autodesk connectors
    GET  /status/autocad    — AutoCAD connector status
    GET  /status/revit      — Revit connector status
    POST /test-connection   — test pipe connection to a specific connector
    GET  /timeouts          — get current timeout configuration
    PUT  /timeouts          — update timeout configuration
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.dependencies import get_api_key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/connectors/autodesk",
    tags=["connectors", "autodesk"],
    dependencies=[Depends(get_api_key)],
)

# ---------------------------------------------------------------------------
# Module-level timeout configuration (in-memory)
# ---------------------------------------------------------------------------

_timeout_config: dict[str, int] = {
    "autocad_timeout_seconds": 30,
    "revit_timeout_seconds": 30,
}

# Track when each connector was last successfully contacted.
_last_success_ts: dict[str, Optional[float]] = {
    "autocad": None,
    "revit": None,
}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConnectorType(StrEnum):
    """Supported Autodesk connector types."""

    AUTOCAD = "autocad"
    REVIT = "revit"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ConnectorStatusResponse(BaseModel):
    """Status of a single Autodesk connector."""

    connector_type: str = Field(
        ...,
        description="Connector type identifier (autocad or revit)",
    )
    connected: bool = Field(
        ...,
        description="Whether the connector plugin is reachable",
    )
    host: str = Field(
        ...,
        description="Host address of the connector plugin",
    )
    port: int = Field(
        ...,
        description="Port number of the connector plugin",
    )
    last_check: str = Field(
        default="",
        description="ISO-8601 UTC timestamp of the last health check",
    )
    uptime_seconds: Optional[float] = Field(
        default=None,
        description="Seconds since the connector was last confirmed reachable",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the connector is unreachable",
    )


class ConnectorHealthResponse(BaseModel):
    """Aggregated health status of all Autodesk connectors."""

    autocad_status: ConnectorStatusResponse = Field(
        ...,
        description="AutoCAD connector status",
    )
    revit_status: ConnectorStatusResponse = Field(
        ...,
        description="Revit connector status",
    )
    overall_healthy: bool = Field(
        ...,
        description="True if all connectors are reachable",
    )


class ConnectionTestRequest(BaseModel):
    """Request body for testing a connector pipe connection."""

    connector_type: ConnectorType = Field(
        ...,
        description="Which connector to test (autocad or revit)",
    )
    timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Connection timeout in seconds",
    )


class ConnectionTestResponse(BaseModel):
    """Result of a connector pipe connection test."""

    success: bool = Field(
        ...,
        description="Whether the connection test succeeded",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Round-trip latency in milliseconds",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the test failed",
    )
    connector_type: str = Field(
        ...,
        description="The connector type that was tested",
    )


class ConnectorTimeoutConfig(BaseModel):
    """Timeout configuration for Autodesk connectors."""

    autocad_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="AutoCAD plugin request timeout in seconds",
    )
    revit_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Revit plugin request timeout in seconds",
    )

    @field_validator("autocad_timeout_seconds", "revit_timeout_seconds")
    @classmethod
    def _timeout_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Timeout must be at least 1 second")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 'Z' timestamp."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_connector_status(connector_type: str) -> ConnectorStatusResponse:
    """Build a :class:`ConnectorStatusResponse` by probing the connector.

    This function lazily imports the connector client classes to avoid
    import-time failures when the connector modules are not installed.
    """

    now_iso = _utc_now_iso()
    now_ts = time.time()

    if connector_type == ConnectorType.AUTOCAD:
        from autodesk_connector.autocad.connector import AutoCADPluginClient

        host = "localhost"
        port = 4820
        timeout = _timeout_config["autocad_timeout_seconds"]
        client = AutoCADPluginClient(
            base_url=f"http://{host}:{port}",
            timeout=timeout,
        )
    elif connector_type == ConnectorType.REVIT:
        from autodesk_connector.revit.connector import RevitPluginClient

        host = "localhost"
        port = 4830
        timeout = _timeout_config["revit_timeout_seconds"]
        client = RevitPluginClient(
            base_url=f"http://{host}:{port}",
            timeout=timeout,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector type: {connector_type}",
        )

    error_msg: Optional[str] = None
    try:
        connected = client.is_available()
    except Exception as exc:  # noqa: BLE001
        connected = False
        error_msg = str(exc)
        logger.warning(
            "connector_health_check_failed type=%s error=%s",
            connector_type,
            error_msg,
        )

    # Update last-success timestamp
    if connected:
        _last_success_ts[connector_type] = now_ts
    uptime_seconds: Optional[float] = None
    last_success = _last_success_ts.get(connector_type)
    if last_success is not None:
        uptime_seconds = round(now_ts - last_success, 2)

    return ConnectorStatusResponse(
        connector_type=connector_type,
        connected=connected,
        host=host,
        port=port,
        last_check=now_iso,
        uptime_seconds=uptime_seconds,
        error=error_msg,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    summary="Get health status of all Autodesk connectors",
)
async def get_connector_status() -> ConnectorHealthResponse:
    """Return the aggregated health status of all Autodesk connectors.

    Probes both the AutoCAD and Revit plugin endpoints and returns
    individual status objects plus an ``overall_healthy`` flag that is
    ``True`` only when *both* connectors are reachable.
    """

    autocad = _build_connector_status(ConnectorType.AUTOCAD)
    revit = _build_connector_status(ConnectorType.REVIT)

    return ConnectorHealthResponse(
        autocad_status=autocad,
        revit_status=revit,
        overall_healthy=autocad.connected and revit.connected,
    )


@router.get(
    "/status/autocad",
    summary="Get AutoCAD connector status",
)
async def get_autocad_status() -> ConnectorStatusResponse:
    """Return the health status of the AutoCAD connector specifically.

    Probes the AutoCAD plugin health endpoint at ``http://localhost:4820/health``.
    """

    return _build_connector_status(ConnectorType.AUTOCAD)


@router.get(
    "/status/revit",
    summary="Get Revit connector status",
)
async def get_revit_status() -> ConnectorStatusResponse:
    """Return the health status of the Revit connector specifically.

    Probes the Revit plugin health endpoint at ``http://localhost:4830/health``.
    """

    return _build_connector_status(ConnectorType.REVIT)


@router.post(
    "/test-connection",
    summary="Test pipe connection to a specific connector",
)
async def test_connection(request: ConnectionTestRequest) -> ConnectionTestResponse:
    """Test a pipe connection to the specified Autodesk connector.

    Sends a health-check request to the connector's plugin and measures
    the round-trip latency.  Returns success/failure status along with
    the latency in milliseconds.

    Args:
        request: The connection test request specifying which connector
            to test and the timeout in seconds.

    Returns:
        A :class:`ConnectionTestResponse` with the test result.
    """

    connector_type = request.connector_type.value
    timeout = request.timeout_seconds

    if connector_type == ConnectorType.AUTOCAD:
        from autodesk_connector.autocad.connector import AutoCADPluginClient

        host = "localhost"
        port = 4820
        client = AutoCADPluginClient(
            base_url=f"http://{host}:{port}",
            timeout=timeout,
        )
    elif connector_type == ConnectorType.REVIT:
        from autodesk_connector.revit.connector import RevitPluginClient

        host = "localhost"
        port = 4830
        client = RevitPluginClient(
            base_url=f"http://{host}:{port}",
            timeout=timeout,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector type: {connector_type}",
        )

    start = time.monotonic()
    error_msg: Optional[str] = None
    try:
        connected = client.is_available()
    except Exception as exc:  # noqa: BLE001
        connected = False
        error_msg = str(exc)
        logger.warning(
            "connector_test_failed type=%s error=%s",
            connector_type,
            error_msg,
        )
    elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)

    if connected:
        _last_success_ts[connector_type] = time.time()

    return ConnectionTestResponse(
        success=connected,
        latency_ms=elapsed_ms if connected else None,
        error=error_msg,
        connector_type=connector_type,
    )


@router.get(
    "/timeouts",
    summary="Get current timeout configuration",
)
async def get_timeouts() -> ConnectorTimeoutConfig:
    """Return the current timeout configuration for Autodesk connectors.

    Timeouts control how long the server waits for a response from the
    C# plugin before giving up.  The defaults are 30 seconds for both
    AutoCAD and Revit.
    """

    return ConnectorTimeoutConfig(**_timeout_config)


@router.put(
    "/timeouts",
    summary="Update timeout configuration",
)
async def update_timeouts(config: ConnectorTimeoutConfig) -> ConnectorTimeoutConfig:
    """Update the timeout configuration for Autodesk connectors.

    Accepts new timeout values (in seconds) for both AutoCAD and Revit
    connectors.  Values must be between 1 and 300 seconds inclusive.

    Args:
        config: The new timeout configuration.

    Returns:
        The updated :class:`ConnectorTimeoutConfig`.
    """

    _timeout_config["autocad_timeout_seconds"] = config.autocad_timeout_seconds
    _timeout_config["revit_timeout_seconds"] = config.revit_timeout_seconds

    logger.info(
        "connector_timeouts_updated autocad=%ds revit=%ds",
        config.autocad_timeout_seconds,
        config.revit_timeout_seconds,
    )

    return ConnectorTimeoutConfig(**_timeout_config)
