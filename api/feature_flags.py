"""
Feature flags for incomplete/unverified study types.
Studies behind feature flags are disabled in production/staging
and shown as 'Coming Soon' in the UI.
"""
from __future__ import annotations

import os

FEATURE_FLAGS = {
    "harmonic_analysis": {"enabled": False, "status": "beta", "description": "Harmonic analysis (IEEE 519) - in development"},
    "motor_starting": {"enabled": False, "status": "beta", "description": "Motor starting analysis (IEEE 399) - in development"},
    "transient_stability": {"enabled": False, "status": "alpha", "description": "Transient stability (swing equation) - experimental"},
    "optimal_power_flow": {"enabled": False, "status": "alpha", "description": "OPF (economic dispatch) - experimental"},
}

def is_feature_enabled(study_type: str) -> bool:
    """Check if a study type is enabled, considering environment."""
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return True
    flag = FEATURE_FLAGS.get(study_type)
    if flag is None:
        return True
    return flag["enabled"]

def get_disabled_studies() -> list[dict]:
    """Return list of disabled studies with their status for UI display."""
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return []
    return [
        {"study_type": k, "status": v["status"], "description": v["description"]}
        for k, v in FEATURE_FLAGS.items()
        if not v["enabled"]
    ]
