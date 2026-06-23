"""
RASP Security Tests
====================
Tests for the Runtime Application Self-Protection engine.

Verifies that all attack types are BLOCKED (not just logged).

Run:
    pytest tests/test_rasp_security.py -v
"""

import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.rasp import (
    _DEFAULT_RULES,
    RASPAction,
    RASPEngine,
    RASPRule,
    RASPSeverity,
    create_default_rasp_engine,
    re,
)


class TestRASPDefaultRules:
    """Test that all default RASP rules are properly configured."""

    def test_default_rules_exist(self):
        """Verify that all 7 default rules exist."""
        assert len(_DEFAULT_RULES) == 7, f"Expected 7 rules, got {len(_DEFAULT_RULES)}"

    def test_all_rules_block_critical_attacks(self):
        """Verify that SQLi, XSS, Cmdi, Path Traversal, NoSQL, SSRF all BLOCK."""
        block_required = [
            "sqli_basic",
            "xss_basic",
            "command_injection",
            "path_traversal",
            "ldap_injection",
            "nosql_injection",
            "ssrf_basic",
        ]
        for rule in _DEFAULT_RULES:
            if rule.name in block_required:
                assert rule.action == RASPAction.BLOCK, (
                    f"Rule '{rule.name}' must be BLOCK, got {rule.action}"
                )

    def test_nosql_injection_blocks_not_logs(self):
        """CRITICAL: NoSQL injection must BLOCK, not LOG."""
        rule = next(r for r in _DEFAULT_RULES if r.name == "nosql_injection")
        assert rule.action == RASPAction.BLOCK, (
            f"nosql_injection action must be BLOCK, got {rule.action}"
        )
        assert rule.severity in (RASPSeverity.HIGH, RASPSeverity.CRITICAL), (
            f"nosql_injection severity must be HIGH or CRITICAL, got {rule.severity}"
        )

    def test_ssrf_blocks_not_logs(self):
        """CRITICAL: SSRF must BLOCK, not LOG."""
        rule = next(r for r in _DEFAULT_RULES if r.name == "ssrf_basic")
        assert rule.action == RASPAction.BLOCK, (
            f"ssrf_basic action must be BLOCK, got {rule.action}"
        )
        assert rule.severity == RASPSeverity.CRITICAL, (
            f"ssrf_basic severity must be CRITICAL, got {rule.severity}"
        )


class TestRASPAttackDetection:
    """Test that RASP correctly detects and blocks attack patterns."""

    def setup_method(self):
        """Create a fresh RASP engine for each test."""
        self.rasp = create_default_rasp_engine()

    def test_sqli_blocked(self):
        """SQL Injection must be blocked."""
        results = self.rasp.inspect({"body": "' OR 1=1; DROP TABLE users;--"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "SQL Injection must be blocked"
        assert blocked[0].rule_name == "sqli_basic"

    def test_xss_blocked(self):
        """XSS must be blocked."""
        results = self.rasp.inspect({"body": "<script>alert(document.cookie)</script>"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "XSS must be blocked"
        assert blocked[0].rule_name == "xss_basic"

    def test_command_injection_blocked(self):
        """Command Injection must be blocked."""
        results = self.rasp.inspect({"body": "; rm -rf / | bash"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "Command Injection must be blocked"
        assert blocked[0].rule_name == "command_injection"

    def test_path_traversal_blocked(self):
        """Path Traversal must be blocked."""
        results = self.rasp.inspect({"path": "/../../../etc/passwd"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "Path Traversal must be blocked"
        assert blocked[0].rule_name == "path_traversal"

    def test_nosql_injection_blocked(self):
        """NoSQL Injection must be BLOCKED (not just logged)."""
        results = self.rasp.inspect({"body": '{"$where": "1=1"}'})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "NoSQL Injection must be BLOCKED"
        assert blocked[0].rule_name == "nosql_injection"

    def test_ssrf_aws_metadata_blocked(self):
        """SSRF to AWS metadata endpoint must be BLOCKED."""
        results = self.rasp.inspect({"body": "http://169.254.169.254/latest/meta-data/"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "SSRF to AWS metadata must be BLOCKED"
        assert blocked[0].rule_name == "ssrf_basic"

    def test_ssrf_localhost_blocked(self):
        """SSRF to localhost must be BLOCKED."""
        results = self.rasp.inspect({"body": "http://localhost:8080/admin"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "SSRF to localhost must be BLOCKED"

    def test_ssrf_internal_ip_blocked(self):
        """SSRF to internal IP must be BLOCKED."""
        results = self.rasp.inspect({"body": "http://10.0.0.1/internal-api"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "SSRF to internal IP must be BLOCKED"

    def test_ssrf_file_protocol_blocked(self):
        """SSRF using file:// protocol must be BLOCKED."""
        results = self.rasp.inspect({"body": "file:///etc/passwd"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "SSRF file:// must be BLOCKED"

    def test_ldap_injection_blocked(self):
        """LDAP Injection must be blocked."""
        results = self.rasp.inspect({"body": "*)(&(objectClass=*))"})
        blocked = [r for r in results if r.action == RASPAction.BLOCK]
        assert len(blocked) > 0, "LDAP Injection must be blocked"


class TestRASPStatistics:
    """Test RASP statistics tracking."""

    def test_stats_track_blocked_attacks(self):
        """Verify that blocked attacks are tracked in stats."""
        rasp = create_default_rasp_engine()
        # Send a realistic SQLi attack that matches the sqli_basic pattern
        rasp.inspect({"body": "'; DROP TABLE users;--"})
        stats = rasp.get_stats()
        assert stats["total_inspections"] == 1
        assert stats["attacks_blocked"] > 0

    def test_stats_track_clean_requests(self):
        """Verify that clean requests don't increment attack counters."""
        rasp = create_default_rasp_engine()
        rasp.inspect({"body": "normal engineering data", "path": "/api/v1/studies/run"})
        stats = rasp.get_stats()
        assert stats["attacks_detected"] == 0

    def test_rasp_can_be_disabled(self):
        """Verify that RASP can be disabled at runtime."""
        rasp = create_default_rasp_engine()
        assert rasp.enabled is True
        rasp.enabled = False
        results = rasp.inspect({"body": "' OR 1=1;--"})
        assert len(results) == 0, "RASP should return no results when disabled"


class TestRASPCustomRules:
    """Test adding and removing custom RASP rules."""

    def test_add_custom_rule(self):
        """Verify custom rules can be added."""
        rasp = create_default_rasp_engine()
        initial_count = len(rasp._rules)
        rasp.add_rule(
            RASPRule(
                name="custom_test_rule",
                pattern=re.compile(r"CUSTOM_ATTACK_PATTERN"),
                action=RASPAction.BLOCK,
                severity=RASPSeverity.HIGH,
            )
        )
        assert len(rasp._rules) == initial_count + 1

    def test_remove_custom_rule(self):
        """Verify custom rules can be removed."""
        rasp = create_default_rasp_engine()
        rasp.add_rule(
            RASPRule(
                name="custom_test_rule",
                pattern=re.compile(r"CUSTOM_ATTACK_PATTERN"),
                action=RASPAction.BLOCK,
            )
        )
        removed = rasp.remove_rule("custom_test_rule")
        assert removed is True

    def test_remove_nonexistent_rule(self):
        """Verify removing a non-existent rule returns False."""
        rasp = create_default_rasp_engine()
        removed = rasp.remove_rule("nonexistent_rule")
        assert removed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
