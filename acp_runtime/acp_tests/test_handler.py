"""Tests for the @capability decorator and discovery helpers."""

from __future__ import annotations

import pytest
from acp.runtime.handler import (
    CapabilityMeta,
    capability,
    discover_capabilities,
    list_capabilities,
)
from acp.schema.capability import CapabilityDescriptor


class MathHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        return a + b

    @capability("math.mul", scopes=("math.read",))
    def mul(self, a: int, b: int) -> int:
        return a * b


class MixedHandler:
    @capability("string.upper", scopes=("text.write", "text.read"))
    def upper(self, s: str) -> str:
        return s.upper()

    def helper(self, x: int) -> int:
        # Not decorated — must NOT show up in discovery.
        return x + 1


def test_decorator_attaches_metadata():
    MathHandler()
    meta = MathHandler.sum._acp_capability
    assert isinstance(meta, CapabilityMeta)
    assert meta.name == "math.sum"
    assert meta.scopes == ("math.read",)
    assert meta.method_name == "sum"


def test_decorator_preserves_functionality():
    h = MathHandler()
    import anyio

    async def call() -> int:
        return await h.sum(a=2, b=3)

    assert anyio.run(call) == 5
    assert h.mul(a=4, b=5) == 20


def test_discover_capabilities_returns_all_decorated():
    caps = discover_capabilities(MathHandler())
    assert set(caps.keys()) == {"math.sum", "math.mul"}
    assert caps["math.sum"].method_name == "sum"
    assert caps["math.mul"].method_name == "mul"


def test_discover_ignores_undecorated_methods():
    caps = discover_capabilities(MixedHandler())
    assert set(caps.keys()) == {"string.upper"}


def test_list_capabilities_returns_descriptors():
    descs = list_capabilities(MixedHandler())
    assert len(descs) == 1
    d = descs[0]
    assert isinstance(d, CapabilityDescriptor)
    assert d.name == "string.upper"
    assert d.scopes == ("text.write", "text.read")
    # Frozen model — must reject mutation.
    # Pydantic v1 raises AttributeError; Pydantic v2 raises ValidationError.
    # Accept either so the test works across both versions.
    with pytest.raises((AttributeError, Exception)):  # noqa: B017, BLE001
        d.name = "string.lower"  # type: ignore[misc]


def test_invalid_capability_name_rejected():
    with pytest.raises(ValueError):
        capability("Math.Sum")  # uppercase not allowed

    with pytest.raises(ValueError):
        capability("123math")  # must start with letter

    with pytest.raises(ValueError):
        capability("a" * 200)  # too long


def test_invalid_scope_rejected():
    with pytest.raises(ValueError):
        capability("foo", scopes=("BAD SCOPE",))

    with pytest.raises(ValueError):
        capability("foo", scopes=("ok.scope", "another bad-one"))


def test_empty_scopes_is_allowed():
    @capability("noop.void")
    def noop() -> None:
        return None

    meta = noop._acp_capability
    assert meta.scopes == ()


def test_capability_meta_is_frozen():
    meta = CapabilityMeta(name="x.y", scopes=(), method_name="y")
    with pytest.raises(AttributeError):
        meta.name = "x.z"  # type: ignore[misc]


def test_scopes_can_be_list_or_tuple():
    @capability("x.a", scopes=["s.read"])
    def a() -> None:
        return None

    meta = a._acp_capability
    assert meta.scopes == ("s.read",)  # normalized to tuple
