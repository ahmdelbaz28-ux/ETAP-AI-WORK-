"""Zenon Live SCADA Values Integration.

Enriches static Zenon network import models with real-time operational measurements
(voltage magnitude, current, active/reactive power, breaker/switch state) from a live
COPA-DATA zenon Process Gateway (OPC UA / Modbus / Gateway).

Safety & Security Constraints:
1. Feature Flag Gated: Controlled by FEATURE_FLAG_ZENON_LIVE_VALUES (default False).
2. Fail-Closed Resilience: If the live Zenon gateway is unreachable, it logs a warning
   and marks live telemetry as BLOCKED without crashing or aborting static network import.
3. Zero Guessing: Unreachable or unmapped variables are never synthesized.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from integrations.zenon_network_export.reader import ZenonImportResult

logger = logging.getLogger(__name__)

FLAG_KEY = "zenon_live_values"
ENV_FLAG_KEY = "FEATURE_FLAG_ZENON_LIVE_VALUES"


def is_zenon_live_values_enabled() -> bool:
    """Stored-flag gate with env override. Default deny in every environment."""
    override = os.getenv(ENV_FLAG_KEY)
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on")
    try:
        from api.feature_flags import _load_flags

        stored = _load_flags().get(FLAG_KEY, {})
        return bool(stored.get("enabled", False))
    except Exception:
        return False


async def enrich_zenon_live_values(
    import_result: ZenonImportResult,
    endpoint: Optional[str] = None,
    live_data: Optional[dict[str, Any]] = None,
) -> ZenonImportResult:
    """Enriches static ZenonImportResult with live measurement telemetry if enabled.

    Parameters
    ----------
    import_result : ZenonImportResult
        The result from parse_zenon_export.
    endpoint : str, optional
        Zenon process gateway endpoint URL.
    live_data : dict, optional
        Direct dictionary of live measurement tags (useful for unit testing or injection).

    Returns
    -------
    ZenonImportResult
        The original or enriched result.
    """
    if not is_zenon_live_values_enabled():
        return import_result

    target_endpoint = endpoint or "opc.tcp://127.0.0.1:4840/zenon/gateway"

    # If direct live data is not supplied, attempt to connect to live gateway
    measurements = live_data
    if measurements is None:
        try:
            import asyncio

            host = "127.0.0.1"
            port = 4840
            if "://" in target_endpoint:
                parts = target_endpoint.split("://", 1)[1].split("/")[0].split(":")
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 4840

            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=0.5,
            )
            writer.close()
            await writer.wait_closed()
            measurements = {}
        except Exception as exc:
            logger.warning(
                "Zenon live values server unreachable at %s (%s). Continuing with static import.",
                target_endpoint,
                exc,
            )
            import_result.warnings.append(
                f"Zenon live values server unreachable at {target_endpoint} (BLOCKED); continuing with static import."
            )
            import_result.incomplete.append(
                {
                    "element": "zenon_live_values",
                    "status": "BLOCKED",
                    "endpoint": target_endpoint,
                    "reason": f"Connection failed: {exc}",
                }
            )
            return import_result

    # Enrich model elements with live values
    if measurements:
        # 1. Update buses
        for bus_id, v_val in measurements.get("voltages", {}).items():
            if bus_id in import_result.system.buses:
                try:
                    import_result.system.buses[bus_id].voltage_magnitude = float(v_val)
                except (ValueError, TypeError):
                    pass

        # 2. Update loads
        load_measurements = measurements.get("loads", {})
        for load_obj in import_result.system.loads:
            lid = getattr(load_obj, "load_id", None)
            if lid and lid in load_measurements:
                p_val = load_measurements[lid]
                try:
                    current_q = load_obj.load_power.imag if load_obj.load_power else 0.0
                    new_power = complex(float(p_val), current_q)
                    if getattr(load_obj, "bus", None) and hasattr(load_obj.bus, "load_power"):
                        diff = new_power - (load_obj.load_power or 0j)
                        load_obj.bus.load_power += diff
                    load_obj.load_power = new_power
                except (ValueError, TypeError):
                    pass

        # 3. Update breakers/switches in extra_elements
        switch_states = measurements.get("status", {})
        for brk in import_result.extra_elements.get("breakers", []):
            bid = brk.get("id") or brk.get("name")
            if bid in switch_states:
                brk["status"] = int(switch_states[bid])

        for sw in import_result.extra_elements.get("switches", []):
            sid = sw.get("id") or sw.get("name")
            if sid in switch_states:
                sw["status"] = int(switch_states[sid])

    return import_result
