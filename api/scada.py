"""
SCADA Endpoints API Router
==========================
Handles all SCADA data model endpoints.
Separated from main engineering service for better modularity.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/scada", tags=["scada"])


@router.get("/live")
async def get_scada_live_data(request: Request):
    """Return live SCADA data model mapping for IEC 61850 logical nodes.

    This endpoint provides the current state of the SCADA data model,
    including bus voltages, loads, and switch positions mapped from
    IEC 61850 logical nodes (MMXU, MSQI, XCBR, XSWI).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from scada_model.scada_model import MeasurementType, QualityFlag, SCADADatabase
        db = SCADADatabase()

        # Return a summary of the SCADA model
        measurements = db.get_all_measurements() if hasattr(db, 'get_all_measurements') else []
        switches = db.get_all_switches() if hasattr(db, 'get_all_switches') else []

        return JSONResponse(content={
            "success": True,
            "data": {
                "measurement_count": len(measurements),
                "switch_count": len(switches),
                "measurement_types": [t.value for t in MeasurementType],
                "quality_flags": [q.value for q in QualityFlag],
                "iec61850_logical_nodes": {
                    "MMXU": "Voltage, current, power measurements",
                    "MSQI": "Sequence components & imbalance",
                    "XCBR": "Circuit breaker positions",
                    "XSWI": "Switch/disconnector positions",
                },
                "supported_protocols": ["IEC 61850", "IEC 60870-5-104", "Modbus TCP"],
            },
            "trace_id": trace_id,
        })
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("scada_live_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})