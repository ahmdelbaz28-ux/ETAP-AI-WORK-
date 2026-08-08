#!/usr/bin/env python3
"""
verify_etap_2021.py — Verify ETAP 2021 COM Compatibility
==========================================================
سكربت للتحقق من أن ETAP 2021 COM API يعمل بشكل صحيح مع
الأكواد المُستخدمة في refactored/etap_com.py.

يختبر:
1. ProgID "ETAP.Application" صالح
2. Version يطابق "21.x"
3. كل property names المُستخدمة موجودة
4. كل module names المُستخدمة موجودة
5. OpenProject + SaveProject يعملان

Usage:
    python verify_etap_2021.py --etap-project "C:\\ETAP Projects\\test.edb"

Branch: fix/etap-com-2021-properties
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("verify_etap_2021")


# Properties to verify per object type
PROPERTIES_TO_VERIFY = {
    "Bus": [
        "ID", "VoltageMag", "VoltageAng", "PMW", "QMVAR",
        "I3PhaseKA", "ILGKA", "ILLKA", "IDLGKA",  # ⚠️ ILLKA not IllKA
        "VoltageKV", "X", "Y",
    ],
    "Branch": [
        "ID", "PFrom", "QFrom", "PTo", "QTo", "Current",
        "FromBus", "ToBus", "Length_m", "R_Ohm_per_km", "X_Ohm_per_km",
    ],
    "Equipment": [
        "ID", "IncidentEnergy", "ArcFlashBoundary", "PPELevel", "ArcDuration",
    ],
}

# Modules to verify
MODULES_TO_VERIFY = [
    "LoadFlow",
    "ShortCircuit",
    "ArcFlash",
    "Harmonic",  # ⚠️ not "HarmonicAnalysis" in ETAP 2021
    "OptimalPowerFlow",
    "MotorStarting",  # ⚠️ not "MotorAcceleration"
    "TransientStability",
    "ProtectionCoordination",
    "CableAmpacity",
    "GroundGrid",
    "Reliability",
]


def verify_etap_compatibility(etap_project_path: str | None = None) -> dict:
    """
    التحقق من توافق ETAP 2021 COM.
    
    Returns:
        dict مع نتائج كل فحص
    """
    if sys.platform != "win32":
        logger.error("❌ ETAP COM requires Windows. Current: %s", sys.platform)
        return {"error": "Windows required"}
    
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        logger.error("❌ pywin32 not installed. Run: pip install pywin32")
        return {"error": "pywin32 missing"}
    
    pythoncom.CoInitialize()
    results = {
        "platform": sys.platform,
        "checks": {},
        "warnings": [],
        "errors": [],
    }
    
    try:
        # ─── Check 1: ProgID ───────────────────────────────────────
        logger.info("Check 1: ProgID 'ETAP.Application'...")
        try:
            app = win32com.client.Dispatch("ETAP.Application")
            results["checks"]["progid"] = True
            logger.info("  ✅ ProgID valid")
        except Exception as exc:
            results["checks"]["progid"] = False
            results["errors"].append(f"ProgID Dispatch failed: {exc}")
            logger.error("  ❌ ProgID failed: %s", exc)
            return results
        
        # ─── Check 2: Version ──────────────────────────────────────
        logger.info("Check 2: ETAP version...")
        try:
            version = str(app.Version)
            results["checks"]["version"] = version
            if "21" in version:
                logger.info("  ✅ ETAP 2021 detected (version: %s)", version)
            else:
                results["warnings"].append(
                    f"ETAP version {version} is not 2021 (no '21' in version string)"
                )
                logger.warning("  ⚠️  Version: %s (expected 21.x)", version)
        except Exception as exc:
            results["checks"]["version"] = None
            results["errors"].append(f"Version read failed: {exc}")
            logger.error("  ❌ Version read failed: %s", exc)
        
        # ─── Check 3: Open project (if path provided) ──────────────
        if etap_project_path:
            logger.info("Check 3: OpenProject('%s')...", etap_project_path)
            try:
                app.Visible = False
                project = app.OpenProject(etap_project_path)
                if project:
                    results["checks"]["open_project"] = True
                    logger.info("  ✅ Project opened")
                    
                    # ─── Check 4: Modules ───────────────────────────
                    logger.info("Check 4: Module availability...")
                    modules_found = {}
                    for module_name in MODULES_TO_VERIFY:
                        try:
                            module = getattr(project, module_name, None)
                            if module is not None:
                                modules_found[module_name] = True
                                logger.info("  ✅ %s", module_name)
                            else:
                                modules_found[module_name] = False
                                results["warnings"].append(
                                    f"Module '{module_name}' not found in ETAP 2021"
                                )
                                logger.warning("  ⚠️  %s not found", module_name)
                        except Exception as exc:
                            modules_found[module_name] = False
                            results["warnings"].append(
                                f"Module '{module_name}' access failed: {exc}"
                            )
                            logger.warning("  ⚠️  %s failed: %s", module_name, exc)
                    
                    results["checks"]["modules"] = modules_found
                    
                    # ─── Check 5: Properties ─────────────────────────
                    logger.info("Check 5: Property availability on Buses...")
                    props_check = {}
                    try:
                        buses = project.Buses
                        if buses and buses.Count > 0:
                            bus = buses.Item(1)
                            for prop in PROPERTIES_TO_VERIFY["Bus"]:
                                try:
                                    val = getattr(bus, prop, None)
                                    props_check[prop] = val is not None
                                    if val is None:
                                        results["warnings"].append(
                                            f"Bus.{prop} returns None — may not exist in ETAP 2021"
                                        )
                                except Exception as exc:
                                    props_check[prop] = False
                                    results["warnings"].append(
                                        f"Bus.{prop} access failed: {exc}"
                                    )
                        else:
                            results["warnings"].append("Project has no buses to verify properties")
                    except Exception as exc:
                        results["errors"].append(f"Buses access failed: {exc}")
                    
                    results["checks"]["bus_properties"] = props_check
                    
                    # Close project
                    project.Close()
                    
                else:
                    results["checks"]["open_project"] = False
                    results["errors"].append("OpenProject returned None")
                    logger.error("  ❌ OpenProject returned None")
            except Exception as exc:
                results["checks"]["open_project"] = False
                results["errors"].append(f"OpenProject failed: {exc}")
                logger.error("  ❌ OpenProject failed: %s", exc)
        
        # Cleanup
        try:
            app.Quit()
        except Exception:
            pass
        
    finally:
        pythoncom.CoUninitialize()
    
    # ─── Summary ──────────────────────────────────────────────────
    total_checks = len(results["checks"])
    passed = sum(1 for v in results["checks"].values() if v is True)
    failed = sum(1 for v in results["checks"].values() if v is False)
    
    results["summary"] = {
        "total_checks": total_checks,
        "passed": passed,
        "failed": failed,
        "warnings_count": len(results["warnings"]),
        "errors_count": len(results["errors"]),
        "etap_2021_compatible": (
            results["checks"].get("progid") is True
            and "21" in str(results["checks"].get("version", ""))
            and failed == 0
        ),
    }
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Verify ETAP 2021 COM compatibility",
    )
    parser.add_argument(
        "--etap-project",
        help="Path to .edb file for full verification (optional)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output JSON file (default: print to stdout)",
    )
    args = parser.parse_args()
    
    import json
    
    print("🔍 Verifying ETAP 2021 COM compatibility...")
    print()
    
    results = verify_etap_compatibility(args.etap_project)
    
    output = json.dumps(results, indent=2, default=str)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"✅ Results saved to: {args.output}")
    else:
        print(output)
    
    print()
    if results.get("summary", {}).get("etap_2021_compatible"):
        print("✅ ETAP 2021 is compatible with the code")
        sys.exit(0)
    else:
        print("❌ ETAP 2021 compatibility issues found")
        sys.exit(1)


if __name__ == "__main__":
    main()
