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


class RoutingResolutionError(ValueError):
    """Raised when goal routing fails to reach an executable study type with required confidence.

    Mandated by M3.1: replaces silent or generic answers with a precise reachability error.
    """

    def __init__(
        self,
        goal: str,
        confidence: float,
        threshold: float,
        reason: str = "",
    ) -> None:
        self.goal = goal
        self.confidence = confidence
        self.threshold = threshold
        self.code = "ROUTING_RESOLUTION_FAILED"
        msg = (
            f"Routing resolution failed for goal '{goal}': confidence {confidence:.2f} "
            f"below required threshold {threshold:.2f}"
        )
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)

