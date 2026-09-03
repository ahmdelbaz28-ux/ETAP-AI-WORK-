"""
api/data_import.py — Power-system data import router (P9).

Provides endpoints for uploading, previewing (dry-run), and executing power-system
model imports in industry-standard formats:

* CIM/XML       — IEC 61970 Common Information Model
* PSS/E RAW     — Siemens PSS/E raw data format
* MATPOWER      — MATLAB MATPOWER case format
* ETAP Project  — ETAP native JSON project export
* JSON          — Generic structured power-system data
* CSV           — Comma-separated bus/branch data

Endpoints (under ``/api/v1/import``):
* ``GET  /formats``  — List supported formats with parsing capabilities.
* ``POST /preview``  — Dry-run / impact report before writing any data.
* ``POST /execute``  — Execute an approved import with Idempotency, Audit,
                       and SessionStreamHub progress.
* ``POST /upload``   — Direct upload and parse (backward compatibility).

Security & Reliability Guarantees:
- Magic bytes verification (rejects executable/corrupt payloads).
- Bounded upload size (10 MiB limit, matching P5).
- Dry-run impact analysis before database/project mutations.
- Dual-control approvals integration with maker-checker checks.
- SessionStreamHub progress streaming (no silent long operations).
- Idempotency-Key support on execute endpoints with replay prevention.
- Persistent audit logging for all preview and execute operations.
- Fail-closed XML parsing (requires defusedxml package; stdlib xml fallback is prohibited to prevent entity expansion vulnerabilities; full XML parsing support requires adding defusedxml to requirements by repository owner in fix/plan-v3-compliance).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import importlib

try:
    _defused_et = importlib.import_module("defusedxml.ElementTree")
    ET = _defused_et
except ImportError:
    ET = None  # fail-closed — guard in _parse_cim_xml triggers when defusedxml is not installed

ERR_DATA_IMPORT_DISABLED = "Data import feature is disabled"

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
)
from api.dual_control import (
    record_approval_event,
)
from api.feature_flags import is_feature_enabled
from api.results_store import (
    RESULT_FILE_MAX_BYTES,
    create_result,
    store_result_file,
)
from api.session_stream import (
    EVENT_JOB_PROGRESS,
    EVENT_RESULT_READY,
    get_hub,
)

logger = logging.getLogger("api.data_import")
UTC = timezone.utc

# Global hard limit for maximum file uploads (10 MB, consistent with P5 ResultStore).
MAX_FILE_SIZE = RESULT_FILE_MAX_BYTES  # 10 Megabytes

router = APIRouter(prefix="/api/v1/import", tags=["Data Import"])

_DECODE_WARNING = "File was not valid UTF-8; decoded as Latin-1."

# Executable signatures to reject immediately
_EXECUTABLE_SIGNATURES = (
    b"MZ",              # DOS / Windows PE
    b"\x7fELF",         # Linux ELF
    b"\xca\xfe\xba\xbe",# Mach-O / Java fat binary
    b"\xce\xfa\xed\xfe",# Mach-O 32-bit
    b"\xcf\xfa\xed\xfe",# Mach-O 64-bit
    b"\xfe\xed\xfa\xce",# Mach-O
    b"\xfe\xed\xfa\xcf",# Mach-O
)

# In-memory bounded preview store
_previews_lock = threading.Lock()
_pending_previews: Dict[str, Dict[str, Any]] = {}
_PREVIEW_TTL_SECONDS = 1800  # 30 minutes


def _assess_risk_level(records_count: int, has_errors: bool) -> str:
    """Determine risk level based on model size and parse errors."""
    if has_errors or records_count > 2000:
        return "high"
    if records_count > 500:
        return "medium"
    return "low"


def _prune_expired_previews() -> None:
    """Remove previews that have exceeded the TTL."""
    now_time = time.time()
    expired = [k for k, v in _pending_previews.items() if now_time - v.get("created_at", 0) > _PREVIEW_TTL_SECONDS]
    for k in expired:
        _pending_previews.pop(k, None)


# ---------------------------------------------------------------------------
# Response & Request models
# ---------------------------------------------------------------------------


class SupportedFormat(BaseModel):
    """A supported import format."""

    id: str = Field(..., description="Format identifier, e.g. 'cim-xml'")
    name: str = Field(..., description="Human-readable name, e.g. 'CIM/XML'")
    description: str = Field(..., description="Short description of the format")
    standard: str = Field(..., description="Industry standard, e.g. 'IEC 61970'")
    extensions: list[str] = Field(..., description="Accepted file extensions")
    max_size_mb: int = Field(10, description="Maximum file size in MB")


class FormatsResponse(BaseModel):
    """Response for GET /formats."""

    formats: list[SupportedFormat]
    count: int


class BusRecord(BaseModel):
    """A single bus/node in the imported power-system model."""

    id: str
    name: str | None = None
    voltage_kv: float | None = None
    type: str | None = None  # PQ, PV, SLACK, etc.


class BranchRecord(BaseModel):
    """A single branch/line in the imported power-system model."""

    id: str
    from_bus: str
    to_bus: str
    type: str | None = None  # LINE, TRANSFORMER, etc.
    r_pu: float | None = None
    x_pu: float | None = None
    rating_mva: float | None = None


class ImportResult(BaseModel):
    """Result of an import operation."""

    success: bool
    format: str
    filename: str
    file_size_bytes: int
    parsed_at: str
    buses: list[BusRecord] = []
    branches: list[BranchRecord] = []
    metadata: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []
    result_id: str | None = None


class ImportPreviewResponse(BaseModel):
    """Impact report for dry-run preview before execution."""

    success: bool
    preview_id: str
    format: str
    filename: str
    file_size_bytes: int
    records_count: int
    buses_count: int
    branches_count: int
    affected_tables: list[str]
    risk_level: str  # "low" | "medium" | "high"
    requires_approval: bool
    warnings: list[str] = []
    errors: list[str] = []
    created_at: str


class ImportExecuteRequest(BaseModel):
    """Request body for executing a previewed import."""

    preview_id: str = Field(..., description="Preview ID returned by POST /preview")
    session_id: Optional[str] = Field(default=None, max_length=64)
    approval_id: Optional[str] = Field(default=None, max_length=64)
    project_name: Optional[str] = Field(default=None, max_length=128)


class ImportExecuteResponse(BaseModel):
    """Result of executing an approved import."""

    success: bool
    import_id: str
    result_id: str
    records_imported: int
    buses_count: int
    branches_count: int
    status: str
    executed_at: str


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

SUPPORTED_FORMATS: list[SupportedFormat] = [
    SupportedFormat(
        id="cim-xml",
        name="CIM/XML",
        description="IEC Common Information Model XML",
        standard="IEC 61970",
        extensions=[".xml", ".cim", ".rdf"],
        max_size_mb=10,
    ),
    SupportedFormat(
        id="psse-raw",
        name="PSS/E RAW",
        description="Siemens PSS/E raw data format",
        standard="PSS/E v35",
        extensions=[".raw", ".psse"],
        max_size_mb=10,
    ),
    SupportedFormat(
        id="matpower",
        name="MATPOWER",
        description="MATLAB MATPOWER case format",
        standard="MATPOWER",
        extensions=[".m", ".matpower"],
        max_size_mb=10,
    ),
    SupportedFormat(
        id="etap-project",
        name="ETAP Project",
        description="ETAP native JSON project export",
        standard="ETAP",
        extensions=[".json", ".etap"],
        max_size_mb=10,
    ),
    SupportedFormat(
        id="json",
        name="JSON",
        description="Generic structured power-system data",
        standard="Custom",
        extensions=[".json"],
        max_size_mb=10,
    ),
    SupportedFormat(
        id="csv",
        name="CSV",
        description="Comma-separated bus/branch data",
        standard="Custom",
        extensions=[".csv", ".tsv"],
        max_size_mb=10,
    ),
]


def _detect_format(filename: str) -> SupportedFormat:
    """Detect the format from the file extension."""
    name_lower = filename.lower()
    for fmt in SUPPORTED_FORMATS:
        for ext in fmt.extensions:
            if name_lower.endswith(ext):
                return fmt
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported file extension. Accepted: {', '.join(sorted({e for f in SUPPORTED_FORMATS for e in f.extensions}))}",
    )


# ---------------------------------------------------------------------------
# Magic bytes & signature validation
# ---------------------------------------------------------------------------


def _validate_magic_bytes(fmt_id: str, content: bytes) -> None:
    """Validate that file content begins with valid signatures for the expected format
    and rejects executable or dangerous binary payloads.
    """
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Fast check: reject executable magic bytes
    for sig in _EXECUTABLE_SIGNATURES:
        if content.startswith(sig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Executable files are strictly rejected",
            )

    header_sample = content[:1024].lstrip(b"\xef\xbb\xbf \t\r\n")

    if fmt_id in ("json", "etap-project"):
        if not header_sample.startswith((b"{", b"[")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON signature: file must start with '{' or '['",
            )
    elif fmt_id == "cim-xml":
        if not header_sample.startswith(b"<"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid XML signature: file must start with '<'",
            )
    elif fmt_id == "csv" and b"\x00" in content[:4096]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Binary files are not valid CSV",
        )
    elif fmt_id in ("psse-raw", "matpower") and b"\x00" in content[:4096]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Binary files are not valid {fmt_id.upper()} format",
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _decode_text(content: bytes) -> tuple[str, list[str]]:
    """Decode bytes to str, trying UTF-8 BOM first, falling back to Latin-1."""
    warnings: list[str] = []
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
        warnings.append(_DECODE_WARNING)
    return text, warnings


def _sanitize_csv_cell(value: str) -> str:
    """Sanitize a CSV cell to prevent formula injection."""
    if not value:
        return value
    stripped = value.strip()
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _make_bus_record(row: dict[str, str]) -> BusRecord:
    """Build a BusRecord from a CSV DictReader row."""
    voltage_raw = row.get("voltage_kv") or row.get("nominal_kv") or row.get("voltage")
    voltage_val = None
    if voltage_raw is not None and voltage_raw.strip():
        voltage_val = float(voltage_raw)
    return BusRecord(
        id=_sanitize_csv_cell((row.get("id") or "").strip()),
        name=_sanitize_csv_cell((row.get("name") or "").strip()) or None,
        voltage_kv=voltage_val,
        type=_sanitize_csv_cell((row.get("type") or "").strip()) or None,
    )


def _make_branch_record(row: dict[str, str]) -> BranchRecord:
    """Build a BranchRecord from a CSV DictReader row."""
    return BranchRecord(
        id=_sanitize_csv_cell((row.get("id") or uuid.uuid4().hex[:8]).strip()),
        from_bus=_sanitize_csv_cell((row.get("from_bus") or row.get("from") or "").strip()),
        to_bus=_sanitize_csv_cell((row.get("to_bus") or row.get("to") or "").strip()),
        type=_sanitize_csv_cell((row.get("type") or "").strip()) or None,
        r_pu=float(row["r_pu"]) if row.get("r_pu") else None,
        x_pu=float(row["x_pu"]) if row.get("x_pu") else None,
        rating_mva=float(row["rating_mva"]) if row.get("rating_mva") else None,
    )


def _json_bus_record(b: dict[str, Any]) -> BusRecord:
    """Build a BusRecord from a JSON dict."""
    voltage_raw = b.get("voltage_kv")
    if voltage_raw is None:
        voltage_raw = b.get("nominal_kv")
    if voltage_raw is None:
        voltage_raw = b.get("voltage")
    voltage_val = float(voltage_raw) if voltage_raw is not None else None
    return BusRecord(
        id=str(b.get("id") or b.get("name") or uuid.uuid4().hex[:8]),
        name=b.get("name"),
        voltage_kv=voltage_val,
        type=b.get("type"),
    )


def _json_branch_record(br: dict[str, Any]) -> BranchRecord:
    """Build a BranchRecord from a JSON dict."""
    return BranchRecord(
        id=str(br.get("id") or uuid.uuid4().hex[:8]),
        from_bus=str(br.get("from_bus") or br.get("from") or br.get("source") or ""),
        to_bus=str(br.get("to_bus") or br.get("to") or br.get("target") or ""),
        type=br.get("type"),
        r_pu=float(br["r_pu"]) if br.get("r_pu") is not None else None,
        x_pu=float(br["x_pu"]) if br.get("x_pu") is not None else None,
        rating_mva=float(br["rating_mva"]) if br.get("rating_mva") is not None else None,
    )


_BUS_TYPE_MAP: dict[int, str] = {1: "PQ", 2: "PV", 3: "SLACK", 4: "ISOLATED"}


def _psse_bus_record(parts: list[str], line_num: int, warnings: list[str]) -> BusRecord | None:
    """Parse a single PSS/E bus line into a BusRecord, or None on failure."""
    if len(parts) < 3:
        return None
    try:
        bus_id = parts[0].strip().strip("'\"")
        name = parts[1].strip().strip("'\"")
        voltage = float(parts[2]) if parts[2] else None
        type_code = int(parts[3]) if len(parts) > 3 and parts[3] else 1
        return BusRecord(
            id=bus_id,
            name=name or None,
            voltage_kv=voltage,
            type=_BUS_TYPE_MAP.get(type_code, "PQ"),
        )
    except (ValueError, IndexError):
        warnings.append(f"Bus line {line_num}: skipped (parse error)")
        return None


def _extract_rdf_id(elem: Any) -> str | None:
    """Extract the RDF ID attribute from an XML element."""
    for attr_key, attr_val in elem.attrib.items():
        if attr_key.split("}")[-1] == "ID":
            return attr_val
    return None


def _extract_child_text(elem: Any, local_tag: str) -> str | None:
    """Extract text of a child element matching a local tag name."""
    for child in elem:
        if child.tag.split("}")[-1] == local_tag:
            return child.text
    return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_csv(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a CSV file. Expects either a bus table or a branch table."""
    text, warnings = _decode_text(content)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")

    fields = {f.lower().strip() for f in reader.fieldnames}
    is_bus = {"id"} <= fields and any(
        v in fields for v in {"voltage_kv", "nominal_kv", "voltage", "type", "name"}
    )
    is_branch = {"from_bus", "to_bus"} <= fields or {"from", "to"} <= fields

    if is_bus:
        buses, branches = _parse_csv_buses(reader, warnings), []
    elif is_branch:
        buses, branches = [], _parse_csv_branches(reader, warnings)
    else:
        raise ValueError(
            "CSV must have either bus columns (id, name, voltage_kv, type) "
            "or branch columns (id, from_bus, to_bus, type, r_pu, x_pu, rating_mva)"
        )

    return buses, branches, {"row_count": len(buses) + len(branches)}, warnings


