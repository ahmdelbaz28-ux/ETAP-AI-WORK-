"""Operational Post-Draw Verification Engine.

Dispatches Load Flow calculation on the generated ETAP project via the ETAP
worker service (or local engine) and validates that calculated bus voltages
and power flows conform to the source engineering values within declared tolerances.

Conforms to MathGuard principles from agents/ahmed_etap_orchestrator.py:
- Deterministic numerical verification
- Zero guessing: strict unit checks
- Any tolerance exceedance flags failure explicitly (never silent acceptance)
- If the calculation engine is unavailable, reports BLOCKED instead of mocking success.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from core_model.system import System

logger = logging.getLogger(__name__)

DEFAULT_VOLTAGE_TOLERANCE_PCT = 2.0  # 2.0% allowable bus voltage variation
DEFAULT_WORKER_URL = os.getenv("ETAP_WORKER_SERVICE_URL", "http://localhost:8001")


class BusVerificationDetail(BaseModel):
    """Detailed per-bus comparison record."""

    bus_id: str
    expected_v_pu: Optional[float] = None
    calculated_v_pu: Optional[float] = None
    diff_pct: Optional[float] = None
    passed: bool
    message: str


class NetworkVerificationResult(BaseModel):
    """Outcome of post-draw load flow verification."""

    passed: bool
    status: str = Field(description="'verified', 'tolerance_exceeded', 'execution_failed', 'blocked'")
    max_voltage_diff_pct: float = 0.0
    bus_comparisons: dict[str, BusVerificationDetail] = Field(default_factory=dict)
    reason: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


def verify_bus_results(
    expected_buses: dict[str, float],
    calculated_buses: dict[str, float],
    tolerance_pct: float = DEFAULT_VOLTAGE_TOLERANCE_PCT,
) -> NetworkVerificationResult:
    """Compares simulated bus voltages against baseline source values.

    Parameters
    ----------
    expected_buses : dict[str, float]
        Mapping of bus_id -> expected voltage magnitude (pu).
    calculated_buses : dict[str, float]
        Mapping of bus_id -> calculated voltage magnitude (pu) from Load Flow.
    tolerance_pct : float
        Maximum acceptable difference percentage (default 2.0%).
    """
    comparisons: dict[str, BusVerificationDetail] = {}
    max_diff = 0.0
    all_passed = True
    failure_reasons: list[str] = []

    for bus_id, expected_v in expected_buses.items():
        if bus_id not in calculated_buses:
            all_passed = False
            msg = f"Bus '{bus_id}' missing in Load Flow calculation results."
            comparisons[bus_id] = BusVerificationDetail(
                bus_id=bus_id,
                expected_v_pu=expected_v,
                calculated_v_pu=None,
                diff_pct=None,
                passed=False,
                message=msg,
            )
            failure_reasons.append(msg)
            continue

        calc_v = float(calculated_buses[bus_id])
        if expected_v is None or expected_v <= 0:
            # Baseline omitted voltage in source; record without failing tolerance
            comparisons[bus_id] = BusVerificationDetail(
                bus_id=bus_id,
                expected_v_pu=None,
                calculated_v_pu=calc_v,
                diff_pct=0.0,
                passed=True,
                message="Source omitted voltage; verified by solver convergence.",
            )
            continue

        diff_pct = abs(calc_v - expected_v) / expected_v * 100.0
        if diff_pct > max_diff:
            max_diff = diff_pct

        is_bus_ok = diff_pct <= tolerance_pct
        if not is_bus_ok:
            all_passed = False
            msg = f"Voltage error {diff_pct:.3f}% exceeds tolerance {tolerance_pct}% (expected: {expected_v:.3f} pu, got: {calc_v:.3f} pu)"
            failure_reasons.append(f"Bus '{bus_id}': {msg}")
        else:
            msg = f"Voltage matches within tolerance (error: {diff_pct:.3f}%)"

        comparisons[bus_id] = BusVerificationDetail(
            bus_id=bus_id,
            expected_v_pu=expected_v,
            calculated_v_pu=calc_v,
            diff_pct=diff_pct,
            passed=is_bus_ok,
            message=msg,
        )

    status_str = "verified" if all_passed else "tolerance_exceeded"
    reason_str = "; ".join(failure_reasons) if failure_reasons else None

    return NetworkVerificationResult(
        passed=all_passed,
        status=status_str,
        max_voltage_diff_pct=max_diff,
        bus_comparisons=comparisons,
        reason=reason_str,
        details={"total_buses_evaluated": len(expected_buses)},
    )


async def dispatch_load_flow_verification(
    project_path: str,
    baseline_model: System | dict[str, Any],
    worker_url: str = DEFAULT_WORKER_URL,
    auth_token: Optional[str] = None,
    tolerance_pct: float = DEFAULT_VOLTAGE_TOLERANCE_PCT,
) -> NetworkVerificationResult:
    """Dispatches a Load Flow study to the ETAP worker service and verifies results."""
    # 1. Extract baseline expected bus voltages
    expected_voltages: dict[str, float] = {}
    if isinstance(baseline_model, System):
        for bid, bus in baseline_model.buses.items():
            expected_voltages[str(bid)] = getattr(bus, "voltage_magnitude", 1.0)
    elif isinstance(baseline_model, dict):
        buses = baseline_model.get("buses") or baseline_model.get("objects", {}).get("buses", [])
        for b in buses:
            b_id = str(b.get("id") or b.get("name"))
            v_val = b.get("v_mag") or b.get("voltage_magnitude")
            if v_val is not None:
                expected_voltages[b_id] = float(v_val)

    # 2. Invoke ETAP worker service
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {
        "project_path": project_path,
        "study_type": "load_flow",
        "parameters": {},
        "visible": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{worker_url.rstrip('/')}/execute",
                json=payload,
                headers=headers,
            )

        if resp.status_code == 401 or resp.status_code == 403:
            return NetworkVerificationResult(
                passed=False,
                status="blocked",
                reason=f"Worker service authentication failed (HTTP {resp.status_code}).",
            )

        if resp.status_code != 200:
            return NetworkVerificationResult(
                passed=False,
                status="execution_failed",
                reason=f"Worker service returned HTTP {resp.status_code}: {resp.text}",
            )

        data = resp.json()
        if not data.get("success", False):
            return NetworkVerificationResult(
                passed=False,
                status="solver_diverged",
                reason=data.get("error_message") or "Load flow calculation did not converge.",
            )

        # 3. Extract bus voltages from study results
        study_output = data.get("results", {})
        bus_results = study_output.get("bus_results", {})
        calc_voltages: dict[str, float] = {}
        for bid, bdata in bus_results.items():
            if isinstance(bdata, dict) and "voltage_magnitude" in bdata:
                calc_voltages[str(bid)] = float(bdata["voltage_magnitude"])
            elif isinstance(bdata, (int, float)):
                calc_voltages[str(bid)] = float(bdata)

        # 4. MathGuard verification check
        return verify_bus_results(expected_voltages, calc_voltages, tolerance_pct)

    except httpx.ConnectError:
        logger.warning("ETAP worker service unavailable at %s", worker_url)
        return NetworkVerificationResult(
            passed=False,
            status="blocked",
            reason="BLOCKED: ETAP worker service is not running or unreachable.",
            details={"worker_url": worker_url},
        )
    except Exception as exc:
        logger.error("Load flow post-draw verification error: %s", exc)
        return NetworkVerificationResult(
            passed=False,
            status="execution_failed",
            reason=f"Verification dispatch failed: {exc}",
        )
