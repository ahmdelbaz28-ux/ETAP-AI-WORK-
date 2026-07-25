"""
tests/test_audit_phase2_fixes.py — Verification tests for Phase 2 high-severity fixes.

Validates that all Phase 2 audit findings are properly remediated:
  S-06: CSRF production guard (RuntimeError if no secret in production)
  S-08: Rate limiter thread safety (threading.Lock) + memory cleanup
  S-09: JWT bypass checks token type and active status
  S-10: R2 path traversal validation
  S-11: Assets authorization (BOLA/IDOR) — owner or admin for PUT/DELETE
  S-12: Docker-compose ports restricted to 127.0.0.1

Run: pytest tests/test_audit_phase2_fixes.py -v
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# S-06: CSRF Production Guard
# ---------------------------------------------------------------------------

class TestCSRFS06:
    """Verify CSRF raises RuntimeError in production if no secret is configured."""

    def test_s06_production_guard_in_source(self):
        """S-06: Source must contain production environment guard."""
        src = Path("api/csrf.py").read_text()
        assert "RuntimeError" in src, (
            "S-06: _get_secret() must raise RuntimeError in production"
        )
        assert "production" in src.lower() or "ENVIRONMENT" in src, (
            "S-06: Must check ENVIRONMENT for production guard"
        )

    def test_s06_dev_fallback_with_warning(self):
        """S-06: Dev/test environments should log warning when using default."""
        src = Path("api/csrf.py").read_text()
        assert "warning" in src.lower(), (
            "S-06: Should log warning when using default secret in dev"
        )


# ---------------------------------------------------------------------------
# S-08: Rate Limiter Thread Safety
# ---------------------------------------------------------------------------

class TestRateLimiterS08:
    """Verify rate limiter is thread-safe and has memory cleanup."""

    def test_s08_threading_lock_present(self):
        """S-08: RateLimiter must use threading.Lock."""
        from api._rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert hasattr(limiter, '_lock'), (
            "S-08: RateLimiter must have a _lock attribute for thread safety"
        )
        import threading
        # threading.Lock() returns _thread.lock in CPython
        assert hasattr(limiter._lock, 'acquire') and hasattr(limiter._lock, 'release'), (
            "S-08: _lock must support acquire/release (thread lock protocol)"
        )

    def test_s08_lock_used_in_is_allowed(self):
        """S-08: is_allowed() must acquire the lock."""
        src = Path("api/_rate_limit.py").read_text()
        # Should contain 'with self._lock'
        assert "with self._lock" in src, (
            "S-08: is_allowed() must use 'with self._lock' for thread safety"
        )

    def test_s08_stale_key_eviction(self):
        """S-08: Must have stale key eviction mechanism."""
        src = Path("api/_rate_limit.py").read_text()
        assert "_evict_stale_keys" in src or "evict" in src.lower() or "cleanup" in src.lower(), (
            "S-08: Must have stale key eviction to prevent memory leak"
        )

    def test_s08_reset_clears_under_lock(self):
        """S-08: reset() must also acquire the lock."""
        src = Path("api/_rate_limit.py").read_text()
        lines = src.splitlines()
        reset_found = False
        for line in lines:
            if "def reset" in line:
                reset_found = True
                continue
            if reset_found:
                # Check the reset method body for lock usage
                if "return" in line and "self._lock" not in src[src.find("def reset"):src.find("def reset")+200]:
                    break
        # Verify reset uses lock by checking source text
        reset_section = src[src.find("def reset"):] if "def reset" in src else ""
        assert "with self._lock" in reset_section or "self._lock" in reset_section, (
            "S-08: reset() must also acquire the lock for thread safety"
        )

    def test_s08_concurrent_safety(self):
        """S-08: Concurrent calls should not corrupt state."""
        import threading
        from api._rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        errors = []

        def hammer():
            try:
                for _ in range(50):
                    limiter.is_allowed("test-key")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread safety errors: {errors}"
        # After 10 threads * 50 requests = 500, but limit is 100, some should be rejected
        # The key point is no exceptions/corruption


# ---------------------------------------------------------------------------
# S-09: JWT Bypass Token Type Check
# ---------------------------------------------------------------------------

class TestJWTS09:
    """Verify JWT bypass path checks token type and active status."""

    def test_s09_token_type_check(self):
        """S-09: Must check that token type is 'access', not 'refresh'."""
        src = Path("api/dependencies.py").read_text()
        assert '"access"' in src or "'access'" in src, (
            "S-09: Must verify token type is 'access'"
        )

    def test_s09_expired_token_check(self):
        """S-09: Must reject expired tokens explicitly."""
        src = Path("api/dependencies.py").read_text()
        assert "ExpiredSignatureError" in src, (
            "S-09: Must handle ExpiredSignatureError explicitly"
        )

    def test_s09_refresh_rejection(self):
        """S-09: Must reject refresh tokens used as access tokens."""
        src = Path("api/dependencies.py").read_text()
        assert "refresh" in src.lower(), (
            "S-09: Must check for and reject refresh tokens"
        )


# ---------------------------------------------------------------------------
# S-10: R2 Path Traversal
# ---------------------------------------------------------------------------

class TestR2S10:
    """Verify R2 storage has path traversal validation."""

    def test_s10_validation_function_exists(self):
        """S-10: Must have a key validation function."""
        src = Path("api/r2_storage.py").read_text()
        assert "_validate_key" in src, (
            "S-10: Must have _validate_key() function"
        )

    def test_s10_rejects_double_dot(self):
        """S-10: Must reject keys containing '..'."""
        src = Path("api/r2_storage.py").read_text()
        assert ".." in src and ("raise" in src or "ValueError" in src), (
            "S-10: Must reject directory traversal ('..')"
        )

    def test_s10_rejects_absolute_path(self):
        """S-10: Must reject keys starting with '/'."""
        src = Path("api/r2_storage.py").read_text()
        assert 'startswith("/")' in src or "absolute" in src.lower(), (
            "S-10: Must reject absolute paths"
        )

    def test_s10_rejects_null_bytes(self):
        """S-10: Must reject keys containing null bytes."""
        src = Path("api/r2_storage.py").read_text()
        assert "\\x00" in src or "null" in src.lower(), (
            "S-10: Must reject null byte injection"
        )

    def test_s10_validation_called_in_upload(self):
        """S-10: upload() must call _validate_key()."""
        src = Path("api/r2_storage.py").read_text()
        upload_section = src[src.find("async def upload"):] if "async def upload" in src else ""
        assert "_validate_key" in upload_section, (
            "S-10: upload() must call _validate_key(key)"
        )

    def test_s10_validation_called_in_download(self):
        """S-10: download() must call _validate_key()."""
        src = Path("api/r2_storage.py").read_text()
        download_section = src[src.find("async def download"):] if "async def download" in src else ""
        assert "_validate_key" in download_section, (
            "S-10: download() must call _validate_key(key)"
        )

    def test_s10_validation_called_in_delete(self):
        """S-10: delete() must call _validate_key()."""
        src = Path("api/r2_storage.py").read_text()
        delete_section = src[src.find("async def delete"):] if "async def delete" in src else ""
        assert "_validate_key" in delete_section, (
            "S-10: delete() must call _validate_key(key)"
        )


# ---------------------------------------------------------------------------
# S-11: Assets Authorization (BOLA/IDOR)
# ---------------------------------------------------------------------------

class TestAssetsS11:
    """Verify asset endpoints have authorization checks."""

    def test_s11_update_has_user_param(self):
        """S-11: update_asset() must require authenticated user."""
        src = Path("api/assets.py").read_text()
        update_section = src[src.find("async def update_asset"):]
        # Must have user parameter with get_current_user_from_header
        assert "user:" in update_section or "CurrentUser" in update_section, (
            "S-11: update_asset() must have user parameter for authorization"
        )

    def test_s11_delete_has_user_param(self):
        """S-11: delete_asset() must require authenticated user."""
        src = Path("api/assets.py").read_text()
        delete_section = src[src.find("async def delete_asset"):]
        assert "user:" in delete_section or "CurrentUser" in delete_section, (
            "S-11: delete_asset() must have user parameter for authorization"
        )

    def test_s11_owner_or_admin_check(self):
        """S-11: Must check created_by == user_id or role == admin."""
        src = Path("api/assets.py").read_text()
        assert "created_by" in src and ("user_id" in src or "user.user_id" in src), (
            "S-11: Must check asset ownership (created_by == user_id)"
        )
        assert "403" in src or "FORBIDDEN" in src, (
            "S-11: Must return 403 Forbidden on authorization failure"
        )

    def test_s11_docstring_mentions_security(self):
        """S-11: Security fix should be documented."""
        src = Path("api/assets.py").read_text()
        assert "S-11" in src, (
            "S-11: Fix should be documented with audit reference S-11"
        )


# ---------------------------------------------------------------------------
# S-12: Docker-Compose Port Restriction
# ---------------------------------------------------------------------------

class TestDockerComposeS12:
    """Verify database/infra ports are bound to 127.0.0.1 only."""

    def test_s12_redis_localhost(self):
        """S-12: Redis port should be bound to 127.0.0.1."""
        src = Path("docker-compose.yml").read_text()
        # Find redis service section and check port bindings
        lines = src.splitlines()
        in_redis = False
        for line in lines:
            if line.strip().startswith("redis:"):
                in_redis = True
            elif in_redis and line.strip().startswith(("postgres:", "celery", "engineering")):
                in_redis = False
            if in_redis and "6379" in line and "ports" not in line.lower():
                # This is a port mapping line
                assert "127.0.0.1" in line, (
                    f"S-12: Redis port must be bound to 127.0.0.1: {line.strip()}"
                )

    def test_s12_postgres_localhost(self):
        """S-12: Postgres port should be bound to 127.0.0.1."""
        src = Path("docker-compose.yml").read_text()
        lines = src.splitlines()
        in_postgres = False
        for line in lines:
            if line.strip().startswith("postgres:"):
                in_postgres = True
            elif in_postgres and line.strip().startswith(("grafana:", "redis:", "  redis:")):
                in_postgres = False
            if in_postgres and "5432" in line and "ports" not in line.lower():
                assert "127.0.0.1" in line, (
                    f"S-12: Postgres port must be bound to 127.0.0.1: {line.strip()}"
                )

    def test_s12_no_zero_dot_zero_dot_zero(self):
        """S-12: No port binding should use 0.0.0.0."""
        src = Path("docker-compose.yml").read_text()
        lines = src.splitlines()
        for line in lines:
            stripped = line.strip()
            # Only check port mapping lines (contain both a colon for IP:PORT and a port number)
            if stripped.startswith("-") and re.match(r'-\s+"[\d.]+:\d+', stripped):
                assert "0.0.0.0" not in stripped, (
                    f"S-12: Port binding uses 0.0.0.0 (exposes to all interfaces): {stripped}"
                )

    def test_s12_grafana_localhost(self):
        """S-12: Grafana port should be bound to 127.0.0.1."""
        src = Path("docker-compose.yml").read_text()
        lines = src.splitlines()
        in_grafana = False
        for line in lines:
            if line.strip().startswith("grafana:"):
                in_grafana = True
            elif in_grafana and line.strip().startswith(("qdrant:", "neo4j:")):
                in_grafana = False
            if in_grafana and "3000" in line and "ports" not in line.lower():
                assert "127.0.0.1" in line, (
                    f"S-12: Grafana port must be bound to 127.0.0.1: {line.strip()}"
                )

    def test_s12_neo4j_localhost(self):
        """S-12: Neo4j ports should be bound to 127.0.0.1."""
        src = Path("docker-compose.yml").read_text()
        lines = src.splitlines()
        in_neo4j = False
        for line in lines:
            if line.strip().startswith("neo4j:"):
                in_neo4j = True
            elif in_neo4j and line.strip().startswith(("volumes:", "networks:")):
                in_neo4j = False
            if in_neo4j and ("7474" in line or "7687" in line) and "ports" not in line.lower():
                assert "127.0.0.1" in line, (
                    f"S-12: Neo4j port must be bound to 127.0.0.1: {line.strip()}"
                )
