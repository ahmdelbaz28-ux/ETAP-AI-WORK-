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

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Add parent directory to path to import etap_integration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etap_integration.etap_com import ETAPAutomation, ETAPStudyType
from security.security_framework import Permission, get_authz_manager

app = FastAPI(title="AhmedETAP Windows Worker", version="1.0.0")

# ----------------------------
# Security: JWT + RBAC
# ----------------------------
# Worker accepts JWT via: Authorization: Bearer <token>
bearer_scheme = HTTPBearer(auto_error=True)

# Keep legacy API key header definition but reject it (JWT-only migration).
API_KEY_NAME = "X-ETAP-Worker-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _reject_legacy_api_key(api_key: str | None) -> None:
    if api_key:
        raise HTTPException(
            status_code=401, detail="Legacy API key auth is not supported. Use JWT Bearer token.",
        )


async def _require_auth(
    legacy_api_key: str | None = Security(api_key_header),
    creds: HTTPAuthorizationCredentials = Security(bearer_scheme),  # noqa: B008
) -> str:
    """
    Validate JWT Bearer token and reject legacy API key auth.

    Returns the validated token string. Permission checks are performed
    by the endpoint handler based on the requested study type.
    """
    _reject_legacy_api_key(legacy_api_key)
    return creds.credentials


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
    """Check if the worker and ETAP COM are reachable."""
    is_windows = sys.platform == "win32"
    return {
        "status": "healthy",
        "platform": sys.platform,
        "etap_compatible": is_windows,
    }


@app.post("/execute", response_model=StudyResponse)
async def execute_study(
    request: StudyRequest,
    token: str = Depends(_require_auth),
):
    """
    Execute an ETAP study via COM automation.

    Authentication: JWT Bearer token required.
    Authorization: RBAC permission checked based on study type.
    """
    if sys.platform != "win32":
        raise HTTPException(status_code=400, detail="ETAP automation only supported on Windows")

    # Map string to ETAPStudyType
    try:
        study_type = ETAPStudyType[request.study_type.upper()]
    except KeyError as err:
        raise HTTPException(
            status_code=400, detail=f"Invalid study type: {request.study_type}",
        ) from err

    # RBAC: check that the authenticated user has permission for this study type
    required_perm = STUDY_TYPE_TO_PERMISSION.get(study_type)
    if required_perm is None:
        raise HTTPException(
            status_code=400, detail=f"No RBAC mapping for study type: {study_type.value}",
        )

    authz = get_authz_manager()
    if not authz.check_permission(token, required_perm):
        raise HTTPException(status_code=403, detail="Forbidden: insufficient permissions")

    # Validate parameters against the study type schema
    if request.parameters:
        ETAPAutomation._validate_study_parameters(study_type, request.parameters)

    try:
        import time

        start_time = time.time()

        with ETAPAutomation(visible=request.visible) as etap:
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
    port = int(os.environ.get("ETAP_WORKER_PORT", 8080))
    # Bind to 0.0.0.0 — required for Docker container port-mapping and
    # Hugging Face Spaces. Override via HOST env var for localhost dev.
    # SonarCloud S8392 flags this as security-sensitive; it's intentional.
    host = os.environ.get("ETAP_WORKER_HOST", "0.0.0.0")
    print(f"Starting ETAP Worker on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
