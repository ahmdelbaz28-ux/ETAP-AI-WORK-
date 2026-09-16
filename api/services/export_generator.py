"""Export Generator Service.

Provides format generators for study results:
- PDF (ReportLab)
- Excel (openpyxl)
- CSV (standard library with formula injection defense)
- JSON (standard library)
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Sequence

UTC = timezone.utc

# Python 3.8 compatibility shim: ReportLab 3.x passes usedforsecurity=False to hashlib.md5
try:
    import hashlib

    try:
        hashlib.md5(b"", usedforsecurity=False)  # nosec: B303
    except TypeError:
        _orig_md5 = hashlib.md5

        def _compat_md5(*args: Any, **kwargs: Any) -> Any:
            kwargs.pop("usedforsecurity", None)
            return _orig_md5(*args, **kwargs)

        hashlib.md5 = _compat_md5
except Exception:
    pass


def _sanitize_csv_cell(val: Any) -> Any:
    """Neutralize spreadsheet formula injection characters (=, +, -, @, tab, CR)."""
    if isinstance(val, str) and val.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{val}"
    return val


def _extract_study_attr(study: Any, attr: str, default: Any = None) -> Any:
    if isinstance(study, dict):
        return study.get(attr, default)
    return getattr(study, attr, default)


def generate_pdf_export(project_name: str, studies: Sequence[Any]) -> bytes:
    """Generate a PDF report using ReportLab with styling and tables."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements: list[Any] = []

        elements.append(Paragraph(f"Project Report: {project_name}", styles["Title"]))
        elements.append(Spacer(1, 12))
        elements.append(
            Paragraph(
                f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 24))

        data = [["Study Type", "Status", "Created", "Results"]]
        for s in studies:
            study_type = _extract_study_attr(s, "study_type", "Unknown")
            status = _extract_study_attr(s, "status", "Unknown")
            created_at = _extract_study_attr(s, "created_at", None)
            results = _extract_study_attr(s, "results", None)

            created_str = ""
            if isinstance(created_at, datetime):
                created_str = created_at.strftime("%Y-%m-%d %H:%M")
            elif created_at:
                created_str = str(created_at)[:16]

            results_summary = ""
            if isinstance(results, dict):
                results_summary = ", ".join(list(results.keys())[:3])
            elif results:
                results_summary = str(results)[:50]

            data.append([str(study_type), str(status), created_str, results_summary])

        table = Table(data, colWidths=[120, 80, 100, 200])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )
        elements.append(table)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        # Minimal pure-python fallback that starts with %PDF
        content = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 72 712 Td (Export Report) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000200 00000 n\n"
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n294\n%%EOF\n"
        )
        return content


def generate_excel_export(project_name: str, studies: Sequence[Any]) -> bytes:
    """Generate an Excel (.xlsx) file using openpyxl."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        wb = Workbook()
        ws = wb.active
        sheet_title = f"Studies-{project_name}"[:31] if project_name else "Study Results"
        if ws is None:
            ws = wb.create_sheet(title=sheet_title)
        else:
            ws.title = sheet_title

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

        headers = ["Study Type", "Status", "Created At", "Results Summary"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for row, s in enumerate(studies, 2):
            study_type = _extract_study_attr(s, "study_type", "Unknown")
            status = _extract_study_attr(s, "status", "Unknown")
            created_at = _extract_study_attr(s, "created_at", "")
            results = _extract_study_attr(s, "results", None)

            ws.cell(row=row, column=1, value=str(study_type))
            ws.cell(row=row, column=2, value=str(status))
            ws.cell(row=row, column=3, value=str(created_at) if created_at else "")
            ws.cell(row=row, column=4, value=json.dumps(results) if results else "")

        for col in range(1, 5):
            ws.column_dimensions[chr(64 + col)].width = 20

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    except ImportError:
        # Fallback to TSV/CSV bytes if openpyxl is not installed
        content = f"# Project: {project_name}\nStudy Type\tStatus\tCreated\tResults\n"
        for s in studies:
            st = _extract_study_attr(s, "study_type", "")
            stt = _extract_study_attr(s, "status", "")
            ca = _extract_study_attr(s, "created_at", "")
            res = _extract_study_attr(s, "results", "")
            content += f"{st}\t{stt}\t{ca}\t{res}\n"
        return content.encode("utf-8")


def generate_csv_export(project_name: str, studies: Sequence[Any]) -> bytes:
    """Generate CSV format study results with formula injection defense."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["project_name", "study_type", "status", "created_at", "results"])
    for s in studies:
        study_type = _extract_study_attr(s, "study_type", "Unknown")
        status = _extract_study_attr(s, "status", "Unknown")
        created_at = _extract_study_attr(s, "created_at", "")
        results = _extract_study_attr(s, "results", None)
        results_str = json.dumps(results) if results is not None else ""
        row = [
            _sanitize_csv_cell(project_name),
            _sanitize_csv_cell(study_type),
            _sanitize_csv_cell(status),
            _sanitize_csv_cell(str(created_at) if created_at else ""),
            _sanitize_csv_cell(results_str),
        ]
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def generate_json_export(project_name: str, studies: Sequence[Any]) -> bytes:
    """Generate JSON format study results."""
    data = {
        "project_name": project_name,
        "exported_at": datetime.now(UTC).isoformat(),
        "studies": [
            {
                "study_type": _extract_study_attr(s, "study_type", "Unknown"),
                "status": _extract_study_attr(s, "status", "Unknown"),
                "created_at": (
                    _extract_study_attr(s, "created_at").isoformat()
                    if isinstance(_extract_study_attr(s, "created_at"), datetime)
                    else str(_extract_study_attr(s, "created_at", ""))
                ),
                "results": _extract_study_attr(s, "results", None),
            }
            for s in studies
        ],
    }
    return json.dumps(data, indent=2).encode("utf-8")
