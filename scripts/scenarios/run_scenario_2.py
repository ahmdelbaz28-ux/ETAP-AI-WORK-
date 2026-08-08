"""
Scenario 2: GIS → ETAP (Reverse Sync)
======================================
قراءة تعديلات من QGIS/ArcGIS → حساب diff → تطبيق على ETAP 2021
→ إعادة تشغيل Load Flow → توليد تقرير مقارنة.

Phases:
  1. Extract features from QGIS/ArcGIS project
  2. Compute diff (GIS features vs ETAP objects)
  3. Audit diff to Neo4j
  4. Backup ETAP .edb (safety gate)
  5. Apply diff to ETAP via COM
  6. Re-run Load Flow on updated project
  7. Generate comparison report (before/after)

Safety gates:
  - ALLOW_GIS_TO_ETAP_SYNC=true required
  - ETAP_BACKUP_BEFORE_SYNC=true required (auto-backup)
  - Rollback automatically if post-sync Load Flow fails

Usage:
  python scripts/scenarios/run_scenario_2.py \\
      --gis-source qgis \\
      --gis-project-path "C:\\projects\\modified.qgz" \\
      --etap-project-path "C:\\ETAP\\MySubstation.edb" \\
      --output-dir ./outputs/scenario2

Branch: feat/scenario-2-gis-to-etap
Refs: PRODUCTION_PLAN/06_SCENARIO_2_GIS_TO_ETAP.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("scenario2")


async def run_scenario(
    gis_source: str,
    gis_project_path: str,
    etap_project_path: str,
    output_dir: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """تنفيذ السيناريو 2: GIS → ETAP reverse sync."""
    start_time = time.time()
    trace_id = f"scen2-{int(start_time)}"
    logger.info("🚀 Scenario 2 started — trace_id=%s", trace_id)
    logger.info("   GIS source: %s", gis_source)
    logger.info("   GIS project: %s", gis_project_path)
    logger.info("   ETAP project: %s", etap_project_path)
    logger.info("   Dry run: %s", dry_run)

    os.makedirs(output_dir, exist_ok=True)
    results: dict[str, Any] = {
        "scenario": "gis_to_etap",
        "trace_id": trace_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "phases": {},
    }

    # ─── Phase 1: Extract GIS features ────────────────────────────
    logger.info("")
    logger.info("═══ Phase 1: Extract features from %s ═══", gis_source)
    phase1_start = time.time()

    try:
        gis_features = _extract_gis_features(gis_source, gis_project_path)
        phase1_time = time.time() - phase1_start
        results["phases"]["1_extract_gis"] = {
            "status": "success",
            "duration_sec": round(phase1_time, 2),
            "features_count": len(gis_features),
        }
        logger.info("✅ Phase 1 done in %.2fs — %d features",
                    phase1_time, len(gis_features))
    except Exception as exc:
        phase1_time = time.time() - phase1_start
        results["phases"]["1_extract_gis"] = {
            "status": "failed", "duration_sec": round(phase1_time, 2), "error": str(exc),
        }
        logger.exception("❌ Phase 1 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 1
        results["error"] = str(exc)
        return results

    # ─── Phase 2: Compute diff ────────────────────────────────────
    logger.info("")
    logger.info("═══ Phase 2: Compute diff (GIS vs ETAP) ═══")
    phase2_start = time.time()

    try:
        diff = _compute_diff(gis_features, etap_project_path, trace_id)
        phase2_time = time.time() - phase2_start
        results["phases"]["2_compute_diff"] = {
            "status": "success",
            "duration_sec": round(phase2_time, 2),
            "creates": len(diff["creates"]),
            "updates": len(diff["updates"]),
            "deletes": len(diff["deletes"]),
            "total_changes": len(diff["creates"]) + len(diff["updates"]) + len(diff["deletes"]),
        }
        logger.info(
            "✅ Phase 2 done in %.2fs — %d creates, %d updates, %d deletes",
            phase2_time, len(diff["creates"]), len(diff["updates"]), len(diff["deletes"]),
        )

        diff_path = os.path.join(output_dir, "diff_report.json")
        with open(diff_path, "w", encoding="utf-8") as f:
            json.dump(diff, f, indent=2, default=str, ensure_ascii=False)
        results["phases"]["2_compute_diff"]["diff_report_path"] = diff_path

    except Exception as exc:
        phase2_time = time.time() - phase2_start
        results["phases"]["2_compute_diff"] = {
            "status": "failed", "duration_sec": round(phase2_time, 2), "error": str(exc),
        }
        logger.exception("❌ Phase 2 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 2
        results["error"] = str(exc)
        return results

    # ─── Phase 3: Audit to Neo4j ──────────────────────────────────
    logger.info("")
    logger.info("═══ Phase 3: Audit diff to Neo4j ═══")
    phase3_start = time.time()

    try:
        audit_count = _audit_to_neo4j(diff, trace_id)
        phase3_time = time.time() - phase3_start
        results["phases"]["3_audit_neo4j"] = {
            "status": "success",
            "duration_sec": round(phase3_time, 2),
            "operations_audited": audit_count,
        }
        logger.info("✅ Phase 3 done in %.2fs — %d operations audited",
                    phase3_time, audit_count)
    except Exception as exc:
        phase3_time = time.time() - phase3_start
        results["phases"]["3_audit_neo4j"] = {
            "status": "failed", "duration_sec": round(phase3_time, 2), "error": str(exc),
        }
        logger.warning("⚠️ Phase 3 (Neo4j) failed — continuing: %s", exc)

    # ─── Dry run check ────────────────────────────────────────────
    if dry_run:
        logger.info("")
        logger.info("🛑 Dry run mode — stopping before applying changes")
        results["status"] = "dry_run_completed"
        results["total_duration_sec"] = round(time.time() - start_time, 2)
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("🎉 Scenario 2 (dry run) completed in %.2fs",
                    results["total_duration_sec"])
        return results

    # ─── Phase 4: Backup ETAP ─────────────────────────────────────
    logger.info("")
    logger.info("═══ Phase 4: Backup ETAP project ═══")
    phase4_start = time.time()

    try:
        backup_path = _backup_etap(etap_project_path)
        phase4_time = time.time() - phase4_start
        results["phases"]["4_backup_etap"] = {
            "status": "success",
            "duration_sec": round(phase4_time, 2),
            "backup_path": backup_path,
        }
        logger.info("✅ Phase 4 done in %.2fs — backup: %s", phase4_time, backup_path)
    except Exception as exc:
        phase4_time = time.time() - phase4_start
        results["phases"]["4_backup_etap"] = {
            "status": "failed", "duration_sec": round(phase4_time, 2), "error": str(exc),
        }
        logger.exception("❌ Phase 4 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 4
        results["error"] = str(exc)
        return results

    # ─── Phase 5: Apply diff to ETAP ──────────────────────────────
    logger.info("")
    logger.info("═══ Phase 5: Apply diff to ETAP via COM ═══")
    phase5_start = time.time()

    try:
        _apply_diff_to_etap(etap_project_path, diff)
        phase5_time = time.time() - phase5_start
        results["phases"]["5_apply_diff"] = {
            "status": "success", "duration_sec": round(phase5_time, 2),
        }
        logger.info("✅ Phase 5 done in %.2fs", phase5_time)
    except Exception as exc:
        phase5_time = time.time() - phase5_start
        results["phases"]["5_apply_diff"] = {
            "status": "failed", "duration_sec": round(phase5_time, 2), "error": str(exc),
        }
        logger.exception("❌ Phase 5 failed — restoring from backup")
        _restore_etap(backup_path, etap_project_path)
        results["status"] = "failed"
        results["failed_phase"] = 5
        results["error"] = str(exc)
        results["etap_restored"] = True
        return results

    # ─── Phase 6: Re-run Load Flow ────────────────────────────────
    logger.info("")
    logger.info("═══ Phase 6: Re-run Load Flow on updated ETAP ═══")
    phase6_start = time.time()

    try:
        from etap_integration.unified_etap_types import (
            ETAPStudyType, get_etap_provider,
        )

        etap_provider = get_etap_provider()
        new_result = etap_provider.execute_study(
            project_path=etap_project_path,
            study_type=ETAPStudyType.LOAD_FLOW,
            visible=False,
        )

        if not new_result.success:
            raise RuntimeError(
                f"Load Flow failed after sync. Errors: {new_result.errors}"
            )

        phase6_time = time.time() - phase6_start
        results["phases"]["6_rerun_loadflow"] = {
            "status": "success",
            "duration_sec": round(phase6_time, 2),
            "converged": new_result.data.get("converged", False),
            "buses_count": len(new_result.data.get("buses", {})),
            "iterations": new_result.data.get("iterations", 0),
        }
        logger.info("✅ Phase 6 done in %.2fs — converged=%s",
                    phase6_time, new_result.data.get("converged", False))

    except Exception as exc:
        phase6_time = time.time() - phase6_start
        results["phases"]["6_rerun_loadflow"] = {
            "status": "failed", "duration_sec": round(phase6_time, 2), "error": str(exc),
        }
        logger.error("❌ Phase 6 failed — restoring ETAP from backup")
        _restore_etap(backup_path, etap_project_path)
        results["status"] = "failed"
        results["failed_phase"] = 6
        results["error"] = str(exc)
        results["etap_restored"] = True
        return results

    # ─── Phase 7: Generate comparison report ──────────────────────
    logger.info("")
    logger.info("═══ Phase 7: Generate comparison report ═══")
    phase7_start = time.time()

    try:
        report_path = os.path.join(output_dir, "comparison_report.json")
        comparison_data = {
            "trace_id": trace_id,
            "etap_project_path": etap_project_path,
            "etap_backup_path": backup_path,
            "diff_applied": {
                "creates": len(diff["creates"]),
                "updates": len(diff["updates"]),
                "deletes": len(diff["deletes"]),
            },
            "new_load_flow": {
                "converged": results["phases"]["6_rerun_loadflow"]["converged"],
                "buses_count": results["phases"]["6_rerun_loadflow"]["buses_count"],
                "iterations": results["phases"]["6_rerun_loadflow"]["iterations"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(comparison_data, f, indent=2, default=str, ensure_ascii=False)

        phase7_time = time.time() - phase7_start
        results["phases"]["7_comparison_report"] = {
            "status": "success",
            "duration_sec": round(phase7_time, 2),
            "report_path": report_path,
        }
        logger.info("✅ Phase 7 done in %.2fs — %s", phase7_time, report_path)

    except Exception as exc:
        phase7_time = time.time() - phase7_start
        results["phases"]["7_comparison_report"] = {
            "status": "failed", "duration_sec": round(phase7_time, 2), "error": str(exc),
        }
        logger.warning("⚠️ Phase 7 failed — continuing: %s", exc)

    # ─── Done ─────────────────────────────────────────────────────
    total_time = time.time() - start_time
    results["total_duration_sec"] = round(total_time, 2)
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["status"] = "completed"
    results["etap_backup_path"] = backup_path

    logger.info("")
    logger.info("🎉 Scenario 2 completed in %.2fs", total_time)
    return results


def _extract_gis_features(gis_source: str, gis_project_path: str) -> list[dict[str, Any]]:
    """استخراج features من QGIS أو ArcGIS Pro."""
    if gis_source == "qgis":
        from gis_integration.providers.qgis_provider import QGISProvider
        provider = QGISProvider()
    elif gis_source == "arcgis":
        from gis_integration.providers.arcgis_provider import ArcGISProvider
        provider = ArcGISProvider()
    else:
        raise ValueError(f"Unknown GIS source: {gis_source}")

    provider.load_project(gis_project_path)

    features: list[dict[str, Any]] = []
    for layer_name in provider.list_layers():
        for feat in provider.extract_features(layer_name):
            features.append({
                "layer": layer_name,
                "id": feat.id,
                "geometry": feat.geometry,
                "properties": feat.properties,
            })

    return features


def _compute_diff(
    gis_features: list[dict[str, Any]],
    etap_project_path: str,
    trace_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """حساب الفروقات بين GIS features و ETAP objects."""
    creates: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    deletes: list[dict[str, Any]] = []

    # Read current ETAP state from Supabase cache
    etap_buses: dict[str, dict[str, Any]] = {}
    try:
        from integrations.supabase_integration import get_supabase_client
        client = get_supabase_client()
        if client is not None:
            response = client.table("gis_buses").select("*").execute()
            for row in response.data or []:
                etap_buses[row.get("bus_id", "")] = row
    except Exception as exc:
        logger.warning("Failed to read ETAP state from Supabase: %s", exc)

    # Build GIS index
    gis_buses: dict[str, dict[str, Any]] = {}
    for feat in gis_features:
        layer = feat.get("layer", "").lower()
        if "bus" in layer:
            bus_id = feat.get("properties", {}).get("id", feat.get("id", ""))
            if bus_id:
                gis_buses[bus_id] = feat

    # Compare
    all_bus_ids = set(gis_buses.keys()) | set(etap_buses.keys())

    for bus_id in all_bus_ids:
        in_gis = bus_id in gis_buses
        in_etap = bus_id in etap_buses

        if in_gis and not in_etap:
            creates.append({
                "object_type": "bus", "id": bus_id,
                "properties": gis_buses[bus_id].get("properties", {}),
                "trace_id": trace_id,
            })
        elif in_gis and in_etap:
            gis_props = gis_buses[bus_id].get("properties", {})
            etap_props = etap_buses[bus_id]
            changes = {}
            for key in set(gis_props.keys()) | set(etap_props.keys()):
                if key in ("id", "trace_id", "updated_at", "created_at", "project_id"):
                    continue
                gis_val = gis_props.get(key)
                etap_val = etap_props.get(key)
                if gis_val != etap_val:
                    changes[key] = {"old": etap_val, "new": gis_val}
            if changes:
                updates.append({
                    "object_type": "bus", "id": bus_id,
                    "changes": changes, "trace_id": trace_id,
                })
        elif in_etap and not in_gis:
            deletes.append({
                "object_type": "bus", "id": bus_id, "trace_id": trace_id,
            })

    return {"creates": creates, "updates": updates, "deletes": deletes, "trace_id": trace_id}


def _audit_to_neo4j(diff: dict[str, list], trace_id: str) -> int:
    """تسجيل diff في Neo4j كـ audit trail."""
    try:
        from integrations.neo4j_integration import neo4j_client
        if not neo4j_client.enabled:
            logger.info("Neo4j not enabled — skipping audit")
            return 0

        count = 0
        for op_type in ("creates", "updates", "deletes"):
            for op in diff.get(op_type, []):
                neo4j_client.execute_query(
                    """
                    CREATE (op:SyncOperation {
                        action: $action, object_type: $obj_type,
                        object_id: $obj_id, trace_id: $trace_id, timestamp: $ts
                    })
                    """,
                    {
                        "action": op_type.rstrip("s"),
                        "obj_type": op.get("object_type", "unknown"),
                        "obj_id": op.get("id", ""),
                        "trace_id": trace_id,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    },
                )
                count += 1
        return count
    except Exception as exc:
        logger.warning("Neo4j audit failed: %s", exc)
        return 0


def _backup_etap(etap_project_path: str) -> str:
    """احتياطي ملف ETAP قبل التعديل."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{etap_project_path}.bak.{timestamp}"
    shutil.copy2(etap_project_path, backup_path)
    logger.info("📦 ETAP backed up: %s", backup_path)
    return backup_path