def _parse_csv_buses(reader: csv.DictReader, warnings: list[str]) -> list[BusRecord]:
    """Parse bus rows from a CSV reader."""
    buses: list[BusRecord] = []
    for row in reader:
        try:
            buses.append(_make_bus_record(row))
        except (ValueError, KeyError) as e:
            warnings.append(f"Row {reader.line_num}: skipped ({e})")
    return buses


def _parse_csv_branches(reader: csv.DictReader, warnings: list[str]) -> list[BranchRecord]:
    """Parse branch rows from a CSV reader."""
    branches: list[BranchRecord] = []
    for row in reader:
        try:
            branches.append(_make_branch_record(row))
        except (ValueError, KeyError) as e:
            warnings.append(f"Row {reader.line_num}: skipped ({e})")
    return branches


def _parse_json(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a JSON file. Accepts either ETAP-style or generic {buses, branches} format."""
    text, warnings = _decode_text(content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    _MAX_JSON_DEPTH = 20
    _MAX_JSON_KEYS = 10000

    def _check_depth(obj: Any, depth: int = 0) -> int:
        if depth > _MAX_JSON_DEPTH:
            raise ValueError(f"JSON nesting exceeds maximum depth of {_MAX_JSON_DEPTH}")
        key_count = 0
        if isinstance(obj, dict):
            key_count = len(obj)
            for v in obj.values():
                key_count += _check_depth(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                key_count += _check_depth(item, depth + 1)
        if key_count > _MAX_JSON_KEYS:
            raise ValueError(f"JSON key count exceeds maximum of {_MAX_JSON_KEYS}")
        return key_count

    _check_depth(data)

    buses_raw = data.get("buses") or data.get("nodes") or data.get("bus_list") or []
    branches_raw = data.get("branches") or data.get("lines") or data.get("branch_list") or []

    buses = [_json_bus_record(b) for b in buses_raw if isinstance(b, dict)]
    branches = [_json_branch_record(br) for br in branches_raw if isinstance(br, dict)]

    return buses, branches, {"key_count": len(data)}, warnings


def _parse_psse_raw(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a PSS/E .raw file. Extracts bus data and base MVA."""
    text, warnings = _decode_text(content)
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError("PSS/E RAW file too short — needs at least header + bus data")

    base_mva = _parse_psse_header(lines)
    buses = _parse_psse_buses(lines, warnings)
    return buses, [], {"base_mva": base_mva, "bus_count": len(buses)}, warnings


def _parse_psse_header(lines: list[str]) -> float:
    """Extract base MVA from the PSS/E header (second line)."""
    if len(lines) < 2:
        return 100.0
    parts = lines[1].strip().split(",")
    if len(parts) >= 2:
        try:
            return float(parts[1].strip())
        except ValueError:
            pass
    return 100.0


def _parse_psse_buses(lines: list[str], warnings: list[str]) -> list[BusRecord]:
    """Extract bus records from PSS/E lines after the header."""
    buses: list[BusRecord] = []
    in_bus_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if "END OF" in upper and "BUS" in upper:
            in_bus_section = True
            continue
        if not in_bus_section:
            continue
        if "END OF" in upper:
            break
        parts = [p.strip() for p in line.split(",")]
        record = _psse_bus_record(parts, i + 1, warnings)
        if record is not None:
            buses.append(record)
    return buses


def _parse_matpower(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a MATPOWER .m case file."""
    text, warnings = _decode_text(content)

    base_mva = _parse_matpower_base_mva(text)
    buses = _parse_matpower_buses(text)
    branches = _parse_matpower_branches(text)

    return (
        buses,
        branches,
        {"base_mva": base_mva, "bus_count": len(buses), "branch_count": len(branches)},
        warnings,
    )


def _parse_matpower_base_mva(text: str) -> float:
    """Extract base MVA from a MATPOWER case file."""
    m = re.search(r"mpc\.baseMVA\s*=\s*([\d.]+)\s*;", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 100.0


def _parse_matpower_buses(text: str) -> list[BusRecord]:
    """Extract bus records from a MATPOWER case file."""
    buses: list[BusRecord] = []
    bus_match = re.search(r"mpc\.bus\s*=\s*\[(.*?)\]\s*;", text, re.DOTALL)
    if not bus_match:
        return buses
    for line in bus_match.group(1).splitlines():
        line = line.strip().rstrip(";").strip()
        if not line or line.startswith("%"):
            continue
        parts = re.split(r"\s+", line)
        try:
            if len(parts) >= 3:
                buses.append(
                    BusRecord(
                        id=parts[0],
                        type=_BUS_TYPE_MAP.get(int(parts[1]), "PQ"),
                        voltage_kv=float(parts[2]) if parts[2] else None,
                    )
                )
        except (ValueError, IndexError):
            continue
    return buses


def _parse_matpower_branches(text: str) -> list[BranchRecord]:
    """Extract branch records from a MATPOWER case file."""
    branches: list[BranchRecord] = []
    branch_match = re.search(r"mpc\.branch\s*=\s*\[(.*?)\]\s*;", text, re.DOTALL)
    if not branch_match:
        return branches
    for line in branch_match.group(1).splitlines():
        line = line.strip().rstrip(";").strip()
        if not line or line.startswith("%"):
            continue
        parts = re.split(r"\s+", line)
        try:
            if len(parts) >= 4:
                branches.append(
                    BranchRecord(
                        id=uuid.uuid4().hex[:8],
                        from_bus=parts[0],
                        to_bus=parts[1],
                        r_pu=float(parts[2]),
                        x_pu=float(parts[3]),
                    )
                )
        except (ValueError, IndexError):
            continue
    return branches


def _parse_cim_xml(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a CIM/XML file.

    Note: Full XML parsing support requires defusedxml in requirements (decision
    reserved for repository owner in fix/plan-v3-compliance branch).
    """
    if ET is None:
        raise ValueError(
            "XML parsing is disabled: defusedxml is not installed. "
            "Install it with: pip install defusedxml"
        )

    text, warnings = _decode_text(content)

    buses: list[BusRecord] = []
    branches: list[BranchRecord] = []

    try:
        root = ET.fromstring(text)  # nosec B314
        for elem in root.iter():
            tag_local = elem.tag.split("}")[-1]
            if tag_local == "TopologicalNode":
                _cim_add_bus(elem, buses)
            elif tag_local == "ACLineSegment":
                _cim_add_branch(elem, branches, warnings)
    except Exception as e:
        raise ValueError(f"Failed to parse CIM XML: {e}") from e

    return buses, branches, {"cim_version": "IEC 61970"}, warnings


def _cim_add_bus(elem: Any, buses: list[BusRecord]) -> None:
    rdf_id = _extract_rdf_id(elem)
    name = _extract_child_text(elem, "IdentifiedObject.name")
    buses.append(BusRecord(id=rdf_id or "", name=name))


def _cim_add_branch(elem: Any, branches: list[BranchRecord], warnings: list[str]) -> None:
    line_id = _extract_rdf_id(elem)
    name = _extract_child_text(elem, "IdentifiedObject.name")
    branches.append(BranchRecord(id=line_id or "", from_bus="", to_bus="", type="LINE"))
    if name:
        warnings.append(
            f"Line {line_id} ({name}): terminals not resolved (CIM Terminal references require full RDF parsing)"
        )


# ---------------------------------------------------------------------------
# Core parsing helper
# ---------------------------------------------------------------------------


def _parse_model_content(
    fmt: SupportedFormat, content: bytes
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str], list[str]]:
    """Parse bytes content into structured records according to format."""
    warnings: list[str] = []
    errors: list[str] = []
    buses: list[BusRecord] = []
    branches: list[BranchRecord] = []
    metadata: dict[str, Any] = {}

    try:
        if fmt.id == "csv":
            buses, branches, metadata, warnings = _parse_csv(content)
        elif fmt.id in ("json", "etap-project"):
            buses, branches, metadata, warnings = _parse_json(content)
        elif fmt.id == "psse-raw":
            buses, branches, metadata, warnings = _parse_psse_raw(content)
        elif fmt.id == "matpower":
            buses, branches, metadata, warnings = _parse_matpower(content)
        elif fmt.id == "cim-xml":
            buses, branches, metadata, warnings = _parse_cim_xml(content)
        else:
            raise ValueError(f"Parser for format '{fmt.id}' is not implemented")
    except ValueError as e:
        err_msg = str(e)
        errors.append(f"Import parsing error: {err_msg}")

    return buses, branches, metadata, warnings, errors


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/formats",
    response_model=FormatsResponse,
    summary="List supported import formats",
    dependencies=[Depends(get_api_key)],
)
async def list_formats() -> Any:
    """Return the list of supported power-system data formats."""
    return FormatsResponse(formats=SUPPORTED_FORMATS, count=len(SUPPORTED_FORMATS))


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    summary="Dry-run impact analysis of a power-system data file before importing",
)
async def preview_import(
    file: Annotated[UploadFile, File(description="Power-system data file")],
    session_id: Annotated[Optional[str], Form(description="Chat session ID")] = None,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> Any:
    """Parse an uploaded power-system file in-memory and return an impact report.

    Security & Safety:
    - Verifies file magic bytes and format signatures.
    - Limits size to 10 MiB (streaming enforcement).
    - Dry-run only: no mutations to database or project tables.
    - Audits preview operation and returns a preview_id for approval/execution.
    """
    if not is_feature_enabled("data_import", default=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_DATA_IMPORT_DISABLED,
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    safe_filename = re.sub(
        r"[\x00-\x1f\x7f]", "", file.filename.replace("..", "").replace("/", "_").replace("\\", "_")
    )
    fmt = _detect_format(safe_filename)

    # Stream read with 10 MiB limit
    chunks: list[bytes] = []
    total_read = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    # Magic bytes check
    _validate_magic_bytes(fmt.id, content)

    buses, branches, metadata, warnings, errors = _parse_model_content(fmt, content)
    total_records = len(buses) + len(branches)

    # Calculate risk level
    risk_level = _assess_risk_level(total_records, bool(errors))

    preview_id = f"imp_prev_{uuid.uuid4().hex}"
    now_iso = datetime.now(UTC).isoformat()

    with _previews_lock:
        _prune_expired_previews()
        _pending_previews[preview_id] = {
            "preview_id": preview_id,
            "tenant_id": user.tenant_id or "default",
            "format": fmt.id,
            "filename": safe_filename,
            "file_size_bytes": len(content),
            "buses": [b.model_dump() for b in buses],
            "branches": [br.model_dump() for br in branches],
            "metadata": metadata,
            "records_count": total_records,
            "buses_count": len(buses),
            "branches_count": len(branches),
            "warnings": warnings,
            "errors": errors,
            "requires_approval": True,
            "created_at": time.time(),
        }

    # Record Audit
    record_approval_event(
        "IMPORT_PREVIEW",
        preview_id,
        user.user_id,
        {
            "format": fmt.id,
            "filename": safe_filename,
            "records_count": total_records,
            "risk_level": risk_level,
        },
    )

    return ImportPreviewResponse(
        success=len(errors) == 0,
        preview_id=preview_id,
        format=fmt.id,
        filename=safe_filename,
        file_size_bytes=len(content),
        records_count=total_records,
        buses_count=len(buses),
        branches_count=len(branches),
        affected_tables=["buses", "branches", "projects"] if total_records > 0 else [],
        risk_level=risk_level,
        requires_approval=True,
        warnings=warnings,
        errors=errors,
        created_at=now_iso,
    )


def _check_action_status(action: PendingAction, preview_id: str, user_id: str) -> None:
    now = datetime.now(UTC)
    expires_at = action.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now or action.status == "expired":
        record_approval_event("EXPIRED", action.id, user_id, {"preview_id": preview_id})
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="ALREADY_RESOLVED: Approval action has expired",
        )

    if action.status in ("resolved", "consumed", "completed"):
        record_approval_event("ALREADY_CONSUMED", action.id, user_id, {"preview_id": preview_id})
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Approval action '{action.id}' has already been resolved/consumed and cannot be reused",
        )

    if action.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action is not approved (current status: {action.status})",
        )


