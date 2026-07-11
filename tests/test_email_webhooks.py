"""
test_email_webhooks.py — Unit tests for api/email_webhooks._should_forward()

Covers the 4 logical branches of the SIM103-simplified _should_forward()
function:

1. Inactive endpoint           → False (regardless of events filter)
2. Active, no events filter    → True  (accept all)
3. Active, filter matches      → True
4. Active, filter doesn't match → False

These tests were added to satisfy SonarCloud's "Coverage on New Code"
quality gate (≥ 80%) after the SIM103 refactor in PR #183. The refactor
collapsed `if X: return False; return True` into `return not (X)` —
semantically identical, but SonarCloud flagged the modified lines as
"new code" requiring test coverage.

Run:
    pytest tests/test_email_webhooks.py -v

No network, no DB, no external dependencies — pure unit tests.
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.email_webhooks import WebhookEndpoint, _should_forward

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# Module-level constants — SonarCloud S2068 (hard-coded credentials)
# accepts module constants. NOT a real secret; HMAC test fixture only.
# We use "# nosec" + "# pragma: allowlist secret" so the repo's local
# scripts/security_scan.py skips this line (it doesn't recognize NOSONAR).
_TEST_HMAC_SECRET = "x" * 32  # nosec  # pragma: allowlist secret  # NOSONAR — S2068: test fixture, not a real secret


def _make_endpoint(
    *,
    events: list[str] | None = None,
    is_active: bool = True,
) -> WebhookEndpoint:
    """Build a minimal WebhookEndpoint for testing _should_forward().

    Only the fields inspected by _should_forward() are populated
    (events, is_active). Other fields get safe defaults.
    """
    return WebhookEndpoint(
        id="ep_test_001",
        url="https://hooks.example.test/etap",
        events=events if events is not None else [],
        secret=_TEST_HMAC_SECRET,
        is_active=is_active,
        created_at="2026-07-11T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Branch 1: Inactive endpoint → always False
# ---------------------------------------------------------------------------


class TestShouldForwardInactiveEndpoint:
    """Inactive endpoints must never receive events, regardless of filter."""

    def test_inactive_endpoint_with_no_filter_returns_false(self) -> None:
        ep = _make_endpoint(events=[], is_active=False)
        assert _should_forward(ep, "email.sent") is False

    def test_inactive_endpoint_with_matching_filter_still_returns_false(self) -> None:
        """is_active check short-circuits before the events filter is evaluated."""
        ep = _make_endpoint(events=["email.sent"], is_active=False)
        assert _should_forward(ep, "email.sent") is False

    def test_inactive_endpoint_with_non_matching_filter_returns_false(self) -> None:
        ep = _make_endpoint(events=["email.bounced"], is_active=False)
        assert _should_forward(ep, "email.sent") is False


# ---------------------------------------------------------------------------
# Branch 2: Active, no events filter → True (accept all)
# ---------------------------------------------------------------------------


class TestShouldForwardActiveNoFilter:
    """An active endpoint with an empty events list accepts every event type."""

    def test_active_endpoint_empty_events_accepts_sent(self) -> None:
        ep = _make_endpoint(events=[], is_active=True)
        assert _should_forward(ep, "email.sent") is True

    def test_active_endpoint_empty_events_accepts_bounced(self) -> None:
        ep = _make_endpoint(events=[], is_active=True)
        assert _should_forward(ep, "email.bounced") is True

    def test_active_endpoint_empty_events_accepts_arbitrary_event(self) -> None:
        ep = _make_endpoint(events=[], is_active=True)
        assert _should_forward(ep, "custom.event.type") is True


# ---------------------------------------------------------------------------
# Branch 3: Active, filter matches → True
# ---------------------------------------------------------------------------


class TestShouldForwardActiveFilterMatches:
    """When the event_type is in the endpoint's events list, forward it."""

    def test_active_endpoint_single_matching_event_returns_true(self) -> None:
        ep = _make_endpoint(events=["email.sent"], is_active=True)
        assert _should_forward(ep, "email.sent") is True

    def test_active_endpoint_multiple_events_first_match_returns_true(self) -> None:
        ep = _make_endpoint(
            events=["email.sent", "email.delivered", "email.bounced"],
            is_active=True,
        )
        assert _should_forward(ep, "email.sent") is True

    def test_active_endpoint_multiple_events_middle_match_returns_true(self) -> None:
        ep = _make_endpoint(
            events=["email.sent", "email.delivered", "email.bounced"],
            is_active=True,
        )
        assert _should_forward(ep, "email.delivered") is True

    def test_active_endpoint_multiple_events_last_match_returns_true(self) -> None:
        ep = _make_endpoint(
            events=["email.sent", "email.delivered", "email.bounced"],
            is_active=True,
        )
        assert _should_forward(ep, "email.bounced") is True


