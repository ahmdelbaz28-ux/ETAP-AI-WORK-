"""JSON-RPC 2.0 envelope schemas — Request, Response, Notification, Error.

All models are frozen (immutable), extra=forbid, and validated at
construction. They serialise to plain dicts via ``model_dump(mode="json")``
and can be reconstructed from dicts via ``model_validate``.

ACP extensions on top of vanilla JSON-RPC 2.0:
    * ``capability``   — the ACP capability name being invoked
    * ``trace_id``     — opaque correlation id (logging / tracing)
    * ``deadline_ms``  — hard timeout for the request
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from acp.schema.ids import RequestId

__all__ = [
    "JsonRpcError",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcNotification",
]


# ------------------------------------------------------------------ Error

class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 error object."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: int
    message: str
    data: dict[str, Any] | None = None


# ------------------------------------------------------------------ Request

class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request with ACP extensions.

    ACP transports MUST include the ``capability`` field; the other
    extensions are optional. If ``id`` is omitted the request is treated
    as a notification (but the separate ``JsonRpcNotification`` model
    is preferred for explicit notifications).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    jsonrpc: str = Field(default="2.0", pattern=r"^2\.0$")
    id: RequestId
    method: str = Field(min_length=1, max_length=256)
    params: list[Any] | dict[str, Any] | None = None
    capability: str = Field(min_length=1, max_length=128)
    trace_id: str = Field(default="", max_length=512)
    deadline_ms: int = Field(default=30_000, ge=1, le=600_000)


# ------------------------------------------------------------------ Response

class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response.

    Exactly one of ``result`` or ``error`` must be present. The
    ``model_validator`` enforces this invariant.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    jsonrpc: str = Field(default="2.0", pattern=r"^2\.0$")
    id: RequestId | None = None
    result: Any | None = None
    error: JsonRpcError | None = None

    @model_validator(mode="after")
    def _exactly_one_of_result_or_error(self) -> JsonRpcResponse:
        if self.result is not None and self.error is not None:
            raise ValueError("response must have exactly one of result or error")
        if self.result is None and self.error is None:
            raise ValueError("response must have at least one of result or error")
        return self


# ------------------------------------------------------------------ Notification

class JsonRpcNotification(BaseModel):
    """JSON-RPC 2.0 notification (no ``id`` field).

    ACP uses notifications for:
        * progress updates
        * capability advertisements
        * audit / telemetry events

    The transport layer MUST NOT reply to a notification.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    jsonrpc: str = Field(default="2.0", pattern=r"^2\.0$")
    method: str = Field(min_length=1, max_length=256)
    params: list[Any] | dict[str, Any] | None = None
    capability: str | None = Field(default=None, max_length=128)
    trace_id: str = Field(default="", max_length=512)
    deadline_ms: int | None = Field(default=None, ge=1, le=600_000)


