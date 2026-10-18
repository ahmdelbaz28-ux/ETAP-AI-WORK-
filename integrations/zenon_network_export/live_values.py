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
import math
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

            # TCP connection succeeded, but opening a raw TCP socket does not acquire telemetry.
            # No live Zenon binary stream / OPC UA client protocol is active to pull measurements.
            logger.warning(
                "Zenon gateway reachable via TCP at %s, but live telemetry data reader is unavailable. "
                "No live telemetry data stream acquired; continuing with static import.",
                target_endpoint,
            )
            import_result.warnings.append(
                f"Zenon gateway at {target_endpoint} reachable via TCP, but live telemetry data reading is unavailable (not supported/no data stream). "
                "Continuing with static import."
            )
            import_result.incomplete.append(
                {
                    "element": "zenon_live_values",
                    "status": "TELEMETRY_UNAVAILABLE",
                    "endpoint": target_endpoint,
                    "reason": "TCP socket connected but live telemetry protocol reader is unavailable or unsupported; no telemetry stream acquired.",
                }
            )
            return import_result
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

    # Handle explicitly provided live data
    if not measurements:
        import_result.warnings.append("Zenon live telemetry payload is empty; no operational measurements updated.")
        import_result.incomplete.append(
            {
                "element": "zenon_live_values",
                "status": "EMPTY_TELEMETRY",
                "reason": "Telemetry payload contained no variables.",
            }
        )
        return import_result

    has_readings = any(
        bool(measurements.get(k)) for k in ("voltages", "loads", "status")
    )
    if not has_readings:
        import_result.warnings.append(
            "Zenon live telemetry payload contained no voltage, load, or status readings; no measurements updated."
        )
        import_result.incomplete.append(
            {
                "element": "zenon_live_values",
                "status": "EMPTY_TELEMETRY",
                "reason": "Telemetry payload contained no operational readings (voltages, loads, or status).",
            }
        )
        return import_result

    # Enrich model elements with authentic live values
    voltages_updated = 0
    loads_updated = 0
    switches_updated = 0

    # Helper to enforce discrete binary states without float truncation
    def _parse_discrete_switch_state(val: Any) -> Optional[int]:
        if val is None or isinstance(val, (dict, list, set)):
            return None
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, (int, float)):
            if not math.isfinite(val):
                return None
            # Enforce discrete integer state - reject fractional floats like 1.5
            if float(val) != int(val):
                return None
            int_val = int(val)
            if int_val in (0, 1):
                return int_val
            return None
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("1", "true", "closed", "close", "on"):
                return 1
            if s in ("0", "false", "open", "opened", "trip", "tripped", "off"):
                return 0
            try:
                f_val = float(s)
                if math.isfinite(f_val) and f_val == int(f_val):
                    int_val = int(f_val)
                    if int_val in (0, 1):
                        return int_val
            except ValueError:
                pass
        return None

    # 1. Update buses (must be positive and finite)
    for bus_id, v_val in measurements.get("voltages", {}).items():
        if bus_id in import_result.system.buses:
            try:
                v_float = float(v_val)
                if math.isfinite(v_float) and v_float > 0.0:
                    import_result.system.buses[bus_id].voltage_magnitude = v_float
                    voltages_updated += 1
            except (ValueError, TypeError):
                pass

    # 2. Update loads (must be finite)
    load_measurements = measurements.get("loads", {})
    for load_obj in import_result.system.loads:
        lid = getattr(load_obj, "load_id", None)
        if lid and lid in load_measurements:
            p_val = load_measurements[lid]
            try:
                p_float = float(p_val)
                if math.isfinite(p_float):
                    current_q = load_obj.load_power.imag if load_obj.load_power else 0.0
                    new_power = complex(p_float, current_q)
                    if getattr(load_obj, "bus", None) and hasattr(load_obj.bus, "load_power"):
                        diff = new_power - (load_obj.load_power or 0j)
                        load_obj.bus.load_power += diff
                    load_obj.load_power = new_power
                    loads_updated += 1
            except (ValueError, TypeError):
                pass

    # 3. Update breakers/switches in extra_elements (must be discrete 0 or 1)
    switch_states = measurements.get("status", {})
    for brk in import_result.extra_elements.get("breakers", []):
        bid = brk.get("id") or brk.get("name")
        if bid in switch_states:
            parsed_st = _parse_discrete_switch_state(switch_states[bid])
            if parsed_st is not None:
                brk["status"] = parsed_st
                switches_updated += 1

    for sw in import_result.extra_elements.get("switches", []):
        sid = sw.get("id") or sw.get("name")
        if sid in switch_states:
            parsed_st = _parse_discrete_switch_state(switch_states[sid])
            if parsed_st is not None:
                sw["status"] = parsed_st
                switches_updated += 1

    total_updated = voltages_updated + loads_updated + switches_updated
    if total_updated == 0:
        import_result.extra_elements["zenon_live_enrichment"] = "NO_MATCHING_TAGS"
        import_result.warnings.append(
            "Zenon live telemetry payload contained readings, but no measurement tags matched any model elements or all values were malformed."
        )
        import_result.incomplete.append(
            {
                "element": "zenon_live_values",
                "status": "NO_MATCHING_TAGS",
                "reason": "No valid telemetry measurements could be applied to any model element (zero tags matched or valid).",
            }
        )
    else:
        import_result.extra_elements["zenon_live_enrichment"] = "ENRICHED"

    import_result.extra_elements["zenon_live_telemetry_counts"] = {
        "voltages_updated": voltages_updated,
        "loads_updated": loads_updated,
        "switches_updated": switches_updated,
    }
    return import_result
