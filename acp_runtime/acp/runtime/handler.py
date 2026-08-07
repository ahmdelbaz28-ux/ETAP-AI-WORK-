"""@capability decorator, AcpHandler Protocol, and capability discovery.

A *handler* is any object with one or more methods decorated with
``@capability``. Discovery walks the object's class hierarchy (via
``dir()``) and returns a name -> metadata map.

The decorated function is mutated in place to carry an attribute
``_acp_capability: CapabilityMeta``. This is a documented contract that
``discover_capabilities`` depends on; the attribute name is prefixed
with an underscore to discourage external use.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from acp.schema.capability import (
    CapabilityDescriptor,
    is_valid_capability_name,
    is_valid_scope,
)

__all__ = [
    "AcpHandler",
    "capability",
    "discover_capabilities",
    "list_capabilities",
    "CapabilityMeta",
]

_CAPABILITY_ATTR = "_acp_capability"


@dataclass(frozen=True)
class CapabilityMeta:
    """Internal metadata stored on a @capability-decorated function."""

    name: str
    scopes: tuple[str, ...]
    method_name: str


@runtime_checkable
class AcpHandler(Protocol):
    """Protocol — any object with @capability-decorated methods is an AcpHandler.

    Not enforced structurally at runtime; this is for type checkers.
    """


def capability(
    name: str,
    *,
    scopes: tuple[str, ...] | list[str] = (),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a method as a callable capability.

    Args:
        name: dotted, lower-snake-case identifier (e.g. ``"math.sum"``).
        scopes: zero or more scope strings required to invoke this capability.

    Returns:
        The original function, with a ``_acp_capability: CapabilityMeta``
        attribute attached.

    Raises:
        ValueError: if ``name`` or any scope is not a valid identifier.
    """
    if not is_valid_capability_name(name):
        raise ValueError(
            f"Invalid capability name: {name!r} (must match ^[a-z][a-z0-9_.-]{{0,127}}$)",
        )
    scopes_t = tuple(scopes)
    for s in scopes_t:
        if not is_valid_scope(s):
            raise ValueError(f"Invalid scope: {s!r} (must match ^[a-z][a-z0-9_.-]{{0,127}}$)")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            func,
            _CAPABILITY_ATTR,
            CapabilityMeta(name=name, scopes=scopes_t, method_name=func.__name__),
        )
        return func

    return decorator


def discover_capabilities(obj: Any) -> dict[str, CapabilityMeta]:
    """Return a name -> CapabilityMeta map of all @capability methods on ``obj``.

    Walks the full ``dir()`` of the object. Does not follow the MRO
    explicitly because ``dir()`` already includes inherited attributes
    for normal classes.
    """
    out: dict[str, CapabilityMeta] = {}
    for attr_name in dir(obj):
        # Cheap guard against re-walking a class attribute we already
        # resolved via descriptor protocol.
        try:
            attr = getattr(obj, attr_name, None)
        except AttributeError:
            continue
        if not callable(attr):
            continue
        meta = getattr(attr, _CAPABILITY_ATTR, None)
        if isinstance(meta, CapabilityMeta):
            out[meta.name] = meta
    return out


def list_capabilities(obj: Any) -> list[CapabilityDescriptor]:
    """Same as ``discover_capabilities`` but in public manifest form."""
    return [
        CapabilityDescriptor(name=meta.name, scopes=meta.scopes)
        for meta in discover_capabilities(obj).values()
    ]
