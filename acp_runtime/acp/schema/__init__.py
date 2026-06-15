"""acp.schema — pydantic v2 models for the ACP wire format.

Public surface:
    CapabilityDescriptor   — frozen, validated capability name + scopes
    RequestId, TraceId     — constrained string types
    JsonRpcRequest         — JSON-RPC 2.0 request + ACP extensions
    JsonRpcResponse        — JSON-RPC 2.0 response (result xor error)
    JsonRpcNotification    — JSON-RPC 2.0 notification (no id)
    JsonRpcError           — JSON-RPC 2.0 error object
    AcpParams, AcpResult   — typed payload bases for params / result
"""
from __future__ import annotations

from acp.schema.capability import CapabilityDescriptor, is_valid_capability_name, is_valid_scope
from acp.schema.envelope import JsonRpcError, JsonRpcNotification, JsonRpcRequest, JsonRpcResponse
from acp.schema.ids import RequestId, TraceId
from acp.schema.params import AcpParams, AcpResult

__all__ = [
    "CapabilityDescriptor",
    "is_valid_capability_name",
    "is_valid_scope",
    "RequestId",
    "TraceId",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcNotification",
    "JsonRpcError",
    "AcpParams",
    "AcpResult",
]
