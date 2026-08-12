"""
Regression tests for the prompt_loader circuit breaker adapter (C-13).

C-13: the second module-level ``def __init__`` shadowed the class
constructor and nested ``is_open``/``record_*`` inside a dead function
body, so ``_langfuse_cb.is_open`` raised ``AttributeError`` — breaking
the async prompt-loading path. These tests pin the fixed behaviour.
"""

from __future__ import annotations

from agents.prompt_loader import _CircuitBreakerAdapter, _langfuse_cb


def test_module_level_circuit_breaker_is_open_accessible() -> None:
    assert _langfuse_cb.is_open is False


def test_adapter_wraps_canonical_breaker() -> None:
    cb = _CircuitBreakerAdapter("test_cb", failure_threshold=2, recovery_timeout=1.0)
    assert cb.is_open is False


def test_breaker_opens_after_threshold_failures() -> None:
    cb = _CircuitBreakerAdapter("test_cb_open", failure_threshold=2, recovery_timeout=60.0)
    cb.record_failure()
    assert cb.is_open is False
    cb.record_failure()
    assert cb.is_open is True


def test_record_success_resets_breaker() -> None:
    cb = _CircuitBreakerAdapter("test_cb_reset", failure_threshold=1, recovery_timeout=60.0)
    cb.record_failure()
    assert cb.is_open is True
    cb.record_success()
    assert cb.is_open is False


def test_langwatch_cb_also_functional() -> None:
    from agents.prompt_loader import _langwatch_cb

    assert _langwatch_cb.is_open is False
