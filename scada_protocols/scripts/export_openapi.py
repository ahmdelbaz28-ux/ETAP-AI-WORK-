"""Generate the OpenAPI 3.0 spec for the scada_protocols API router.

Run with: python -m scada_protocols.scripts.export_openapi > scada_protocols/config/openapi.yaml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # type: ignore
from fastapi import FastAPI

from scada_protocols.api import build_router


def export_spec() -> dict:
    app = FastAPI(
        title="AhmedETAP SCADA Protocols API",
        description=(
            "Real-time SCADA protocol management for the AhmedETAP Digital "
            "Twin platform. Exposes Modbus TCP, OPC UA, and IEC 60870-5-104 "
            "adapters as a unified REST API."
        ),
        version="1.0.0",
        contact={
            "name": "AhmedETAP",
            "url": "https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/license/mit/",
        },
    )
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    return app.openapi()


def main() -> int:
    spec = export_spec()
    if "--json" in sys.argv:
        print(json.dumps(spec, indent=2, sort_keys=False))
    else:
        print(yaml.safe_dump(spec, sort_keys=False, default_flow_style=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
