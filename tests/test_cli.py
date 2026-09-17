"""Fake handler module for CLI tests.

This module exists so that ``acp_runtime/acp_tests/test_cli.py`` can load
it via ``_load_handlers("tests.test_cli")`` and verify the CLI handler-loading
logic.

The test asserts ``isinstance(h, FakeHandler)`` where ``FakeHandler`` is the
class defined in the test file. For that ``isinstance`` check to pass, this
module must expose the **same** class object (not a copy).

The test module lives at ``acp_runtime/acp_tests/test_cli.py``. Depending on
the pytest invocation (rootdir vs. ``acp_runtime/acp_tests/``), the module
may be importable as ``acp_tests.test_cli`` or as
``acp_runtime.acp_tests.test_cli``. We try both, and fall back to defining a
local ``FakeHandler`` if neither import works (which still lets the CLI
loading logic be exercised, just without the strict isinstance check).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Add acp_runtime/ to sys.path so we can import the test module as
# `acp_tests.test_cli` regardless of where pytest was invoked from.
_ACP_TESTS_DIR = Path(__file__).resolve().parent.parent / "acp_runtime"
if str(_ACP_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ACP_TESTS_DIR))

FakeHandler = None  # type: ignore[assignment]
for _mod_name in ("acp_tests.test_cli", "acp_runtime.acp_tests.test_cli"):
    try:
        _mod = importlib.import_module(_mod_name)
        if hasattr(_mod, "FakeHandler"):
            FakeHandler = _mod.FakeHandler
            break
    except ImportError:
        continue

if FakeHandler is None:
    try:
        from acp.runtime import capability  # type: ignore[import-not-found]
    except (ImportError, ModuleNotFoundError):
        def capability(name: str, scopes: tuple[str, ...] = ()):  # type: ignore[misc]
            def decorator(fn):
                fn.__capability_name__ = name
                fn.__capability_scopes__ = scopes
                return fn
            return decorator

    class FakeHandler:  # type: ignore[no-redef]
        @capability("math.sum", scopes=("math.read",))
        async def sum(self, a: int, b: int) -> int:
            return a + b


def test_fake_handler_importable():
    """Verify FakeHandler can be imported and executed for CLI handler-loading tests."""
    assert FakeHandler is not None, "FakeHandler must be defined"
    assert hasattr(FakeHandler, "sum"), "FakeHandler is missing the 'sum' capability method"
    import asyncio
    handler = FakeHandler()
    res = asyncio.run(handler.sum(2, 3))
    assert res == 5


__all__ = ["FakeHandler"]
