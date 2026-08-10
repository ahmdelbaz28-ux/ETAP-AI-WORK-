"""
test_security_requirements.py — Regression tests for SECURITY_REQUIREMENTS.md
remediation (SR-001, SR-008, SR-010, SR-011).

Phase A (CRITICAL) coverage:
  - SR-001: sandbox ``__dict__`` escape rejected (regex pre-scan + AST) and
            pre-imported modules deep-frozen INSIDE the executing subprocess.
  - SR-008: RLS ``app.current_tenant_id`` re-issued before EVERY query (no
            pooled-connection skip) and reset on connection checkin.
  - SR-010: docker-compose secrets are mandatory (``:?``) — no sample defaults.
  - SR-011: config validation hard-fails on missing / weak / sample JWT secret;
            token layer (api.dependencies) refuses sample secrets.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECURE_EXECUTOR = PROJECT_ROOT / "security" / "secure_executor.py"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

_SR010_VARS = (
    "REDIS_PASSWORD",
    "ENGINEERING_SERVICE_API_KEY",
    "POSTGRES_PASSWORD",
    "FIREAI_SESSION_SECRET",
    "JWT_SECRET_KEY",
    "FERNET_ENCRYPTION_KEY",
)

_SR010_SAMPLES = (
    "etap_redis_pass_change_in_prod",
    "etap_dev_api_key_1234567890",
    "etap_postgres_pass_change_in_prod",
    "super_secret_session_key_minimum_43_characters_long_entropy_12345",
    "test-secret-32-bytes-long-aaaa-bbbb",
    "gAAAAABk_sample_fernet_key_32bytes_base64_encoded=",
)


# ---------------------------------------------------------------------------
# SR-001 — sandbox __dict__ escape
# ---------------------------------------------------------------------------


def _run_executor(code: str, timeout: int = 30) -> tuple[int, dict]:
    """Spawn security/secure_executor.py (the exact binary the TypeScript
    python-tool spawns) with code piped through stdin; return (rc, wrapper)."""
    if not SECURE_EXECUTOR.exists():
        pytest.skip(f"secure_executor.py not found at {SECURE_EXECUTOR}")
    proc = subprocess.run(
        [sys.executable, str(SECURE_EXECUTOR)],
        input=code,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    try:
        wrapper = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        wrapper = {"success": False}
    return proc.returncode, wrapper


@pytest.mark.parametrize(
    "code",
    [
        "import numpy as np\nnp.__dict__['os'].system('echo pwned')",
        "import numpy.f2py as nf\nnf.__dict__['os'].system('echo pwned')",
        "import scipy as sp\nsp.__dict__['sys'].modules",
        "import numpy as np\nd = np.__dict__\nprint(d)",
        "import numpy as np\nnp.__getattribute__('os')",
    ],
    ids=[
        "numpy-dict-os",
        "numpy-f2py-dict-os",
        "scipy-dict-sys",
        "numpy-dict-alias",
        "numpy-getattribute",
    ],
)
def test_sandbox_rejects_dict_escape(code: str) -> None:
    """SR-001: __dict__ / __getattribute__ module escapes are rejected pre-exec."""
    rc, wrapper = _run_executor(code)
    assert rc != 0 or not wrapper.get("success"), (
        f"Sandbox escape was NOT rejected:\nrc={rc}\nwrapper={wrapper!r}"
    )
    assert "Security Violation" in str(wrapper.get("error", ""))


def test_sandbox_freezes_module_attrs_in_subprocess() -> None:
    """SR-001: dangerous attrs (os, sys) are nullified INSIDE the subprocess,
    not just in the discarded parent-process freeze."""
    code = (
        "import numpy as np\n"
        "print(np.os is None)\n"
        "import scipy as sp\n"
        "print(sp.sys is None)\n"
    )
    rc, wrapper = _run_executor(code)
    assert wrapper.get("success") is True, f"Legit code failed: {wrapper!r}"
    assert "True\nTrue" in wrapper.get("output", ""), wrapper


def test_sandbox_legit_code_still_runs() -> None:
    """No regression: allowed numeric code runs normally."""
    code = "import numpy as np\nprint(np.array([1, 2, 3]).sum())"
    rc, wrapper = _run_executor(code)
    assert wrapper.get("success") is True, f"Legit code failed: {wrapper!r}"
    assert "6" in wrapper.get("output", ""), wrapper


# ---------------------------------------------------------------------------
# SR-008 — RLS tenant isolation on pooled connections
# ---------------------------------------------------------------------------


class _FakeDialect:
    name = "postgresql"


class _FakeConn:
    """Fake SQLAlchemy Connection whose .execute() records statements."""

    dialect = _FakeDialect()

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    def execute(self, stmt, params=None) -> None:
        self.executed.append((str(stmt), params or {}))


from backend import request_context as rc  # noqa: E402


def test_rls_set_issued_on_every_query_no_skip() -> None:
    """SR-008: the process-wide WeakSet skip is gone — every query re-issues
    SET for the CURRENT request's tenant."""
    conn = _FakeConn()
    rc.set_tenant_id("tenant-A")
    rc._set_tenant_before_query(conn, None, "SELECT 1", None, None, False)
    rc._set_tenant_before_query(conn, None, "SELECT 2", None, None, False)
    assert len(conn.executed) == 2
    assert all("SET app.current_tenant_id" in s for s, _ in conn.executed)
    assert all(p.get("tid") == "tenant-A" for _, p in conn.executed)

    # Same pooled connection, next request (tenant B) → SET re-issued with B.
    rc.set_tenant_id("tenant-B")
    rc._set_tenant_before_query(conn, None, "SELECT 3", None, None, False)
    assert len(conn.executed) == 3
    assert conn.executed[-1][1].get("tid") == "tenant-B"


