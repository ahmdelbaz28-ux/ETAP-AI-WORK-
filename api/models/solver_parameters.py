"""ORM model for ProjectSolverParameters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base

UTC = timezone.utc


class ProjectSolverParameters(Base):
    """Persisted solver parameters scoped by project."""

    __tablename__ = "project_solver_parameters"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    convergence_tolerance: Mapped[float] = mapped_column(Float, nullable=False, default=1e-5)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    acceleration_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
