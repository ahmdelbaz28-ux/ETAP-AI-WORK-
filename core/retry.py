"""
core/retry.py — Reusable retry decorators for network, skill-loading,
and general fault-tolerant operations.

Patterns drawn from Tenacity/tenacity:
- @retry decorator with configurable strategies
- Exponential backoff with jitter
- Selective retry on specific exception types
- Logging hooks for observability
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    wait_random,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-built retry decorators for common scenarios
# ---------------------------------------------------------------------------


def network_retry(
    max_attempts: int = 3,
    max_delay: int = 10,
    multiplier: float = 1.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = (ConnectionError, TimeoutError, OSError),
    reraise: bool = True,
) -> Callable:
    """Retry decorator for network / I/O operations."""
    wait_strat = wait_fixed(0) if max_delay == 0 else wait_exponential(multiplier=multiplier or 1, min=1, max=max_delay)
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_strat,
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
        reraise=reraise,
    )


def async_network_retry(
    max_attempts: int = 3,
    max_delay: int = 10,
    multiplier: float = 1.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = (ConnectionError, TimeoutError, OSError),
    reraise: bool = True,
) -> Callable:
    """Async retry decorator for network / I/O operations."""
    wait_strat = wait_fixed(0) if max_delay == 0 else wait_exponential(multiplier=multiplier or 1, min=1, max=max_delay)
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_strat,
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=reraise,
    )


def conditional_retry(
    condition_fn: Callable[[Any], bool],
    max_attempts: int = 3,
    max_delay: int = 10,
    reraise: bool = True,
) -> Callable:
    """Retry decorator that retries when condition_fn(result) returns True."""
    wait_strat = wait_fixed(0) if max_delay == 0 else wait_exponential(multiplier=1, min=1, max=max_delay)
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_strat,
        retry=retry_if_result(condition_fn) | retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=reraise,
    )


def skill_retry(
    max_attempts: int = 3,
    max_delay: int = 30,
    multiplier: float = 0.5,
    exceptions: type[Exception] | tuple[type[Exception], ...] = (ImportError, ModuleNotFoundError),
    reraise: bool = True,
) -> Callable:
    """Retry decorator for skill / module loading operations."""
    wait_strat = wait_fixed(0) if max_delay == 0 else wait_exponential(multiplier=multiplier or 1, min=1, max=max_delay)
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_strat,
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=reraise,
    )



def bounded_retry(
    max_attempts: int = 3,
    max_delay_seconds: float = 30.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    reraise: bool = True,
) -> Callable:
    """General-purpose bounded retry decorator."""
    return retry(
        stop=stop_after_attempt(max_attempts) | stop_after_delay(max_delay_seconds),
        wait=wait_fixed(1) + wait_random(0, 0.5),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
        reraise=reraise,
    )

