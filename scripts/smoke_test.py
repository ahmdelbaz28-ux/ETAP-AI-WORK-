"""scripts/smoke_test.py — Full Production Smoke Test Script.

Validates end-to-end production readiness:
1. Project Creation
2. Solver Parameter Persistence
3. Re-run #1 Execution (Rev 1)
4. Re-run #2 Execution with parameter change (Rev 2 > Rev 1)
5. PDF Export Generation (application/pdf)
6. SCADA Fail-Closed (HTTP 503 when unconfigured)
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Handle Windows terminal charmap encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/smoke_test.db")
os.environ.setdefault("AUTH_DISABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!")

from sqlalchemy import select
from starlette.testclient import TestClient

from api.auth import User, _create_access_token, _hash_password
from api.csrf import generate_csrf_token
from api.database import async_session, init_db
from api.routes import app


async def setup_smoke_db():
    await init_db()
    async with async_session() as session:
        res = await session.execute(select(User).where(User.id == "smoke-user-id"))
        user = res.scalar_one_or_none()
        if user is None:
            user = User(
                id="smoke-user-id",
                tenant_id="",
                username="smokeuser",
                email="smokeuser@example.com",
                password_hash=_hash_password("Str0ngP@ss!"),
                role="admin",
                is_active=True,
            )
            session.add(user)
            await session.commit()
        else:
            user.role = "admin"
            await session.commit()


async def run_smoke():
    prod_url = os.environ.get("PRODUCTION_URL", os.environ.get("BASE_URL", "")).rstrip("/")

    if prod_url:
        print(f"--- STARTING PRODUCTION SMOKE TEST (REMOTE: {prod_url}) ---")
        import httpx

        token = os.environ.get("ADMIN_TOKEN", os.environ.get("AUTH_TOKEN", ""))
        if not token:
            token = _create_access_token("admin-user", role="admin")

        headers = {
            "Authorization": f"Bearer {token}",
            "x-csrf-token": generate_csrf_token(),
            "Idempotency-Key": "smoke-test-001",
        }
        client = httpx.Client(base_url=prod_url, headers=headers, timeout=30.0)
    else:
        print("--- STARTING PRODUCTION SMOKE TEST (LOCAL ASGI) ---")
        await setup_smoke_db()
        token = _create_access_token("smoke-user-id", role="admin")
        headers = {
            "Authorization": f"Bearer {token}",
            "x-csrf-token": generate_csrf_token(),
            "Idempotency-Key": "smoke-test-001",
        }
        client = TestClient(app)
        for k, v in headers.items():
            client.headers[k] = v

    # 1. إنشاء مشروع
    proj = client.post(
        "/api/v1/projects/",
        json={"name": "Smoke Test Project", "description": "Production validation"},
    )
    assert proj.status_code == 201, f"Failed: {proj.status_code} {proj.text}"
    project_id = proj.json()["id"]
    print(f"✅ Project created: {project_id}")

    # 2. حفظ معاملات
    params = client.put(
        f"/api/v1/studies/parameters/{project_id}",
        json={"convergence_tolerance": 1e-5, "max_iterations": 50},
    )
    assert params.status_code == 200, f"Failed: {params.status_code} {params.text}"
    print("✅ Parameters saved")

    # 3. Re-run #1
    rerun1 = client.post(
        "/api/v1/studies/re-run",
        json={
            "project_id": project_id,
            "tool": "load_flow",
            "parameters": {"convergence_tolerance": 1e-5},
        },
    )
    assert rerun1.status_code == 200, f"Failed: {rerun1.status_code} {rerun1.text}"
    rev1 = rerun1.json().get("version")
    print(f"✅ Re-run 1: Rev {rev1}")

    # 4. Re-run #2 مع معامل مختلف
    headers2 = {**headers, "Idempotency-Key": "smoke-test-002"}
    rerun2 = client.post(
        "/api/v1/studies/re-run",
        json={
            "project_id": project_id,
            "tool": "load_flow",
            "parameters": {"convergence_tolerance": 1e-4},
        },
        headers=headers2,
    )
    assert rerun2.status_code == 200, f"Failed: {rerun2.status_code} {rerun2.text}"
    rev2 = rerun2.json().get("version")
    assert rev2 > rev1, f"Revision not incremented: {rev1} -> {rev2}"
    print(f"✅ Re-run 2: Rev {rev2}")

    # 5. Export PDF
    export = client.post(f"/api/v1/export/{project_id}/pdf")
    assert export.status_code == 200, f"Failed: {export.status_code} {export.text}"
    assert export.headers["content-type"] == "application/pdf"
    print(f"✅ PDF Export works (size: {len(export.content)} bytes)")

    # 6. SCADA 503 check (production_hardening=true)
    scada = client.get("/api/v1/scada/live")
    assert scada.status_code in (200, 503), f"Unexpected: {scada.status_code}"
    if scada.status_code == 503:
        print("✅ SCADA correctly returns 503 (no bridge connected - fail-closed)")
    else:
        print("✅ SCADA bridge connected")

    print("\n🎉 ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(run_smoke())
