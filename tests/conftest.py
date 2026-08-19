"""
tests/conftest.py — Global pytest configuration for AhmedETAP test suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

# Ensure project root is at the front of sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment variables
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!")
