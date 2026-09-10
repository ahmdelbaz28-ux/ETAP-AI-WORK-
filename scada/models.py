"""
scada/models.py — Data contracts and schemas for SCADA control operations.

Complies with:
- IEC 61850 (CSWI / XCBR control model)
- IEC 60870-5-104 (Command ASDUs)
- IEEE C37.90 (Relay and breaker control)
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

UTC = timezone.utc


class ControlProtocol(str, enum.Enum):  # noqa: UP042
    """Supported industrial OT communication protocols."""

    OPC_UA = "opc_ua"
    MODBUS_TCP = "modbus_tcp"
    IEC_104 = "iec_104"
    IEC_61850 = "iec_61850"


class ControlActionType(str, enum.Enum):  # noqa: UP042
    """Types of control actions on electrical equipment."""

    BREAKER_OPEN = "breaker_open"
    BREAKER_CLOSE = "breaker_close"
    SETPOINT_VOLTAGE = "setpoint_voltage"
    SETPOINT_ACTIVE_POWER = "setpoint_active_power"
    SETPOINT_REACTIVE_POWER = "setpoint_reactive_power"
    TAP_CHANGER = "tap_changer"


class CommandStatus(str, enum.Enum):  # noqa: UP042
    """Lifecycle status of a control command."""

    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SignalQuality(str, enum.Enum):  # noqa: UP042
    """IEC 61850 / SCADA telemetry quality classifications."""

    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    INVALID = "INVALID"


class BreakerState(str, enum.Enum):  # noqa: UP042
    """Double-point circuit breaker physical states."""

    OPEN = "OPEN"  # 01 binary
    CLOSED = "CLOSED"  # 10 binary
    INTERMEDIATE = "INTERMEDIATE"  # 00 binary (in transit)
    FAULTED = "FAULTED"  # 11 binary (discrepancy)


class ControlCommandRequest(BaseModel):
    """Request payload to propose a SCADA control operation."""

    model_config = ConfigDict(extra="ignore")

    device_id: str = Field(
        ..., min_length=1, max_length=64, description="Target device ID, e.g. 'CB_001'"
    )
    protocol: ControlProtocol = Field(default=ControlProtocol.OPC_UA)
    action_type: ControlActionType = Field(...)
    target_value: Any = Field(
        ..., description="Target value: 0/1 for breaker open/close, float for setpoints"
    )
    reason: str = Field(
        ..., min_length=5, max_length=500, description="Engineering justification for action"
    )
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    expected_current_state: Optional[str] = Field(
        default=None, description="Expected state before command (pre-check)"
    )
    timeout_sec: float = Field(
        default=5.0, ge=0.1, le=30.0, description="Max time to wait for readback verification"
    )
    local_remote_check: bool = Field(default=True, description="Enforce ANSI 43 remote-mode check")
    project_id: Optional[str] = Field(
        default=None, description="Optional associated power system project ID"
    )
    bay_id: Optional[str] = Field(default=None, description="Optional substation bay identifier")


class ControlCommandResponse(BaseModel):
    """Response returned upon proposing or executing a control command."""

    model_config = ConfigDict(from_attributes=True)

    command_id: str
    action_id: Optional[str] = None
    device_id: str
    protocol: ControlProtocol
    action_type: ControlActionType
    status: CommandStatus
    target_value: Any
    initial_state: Optional[Any] = None
    final_state: Optional[Any] = None
    readback_verified: bool = False
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
