"""Tests for the security layer — authentication, audit logging, and router integration.

Covers:
    * HMAC token issuance and validation (valid, expired, bad sig, bad payload)
    * CallerIdentity construction and scope validation
    * Bearer token extraction from header
    * AuditEntry serialization
    * InMemoryAuditLogger capture and thread safety
    * NDJSONAuditLogger file writing (using temp dir)
    * Router integration: auth enabled / disabled, audit enabled / disabled
    * Public capability bypass with auth, require_auth_for_public flag
    * Auth failure maps to -32005 AuthenticationRequired
    * Audit entries for success, error, denied, notification
"""
from __future__ import annotations
import json
import time
import tempfile
from pathlib import Path

import anyio
import pytest

from acp.security import (
    CallerIdentity,
    AuthConfig,
    HmacTokenValidator,
    validate_bearer_token,
    extract_token_from_header,
    AuditEntry,
    AuditLogger,
    InMemoryAuditLogger,
    NDJSONAuditLogger,
)
from acp.security.auth import AuthenticationRequired
from acp.router import Router, RouterConfig
from acp.runtime import AcpRuntime, capability


# ------------------------------------------------------- test handlers

class MathHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        await anyio.sleep(0.001)
        return a + b

    @capability("math.public")
    async def identity(self, x: int) -> int:
        return x


# ------------------------------------------------------- HmacTokenValidator

class TestHmacTokenValidator:
    def _make(self, secret: str = "secret", ttl: int = 3600) -> HmacTokenValidator:
        return HmacTokenValidator(AuthConfig(secret_key=secret, token_ttl_seconds=ttl))

    def test_issue_and_validate(self):
        validator = self._make()
        token = validator.issue("alice", {"math.read", "math.write"})
        identity = validator.validate(token)
        assert identity.caller_id == "alice"
        assert identity.scopes == {"math.read", "math.write"}

    def test_expired_token_rejected(self):
        validator = self._make(ttl=1)
        token = validator.issue("alice", {"math.read"})
        time.sleep(1.1)
        with pytest.raises(AuthenticationRequired):
            validator.validate(token)

    def test_bad_signature_rejected(self):
        validator = self._make()
        token = validator.issue("alice", {"math.read"})
        bad_token = token[:-4] + "XXXX"
        with pytest.raises(AuthenticationRequired):
            validator.validate(bad_token)

    def test_malformed_token_rejected(self):
        validator = self._make()
        with pytest.raises(AuthenticationRequired):
            validator.validate("not-a-token")
        with pytest.raises(AuthenticationRequired):
            validator.validate("onlypayload")

    def test_issuer_mismatch(self):
        # Issue with one issuer, validate with another
        issuer_validator = HmacTokenValidator(
            AuthConfig(secret_key="secret", issuer="wrong-server")
        )
        token = issuer_validator.issue("alice", {"math.read"})
        validator = HmacTokenValidator(
            AuthConfig(secret_key="secret", issuer="acp-server")
        )
        with pytest.raises(AuthenticationRequired):
            validator.validate(token)

    def test_audience_mismatch(self):
        # Issue with one audience, validate with another
        aud_validator = HmacTokenValidator(
            AuthConfig(secret_key="secret", audience="wrong-client")
        )
        token = aud_validator.issue("alice", {"math.read"})
        validator = HmacTokenValidator(
            AuthConfig(secret_key="secret", audience="acp-client")
        )
        with pytest.raises(AuthenticationRequired):
            validator.validate(token)

    def test_custom_claims_preserved(self):
        validator = self._make()
        token = validator.issue("alice", {"math.read"}, role="admin", org="acme")
        identity = validator.validate(token)
        assert identity.metadata["role"] == "admin"
        assert identity.metadata["org"] == "acme"

    def test_empty_scopes_allowed(self):
        validator = self._make()
        token = validator.issue("bob", set())
        identity = validator.validate(token)
        assert identity.scopes == set()

    def test_invalid_scope_in_identity_rejected(self):
        with pytest.raises(ValueError):
            CallerIdentity("eve", {"BadScope"})

    def test_no_expiry_check_when_ttl_zero(self):
        validator = self._make(ttl=0)
        token = validator.issue("alice", {"math.read"})
        time.sleep(0.1)
        # Should not raise even though token is "old"
        identity = validator.validate(token)
        assert identity.caller_id == "alice"


# ------------------------------------------------------- CallerIdentity

class TestCallerIdentity:
    def test_repr(self):
        ci = CallerIdentity("u1", {"a", "b"})
        r = repr(ci)
        assert "u1" in r
        assert "a" in r
        assert "b" in r

    def test_empty_defaults(self):
        ci = CallerIdentity("u2")
        assert ci.scopes == set()
        assert ci.metadata == {}


# ------------------------------------------------------- Header helpers

