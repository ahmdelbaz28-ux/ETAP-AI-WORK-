"""Study Execution Service for Edit & Re-run workflows.

Orchestrates:
1. Updating and persisting solver parameters in the database
2. Validating the project
3. Executing the study calculation
4. Persisting StudyResult in the database
5. Creating a StudyVersion revision snapshot
"""

from __future__ import annotations

import asyncio
import time
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

    Persists the parameters to the database, executes the study calculation
    using the real StudyExecutor engine (FIX-13 Phase B), creates a new StudyResult record,
    and creates an associated StudyVersion revision snapshot.
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

    # 3. FIX-13 Phase B: Real study execution engine integration
    system_data = params.get("system") or getattr(project, "system_config", None)

    from services.study_executor import _TYPES_REQUIRING_SYSTEM

    canonical_tool = tool.lower()
    if canonical_tool in ("fault_analysis", "fault"):
        canonical_tool = "short_circuit"

    if canonical_tool in _TYPES_REQUIRING_SYSTEM and not system_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="System configuration is required for re-run.",
        )

    system_spec = None
    if system_data is not None:
        if isinstance(system_data, dict):
            from core_model.specs import SystemSpec

            try:
                system_spec = SystemSpec(**system_data)
            except Exception as spec_err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid system configuration: {spec_err}",
                ) from spec_err
        else:
            system_spec = system_data

    from core_model.specs import StudyRequest
    from services.study_executor import StudyExecutor

    executor = StudyExecutor()
    task_id = f"rerun_{project_id}_{int(time.time() * 1000)}"
    request_payload = StudyRequest(
        study_type=canonical_tool,
        parameters=params,
        system=system_spec,
        task_id=task_id,
    )

    study_res = await executor.execute(request_payload)

    # 4. Persist StudyResult record in DB
    study_id = str(uuid.uuid4())
    creator_id = (
        getattr(user, "user_id", None)
        or getattr(user, "id", None)
        or getattr(project, "created_by", "system")
        or "system"
    )
    tenant_id = getattr(user, "tenant_id", None) or getattr(project, "tenant_id", None)

    status_val = StudyStatus.COMPLETED.value if study_res.success else StudyStatus.FAILED.value
    err_msg = "; ".join(study_res.errors) if study_res.errors else None

    db_study_result = StudyResult(
        id=study_id,
        tenant_id=tenant_id,
        project_id=project_id,
        study_type=tool,
        status=status_val,
        config=params,
        results=study_res.data,
        error_message=err_msg,
        completed_at=datetime.now(UTC),
        created_by=str(creator_id),
    )
    db.add(db_study_result)

    # 5. Create a StudyVersion revision snapshot with retry loop on concurrency IntegrityError
    from sqlalchemy.exc import IntegrityError

    max_retries = 3
    version_number = 1
    for attempt in range(max_retries):
        version_number = await get_next_revision_number(db, project_id)
        study_version = StudyVersion(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            study_id=study_id,
            project_id=project_id,
            version_number=version_number,
            label=f"v{version_number}",
            description=f"Re-run study using {tool}",
            config_snapshot=params,
            results_snapshot=study_res.data,
            diff_summary=f"Re-run executed with tool={tool} (status={status_val})",
            created_by=str(creator_id),
            created_at=datetime.now(UTC),
        )
        db.add(study_version)
        try:
            await db.commit()
            break
        except IntegrityError:
            await db.rollback()
            if attempt == max_retries - 1:
                raise
            # Session rollback clears uncommitted objects, so re-add db_study_result
            db.add(db_study_result)
            await asyncio.sleep(0.01 * (attempt + 1))

    return {
        "success": study_res.success,
        "project_id": project_id,
        "study_id": study_id,
        "version_number": version_number,
        "tool": tool,
        "status": status_val,
        "results": study_res.data,
        "warnings": study_res.warnings,
        "errors": study_res.errors,
    }
