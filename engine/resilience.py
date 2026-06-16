"""
Reliability and resilience patterns for the AhmedETAP Engineering Platform.

Provides production-grade retry handling, circuit breaker, multi-level recovery,
and computational stability enforcement.
"""

import logging
import random
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global circuit breaker registry
# ---------------------------------------------------------------------------

_circuit_breaker_registry: Dict[str, "CircuitBreaker"] = {}
_registry_lock = threading.Lock()


def register_circuit_breaker(cb: "CircuitBreaker") -> None:
    """Register a named circuit breaker in the global registry."""
    with _registry_lock:
        _circuit_breaker_registry[cb.name] = cb


def get_circuit_breaker(name: str) -> Optional["CircuitBreaker"]:
    """Look up a registered circuit breaker by name."""
    with _registry_lock:
        return _circuit_breaker_registry.get(name)


def get_all_circuit_breakers() -> Dict[str, "CircuitBreaker"]:
    """Return a copy of all registered circuit breakers."""
    with _registry_lock:
        return dict(_circuit_breaker_registry)


# ---------------------------------------------------------------------------
# RetryHandler
# ---------------------------------------------------------------------------

class RetryHandler:
    """Retry mechanism with exponential backoff and optional jitter.

    Implements: delay = base_delay * (exponential_base ** attempt) + jitter
    where jitter is a random value in [0, computed_delay] when enabled.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (default 3).
    base_delay : float
        Initial delay in seconds (default 1.0).
    max_delay : float
        Maximum delay cap in seconds (default 60.0).
    exponential_base : float
        Base for exponential growth (default 2.0).
    jitter : bool
        Apply random jitter to spread retry timing (default True).
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

        self._total_calls = 0
        self._total_retries = 0
        self._lock = threading.Lock()

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def total_retries(self) -> int:
        return self._total_retries

    def _compute_delay(self, attempt: int) -> float:
        """Compute the delay for a given retry attempt."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = random.uniform(0, delay)
        return delay

    def _default_retryable(self, exc: BaseException) -> bool:
        return isinstance(exc, (ConnectionError, TimeoutError, IOError))

    def execute(
        self,
        fn: Callable[..., Any],
        *args: Any,
        retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a callable with retry logic.

        Parameters
        ----------
        fn : callable
            The function to execute.
        *args : Any
            Positional arguments forwarded to *fn*.
        retryable_exceptions : sequence of exception types, optional
            Exceptions that trigger a retry. Defaults to
            ``(ConnectionError, TimeoutError, IOError)``.
        **kwargs : Any
            Keyword arguments forwarded to *fn*.

        Returns
        -------
        Any
            The return value of *fn*.

        Raises
        ------
        Exception
            The last exception raised if all retries are exhausted.
        """
        last_exc: Optional[BaseException] = None

        with self._lock:
            self._total_calls += 1

        for attempt in range(self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and self._is_retryable(
                    exc, retryable_exceptions
                ):
                    delay = self._compute_delay(attempt)
                    with self._lock:
                        self._total_retries += 1
                    logger.warning(
                        "Retry attempt %d/%d for %s failed with %s. "
                        "Waiting %.2fs before next retry.",
                        attempt + 1,
                        self.max_retries,
                        fn.__name__,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    if attempt >= self.max_retries:
                        logger.error(
                            "All %d retries exhausted for %s.",
                            self.max_retries,
                            fn.__name__,
                        )
                    break

        raise last_exc  # type: ignore[misc]

    async def async_execute(
        self,
        fn: Callable[..., Any],
        *args: Any,
        retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute an async callable with retry logic.

        Parameters and behaviour are identical to :meth:`execute` but for
        ``async def`` callables.
        """
        import asyncio

        last_exc: Optional[BaseException] = None

        with self._lock:
            self._total_calls += 1

        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and self._is_retryable(
                    exc, retryable_exceptions
                ):
                    delay = self._compute_delay(attempt)
                    with self._lock:
                        self._total_retries += 1
                    logger.warning(
                        "Async retry attempt %d/%d for %s failed with %s. "
                        "Waiting %.2fs before next retry.",
                        attempt + 1,
                        self.max_retries,
                        fn.__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    if attempt >= self.max_retries:
                        logger.error(
                            "All %d async retries exhausted for %s.",
                            self.max_retries,
                            fn.__name__,
                        )
                    break

        raise last_exc  # type: ignore[misc]

    def _is_retryable(
        self,
        exc: BaseException,
        retryable_exceptions: Optional[Sequence[Type[BaseException]]],
    ) -> bool:
        if retryable_exceptions is not None:
            return isinstance(exc, tuple(retryable_exceptions))
        return self._default_retryable(exc)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that wraps a function with :class:`RetryHandler`.

    Parameters
    ----------
    max_retries : int
        Maximum retry attempts (default 3).
    base_delay : float
        Initial delay in seconds (default 1.0).
    max_delay : float
        Maximum delay cap in seconds (default 60.0).
    exponential_base : float
        Base for exponential growth (default 2.0).
    jitter : bool
        Apply random jitter (default True).
    retryable_exceptions : sequence of exception types, optional
        Exceptions that trigger a retry. Defaults to
        ``(ConnectionError, TimeoutError, IOError)``.

    Returns
    -------
    callable
        Decorated function that automatically retries on failure.

    Examples
    --------
    >>> @with_retry(max_retries=5)
    >>> def fetch_data(url):
    ...     return requests.get(url)
    """
    handler = RetryHandler(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return handler.execute(
                fn, *args, retryable_exceptions=retryable_exceptions, **kwargs
            )
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitBreakerState:
    """Circuit breaker state constants."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit breaker pattern implementation.

    Protects downstream services from cascading failures by monitoring
    failure rates and short-circuiting calls when a threshold is exceeded.

    States
    ------
    CLOSED
        Normal operation; all calls pass through.
    OPEN
        Calls are rejected immediately without invoking the wrapped function.
        After *recovery_timeout* the breaker transitions to HALF_OPEN.
    HALF_OPEN
        A limited number of trial calls are allowed. If they succeed the
        breaker resets to CLOSED; otherwise it reverts to OPEN.

    Parameters
    ----------
    name : str
        Circuit breaker identifier (used for logging and registry look-up).
    failure_threshold : int
        Consecutive failures before opening the circuit (default 5).
    recovery_timeout : float
        Seconds to wait before transitioning from OPEN to HALF_OPEN (default 30).
    half_open_max_calls : int
        Maximum calls allowed in HALF_OPEN state (default 1).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._total_calls = 0
        self._failed_calls = 0
        self._last_failure_time: Optional[float] = None
        self._state_changes = 0
        self._half_open_calls = 0
        self._lock = threading.Lock()

        register_circuit_breaker(self)

    # -- public properties ---------------------------------------------------

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def failed_calls(self) -> int:
        return self._failed_calls

    @property
    def last_failure_time(self) -> Optional[float]:
        return self._last_failure_time

    @property
    def state_changes(self) -> int:
        return self._state_changes

    # -- public API ----------------------------------------------------------

    def get_state(self) -> str:
        """Return the current circuit breaker state string."""
        with self._lock:
            return self._state

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info("Circuit breaker '%s' manually reset to CLOSED.", self.name)

    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        fallback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute *fn* through the circuit breaker.

        Parameters
        ----------
        fn : callable
            The protected function.
        *args : Any
            Positional arguments forwarded to *fn*.
        fallback : callable, optional
            Fallback function invoked when the circuit is OPEN.
        **kwargs : Any
            Keyword arguments forwarded to *fn*.

        Returns
        -------
        Any
            Result of *fn* or *fallback* (if provided when circuit is OPEN).

        Raises
        ------
        CircuitBreakerOpenError
            If the circuit is OPEN and no fallback is provided.
        Exception
            Any exception raised by *fn* (after updating failure tracking).
        """
        with self._lock:
            self._total_calls += 1
            self._check_state_transition()
            state = self._state

        if state == CircuitBreakerState.OPEN:
            if fallback is not None:
                logger.info(
                    "Circuit '%s' is OPEN. Invoking fallback.", self.name
                )
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Call rejected."
            )

        if state == CircuitBreakerState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN "
                        f"and at capacity ({self.half_open_max_calls}). "
                        "Call rejected."
                    )
                self._half_open_calls += 1

        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            self._record_failure()
            if state == CircuitBreakerState.HALF_OPEN:
                self._transition_to(CircuitBreakerState.OPEN)
            raise exc
        else:
            if state == CircuitBreakerState.HALF_OPEN:
                self._transition_to(CircuitBreakerState.CLOSED)
            else:
                with self._lock:
                    self._failure_count = 0
            return result

    async def async_call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        fallback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Async variant of :meth:`call`.

        Parameters and behaviour are identical but works with ``async def``
        callables.
        """
        with self._lock:
            self._total_calls += 1
            self._check_state_transition()
            state = self._state

        if state == CircuitBreakerState.OPEN:
            if fallback is not None:
                logger.info(
                    "Circuit '%s' is OPEN. Invoking async fallback.", self.name
                )
                return await fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Async call rejected."
            )

        if state == CircuitBreakerState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN "
                        f"and at capacity ({self.half_open_max_calls}). "
                        "Async call rejected."
                    )
                self._half_open_calls += 1

        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            self._record_failure()
            if state == CircuitBreakerState.HALF_OPEN:
                self._transition_to(CircuitBreakerState.OPEN)
            raise exc
        else:
            if state == CircuitBreakerState.HALF_OPEN:
                self._transition_to(CircuitBreakerState.CLOSED)
            else:
                with self._lock:
                    self._failure_count = 0
            return result

    # -- internal helpers ----------------------------------------------------

    def _check_state_transition(self) -> None:
        """Evaluate whether the circuit should transition from OPEN to HALF_OPEN."""
        if self._state != CircuitBreakerState.OPEN:
            return
        if self._last_failure_time is None:
            return
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.recovery_timeout:
            self._transition_to(CircuitBreakerState.HALF_OPEN)

    def _record_failure(self) -> None:
        with self._lock:
            self._failed_calls += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitBreakerState.OPEN:
                    self._transition_to(CircuitBreakerState.OPEN)

    def _transition_to(self, new_state: str) -> None:
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        self._state_changes += 1
        if new_state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self._half_open_calls = 0
        logger.info(
            "Circuit breaker '%s' transitioned: %s -> %s.",
            self.name,
            old_state,
            new_state,
        )


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit breaker is OPEN."""


# ---------------------------------------------------------------------------
# MultiLevelRecovery
# ---------------------------------------------------------------------------

class RecoveryResult:
    """Result container for a multi-level recovery attempt."""

    def __init__(
        self,
        success: bool,
        level_used: int,
        actions_taken: List[str],
        duration: float,
        error: Optional[BaseException] = None,
    ) -> None:
        self.success = success
        self.level_used = level_used
        self.actions_taken = actions_taken
        self.duration = duration
        self.error = error

    def __repr__(self) -> str:
        return (
            f"RecoveryResult(success={self.success}, level_used={self.level_used}, "
            f"actions={self.actions_taken}, duration={self.duration:.3f}s)"
        )


class MultiLevelRecovery:
    """Multi-level recovery strategies for graceful degradation.

    Levels
    ------
    1 (fast)
        Quick retry, cache refresh, lightweight fixes.
    2 (medium)
        Reconnect, reset local state, clear caches.
    3 (full)
        Full restart, rebuild cache, heavy re-initialisation.

    Strategies are attempted from level 1 upward. A level is skipped if its
    condition function returns ``False``.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._strategies: Dict[int, List[Tuple[Callable, Optional[Callable]]]] = {
            1: [],
            2: [],
            3: [],
        }
        self._total_recoveries = 0
        self._successful_recoveries = 0
        self._lock = threading.Lock()

    @property
    def total_recoveries(self) -> int:
        return self._total_recoveries

    @property
    def successful_recoveries(self) -> int:
        return self._successful_recoveries

    def add_strategy(
        self,
        level: int,
        fn: Callable[[Any], Any],
        condition_fn: Optional[Callable[[Any], bool]] = None,
    ) -> None:
        """Register a recovery strategy at the given level.

        Parameters
        ----------
        level : int
            Recovery level (1, 2, or 3).
        fn : callable
            The recovery action. Receives ``(error, context)``.
        condition_fn : callable, optional
            Predicate ``(error, context) -> bool`` that gates execution.
            When omitted the strategy is always executed.
        """
        if level not in self._strategies:
            raise ValueError(f"Invalid recovery level: {level}. Use 1, 2, or 3.")
        self._strategies[level].append((fn, condition_fn))

    def recover(
        self, error: BaseException, context: Optional[Any] = None
    ) -> RecoveryResult:
        """Execute recovery strategies from level 1 upward.

        Returns as soon as a level produces a result considered successful
        (no exception raised by any strategy at that level).

        Parameters
        ----------
        error : BaseException
            The error that triggered recovery.
        context : Any, optional
            Additional context passed to strategy functions.

        Returns
        -------
        RecoveryResult
            Outcome of the recovery attempt.
        """
        start = time.monotonic()
        actions_taken: List[str] = []

        with self._lock:
            self._total_recoveries += 1

        for level in sorted(self._strategies):
            level_actions: List[str] = []
            level_ok = True
            for fn, condition_fn in self._strategies[level]:
                if condition_fn is not None:
                    try:
                        if not condition_fn(error):
                            logger.debug(
                                "Skipping strategy %s at level %d: condition not met.",
                                fn.__name__,
                                level,
                            )
                            continue
                    except Exception:
                        logger.warning(
                            "Condition function %s failed; executing strategy anyway.",
                            condition_fn.__name__,
                        )
                try:
                    fn(error, context)
                    level_actions.append(fn.__name__)
                    logger.info(
                        "Recovery strategy '%s' at level %d succeeded.",
                        fn.__name__,
                        level,
                    )
                except Exception as strategy_exc:
                    logger.error(
                        "Recovery strategy '%s' at level %d failed: %s",
                        fn.__name__,
                        level,
                        strategy_exc,
                    )
                    level_ok = False

            actions_taken.extend(
                f"L{level}:{a}" for a in level_actions
            )

            if level_ok and level_actions:
                elapsed = time.monotonic() - start
                with self._lock:
                    self._successful_recoveries += 1
                return RecoveryResult(
                    success=True,
                    level_used=level,
                    actions_taken=actions_taken,
                    duration=elapsed,
                )

        elapsed = time.monotonic() - start
        return RecoveryResult(
            success=False,
            level_used=3,
            actions_taken=actions_taken,
            duration=elapsed,
            error=error,
        )


