"""
Unit tests for api/_rate_limit.py — shared sliding-window rate limiter.

These tests exercise the RateLimiter class extracted from
api/akamai_protection.py and api/cloudflare_protection.py to eliminate
code duplication (SonarCloud new_duplicated_lines_density).
"""
from __future__ import annotations

import time

import pytest

from api._rate_limit import RateLimiter


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_requests_under_limit(self):
        """GIVEN a limiter with max=5
        WHEN 3 requests are made
        THEN all 3 are allowed.
        """
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(3):
            assert limiter.is_allowed("192.168.1.1") is True, f"Request {i+1} should be allowed"

    def test_blocks_requests_over_limit(self):
        """GIVEN a limiter with max=3
        WHEN 4 requests are made
        THEN the 4th is blocked.
        """
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is False, "4th request should be blocked"

    def test_separate_keys_are_independent(self):
        """GIVEN a limiter with max=2
        WHEN 2 requests from IP-A and 2 from IP-B are made
        THEN all 4 are allowed (each IP has its own counter).
        """
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("2.2.2.2") is True
        assert limiter.is_allowed("2.2.2.2") is True
        # Both IPs are now at limit
        assert limiter.is_allowed("1.1.1.1") is False
        assert limiter.is_allowed("2.2.2.2") is False

    def test_window_expiry_allows_new_requests(self):
        """GIVEN a limiter with max=2, window=1s
        WHEN 2 requests are made, then 1s passes, then 1 more
        THEN the new request is allowed (old entries expired).
        """
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        assert limiter.is_allowed("3.3.3.3") is True
        assert limiter.is_allowed("3.3.3.3") is True
        assert limiter.is_allowed("3.3.3.3") is False
        # Wait for window to expire
        time.sleep(1.1)
        assert limiter.is_allowed("3.3.3.3") is True, "After window expiry, request should be allowed"

    def test_reset_clears_all_entries(self):
        """GIVEN a limiter at capacity
        WHEN reset() is called
        THEN subsequent requests are allowed again.
        """
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("4.4.4.4") is True
        assert limiter.is_allowed("4.4.4.4") is False
        limiter.reset()
        assert limiter.is_allowed("4.4.4.4") is True, "After reset, request should be allowed"

    def test_default_window_is_60_seconds(self):
        """GIVEN a limiter created without window_seconds
        THEN window_seconds defaults to 60.
        """
        limiter = RateLimiter(max_requests=10)
        assert limiter.window_seconds == 60

    def test_max_requests_attribute(self):
        """GIVEN a limiter with max=42
        THEN max_requests attribute equals 42.
        """
        limiter = RateLimiter(max_requests=42, window_seconds=30)
        assert limiter.max_requests == 42
        assert limiter.window_seconds == 30

    def test_pruning_old_entries(self):
        """GIVEN a limiter with window=1s
        WHEN entries are added, window expires, then new request
        THEN old entries are pruned (store doesn't grow unbounded).
        """
        limiter = RateLimiter(max_requests=100, window_seconds=1)
        # Add some entries
        for _ in range(5):
            limiter.is_allowed("5.5.5.5")
        assert len(limiter._store["5.5.5.5"]) == 5
        # Wait for expiry
        time.sleep(1.1)
        # New request should prune old entries
        limiter.is_allowed("5.5.5.5")
        assert len(limiter._store["5.5.5.5"]) == 1, "Old entries should be pruned"

    def test_empty_key_is_handled(self):
        """GIVEN a limiter
        WHEN is_allowed is called with empty string
        THEN it works without error (empty string is a valid key).
        """
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("") is True
        assert limiter.is_allowed("") is False

    def test_concurrent_different_keys(self):
        """GIVEN a limiter with max=1
        WHEN requests from many different IPs come in
        THEN each IP gets exactly 1 allowed request.
        """
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        for i in range(100):
            ip = f"6.6.6.{i}"
            assert limiter.is_allowed(ip) is True, f"First request from {ip} should be allowed"
            assert limiter.is_allowed(ip) is False, f"Second request from {ip} should be blocked"
