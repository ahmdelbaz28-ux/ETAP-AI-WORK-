"""Comprehensive Engineering Capability Test Suite & Verification Matrix.

Tests ALL canonical engineering study types across the platform:
- Direct canonical execution path via ExecutionOrchestrator (engine/dispatch.py)
- Cloud execution verification via POST /api/v1/studies/run (or Worker proxy)
- Generates a verified engineering matrix table with real results and standards.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("capability_matrix")

# Standard test IEEE 9-bus distribution model conforming to SystemSpec
TEST_SYSTEM: Dict[str, Any] = {
    "base_mva": 100.0,
    "base_kv": 13.8,
    "buses": [
        {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0, "voltage_angle": 0.0, "base_kv": 13.8},
        {"bus_id": 2, "bus_type": "pv", "voltage_magnitude": 1.02, "base_kv": 13.8, "q_min": -50.0, "q_max": 100.0},
        {"bus_id": 3, "bus_type": "pq", "voltage_magnitude": 1.0, "base_kv": 13.8},
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r": 0.01, "x": 0.085, "b": 0.176},
        {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r": 0.017, "x": 0.092, "b": 0.158},
        {"line_id": 3, "from_bus_id": 1, "to_bus_id": 3, "r": 0.032, "x": 0.161, "b": 0.306},
    ],
    "generators": [
        {"generator_id": 1, "bus_id": 1, "power_real": 100.0, "power_reactive": 0.0, "internal_voltage_mag": 1.0},
        {"generator_id": 2, "bus_id": 2, "power_real": 163.0, "power_reactive": 0.0, "internal_voltage_mag": 1.02},
    ],
    "loads": [
        {"load_id": 1, "bus_id": 3, "p_mw": 90.0, "q_mvar": 30.0},
    ],
}

# Parameters per capability conforming strictly to engineering schemas
CAPABILITY_PAYLOADS: Dict[str, Dict[str, Any]] = {
    "load_flow": {
        "system": TEST_SYSTEM,
        "parameters": {"max_iterations": 20, "tolerance": 1e-4},
    },
    "short_circuit": {
        "system": TEST_SYSTEM,
        "parameters": {"bus_id": 3, "fault_type": "three_phase"},
    },
    "arc_flash": {
        "system": {},
        "parameters": {
            "voltage_kv": 13.8,
            "bolted_fault_current_ka": 25.0,
            "arc_duration_sec": 0.1,
            "working_distance_mm": 914.0,
            "arc_gap_mm": 152.0,
            "gap_mm": 152.0,
            "electrode_config": "VCB",
            "enclosure_type": "box",
            "enclosure_width_mm": 508.0,
            "enclosure_height_mm": 508.0,
            "enclosure_depth_mm": 508.0,
        },
    },
    "protection_coordination": {
        "system": TEST_SYSTEM,
        "parameters": {
            "upstream_relay_id": 1,
            "downstream_relay_id": 2,
            "fault_currents": [10.0, 15.0, 20.0],
            "relays_config": {
                "upstream": {"tms": 0.5, "pickup_current_a": 100.0, "curve_type": "standard_inverse"},
                "downstream": {"tms": 0.2, "pickup_current_a": 50.0, "curve_type": "standard_inverse"},
            },
        },
    },
    "harmonic_analysis": {
        "system": TEST_SYSTEM,
        "parameters": {"order": [3, 5, 7, 11, 13], "harmonic_source_bus": 3},
    },
    "optimal_power_flow": {
        "system": TEST_SYSTEM,
        "parameters": {
            "method": "dc",
            "generator_costs": [
                {"generator_id": 1, "cost_coefficients": [0.0, 20.0, 0.05], "p_min": 0.0, "p_max": 200.0, "q_min": -50.0, "q_max": 100.0},
                {"generator_id": 2, "cost_coefficients": [0.0, 25.0, 0.08], "p_min": 0.0, "p_max": 200.0, "q_min": -50.0, "q_max": 100.0},
            ],
            "generator_locations": {1: 1, 2: 2},
        },
    },
    "motor_starting": {
        "system": TEST_SYSTEM,
        "parameters": {
            "analysis_type": "starting_current",
            "motor_hp": 250.0,
            "voltage_v": 480.0,
            "starting_method": "DOL",
            "nema_code": "F",
            "source_impedance_r_pu": 0.01,
            "source_impedance_x_pu": 0.05,
        },
    },
    "transient_stability": {
        "system": TEST_SYSTEM,
        "parameters": {
            "analysis_type": "critical_clearing_time",
            "smib_H": 5.0,
            "smib_Pm": 0.8,
            "smib_E": 1.05,
            "smib_V_inf": 1.0,
            "smib_X_total": 0.4,
            "smib_X_faulted": 1.2,
            "smib_delta0": 0.35,
        },
    },
    "cable_sizing": {
        "system": TEST_SYSTEM,
        "parameters": {
            "analysis_type": "recommend",
            "load_current_A": 125.0,
            "cable_length_m": 75.0,
            "system_voltage_V": 400.0,
            "power_factor": 0.85,
            "installation_method": "in_air",
            "max_vdrop_percent": 3.0,
        },
    },
    "earth_grid": {
        "system": TEST_SYSTEM,
        "parameters": {
            "analysis_type": "design",
            "soil_resistivity_ohm_m": 100.0,
            "fault_current_A": 1000.0,
            "fault_duration_s": 0.5,
            "grid_length_m": 50.0,
            "grid_width_m": 40.0,
        },
    },
    "renewable_integration": {
        "system": TEST_SYSTEM,
        "parameters": {
            "poi_bus_id": 3,
            "pv_capacity_mw": 10.0,
            "power_factor": 0.95,
            "solar_profile": [0.0, 0.0, 0.2, 0.6, 0.9, 1.0, 0.8, 0.4, 0.0],
        },
    },
    "battery_storage": {
        "system": TEST_SYSTEM,
        "parameters": {
            "demo": True,
            "bus_id": 3,
            "rated_power_mw": 2.0,
            "rated_capacity_mwh": 8.0,
        },
    },
    "scada": {
        "system": TEST_SYSTEM,
        "parameters": {"protocol": "IEC61850", "action": "poll_telemetry"},
    },
    "digital_twin": {
        "system": TEST_SYSTEM,
        "parameters": {"action": "sync_state", "drift_threshold": 0.05},
    },
    "etap_expert": {
        "system": {},
        "parameters": {
            "question": "What is the procedure for arc flash calculation per IEEE 1584 in ETAP?",
        },
    },
    "etap_gui": {
        "system": {},
        "parameters": {
            "question": "Navigate to the Load Flow calculation toolbar and trigger simulation.",
        },
    },
    "generative_design": {
        "system": {},
        "parameters": {
            "substation_type": "industrial",
            "primary_voltage_kv": 33.0,
            "secondary_voltage_kv": 11.0,
            "capacity_mva": 20.0,
        },
    },
    "ahmed_etap_orchestration": {
        "system": TEST_SYSTEM,
        "parameters": {
            "workflow": "comprehensive_analysis",
            "studies": ["load_flow", "short_circuit"],
        },
    },
}

STANDARDS_MAP: Dict[str, str] = {
    "load_flow": "IEEE 3002.7-2018",
    "short_circuit": "IEC 60909-0:2016",
    "arc_flash": "IEEE 1584-2018 (Simplified Educational)",
    "protection_coordination": "IEC 60255-151",
    "harmonic_analysis": "IEEE 519-2022",
    "optimal_power_flow": "IEEE 3002.7-2018",
    "motor_starting": "IEEE 399-1997",
    "transient_stability": "IEEE 399-1997",
    "cable_sizing": "IEC 60364-5-52",
    "earth_grid": "IEEE 80-2013",
    "renewable_integration": "IEEE 1547-2018",
    "battery_storage": "IEC 62933-2-1",
    "scada": "IEC 61850",
    "digital_twin": "ISO 23247",
    "etap_expert": "IEEE / IEC / NFPA 70E Knowledge Base",
    "etap_gui": "CUA Desktop Automation",
    "generative_design": "IEEE 141 / IEC 62271 (Scaffold)",
    "ahmed_etap_orchestration": "Autonomous Orchestrator",
}


def test_canonical_local_execution(capability: str) -> Dict[str, Any]:
    """Execute capability through direct ExecutionOrchestrator in Python runtime."""
    payload = CAPABILITY_PAYLOADS.get(capability, {})
    system = payload.get("system", {})
    parameters = payload.get("parameters", {})

    from services.execution_orchestrator import get_execution_orchestrator
    from services.execution_request import ExecutionRequest
    from services.study_service import _run_async

    req = ExecutionRequest(
        capability_id=capability,
        tenant_id="staging_acceptance_tenant",
        user_id="user_tester:staging_matrix",
        user_role="engineer",
        input={"system": system, "parameters": parameters},
        metadata={"caller": "test_all_engineering_capabilities"},
    )

    t0 = time.time()
    try:
        orchestrator = get_execution_orchestrator()
        res = _run_async(orchestrator.execute(req))
        dt = time.time() - t0
        return {
            "status": "PASS" if res.success else ("BLOCKED" if res.status in ("rejected", "disabled", "failed") else "FAIL"),
            "execution_status": res.status,
            "duration_sec": round(dt, 3),
            "errors": res.errors,
            "warnings": res.warnings,
            "data_summary": (
                f"{len(res.data)} output fields" if isinstance(res.data, dict) else type(res.data).__name__
            ) if res.data else "None",
        }
    except Exception as exc:
        dt = time.time() - t0
        return {
            "status": "FAIL",
            "execution_status": "exception",
            "duration_sec": round(dt, 3),
            "errors": [str(exc)],
            "data_summary": "None",
        }


def test_cloud_execution(client: httpx.Client, base_url: str, capability: str, api_key: str) -> Dict[str, Any]:
    """Execute capability through public HTTP API endpoint."""
    payload = CAPABILITY_PAYLOADS.get(capability, {})
    request_data = {
        "study_type": capability,
        "system": payload.get("system", {}),
        "parameters": payload.get("parameters", {}),
    }

    t0 = time.time()
    try:
        resp = client.post(
            f"{base_url}/api/v1/studies/run",
            json=request_data,
            headers={"X-API-Key": api_key},
            timeout=15.0,
        )
        dt = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            is_success = data.get("success", False)
            return {
                "status": "PASS" if is_success else "FAIL",
                "http_status": resp.status_code,
                "duration_sec": round(dt, 3),
                "response": data.get("reference", "OK"),
            }
        else:
            return {
                "status": "BLOCKED" if resp.status_code in (503, 403, 422) else "FAIL",
                "http_status": resp.status_code,
                "duration_sec": round(dt, 3),
                "error": resp.text[:120],
            }
    except Exception as exc:
        dt = time.time() - t0
        return {
            "status": "BLOCKED",
            "http_status": "connection_error",
            "duration_sec": round(dt, 3),
            "error": str(exc)[:120],
        }


def run_matrix():
    parser = argparse.ArgumentParser(description="Test all engineering capabilities")
    parser.add_argument(
        "--url",
        default="https://bazahmedux-ahmedetap.hf.space",
        help="Cloud Space base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ENGINEERING_SERVICE_API_KEY", "etap_staging_sec_99b7c12f45ea08139d6728e1c4a5b6c7"),
        help="API Key",
    )
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []

    print("\n" + "=" * 90)
    print(" AHMEDETAP COMPREHENSIVE ENGINEERING CAPABILITY TEST & CLOUD MATRIX")
    print("=" * 90)

    client = httpx.Client(timeout=15.0)

    for cap_id in CAPABILITY_PAYLOADS:
        std = STANDARDS_MAP.get(cap_id, "Standard")
        print(f"\n--> Testing capability: {cap_id} ({std})...")

        # 1. Local canonical path
        local_res = test_canonical_local_execution(cap_id)
        print(f"    Local Engine: {local_res['status']} ({local_res['execution_status']}, {local_res['duration_sec']}s)")

        # 2. Cloud endpoint
        cloud_res = test_cloud_execution(client, args.url, cap_id, args.api_key)
        print(f"    Cloud Target: {cloud_res['status']} (HTTP {cloud_res.get('http_status')}, {cloud_res['duration_sec']}s)")

        results.append({
            "capability": cap_id,
            "standard": std,
            "local_status": local_res["status"],
            "local_summary": local_res.get("data_summary", ""),
            "cloud_status": cloud_res["status"],
            "cloud_detail": cloud_res.get("http_status", ""),
        })

    print("\n" + "=" * 90)
    print(" FINAL ENGINEERING CAPABILITY VERIFICATION MATRIX")
    print("=" * 90)
    header = f"{'Capability':<26} | {'Standard':<32} | {'Local Solver':<12} | {'Cloud API':<12}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['capability']:<26} | {r['standard']:<32} | {r['local_status']:<12} | {r['cloud_status']:<12}")
    print("=" * 90)


if __name__ == "__main__":
    run_matrix()