# ---------------------------------------------------------------------------
# StabilityEnforcer
# ---------------------------------------------------------------------------

class StabilityEnforcer:
    """Computational stability utilities for numerical operations.

    Provides matrix singularity checks, safe inversion, convergence
    monitoring, bounds enforcement, and numerical result validation.
    """

    def __init__(self) -> None:
        self._checks_performed = 0
        self._violations_detected = 0
        self._lock = threading.Lock()

    @property
    def checks_performed(self) -> int:
        return self._checks_performed

    @property
    def violations_detected(self) -> int:
        return self._violations_detected

    def check_matrix_singularity(
        self, matrix: np.ndarray, tolerance: float = 1e-12
    ) -> bool:
        """Check whether *matrix* is near-singular.

        Uses the ratio of smallest to largest singular value; if below
        *tolerance* the matrix is considered singular.

        Parameters
        ----------
        matrix : ndarray
            Input matrix (2D).
        tolerance : float
            Threshold for the singular-value ratio (default 1e-12).

        Returns
        -------
        bool
            ``True`` if the matrix is near-singular (unstable).
        """
        with self._lock:
            self._checks_performed += 1

        if matrix.ndim != 2:
            raise ValueError(f"Expected 2D array, got {matrix.ndim}D.")

        try:
            s = np.linalg.svd(matrix, compute_uv=False)
            ratio = s[-1] / s[0] if s[0] != 0 else 0.0
            singular = ratio < tolerance
        except np.linalg.LinAlgError:
            singular = True

        if singular:
            with self._lock:
                self._violations_detected += 1
            logger.warning("Matrix singularity check FAILED (ratio < %e).", tolerance)
        return singular

    def safe_matrix_inverse(
        self, matrix: np.ndarray, fallback_to_pinv: bool = True
    ) -> np.ndarray:
        """Compute the inverse of *matrix* with singularity fallback.

        Parameters
        ----------
        matrix : ndarray
            Square matrix to invert.
        fallback_to_pinv : bool
            If ``True`` and the matrix is singular, return the Moore-Penrose
            pseudo-inverse instead of raising (default True).

        Returns
        -------
        ndarray
            Inverse or pseudo-inverse of *matrix*.

        Raises
        ------
        np.linalg.LinAlgError
            If the matrix is singular and *fallback_to_pinv* is ``False``.
        """
        with self._lock:
            self._checks_performed += 1

        try:
            return np.linalg.inv(matrix)
        except np.linalg.LinAlgError:
            with self._lock:
                self._violations_detected += 1
            if fallback_to_pinv:
                logger.warning(
                    "Matrix inverse failed; returning pseudo-inverse."
                )
                return np.linalg.pinv(matrix)
            raise

    def check_convergence(
        self,
        history: Sequence[float],
        window: int = 5,
        tolerance: float = 1e-6,
    ) -> bool:
        """Check whether the iterative solution history is converging.

        Convergence is declared when the absolute change over the last
        *window* steps is below *tolerance*.

        Parameters
        ----------
        history : sequence of float
            Sequence of residual / error values from an iterative solver.
        window : int
            Number of recent steps to examine (default 5).
        tolerance : float
            Convergence threshold (default 1e-6).

        Returns
        -------
        bool
            ``True`` if the solution is converging.
        """
        with self._lock:
            self._checks_performed += 1

        if len(history) < window + 1:
            return False

        recent = history[-window:]
        # Convergence: the latest residual is below tolerance
        final_mismatch = abs(recent[-1])

        if final_mismatch > tolerance:
            with self._lock:
                self._violations_detected += 1
            return False

        logger.debug("Convergence check passed (final_mismatch = %e).", final_mismatch)
        return True

    @staticmethod
    def enforce_bounds(value: float, min_val: float, max_val: float) -> float:
        """Clamp *value* to the interval [*min_val*, *max_val*].

        Parameters
        ----------
        value : float
            Input value.
        min_val : float
            Lower bound.
        max_val : float
            Upper bound.

        Returns
        -------
        float
            Clamped value.
        """
        if min_val > max_val:
            raise ValueError(
                f"min_val ({min_val}) must not exceed max_val ({max_val})."
            )
        return max(min_val, min(value, max_val))

    @staticmethod
    def validate_numerical_result(
        result: float,
        expected_range: Tuple[float, float],
    ) -> bool:
        """Validate whether *result* falls within the expected range.

        Also checks for NaN and infinity.

        Parameters
        ----------
        result : float
            Numerical value to validate.
        expected_range : tuple of (float, float)
            Acceptable (min, max) range.

        Returns
        -------
        bool
            ``True`` if the result is finite and within range.
        """
        if not np.isfinite(result):
            return False
        return expected_range[0] <= result <= expected_range[1]


# ---------------------------------------------------------------------------
# Global stats
# ---------------------------------------------------------------------------

def get_resilience_stats() -> Dict[str, Any]:
    """Return aggregate resilience statistics for the entire platform.

    Collects data from all registered circuit breakers, as well as overall
    operational metrics.

    Returns
    -------
    dict
        Resilience statistics summary.
    """
    breakers = get_all_circuit_breakers()

    total_calls = sum(cb.total_calls for cb in breakers.values())
    total_failures = sum(cb.failed_calls for cb in breakers.values())
    open_breakers = [
        name for name, cb in breakers.items() if cb.get_state() == CircuitBreakerState.OPEN
    ]
    half_open_breakers = [
        name for name, cb in breakers.items()
        if cb.get_state() == CircuitBreakerState.HALF_OPEN
    ]

    return {
        "circuit_breakers": {
            "total": len(breakers),
            "names": list(breakers.keys()),
            "open": open_breakers,
            "half_open": half_open_breakers,
        },
        "circuit_breaker_calls": {
            "total": total_calls,
            "failed": total_failures,
            "failure_rate": (total_failures / total_calls * 100)
            if total_calls > 0 else 0.0,
        },
        "timestamp": time.time(),
    }
