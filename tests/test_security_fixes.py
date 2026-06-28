"""
Targeted regression tests for the 8-file security audit remediation.

Coverage:
 1. docker-compose.yml: all secrets required, no hardcoded passwords
 2. api/auth.py:     reset_token not leaked + blocklist expanded + composite indexes
 3. api/routes.py:   AUTH_DISABLED blocked in production + trace_id sanitized + dead code removed
 4. api/database.py: generic error in health check
 5. api/studies.py:  input validators for BusSpec/LineSpec/TransformerSpec/SystemSpec
 6. api/auth.py:     Redis-backed login rate limiting
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


class TestDockerComposeSecrets:
    def test_postgres_requires_password(self):
        content = read("docker-compose.yml")
        assert "POSTGRES_PASSWORD:?POSTGRES_PASSWORD" in content

    def test_grafana_requires_password(self):
        content = read("docker-compose.yml")
        assert "GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD" in content

    def test_neo4j_requires_password(self):
        content = read("docker-compose.yml")
        assert "NEO4J_PASSWORD:?NEO4J_PASSWORD" in content

    def test_redis_requires_password(self):
        content = read("docker-compose.yml")
        assert "REDIS_PASSWORD:?REDIS_PASSWORD" in content

    def test_qdrant_requires_api_key(self):
        content = read("docker-compose.yml")
        assert "QDRANT_API_KEY:?QDRANT_API_KEY" in content

    def test_no_hardcoded_passwords(self):
        content = read("docker-compose.yml")
        assert "etap_dev_password" not in content
        assert "GRAFANA_ADMIN_PASSWORD:-admin" not in content
        assert "etap_password" not in content

    def test_redis_requirepass_present(self):
        content = read("docker-compose.yml")
        assert "--requirepass" in content


class TestAuthSecurity:
    def test_reset_token_not_leaked(self):
        content = read("api/auth.py")
        assert 'response_data["reset_token"]' not in content
        assert "response_data['reset_token']" not in content

    def test_common_passwords_blocklist_expanded(self):
        content = read("api/auth.py")
        assert "_COMMON_PASSWORDS" in content
        assert "elbaz123" in content
        assert "password123" in content
        assert "letmein" in content

    def test_composite_indexes_defined(self):
        content = read("api/auth.py")
        assert 'Index("ix_users_username_password"' in content
        assert 'Index("ix_users_reset_token"' in content


class TestRoutesSecurity:
    def test_auth_disabled_blocked_in_production(self):
        content = read("api/routes.py")
        assert "AUTH_DISABLED=true is NOT allowed" in content

    def test_trace_id_sanitized(self):
        content = read("api/routes.py")
        assert "isalnum" in content

    def test_dead_code_removed(self):
        content = read("api/routes.py")
        assert "_shared_state_store" not in content
        assert "_shared_event_bus" not in content
        assert "_shared_validation_gateway" not in content


class TestDatabaseHealth:
    def test_generic_error_message(self):
        content = read("api/database.py")
        assert '"error": "Database connection failed"' in content


class TestStudyValidators:
    def test_bus_spec_valid(self):
        from api.studies import BusSpec
        bus = BusSpec(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack")
        assert bus.bus_id == 1

    def test_bus_spec_rejects_bad_voltage(self):
        from api.studies import BusSpec
        with pytest.raises(Exception):
            BusSpec(bus_id=1, voltage_magnitude=3.0, voltage_angle=0.0, bus_type="pq")

    def test_line_spec_rejects_negative_impedance(self):
        from api.studies import LineSpec
        with pytest.raises(Exception):
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=-0.01, x1=0.05)

    def test_transformer_rejects_bad_tap_ratio(self):
        from api.studies import TransformerSpec
        with pytest.raises(Exception):
            TransformerSpec(transformer_id=1, from_bus_id=1, to_bus_id=2, tap_ratio=3.0)

    def test_system_spec_rejects_invalid_base_mva(self):
        from api.studies import SystemSpec
        with pytest.raises(Exception):
            SystemSpec(base_mva=-50.0)


class TestAuthRateLimiting:
    def test_rate_limit_is_async(self):
        import api.auth as auth
        assert inspect.iscoroutinefunction(auth._check_rate_limit)
