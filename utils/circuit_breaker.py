"""
Reusable circuit breaker pattern for external service calls.

DEPRECATED: This module has been superseded by engine.resilience.CircuitBreaker,
which is thread-safe, supports half-open probing, has a call() method with
fallback support, and uses a global registry with stats tracking.

All consumers should migrate to:
    from engine.resilience import CircuitBreaker, CircuitBreakerOpenError, get_circuit_breaker

This module now provides thin compatibility wrappers that delegate to the
canonical implementation in engine.resilience, preserving backward compatibility
for any remaining external imports while eliminating the duplicate class.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

# Import canonical implementation — this module is now a thin facade
from engine.resilience import (
    CircuitBreaker as _CanonicalCircuitBreaker,
)
from engine.resilience import (
    CircuitBreakerState,
)
from engine.resilience import (
    get_circuit_breaker as _canonical_get_circuit_breaker,
)

logger = logging.getLogger("utils.circuit_breaker")


class CircuitBreaker(_CanonicalCircuitBreaker):
    """Backward-compatible facade over engine.resilience.CircuitBreaker.

    Accepts the old parameter names (threshold, reset_seconds) and delegates
    to the canonical implementation. Will emit a DeprecationWarning guiding
    consumers to import directly from engine.resilience.
    """

    def __init__(
        self,
        name: str = "unknown",
        threshold: int = 5,
        reset_seconds: int = 300,
    ) -> None:
        warnings.warn(
            "utils.circuit_breaker.CircuitBreaker is deprecated. "
            "Import from engine.resilience instead: "
            "from engine.resilience import CircuitBreaker",
            DeprecationWarning,
            stacklevel=2,
        )
        # Map old param names → canonical param names
        super().__init__(
            name=name,
            failure_threshold=threshold,
            recovery_timeout=float(reset_seconds),
        )

    # ─── Backward-compat property aliases ────────────────────────────────

    @property
    def threshold(self) -> int:
        return self.failure_threshold

    @property
    def reset_seconds(self) -> int:
        return int(self.recovery_timeout)

    @property
    def is_open(self) -> bool:
        """Compat alias: True when state is OPEN."""
        return self.get_state() == CircuitBreakerState.OPEN

    @property
    def state(self) -> str:
        """Compat alias: returns lowercase state string."""
        return self.get_state().lower()

    @property
    def _consecutive_failures(self) -> int:
        """Compat alias for private attribute access."""
        return self._failure_count

    @property
    def _circuit_open_until(self) -> float:
        """Compat alias: calculate open-until timestamp from engine CB internals."""
        if self._last_failure_time is not None:
            return self._last_failure_time + self.recovery_timeout
        return 0.0

    # record_success() and record_failure() are now on the canonical class
    # (engine.resilience.CircuitBreaker), so no overrides needed here.


def get_circuit_breaker(
    name: str,
    threshold: int = 5,
    reset_seconds: int = 300,
) -> CircuitBreaker:
    """Get or create a named circuit breaker (compat wrapper).

    Looks up an existing circuit breaker by name, or creates a new compat
    ``CircuitBreaker`` instance (which inherits from the canonical one
    and adds param-name aliases).
    """
    existing = _canonical_get_circuit_breaker(name)
    if existing is not None:
        # Return the existing CB — it already has record_success/record_failure
        # from the canonical class, plus any compat methods if it was originally
        # created via this wrapper.
        return existing
    # Create a compat CircuitBreaker (subclass) so callers get the old
    # param aliases (threshold, reset_seconds, is_open, state).
    return CircuitBreaker(
        name=name,
        threshold=threshold,
        reset_seconds=reset_seconds,
    )


def circuit_breaker_status() -> dict[str, Any]:
    """Return status of all registered circuit breakers."""
    from engine.resilience import get_all_circuit_breakers

    all_cbs = get_all_circuit_breakers()
    return {
        name: {
            "state": cb.get_state(),
            "failure_count": cb._failure_count,
            "failure_threshold": cb.failure_threshold,
            "recovery_timeout": cb.recovery_timeout,
        }
        for name, cb in all_cbs.items()
    }