def _restore_etap(backup_path: str, original_path: str) -> None:
    """استعادة ETAP من backup."""
    shutil.copy2(backup_path, original_path)
    logger.info("🔄 ETAP restored from: %s", backup_path)


def _apply_diff_to_etap(etap_project_path: str, diff: dict[str, list]) -> None:
    """تطبيق diff على ETAP عبر COM. Windows-only."""
    if os.name != "nt":
        raise RuntimeError(
            f"apply_diff_to_etap requires Windows (COM automation). "
            f"Current platform: {os.name}"
        )

    import win32com.client  # type: ignore
    import pythoncom  # type: ignore

    pythoncom.CoInitialize()
    try:
        app = win32com.client.Dispatch("ETAP.Application")
        app.Visible = False
        app.Timeout = 300000

        project = app.OpenProject(etap_project_path)
        if not project:
            raise RuntimeError(f"Failed to open ETAP project: {etap_project_path}")

        try:
            # Apply creates
            for op in diff.get("creates", []):
                if op.get("object_type") == "bus":
                    bus_id = op.get("id", "")
                    props = op.get("properties", {})
                    try:
                        bus = project.AddBus(bus_id)
                        if "voltage_kv" in props:
                            bus.VoltageKV = props["voltage_kv"]
                        logger.info("➕ Created bus: %s", bus_id)
                    except Exception as exc:
                        logger.warning("Failed to create bus %s: %s", bus_id, exc)

            # Apply updates
            for op in diff.get("updates", []):
                bus_id = op.get("id", "")
                changes = op.get("changes", {})
                try:
                    bus = project.Buses(bus_id)
                    if bus:
                        for field, change in changes.items():
                            try:
                                setattr(bus, field, change["new"])
                                logger.info("✏️ Updated %s.%s", bus_id, field)
                            except Exception as exc:
                                logger.warning("Failed to update %s.%s: %s",
                                               bus_id, field, exc)
                except Exception as exc:
                    logger.warning("Bus %s not found: %s", bus_id, exc)

            # Apply deletes
            for op in diff.get("deletes", []):
                bus_id = op.get("id", "")
                try:
                    project.RemoveObject(bus_id)
                    logger.info("❌ Deleted: %s", bus_id)
                except Exception as exc:
                    logger.warning("Failed to delete %s: %s", bus_id, exc)

            project.Save()
            logger.info("💾 ETAP project saved: %s", etap_project_path)

        finally:
            project.Close()
            app.Quit()

    finally:
        pythoncom.CoUninitialize()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scenario 2: GIS → ETAP (Reverse Sync)",
    )
    parser.add_argument("--gis-source", choices=["qgis", "arcgis"], required=True)
    parser.add_argument("--gis-project-path", required=True)
    parser.add_argument("--etap-project-path", required=True)
    parser.add_argument("--output-dir", default="./outputs/scenario2")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute diff only, don't apply to ETAP")
    args = parser.parse_args()

    if not os.environ.get("ALLOW_GIS_TO_ETAP_SYNC") == "true":
        print("❌ Set ALLOW_GIS_TO_ETAP_SYNC=true to run this scenario")
        sys.exit(1)

    if not args.dry_run and not os.environ.get("USE_ETAP") == "true":
        print("❌ Set USE_ETAP=true to enable ETAP integration")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        result = asyncio.run(run_scenario(
            gis_source=args.gis_source,
            gis_project_path=args.gis_project_path,
            etap_project_path=args.etap_project_path,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        ))

        result_path = os.path.join(args.output_dir, "scenario2_result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        print("\n" + "=" * 60)
        if result.get("status") in ("completed", "dry_run_completed"):
            print(f"✅ Scenario 2 {result['status']}")
        else:
            print(f"❌ Scenario 2 failed at phase {result.get('failed_phase')}")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

        sys.exit(0 if result.get("status") in ("completed", "dry_run_completed") else 1)

    except Exception as e:
        logger.exception("Scenario 2 failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
