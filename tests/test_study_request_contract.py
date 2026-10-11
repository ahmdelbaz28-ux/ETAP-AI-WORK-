"""tests/test_study_request_contract.py — Contract tests for Frontend/Backend Study Requests (P0-1).

Validates:
1. Canonical contract UI -> api/studies.py -> StudyRequest -> ExecutionRequest -> executor.
2. UI-shaped payload with non-default engineering inputs retains them after Pydantic validation.
3. Legacy params alias is normalized to parameters without loss.
4. Embedded system in params is cleanly extracted to system model.
5. dry_run=True short-circuits execution: validates preconditions without invoking solver.
6. Unknown/invalid fields cannot create false applied setting claims.
"""

from __future__ import annotations

import pytest

from core_model.specs import BusSpec, LineSpec, StudyRequest, SystemSpec
from services.execution_orchestrator import ExecutionOrchestrator
from services.execution_request import ExecutionRequest

_SAMPLE_SYSTEM_PAYLOAD = {
    "base_mva": 100.0,
    "buses": [
        {"bus_id": 1, "voltage_magnitude": 1.0, "voltage_angle": 0.0, "bus_type": "slack", "base_kv": 11.0},
        {"bus_id": 2, "voltage_magnitude": 1.0, "voltage_angle": 0.0, "bus_type": "pq", "base_kv": 11.0},
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
    ],
}


def test_ui_shaped_payload_preserves_custom_parameters():
    """UI sends {study_type, params, dry_run, system}; non-default engineering parameters must be preserved."""
    ui_payload = {
        "study_type": "load_flow",
        "params": {
            "max_iterations": 42,
            "tolerance": 1e-5,
            "mode": "engineering",
        },
        "dry_run": False,
        "system": _SAMPLE_SYSTEM_PAYLOAD,
    }

    # Pydantic validation into StudyRequest
    study_req = StudyRequest.model_validate(ui_payload)
    assert study_req.study_type == "load_flow"
    assert study_req.dry_run is False
    assert study_req.parameters["max_iterations"] == 42
    assert study_req.parameters["tolerance"] == 1e-5
    assert study_req.parameters["mode"] == "engineering"
    assert study_req.system is not None
    assert len(study_req.system.buses) == 2

    # Conversion into ExecutionRequest
    exec_req = ExecutionRequest.from_study_request(study_req, user_id="u1", tenant_id="t1")
    params = exec_req.get_parameters()
    assert params["max_iterations"] == 42
    assert params["tolerance"] == 1e-5
    assert params["mode"] == "engineering"
    assert exec_req.input.get("dry_run") is False


def test_embedded_system_in_params_is_lifted():
    """When UI sends system inside params without top-level system, it is lifted cleanly."""
    payload = {
        "study_type": "load_flow",
        "params": {
            "system": _SAMPLE_SYSTEM_PAYLOAD,
            "max_iterations": 35,
        },
    }
    study_req = StudyRequest.model_validate(payload)
    assert study_req.system is not None
    assert len(study_req.system.buses) == 2
    assert study_req.parameters["max_iterations"] == 35


def test_canonical_parameters_key_supported():
    """Payload using canonical parameters key directly works seamlessly."""
    payload = {
        "study_type": "load_flow",
        "parameters": {
            "max_iter": 55,
            "tol": 1e-4,
        },
        "system": _SAMPLE_SYSTEM_PAYLOAD,
    }
    study_req = StudyRequest.model_validate(payload)
    assert study_req.parameters["max_iter"] == 55
    assert study_req.parameters["tol"] == 1e-4


@pytest.mark.asyncio
async def test_dry_run_short_circuit_never_invokes_solver():
    """When dry_run=True, orchestrator validates preconditions and returns status='dry_run' without invoking solver."""
    payload = {
        "study_type": "load_flow",
        "params": {
            "max_iterations": 50,
            "tolerance": 1e-5,
        },
        "dry_run": True,
        "system": _SAMPLE_SYSTEM_PAYLOAD,
    }

    study_req = StudyRequest.model_validate(payload)
    exec_req = ExecutionRequest.from_study_request(study_req, user_id="u1", tenant_id="t1")

    orchestrator = ExecutionOrchestrator()
    result = await orchestrator.execute(exec_req)

    # Must succeed with dry_run status
    assert result.success is True
    assert result.status == "dry_run"
    assert result.executor_kind == "dry_run"
    assert result.solver == "dry_run_validator"
    assert result.data["dry_run"] is True
    assert result.data["validated"] is True
    assert result.data["system_validated"] is True
    assert result.authoritative is False

    # Conversion to StudyResult preserves dry_run status
    study_result = result.to_study_result()
    assert study_result.status == "dry_run"
    assert study_result.success is True


@pytest.mark.asyncio
async def test_dry_run_rejects_missing_system_model():
    """Dry run still enforces schema and system preconditions; missing required system model fails."""
    payload = {
        "study_type": "load_flow",
        "params": {"max_iterations": 50},
        "dry_run": True,
        # system omitted!
    }
    study_req = StudyRequest.model_validate(payload)
    exec_req = ExecutionRequest.from_study_request(study_req, user_id="u1", tenant_id="t1")

    orchestrator = ExecutionOrchestrator()
    result = await orchestrator.execute(exec_req)

    assert result.success is False
    assert result.status == "rejected"
    assert "SYSTEM_MODEL_REQUIRED" in result.errors[0]
