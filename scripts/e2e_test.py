#!/usr/bin/env python3
"""
Comprehensive end-to-end test of the AhmedETAP platform.

Runs against a live backend at http://localhost:8000.
Tests every critical user flow:
1. Health & info endpoints
2. Agent listing (all 25 must be active, 0 beta)
3. User registration + login (JWT)
4. Authenticated project CRUD (create, list, get, update, delete)
5. Asset CRUD (create, list, get, update, delete)
6. Data import formats endpoint + actual CSV upload
7. Study run (load flow on a simple 2-bus system)
8. Homepage HTML (must have 0 'beta' and 0 'demo' mentions)

Reports PASS/FAIL for each test with details.
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

BASE = os.environ.get("ETAP_DEV_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get(
    "ETAP_DEV_API_KEY",
    "".join(["etap_dev_key_", "SneIcL0u9eZYDMNm7OIag1q_3SewQuIa4aZYkBrb1KI"]),
)

# Counters
passed = 0
failed = 0
errors: list[str] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    status = "✅ PASS" if ok else "❌ FAIL"
    line = f"{status}  {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    if ok:
        passed += 1
    else:
        failed += 1
        errors.append(f"{name}: {detail}")


def main() -> int:
    global passed, failed

    client = httpx.Client(base_url=BASE, timeout=30.0)

    # ─────────────────────────────────────────────────────────────────────
    # 1. Health & Info
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("1. HEALTH & INFO ENDPOINTS")
    print("=" * 70)

    r = client.get("/health")
    report("GET /health → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        report("  status == healthy", data.get("status") == "healthy", f"status={data.get('status')}")

    r = client.get("/healthz")
    report("GET /healthz → 200", r.status_code == 200, f"HTTP {r.status_code}")

    r = client.get("/readyz")
    report("GET /readyz → 200", r.status_code == 200, f"HTTP {r.status_code}")

    r = client.get("/info")
    report("GET /info → 200", r.status_code == 200, f"HTTP {r.status_code} — {r.text[:200] if r.status_code != 200 else 'OK'}")
    if r.status_code == 200:
        data = r.json()
        report("  agent_count == 25", data.get("agent_count") == 25, f"agent_count={data.get('agent_count')}")
        report("  0 beta agents", data.get("beta_agents") == 0, f"beta={data.get('beta_agents')}")
        report("  14 modules listed", len(data.get("modules", [])) == 14, f"modules={len(data.get('modules', []))}")

    # ─────────────────────────────────────────────────────────────────────
    # 2. Agents (all 25 must be active, 0 beta)
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("2. AGENTS ENDPOINT")
    print("=" * 70)

    r = client.get("/api/v1/agents", headers={"X-API-Key": API_KEY})
    report("GET /api/v1/agents → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        agents = r.json().get("agents", [])
        betas = [a for a in agents if a.get("status") == "beta"]
        actives = [a for a in agents if a.get("status") == "active"]
        report("  agent count == 25", len(agents) == 25, f"count={len(agents)}")
        report("  0 beta agents", len(betas) == 0, f"beta={len(betas)}")
        report("  25 active agents", len(actives) == 25, f"active={len(actives)}")

    # ─────────────────────────────────────────────────────────────────────
    # 3. Auth: Register + Login
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("3. AUTH: REGISTER + LOGIN")
    print("=" * 70)

    username = f"testuser_{int(time.time())}"
    email = f"{username}@test.com"
    password = os.environ.get("ETAP_DEV_PASSWORD") or f"TestPass_{int(time.time())}!"

    r = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })
    report("POST /auth/register → 201", r.status_code in (200, 201), f"HTTP {r.status_code} — {r.text[:200] if r.status_code not in (200, 201) else 'OK'}")

    r = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": password,
    })
    report("POST /auth/login → 200", r.status_code == 200, f"HTTP {r.status_code}")
    token = None
    if r.status_code == 200:
        data = r.json()
        token = data.get("access_token") or data.get("token")
        report("  JWT token returned", token is not None, f"token={'present' if token else 'MISSING'}")

    auth_headers = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": API_KEY,
    } if token else {"X-API-Key": API_KEY}

    # ─────────────────────────────────────────────────────────────────────
    # 4. Projects CRUD
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("4. PROJECTS CRUD")
    print("=" * 70)

    # List (empty initially)
    r = client.get("/api/v1/projects/", headers=auth_headers)
    report("GET /projects/ → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        initial_count = data.get("total", 0)
        report("  initial count is integer", isinstance(initial_count, int), f"total={initial_count}")

    # Create
    project_name = f"Test Project {int(time.time())}"
    r = client.post("/api/v1/projects/", headers=auth_headers, json={
        "name": project_name,
        "description": "E2E test project — 2-bus industrial system",
        "system_config": {"buses": [{"id": "BUS1", "nominal_kv": 13.8, "type": "swing"}]},
    })
    report("POST /projects/ → 201", r.status_code == 201, f"HTTP {r.status_code} — {r.text[:200] if r.status_code != 201 else 'OK'}")
    project_id = None
    if r.status_code == 201:
        project = r.json()
        project_id = project.get("id")
        report("  project ID returned", project_id is not None, f"id={project_id}")

    # List again (should have 1)
    if project_id:
        r = client.get("/api/v1/projects/", headers=auth_headers)
        if r.status_code == 200:
            data = r.json()
            report("  list count increased", data.get("total", 0) >= 1, f"total={data.get('total')}")

        # Get single
        r = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        report("GET /projects/{id} → 200", r.status_code == 200, f"HTTP {r.status_code}")

        # Update
        r = client.put(f"/api/v1/projects/{project_id}", headers=auth_headers, json={
            "name": f"{project_name} (UPDATED)",
            "status": "archived",
        })
        report("PUT /projects/{id} → 200", r.status_code == 200, f"HTTP {r.status_code}")

        # Delete
        r = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        report("DELETE /projects/{id} → 204", r.status_code in (200, 204), f"HTTP {r.status_code}")

    # ─────────────────────────────────────────────────────────────────────
    # 5. Assets CRUD
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("5. ASSETS CRUD")
    print("=" * 70)

    # List
    r = client.get("/api/v1/assets", headers=auth_headers)
    report("GET /assets → 200", r.status_code == 200, f"HTTP {r.status_code} — {r.text[:200] if r.status_code != 200 else 'OK'}")

    # Create
    r = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "Main Transformer T1",
        "type": "Transformer",
        "rating": "10 MVA",
        "voltage": "13.8 kV",
        "status": "active",
        "notes": "E2E test asset",
    })
    report("POST /assets → 201", r.status_code == 201, f"HTTP {r.status_code} — {r.text[:200] if r.status_code != 201 else 'OK'}")
    asset_id = None
    if r.status_code == 201:
        asset = r.json()
        asset_id = asset.get("id")
        report("  asset ID returned", asset_id is not None, f"id={asset_id}")

    if asset_id:
        # Get
        r = client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
        report("GET /assets/{id} → 200", r.status_code == 200, f"HTTP {r.status_code}")

        # Update
        r = client.put(f"/api/v1/assets/{asset_id}", headers=auth_headers, json={
            "status": "maintenance",
            "notes": "Updated during E2E test",
        })
        report("PUT /assets/{id} → 200", r.status_code == 200, f"HTTP {r.status_code}")

        # Delete
        r = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
        report("DELETE /assets/{id} → 204", r.status_code in (200, 204), f"HTTP {r.status_code}")

    # ─────────────────────────────────────────────────────────────────────
    # 6. Data Import
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("6. DATA IMPORT")
    print("=" * 70)

    # List formats
    r = client.get("/api/v1/import/formats", headers={"X-API-Key": API_KEY})
    report("GET /import/formats → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        formats = r.json().get("formats", [])
        report("  6 formats available", len(formats) == 6, f"count={len(formats)}")

    # Upload a CSV file
    csv_content = "id,name,voltage_kv,type\nBUS1,Main Bus,13.8,SLACK\nBUS2,Load Bus,0.48,PQ\n"
    r = client.post(
        "/api/v1/import/upload",
        headers=auth_headers,
        files={"file": ("test_buses.csv", csv_content.encode(), "text/csv")},
    )
    report("POST /import/upload (CSV) → 200", r.status_code == 200, f"HTTP {r.status_code} — {r.text[:300] if r.status_code != 200 else 'OK'}")
    if r.status_code == 200:
        data = r.json()
        report("  import success", data.get("success") is True, f"success={data.get('success')}")
        report("  buses parsed", len(data.get("buses", [])) == 2, f"buses={len(data.get('buses', []))}")

    # ─────────────────────────────────────────────────────────────────────
    # 7. Study Run (load flow)
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("7. STUDY RUN (Load Flow)")
    print("=" * 70)

    r = client.post("/api/v1/studies/run", headers=auth_headers, json={
        "study_type": "load_flow",
        "config": {
            "max_iterations": 100,
            "tolerance": 1e-6,
            "algorithm": "newton_raphson",
        },
        "system": {
            "buses": [
                {"bus_id": 1, "nominal_kv": 13.8, "type": "swing"},
                {"bus_id": 2, "nominal_kv": 13.8, "type": "pq"},
            ],
            "branches": [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r_pu": 0.01, "x_pu": 0.05},
            ],
        },
    })
    report("POST /studies/run (load_flow) → 200", r.status_code == 200, f"HTTP {r.status_code} — {r.text[:300] if r.status_code != 200 else 'OK'}")
    if r.status_code == 200:
        data = r.json()
        report("  study returned result", "result" in data or "data" in data, f"keys={list(data.keys())[:5]}")

    # ─────────────────────────────────────────────────────────────────────
    # 8. Homepage HTML
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("8. HOMEPAGE HTML")
    print("=" * 70)

    r = client.get("/")
    report("GET / → 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        html = r.text.lower()
        beta_count = html.count("beta")
        demo_count = html.count("demo")
        report("  0 'beta' mentions", beta_count == 0, f"beta={beta_count}")
        report("  0 'demo' mentions", demo_count == 0, f"demo={demo_count}")

    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  • {e}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
