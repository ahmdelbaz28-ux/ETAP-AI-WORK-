"""
api/export.py — Advanced Export Service.

Provides:
- PDF export with ReportLab
- Excel export with openpyxl
- Custom report templates
- Export history tracking

Exposes endpoints under ``/api/v1/export``:
* ``POST /{project_id}/pdf``     — Export study results as PDF
* ``POST /{project_id}/excel``   — Export study results as Excel
* ``GET  /history``              — List export history
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime
from typing import Optional

UTC = UTC

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    DateTime,
    String,
    desc,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    pagination_params,
)
from api.rbac import require_permission


class ExportHistory(Base):
    """Track export operations."""

    __tablename__ = "export_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    study_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    export_type: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf, excel, csv
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    study_id: Optional[str] = None
    export_type: str
    file_name: str
    file_size_bytes: Optional[int] = None
    created_by: str = ""
    created_at: Optional[datetime] = None


class ExportHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    exports: list[ExportResponse]
    total: int


router = APIRouter(prefix="/api/v1/export", tags=["Export"])


async def _get_project_studies(project_id: str, db: AsyncSession) -> list:
    from api.projects import StudyResult
    result = await db.execute(
        select(StudyResult).where(StudyResult.project_id == project_id)
        .order_by(desc(StudyResult.created_at))
    )
    return result.scalars().all()


def _generate_pdf(project_name: str, studies: list) -> bytes:
    """Generate a PDF report using ReportLab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        # Fallback: return a simple text-based PDF
        content = f"PDF Export - {project_name}\n\n"
        for s in studies:
            content += f"Study: {s.study_type} - Status: {s.status}\n"
        return content.encode("utf-8")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"Project Report: {project_name}", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    elements.append(Spacer(1, 24))

    # Studies table
    data = [["Study Type", "Status", "Created", "Results"]]
    for s in studies:
        results_summary = ""
        if s.results:
            results_summary = ", ".join(list(s.results.keys())[:3])
        data.append([
            s.study_type,
            s.status,
            s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
            results_summary,
        ])

    table = Table(data, colWidths=[120, 80, 100, 200])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _generate_excel(project_name: str, studies: list) -> bytes:
    """Generate an Excel file using openpyxl."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        # Fallback: return CSV
        content = "Study Type,Status,Created,Results\n"
        for s in studies:
            results_str = json.dumps(s.results) if s.results else ""
            content += f"{s.study_type},{s.status},{s.created_at},{results_str}\n"
        return content.encode("utf-8")

    wb = Workbook()
    ws = wb.active
    ws.title = "Study Results"

    # Header styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

    # Headers
    headers = ["Study Type", "Status", "Created At", "Results Summary"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Data
    for row, s in enumerate(studies, 2):
        ws.cell(row=row, column=1, value=s.study_type)
        ws.cell(row=row, column=2, value=s.status)
        ws.cell(row=row, column=3, value=str(s.created_at) if s.created_at else "")
        ws.cell(row=row, column=4, value=json.dumps(s.results) if s.results else "")

    # Auto-adjust column widths
    for col in range(1, 5):
        ws.column_dimensions[chr(64 + col)].width = 20

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


@router.post("/{project_id}/pdf")
async def export_pdf(
    project_id: str, db,
    user: CurrentUser = Depends(require_permission("export", "create")),
):
    """Export study results as PDF."""
    from api.projects import Project
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    studies = await _get_project_studies(project_id, db)
    pdf_bytes = _generate_pdf(project.name, studies)

    # Record export
    export = ExportHistory(
        id=str(uuid.uuid4()), project_id=project_id, export_type="pdf",
        file_name=f"{project.name}_report.pdf", file_size_bytes=len(pdf_bytes),
        created_by=user.user_id,
    )
    db.add(export)
    await db.flush()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_report.pdf"'},
    )


@router.post("/{project_id}/excel")
async def export_excel(
    project_id: str, db,
    user: CurrentUser = Depends(require_permission("export", "create")),
):
    """Export study results as Excel."""
    from api.projects import Project
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    studies = await _get_project_studies(project_id, db)
    excel_bytes = _generate_excel(project.name, studies)

    export = ExportHistory(
        id=str(uuid.uuid4()), project_id=project_id, export_type="excel",
        file_name=f"{project.name}_results.xlsx", file_size_bytes=len(excel_bytes),
        created_by=user.user_id,
    )
    db.add(export)
    await db.flush()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_results.xlsx"'},
    )


@router.get("/history", response_model=ExportHistoryResponse)
async def export_history(
    db,
    user: CurrentUser = Depends(require_permission("export", "list")),
    pagination: PaginationParams = Depends(pagination_params),
):
    result = await db.execute(
        select(ExportHistory).where(ExportHistory.created_by == user.user_id)
        .order_by(desc(ExportHistory.created_at))
        .offset(pagination.offset).limit(pagination.page_size)
    )
    exports = result.scalars().all()
    count = await db.execute(
        select(func.count()).select_from(ExportHistory)
        .where(ExportHistory.created_by == user.user_id)
    )
    total = count.scalar_one()
    return ExportHistoryResponse(
        exports=[ExportResponse(
            id=str(e.id), project_id=e.project_id, study_id=e.study_id,
            export_type=e.export_type, file_name=e.file_name,
            file_size_bytes=e.file_size_bytes, created_by=e.created_by,
            created_at=e.created_at,
        ) for e in exports],
        total=total,
    )
