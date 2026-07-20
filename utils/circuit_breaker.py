"""
Reusable circuit breaker pattern for external service calls.
Used by ETAP Remote provider, LLM clients, and any other
network-dependent integration.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("utils.circuit_breaker")


class CircuitBreaker:
    """Circuit breaker for external service calls.

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (probing)

    Usage::
        cb = CircuitBreaker(name="OpenAI", threshold=5, reset_seconds=300)
        with cb:
            result = await openai_client.chat(...)
    """

    def __init__(
        self,
        name: str = "unknown",
        threshold: int = 5,
        reset_seconds: int = 300,
    ):
        self.name = name
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._consecutive_failures < self.threshold:
            return False
        if time.time() < self._circuit_open_until:
            return True
        logger.info("Circuit breaker %s transitioning to HALF_OPEN", self.name)
        return False

    @property
    def state(self) -> str:
        if self._consecutive_failures == 0:
            return "closed"
        if self._consecutive_failures < self.threshold:
            return "closed_with_warnings"
        if time.time() < self._circuit_open_until:
            return "open"
        return "half_open"

    def record_success(self) -> None:
        if self._consecutive_failures > 0:
            logger.info("Circuit breaker %s reset to CLOSED after success", self.name)
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.threshold:
            self._circuit_open_until = time.time() + self.reset_seconds
            logger.warning(
                "Circuit breaker %s OPEN after %d consecutive failures. "
                "Will retry after %d seconds.",
                self.name, self._consecutive_failures, self.reset_seconds,
            )

    def __enter__(self) -> "CircuitBreaker":
        if self.is_open:
            remaining = int(self._circuit_open_until - time.time())
            raise CircuitBreakerOpenError(
                f"{self.name} circuit breaker is OPEN. "
                f"Retry after {remaining}s ({self._consecutive_failures} failures)."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and exc_type is not CircuitBreakerOpenError:
            self.record_failure()
        else:
            self.record_success()


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open."""


# Module-level registry of circuit breakers
_registry: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, threshold: int = 5, reset_seconds: int = 300) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _registry:
        _registry[name] = CircuitBreaker(name=name, threshold=threshold, reset_seconds=reset_seconds)
    return _registry[name]

def circuit_breaker_status() -> dict[str, Any]:
    """Return status of all registered circuit breakers."""
    return {
        name: {
            "state": cb.state,
            "consecutive_failures": cb._consecutive_failures,
            "threshold": cb.threshold,
            "reset_seconds": cb.reset_seconds,
        }
        for name, cb in _registry.items()
    }
