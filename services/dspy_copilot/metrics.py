"""
services/dspy_copilot/metrics.py — Pure deterministic metrics and physics guardrails.

This module contains ZERO LLM calls and performs NO iterative solving.
It validates schema adherence and evaluates deterministic physical bounds:
voltage band [0.95, 1.05], line overload > 100%, solver convergence, and reactive power limits.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from core_model.specs import StudyResult, SystemSpec
from services.dspy_copilot.schemas import DiagnosticFinding

logger = logging.getLogger(__name__)


def metric_schema_adherence(pred_json: str, schema: type[BaseModel]) -> bool:
    """Evaluate whether pred_json parses and validates against the given Pydantic schema."""
    if not isinstance(pred_json, str):
        return False
    try:
        data = json.loads(pred_json)
        schema.model_validate(data)
        return True
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return False


def check_physics_guards(
    system_spec: SystemSpec | None,
    study_data: StudyResult | dict[str, Any],
) -> list[DiagnosticFinding]:
    """Inspect deterministic study results against fundamental engineering constraints.

    Guards:
    - V < 0.95 pu or V > 1.05 pu -> violation V-BAND
    - loading% > 100% -> violation OVERLOAD
    - converged == False -> violation DIVERGED
    - Q outside [q_min, q_max] (ONLY if system_spec provided) -> warning Q-LIMIT
    - missing slack bus -> violation NO-SLACK

    Never alters numerical values; returns pure diagnostic findings.
    """
    # 1. First validate any dict input against StudyResult (raise on invalid — guards never guess)
    if isinstance(study_data, dict):
        result = StudyResult.model_validate(study_data)
    elif isinstance(study_data, StudyResult):
        result = study_data
    else:
        raise ValueError(f"study_data must be StudyResult or dict, got {type(study_data)}")

    findings: list[DiagnosticFinding] = []
    res_data = result.data or result.results or {}

    # 2. Check convergence
    converged = res_data.get("converged")
    if converged is None:
        # Check top-level success
        converged = result.success

    if not converged:
        findings.append(
            DiagnosticFinding(
                severity="violation",
                code="DIVERGED",
                message="Power system study solver failed to reach mathematical convergence",
                bus_id=None,
                standard_ref="IEEE 3002.7 Section 6.2",
            )
        )

    # 3. Check Slack Bus existence (if system_spec provided)
    if system_spec is not None:
        has_slack = any(getattr(b, "bus_type", "").lower() == "slack" for b in system_spec.buses)
        if not has_slack:
            findings.append(
                DiagnosticFinding(
                    severity="violation",
                    code="NO-SLACK",
                    message="System topology specification lacks a reference Slack bus",
                    bus_id=None,
                    standard_ref="IEEE 3002.7 Section 5.1",
                )
            )

    # 4. Check Voltage Limits [0.95, 1.05]
    buses_data = res_data.get("buses") or {}
    if isinstance(buses_data, dict):
        for b_id_raw, b_info in buses_data.items():
            try:
                b_id = int(b_id_raw)
            except (ValueError, TypeError):
                b_id = None

            vm = None
            if isinstance(b_info, dict):
                vm = b_info.get("voltage_magnitude_pu")
                if vm is None:
                    vm = b_info.get("voltage") or b_info.get("vm")
            elif isinstance(b_info, (int, float)):
                vm = float(b_info)

            if vm is not None:
                if vm < 0.95:
                    findings.append(
                        DiagnosticFinding(
                            severity="violation",
                            code="V-BAND",
                            message=f"Bus {b_id_raw} voltage {vm:.4f} pu is below lower limit (0.95 pu)",
                            bus_id=b_id,
                            standard_ref="ANSI C84.1 Range A / IEC 60038",
                        )
                    )
                elif vm > 1.05:
                    findings.append(
                        DiagnosticFinding(
                            severity="violation",
                            code="V-BAND",
                            message=f"Bus {b_id_raw} voltage {vm:.4f} pu is above upper limit (1.05 pu)",
                            bus_id=b_id,
                            standard_ref="ANSI C84.1 Range A / IEC 60038",
                        )
                    )

    # 5. Check Thermal Overload (loading% > 100%)
    # Scan branches, lines, or top-level loading entries
    branch_candidates = []
    for key in ("lines", "branches", "line_results", "transformers"):
        val = res_data.get(key)
        if isinstance(val, (list, dict)):
            branch_candidates.append(val)

    # Also check if loading is directly provided at top-level
    if "loading" in res_data:
        val = res_data["loading"]
        loading_num = float(val) if isinstance(val, (int, float)) else None
        if loading_num is not None and loading_num > 100.0:
            findings.append(
                DiagnosticFinding(
                    severity="violation",
                    code="OVERLOAD",
                    message=f"Branch loading {loading_num:.1f}% exceeds 100% thermal rating",
                    bus_id=None,
                    standard_ref="IEEE 3002.7 Section 7.4",
                )
            )

    for cand in branch_candidates:
        items = cand.values() if isinstance(cand, dict) else cand
        for item in items:
            if not isinstance(item, dict):
                continue
            loading = item.get("loading_pct") or item.get("loading_percent") or item.get("loading")
            if loading is not None:
                try:
                    loading_val = float(loading)
                    if loading_val > 100.0:
                        branch_id = item.get("line_id") or item.get("id") or item.get("name", "branch")
                        raw_bus = item.get("from_bus_id") or item.get("to_bus_id")
                        overload_bus_id: int | None = None
                        if raw_bus is not None:
                            try:
                                overload_bus_id = int(raw_bus)
                            except (ValueError, TypeError):
                                overload_bus_id = None
                        findings.append(
                            DiagnosticFinding(
                                severity="violation",
                                code="OVERLOAD",
                                message=f"Branch {branch_id} loading {loading_val:.1f}% exceeds 100% thermal rating",
                                bus_id=overload_bus_id,
                                standard_ref="IEEE 3002.7 Section 7.4",
                            )
                        )
                except (ValueError, TypeError):
                    continue

    # 6. Check Q-LIMIT: if and only if system_spec provides limits; otherwise skip explicitly
    if system_spec is not None:
        for bus in system_spec.buses:
            # Check if non-default limits are configured
            has_explicit_limits = (bus.q_min > -990.0) or (bus.q_max < 990.0)
            if has_explicit_limits and isinstance(buses_data, dict):
                b_info = buses_data.get(bus.bus_id) or buses_data.get(str(bus.bus_id))
                if isinstance(b_info, dict):
                    q_gen = b_info.get("reactive_power_mvar") or b_info.get("q_gen") or b_info.get("qg")
                    if q_gen is not None:
                        try:
                            q_val = float(q_gen)
                            if q_val < bus.q_min or q_val > bus.q_max:
                                findings.append(
                                    DiagnosticFinding(
                                        severity="warning",
                                        code="Q-LIMIT",
                                        message=f"Bus {bus.bus_id} reactive power {q_val:.2f} MVAr violated limits [{bus.q_min}, {bus.q_max}]",
                                        bus_id=bus.bus_id,
                                        standard_ref="IEEE 3002.7 Section 6.4",
                                    )
                                )
                        except (ValueError, TypeError):
                            continue

    return findings


def metric_guards_recall(predicted: list[DiagnosticFinding], expected_codes: set[str]) -> float:
    """Calculate recall of expected diagnostic guard codes in predicted findings."""
    if not expected_codes:
        return 1.0
    pred_codes = {f.code for f in predicted}
    hits = expected_codes.intersection(pred_codes)
    return len(hits) / len(expected_codes)
