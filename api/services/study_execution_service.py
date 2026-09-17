"""Study Execution Service for Edit & Re-run workflows.

Orchestrates:
1. Updating and persisting solver parameters in the database
2. Validating the project
3. Executing the study calculation
4. Persisting StudyResult in the database
5. Creating a StudyVersion revision snapshot
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api._messages import MSG_PROJECT_NOT_FOUND
from api.dependencies import CurrentUser
from api.projects import Project, StudyResult, StudyStatus
from api.services.solver_parameter_service import save_solver_params
from api.study_versions import StudyVersion

UTC = timezone.utc


async def get_next_revision_number(
    db: AsyncSession,
    project_id: str,
    study_id: Optional[str] = None,
) -> int:
    """Safely calculate the next revision number for a project or study."""
    bind = db.get_bind()
    dialect_name = getattr(bind, "name", "")

    stmt = select(func.coalesce(func.max(StudyVersion.version_number), 0) + 1)
    if study_id:
        stmt = stmt.where(StudyVersion.study_id == study_id)
    else:
        stmt = stmt.where(StudyVersion.project_id == project_id)

    if dialect_name == "postgresql":
        stmt = stmt.with_for_update()

    res = await db.execute(stmt)
    val = res.scalar()
    return int(val) if val is not None else 1


async def execute_study_re_run(
    project_id: str,
    tool: str,
    params: Dict[str, Any],
    user: Optional[CurrentUser] = None,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Execute a study re-run with updated solver parameters.

    Persists the parameters to the database, generates/calculates the study results,
    creates a new StudyResult record, and creates an associated StudyVersion record.
    """
    if db is None:
        raise ValueError("Database session is required for execute_study_re_run")

    # 1. Verify project exists
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_PROJECT_NOT_FOUND,
        )

    # 2. Persist updated solver parameters for this project
    await save_solver_params(project_id, params, db)

    # 3. FIX-13 Phase A: Real study execution engine integration
    # Hardcoded fake results (BUS-1/BUS-2, 0.42 MW) are permanently removed.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Real study execution engine integration for project re-run is not yet connected.",
    )
