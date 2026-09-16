"""Production configuration for AhmedETAP Platform.

Contains configuration flags and environment validation for production deployment.
"""

from __future__ import annotations

import os
from typing import Any, Dict

# Feature flag: production_hardening enforced in production environment
production_hardening: bool = True

PRODUCTION_CONFIG: Dict[str, Any] = {
    "environment": "production",
    "production_hardening": True,
    "scada_mode": os.getenv("SCADA_MODE", "production"),
    "database_url": os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/etap"),
}
