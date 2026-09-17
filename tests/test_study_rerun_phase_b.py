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


@pytest.mark.asyncio
async def test_re_run_422_when_system_config_missing(async_db: AsyncSession):
    """Verify 422 is returned when both params['system'] and project.system_config are absent."""
    project_id = "proj-no-system-config"
    proj = Project(
        id=project_id,
        tenant_id="tenant-beta",
        name="Empty Project",
        description="No system data attached",
        system_config=None,
        created_by="engineer-2",
    )
    async_db.add(proj)
    await async_db.commit()

    user = CurrentUser(
        user_id="eng-456",
        username="engineer2",
        email="eng2@etap-ai.internal",
        role="engineer",
        tenant_id="tenant-beta",
    )

    with pytest.raises(HTTPException) as exc:
        await execute_study_re_run(
            project_id=project_id,
            tool="load_flow",
            params={"max_iterations": 50},
            user=user,
            db=async_db,
        )
    assert exc.value.status_code == 422
    assert "System configuration is required for re-run" in exc.value.detail


@pytest.mark.asyncio
async def test_study_version_unique_constraint_blocks_duplicates(async_db: AsyncSession):
    """Verify UniqueConstraint('project_id', 'version_number') prevents duplicate version records."""
    import uuid

    from sqlalchemy.exc import IntegrityError

    v1 = StudyVersion(
        id=str(uuid.uuid4()),
        project_id="proj-unique-test",
        study_id="study-1",
        version_number=1,
        label="v1",
        config_snapshot={},
        created_by="eng-1",
    )
    async_db.add(v1)
    await async_db.commit()

    # Attempt to insert identical project_id and version_number
    v1_dup = StudyVersion(
        id=str(uuid.uuid4()),
        project_id="proj-unique-test",
        study_id="study-2",
        version_number=1,
        label="v1-duplicate",
        config_snapshot={},
        created_by="eng-2",
    )
    async_db.add(v1_dup)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_re_run_retry_on_version_concurrency_race(async_db: AsyncSession, monkeypatch):
    """Verify that execute_study_re_run retries and recovers when version race condition occurs."""
    project_id = "proj-race-test"
    proj = Project(
        id=project_id,
        tenant_id="tenant-gamma",
        name="Race Test Substation",
        system_config=get_sample_system_dict(),
        created_by="engineer-3",
    )
    async_db.add(proj)
    await async_db.commit()

    user = CurrentUser(
        user_id="eng-789",
        username="engineer3",
        email="eng3@etap-ai.internal",
        role="engineer",
        tenant_id="tenant-gamma",
    )

    # First re-run succeeds at version 1
    res1 = await execute_study_re_run(
        project_id=project_id,
        tool="load_flow",
        params={},
        user=user,
        db=async_db,
    )
    assert res1["version_number"] == 1

    # Second re-run: simulate get_next_revision_number returning 1 on first attempt (simulating race),
    # then 2 on subsequent attempts
    from api.services import study_execution_service

    original_get_rev = study_execution_service.get_next_revision_number
    call_count = 0

    async def mock_get_next_revision_number(db, p_id, s_id=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 1  # collision with already existing v1
        return await original_get_rev(db, p_id, s_id)

    monkeypatch.setattr(
        "api.services.study_execution_service.get_next_revision_number",
        mock_get_next_revision_number,
    )

    res2 = await execute_study_re_run(
        project_id=project_id,
        tool="load_flow",
        params={},
        user=user,
        db=async_db,
    )
    assert res2["version_number"] == 2
    assert call_count >= 2, "Retry loop should have retried after collision"


@pytest.mark.asyncio
async def test_create_version_retry_on_concurrency_collision(async_db: AsyncSession, monkeypatch):
    """Verify create_version retries and succeeds with incremented version number when collision occurs."""
    from unittest.mock import MagicMock

    from api.study_versions import VersionCreateRequest, create_version

    project_id = "proj-create-ver-retry"
    study_id = "study-create-ver-1"

    proj = Project(
        id=project_id,
        tenant_id="tenant-delta",
        name="Test Project Delta",
        created_by="eng-1",
    )
    async_db.add(proj)

    study = StudyResult(
        id=study_id,
        project_id=project_id,
        tenant_id="tenant-delta",
        study_type="load_flow",
        status="completed",
        config={"base_mva": 100.0},
        results={"buses": []},
        created_by="eng-1",
    )
    async_db.add(study)
    await async_db.commit()

    user = CurrentUser(
        user_id="eng-1",
        username="engineer1",
        email="eng1@delta.internal",
        role="engineer",
        tenant_id="tenant-delta",
    )

    # 1. Create first version
    v1 = await create_version(
        project_id=project_id,
        study_id=study_id,
        body=VersionCreateRequest(label="Baseline"),
        db=async_db,
        user=user,
    )
    assert v1.version_number == 1
    await async_db.commit()

    # 2. Simulate collision on first attempt of second create_version:
    # return version 1 (which causes IntegrityError on flush), then real query on retry.
    call_count = 0
    orig_execute = async_db.execute

    async def mock_execute(statement, *args, **kwargs):
        nonlocal call_count
        stmt_str = str(statement).lower()
        if "max" in stmt_str and "study_version" in stmt_str:
            call_count += 1
            if call_count == 1:
                mock_res = MagicMock()
                mock_res.scalar_one.return_value = 1  # collision with v1
                return mock_res
        return await orig_execute(statement, *args, **kwargs)

    monkeypatch.setattr(async_db, "execute", mock_execute)

    v2 = await create_version(
        project_id=project_id,
        study_id=study_id,
        body=VersionCreateRequest(label="Second Version"),
        db=async_db,
        user=user,
    )
    assert v2.version_number == 2
    assert call_count >= 2, "Should have retried after collision on attempt 0"


@pytest.mark.asyncio
async def test_rollback_version_retry_on_concurrency_collision(async_db: AsyncSession, monkeypatch):
    """Verify rollback_version retries and succeeds when audit version number collides."""
    from unittest.mock import MagicMock

    from api.study_versions import VersionCreateRequest, create_version, rollback_version

    project_id = "proj-rollback-retry"
    study_id = "study-rollback-1"

    proj = Project(
        id=project_id,
        tenant_id="tenant-omega",
        name="Test Project Omega",
        created_by="eng-omega",
    )
    async_db.add(proj)

    study = StudyResult(
        id=study_id,
        project_id=project_id,
        tenant_id="tenant-omega",
        study_type="load_flow",
        status="completed",
        config={"base_mva": 100.0},
        results={"v": 1.0},
        created_by="eng-omega",
    )
    async_db.add(study)
    await async_db.commit()

    user = CurrentUser(
        user_id="eng-omega",
        username="engineer_omega",
        email="eng@omega.internal",
        role="engineer",
        tenant_id="tenant-omega",
    )

    # Create v1
    v1 = await create_version(
        project_id=project_id,
        study_id=study_id,
        body=VersionCreateRequest(label="Original Snapshot"),
        db=async_db,
        user=user,
    )
    assert v1.version_number == 1

    # Create v2
    v2 = await create_version(
        project_id=project_id,
        study_id=study_id,
        body=VersionCreateRequest(label="Updated Snapshot"),
        db=async_db,
        user=user,
    )
    assert v2.version_number == 2
    await async_db.commit()

    # Simulate collision on first attempt of rollback audit snapshot:
    # return version 1 (which causes IntegrityError on flush), then real query on retry.
    call_count = 0
    orig_execute = async_db.execute

    async def mock_execute(statement, *args, **kwargs):
        nonlocal call_count
        stmt_str = str(statement).lower()
        if "max" in stmt_str and "study_version" in stmt_str:
            call_count += 1
            if call_count == 1:
                mock_res = MagicMock()
                mock_res.scalar_one.return_value = 1  # collision with v1
                return mock_res
        return await orig_execute(statement, *args, **kwargs)

    monkeypatch.setattr(async_db, "execute", mock_execute)

    # Perform rollback to v1 (pre-rollback audit snapshot will be version 3 after retry)
    res_rollback = await rollback_version(
        project_id=project_id,
        study_id=study_id,
        version_id=v1.id,
        db=async_db,
        user=user,
    )
    assert res_rollback["version"] == 1
    assert res_rollback["audit_snapshot_version"] == 3
    assert call_count >= 2, "Should have retried after collision on attempt 0"
