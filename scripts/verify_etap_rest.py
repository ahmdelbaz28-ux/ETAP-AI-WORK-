"""Manual real-host gate for ETAP REST Auto-Build (NOT run in CI).

Creates ONE bus on the real ETAP DataHub host, re-reads it, compares
name/kind, deletes it, prints PASS/FAIL. If FAIL => feature stays OFF.

Usage:
    python scripts/verify_etap_rest.py --url https://<etap-host>/etapapi --token <token> --project <project-id>

Exit codes: 0 PASS, 1 FAIL, 2 BLOCKED (no DataHub/etapAPI).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Bootstrap: allow running as `python scripts/verify_etap_rest.py` from anywhere —
# repo root (parent of scripts/) must be importable for `etap_integration`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import httpx  # noqa: F401
    import pydantic  # noqa: F401
except ImportError:
    print("BLOCKED: missing dependencies. Run with the project interpreter:")
    print('  pip install httpx "pydantic>=2"')
    sys.exit(2)


async def _main(url: str, token: str, project: str) -> int:
    from urllib.parse import urlparse

    from etap_integration.etap_rest import EtapDrawPlan, EtapRestClient

    host = urlparse(url).hostname or ""
    if not host or "<" in url or ">" in url or any(ord(c) > 127 for c in host):
        print("BLOCKED: bad --url. Use the REAL DataHub host (ASCII only), e.g.:")
        print('  --url "https://192.168.1.50/etapapi"   (no <> placeholders, no description words)')
        print("Tip: the same host must open https://<host>/etapapi/swagger in a browser.")
        return 2

    client = EtapRestClient(base_url=url, token=token)
    if not await client.health_check():
        print("BLOCKED: DataHub/etapAPI not reachable — do not enable etap_rest_draw.")
        return 2
    plan = EtapDrawPlan(
        project_id=project,
        items=[{"element_type": "bus", "name": "VERIFY_BUS_1", "properties": {"base_kv": 11.0}}],
        reason="manual verify-etap-rest gate",
    )
    try:
        result = await client.apply_draw(plan)
    except Exception as exc:  # noqa: BLE001 - manual gate reports any failure
        print(f"FAIL: apply_draw raised {type(exc).__name__}: {exc}")
        return 1
    if not result.readback_verified or not result.created_ids:
        print("FAIL: draw not verified.")
        return 1
    await client.delete_elements(project, result.created_ids)
    print(f"PASS: drawing={result.drawing_id} verified + cleaned up.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Real-host ETAP REST verify gate (manual, not CI).")
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    return asyncio.run(_main(args.url, args.token, args.project))


if __name__ == "__main__":
    sys.exit(main())
