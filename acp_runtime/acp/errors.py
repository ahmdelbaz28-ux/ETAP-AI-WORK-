"""AcpError hierarchy.

Every ACP error carries a JSON-RPC 2.0 error code. The codes -32700 to
-32603 are reserved by the JSON-RPC 2.0 spec; ACP defines -32001 to
-32007 for protocol-level concerns.

Layer rule: only these errors (plus stdlib exceptions) may leave a layer.
"""
from __future__ import annotations

from typing import Optional, Union
__all__ = [
    "AcpError",
    "DeadlineExceeded",
    "CapabilityNotFound",
    "ScopeNotPermitted",
    "HandlerError",
    "AuthenticationRequired",
    "RateLimitExceeded",
    "TransportClosed",
]


class AcpError(Exception):
    """Base class for every error this library raises.

    Subclasses must set ``code`` and may override ``message``.
    """

    code: int = -32603  # JSON-RPC "Internal error" (default)
    message: str = "Internal ACP error"

    def __init__(self, message: Optional[str] = None, *, data: Optional[dict] = None) -> None:
        if message is not None:
            self.message = message
        self.data: dict = data or {}
        super().__init__(self.message)

    def to_wire(self) -> dict:
        """Serialize as a JSON-RPC 2.0 error object."""
        out: dict = {"code": self.code, "message": self.message}
        if self.data:
            out["data"] = self.data
        return out

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code}, message={self.message!r})"


class DeadlineExceeded(AcpError):
    code = -32001
    message = "Execution deadline exceeded"


class CapabilityNotFound(AcpError):
    code = -32002
    message = "Capability not found"


class ScopeNotPermitted(AcpError):
    code = -32003
    message = "Scope not permitted"


class HandlerError(AcpError):
    code = -32004
    message = "Handler raised an exception"


class AuthenticationRequired(AcpError):
    code = -32005
    message = "Authentication required"


class RateLimitExceeded(AcpError):
    code = -32006
    message = "Rate limit exceeded"


class TransportClosed(AcpError):
    code = -32007
    message = "Transport closed mid-request"