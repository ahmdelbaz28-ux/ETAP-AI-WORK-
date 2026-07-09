"""ACP params / result base models.

These are the strongly-typed, domain-specific wrappers that sit inside
``JsonRpcRequest.params`` and ``JsonRpcResponse.result``. Every ACP
method defines its own params and result subclasses, but these bases
provide the common fields (capability, trace_id, deadline_ms) that
the Router layer validates before dispatching to the Runtime layer.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AcpParams", "AcpResult"]


class AcpParams(BaseModel):
    """Base model for every ACP request payload.

    Subclasses add their own typed fields (e.g. ``a: int``, ``b: int``
    for a sum capability). The router layer populates ``capability``,
    ``trace_id``, and ``deadline_ms`` from the envelope before passing
    the params to the runtime.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str = Field(min_length=1, max_length=128)
    trace_id: str = Field(default="", max_length=128)
    deadline_ms: int = Field(default=30_000, ge=1, le=600_000)


class AcpResult(BaseModel):
    """Base model for every ACP response payload.

    Subclasses add their own typed fields. The runtime layer fills
    ``capability`` and ``trace_id`` from the request before wrapping
    the handler's return value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str = Field(min_length=1, max_length=128)
    trace_id: str = Field(default="", max_length=128)
    output: Optional[Any] = None
