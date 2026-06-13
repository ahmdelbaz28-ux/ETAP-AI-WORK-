"""Shared pytest fixtures / configuration."""
from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Force the asyncio backend (default on Windows)."""
    return "asyncio"
