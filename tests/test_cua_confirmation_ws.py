"""
tests/test_cua_confirmation_ws.py — Regression tests for CUA ConfirmationBroker tenant isolation and dual confirmation.
"""

from __future__ import annotations

import pytest

from api.cua_confirmation_ws import ConfirmationBroker, ConfirmationRequest


@pytest.mark.asyncio
async def test_cua_confirmation_tenant_isolation_and_dual_control():
    broker = ConfirmationBroker()

    # Tenant A creates confirmation request requiring dual confirmation (2 humans)
    req_a = ConfirmationRequest(
        request_id="req-tenant-a-1",
        action_type="TRIP",
        action_target="BREAKER-4160V",
        tenant_id="tenant_a",
        initiator_id="admin_a1",
        requires_dual_confirmation=True,
    )
    broker._pending["req-tenant-a-1"] = req_a

    # 1. Initiator cannot confirm own request (Maker-Checker violation)
    res_initiator = await broker.confirm(
        request_id="req-tenant-a-1",
        session_id="admin_a1",
        tenant_id="tenant_a",
    )
    assert res_initiator.get("error") == "maker_checker_violation"

    # 2. Tenant B attempts confirm → cross_tenant_forbidden
    res_cross = await broker.confirm(
        request_id="req-tenant-a-1",
        session_id="admin_b1",
        tenant_id="tenant_b",
    )
    assert res_cross.get("error") == "cross_tenant_forbidden"

    # 3. First admin in tenant A confirms → success, but not yet resolved (needs 2)
    res_confirm1 = await broker.confirm(
        request_id="req-tenant-a-1",
        session_id="admin_a2",
        tenant_id="tenant_a",
    )
    assert res_confirm1.get("success") is True
    assert req_a._result is None

    # 4. Second admin in tenant A confirms → success and resolved!
    res_confirm2 = await broker.confirm(
        request_id="req-tenant-a-1",
        session_id="admin_a3",
        tenant_id="tenant_a",
    )
    assert res_confirm2.get("success") is True
    assert req_a._result is True
