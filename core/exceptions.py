"""
core/exceptions.py — Standardized exceptions for AhmedETAP platform.

Provides unified error definitions across the study dispatch and execution pipeline.
"""

from __future__ import annotations


class SpecializedExecutionUnavailableError(ValueError):
    """Raised when a study type is registered but no specialized execution handler is available."""

    def __init__(self, study_type: str, reason: str = ""):
        self.study_type = study_type
        self.code = "SPECIALIZED_EXECUTION_UNAVAILABLE"
        msg = f"Specialized execution unavailable for study '{study_type}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
