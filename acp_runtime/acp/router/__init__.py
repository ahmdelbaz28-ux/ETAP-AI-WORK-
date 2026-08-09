"""acp.router — JSON-RPC 2.0 dispatch layer.

The router sits between the Transport layer (receives raw dicts) and
the Runtime layer (executes capabilities). It is responsible for:

    * Validating the JSON-RPC envelope (pydantic v2)
    * Optional authentication (via ``auth_validator`` in RouterConfig)
    * Scope-based authorization
    * Optional audit logging (via ``audit_logger`` in RouterConfig)
    * Dispatching to the correct capability via AcpRuntime
    * Mapping exceptions back to JSON-RPC 2.0 error responses
    * Handling notifications (no response returned)

Out of scope:
    * Transport I/O (stdio, UDS, WebSocket) — Transport layer
    * Capability implementation — Runtime layer
    * Token issuance / HMAC signing — Security layer
"""

from __future__ import annotations

from acp.router.router import Router, RouterConfig
from acp.router.scope import ScopeValidator, check_scope

__all__ = [
    "Router",
    "RouterConfig",
    "ScopeValidator",
    "check_scope",
]
