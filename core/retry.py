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

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
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
    reraise: bool = True,
) -> Callable:
    """Retry decorator for network / I/O operations.

    Uses exponential backoff + jitter with a cap on total attempts.

    Parameters
    ----------
    max_attempts : int
        Maximum number of retry attempts (default 3).
    max_delay : int
        Maximum wait time in seconds between retries (default 10).
    reraise : bool
        Whether to re-raise the last exception when exhausted (default True).

    Examples
    --------
    >>> @network_retry(max_attempts=5)
    ... async def fetch_data(url: str) -> bytes:
    ...     ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=max_delay) + wait_random(0, 1),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
        reraise=reraise,
    )


def skill_retry(
    max_attempts: int = 3,
    reraise: bool = True,
) -> Callable:
    """Retry decorator for skill / module loading operations.

    Uses shorter exponential backoff (0.5x multiplier) to avoid
    blocking the agent for too long.

    Parameters
    ----------
    max_attempts : int
        Maximum number of retry attempts (default 3).
    reraise : bool
        Whether to re-raise the last exception when exhausted (default True).

    Examples
    --------
    >>> @skill_retry(max_attempts=5)
    ... def load_skill_module(skill_path: str) -> object:
    ...     ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=1, max=30),
        retry=retry_if_exception_type((ImportError, ModuleNotFoundError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=reraise,
    )


def bounded_retry(
    max_attempts: int = 3,
    max_delay_seconds: float = 30.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    reraise: bool = True,
) -> Callable:
    """General-purpose bounded retry decorator.

    Stops after *either* the attempt limit is reached *or* the total
    elapsed time exceeds *max_delay_seconds* — whichever comes first.

    Parameters
    ----------
    max_attempts : int
        Maximum number of retry attempts (default 3).
    max_delay_seconds : float
        Hard time limit across all retries (default 30).
    exceptions : exception type or tuple
        Which exceptions to retry on (default ``Exception``, i.e. all).
    reraise : bool
        Whether to re-raise the last exception when exhausted (default True).

    Examples
    --------
    >>> @bounded_retry(max_attempts=5, max_delay_seconds=10.0)
    ... def query_database(query: str) -> list:
    ...     ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts) | stop_after_delay(max_delay_seconds),
        wait=wait_fixed(1) + wait_random(0, 0.5),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
        reraise=reraise,
    )
