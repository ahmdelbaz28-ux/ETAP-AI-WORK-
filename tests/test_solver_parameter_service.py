"""Unit tests for api.services.solver_parameter_service.

Verifies database persistence, default parameters, and ensures acceleration_factor
is not forcefully defaulted to 1.6 on Newton-Raphson solver parameter records.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.services.solver_parameter_service import (
    DEFAULT_CONVERGENCE_TOLERANCE,
    DEFAULT_MAX_ITERATIONS,
    get_default_parameters,
    load_solver_params,
    save_solver_params,
)


@pytest.fixture
async def async_db_session():
    """Create an in-memory SQLite database session for unit testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_default_parameters():
    """get_default_parameters should return Newton-Raphson defaults without 1.6 acceleration."""
    defaults = get_default_parameters()
    assert defaults["convergence_tolerance"] == DEFAULT_CONVERGENCE_TOLERANCE
    assert defaults["solver_convergence_tolerance"] == DEFAULT_CONVERGENCE_TOLERANCE
    assert defaults["max_iterations"] == DEFAULT_MAX_ITERATIONS
    assert defaults["acceleration_factor"] is None


@pytest.mark.asyncio
async def test_save_and_load_without_acceleration_factor(async_db_session: AsyncSession):
    """Saving parameters without acceleration_factor should not inject 1.6."""
    proj_id = "test-proj-no-accel"
    saved = await save_solver_params(
        project_id=proj_id,
        params={"convergence_tolerance": 1e-4, "max_iterations": 80},
        db=async_db_session,
    )
    assert saved["convergence_tolerance"] == 1e-4
    assert saved["max_iterations"] == 80
    assert saved["acceleration_factor"] is None

    loaded = await load_solver_params(proj_id, db=async_db_session)
    assert loaded["convergence_tolerance"] == 1e-4
    assert loaded["max_iterations"] == 80
    assert loaded["acceleration_factor"] is None


@pytest.mark.asyncio
async def test_save_and_load_with_explicit_acceleration_factor(async_db_session: AsyncSession):
    """Explicit acceleration_factor should be preserved for legacy/UI compatibility."""
    proj_id = "test-proj-with-accel"
    saved = await save_solver_params(
        project_id=proj_id,
        params={"convergence_tolerance": 2e-5, "max_iterations": 60, "acceleration_factor": 1.35},
        db=async_db_session,
    )
    assert saved["acceleration_factor"] == 1.35

    loaded = await load_solver_params(proj_id, db=async_db_session)
    assert loaded["acceleration_factor"] == 1.35
