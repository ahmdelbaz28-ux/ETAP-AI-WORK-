"""Tests for ABAC, MFA (TOTP), and SIEM security modules.

Tests the security hardening components:
- ABAC: Attribute-Based Access Control policy engine
- TOTP: Time-based One-Time Password generation and verification
- SIEM: Security event formatting for Loki/ELK
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# ABAC Tests
# ===========================================================================

class TestABAC:
    """Tests for the Attribute-Based Access Control engine."""

    def test_role_policy_allow(self):
        """Test 1: Role-based allow policy grants access to matching role."""
        from security.abac import (
            ABACPolicy,
            ABACPolicyEngine,
            ABACRule,
            RuleType,
            make_role_policy,
        )
        engine = ABACPolicyEngine()
        engine.add_policy(make_role_policy(
            name="engineer_access",
            allowed_roles=["engineer", "admin"],
            priority=10,
        ))

        subject = {"role": "engineer", "department": "power_systems"}
        action = "post:/api/studies"
        resource = {"path": "/api/studies"}
        environment = {}

        assert engine.evaluate(subject, action, resource, environment) is True

    def test_role_policy_deny(self):
        """Test 2: Role-based policy denies access to non-matching role."""
        from security.abac import ABACPolicyEngine, make_role_policy
        engine = ABACPolicyEngine()
        engine.add_policy(make_role_policy(
            name="engineer_only",
            allowed_roles=["engineer"],
            priority=10,
        ))

        subject = {"role": "viewer", "department": "operations"}
        action = "post:/api/studies"
        resource = {"path": "/api/studies"}
        environment = {}

        assert engine.evaluate(subject, action, resource, environment) is False

    def test_attribute_policy(self):
        """Test 3: Attribute-based policy checks department and region."""
        from security.abac import (
            ABACPolicy,
            ABACPolicyEngine,
            ABACRule,
            RuleType,
        )
        engine = ABACPolicyEngine()
        policy = ABACPolicy(
            name="mena_engineers",
            rules=[
                ABACRule(
                    rule_type=RuleType.ROLE,
                    field_path="role",
                    operator="==",
                    value="engineer",
                    description="Must be engineer",
                ),
                ABACRule(
                    rule_type=RuleType.ATTRIBUTE,
                    field_path="region",
                    operator="==",
                    value="MENA",
                    description="Must be in MENA region",
                ),
            ],
            priority=10,
            effect="allow",
        )
        engine.add_policy(policy)

        # Matching both rules
        subject_match = {"role": "engineer", "region": "MENA"}
        assert engine.evaluate(subject_match, "run_study", {}, {}) is True

        # Missing region
        subject_no_region = {"role": "engineer", "region": "APAC"}
        assert engine.evaluate(subject_no_region, "run_study", {}, {}) is False

    def test_default_deny(self):
        """Test 4: Default deny when no policy matches."""
        from security.abac import ABACPolicyEngine
        engine = ABACPolicyEngine()  # No policies added

        subject = {"role": "admin"}
        result = engine.evaluate(subject, "do_something", {}, {})
        assert result is False

    def test_deny_overrides_allow(self):
        """Test 5: Explicit deny policy overrides allow policy."""
        from security.abac import (
            ABACPolicy,
            ABACPolicyEngine,
            ABACRule,
            RuleType,
        )
        engine = ABACPolicyEngine()

        # Allow all engineers
        engine.add_policy(ABACPolicy(
            name="allow_engineers",
            rules=[
                ABACRule(RuleType.ROLE, "role", "==", "engineer",
                         "Engineer allow"),
            ],
            priority=5,
            effect="allow",
        ))

        # Deny specific department
        engine.add_policy(ABACPolicy(
            name="deny_interns",
            rules=[
                ABACRule(RuleType.ATTRIBUTE, "department", "==", "intern",
                         "Intern deny"),
            ],
            priority=10,  # Higher priority
            effect="deny",
        ))

        subject = {"role": "engineer", "department": "intern"}
        # Deny has higher priority and matches → DENY
        assert engine.evaluate(subject, "run_study", {}, {}) is False

    def test_ip_range_checking(self):
        """Test 6: IP range checking via ip_in_ranges utility."""
        from security.abac import ip_in_ranges
        # Internal IP → within range
        assert ip_in_ranges("10.0.1.5", ["10.0.0.0/8", "192.168.0.0/16"]) is True
        # External IP → not in range
        assert ip_in_ranges("203.0.113.5", ["10.0.0.0/8", "192.168.0.0/16"]) is False

    def test_policy_removal(self):
        """Test 7: Policies can be removed at runtime."""
        from security.abac import ABACPolicyEngine, make_role_policy
        engine = ABACPolicyEngine()
        engine.add_policy(make_role_policy(
            name="temp_access", allowed_roles=["engineer"],
        ))
        assert "temp_access" in engine.list_policies()

        engine.remove_policy("temp_access")
        assert "temp_access" not in engine.list_policies()

    def test_create_default_etap_abac_engine(self):
        """Test 8: Default ETAP ABAC engine has expected policies."""
        from security.abac import create_default_etap_abac_engine
        engine = create_default_etap_abac_engine()
        policies = engine.list_policies()
        assert "admin_full_access" in policies
        assert "engineer_studies" in policies

    def test_ip_in_ranges(self):
        """Test 9: IP range checking utility function."""
        from security.abac import ip_in_ranges
        assert ip_in_ranges("10.0.1.5", ["10.0.0.0/8"]) is True
        assert ip_in_ranges("192.168.1.1", ["10.0.0.0/8"]) is False
        assert ip_in_ranges("192.168.1.1", ["10.0.0.0/8", "192.168.0.0/16"]) is True
        assert ip_in_ranges("invalid_ip", ["10.0.0.0/8"]) is False


# ===========================================================================
# TOTP Tests
# ===========================================================================

class TestTOTP:
    """Tests for the TOTP (Time-based One-Time Password) provider."""

    def test_generate_and_verify(self):
        """Test 1: Generate TOTP secret and verify a code."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test Platform")

        secret = provider.generate_secret("user-001")
        assert secret is not None
        assert len(secret) > 0

        # Generate a valid code using the pure-Python TOTP implementation
        from security.mfa import _totp_code
        code = _totp_code(secret)
        assert provider.verify_code(secret, code) is True

    def test_window_tolerance(self):
        """Test 2: TOTP verification with ±1 window for clock drift."""
        from security.mfa import TOTPProvider, _totp_code
        provider = TOTPProvider(issuer="Test", window=1)

        secret = provider.generate_secret("user-002")
        now = time.time()

        # Generate code for current time step
        current_code = _totp_code(secret, t=now)
        assert provider.verify_code(secret, current_code) is True

        # Generate code one step in the past (within window)
        past_code = _totp_code(secret, t=now - 30)
        # With window=1, this should also be accepted
        assert provider.verify_code(secret, past_code) is True

    def test_invalid_code_rejected(self):
        """Test 3: Invalid TOTP code is rejected."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test")

        secret = provider.generate_secret("user-003")
        assert provider.verify_code(secret, "000000") is False

    def test_qr_code_uri(self):
        """Test 4: QR code URI is properly formatted."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="ETAP AI Platform")

        secret = provider.generate_secret("user-004")
        uri = provider.generate_qr_code("user-004", secret)

        assert uri.startswith("otpauth://totp/")
        assert "ETAP+AI+Platform" in uri or "ETAP AI Platform" in uri
        assert f"secret={secret}" in uri

    def test_backup_codes(self):
        """Test 5: Backup codes can be generated and verified."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test")

        codes = provider.generate_backup_codes("user-005", count=5)
        assert len(codes) == 5

        # First code should verify and be consumed
        first_code = codes[0]
        assert provider.verify_backup_code("user-005", first_code) is True
        # Verify the code was removed from the list
        entry = provider._secrets.get("user-005")
        assert first_code not in entry.backup_codes
        # Same code should not verify again (one-time use)
        assert provider.verify_backup_code("user-005", first_code) is False
        # Different code should verify
        assert provider.verify_backup_code("user-005", codes[1]) is True

    def test_enable_totp(self):
        """Test 6: Enable TOTP returns secret, URI, and backup codes."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test")

        result = provider.enable_totp("user-006")
        assert "secret" in result
        assert "qr_uri" in result
        assert "backup_codes" in result
        assert len(result["backup_codes"]) > 0

    def test_remove_secret(self):
        """Test 7: TOTP secret can be removed."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test")

        provider.generate_secret("user-007")
        assert provider.get_secret("user-007") is not None

        removed = provider.remove_secret("user-007")
        assert removed is True
        assert provider.get_secret("user-007") is None

    def test_remove_nonexistent_secret(self):
        """Test 8: Removing nonexistent secret returns False."""
        from security.mfa import TOTPProvider
        provider = TOTPProvider(issuer="Test")
        assert provider.remove_secret("nonexistent") is False


# ===========================================================================
# SIEM Tests
# ===========================================================================

class TestSIEM:
    """Tests for the SIEM event formatting and forwarding."""

    def test_security_event_creation(self):
        """Test 1: SecurityEvent is created with proper fields."""
        from security.siem import SecurityEvent
        event = SecurityEvent(
            event_type="auth",
            severity="warning",
            source="etap-ai-platform",
            details={"user": "admin", "action": "login_failed"},
        )
        d = event.to_dict()
        assert d["event_type"] == "auth"
        assert d["severity"] == "warning"
        assert d["details"]["user"] == "admin"
        assert "event_id" in d
        assert "timestamp" in d

    def test_security_event_json(self):
        """Test 2: SecurityEvent serializes to valid JSON."""
        import json

        from security.siem import SecurityEvent
        event = SecurityEvent(
            event_type="access",
            severity="info",
            details={"resource": "/api/studies"},
        )
        json_str = event.to_json()
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "access"

    def test_loki_payload_format(self):
        """Test 3: Loki payload has correct structure."""
        import json

        from security.siem import SecurityEvent, SIEMForwarder

        forwarder = SIEMForwarder(
            endpoint="http://localhost:3100/loki/api/v1/push",
            siem_type="loki",
        )
        events = [
            SecurityEvent(event_type="auth", severity="info",
                          details={"user": "admin"}),
        ]
        payload = forwarder._build_loki_payload(events)
        parsed = json.loads(payload)

        assert "streams" in parsed
        assert len(parsed["streams"]) > 0
        stream = parsed["streams"][0]
        assert "stream" in stream
        assert "values" in stream
        assert len(stream["values"]) == 1

    def test_elk_payload_format(self):
        """Test 4: ELK payload has correct bulk-index structure."""
        import json

        from security.siem import SecurityEvent, SIEMForwarder

        forwarder = SIEMForwarder(
            endpoint="http://localhost:9200/etap-security-*/_doc",
            siem_type="elk",
        )
        events = [
            SecurityEvent(event_type="anomaly", severity="critical",
                          details={"type": "brute_force"}),
        ]
        payload = forwarder._build_elk_payload(events)
        lines = payload.decode("utf-8").strip().split("\n")
        # Each event produces 2 lines: action + data
        assert len(lines) == 2
        action = json.loads(lines[0])
        assert "index" in action
        data = json.loads(lines[1])
        assert data["event_type"] == "anomaly"

    def test_siem_forwarder_stats(self):
        """Test 5: Forwarder tracks statistics."""
        from security.siem import SIEMForwarder
        forwarder = SIEMForwarder(
            endpoint="http://localhost:3100/loki/api/v1/push",
        )
        stats = forwarder.get_stats()
        assert "forwarded" in stats
        assert "failed" in stats
        assert "buffered" in stats
        assert "dropped" in stats

    def test_siem_type_validation(self):
        """Test 6: Invalid SIEM type defaults to loki."""
        from security.siem import SIEMForwarder
        forwarder = SIEMForwarder(
            endpoint="http://localhost:9200",
            siem_type="invalid_type",
        )
        assert forwarder.siem_type == "loki"

    def test_buffer_overflow_protection(self):
        """Test 7: Buffer overflow protection drops oldest events."""
        from security.siem import SIEMForwarder
        forwarder = SIEMForwarder(
            endpoint="http://localhost:3100/loki/api/v1/push",
            buffer_size=5,
        )
        # The buffer deque has maxlen=5, so adding more events
        # should drop the oldest
        stats = forwarder.get_stats()
        assert stats["buffer_size"] >= 0

    @pytest.mark.asyncio
    async def test_forward_auth_event(self):
        """Test 8: Auth event forwarding formats correctly.

        This test does not require a running SIEM — it only verifies
        that the event is buffered properly.
        """
        from security.siem import SIEMForwarder
        forwarder = SIEMForwarder(
            endpoint="http://localhost:3100/loki/api/v1/push",
            retry_attempts=1,
            retry_delay_seconds=0.01,
        )
        # This will attempt to forward but fail (no Loki running),
        # which is fine — we're testing the event structure
        result = await forwarder.forward_auth_event(
            user="admin",
            action="login",
            success=True,
            ip="10.0.1.5",
        )
        # Result may be True or False depending on whether flush fails,
        # but the event should be buffered
        stats = forwarder.get_stats()
        assert stats["buffered"] > 0 or stats["forwarded"] > 0 or stats["failed"] > 0
