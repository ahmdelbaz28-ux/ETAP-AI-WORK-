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
        # Unpack tuple (network_dict, problems_list) returned by _extract_network_from_project_config
        extracted, problems = _extract_network_from_project_config(config)
        assert len(extracted["buses"]) == 1
        assert extracted["buses"][0]["id"] == "SS_1"
        assert len(extracted["transformers"]) == 1
        assert extracted["transformers"][0]["rating_mva"] == 25.0

    def test_extract_adms_assets_zero_guessing_rejects_missing_voltage(self):
        """Zero-guessing audit: missing voltage must NOT default to 11.0 kV."""
        config = {
            "assets": [
                {
                    "asset_id": "SS_MISSING_V",
                    "asset_type": "SUBSTATION",
                    "metadata": {"name": "Substation Without Voltage"},
                }
            ]
        }
        extracted, problems = _extract_network_from_project_config(config)
        assert len(extracted["buses"]) == 0
        assert any(p.get("reason") == "missing_voltage" for p in problems)


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

    def test_propose_from_project_creates_pending_chunks(self, draw_test_client: TestClient):
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
        assert "action_id" in body

    def test_propose_zenon_parse_failed_returns_422(
        self, draw_test_client: TestClient, full_draw_db: AsyncSession
    ):
        """Malformed zenon_network payload fails fast with 422 ZENON_PARSE_FAILED."""
        import pytest_asyncio

        from api.projects import Project

        # Add project with invalid zenon_network payload
        async def _seed():
            bad_proj = Project(
                id="PROJ_BAD_ZENON",
                tenant_id=TENANT_ID,
                name="Bad Zenon Project",
                created_by="user_eng_1",
                system_config={"zenon_network": "NOT_A_VALID_JSON_OR_CONTRACT"},
            )
            full_draw_db.add(bad_proj)
            await full_draw_db.commit()

        import asyncio

        asyncio.get_event_loop().run_until_complete(_seed())

        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_BAD_ZENON", "reason": "Deploy malformed zenon"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"]["code"] == "ZENON_PARSE_FAILED"

    def test_resolve_full_network_maker_checker_violation(self, draw_test_client: TestClient):
        """Proposer cannot self-approve their full network drawing."""
        # 1. Propose as user_eng_1
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 202
        action_id = resp.json()["action_id"]

        # 2. Try to self-approve as user_eng_1 even with admin role
        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_eng_1",
                username="engineer1",
                email="eng@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Self-approval attempt"},
        )
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "MAKER_CHECKER_VIOLATION"

    def test_resolve_full_network_admin_approves_atomic_and_verifies(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """Second admin approves: multi-chunk atomic execution and post-draw verification run."""
        # 1. Propose as engineer
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 202
        action_id = resp.json()["action_id"]

        # 2. Mock ETAP REST client for atomic execution
        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["elem_1", "elem_2", "elem_3"],
            drawing_id="DRW_FULL_TEST",
            readback_verified=True,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        # 3. Mock post-draw load flow verification to succeed
        from etap_integration.post_draw_verifier import (
            BusVerificationDetail,
            NetworkVerificationResult,
        )

        mock_verification = NetworkVerificationResult(
            passed=True,
            status="verified",
            max_voltage_diff_pct=0.45,
            bus_comparisons={
                "BUS_A": BusVerificationDetail(
                    bus_id="BUS_A",
                    expected_v_pu=1.0,
                    calculated_v_pu=1.002,
                    diff_pct=0.2,
                    passed=True,
                    message="Within tolerance",
                ),
                "BUS_B": BusVerificationDetail(
                    bus_id="BUS_B",
                    expected_v_pu=0.98,
                    calculated_v_pu=0.975,
                    diff_pct=0.45,
                    passed=True,
                    message="Within tolerance",
                ),
            },
            details={"study": "load_flow", "iterations": 3},
        )
        monkeypatch.setattr(
            draw_mod,
            "dispatch_load_flow_verification",
            AsyncMock(return_value=mock_verification),
        )

        # 4. Approve as admin_2 (different user)
        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approved by Senior Engineer / Admin"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "completed"
        assert data["plan_kind"] == "full_network"
        assert data["total_chunks"] >= 1
        assert data["executed_chunks"] >= 1
        assert data["drawing_completed"] is True
        assert data["verification_passed"] is True
        assert "verification" in data
        assert data["verification"]["status"] == "verified"

    def test_resolve_full_network_verification_out_of_tolerance_marks_failed(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """Draw succeeds but load-flow verification exceeds tolerance -> must mark action failed."""
        # 1. Propose
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 202
        action_id = resp.json()["action_id"]

        # 2. Mock ETAP REST client to succeed
        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["elem_1", "elem_2", "elem_3"],
            drawing_id="DRW_FULL_TEST",
            readback_verified=True,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        # 3. Mock verification to report tolerance exceeded
        from etap_integration.post_draw_verifier import (
            BusVerificationDetail,
            NetworkVerificationResult,
        )

        mock_fail = NetworkVerificationResult(
            passed=False,
            status="tolerance_exceeded",
            max_voltage_diff_pct=8.4,
            bus_comparisons={
                "BUS_B": BusVerificationDetail(
                    bus_id="BUS_B",
                    expected_v_pu=0.98,
                    calculated_v_pu=0.898,
                    diff_pct=8.4,
                    passed=False,
                    message="Voltage diff 8.40% exceeds tolerance 2.0%",
                )
            },
            reason="Bus BUS_B voltage variation 8.40% exceeds allowable 2.0%",
        )
        monkeypatch.setattr(
            draw_mod,
            "dispatch_load_flow_verification",
            AsyncMock(return_value=mock_fail),
        )

        # 4. Approve as admin_2
        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approved for live test"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "failed"
        assert data["drawing_completed"] is True
        assert data["verification_passed"] is False
        assert data["error"]["code"] == "VERIFICATION_TOLERANCE_EXCEEDED"
        assert data["error"]["verification_status"] == "tolerance_exceeded"
        assert "BUS_B" in data["error"]["message"]

    def test_resolve_full_network_worker_unreachable_blocked_marks_failed(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """When calculation worker is offline/unreachable, result is BLOCKED and marked failed."""
        # 1. Propose
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        assert resp.status_code == 202
        action_id = resp.json()["action_id"]

        # 2. Mock ETAP REST client to succeed
        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["elem_1", "elem_2", "elem_3"],
            drawing_id="DRW_FULL_TEST",
            readback_verified=True,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        # 3. Verification unmocked -> worker at localhost:8001 is unreachable -> returns BLOCKED

        # 4. Approve as admin_2
        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approved for live test"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "failed"
        assert data["drawing_completed"] is True
        assert data["verification_passed"] is False
        assert data["error"]["code"] == "VERIFICATION_BLOCKED"
        assert data["error"]["verification_status"] == "blocked"

    def test_resolve_full_network_missing_baseline_marks_failed(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """When baseline voltages are missing, verification cannot pass -> must fail."""
        # 1. Propose
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        action_id = resp.json()["action_id"]

        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["elem_1"],
            drawing_id="DRW_FULL_TEST",
            readback_verified=True,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        from etap_integration.post_draw_verifier import NetworkVerificationResult

        mock_missing = NetworkVerificationResult(
            passed=False,
            status="baseline_missing",
            reason="Missing baseline voltages for all buses",
        )
        monkeypatch.setattr(
            draw_mod,
            "dispatch_load_flow_verification",
            AsyncMock(return_value=mock_missing),
        )

        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approve"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "failed"
        assert data["verification_passed"] is False
        assert data["error"]["verification_status"] == "baseline_missing"

    def test_resolve_full_network_idempotency_replay_preserves_failure(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """Replaying with Idempotency-Key returns stored failed verification response, never cached success."""
        resp = draw_test_client.post(
            "/api/v1/etap/draw/from-project",
            json={"project_id": "PROJ_LIVE_1", "reason": "Deploy live drawing to ETAP"},
        )
        action_id = resp.json()["action_id"]

        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["elem_1"],
            drawing_id="DRW_FULL_TEST",
            readback_verified=True,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        from etap_integration.post_draw_verifier import NetworkVerificationResult

        mock_fail = NetworkVerificationResult(
            passed=False,
            status="tolerance_exceeded",
            reason="Bus voltage drift > 5%",
        )
        monkeypatch.setattr(
            draw_mod,
            "dispatch_load_flow_verification",
            AsyncMock(return_value=mock_fail),
        )

        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        headers = {"Idempotency-Key": "test-idem-full-draw-fail-123"}
        res1 = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approve"},
            headers=headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is False
        assert data1["status"] == "failed"

        # Replay with same idempotency key
        res2 = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approve"},
            headers=headers,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["success"] is False
        assert data2["status"] == "failed"
        assert data2["error"]["verification_status"] == "tolerance_exceeded"

    def test_resolve_single_draw_readback_failed_marks_failed(
        self, draw_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """Single-draw proposal approved, but readback_verified=False -> marks failed."""
        # 1. Propose single draw with correct schema
        plan = {
            "project_id": "PROJ_LIVE_1",
            "items": [
                {
                    "element_type": "bus",
                    "name": "B_SINGLE",
                    "properties": {"name": "B_SINGLE", "base_kv": 11.0},
                }
            ],
            "reason": "Add single bus for test",
        }
        resp = draw_test_client.post("/api/v1/etap/draw/propose", json=plan)
        assert resp.status_code == 202
        action_id = resp.json()["action_id"]

        # 2. Mock REST client with readback_verified=False
        import api.etap_draw as draw_mod

        mock_rest = AsyncMock(spec=EtapRestClient)
        mock_rest.apply_draw.return_value = DrawResult(
            created_ids=["B_SINGLE"],
            drawing_id="DRW_SINGLE_1",
            readback_verified=False,
        )
        monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: mock_rest)

        # 3. Approve as admin_2
        draw_test_client.app.dependency_overrides[get_current_user_from_header] = (
            lambda: CurrentUser(
                user_id="user_admin_2",
                username="admin2",
                email="admin2@test.local",
                role="admin",
                tenant_id=TENANT_ID,
            )
        )
        res = draw_test_client.post(
            f"/api/v1/etap/draw/{action_id}/resolve",
            json={"decision": "approve", "reason": "Approve single draw"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "failed"
        assert data["drawing_completed"] is True
        assert data["verification_passed"] is False
        assert data["error"]["code"] == "VERIFICATION_READBACK_FAILED"


class TestPostDrawVerifierFailClosed:
    """Verifies fail-closed post-draw load-flow verification contracts (P1-A)."""

    def test_empty_expected_baseline_fails_closed(self):
        """Empty expected baseline must return baseline_missing and passed=False."""
        res = verify_bus_results(expected_buses={}, calculated_buses={"B1": 1.0})
        assert res.passed is False
        assert res.status == "baseline_missing"
        assert "no verifiable buses" in res.reason.lower()

    def test_empty_calculated_results_fails_closed(self):
        """Empty calculated results must return execution_failed and passed=False."""
        res = verify_bus_results(expected_buses={"B1": 1.0}, calculated_buses={})
        assert res.passed is False
        assert res.status == "execution_failed"
        assert "empty calculation" in res.reason.lower()

    def test_missing_expected_voltage_for_source_bus_fails_closed(self):
        """Missing or None expected voltage for a source bus must fail closed."""
        res = verify_bus_results(expected_buses={"B1": None}, calculated_buses={"B1": 1.0})
        assert res.passed is False
        assert res.status == "baseline_missing"
        assert res.bus_comparisons["B1"].passed is False
        assert "baseline voltage missing" in res.bus_comparisons["B1"].message.lower()

    def test_normal_within_tolerance_passes(self):
        """Comparable buses within tolerance return passed=True and verified."""
        res = verify_bus_results(
            expected_buses={"B1": 1.0, "B2": 0.98},
            calculated_buses={"B1": 1.005, "B2": 0.985},
            tolerance_pct=2.0,
        )
        assert res.passed is True
        assert res.status == "verified"
        assert len(res.bus_comparisons) == 2

    def test_out_of_tolerance_fails(self):
        """Drift exceeding tolerance returns passed=False and tolerance_exceeded."""
        res = verify_bus_results(
            expected_buses={"B1": 1.0},
            calculated_buses={"B1": 1.05},
            tolerance_pct=2.0,
        )
        assert res.passed is False
        assert res.status == "tolerance_exceeded"
        assert res.max_voltage_diff_pct >= 5.0

    @pytest.mark.asyncio
    async def test_dispatch_empty_baseline_model_fails_closed(self):
        """dispatch_load_flow_verification with empty baseline model returns baseline_missing."""
        res = await dispatch_load_flow_verification(project_path="dummy/path.etap", baseline_model={})
        assert res.passed is False
        assert res.status == "baseline_missing"

    def test_nonfinite_nan_and_inf_in_expected_baseline_fails_closed(self):
        """NaN, +inf, -inf in expected baseline must fail closed with baseline_missing."""
        import math

        for bad_val in (float("nan"), float("inf"), float("-inf")):
            res = verify_bus_results(expected_buses={"B1": bad_val}, calculated_buses={"B1": 1.0})
            assert res.passed is False
            assert res.status == "baseline_missing"
            assert res.bus_comparisons["B1"].passed is False
            assert "baseline voltage missing or invalid" in res.bus_comparisons["B1"].message.lower()

    def test_nonfinite_nan_and_inf_in_calculated_voltages_fails_closed(self):
        """NaN, +inf, -inf in calculated results must fail closed."""
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            res = verify_bus_results(expected_buses={"B1": 1.0}, calculated_buses={"B1": bad_val})
            assert res.passed is False
            assert res.bus_comparisons["B1"].passed is False
            assert "invalid, non-finite, or non-positive" in res.bus_comparisons["B1"].message

    def test_nonnumeric_in_expected_and_calculated_fails_closed(self):
        """Nonnumeric strings or objects in expected or calculated buses must not raise unhandled exception."""
        res_exp = verify_bus_results(expected_buses={"B1": "not_a_number"}, calculated_buses={"B1": 1.0})
        assert res_exp.passed is False
        assert res_exp.status == "baseline_missing"

        res_calc = verify_bus_results(expected_buses={"B1": 1.0}, calculated_buses={"B1": "malformed_voltage"})
        assert res_calc.passed is False
        assert res_calc.bus_comparisons["B1"].passed is False

    def test_baseline_with_no_valid_numerical_comparison_fails(self):
        """A baseline where require_baseline=False but no comparison could be made fails closed."""
        res = verify_bus_results(expected_buses={"B1": None}, calculated_buses={"B1": 1.0}, require_baseline=False)
        assert res.passed is False
        assert res.status == "baseline_missing"
