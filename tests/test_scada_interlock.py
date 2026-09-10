"""
tests/test_scada_interlock.py — Unit tests for SCADA Engineering Interlock Engine.

Verifies:
- Signal quality validation (GOOD accepted, UNCERTAIN/BAD rejected)
- Telemetry timestamp freshness (stale timestamps rejected)
- ANSI 43 Local/Remote switch check (LOCAL mode blocks remote control)
- Load Flow contingency overload prevention (>100% thermal capacity blocked)
- Protection coordination selectivity check (IEC 60255 CTI < 0.2s blocked)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scada.interlock_engine import InterlockViolation, SCADAInterlockEngine
from scada.models import (
    ControlActionType,
    ControlCommandRequest,
    ControlProtocol,
    SignalQuality,
)

UTC = timezone.utc


@pytest.fixture
def interlock_engine() -> SCADAInterlockEngine:
    return SCADAInterlockEngine(
        max_telemetry_age_sec=10.0,
        max_line_loading_pct=100.0,
        min_coordination_margin_sec=0.2,
    )


@pytest.fixture
def sample_breaker_command() -> ControlCommandRequest:
    return ControlCommandRequest(
        device_id="CB_001",
        protocol=ControlProtocol.OPC_UA,
        action_type=ControlActionType.BREAKER_OPEN,
        target_value=0,
        reason="Scheduled maintenance on feeder 1",
    )


class TestSCADAInterlockEngine:
    def test_good_signal_quality_passes(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "REMOTE",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        # Must not raise
        interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

    def test_poor_signal_quality_rejected(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.UNCERTAIN.value,
                "control_mode": "REMOTE",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "POOR_DATA_QUALITY"
        assert "UNCERTAIN" in exc_info.value.message

    def test_stale_telemetry_rejected(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        stale_time = (datetime.now(UTC) - timedelta(seconds=25)).isoformat()
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "REMOTE",
                "timestamp": stale_time,
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "STALE_TELEMETRY"
        assert "stale" in exc_info.value.message.lower()

    def test_local_mode_blocks_remote_operation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "LOCAL",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "EQUIPMENT_IN_LOCAL_MODE"
        assert "LOCAL" in exc_info.value.message

    def test_overload_contingency_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Mock load flow overload detection."""
        class MockBranch:
            def __init__(self, bid):
                self.id = bid
                self.status = 1

        mock_network = {
            "branches": [MockBranch("CB_001")],
        }

        # Subclass engine to simulate overload branch result
        class OverloadingEngine(SCADAInterlockEngine):
            def validate_load_flow_overload(self, command, network_data=None):
                if network_data:
                    raise InterlockViolation(
                        code="INTERLOCK_OVERLOAD_PREVENTED",
                        message=f"Action on {command.device_id} causes branch Line_4 to overload at 118.5%",
                    )

        engine = OverloadingEngine()
        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            engine.pre_flight_check(sample_breaker_command, telemetry=telemetry, network_data=mock_network)

        assert exc_info.value.code == "INTERLOCK_OVERLOAD_PREVENTED"
        assert "118.5%" in exc_info.value.message

    def test_coordination_margin_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Protection margin < 0.2s must raise COORDINATION_MARGIN_VIOLATION."""
        class MockRelay:
            def __init__(self, time_val):
                self._t = time_val

            def trip_time(self, current):
                return self._t

        coordination_data = {
            "upstream_relay": MockRelay(0.35),
            "downstream_relay": MockRelay(0.25),  # Margin is 0.10s (< 0.20s standard)
            "fault_current": 10.0,
        }

        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(
                sample_breaker_command,
                telemetry=telemetry,
                coordination_data=coordination_data,
            )

        assert exc_info.value.code == "COORDINATION_MARGIN_VIOLATION"
        assert "0.100s" in exc_info.value.message

    def test_direct_branch_loading_overload_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Branch loading > 100% in network data raises INTERLOCK_OVERLOAD_PREVENTED."""
        network_data = {
            "branches": [{"id": "CB_001", "status": 1}],
            "branch_loadings": {"FEEDER_B": 108.5},
        }
        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(
                sample_breaker_command,
                telemetry=telemetry,
                network_data=network_data,
            )
        assert exc_info.value.code == "INTERLOCK_OVERLOAD_PREVENTED"
        assert "108.5%" in exc_info.value.message

    def test_direct_margin_coordination_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Coordination margin < 0.20s in coordination data raises COORDINATION_MARGIN_VIOLATION."""
        coordination_data = {"margin": 0.12, "fault_current": 8.0}
        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(
                sample_breaker_command,
                telemetry=telemetry,
                coordination_data=coordination_data,
            )
        assert exc_info.value.code == "COORDINATION_MARGIN_VIOLATION"
        assert "0.120s" in exc_info.value.message


class TestSCADAInterlockAPIGateway:
    """Tests that API layer enforces interlocks during control proposal."""

    @pytest.mark.asyncio
    async def test_propose_without_network_model_returns_422(self) -> None:
        """Breaker switching without network model branches raises 422 MISSING_NETWORK_MODEL."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from api.database import Base, get_db
        from api.dependencies import CurrentUser, get_current_user_from_header
        from api.scada import router as scada_router
        from scada.control_executor import scada_executor

        app = FastAPI()
        app.include_router(scada_router)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _override_get_db():
            async with async_session() as s:
                yield s

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="eng_user",
            username="engineer1",
            email="eng@substation.ot",
            role="engineer",
            tenant_id="tenant_empty_grid",
        )

        scada_executor.set_device_state(
            "CB_001",
            status=1,
            quality="GOOD",
            control_mode="REMOTE",
        )

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/scada/control/propose",
                    json={
                        "device_id": "CB_001",
                        "protocol": "opc_ua",
                        "action_type": "breaker_open",
                        "target_value": 0,
                        "reason": "Test no model",
                    },
                    headers={"X-API-Key": "test-key"},
                )
                assert resp.status_code == 422
                data = resp.json()
                assert data["detail"]["code"] == "MISSING_NETWORK_MODEL"
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_propose_overload_violation_returns_422(self) -> None:
        """Network model overload contingency triggers 422 INTERLOCK_OVERLOAD_PREVENTED."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from api.database import Base, get_db
        from api.dependencies import CurrentUser, get_current_user_from_header
        from api.projects import Project
        from api.scada import router as scada_router
        from scada.control_executor import scada_executor

        app = FastAPI()
        app.include_router(scada_router)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            overloaded_proj = Project(
                id="proj_overloaded",
                tenant_id="tenant_overload_test",
                name="Overloaded Grid",
                created_by="system",
                status="active",
                system_config={
                    "branches": [{"id": "CB_001", "name": "CB_001", "status": 1}],
                    "branch_loadings": {"FEEDER_LINE_3": 114.2},
                },
            )
            session.add(overloaded_proj)
            await session.commit()

        async def _override_get_db():
            async with async_session() as s:
                yield s

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="eng_user",
            username="engineer1",
            email="eng@substation.ot",
            role="engineer",
            tenant_id="tenant_overload_test",
        )

        scada_executor.set_device_state(
            "CB_001",
            status=1,
            quality="GOOD",
            control_mode="REMOTE",
        )

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/scada/control/propose",
                    json={
                        "device_id": "CB_001",
                        "protocol": "opc_ua",
                        "action_type": "breaker_open",
                        "target_value": 0,
                        "reason": "Test overload check",
                    },
                    headers={"X-API-Key": "test-key"},
                )
                assert resp.status_code == 422
                data = resp.json()
                assert data["detail"]["code"] == "INTERLOCK_OVERLOAD_PREVENTED"
                assert "114.2%" in data["detail"]["message"]
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_propose_coordination_margin_violation_returns_422(self) -> None:
        """Protection margin < 0.20s triggers 422 COORDINATION_MARGIN_VIOLATION."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from api.database import Base, get_db
        from api.dependencies import CurrentUser, get_current_user_from_header
        from api.projects import Project
        from api.scada import router as scada_router
        from scada.control_executor import scada_executor

        app = FastAPI()
        app.include_router(scada_router)

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            coord_proj = Project(
                id="proj_coord",
                tenant_id="tenant_coord_test",
                name="Coordination Grid",
                created_by="system",
                status="active",
                system_config={
                    "branches": [{"id": "CB_001", "name": "CB_001", "status": 1}],
                    "protection_settings": {
                        "CB_001": {
                            "margin": 0.14,
                            "fault_current": 12.0,
                        }
                    },
                },
            )
            session.add(coord_proj)
            await session.commit()

        async def _override_get_db():
            async with async_session() as s:
                yield s

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="eng_user",
            username="engineer1",
            email="eng@substation.ot",
            role="engineer",
            tenant_id="tenant_coord_test",
        )

        scada_executor.set_device_state(
            "CB_001",
            status=1,
            quality="GOOD",
            control_mode="REMOTE",
        )

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/scada/control/propose",
                    json={
                        "device_id": "CB_001",
                        "protocol": "opc_ua",
                        "action_type": "breaker_open",
                        "target_value": 0,
                        "reason": "Test coordination margin",
                    },
                    headers={"X-API-Key": "test-key"},
                )
                assert resp.status_code == 422
                data = resp.json()
                assert data["detail"]["code"] == "COORDINATION_MARGIN_VIOLATION"
                assert "0.140s" in data["detail"]["message"]
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()