def _check_action_maker_checker(action: PendingAction, preview_id: str, user_id: str) -> None:
    if isinstance(action.args, dict) and action.args.get("preview_id"):
        bound_preview = action.args["preview_id"]
        if bound_preview != preview_id:
            record_approval_event(
                "PREVIEW_MISMATCH",
                action.id,
                user_id,
                {"expected_preview_id": bound_preview, "actual_preview_id": preview_id},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval action '{action.id}' is bound to preview '{bound_preview}', not '{preview_id}'",
            )

    if not action.decided_by_user_id or action.decided_by_user_id == action.requested_by_user_id:
        record_approval_event(
            "MAKER_CHECKER_VIOLATION",
            action.id,
            user_id,
            {"requested_by": action.requested_by_user_id, "decided_by": action.decided_by_user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MAKER_CHECKER_VIOLATION: Maker cannot approve their own action",
        )


async def _validate_import_approval(
    preview: dict[str, Any],
    body: ImportExecuteRequest,
    user: CurrentUser,
    db: AsyncSession,
) -> Optional[PendingAction]:
    """Validate Maker-Checker dual control constraints for import execution."""
    if not preview.get("requires_approval", True):
        return None

    if not body.approval_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approval_id is required to execute this import",
        )

    stmt = select(PendingAction).where(PendingAction.id == body.approval_id)
    action_res = await db.execute(stmt)
    action = action_res.scalar_one_or_none()

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval action '{body.approval_id}' not found",
        )

    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id or preview.get("tenant_id")):
        record_approval_event(
            "CROSS_TENANT_FORBIDDEN",
            action.id,
            user.user_id,
            {"preview_id": body.preview_id, "user_tenant": user.tenant_id, "action_tenant": action.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant approval access forbidden",
        )

    _check_action_status(action, body.preview_id, user.user_id)
    _check_action_maker_checker(action, body.preview_id, user.user_id)
    return action


@router.post(
    "/execute",
    response_model=ImportExecuteResponse,
    summary="Execute a previewed import into ResultStore with Maker-Checker dual control and session streaming.",
)
async def execute_import(
    body: ImportExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Mandatory Idempotency-Key header"),
) -> Any:
    """Execute a previewed import into ResultStore with Maker-Checker dual control and session streaming."""
    if not is_feature_enabled("data_import", default=False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_DATA_IMPORT_DISABLED,
        )

    from api.approvals import (
        PendingAction,
        _norm_tenant,
        _replay_idempotent,
        _store_idempotent,
    )

    endpoint = "POST /api/v1/import/execute"
    replay = await _replay_idempotent(db, idempotency_key, endpoint, user.tenant_id or "default")
    if replay is not None:
        return replay

    with _previews_lock:
        preview = _pending_previews.get(body.preview_id)

    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import preview expired or not found",
        )

    # Tenant isolation check
    if preview.get("tenant_id") != (user.tenant_id or "default"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Preview belongs to a different tenant",
        )

    # Dual-control approval enforcement
    action = await _validate_import_approval(preview, body, user, db)

    hub = get_hub()
    session_id = body.session_id

    # Progress streaming: phase-based progress events
    if session_id:
        hub.publish(session_id, EVENT_JOB_PROGRESS, {"phase": "validating", "pct": 25, "tool": "data_import"})
        hub.publish(session_id, EVENT_JOB_PROGRESS, {"phase": "parsing", "pct": 50, "tool": "data_import"})
        hub.publish(session_id, EVENT_JOB_PROGRESS, {"phase": "persisting", "pct": 80, "tool": "data_import"})

    summary = {
        "format": preview["format"],
        "filename": preview["filename"],
        "records_imported": preview["records_count"],
        "buses_count": preview["buses_count"],
        "branches_count": preview["branches_count"],
        "metadata": preview["metadata"],
        "warnings": preview["warnings"],
    }

    # Store into ResultStore (P5)
    result_id = await create_result(
        tenant_id=user.tenant_id or "default",
        project_id=body.project_name or preview["filename"],
        created_by=user.user_id,
        summary_json=summary,
        ttl_days=30,
    )

    model_bytes = json.dumps(
        {
            "buses": preview["buses"],
            "branches": preview["branches"],
            "metadata": preview["metadata"],
        },
        indent=2,
    ).encode("utf-8")

    await store_result_file(
        tenant_id=user.tenant_id or "default",
        result_id=result_id,
        rel_path="model.json",
        data=model_bytes,
        mime="application/json",
    )

    # Progress: completed
    if session_id:
        hub.publish(session_id, EVENT_JOB_PROGRESS, {"phase": "completed", "pct": 100, "tool": "data_import"})
        hub.publish(
            session_id,
            EVENT_RESULT_READY,
            {
                "result_id": result_id,
                "tool": "data_import",
                "summary": summary,
            },
        )

    import_id = f"imp_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    # Mark approval action as resolved/consumed to prevent reuse
    if preview.get("requires_approval", True) and body.approval_id and action is not None:
        action.status = "resolved"
        action.resolved_at = datetime.now(UTC)
        await db.flush()
        await db.commit()

        record_approval_event(
            "APPROVAL_CONSUMED",
            action.id,
            user.user_id,
            {
                "result_id": result_id,
                "preview_id": body.preview_id,
                "import_id": import_id,
            },
        )

    # Record Audit
    record_approval_event(
        "IMPORT_EXECUTED",
        import_id,
        user.user_id,
        {
            "result_id": result_id,
            "preview_id": body.preview_id,
            "approval_id": body.approval_id,
            "records_imported": preview["records_count"],
        },
    )

    response_payload = {
        "success": True,
        "import_id": import_id,
        "result_id": result_id,
        "records_imported": preview["records_count"],
        "buses_count": preview["buses_count"],
        "branches_count": preview["branches_count"],
        "status": "completed",
        "executed_at": now_iso,
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id or "default", response_payload)
    return response_payload


