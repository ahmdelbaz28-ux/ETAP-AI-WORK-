"""tests/test_audit_logs_security.py — Security tests for audit logs scoping and authorization (A4)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.audit_logs as audit_module
from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header


@pytest.fixture
def audit_app():
    app = FastAPI()
    app.include_router(audit_module.router)
    return app


def test_audit_logs_scoping_and_roles(audit_app):
    client = TestClient(audit_app)
    audit_app.dependency_overrides[get_api_key] = lambda: "valid-key"

    # Sample test logs with different tenants and users
    test_logs = [
        {
            "id": "log-1",
            "timestamp": "2026-09-07T10:00:00Z",
            "severity": "info",
            "action": "login",
            "user": "alice",
            "user_id": "user-a",
            "tenant_id": "tenant-A",
            "ip_address": "127.0.0.1",
            "resource": "/login",
            "details": "User login",
            "trace_id": "t1",
        },
        {
            "id": "log-2",
            "timestamp": "2026-09-07T10:05:00Z",
            "severity": "high",
            "action": "study_run",
            "user": "bob",
            "user_id": "user-b",
            "tenant_id": "tenant-B",
            "ip_address": "127.0.0.1",
            "resource": "/studies",
            "details": "Run study",
            "trace_id": "t2",
        },
        {
            "id": "log-3",
            "timestamp": "2026-09-07T10:10:00Z",
            "severity": "low",
            "action": "logout",
            "user": "alice",
            "user_id": "user-a",
            "tenant_id": "tenant-A",
            "ip_address": "127.0.0.1",
            "resource": "/logout",
            "details": "User logout",
            "trace_id": "t3",
        },
    ]

    # Temporarily monkeypatch _SAMPLE_AUDIT_LOGS
    orig_logs = audit_module._SAMPLE_AUDIT_LOGS
    audit_module._SAMPLE_AUDIT_LOGS = test_logs

    try:
        # 1. Non-admin engineer (Alice) in Tenant-A: should only see Alice's logs
        alice = CurrentUser(
            user_id="user-a",
            username="alice",
            email="alice@test.com",
            role="engineer",
            tenant_id="tenant-A",
        )
        audit_app.dependency_overrides[get_current_user_from_header] = lambda: alice

        res = client.get("/api/v1/security/audit-logs/")
        assert res.status_code == 200
        entries = res.json()["entries"]
        assert len(entries) == 2
        for e in entries:
            assert e["user"] == "alice"

        # Alice tries to get Bob's log (log-2) -> 404
        res_bob_log = client.get("/api/v1/security/audit-logs/log-2")
        assert res_bob_log.status_code == 404

        # Alice gets her own log (log-1) -> 200
        res_alice_log = client.get("/api/v1/security/audit-logs/log-1")
        assert res_alice_log.status_code == 200
        assert res_alice_log.json()["id"] == "log-1"

        # 2. Auditor in Tenant-A: sees all Tenant-A logs (not Bob in Tenant-B)
        auditor_a = CurrentUser(
            user_id="audit-1",
            username="auditor1",
            email="auditor@test.com",
            role="auditor",
            tenant_id="tenant-A",
        )
        audit_app.dependency_overrides[get_current_user_from_header] = lambda: auditor_a

        res = client.get("/api/v1/security/audit-logs/")
        assert res.status_code == 200
        entries = res.json()["entries"]
        assert len(entries) == 2

        # 3. Global Admin: can see all logs across tenants
        admin = CurrentUser(
            user_id="admin-1",
            username="superadmin",
            email="admin@test.com",
            role="admin",
            tenant_id="",
        )
        audit_app.dependency_overrides[get_current_user_from_header] = lambda: admin

        res = client.get("/api/v1/security/audit-logs/")
        assert res.status_code == 200
        assert len(res.json()["entries"]) == 3

        # Admin gets Bob's log -> 200
        res_bob_admin = client.get("/api/v1/security/audit-logs/log-2")
        assert res_bob_admin.status_code == 200
        assert res_bob_admin.json()["id"] == "log-2"

        # CSV export works
        res_csv = client.get("/api/v1/security/audit-logs/export/csv")
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]

        # Stats work
        res_stats = client.get("/api/v1/security/audit-logs/stats")
        assert res_stats.status_code == 200
        assert res_stats.json()["total"] == 3

    finally:
        audit_module._SAMPLE_AUDIT_LOGS = orig_logs
        audit_app.dependency_overrides.clear()
