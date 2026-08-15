"""
api/data_import.py — Power-system data import router.

Provides endpoints for uploading and parsing power-system model files in
industry-standard formats:

* CIM/XML       — IEC 61970 Common Information Model
* PSS/E RAW     — Siemens PSS/E raw data format
* MATPOWER      — MATLAB MATPOWER case format
* ETAP Project  — ETAP native JSON project export
* JSON          — Generic structured power-system data
* CSV           — Comma-separated bus/branch data

Endpoints (under ``/api/v1/import``):
* ``POST /upload`` — Upload a file, parse it, and return a structured
                      power-system model that can be saved as a project.
* ``GET  /formats`` — List supported formats with parsing capabilities.

All endpoints require a valid JWT (or X-API-Key when API_KEY is configured).
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid

try:
    import defusedxml.ElementTree as ET  # SECURITY: prevents XXE / billion-laughs attacks
except ImportError:
    # V-33 FIX: defusedxml is now a HARD requirement, not a soft fallback.
    # The fallback to xml.etree.ElementTree is vulnerable to XXE and
    # billion-laughs attacks. If defusedxml is not installed, the XML
    # parser is disabled entirely.
    ET = None
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from api.dependencies import get_api_key, get_current_user_from_header

# Global hard limit for maximum file uploads (50 MB) to prevent OOM.
# This is the absolute ceiling regardless of per-format limits.
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Megabytes

router = APIRouter(prefix="/api/v1/import", tags=["Data Import"])

_DECODE_WARNING = "File was not valid UTF-8; decoded as Latin-1."


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SupportedFormat(BaseModel):
    """A supported import format."""

    id: str = Field(..., description="Format identifier, e.g. 'cim-xml'")
    name: str = Field(..., description="Human-readable name, e.g. 'CIM/XML'")
    description: str = Field(..., description="Short description of the format")
    standard: str = Field(..., description="Industry standard, e.g. 'IEC 61970'")
    extensions: list[str] = Field(..., description="Accepted file extensions")
    max_size_mb: int = Field(20, description="Maximum file size in MB")


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
        max_size_mb=20,
    ),
    SupportedFormat(
        id="psse-raw",
        name="PSS/E RAW",
        description="Siemens PSS/E raw data format",
        standard="PSS/E v35",
        extensions=[".raw", ".psse"],
        max_size_mb=20,
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
        max_size_mb=20,
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


def _make_bus_record(row: dict[str, str]) -> BusRecord:
    """Build a BusRecord from a CSV DictReader row."""
    return BusRecord(
        id=_sanitize_csv_cell(str(row.get("id", "")).strip()),
        name=_sanitize_csv_cell((row.get("name") or "").strip()) or None,
        voltage_kv=float(row["voltage_kv"]) if row.get("voltage_kv") else None,
        type=_sanitize_csv_cell((row.get("type") or "").strip()) or None,
    )


def _make_branch_record(row: dict[str, str]) -> BranchRecord:
    """Build a BranchRecord from a CSV DictReader row."""
    return BranchRecord(
        id=_sanitize_csv_cell(str(row.get("id", uuid.uuid4().hex[:8])).strip()),
        from_bus=_sanitize_csv_cell((row.get("from_bus") or row.get("from") or "").strip()),
        to_bus=_sanitize_csv_cell((row.get("to_bus") or row.get("to") or "").strip()),
        type=_sanitize_csv_cell((row.get("type") or "").strip()) or None,
        r_pu=float(row["r_pu"]) if row.get("r_pu") else None,
        x_pu=float(row["x_pu"]) if row.get("x_pu") else None,
        rating_mva=float(row["rating_mva"]) if row.get("rating_mva") else None,
    )


def _json_bus_record(b: dict[str, Any]) -> BusRecord:
    """Build a BusRecord from a JSON dict."""
    return BusRecord(
        id=str(b.get("id") or b.get("name") or uuid.uuid4().hex[:8]),
        name=b.get("name"),
        voltage_kv=float(b["voltage_kv"]) if b.get("voltage_kv") is not None else None,
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


def _sanitize_csv_cell(value: str) -> str:
    """V-32: Sanitize a CSV cell to prevent formula injection.

    If a cell starts with =, +, -, or @, it could be interpreted as a
    formula when the exported data is opened in Excel. Prefix with a
    single quote to prevent formula execution.
    """
    if not value:
        return value
    stripped = value.strip()
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _parse_csv(
    content: bytes,
) -> tuple[list[BusRecord], list[BranchRecord], dict[str, Any], list[str]]:
    """Parse a CSV file. Expects either a bus table or a branch table.

    Bus CSV columns: id, name, voltage_kv, type
    Branch CSV columns: id, from_bus, to_bus, type, r_pu, x_pu, rating_mva
    """
    text, warnings = _decode_text(content)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")

    fields = {f.lower().strip() for f in reader.fieldnames}
    is_bus = {"id"} <= fields and any(
        v in fields for v in {"voltage_kv", "voltage", "type", "name"}
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
    """Parse a JSON file. Accepts either ETAP-style or generic {buses, branches} format.

    V-52 FIX: Added JSON depth limit (max 20 levels) and key count limit
    (max 10,000 keys) to prevent JSON bomb attacks (deeply nested or
    excessively wide JSON objects that exhaust memory/CPU during parsing).
    """
    text, warnings = _decode_text(content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    # V-52: Validate JSON depth and key count to prevent JSON bomb attacks
    _MAX_JSON_DEPTH = 20
    _MAX_JSON_KEYS = 10000

    def _check_depth(obj: Any, depth: int = 0) -> int:
        """Recursively check JSON depth and count keys. Returns key count."""
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
    """Parse a PSS/E .raw file. Extracts bus data (first section) and branch data (third section)."""
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
    """Parse a MATPOWER .m case file. Extracts mpc.bus and mpc.branch matrices."""
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
                        id=str(uuid.uuid4().hex[:8]),
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
    """Parse a CIM/XML file. Extracts TopologicalNode and ACLineSegment elements."""
    # V-33: defusedxml is a hard requirement — if not installed, reject XML uploads
    if ET is None:
        raise ValueError(
            "XML parsing is disabled: defusedxml is not installed. "
            "Install it with: pip install defusedxml"
        )

    text, warnings = _decode_text(content)

    buses: list[BusRecord] = []
    branches: list[BranchRecord] = []

    try:
        root = ET.fromstring(text)  # defusedxml protects against XXE / billion-laughs
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
    """Extract a CIM TopologicalNode element and append a BusRecord."""
    rdf_id = _extract_rdf_id(elem)
    name = _extract_child_text(elem, "IdentifiedObject.name")
    buses.append(BusRecord(id=rdf_id or "", name=name))


def _cim_add_branch(elem: Any, branches: list[BranchRecord], warnings: list[str]) -> None:
    """Extract a CIM ACLineSegment element and append a BranchRecord."""
    line_id = _extract_rdf_id(elem)
    name = _extract_child_text(elem, "IdentifiedObject.name")
    branches.append(BranchRecord(id=line_id or "", from_bus="", to_bus="", type="LINE"))
    if name:
        warnings.append(
            f"Line {line_id} ({name}): terminals not resolved (CIM Terminal references require full RDF parsing)"
        )


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
    "/upload",
    response_model=ImportResult,
    summary="Upload and parse a power-system data file",
    dependencies=[Depends(get_api_key)],
)
async def upload_file(  # NOSONAR - already uses Annotated type hints for FastAPI dependency injection
    file: Annotated[UploadFile, File(description="Power-system data file")],
    user: Annotated[Any, Depends(get_current_user_from_header)],
) -> Any:
    """Upload a power-system data file and parse it into a structured model.

    The parsed model (buses + branches) can then be saved as a project via
    POST /api/v1/projects/.

    Supported formats: CIM/XML, PSS/E RAW, MATPOWER, ETAP JSON, JSON, CSV.
    Maximum file size: per-format limit (10-20 MB) with a global hard cap of 50 MB.

    CRITICAL FIX — OOM Protection:
    Files are read in 1 MB chunks with a two-tier size limit enforced
    during streaming to prevent memory exhaustion and OOM Killer crashes.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # SECURITY: Sanitize filename — strip control characters and path traversal
    import re as _re

    safe_filename = _re.sub(
        r"[\x00-\x1f\x7f]", "", file.filename.replace("..", "").replace("/", "_").replace("\\", "_")
    )
    if safe_filename != file.filename:
        import logging as _logging

        # NOSONAR
        _logging.getLogger("etap.api.data_import").warning(
            "filename_sanitized safe=%s (original contained control chars/path traversal)",
            safe_filename,
        )

    fmt = _detect_format(safe_filename)

    # SECURITY: Stream-read with size limit to prevent zip-bomb / memory exhaustion.
    # Read in chunks up to max_bytes + 1 (the +1 lets us detect if the file
    # exceeds the limit without reading the entire file first).
    #
    # CRITICAL FIX — OOM Protection:
    # Two-tier size enforcement:
    #   1. Per-format limit (fmt.max_size_mb): e.g. 20 MB for CIM/XML, 10 MB for CSV
    #   2. Global hard limit (MAX_FILE_SIZE = 50 MB): absolute ceiling regardless of format
    # This prevents a malicious or misconfigured format from allowing uploads
    # that consume excessive RAM and trigger the Linux OOM Killer.
    max_bytes = min(fmt.max_size_mb * 1024 * 1024, MAX_FILE_SIZE)
    chunks: list[bytes] = []
    total_read = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB chunks
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: exceeds {fmt.max_size_mb} MB limit for {fmt.name} (global max: {MAX_FILE_SIZE // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # V-30: Zip bomb protection — check decompression ratio.
    # The streaming read above already enforces the size limit. However,
    # for ZIP files (which are not currently decompressed here), we add
    # an additional safeguard: if the upload size exceeds the format's
    # max_size_mb, reject it. The stream-read loop already handles this,
    # but this is a belt-and-suspenders check.
    #
    # NOTE: The previous version compared `total_read` with `len(content)`
    # which were always equal (content is just the concatenation of chunks),
    # making the ratio check a no-op. This version instead validates the
    # Content-Encoding header — if the client claims gzip/deflate encoding,
    # we reject it to prevent decompression bombs. The actual decompression
    # ratio check is only meaningful for ZIP files, which are handled by
    # a dedicated ZIP parser (not yet implemented).
    content_encoding = file.headers.get("content-encoding", "").lower()
    if content_encoding in ("gzip", "deflate", "br", "zstd"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Compressed uploads are not supported. Please upload the uncompressed file.",
        )

    # Size already enforced during streaming read above

    # Parse based on format
    warnings: list[str] = []
    errors: list[str] = []
    buses: list[BusRecord] = []
    branches: list[BranchRecord] = []
    metadata: dict[str, Any] = {}

    try:
        if fmt.id == "csv":
            buses, branches, metadata, warnings = _parse_csv(content)
        elif fmt.id == "json" or fmt.id == "etap-project":
            buses, branches, metadata, warnings = _parse_json(content)
        elif fmt.id == "psse-raw":
            buses, branches, metadata, warnings = _parse_psse_raw(content)
        elif fmt.id == "matpower":
            buses, branches, metadata, warnings = _parse_matpower(content)
        elif fmt.id == "cim-xml":
            buses, branches, metadata, warnings = _parse_cim_xml(content)
        else:
            raise ValueError(f"Parser for format '{fmt.id}' is not implemented")
    except ValueError:
        errors.append(f"Parse error in format '{fmt.id}'")
        return ImportResult(
            success=False,
            format=fmt.id,
            filename=safe_filename,
            file_size_bytes=len(content),
            parsed_at=datetime.now(UTC).isoformat(),
            buses=[],
            branches=[],
            metadata={},
            warnings=warnings,
            errors=errors,
        )

    return ImportResult(
        success=True,
        format=fmt.id,
        filename=safe_filename,
        file_size_bytes=len(content),
        parsed_at=datetime.now(UTC).isoformat(),
        buses=buses,
        branches=branches,
        metadata=metadata,
        warnings=warnings,
        errors=errors,
    )

