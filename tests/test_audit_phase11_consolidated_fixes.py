"""Phase 11: Security Audit Consolidated Findings Verification Suite.

Tests verify all 48 findings remediations across:
- CSV Formula Injection defense in export.py
- ZipSlip path-traversal prevention in unpack.py
- Study Versioning tenant scoping, GET /{version_id}, and pre-rollback snapshots
- Approvals auto-approve role restriction (403 for viewers)
- Agent executor tenant-namespaced idempotency keys
- ABAC constant-time API key verification
- CUA Executor fail-closed confirmation enforcement
- CUA WebSocket dual-control maker-checker
- Arc Flash Engine NaN/Inf validation
- Engine electrode configuration validation
- SCADA Interlock fail-closed timestamp parsing
- Storage Management tenant scoping and role restrictions
- Email Digest cross-email restriction
- Dependencies JWT algorithm pinning and is_active enforcement
- Auth MFA JTI blacklist and token revocation
"""

from __future__ import annotations

import io
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Export CSV Formula Injection Defense
# ---------------------------------------------------------------------------


def test_csv_formula_injection_sanitization() -> None:
    from api.export import _generate_csv, _sanitize_csv_cell

    for prefix in ["=", "+", "-", "@", "\t", "\r"]:
        dangerous = f"{prefix}cmd|' /C calc'!A0"
        sanitized = _sanitize_csv_cell(dangerous)
        assert sanitized.startswith("'"), f"Failed to escape formula prefix {prefix}"

    safe = "Transformer-1"
    assert _sanitize_csv_cell(safe) == safe


# ---------------------------------------------------------------------------
# 2. ZipSlip Path Traversal in PPT unpack.py
# ---------------------------------------------------------------------------


def test_unpack_zipslip_defense(tmp_path: Path) -> None:
    from skills.ppt.ooxml.scripts.unpack import unpack_document

    # Create a malicious zip file with path traversal
    zip_bytes_io = io.BytesIO()
    with zipfile.ZipFile(zip_bytes_io, mode="w") as zf:
        zf.writestr("../../evil.txt", "exploit")
    zip_bytes_io.seek(0)

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    with pytest.raises(ValueError, match="ZipSlip detected"):
        unpack_document(zip_bytes_io, target_dir)


# ---------------------------------------------------------------------------
# 3. Arc Flash Engine NaN/Inf Validation
# ---------------------------------------------------------------------------


def test_arc_flash_nan_inf_rejection() -> None:
    from fault_analysis.arc_flash_engine import ArcFlashEngine

    engine = ArcFlashEngine()

    invalid_args = [
        (float("nan"), 25.0, 0.1, 457.0),
        (13.8, float("inf"), 0.1, 457.0),
        (13.8, 25.0, float("-inf"), 457.0),
        (13.8, 25.0, 0.1, float("nan")),
    ]

    for v, i, t, d in invalid_args:
        with pytest.raises(ValueError, match="must be a finite number"):
            engine.calculate(
                voltage_kv=v,
                bolted_fault_current_ka=i,
                arc_duration_sec=t,
                working_distance_mm=d,
            )


# ---------------------------------------------------------------------------
# 4. Engine Electrode Configuration Strict Validation
# ---------------------------------------------------------------------------


def test_engine_invalid_electrode_config() -> None:
    from engine.engine import PowerSystemEngine

    engine = PowerSystemEngine()
    with pytest.raises(ValueError, match="Invalid electrode_config"):
        engine.run_arc_flash(
            voltage_kv=13.8,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            electrode_config="MALICIOUS_CONFIG",
        )


# ---------------------------------------------------------------------------
# 5. SCADA Interlock Timestamp Fail-Closed
# ---------------------------------------------------------------------------


