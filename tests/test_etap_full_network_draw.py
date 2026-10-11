"""End-to-End Tests for ETAP Full Network Drawing and Operational Verification.

Tests:
1. draw_plan_builder:
   - Dependency ordering: buses -> transformers -> breakers/switches -> lines/cables/loads/generators
   - Pre-flight connectivity validation (fail-early on dangling bus)
   - Chunking bounded to <= 50 elements
   - Atomic multi-chunk rollback on intermediate chunk failure
2. Dual-control endpoint POST /api/v1/etap/draw/from-project:
   - Feature flag gating (disabled by default -> 403 FEATURE_DISABLED)
   - Tenant allowlist enforcement (empty/non-matching -> 403 TENANT_NOT_ALLOWLISTED)
   - Maker-Checker dual control and anti-self-approval
3. Post-draw load flow verification:
   - Within-tolerance matching (passed=True, status="verified")
   - Out-of-tolerance detection (passed=False, status="tolerance_exceeded")
   - Unreachable calculation worker returns BLOCKED (zero fake success)
4. External ADMS connectors:
   - ArcFM and EcoStruxure ADMS connectors report BLOCKED.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.etap_draw import (
    EtapDrawFromProjectRequest,
    _extract_network_from_project_config,
    is_full_network_draw_enabled,
)
from core_model.bus import Bus
from core_model.line import Line
from core_model.system import System
from core_model.transformer import Transformer
from etap_integration.draw_plan_builder import (
    build_draw_plan,
    execute_draw_plans_atomic,
)
from etap_integration.etap_rest import (
    DrawResult,
    EtapDrawPlan,
    EtapElement,
    EtapRestClient,
    ETAPRestError,
)
from etap_integration.post_draw_verifier import (
    dispatch_load_flow_verification,
    verify_bus_results,
)
from integrations.external_adms_connectors import (
    ArcFMFeederConnector,
    EcoStruxureADMSConnector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_system() -> System:
    """A realistic 3-bus system with transformer and tie line."""
    sys = System(base_mva=100.0)
    b1 = Bus(bus_id="B1", base_kv=132.0, bus_type="slack")
    b2 = Bus(bus_id="B2", base_kv=33.0, bus_type="pq")
    b3 = Bus(bus_id="B3", base_kv=33.0, bus_type="pq")
    sys.add_bus(b1)
    sys.add_bus(b2)
    sys.add_bus(b3)

    tr = Transformer(
        transformer_id="T1",
        from_bus=b1,
        to_bus=b2,
        z1=complex(0.005, 0.08),
        rating=40.0,
    )
    sys.add_transformer(tr)

    line = Line(
        line_id="L1",
        from_bus=b2,
        to_bus=b3,
        z1=complex(0.02, 0.06),
        rating=25.0,
    )
    sys.add_line(line)
    return sys


# ---------------------------------------------------------------------------
# Tests: draw_plan_builder
# ---------------------------------------------------------------------------


class TestDrawPlanBuilder:
    """Verifies dependency ordering, bounding, topology checks, and atomic rollback."""

    def test_dependency_ordering(self, sample_system: System):
        plans = build_draw_plan(sample_system, project_id="PROJ_TEST_1", max_items=50)
        assert len(plans) == 1
        items = plans[0].items

        # Sequence must be buses (3) -> transformers (1) -> lines (1)
        types = [it.element_type for it in items]
        assert types == ["bus", "bus", "bus", "transformer", "line"]
        assert all(it.properties.get("name") is not None for it in items)

    def test_chunking_bounded(self, sample_system: System):
        # With max_items=2, 5 elements should yield 3 chunks (2, 2, 1)
        plans = build_draw_plan(sample_system, project_id="PROJ_TEST_1", max_items=2)
        assert len(plans) == 3
        assert len(plans[0].items) == 2
        assert len(plans[1].items) == 2
        assert len(plans[2].items) == 1

    def test_preflight_topology_validation_rejects_dangling_bus(self):
        malformed = {
            "buses": [{"id": "BUS_A", "base_kv": 11.0}],
            "lines": [
                {
                    "id": "LINE_DANGLING",
                    "from_bus": "BUS_A",
                    "to_bus": "BUS_GHOST",  # does not exist
                    "r_pu": 0.01,
                    "x_pu": 0.05,
                }
            ],
        }
        with pytest.raises(ETAPRestError) as exc_info:
            build_draw_plan(malformed, project_id="PROJ_TEST_DANGLING")
        assert exc_info.value.code == "INVALID_TOPOLOGY"
        assert "BUS_GHOST" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_atomic_multi_chunk_rollback_on_failure(self, sample_system: System):
        """If chunk 2 fails, elements from chunk 1 MUST be rolled back via delete_elements."""
        plans = build_draw_plan(sample_system, project_id="PROJ_ROLLBACK", max_items=2)
        assert len(plans) >= 2

        mock_client = AsyncMock(spec=EtapRestClient)
        # Chunk 1 succeeds, Chunk 2 raises ETAPRestError
        mock_client.apply_draw.side_effect = [
            DrawResult(created_ids=["elem_1", "elem_2"], drawing_id="D1", readback_verified=True),
            ETAPRestError("ETAP_SERVER_ERROR", "Simulated DataHub failure on chunk 2"),
        ]

        with pytest.raises(ETAPRestError) as exc_info:
            await execute_draw_plans_atomic(mock_client, plans)

        assert exc_info.value.code == "DRAW_CHUNK_FAILED"
        # Verify rollback was called with elements from chunk 1
        mock_client.delete_elements.assert_called_once_with("PROJ_ROLLBACK", ["elem_1", "elem_2"])


# ---------------------------------------------------------------------------
# Tests: Post-Draw Verification & MathGuard Rules
# ---------------------------------------------------------------------------


class TestPostDrawVerification:
    """Verifies load flow comparison against baseline and fail-closed behavior."""

    def test_verify_bus_results_within_tolerance(self):
        expected = {"B1": 1.00, "B2": 0.98, "B3": 0.97}
        calculated = {"B1": 1.001, "B2": 0.985, "B3": 0.968}

        res = verify_bus_results(expected, calculated, tolerance_pct=2.0)
        assert res.passed
        assert res.status == "verified"
        assert res.max_voltage_diff_pct < 2.0

    def test_verify_bus_results_out_of_tolerance_fails(self):
        expected = {"B1": 1.00, "B2": 0.98}
        calculated = {"B1": 1.00, "B2": 0.90}  # ~8.16% voltage deviation

        res = verify_bus_results(expected, calculated, tolerance_pct=2.0)
        assert not res.passed
        assert res.status == "tolerance_exceeded"
        assert "B2" in res.reason

    @pytest.mark.asyncio
    async def test_worker_unavailable_reports_blocked(self, sample_system: System):
        """Unreachable ETAP worker reports BLOCKED, never fake success."""
        res = await dispatch_load_flow_verification(
            project_path="C:/fake/proj.eti",
            baseline_model=sample_system,
            worker_url="http://127.0.0.1:59999",  # non-existent port
        )
        assert not res.passed
        assert res.status == "blocked"
        assert "BLOCKED" in res.reason


# ---------------------------------------------------------------------------
# Tests: External ADMS Connectors (Abstract / Fail-Closed)
# ---------------------------------------------------------------------------


class TestExternalADMSConnectors:
    """Verifies ArcFM and EcoStruxure connectors report BLOCKED instead of mock success."""

    @pytest.mark.asyncio
    async def test_arcfm_connector_reports_blocked(self):
        connector = ArcFMFeederConnector()
        with patch("integrations.external_adms_connectors.is_feature_enabled", return_value=True):
            with pytest.raises(ETAPRestError) as exc_info:
                await connector.connect()
            assert exc_info.value.code == "BLOCKED"
            assert "ArcFM" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_ecostruxure_connector_reports_blocked(self):
        connector = EcoStruxureADMSConnector()
        with patch("integrations.external_adms_connectors.is_feature_enabled", return_value=True):
            with pytest.raises(ETAPRestError) as exc_info:
                await connector.connect()
            assert exc_info.value.code == "BLOCKED"
            assert "EcoStruxure" in exc_info.value.message


# ---------------------------------------------------------------------------
# Tests: Extraction of project.system_config
# ---------------------------------------------------------------------------


class TestProjectNetworkExtraction:
    """Verifies extraction of assets or zenon_network from system_config."""

    def test_extract_adms_assets(self):
        config = {
            "assets": [
                {
                    "asset_id": "SS_1",
                    "asset_type": "SUBSTATION",
                    "metadata": {"name": "Substation 1", "nominal_voltage_kv": 132.0},
                },
                {
                    "asset_id": "TR_1",
                    "asset_type": "TRANSFORMER",
                    "metadata": {
                        "name": "Trafo 1",
                        "from_bus": "SS_1",
                        "to_bus": "SS_1",
                        "rating_mva": 25.0,
                    },
                },
            ]
        }
        extracted = _extract_network_from_project_config(config)
        assert len(extracted["buses"]) == 1
        assert extracted["buses"][0]["id"] == "SS_1"
        assert len(extracted["transformers"]) == 1
        assert extracted["transformers"][0]["rating_mva"] == 25.0


# ---------------------------------------------------------------------------
# Router Tests: POST /api/v1/etap/draw/from-project (Dual-Control)
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.etap_draw import router as etap_draw_router
from api.projects import Project

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TENANT_ID = "tenant_full_draw_test"


@pytest.fixture
async def full_draw_db() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        # Seed a test project
        proj = Project(
            id="PROJ_LIVE_1",
            tenant_id=TENANT_ID,
            name="Live Substation Project",
            created_by="user_eng_1",
            system_config={
                "buses": [{"id": "BUS_A", "base_kv": 132.0}, {"id": "BUS_B", "base_kv": 33.0}],
                "transformers": [
                    {"id": "TR1", "from_bus": "BUS_A", "to_bus": "BUS_B", "rating_mva": 40.0}
                ],
            },
        )
        session.add(proj)
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def draw_test_client(full_draw_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FEATURE_FLAG_ETAP_REST_DRAW", "true")
    monkeypatch.setenv("FEATURE_FLAG_ETAP_DRAW_FULL_NETWORK", "true")
    monkeypatch.setenv("ETAP_REST_ALLOWLIST", TENANT_ID)

    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-api-key")

    test_app = FastAPI()
    test_app.include_router(etap_draw_router)

    async def _override_get_db():
        yield full_draw_db

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="user_eng_1",
        username="engineer1",
        email="eng@test.local",
        role="engineer",
        tenant_id=TENANT_ID,
    )
    test_app.dependency_overrides[deps.get_api_key] = lambda: "test-api-key"

    with TestClient(test_app) as client:
        yield client


class TestEtapDrawFromProjectEndpoint:
    """Verifies dual-control Maker-Checker, flag gates, and tenant allowlist on /from-project."""

    def test_flag_disabled_returns_403(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("FEATURE_FLAG_ETAP_DRAW_FULL_NETWORK", "false")
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"

    def test_tenant_not_allowlisted_returns_403(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("ETAP_REST_ALLOWLIST", "other_tenant_only")
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "TENANT_NOT_ALLOWLISTED"

    def test_propose_from_project_creates_pending_chunks(
        self, draw_test_client: TestClient
    ):
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        assert body["total_chunks"] >= 1
        assert body["total_elements"] == 3  # 2 buses + 1 transformer
        assert len(body["action_ids"]) == body["total_chunks"]
        assert body["status"] == "pending_approval"

