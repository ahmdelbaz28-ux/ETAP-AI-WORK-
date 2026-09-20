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
    """get_default_parameters should return Newton-Raphson defaults without acceleration_factor."""
    defaults = get_default_parameters()
    assert defaults["convergence_tolerance"] == DEFAULT_CONVERGENCE_TOLERANCE
    assert defaults["solver_convergence_tolerance"] == DEFAULT_CONVERGENCE_TOLERANCE
    assert defaults["max_iterations"] == DEFAULT_MAX_ITERATIONS
    assert "acceleration_factor" not in defaults


@pytest.mark.asyncio
async def test_save_and_load_persistence(async_db_session: AsyncSession):
    """Saving and loading solver parameters operates cleanly without acceleration_factor."""
    proj_id = "test-proj-persistence"
    saved = await save_solver_params(
        project_id=proj_id,
        params={"convergence_tolerance": 1e-4, "max_iterations": 80},
        db=async_db_session,
    )
    assert saved["convergence_tolerance"] == 1e-4
    assert saved["max_iterations"] == 80
    assert "acceleration_factor" not in saved

    loaded = await load_solver_params(proj_id, db=async_db_session)
    assert loaded["convergence_tolerance"] == 1e-4
    assert loaded["max_iterations"] == 80
    assert "acceleration_factor" not in loaded