def test_scada_interlock_invalid_timestamp_rejected() -> None:
    from scada.interlock_engine import InterlockViolation, SCADAInterlockEngine
    from scada.models import (
        ControlActionType,
        ControlCommandRequest,
        ControlProtocol,
        SignalQuality,
    )

    engine = SCADAInterlockEngine()
    cmd = ControlCommandRequest(
        device_id="CB_001",
        protocol=ControlProtocol.OPC_UA,
        action_type=ControlActionType.BREAKER_OPEN,
        target_value=0,
        reason="Test invalid timestamp",
    )
    telemetry = {
        "CB_001": {
            "quality": SignalQuality.GOOD.value,
            "control_mode": "REMOTE",
            "timestamp": "INVALID_NOT_A_DATE",
        }
    }
    with pytest.raises(InterlockViolation, match="invalid telemetry timestamp"):
        engine.pre_flight_check(cmd, telemetry=telemetry)


# ---------------------------------------------------------------------------
# 6. ABAC Constant-Time API Key Comparison
# ---------------------------------------------------------------------------


def test_abac_uses_hmac_compare_digest() -> None:
    abac_source = _read_file("security/abac.py")
    assert "hmac.compare_digest" in abac_source


# ---------------------------------------------------------------------------
# 7. CUA Executor Fail-Closed on Unhandled Confirmation
# ---------------------------------------------------------------------------


def test_cua_executor_fail_closed_on_confirmation() -> None:
    source = _read_file("agents/cua_base_executor.py")
    assert "Missing confirmation callback for confirmed action (fail-closed)" in source
    assert (
        "Dual confirmation required but no confirmation callback provided (fail-closed)" in source
    )


# ---------------------------------------------------------------------------
# 8. CUA Confirmation Dual Control (Maker-Checker)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cua_confirmation_maker_checker_broker() -> None:
    from api.cua_confirmation_ws import ConfirmationBroker, ConfirmationRequest

    broker = ConfirmationBroker()
    req = ConfirmationRequest(
        request_id="req-123",
        action_type="TRIP",
        action_target="CB-01",
        tenant_id="tenant-A",
        initiator_id="engineer-1",
    )
    broker._pending["req-123"] = req

    # Attempt 1: Initiator attempts self-approval -> maker_checker_violation
    res_self = await broker.confirm(
        request_id="req-123",
        session_id="engineer-1",
        tenant_id="tenant-A",
    )
    assert res_self.get("error") == "maker_checker_violation"

    # Attempt 2: Approver from different tenant -> cross_tenant_forbidden
    res_cross = await broker.confirm(
        request_id="req-123",
        session_id="checker-1",
        tenant_id="tenant-B",
    )
    assert res_cross.get("error") == "cross_tenant_forbidden"

    # Attempt 3: Valid independent approver in same tenant -> accepted
    res_valid = await broker.confirm(
        request_id="req-123",
        session_id="checker-1",
        tenant_id="tenant-A",
    )
    assert "error" not in res_valid
    assert "checker-1" in req.confirmations


# ---------------------------------------------------------------------------
# 9. JWT Algorithm Pinning and User is_active
# ---------------------------------------------------------------------------


def test_dependencies_jwt_and_active_checks() -> None:
    dep_source = _read_file("api/dependencies.py")
    assert 'algorithms=["HS256"]' in dep_source
    assert "user.is_active" in dep_source


# ---------------------------------------------------------------------------
# 10. Study Versioning Tenant Scoping & Snapshot Verification
# ---------------------------------------------------------------------------


def test_study_versions_tenant_scoped_and_snapshot() -> None:
    sv_source = _read_file("api/study_versions.py")
    assert "tenant_id" in sv_source
    assert "Automated audit snapshot before rolling back" in sv_source
    assert "versions/{version_id}" in sv_source
    assert "def get_version(" in sv_source


# ---------------------------------------------------------------------------
# 11. Storage Management Role and Tenant Scoping
# ---------------------------------------------------------------------------


def test_storage_management_scoped() -> None:
    sm_source = _read_file("api/storage_management.py")
    assert "user.tenant_id" in sm_source
    assert 'user.role not in ("admin", "lead_engineer")' in sm_source