class TestHeaderHelpers:
    def test_extract_bearer_token(self):
        assert extract_token_from_header("Bearer abc123") == "abc123"
        assert extract_token_from_header("bearer abc123") == "abc123"
        assert extract_token_from_header("Basic abc123") is None
        assert extract_token_from_header(None) is None
        assert extract_token_from_header("") is None

    def test_validate_bearer_token_with_validator(self):
        validator = HmacTokenValidator(AuthConfig("secret"))
        token = validator.issue("alice", {"math.read"})
        identity = validate_bearer_token(f"Bearer {token}", validator.validate)
        assert identity is not None
        assert identity.caller_id == "alice"

    def test_validate_bearer_token_no_validator(self):
        assert validate_bearer_token("Bearer abc", None) is None

    def test_validate_bearer_token_missing_header(self):
        with pytest.raises(AuthenticationRequired):
            validate_bearer_token(None, lambda t: CallerIdentity("x"))

    def test_validate_bearer_token_bad_format(self):
        with pytest.raises(AuthenticationRequired):
            validate_bearer_token("Basic abc", lambda t: CallerIdentity("x"))


# ------------------------------------------------------- AuditEntry

class TestAuditEntry:
    def test_to_json(self):
        entry = AuditEntry(
            timestamp=1_700_000_000.123,
            method="math.sum",
            capability="math.sum",
            caller_id="alice",
            outcome="success",
            duration_ms=42,
            error_code=0,
            trace_id="t1",
            metadata={"ip": "127.0.0.1"},
        )
        line = entry.to_json()
        data = json.loads(line)
        assert data["method"] == "math.sum"
        assert data["caller_id"] == "alice"
        assert data["outcome"] == "success"
        assert data["duration_ms"] == 42
        assert data["metadata"]["ip"] == "127.0.0.1"


# ------------------------------------------------------- InMemoryAuditLogger

@pytest.mark.anyio
async def test_in_memory_audit_logger():
    logger = InMemoryAuditLogger()
    await logger.log(
        method="m1",
        capability="c1",
        caller_id="alice",
        outcome="success",
        duration_ms=10,
    )
    await logger.log(
        method="m2",
        capability="c2",
        caller_id="bob",
        outcome="error",
        error_code=-32001,
    )
    entries = logger.entries
    assert len(entries) == 2
    assert entries[0].caller_id == "alice"
    assert entries[1].error_code == -32001


@pytest.mark.anyio
async def test_in_memory_audit_logger_clear():
    logger = InMemoryAuditLogger()
    await logger.log(method="m", capability="c", outcome="success")
    logger.clear()
    assert len(logger.entries) == 0


@pytest.mark.anyio
async def test_in_memory_audit_logger_thread_safety():
    logger = InMemoryAuditLogger()

    async def write_many(n: int):
        for i in range(n):
            await logger.log(
                method=f"m{i}",
                capability="c",
                outcome="success",
            )

    async with anyio.create_task_group() as tg:
        tg.start_soon(write_many, 50)
        tg.start_soon(write_many, 50)

    assert len(logger.entries) == 100


# ------------------------------------------------------- NDJSONAuditLogger

@pytest.mark.anyio
async def test_ndjson_audit_logger():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.ndjson"
        logger = NDJSONAuditLogger(path)
        await logger.log(
            method="math.sum",
            capability="math.sum",
            caller_id="alice",
            outcome="success",
            duration_ms=5,
        )
        await logger.close()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["method"] == "math.sum"
        assert data["caller_id"] == "alice"


# ------------------------------------------------------- Router + Auth integration

@pytest.mark.anyio
async def test_router_with_valid_auth():
    runtime = AcpRuntime([MathHandler()])
    validator = HmacTokenValidator(AuthConfig("secret"))
    token = validator.issue("alice", {"math.read"})
    audit = InMemoryAuditLogger()

    router = Router(
        runtime,
        RouterConfig(
            auth_validator=validator.validate,
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-1",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": token,
    })
    assert resp["result"] == 3
    assert len(audit.entries) == 1
    assert audit.entries[0].caller_id == "alice"
    assert audit.entries[0].outcome == "success"


@pytest.mark.anyio
async def test_router_with_invalid_auth():
    runtime = AcpRuntime([MathHandler()])
    validator = HmacTokenValidator(AuthConfig("secret"))
    audit = InMemoryAuditLogger()

    router = Router(
        runtime,
        RouterConfig(
            auth_validator=validator.validate,
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-2",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": "bad-token",
    })
    assert resp["error"]["code"] == -32005
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "denied"
    assert audit.entries[0].error_code == -32005


@pytest.mark.anyio
async def test_router_auth_missing_token():
    runtime = AcpRuntime([MathHandler()])
    validator = HmacTokenValidator(AuthConfig("secret"))
    audit = InMemoryAuditLogger()

    router = Router(
        runtime,
        RouterConfig(
            auth_validator=validator.validate,
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-3",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": "",
    })
    assert resp["error"]["code"] == -32005
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "denied"


