"""
Property-based tests for the retry layer.

Verifies:
- Tenacity decorators compile and apply correctly
- Retry on expected exception types
- Bounded retry stops after max_attempts
- Successful calls return immediately
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.retry import bounded_retry, network_retry, skill_retry

# ---------------------------------------------------------------------------
# Unit tests — decorator composition
# ---------------------------------------------------------------------------


def test_network_retry_returns_value_on_success() -> None:
    """A function decorated with @network_retry should return the normal value."""

    @network_retry(max_attempts=3)
    def working_fn() -> str:
        return "ok"

    assert working_fn() == "ok"


def test_network_retry_raises_on_unrelated_exception() -> None:
    """@network_retry must NOT catch unrelated exceptions (e.g. ValueError)."""

    @network_retry(max_attempts=2)
    def broken_fn() -> None:
        raise ValueError("unrelated")

    with pytest.raises(ValueError):
        broken_fn()


def test_network_retry_retries_on_connection_error() -> None:
    """@network_retry MUST retry on ConnectionError (transient)."""
    call_count = 0

    @network_retry(max_attempts=3)
    def flaky_fn() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient failure")
        return "recovered"

    assert flaky_fn() == "recovered"
    assert call_count == 3


def test_skill_retry_returns_value() -> None:
    """@skill_retry should pass through a successful return."""

    @skill_retry(max_attempts=2)
    def working_fn() -> int:
        return 42

    assert working_fn() == 42


def test_skill_retry_retries_on_import_error() -> None:
    """@skill_retry MUST retry on ImportError."""
    call_count = 0

    @skill_retry(max_attempts=3)
    def flaky_import() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ImportError("module not found")
        return "loaded"

    assert flaky_import() == "loaded"
    assert call_count == 3


def test_bounded_retry_stops_after_max_attempts() -> None:
    """@bounded_retry MUST give up after ``max_attempts`` failures."""
    call_count = 0

    @bounded_retry(max_attempts=3, max_delay_seconds=30.0)
    def always_fails() -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("persistent failure")

    with pytest.raises(RuntimeError):
        always_fails()

    assert call_count == 3


def test_bounded_retry_success_on_first_try() -> None:
    """@bounded_retry must return immediately when the call succeeds."""

    @bounded_retry(max_attempts=5)
    def quick() -> str:
        return "instant"

    assert quick() == "instant"


# ---------------------------------------------------------------------------
# Property-based — retry decorators accept valid parameters
# ---------------------------------------------------------------------------


@given(
    max_attempts=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20)
def test_network_retry_accepts_valid_attempts(max_attempts: int) -> None:
    """Property: @network_retry compiles for any reasonable max_attempts."""

    @network_retry(max_attempts=max_attempts)
    def fn() -> int:
        return max_attempts

    assert fn() == max_attempts


@given(
    max_attempts=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20)
def test_skill_retry_accepts_valid_attempts(max_attempts: int) -> None:
    """Property: @skill_retry compiles for any reasonable max_attempts."""

    @skill_retry(max_attempts=max_attempts)
    def fn() -> int:
        return max_attempts

    assert fn() == max_attempts


# ---------------------------------------------------------------------------
# Parametrized — correct exception filtering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exception_cls",
    [
        ConnectionError,
        TimeoutError,
        OSError,
    ],
)
def test_network_retry_retries_on_network_exceptions(exception_cls: type) -> None:
    """@network_retry should retry on all relevant I/O exception types."""
    call_count = 0

    @network_retry(max_attempts=2)
    def flaky() -> str:
        nonlocal call_count
        call_count += 1
        raise exception_cls("transient")

    with pytest.raises(exception_cls):
        flaky()

    assert call_count == 2  # initial + 1 retry


@pytest.mark.parametrize(
    "exception_cls",
    [
        ImportError,
        ModuleNotFoundError,
    ],
)
def test_skill_retry_retries_on_load_exceptions(exception_cls: type) -> None:
    """@skill_retry should retry on module-loading exception types."""
    call_count = 0

    @skill_retry(max_attempts=2)
    def flaky() -> str:
        nonlocal call_count
        call_count += 1
        raise exception_cls("not found")

    with pytest.raises(exception_cls):
        flaky()

    assert call_count == 2
