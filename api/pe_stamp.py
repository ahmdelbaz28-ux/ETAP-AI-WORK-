"""
Professional Engineer (PE) stamp workflow for regulated studies.
Required by law in most jurisdictions for protection, arc flash, and safety studies.
"""

from __future__ import annotations
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional
import logging

logger = logging.getLogger("api.pe_stamp")

# Studies that legally require a PE stamp
REQUIRES_PE_STAMP = {
    "protection_coordination",
    "arc_flash",
    "short_circuit",
    "load_flow",
}

def create_pe_stamp(
    engineer_id: str,
    license_number: str,
    study_type: str,
    study_id: str,
    result_hash: str,
) -> dict[str, Any]:
    """Create a PE stamp for a study result."""
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
        engineer_id, license_number, study_id, signature_hash[:12],
    )
    return stamp

def requires_stamp(study_type: str) -> bool:
    """Check if a study type requires PE stamp."""
    return study_type in REQUIRES_PE_STAMP
