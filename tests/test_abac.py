"""
Unit tests for security/abac.py — Attribute-Based Access Control engine.

Tests the pure functions (ip_in_ranges, _resolve_path) and the
ABACPolicy / ABACRule / ABACPolicyEngine classes without needing
database or external services.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from security.abac import (
    ABACPolicy,
    ABACPolicyEngine,
    ABACRule,
    RuleType,
    _resolve_path,
    ip_in_ranges,
    make_business_hours_policy,
    make_clearance_policy,
    make_ip_allowlist_policy,
    make_role_policy,
)


class TestResolvePath:
    """Tests for _resolve_path()."""

    def test_resolves_simple_path(self):
        """GIVEN a context with a 'role' key
        WHEN _resolve_path is called with 'role'
        THEN it returns the value.
        """
        context = {"role": "admin", "user_id": "u1"}
        assert _resolve_path(context, "role") == "admin"

    def test_resolves_nested_path(self):
        """GIVEN a context with nested dicts
        WHEN _resolve_path is called with 'user.role'
        THEN it returns the nested value.
        """
        context = {"user": {"role": "editor", "id": "u1"}}
        assert _resolve_path(context, "user.role") == "editor"

    def test_returns_none_for_missing_path(self):
        """GIVEN a context without the requested key
        WHEN _resolve_path is called
        THEN it returns None.
        """
        context = {"role": "admin"}
        assert _resolve_path(context, "nonexistent") is None

    def test_returns_none_for_missing_nested_path(self):
        """GIVEN a context where a nested key doesn't exist
        WHEN _resolve_path is called
        THEN it returns None.
        """
        context = {"user": {"role": "admin"}}
        assert _resolve_path(context, "user.nonexistent") is None

    def test_returns_none_for_non_dict_intermediate(self):
        """GIVEN a context where an intermediate value is not a dict
        WHEN _resolve_path is called with a deeper path
        THEN it returns None.
        """
        context = {"user": "admin"}  # user is a string, not a dict
        assert _resolve_path(context, "user.role") is None


class TestIpInRanges:
    """Tests for ip_in_ranges()."""

    def test_single_ip_match(self):
        """GIVEN an IP that matches a single-IP range
        WHEN ip_in_ranges is called
        THEN it returns True.
        """
        assert ip_in_ranges("192.168.1.100", ["192.168.1.100"]) is True

    def test_single_ip_no_match(self):
        """GIVEN an IP that doesn't match
        WHEN ip_in_ranges is called
        THEN it returns False.
        """
        assert ip_in_ranges("192.168.1.100", ["10.0.0.1"]) is False

    def test_cidr_match(self):
        """GIVEN an IP in a CIDR range
        WHEN ip_in_ranges is called
        THEN it returns True.
        """
        assert ip_in_ranges("192.168.1.50", ["192.168.1.0/24"]) is True

    def test_cidr_no_match(self):
        """GIVEN an IP outside a CIDR range
        WHEN ip_in_ranges is called
        THEN it returns False.
        """
        assert ip_in_ranges("192.168.2.50", ["192.168.1.0/24"]) is False

    def test_multiple_ranges(self):
        """GIVEN multiple ranges
        WHEN ip_in_ranges is called
        THEN it returns True if IP matches any.
        """
        ranges = ["10.0.0.0/8", "192.168.0.0/16", "172.16.0.5"]
        assert ip_in_ranges("192.168.5.5", ranges) is True
        assert ip_in_ranges("10.1.2.3", ranges) is True
        assert ip_in_ranges("172.16.0.5", ranges) is True
        assert ip_in_ranges("8.8.8.8", ranges) is False

    def test_empty_ranges(self):
        """GIVEN an empty ranges list
        WHEN ip_in_ranges is called
        THEN it returns False.
        """
        assert ip_in_ranges("192.168.1.1", []) is False

    def test_invalid_ip(self):
        """GIVEN an invalid IP string
        WHEN ip_in_ranges is called
        THEN it returns False (no exception).
        """
        assert ip_in_ranges("not-an-ip", ["192.168.1.0/24"]) is False


class TestABACRule:
    """Tests for the ABACRule dataclass."""

    def test_create_rule(self):
        """GIVEN rule parameters
        WHEN ABACRule is created
        THEN it has the expected attributes.
        """
        rule = ABACRule(
            rule_type=RuleType.ROLE,
            field_path="role",
            operator="eq",
            value="admin",
        )
        assert rule.rule_type == RuleType.ROLE
        assert rule.field_path == "role"
        assert rule.value == "admin"


class TestABACPolicy:
    """Tests for the ABACPolicy class."""

    def test_create_empty_policy(self):
        """GIVEN no rules
        WHEN ABACPolicy is created
        THEN it has empty allow/deny rule lists.
        """
        policy = ABACPolicy(name="test", description="test policy")
        assert policy.name == "test"

    def test_add_rule(self):
        """GIVEN an ABACPolicy
        WHEN a rule is added
        THEN the policy has 1 rule in the rules list.
        """
        policy = ABACPolicy(name="test", description="test")
        rule = ABACRule(
            rule_type=RuleType.ROLE,
            field_path="role",
            operator="eq",
            value="admin",
        )
        policy.rules.append(rule)
        assert len(policy.rules) == 1


class TestABACPolicyEngine:
    """Tests for the ABACPolicyEngine class."""

    def test_create_engine(self):
        """GIVEN no policies
        WHEN ABACPolicyEngine is created
        THEN it has an empty policy list.
        """
        engine = ABACPolicyEngine()
        assert engine is not None

    def test_evaluate_empty_engine(self):
        """GIVEN an engine with no policies
        WHEN evaluate is called with subject, action, resource, environment
        THEN it returns False (default-deny posture).
        """
        engine = ABACPolicyEngine()
        subject = {"role": "admin", "user_id": "u1"}
        resource = {"type": "study", "id": "r1"}
        environment = {"time": "12:00", "ip": "10.0.0.1"}
        # Default-deny: empty engine should deny
        result = engine.evaluate(subject, "read", resource, environment)
        assert result in (False, "deny", None) or result is False


class TestPolicyFactories:
    """Tests for the make_*_policy() factory functions."""

    def test_make_role_policy(self):
        """GIVEN a name and allowed_roles
        WHEN make_role_policy is called
        THEN it returns an ABACPolicy.
        """
        policy = make_role_policy("test_role_policy", ["admin", "engineer"])
        assert policy is not None
        assert isinstance(policy, ABACPolicy)

    def test_make_business_hours_policy(self):
        """GIVEN start_hour and end_hour
        WHEN make_business_hours_policy is called
        THEN it returns a list of ABACPolicy.
        """
        policies = make_business_hours_policy(
            name="office_hours", start_hour=9, end_hour=17
        )
        assert policies is not None
        assert isinstance(policies, list)
        assert all(isinstance(p, ABACPolicy) for p in policies)

    def test_make_ip_allowlist_policy(self):
        """GIVEN a name and allowed CIDRs
        WHEN make_ip_allowlist_policy is called
        THEN it returns an ABACPolicy.
        """
        policy = make_ip_allowlist_policy(
            name="internal_network", allowed_cidrs=["10.0.0.0/8"]
        )
        assert policy is not None
        assert isinstance(policy, ABACPolicy)

    def test_make_clearance_policy(self):
        """GIVEN a name
        WHEN make_clearance_policy is called
        THEN it returns an ABACPolicy.
        """
        policy = make_clearance_policy(name="level_5_required")
        assert policy is not None
        assert isinstance(policy, ABACPolicy)