@router.post(
    "/upload",
    response_model=ImportResult,
    summary="Upload and parse a power-system data file",
    dependencies=[Depends(get_api_key)],
)
async def upload_file(
    file: Annotated[UploadFile, File(description="Power-system data file")],
    user: Annotated[Any, Depends(get_current_user_from_header)],
) -> Any:
    """Upload a power-system data file and parse it into a structured model (legacy/direct path)."""
    if not is_feature_enabled("data_import", default=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_DATA_IMPORT_DISABLED,
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    safe_filename = re.sub(
        r"[\x00-\x1f\x7f]", "", file.filename.replace("..", "").replace("/", "_").replace("\\", "_")
    )
    fmt = _detect_format(safe_filename)

    max_bytes = min(fmt.max_size_mb * 1024 * 1024, MAX_FILE_SIZE)
    chunks: list[bytes] = []
    total_read = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: exceeds {fmt.max_size_mb} MB limit for {fmt.name}",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    # Validate magic bytes
    _validate_magic_bytes(fmt.id, content)

    buses, branches, metadata, warnings, errors = _parse_model_content(fmt, content)

    # Save to ResultStore if successful
    result_id = None
    if not errors:
        tenant = getattr(user, "tenant_id", None) or "default"
        user_id = getattr(user, "user_id", None) or "system"
        try:
            result_id = await create_result(
                tenant_id=tenant,
                project_id=safe_filename,
                created_by=str(user_id),
                summary_json={
                    "format": fmt.id,
                    "filename": safe_filename,
                    "buses_count": len(buses),
                    "branches_count": len(branches),
                },
                ttl_days=30,
            )
        except Exception:
            logger.debug("Failed to store upload result to ResultStore", exc_info=True)

    return ImportResult(
        success=len(errors) == 0,
        format=fmt.id,
        filename=safe_filename,
        file_size_bytes=len(content),
        parsed_at=datetime.now(UTC).isoformat(),
        buses=buses,
        branches=branches,
        metadata=metadata,
        warnings=warnings,
        errors=errors,
        result_id=result_id,
    )
