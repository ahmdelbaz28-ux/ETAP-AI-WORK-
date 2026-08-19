"""Root conftest.py for AhmedETAP.

Ensures the project root directory is on sys.path for test discovery and execution.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!")
os.environ.setdefault("ETAP_SECRET_KEY", "test-etap-secret-key-32-chars-long!")
