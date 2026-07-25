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
    CircuitBreakerOpenError,
    CircuitBreakerState,
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
        """Compat alias: calculate open-unil timestamp from engine CB internals."""
        if self._last_failure_time is not None:
            return self._last_failure_time + self.recovery_timeout
        return 0.0

    def record_success(self) -> None:
        """Compat alias: reset circuit breaker on success."""
        self.reset()

    def record_failure(self) -> None:
        """Compat alias: record a failure via the canonical call mechanism."""
        # The canonical CB tracks failures internally via call(); this method
        # exists for backward-compat callers that manage failure tracking
        # externally (like etap_provider.py did before migration).
        with self._lock:
            self._failure_count += 1
            self._failed_calls += 1
            self._last_failure_time = __import__("time").time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                self._state_changes += 1
                logger.warning(
                    "Circuit breaker '%s' OPEN after %d consecutive failures. "
                    "Will retry after %.0f seconds.",
                    self.name,
                    self._failure_count,
                    self.recovery_timeout,
                )


def get_circuit_breaker(
    name: str,
    threshold: int = 5,
    reset_seconds: int = 300,
) -> CircuitBreaker:
    """Get or create a named circuit breaker (compat wrapper).

    Looks up an existing circuit breaker by name, or creates a new one
    using engine.resilience.CircuitBreaker with the mapped params.
    """
    existing = _canonical_get_circuit_breaker(name)
    if existing is not None:
        return existing
    # Create a new canonical CB (auto-registers itself)
    return _CanonicalCircuitBreaker(
        name=name,
        failure_threshold=threshold,
        recovery_timeout=float(reset_seconds),
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