@pytest.mark.anyio
async def test_router_no_auth_bypass():
    runtime = AcpRuntime([MathHandler()])
    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            caller_scopes={"math.read"},
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-4",
        "method": "math.sum",
        "params": {"a": 3, "b": 4},
        "capability": "math.sum",
    })
    assert resp["result"] == 7
    assert len(audit.entries) == 1
    assert audit.entries[0].caller_id == ""


@pytest.mark.anyio
async def test_router_require_auth_for_public():
    runtime = AcpRuntime([MathHandler()])
    validator = HmacTokenValidator(AuthConfig("secret"))
    audit = InMemoryAuditLogger()

    router = Router(
        runtime,
        RouterConfig(
            auth_validator=validator.validate,
            audit_logger=audit,
            require_auth_for_public=True,
        ),
    )
    # Without token, public capability should be denied
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-5",
        "method": "math.identity",
        "params": {"x": 1},
        "capability": "math.public",
        "trace_id": "",
    })
    assert resp["error"]["code"] == -32005
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "denied"

    # With valid token, public capability should succeed
    token = validator.issue("bob", {"math.read"})
    audit.clear()
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-6",
        "method": "math.identity",
        "params": {"x": 2},
        "capability": "math.public",
        "trace_id": token,
    })
    assert resp["result"] == 2
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "success"


@pytest.mark.anyio
async def test_router_auth_with_scope_merge():
    runtime = AcpRuntime([MathHandler()])
    validator = HmacTokenValidator(AuthConfig("secret"))
    token = validator.issue("alice", {"math.read"})
    audit = InMemoryAuditLogger()

    router = Router(
        runtime,
        RouterConfig(
            caller_scopes={"text.read"},
            auth_validator=validator.validate,
            audit_logger=audit,
        ),
    )
    # Token provides math.read, config provides text.read
    # math.sum requires math.read → should succeed
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-auth-7",
        "method": "math.sum",
        "params": {"a": 5, "b": 6},
        "capability": "math.sum",
        "trace_id": token,
    })
    assert resp["result"] == 11


@pytest.mark.anyio
async def test_router_audit_on_error():
    runtime = AcpRuntime([MathHandler()])
    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            caller_scopes={"math.read"},
            audit_logger=audit,
        ),
    )
    # Unknown capability
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-audit-1",
        "method": "math.nope",
        "params": {},
        "capability": "math.nope",
    })
    assert resp["error"]["code"] == -32002
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "error"
    assert audit.entries[0].error_code == -32002


@pytest.mark.anyio
async def test_router_audit_on_scope_denied():
    runtime = AcpRuntime([MathHandler()])
    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            caller_scopes=set(),
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-audit-2",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
    })
    assert resp["error"]["code"] == -32003
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "denied"
    assert audit.entries[0].error_code == -32003


@pytest.mark.anyio
async def test_router_audit_on_notification():
    runtime = AcpRuntime([MathHandler()])
    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            audit_logger=audit,
        ),
    )
    result = await router.handle({
        "jsonrpc": "2.0",
        "method": "progress.update",
        "params": {"percent": 50},
    })
    assert result is None
    assert len(audit.entries) == 1
    assert audit.entries[0].outcome == "notification"


@pytest.mark.anyio
async def test_router_audit_disabled():
    runtime = AcpRuntime([MathHandler()])
    router = Router(
        runtime,
        RouterConfig(
            caller_scopes={"math.read"},
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-audit-3",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
    })
    assert resp["result"] == 3
    # No audit logger configured → no entries, no crash


@pytest.mark.anyio
async def test_router_auth_async_validator():
    runtime = AcpRuntime([MathHandler()])

    async def async_validator(token: str) -> CallerIdentity:
        if token == "async-token":
            return CallerIdentity("async-user", {"math.read"})
        raise AuthenticationRequired("Bad async token")

    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            auth_validator=async_validator,
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-async-1",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": "async-token",
    })
    assert resp["result"] == 3
    assert audit.entries[0].caller_id == "async-user"

    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-async-2",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": "bad",
    })
    assert resp["error"]["code"] == -32005


@pytest.mark.anyio
async def test_router_auth_exception_becomes_auth_required():
    runtime = AcpRuntime([MathHandler()])

    def bad_validator(token: str) -> CallerIdentity:
        raise RuntimeError("validator crashed")

    audit = InMemoryAuditLogger()
    router = Router(
        runtime,
        RouterConfig(
            auth_validator=bad_validator,
            audit_logger=audit,
        ),
    )
    resp = await router.handle({
        "jsonrpc": "2.0",
        "id": "req-crash",
        "method": "math.sum",
        "params": {"a": 1, "b": 2},
        "capability": "math.sum",
        "trace_id": "any",
    })
    assert resp["error"]["code"] == -32005
    assert "validator crashed" in resp["error"]["message"]
    assert audit.entries[0].outcome == "denied"
