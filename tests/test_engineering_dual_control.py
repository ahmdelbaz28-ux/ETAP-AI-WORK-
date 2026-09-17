"""
tests/test_engineering_dual_control.py — Dual-Control Maker-Checker Enforcement for Engineering Operations.

Verifies:
1. Critical engineering actions require approval (status=pending, risk_class=critical).
2. Anti-Self-Approval: Maker cannot approve their own action (HTTP 403 MAKER_CHECKER_VIOLATION).
3. Separate authorized Checker/Admin can approve the action (HTTP 200, status=approved).
4. Separate authorized Checker/Admin can reject the action (HTTP 200, status=rejected).
5. Cross-tenant approvals are blocked.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.approvals import (
    _RISK_CRITICAL,
    _STATUS_APPROVED,
    _STATUS_PENDING,
    _STATUS_REJECTED,
    CROSS_TENANT_FORBIDDEN,
    MAKER_CHECKER_VIOLATION,
    PendingAction,
    ResolveRequest,
    _utc_now,
    compute_args_hash,
    resolve_action,
)
from api.database import Base
from api.dependencies import CurrentUser

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.mark.asyncio
async def test_dual_control_anti_self_approval(async_db: AsyncSession):
    """Verify Maker cannot approve their own critical engineering action."""
    maker = CurrentUser(
        user_id="user_maker_1",
        username="engineer_maker",
        email="maker@etap-ai.internal",
        role="engineer",
        tenant_id="substation_tenant",
    )

    args = {"substation_id": "SUB-4", "breaker_id": "CB-101", "command": "TRIP"}
    action = PendingAction(
        id="act_critical_001",
        tenant_id="substation_tenant",
        session_id="sess_maker_01",
        tool="scada_breaker_trip",
        args=args,
        args_hash=compute_args_hash(args),
        risk_class=_RISK_CRITICAL,
        requested_by_user_id=maker.user_id,
        requested_by_role=maker.role,
        status=_STATUS_PENDING,
        expires_at=_utc_now() + timedelta(seconds=300),
    )
    async_db.add(action)
    await async_db.commit()

    # Maker attempts self-approval -> MUST raise 403 MAKER_CHECKER_VIOLATION
    decision_req = ResolveRequest(
        decision="approve",
        reason="Self-approval attempt",
    )

    with pytest.raises(HTTPException) as exc:
        await resolve_action(
            action_id=action.id,
            body=decision_req,
            user=maker,
            db=async_db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail.get("code") == MAKER_CHECKER_VIOLATION


@pytest.mark.asyncio
async def test_dual_control_checker_approval_success(async_db: AsyncSession):
    """Verify a second independent engineer (Checker) can approve the critical action."""
    args = {"relay_id": "R-501", "pickup_setting": 4.5}
    action = PendingAction(
        id="act_critical_002",
        tenant_id="substation_tenant",
        session_id="sess_maker_02",
        tool="relay_curve_update",
        args=args,
        args_hash=compute_args_hash(args),
        risk_class=_RISK_CRITICAL,
        requested_by_user_id="user_maker_1",
        requested_by_role="engineer",
        status=_STATUS_PENDING,
        expires_at=_utc_now() + timedelta(seconds=300),
    )
    async_db.add(action)
    await async_db.commit()

    checker = CurrentUser(
        user_id="user_checker_2",
        username="lead_checker",
        email="checker@etap-ai.internal",
        role="admin",
        tenant_id="substation_tenant",
    )

    decision_req = ResolveRequest(
        decision="approve",
        reason="Verified coordination margin and selectivity, approved for field deployment.",
    )

    res = await resolve_action(
        action_id=action.id,
        body=decision_req,
        user=checker,
        db=async_db,
    )

    assert res["success"] is True
    assert res["data"]["status"] == _STATUS_APPROVED
    assert res["data"]["decided_by_user_id"] == "user_checker_2"
    assert res["data"]["resolved_at"] is not None


@pytest.mark.asyncio
async def test_dual_control_checker_rejection(async_db: AsyncSession):
    """Verify Checker can reject an unsafe proposed engineering action."""
    args = {"breaker_id": "CB-101", "action": "RECLOSE"}
    action = PendingAction(
        id="act_critical_003",
        tenant_id="substation_tenant",
        session_id="sess_maker_03",
        tool="scada_breaker_reclose",
        args=args,
        args_hash=compute_args_hash(args),
        risk_class=_RISK_CRITICAL,
        requested_by_user_id="user_maker_1",
        requested_by_role="engineer",
        status=_STATUS_PENDING,
        expires_at=_utc_now() + timedelta(seconds=300),
    )
    async_db.add(action)
    await async_db.commit()

    checker = CurrentUser(
        user_id="user_checker_2",
        username="lead_checker",
        email="checker@etap-ai.internal",
        role="admin",
        tenant_id="substation_tenant",
    )

    decision_req = ResolveRequest(
        decision="reject",
        reason="Downstream fault is not cleared. Reclosing rejected for safety.",
    )

    res = await resolve_action(
        action_id=action.id,
        body=decision_req,
        user=checker,
        db=async_db,
    )

    assert res["success"] is True
    assert res["data"]["status"] == _STATUS_REJECTED
    assert res["data"]["decided_by_user_id"] == "user_checker_2"


@pytest.mark.asyncio
async def test_dual_control_cross_tenant_forbidden(async_db: AsyncSession):
    """Verify a user from another tenant cannot resolve or access pending action."""
    args = {"breaker_id": "CB-999", "action": "TRIP"}
    action = PendingAction(
        id="act_critical_004",
        tenant_id="substation_tenant",
        session_id="sess_maker_04",
        tool="scada_breaker_trip",
        args=args,
        args_hash=compute_args_hash(args),
        risk_class=_RISK_CRITICAL,
        requested_by_user_id="user_maker_1",
        requested_by_role="engineer",
        status=_STATUS_PENDING,
        expires_at=_utc_now() + timedelta(seconds=300),
    )
    async_db.add(action)
    await async_db.commit()

    foreign_checker = CurrentUser(
        user_id="user_foreign_3",
        username="foreign_checker",
        email="foreign@other-org.internal",
        role="admin",
        tenant_id="other_tenant",
    )

    decision_req = ResolveRequest(
        decision="approve",
        reason="Attempting cross-tenant approval",
    )

    with pytest.raises(HTTPException) as exc:
        await resolve_action(
            action_id=action.id,
            body=decision_req,
            user=foreign_checker,
            db=async_db,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail.get("code") == CROSS_TENANT_FORBIDDEN