# ---------------------------------------------------------------------------
# Branch 4: Active, filter doesn't match → False
# ---------------------------------------------------------------------------


class TestShouldForwardActiveFilterNoMatch:
    """When the event_type is NOT in the endpoint's events list, skip it."""

    def test_active_endpoint_non_matching_event_returns_false(self) -> None:
        ep = _make_endpoint(events=["email.bounced"], is_active=True)
        assert _should_forward(ep, "email.sent") is False

    def test_active_endpoint_partial_name_does_not_match_returns_false(self) -> None:
        """Substring matches must not be treated as a match — exact only."""
        ep = _make_endpoint(events=["email.sent"], is_active=True)
        assert _should_forward(ep, "email") is False
        assert _should_forward(ep, "sent") is False
        assert _should_forward(ep, "email.sent.delivered") is False

    def test_active_endpoint_case_sensitive_no_match_returns_false(self) -> None:
        """Event filtering is case-sensitive (no .lower() normalization)."""
        ep = _make_endpoint(events=["email.sent"], is_active=True)
        assert _should_forward(ep, "EMAIL.SENT") is False
        assert _should_forward(ep, "Email.Sent") is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestShouldForwardEdgeCases:
    """Edge cases that could trip up a naive implementation."""

    def test_empty_string_event_type_with_empty_filter_returns_true(self) -> None:
        """Empty events list = accept all, even an empty event_type string."""
        ep = _make_endpoint(events=[], is_active=True)
        assert _should_forward(ep, "") is True

    def test_empty_string_event_type_with_non_empty_filter_returns_false(self) -> None:
        ep = _make_endpoint(events=["email.sent"], is_active=True)
        assert _should_forward(ep, "") is False

    def test_default_is_active_is_true(self) -> None:
        """Verify the WebhookEndpoint default is_active=True (used elsewhere)."""
        ep = WebhookEndpoint(
            id="ep_default",
            url="https://hooks.example.test",
            events=[],
            secret=_TEST_HMAC_SECRET,
        )
        assert ep.is_active is True
        assert _should_forward(ep, "email.sent") is True


# ---------------------------------------------------------------------------
# Truth-table coverage summary (documents the SIM103 equivalence)
# ---------------------------------------------------------------------------
#
# The SIM103 refactor replaced:
#     if ep.events and event_type not in ep.events:
#         return False
#     return True
#
# with:
#     return not (ep.events and event_type not in ep.events)
#
# Truth table for the inner expression `ep.events and event_type not in ep.events`:
#
#   | ep.events | event_type in ep.events | (ep.events AND not in) | not (...) |
#   |:---------:|:----------------------:|:----------------------:|:---------:|
#   | []        | (n/a — empty)          | False (empty seq)      | True      |
#   | ["x"]     | True                   | False                  | True      |
#   | ["x"]     | False                  | True                   | False     |
#
# Combined with the short-circuit `if not ep.is_active: return False` guard,
# this is logically equivalent to the pre-refactor implementation.
# ---------------------------------------------------------------------------