def test_rls_no_set_when_tenant_empty() -> None:
    conn = _FakeConn()
    rc.set_tenant_id("")
    rc._set_tenant_before_query(conn, None, "SELECT 1", None, None, False)
    assert conn.executed == []


def test_rls_no_set_on_non_postgres_dialect() -> None:
    conn = _FakeConn()
    conn.dialect = type("SQLite", (), {"name": "sqlite"})()
    rc.set_tenant_id("tenant-A")
    rc._set_tenant_before_query(conn, None, "SELECT 1", None, None, False)
    assert conn.executed == []


def test_rls_set_not_recursive_for_set_statement() -> None:
    """Re-entrancy guard: the handler's own SET execution doesn't re-trigger."""
    conn = _FakeConn()
    rc.set_tenant_id("tenant-A")
    rc._set_tenant_before_query(conn, None, "SET app.current_tenant_id = :tid", None, None, False)
    assert conn.executed == []


def test_rls_reset_on_checkin(monkeypatch: pytest.MonkeyPatch) -> None:
    """SR-008: session variable cleared when the connection returns to pool."""

    class _Cursor:
        def __init__(self) -> None:
            self.executed: list[str] = []

        def execute(self, stmt: str) -> None:
            self.executed.append(stmt)

        def close(self) -> None:
            pass

    class _DbapiConn:
        def __init__(self) -> None:
            self.cursor_obj = _Cursor()

        def cursor(self) -> _Cursor:
            return self.cursor_obj

    class _SyncEngine:
        dialect = _FakeDialect()

    class _FakeEngine:
        sync_engine = _SyncEngine()

    monkeypatch.setattr("api.database.engine", _FakeEngine())
    dbapi = _DbapiConn()
    rc._reset_tenant_on_checkin(dbapi, None)
    assert dbapi.cursor_obj.executed == ["SET app.current_tenant_id = ''"]


# ---------------------------------------------------------------------------
# SR-010 — mandatory deployment secrets (docker-compose)
# ---------------------------------------------------------------------------


def test_compose_has_no_sample_secret_defaults() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    for sample in _SR010_SAMPLES:
        assert sample not in compose, f"sample secret still present: {sample}"


def test_compose_secrets_are_mandatory_no_default() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    # Every occurrence of the six secrets must use :? (fail when unset).
    for var in _SR010_VARS:
        assert "${" + var + ":?" in compose, (
            f"{var} must use mandatory ':?' syntax (no fallback default)"
        )
    assert (
        re.search(
            r"\$\{(?:%s):-" % "|".join(_SR010_VARS),
            compose,
        )
        is None
    ), "a secret still has a fallback default (:-)"


# ---------------------------------------------------------------------------
# SR-011 — config secret validation hard-fail
# ---------------------------------------------------------------------------


def _config_subclass(**attrs) -> type:
    import backend.config as bc

    return type("_TestConfig", (bc.Config,), attrs)


def test_config_raises_on_missing_jwt_in_production() -> None:
    cls = _config_subclass(ENVIRONMENT="production", JWT_SECRET_KEY="")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY is not set"):
        cls.validate_config()


def test_config_raises_on_short_jwt_in_production() -> None:
    cls = _config_subclass(ENVIRONMENT="production", JWT_SECRET_KEY="too-short")
    with pytest.raises(ValueError, match="at least 32 bytes"):
        cls.validate_config()


def test_config_raises_on_sample_jwt_in_production() -> None:
    cls = _config_subclass(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="test-secret-32-bytes-long-aaaa-bbbb",
    )
    with pytest.raises(ValueError, match="known-insecure sample"):
        cls.validate_config()


def test_config_accepts_strong_jwt_in_production() -> None:
    cls = _config_subclass(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a" * 64,
        DATABASE_URL="sqlite:///./db/digital_twin.db",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_PASSWORD="",
    )
    assert cls.validate_config() == []


def test_dependencies_refuse_sample_jwt_secret() -> None:
    """SR-011: the token layer refuses to start with a known-insecure sample."""
    code = (
        "import os\n"
        "os.environ['JWT_SECRET_KEY'] = 'test-secret-32-bytes-long-aaaa-bbbb'\n"
        "os.environ['ENVIRONMENT'] = 'production'\n"
        "import api.dependencies\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        timeout=60,
    )
    assert proc.returncode != 0, "dependencies must refuse sample JWT secret"
    assert "known-insecure sample" in proc.stderr.lower()


def test_dependencies_refuse_sample_api_key() -> None:
    code = (
        "import os\n"
        "os.environ['JWT_SECRET_KEY'] = 'x' * 64\n"
        "os.environ['ENGINEERING_SERVICE_API_KEY'] = 'etap_dev_api_key_1234567890'\n"
        "import api.dependencies\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        timeout=60,
    )
    assert proc.returncode != 0, "dependencies must refuse sample API key"
    assert "known-insecure sample" in proc.stderr.lower()