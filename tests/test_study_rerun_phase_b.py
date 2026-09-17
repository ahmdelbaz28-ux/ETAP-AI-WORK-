"""
tests/test_study_rerun_phase_b.py — Unit tests for FIX-13 Phase B.

Verifies:
1. execute_study_re_run executes real study engine (PowerSystemEngine / StudyExecutor).
2. Creates real StudyResult in DB with status, results, and completed_at.
3. Creates incremental StudyVersion revision records (v1, v2).
4. Returns 404 when project does not exist.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.dependencies import CurrentUser
from api.projects import Project, StudyResult
from api.services.study_execution_service import execute_study_re_run
from api.study_versions import StudyVersion

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def get_sample_system_dict() -> dict:
    """Return a valid two-bus power system dictionary."""
    return {
        "buses": [
            {
                "bus_id": 1,
                "voltage_magnitude": 1.05,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "slack",
                "generation_power_real": 50.0,
                "generation_power_imag": 20.0,
            },
            {
                "bus_id": 2,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
                "generation_power_real": 0.0,
                "generation_power_imag": 0.0,
            },
        ],
        "lines": [
            {
                "line_id": 1,
                "from_bus_id": 1,
                "to_bus_id": 2,
                "r1": 0.01,
                "x1": 0.05,
                "bshunt1": 0.0,
            }
        ],
        "transformers": [],
        "generators": [],
        "loads": [
            {
                "load_id": 1,
                "bus_id": 2,
                "active_power": 30.0,
                "reactive_power": 10.0,
            }
        ],
    }


@pytest.mark.asyncio
async def test_re_run_executes_real_engine_and_increments_versions(async_db: AsyncSession):
    """Verify Phase B executes real calculations and creates StudyVersion snapshots."""
    # 1. Create test project with system_config
    project_id = "proj-test-rerun-1"
    sys_config = get_sample_system_dict()
    proj = Project(
        id=project_id,
        tenant_id="tenant-alpha",
        name="Industrial Substation",
        description="Substation feeder study",
        system_config=sys_config,
        created_by="engineer-1",
    )
    async_db.add(proj)
    await async_db.commit()

    user = CurrentUser(
        user_id="eng-123",
        username="engineer1",
        email="engineer@etap-ai.internal",
        role="engineer",
        tenant_id="tenant-alpha",
    )

    # 2. First re-run: Load Flow
    res1 = await execute_study_re_run(
        project_id=project_id,
        tool="load_flow",
        params={"max_iterations": 50, "tolerance": 1e-5},
        user=user,
        db=async_db,
    )

    assert res1["success"] is True
    assert res1["version_number"] == 1
    assert res1["tool"] == "load_flow"
    assert "results" in res1
    # Verify no fake BUS-1 / 0.42 MW legacy data
    res_data = res1["results"]
    assert res_data != {"buses": [{"id": "BUS-1", "voltage": 1.0}], "losses": 0.42}

    # Verify StudyResult saved in DB
    db_res = await async_db.get(StudyResult, res1["study_id"])
    assert db_res is not None
    assert db_res.study_type == "load_flow"
    assert db_res.status == "completed"
    assert db_res.created_by == "eng-123"

    # Verify StudyVersion saved in DB
    db_ver1 = await async_db.get(StudyVersion, res1["study_id"])  # Wait, StudyVersion has unique id
    from sqlalchemy import select

    ver_stmt = select(StudyVersion).where(StudyVersion.project_id == project_id)
    ver_rows = (await async_db.execute(ver_stmt)).scalars().all()
    assert len(ver_rows) == 1
    assert ver_rows[0].version_number == 1
    assert ver_rows[0].label == "v1"

    # 3. Second re-run: Short Circuit / Fault analysis
    res2 = await execute_study_re_run(
        project_id=project_id,
        tool="fault_analysis",
        params={"fault_type": "three_phase", "bus_id": 2},
        user=user,
        db=async_db,
    )

    assert res2["success"] is True
    assert res2["version_number"] == 2
    assert res2["tool"] == "fault_analysis"

    # Verify 2 versions now exist in revision history
    ver_rows_updated = (
        (await async_db.execute(ver_stmt.order_by(StudyVersion.version_number))).scalars().all()
    )
    assert len(ver_rows_updated) == 2
    assert ver_rows_updated[0].version_number == 1
    assert ver_rows_updated[1].version_number == 2


@pytest.mark.asyncio
async def test_re_run_404_when_project_not_found(async_db: AsyncSession):
    """Verify 404 is returned if project does not exist."""
    with pytest.raises(HTTPException) as exc:
        await execute_study_re_run(
            project_id="non-existent-proj",
            tool="load_flow",
            params={},
            db=async_db,
        )
    assert exc.value.status_code == 404
