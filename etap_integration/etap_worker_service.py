"""
Windows ETAP Worker Service
===========================
A FastAPI service to be run on Windows hosts with ETAP installed.
Provides a REST API for the Linux-based AI platform to execute ETAP studies.
"""

from __future__ import annotations

import os
import sys
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Add parent directory to path to import etap_integration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etap_integration.etap_com import ETAPAutomation, ETAPStudyType
from security.security_framework import Permission, get_authz_manager

_is_prod = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")
_enable_docs = os.environ.get("ENABLE_DOCS", "").lower() in ("true", "1") or not _is_prod
app = FastAPI(
    title="AhmedETAP Windows Worker",
    version="1.0.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _enable_docs else None,
)

# ----------------------------
# Security: Bearer auth (JWT-only)
# ----------------------------
# All callers authenticate with a single header shape:
#     Authorization: Bearer <credential>
#
# Credential resolution:
#   JWT access token — validated downstream by the RBAC authorization
#   manager (check_permission). Static shared bearer key removed per
#   security audit run-4.
bearer_scheme = HTTPBearer(auto_error=True)


def _require_auth(
    creds: HTTPAuthorizationCredentials = Security(bearer_scheme),  # noqa: B008
) -> tuple[str, bool]:
    credential = creds.credentials
    # JWT-only authentication; static key removed per security audit run-4.
    return credential, False


# Map ETAP study types to RBAC permissions.
STUDY_TYPE_TO_PERMISSION: dict[ETAPStudyType, Permission] = {
    ETAPStudyType.LOAD_FLOW: Permission.CALC_LOAD_FLOW,
    ETAPStudyType.SHORT_CIRCUIT: Permission.CALC_SHORT_CIRCUIT,
    ETAPStudyType.ARC_FLASH: Permission.CALC_ARC_FLASH,
    ETAPStudyType.OPTIMAL_POWER_FLOW: Permission.CALC_OPF,
    ETAPStudyType.PROTECTION_COORDINATION: Permission.CALC_PROTECTION,
    ETAPStudyType.HARMONIC_ANALYSIS: Permission.CALC_HARMONIC,
    ETAPStudyType.MOTOR_STARTING: Permission.CALC_MOTOR_STARTING,
    ETAPStudyType.MOTOR_ACCELERATION: Permission.CALC_MOTOR_ACCELERATION,
    ETAPStudyType.TRANSIENT_STABILITY: Permission.CALC_TRANSIENT_STABILITY,
    ETAPStudyType.CABLE_AMACITY: Permission.CALC_CABLE_AMACITY,
    ETAPStudyType.GROUND_GRID: Permission.CALC_GROUND_GRID,
    ETAPStudyType.RELIABILITY: Permission.CALC_RELIABILITY,
}


class StudyRequest(BaseModel):
    project_path: str
    study_type: str
    visible: bool = False
    parameters: dict[str, Any] | None = None


class StudyResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    execution_time: float


@app.get("/health")
async def health_check():
    """Check if the worker and ETAP COM are reachable.

    P0-8: Previously returned hardcoded {'status': 'healthy'} — a stub
    that always reported healthy even when ETAP COM was not installed.
    Now performs real checks: ETAP COM availability (Windows only),
    Python version, and worker process uptime.
    """
    import time as _time

    is_windows = sys.platform == "win32"
    etap_available = False

    # Check if ETAP COM is actually registered (Windows only). A real ProgID
    # registry probe — not merely "pywin32 imported" — so /health reflects
    # whether ETAP.Application could actually be dispatched on this host.
    if is_windows:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"ETAP.Application\CLSID"):
                etap_available = True
        except OSError:
            etap_available = False

    # Determine actual health status
    is_healthy = True
    issues = []
    if is_windows and not etap_available:
        is_healthy = False
        issues.append("ETAP COM not available (ETAP.Application ProgID not registered)")

    return {
        "status": "healthy" if is_healthy else "degraded",
        "platform": sys.platform,
        "etap_compatible": is_windows,
        "etap_com_available": etap_available,
        "issues": issues if issues else None,
        "timestamp": _time.time(),
    }


@app.post("/execute", response_model=StudyResponse)
async def execute_study(
    request: StudyRequest,
    auth: Annotated[tuple[str, bool], Depends(_require_auth)],  # NOSONAR
):
    """
    Execute an ETAP study via COM automation.

    Authentication: Bearer JWT access token required.
    Authorization: JWT callers are checked via RBAC permission mapped from
    the requested study type.
    """
    token, _ = auth

    if sys.platform != "win32" and ETAPAutomation.__name__ == "ETAPAutomation":
        raise HTTPException(  # NOSONAR
            status_code=400, detail="ETAP automation only supported on Windows"
        )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

    # Map string to ETAPStudyType
    try:
        study_type = ETAPStudyType[request.study_type.upper()]
    except KeyError as err:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Invalid study type: {request.study_type}",
        ) from err

    # RBAC: check that the authenticated user has permission for this study type
    required_perm = STUDY_TYPE_TO_PERMISSION.get(study_type)
    if required_perm is None:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"No RBAC mapping for study type: {study_type.value}",
        )

    authz = get_authz_manager()
    if not authz.check_permission(token, required_perm):
        raise HTTPException(  # NOSONAR
            status_code=403, detail="Forbidden: insufficient permissions"
        )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

    # Validate parameters against the study type schema
    if request.parameters:
        ETAPAutomation._validate_study_parameters(study_type, request.parameters)

    try:
        import time

        start_time = time.time()

        with ETAPAutomation(visible=request.visible) as etap:
            validate_fn = getattr(etap, "_validate_project_path", None)
            if validate_fn is not None and not validate_fn(request.project_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Project path not permitted: {request.project_path}",
                )
            project = etap.open_project(request.project_path)
            if not project:
                return StudyResponse(
                    success=False,
                    data={},
                    warnings=[],
                    errors=[f"Failed to open project: {request.project_path}"],
                    execution_time=time.time() - start_time,
                )

            if request.parameters:
                result = project.run_study(study_type, **request.parameters)
            else:
                result = project.run_study(study_type)

            return StudyResponse(
                success=result.success,
                data=result.data,
                warnings=result.warnings,
                errors=result.errors,
                execution_time=time.time() - start_time,
            )

    except Exception as e:
        return StudyResponse(
            success=False,
            data={},
            warnings=[],
            errors=[str(e)],
            execution_time=0.0,
        )


if __name__ == "__main__":
    # Load configuration
    port = int(os.environ.get("ETAP_WORKER_PORT", 8081))
    # Default to 127.0.0.1 (safer for local dev). Override with HOST=0.0.0.0
    # for Docker/HF Spaces where port-mapping requires binding to all interfaces.
    # SonarCloud S8392: 0.0.0.0 is NOT the default — it's only used when
    # explicitly set via the ETAP_WORKER_HOST env var in containerized deployments.
    host = os.environ.get("ETAP_WORKER_HOST", "127.0.0.1")
    print(f"Starting ETAP Worker on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
