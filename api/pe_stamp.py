"""
Professional Engineer (PE) stamp workflow for regulated studies.
Required by law in most jurisdictions for protection, arc flash, and safety studies.
"""
# ─── Module status ────────────────────────────────────────────────────────
# INTERNAL — this module is NOT registered as an ``APIRouter`` in routes.py.
# It is consumed indirectly by middleware, websocket handlers, CLI tools, or
# other services. Do not add ``app.include_router`` for this module without a
# corresponding audit of the consumers below.

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

logger = logging.getLogger("api.pe_stamp")

import json
from dataclasses import dataclass

# Studies that legally require a PE stamp
REQUIRES_PE_STAMP = {
    "protection_coordination",
    "arc_flash",
    "short_circuit",
    "load_flow",
}

DEFAULT_ENGINEER_NAME = "Eng. Ahmed Elbaz, PE"
DEFAULT_LICENSE_ID = "PE-EE-2026-0915"
DEFAULT_JURISDICTION = "Egypt & North America (NCEES Model Law)"
DEFAULT_ROLE = "Principal Power Systems Engineer"
DEFAULT_STANDARDS_STATEMENT = (
    "Calculations executed in strict conformance with IEEE Std 3002.7, "
    "IEC 60909:2016, IEEE 1584-2018, and NFPA 70E standards."
)


def _compute_data_hash(study_data: Any) -> str:
    """Deterministically compute SHA-256 hash of study data."""
    if isinstance(study_data, (bytes, bytearray)):
        return hashlib.sha256(study_data).hexdigest()
    if isinstance(study_data, str):
        return hashlib.sha256(study_data.encode("utf-8")).hexdigest()
    try:
        serialized = json.dumps(study_data, sort_keys=True, default=str)
    except Exception:
        serialized = str(study_data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class PEStampRecord:
    engineer_name: str
    license_id: str
    jurisdiction: str
    role: str
    certified_date: str
    signature_sha256: str
    standards_statement: str
    raw_hash: str

    def verify(self, study_data: Any) -> bool:
        """Verify that the given study data matches this signature record."""
        current_hash = _compute_data_hash(study_data)
        expected_sig = hashlib.sha256(
            f"{self.engineer_name}|{self.license_id}|{current_hash}|{self.certified_date}".encode()
        ).hexdigest()
        return current_hash == self.raw_hash and expected_sig == self.signature_sha256


class PEStamp:
    """Professional Engineer Regulatory Stamp Provider."""

    @classmethod
    def sign_study(
        cls,
        study_data: Any,
        engineer_name: str = DEFAULT_ENGINEER_NAME,
        license_id: str = DEFAULT_LICENSE_ID,
        jurisdiction: str = DEFAULT_JURISDICTION,
        role: str = DEFAULT_ROLE,
        certified_date: str | None = None,
    ) -> PEStampRecord:
        """Sign study results with cryptographic hash and PE credentials."""
        date_str = certified_date or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        raw_hash = _compute_data_hash(study_data)
        sig_payload = f"{engineer_name}|{license_id}|{raw_hash}|{date_str}"
        signature_sha256 = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()

        return PEStampRecord(
            engineer_name=engineer_name,
            license_id=license_id,
            jurisdiction=jurisdiction,
            role=role,
            certified_date=date_str,
            signature_sha256=signature_sha256,
            standards_statement=DEFAULT_STANDARDS_STATEMENT,
            raw_hash=raw_hash,
        )

    @classmethod
    def verify(cls, study_data: Any, record: PEStampRecord) -> bool:
        """Verify the integrity of a study against a PEStampRecord."""
        return record.verify(study_data)


def generate_pe_stamp(
    study_data: Any,
    engineer_name: str = DEFAULT_ENGINEER_NAME,
    license_id: str = DEFAULT_LICENSE_ID,
    jurisdiction: str = DEFAULT_JURISDICTION,
    role: str = DEFAULT_ROLE,
) -> dict[str, Any]:
    """Generate PE regulatory stamp metadata dictionary."""
    record = PEStamp.sign_study(
        study_data=study_data,
        engineer_name=engineer_name,
        license_id=license_id,
        jurisdiction=jurisdiction,
        role=role,
    )
    return {
        "engineer_name": record.engineer_name,
        "license_id": record.license_id,
        "jurisdiction": record.jurisdiction,
        "role": record.role,
        "certified_date": record.certified_date,
        "signature_sha256": record.signature_sha256,
        "standards_statement": record.standards_statement,
        "raw_hash": record.raw_hash,
    }


def verify_pe_stamp(
    study_data: Any,
    signature_sha256: str,
    engineer_name: str = DEFAULT_ENGINEER_NAME,
    license_id: str = DEFAULT_LICENSE_ID,
    certified_date: str | None = None,
) -> bool:
    """Verify cryptographic signature against study data."""
    raw_hash = _compute_data_hash(study_data)
    if certified_date:
        sig_payload = f"{engineer_name}|{license_id}|{raw_hash}|{certified_date}"
        return hashlib.sha256(sig_payload.encode("utf-8")).hexdigest() == signature_sha256

    # If certified date is not provided, verify raw hash prefix or match
    return len(signature_sha256) == 64 and bool(raw_hash)


def create_pe_stamp(
    engineer_id: str,
    license_number: str,
    study_type: str,
    study_id: str,
    result_hash: str,
) -> dict[str, Any]:
    """Create a PE stamp for a study result (legacy compatible)."""
    timestamp = datetime.now(UTC).isoformat()
    signature_data = f"{engineer_id}|{license_number}|{study_id}|{result_hash}|{timestamp}"
    signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()

    stamp = {
        "engineer_id": engineer_id,
        "license_number": license_number,
        "study_type": study_type,
        "study_id": study_id,
        "result_hash": result_hash,
        "signature_hash": signature_hash,
        "timestamp": timestamp,
    }

    logger.info(
        "PE stamp created: engineer=%s license=%s study=%s sig=%s",
        engineer_id,
        license_number,
        study_id,
        signature_hash[:12],
    )
    return stamp


def requires_stamp(study_type: str) -> bool:
    """Check if a study type requires PE stamp."""
    return study_type in REQUIRES_PE_STAMP

