"""
System Validation API Router
============================
Handles all power system validation endpoints.
Separated from main engineering service for better modularity.
"""


from fastapi import APIRouter, HTTPException, Request

from api.studies import SystemSpec, _build_system_from_spec

router = APIRouter(prefix="/api/v1/system", tags=["validation"])


@router.post("/validate")
async def validate_system(request: Request, spec: SystemSpec):
    """Validate a power system model specification.

    Checks structural integrity: all bus references exist, impedance
    values are non-negative, slack bus is present, etc.

    Accepts the same flexible field names as /api/v1/studies/run
    (e.g. ``b1`` for ``bshunt1``, ``load_power_reactive`` for
    ``load_power_imag``).  Extra fields are silently ignored.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    warnings: list[str] = []
    errors: list[str] = []

    try:
        # Structural validation
        if not spec.buses:
            errors.append("System must have at least one bus")
        if not spec.lines and not spec.transformers:
            warnings.append("System has no lines or transformers — it may be degenerate")
        slack_buses = [b for b in spec.buses if b.bus_type == "slack"]
        if len(slack_buses) == 0:
            errors.append("System must have at least one slack bus")
        if len(slack_buses) > 1:
            warnings.append(
                f"System has {len(slack_buses)} slack buses; typically only one is expected",
            )

        bus_ids = {b.bus_id for b in spec.buses}
        for line in spec.lines:
            if line.from_bus_id not in bus_ids:
                errors.append(
                    f"Line {line.line_id} references unknown from_bus_id {line.from_bus_id}",
                )
            if line.to_bus_id not in bus_ids:
                errors.append(f"Line {line.line_id} references unknown to_bus_id {line.to_bus_id}")

        for gen in spec.generators:
            if gen.bus_id not in bus_ids:
                errors.append(
                    f"Generator {gen.generator_id} references unknown bus_id {gen.bus_id}",
                )

        for ld in spec.loads:
            if ld.bus_id not in bus_ids:
                errors.append(f"Load {ld.load_id} references unknown bus_id {ld.bus_id}")

        # Build system to catch remaining issues
        if not errors:
            _build_system_from_spec(spec)

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
            "bus_count": len(spec.buses),
            "line_count": len(spec.lines),
            "generator_count": len(spec.generators),
            "load_count": len(spec.loads),
            "transformer_count": len(spec.transformers),
            "trace_id": trace_id,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("system_validation_failed error=%s", str(e), extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Internal validation error") from e
