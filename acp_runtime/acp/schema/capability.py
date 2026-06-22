"""CapabilityDescriptor — wire-safe representation of a callable capability.

Used for discovery, manifests, and registry introspection. The internal
``@capability`` decorator stores richer metadata (including the bound
method name); the public descriptor is what is exposed across layer
boundaries.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_NAME_PATTERN = r"^[a-z][a-z0-9_.\-]{0,127}$"
SCOPE_PATTERN = r"^[a-z][a-z0-9_.\-]{0,127}$"

_CAPABILITY_NAME_RE = re.compile(CAPABILITY_NAME_PATTERN)
_SCOPE_RE = re.compile(SCOPE_PATTERN)


def is_valid_capability_name(name: str) -> bool:
    return isinstance(name, str) and bool(_CAPABILITY_NAME_RE.match(name))


def is_valid_scope(scope: str) -> bool:
    return isinstance(scope, str) and bool(_SCOPE_RE.match(scope))


class CapabilityDescriptor(BaseModel):
    """Public, frozen, wire-safe description of one capability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    scopes: tuple[str, ...] = Field(default_factory=tuple)

    def __init__(self, *, name: str, scopes: tuple[str, ...] | list[str] = ()) -> None:
        # Validate scopes at construction (Field(pattern=) only validates
        # string elements when the field type is list[str]; for tuple,
        # validate explicitly).
        scopes_t = tuple(scopes)
        for s in scopes_t:
            if not is_valid_scope(s):
                raise ValueError(f"Invalid scope: {s!r}")
        super().__init__(name=name, scopes=scopes_t)
