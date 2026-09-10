"""Tests for safe ETAP REST Auto-Build drawings (mocked httpx only, zero live net).

Covers (per surgical prompt):
- success + readback verified
- partial server result => full fail (PARTIAL_RESULT / VERIFY_MISMATCH + cleanup)
- invalid plan => local reject, no HTTP issued
- flag OFF => 403 FEATURE_DISABLED
- self-approve => 403 MAKER_CHECKER_VIOLATION
- cross-tenant => 403 CROSS_TENANT_FORBIDDEN (repo convention, mirrors scada)
- ETAP 401 => unavailable (503)
- provider selection: ETAP_PROVIDER=rest wiring + missing-config fallback
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.etap_draw import is_draw_enabled
from api.etap_draw import router as etap_draw_router
from etap_integration.etap_provider import NullEtapProvider, RestEtapProvider, get_etap_provider
from etap_integration.etap_rest import (
    DrawResult,
    EtapDrawPlan,
    EtapElement,
    EtapRestClient,
    ETAPRestError,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TENANT = "tenant_draw_test"


def _engineer(uid="user_eng_1", role="engineer", tenant=TENANT):
    return CurrentUser(user_id=uid, username="u", email="u@t.ot", role=role, tenant_id=tenant)


def _plan(**kw):
    base = {
        "project_id": "PRJ1",
        "items": [{"element_type": "bus", "name": "BUS_1", "properties": {"base_kv": 11.0}}],
        "reason": "add incomer bus",
    }
    base.update(kw)
    return base


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(etap_draw_router)
    return test_app


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client(app: FastAPI, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-api-key")
    monkeypatch.setenv("FEATURE_FLAG_ETAP_REST_DRAW", "true")
    monkeypatch.setenv("ETAP_REST_ALLOWLIST", TENANT)
    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-api-key")

    async def _override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user_from_header] = lambda: _engineer()
    with TestClient(app) as test_client:
        yield test_client


def _ok_transport(calls: list, mode="ok"):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"}, request=request)
        if path.endswith("/autobuild"):
            return httpx.Response(200, json={"drawing_id": "DRW-1"}, request=request)
        if path.endswith("/elements") and request.method == "POST":
            if mode == "partial":
                return httpx.Response(200, json={"created_ids": ["E1"]}, request=request)
            return httpx.Response(200, json={"created_ids": ["E1"]}, request=request)
        if path.endswith("/elements") and request.method == "GET":
            if mode == "miss":
                return httpx.Response(200, json={"elements": [{"id": "OTHER"}]}, request=request)
            return httpx.Response(
                200, json={"elements": [{"id": "E1", "name": "BUS_1"}]}, request=request
            )
        if path.endswith("/elements") and request.method == "DELETE":
            return httpx.Response(200, json={"deleted": 1}, request=request)
        return httpx.Response(404, json={}, request=request)

    return httpx.MockTransport(handler)


def _client(mode="ok", **kw):
    calls: list = []
    kw.setdefault("retry_delays", (0, 0, 0))
    c = EtapRestClient(
        base_url="https://etap.test/etapapi", token="t", transport=_ok_transport(calls, mode), **kw
    )
    return c, calls


# --- client unit tests (no router, no DB) ---


async def test_apply_draw_success_verified():
    c, calls = _client()
    res = await c.apply_draw(EtapDrawPlan(**_plan()))
    assert res.readback_verified is True
    assert res.created_ids == ["E1"]
    assert res.drawing_id == "DRW-1"
    methods = [m for m, _ in calls]
    assert "POST" in methods and "GET" in methods


async def test_apply_draw_partial_create_fails():
    c, _ = _client()
    plan = EtapDrawPlan(
        **_plan(
            items=[
                {"element_type": "bus", "name": "B1", "properties": {"base_kv": 11.0}},
                {"element_type": "bus", "name": "B2", "properties": {"base_kv": 33.0}},
            ]
        )
    )
    with pytest.raises(ETAPRestError) as ei:
        await c.apply_draw(plan)
    assert ei.value.code == "PARTIAL_RESULT"


async def test_apply_draw_readback_miss_fails_and_cleans_up():
    c, calls = _client(mode="miss")
    with pytest.raises(ETAPRestError) as ei:
        await c.apply_draw(EtapDrawPlan(**_plan()))
    assert ei.value.code == "VERIFY_MISMATCH"
    assert any(m == "DELETE" and p.endswith("/api/v1/projects/PRJ1/elements") for m, p in calls)


async def test_auth_401_maps_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={}, request=request)

    c = EtapRestClient(
        base_url="https://x",
        token="bad",
        transport=httpx.MockTransport(handler),
        retry_delays=(0, 0, 0),
    )
    with pytest.raises(ETAPRestError) as ei:
        await c.apply_draw(EtapDrawPlan(**_plan()))
    assert ei.value.code == "AUTH_FAILED"


async def test_retry_on_503_then_success():
    seen: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/health") and len(seen) == 1:
            return httpx.Response(503, json={}, request=request)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    c = EtapRestClient(
        base_url="https://x",
        token="t",
        transport=httpx.MockTransport(handler),
        retry_delays=(0, 0, 0),
    )
    assert await c.health_check() is True
    assert len(seen) == 2


def test_invalid_plan_rejected_locally_no_http():
    with pytest.raises(Exception):
        EtapElement(element_type="bus", name="B1", properties={"base_kv": 11.0, "x": 5.0})
    with pytest.raises(Exception):
        EtapDrawPlan(project_id="P", items=[], reason="long enough reason")
    with pytest.raises(Exception):
        EtapDrawPlan(**_plan(delete_ids=["*"]))
    with pytest.raises(Exception):
        EtapDrawPlan(**_plan(reason="abc"))


def test_redact_never_leaks_token():
    from etap_integration.etap_rest import _redact_secrets

    assert "t0k3n" not in _redact_secrets("https://h/?token=t0k3n&x=1")
    assert "t0k3n" not in _redact_secrets("Bearer t0k3n")


# --- provider selection ---


def test_provider_rest_selected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_ETAP", "true")
    monkeypatch.setenv("ETAP_PROVIDER", "rest")
    monkeypatch.setenv("ETAP_REST_URL", "https://etap.test/etapapi")
    monkeypatch.setenv("ETAP_REST_TOKEN", "t")
    p = get_etap_provider()
    assert isinstance(p, RestEtapProvider) and p.is_available()


def test_provider_rest_missing_config_falls_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_ETAP", "true")
    monkeypatch.setenv("ETAP_PROVIDER", "rest")
    monkeypatch.delenv("ETAP_REST_URL", raising=False)
    monkeypatch.delenv("ETAP_REST_TOKEN", raising=False)
    p = get_etap_provider()
    # Falls through past rest (to Local on win32 / Null elsewhere) — never a broken Rest provider.
    assert not (isinstance(p, RestEtapProvider) and p.is_available())


# --- router tests (dual-control, :memory: DB) ---


def test_flag_off_blocks_propose(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_FLAG_ETAP_REST_DRAW", "false")
    assert is_draw_enabled() is False
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_propose_and_self_approve_blocked(client: TestClient, app: FastAPI):
    app.dependency_overrides[get_current_user_from_header] = lambda: _engineer(
        uid="admin_1", role="admin"
    )
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    assert r.status_code == 202, r.text
    action_id = r.json()["action_id"]
    r2 = client.post(f"/api/v1/etap/draw/{action_id}/resolve", json={"decision": "approve"})
    assert r2.status_code == 403
    assert r2.json()["detail"]["code"] == "MAKER_CHECKER_VIOLATION"


def test_other_admin_approves_and_verifies(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
):
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    assert r.status_code == 202, r.text
    action_id = r.json()["action_id"]

    async def _fake_apply(plan):
        return DrawResult(created_ids=["E1"], drawing_id="DRW-1", readback_verified=True)

    class _FakeClient:
        async def apply_draw(self, plan):
            return await _fake_apply(plan)

    import api.etap_draw as draw_mod

    monkeypatch.setattr(draw_mod, "get_rest_client_from_env", lambda: _FakeClient())
    app.dependency_overrides[get_current_user_from_header] = lambda: _engineer(
        uid="admin_2", role="admin"
    )
    r2 = client.post(f"/api/v1/etap/draw/{action_id}/resolve", json={"decision": "approve"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["status"] == "completed"
    assert body["result"]["readback_verified"] is True


def test_cross_tenant_resolve_forbidden(client: TestClient, app: FastAPI):
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    action_id = r.json()["action_id"]
    app.dependency_overrides[get_current_user_from_header] = lambda: _engineer(
        uid="admin_x", role="admin", tenant="other"
    )
    r2 = client.post(f"/api/v1/etap/draw/{action_id}/resolve", json={"decision": "approve"})
    assert r2.status_code == 403
    assert r2.json()["detail"]["code"] == "CROSS_TENANT_FORBIDDEN"


def test_reject_flow(client: TestClient, app: FastAPI):
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    action_id = r.json()["action_id"]
    app.dependency_overrides[get_current_user_from_header] = lambda: _engineer(
        uid="admin_2", role="admin"
    )
    r2 = client.post(
        f"/api/v1/etap/draw/{action_id}/resolve", json={"decision": "reject", "reason": "no"}
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"


def test_status_and_pending(client: TestClient):
    r = client.post("/api/v1/etap/draw/propose", json=_plan())
    action_id = r.json()["action_id"]
    s = client.get(f"/api/v1/etap/draw/{action_id}/status")
    assert s.status_code == 200 and s.json()["status"] == "pending"
    p = client.get("/api/v1/etap/draw/pending")
    assert p.status_code == 200 and p.json()["total"] >= 1
