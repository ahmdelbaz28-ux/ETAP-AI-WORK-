"""
tests/test_hf_space_data_survival.py — Data Survival Across HF Space Restarts.

Verifies the Mission A4 requirement:
Proves definitively that user accounts, projects, and study results persist
intact across application restarts and lifecycle restarts when using a persistent database.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from api.auth import User
from api.database import (
    _build_sqlite_engine,
    _rebind_session,
    async_session,
    close_db,
    init_db,
)
from api.projects import Project, ProjectStatus, StudyResult, StudyStatus


def _load_hf_app():
    """Load hf-space/app.py dynamically."""
    app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    if not app_path.exists():
        pytest.skip(f"hf-space/app.py not found at {app_path}")
    spec = importlib.util.spec_from_file_location("hf_app_survival", app_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hf_app_survival"] = mod
    spec.loader.exec_module(mod)
    return mod.app


@pytest.mark.asyncio
async def test_hf_space_data_survival_across_restarts(tmp_path, monkeypatch):
    """
    Simulate a full Space lifecycle:
    1. First Boot: Initialize DB with persistent SQLite, create user + project + study result.
    2. Record version and timestamp.
    3. Simulate Space Shutdown & Restart (dispose engine, recreate app context against same DB).
    4. Second Boot: Verify identical data exists and matches perfectly.
    """
    db_file = tmp_path / "persistent_etap.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ALLOW_SQLITE_IN_PROD", "true")

    # ─── 1. FIRST BOOT: Initialize & Insert Entities ────────────────────────
    engine1 = _build_sqlite_engine(db_url)
    _rebind_session(engine1)
    await init_db()

    user_id = str(uuid.uuid4())
    username = f"survival_user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    hashed = "$2b$12$e8Y6B8K1Z5yv0q1l7s7vE.gK2qW4p5k6m7n8o9p0q1r2s3t4u5v6w"

    project_id = str(uuid.uuid4())
    project_name = "Substation 115kV Grid Expansion"
    system_config = {
        "base_mva": 100.0,
        "buses": [{"bus_id": 1, "name": "Bus1", "base_kv": 115.0}],
    }

    study_id = str(uuid.uuid4())
    study_type = "load_flow"
    study_results = {
        "converged": True,
        "iterations": 4,
        "losses_mw": 0.35,
    }

    boot1_time = datetime.now(timezone.utc)

    async with async_session() as session:
        # Create user
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=hashed,
            is_active=True,
            created_at=boot1_time,
        )
        session.add(user)

        # Create project
        project = Project(
            id=project_id,
            name=project_name,
            description="Mission-critical persistence validation project",
            status=ProjectStatus.ACTIVE.value,
            system_config=system_config,
            created_by=user_id,
            created_at=boot1_time,
            updated_at=boot1_time,
        )
        session.add(project)

        # Create study result
        study_result = StudyResult(
            id=study_id,
            project_id=project_id,
            study_type=study_type,
            status=StudyStatus.COMPLETED.value,
            config={"tol": 1e-6},
            results=study_results,
            created_by=user_id,
            created_at=boot1_time,
            completed_at=boot1_time,
        )
        session.add(study_result)
        await session.commit()

    # ─── 2. SIMULATE SPACE RESTART / RE-BOOT ─────────────────────────────────
    await close_db()

    # Verify that the DB file physically exists and contains data
    assert db_file.exists()
    assert db_file.stat().st_size > 0

    # ─── 3. SECOND BOOT: Re-initialize and Verify Persistence ────────────────
    engine2 = _build_sqlite_engine(db_url)
    _rebind_session(engine2)
    await init_db()

    async with async_session() as session:
        # Verify User survived
        user_stmt = select(User).where(User.id == user_id)
        res_user = await session.execute(user_stmt)
        recovered_user = res_user.scalar_one_or_none()
        assert recovered_user is not None, "User record was lost during Space restart!"
        assert recovered_user.username == username
        assert recovered_user.email == email

        # Verify Project survived
        proj_stmt = select(Project).where(Project.id == project_id)
        res_proj = await session.execute(proj_stmt)
        recovered_project = res_proj.scalar_one_or_none()
        assert recovered_project is not None, "Project record was lost during Space restart!"
        assert recovered_project.name == project_name
        assert recovered_project.system_config == system_config

        # Verify Study Result survived
        study_stmt = select(StudyResult).where(StudyResult.id == study_id)
        res_study = await session.execute(study_stmt)
        recovered_study = res_study.scalar_one_or_none()
        assert recovered_study is not None, "Study Result record was lost during Space restart!"
        assert recovered_study.study_type == study_type
        assert recovered_study.results["converged"] is True
        assert recovered_study.results["losses_mw"] == 0.35

    await close_db()


@pytest.mark.asyncio
async def test_hf_space_version_and_health_integrity(monkeypatch):
    """Verify that /version and /healthz endpoints reflect runtime state consistently."""
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setenv("DEPLOY_SHA", "commit_sha_survival_gate_proof_2026")
    monkeypatch.setenv("ALLOW_SQLITE_IN_PROD", "true")
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-key-ci")
    monkeypatch.setenv("HF_API_KEY", "test-key-ci")

    app = _load_hf_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Version endpoint
        resp_ver = await client.get("/version")
        assert resp_ver.status_code == 200
        data_ver = resp_ver.json()
        assert data_ver.get("commit_sha") == "commit_sha_survival_gate_proof_2026"
        assert "version" in data_ver
        assert "environment" in data_ver

        # 2. Health endpoint
        resp_health = await client.get("/healthz")
        assert resp_health.status_code == 200
        data_health = resp_health.json()
        assert data_health.get("status") in ("ok", "healthy", "degraded")
        assert "database" in data_health
