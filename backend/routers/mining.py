"""
backend/routers/mining.py — Mining fire protection API endpoints.

V214: Exposes the mining fire-protection module via HTTP endpoints:
  POST /api/v1/mining/methane-check        — Classify methane hazard
  POST /api/v1/mining/ventilation-check    — Check MSHA ventilation compliance
  POST /api/v1/mining/co-check             — Classify CO hazard
  POST /api/v1/mining/conveyor-suppression — Design suppression system
  POST /api/v1/mining/compliance-report    — Full MSHA compliance report
  GET  /api/v1/mining/standards            — List supported standards

Phase 3 cleanup (BAZSPARK contamination):
  The fireai.mining.* package was deleted from the codebase. Each endpoint
  that previously lazy-imported from fireai.mining.* now returns HTTP 503
  with a migration notice. The endpoint signatures are preserved so the
  routes still register and clients see a structured error rather than a
  404. When the underlying mining services are migrated to new module
  paths, re-introduce the lazy imports inside each endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mining", tags=["mining"])


# ── Request Models ─────────────────────────────────────────────────────────


class MethaneCheckRequest(BaseModel):
    """Request for methane hazard classification."""

    concentration_pct: float = Field(..., ge=0, le=100, description="CH4 % by volume")
    location: str = Field("working_face", description="Mine location")


class VentilationCheckRequest(BaseModel):
    """Request for MSHA ventilation compliance check."""

    airflow_m3_s: float = Field(..., ge=0, description="Airflow in m³/s")
    location_type: str = Field(
        "working_face", description="working_face, last_open_crosscut, or belt_entry"
    )
    cross_sectional_area_m2: float | None = Field(None, description="For velocity check")


class CoCheckRequest(BaseModel):
    """Request for CO hazard classification."""

    co_ppm: float = Field(..., ge=0, description="CO in ppm")


class ConveyorSuppressionRequest(BaseModel):
    """Request for conveyor suppression system design."""

    belt_length_m: float = Field(..., ge=0)
    belt_width_m: float = Field(..., ge=0)
    belt_speed_m_s: float = Field(0.0, ge=0)
    has_fire_resistant_belt: bool = True
    number_of_drives: int = Field(1, ge=1)
    number_of_tail_pieces: int = Field(1, ge=1)
    has_take_up: bool = True


class ComplianceReportRequest(BaseModel):
    """Request for full MSHA compliance report."""

    mine_name: str
    section_name: str
    methane_pct: float = Field(0.0, ge=0)
    co_ppm: float = Field(0.0, ge=0)
    airflow_m3_s: float = Field(0.0, ge=0)
    ventilation_location: str = "working_face"
    conveyor_length_m: float = Field(0.0, ge=0)
    conveyor_width_m: float = Field(0.0, ge=0)
    has_fire_resistant_belt: bool = True


# ── Helpers ────────────────────────────────────────────────────────────────


def _mining_unavailable_503(missing_module: str) -> HTTPException:
    """Build a 503 response describing a fireai.mining dependency that was removed."""
    return HTTPException(
        status_code=503,
        detail={
            "error": "MINING_SERVICE_UNAVAILABLE",
            "detail": (
                f"The mining endpoint requires {missing_module} which was "
                "removed during the BAZSPARK cleanup and is being migrated "
                "to a new module path."
            ),
            "missing_module": missing_module,
            "action": "Wait for the mining-module migration to complete.",
        },
    )


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/standards")
async def list_standards():
    """List supported mining fire protection standards."""
    return {
        "success": True,
        "standards": [
            {"code": "NFPA 120-2022", "title": "Fire Prevention and Control in Coal Mines"},
            {"code": "NFPA 122-2022", "title": "Fire Prevention in Metal/Nonmetal Mining"},
            {"code": "MSHA 30 CFR Part 75", "title": "Underground Coal Mine Safety Standards"},
            {"code": "IEC 60079-10-1", "title": "Hazardous Area Classification (methane/dust)"},
        ],
    }


@router.post("/methane-check", dependencies=[Depends(require_permission(Permission.ELEMENT_READ))])
async def methane_check(request: MethaneCheckRequest):
    """Classify methane concentration per MSHA 30 CFR §75.323."""
    # Phase 3 cleanup: fireai.mining.core.methane_calculator was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.methane_calculator import MSHA_THRESHOLDS, MethaneCalculator
    raise _mining_unavailable_503("fireai.mining.core.methane_calculator") from None


@router.post(
    "/ventilation-check", dependencies=[Depends(require_permission(Permission.ELEMENT_READ))]
)
async def ventilation_check(request: VentilationCheckRequest):
    """Check MSHA ventilation compliance per 30 CFR §75.326-327."""
    # Phase 3 cleanup: fireai.mining.core.ventilation_calculator was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.ventilation_calculator import VentilationCalculator
    raise _mining_unavailable_503("fireai.mining.core.ventilation_calculator") from None


@router.post("/co-check", dependencies=[Depends(require_permission(Permission.ELEMENT_READ))])
async def co_check(request: CoCheckRequest):
    """Classify CO concentration per MSHA 30 CFR §75.351."""
    # Phase 3 cleanup: fireai.mining.core.conveyor_fire was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.conveyor_fire import (
    #       CO_ALERT_PPM, CO_EVACUATE_PPM, CO_IMMINENT_PPM, CO_WITHDRAW_PPM,
    #       ConveyorFireAnalyzer,
    #   )
    raise _mining_unavailable_503("fireai.mining.core.conveyor_fire") from None


@router.post(
    "/conveyor-suppression", dependencies=[Depends(require_permission(Permission.ELEMENT_READ))]
)
async def conveyor_suppression(request: ConveyorSuppressionRequest):
    """Design conveyor belt fire suppression per NFPA 120 §8.4."""
    # Phase 3 cleanup: fireai.mining.core.conveyor_fire was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.conveyor_fire import ConveyorFireAnalyzer, ConveyorSpec
    raise _mining_unavailable_503("fireai.mining.core.conveyor_fire") from None


@router.post(
    "/compliance-report", dependencies=[Depends(require_permission(Permission.REPORT_GENERATE))]
)
async def compliance_report(request: ComplianceReportRequest):
    """Generate full MSHA + NFPA 120 compliance report."""
    # Phase 3 cleanup: fireai.mining.output.msha_report and
    # fireai.mining.core.msha_compliance were removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.msha_report import generate_msha_report
    #   from <new_module>.msha_compliance import MSHAComplianceChecker
    raise _mining_unavailable_503("fireai.mining.core.msha_compliance") from None
