import sys
from pathlib import Path

import pytest

# Ensure acp_runtime and repo root are on sys.path
ACP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ACP_DIR.parent
if str(ACP_DIR) not in sys.path:
    sys.path.insert(0, str(ACP_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def anyio_backend() -> str:
    """Force the asyncio backend (default on Windows)."""
    return "asyncio"
