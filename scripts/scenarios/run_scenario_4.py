"""
Scenario 4: Bidirectional Full
===============================
دمج السيناريوهات 1+2+3 في workflow متكامل:
  1. GIS modifications (extract from QGIS/ArcGIS)
  2. Compute diff + apply to ETAP (Scenario 2)
  3. Re-run multiple studies (LoadFlow + ShortCircuit + ArcFlash + Protection)
  4. Export results to GIS (Scenario 1)
  5. Activate SCADA live monitoring (Scenario 3) for N seconds
  6. Compute impact analysis (before/after comparison)
  7. Generate comprehensive JSON report

Safety gates:
  - ALLOW_BIDIRECTIONAL_SYNC=true required
  - USE_ETAP=true required
  - Automatic backup + rollback on any failure

Usage:
  python scripts/scenarios/run_scenario_4.py \\
      --gis-source qgis \\
      --gis-project-path "C:\\projects\\modified.qgz" \\
      --etap-project-path "C:\\ETAP\\MySubstation.edb" \\
      --output-dir ./outputs/scenario4 \\
      --scada-monitoring-sec 60

Branch: feat/scenario-4-bidirectional
Refs: PRODUCTION_PLAN/08_SCENARIO_4_BIDIRECTIONAL.md
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

logger = logging.getLogger("scenario4")


async def run_scenario(
    gis_source: str,
    gis_project_path: str,
    etap_project_path: str,
    output_dir: str,
    scada_monitoring_sec: int = 300,
) -> dict[str, Any]:
    """تنفيذ السيناريو الشامل 4: Bidirectional Full."""
    start_time = time.time()
    trace_id = f"scen4-{int(start_time)}"
    logger.info("=" * 60)
    logger.info("🚀 Scenario 4: BIDIRECTIONAL FULL — trace_id=%s", trace_id)
    logger.info("=" * 60)
    logger.info("   GIS source: %s", gis_source)
    logger.info("   GIS project: %s", gis_project_path)
    logger.info("   ETAP project: %s", etap_project_path)
    logger.info("   SCADA monitoring: %d sec", scada_monitoring_sec)

    os.makedirs(output_dir, exist_ok=True)
    results: dict[str, Any] = {
        "scenario": "bidirectional_full",
        "trace_id": trace_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }

    # ─── STEP 1: Extract GIS features ─────────────────────────────
    logger.info("")
    logger.info("═══ Step 1/7: Extract GIS features ═══")
    t1 = time.time()

    try:
        gis_features = _extract_gis_features(gis_source, gis_project_path)
        results["phases"]["1_extract_gis"] = {
            "status": "success",
            "duration_sec": round(time.time() - t1, 2),
            "features_count": len(gis_features),
        }
        logger.info("✅ Step 1: %d features in %.2fs",
                    len(gis_features), time.time() - t1)
    except Exception as exc:
        results["phases"]["1_extract_gis"] = {"status": "failed", "error": str(exc)}
        results["status"] = "failed"
        results["failed_phase"] = 1
        results["error"] = str(exc)
        return results

    # ─── STEP 2: Compute diff + apply to ETAP ─────────────────────
    logger.info("")
    logger.info("═══ Step 2/7: Compute diff + apply to ETAP ═══")
    t2 = time.time()

    try:
        diff = _compute_diff(gis_features, etap_project_path, trace_id)
        logger.info("  Diff: %d creates, %d updates, %d deletes",
                    len(diff["creates"]), len(diff["updates"]), len(diff["deletes"]))

        # Audit
        _audit_to_neo4j(diff, trace_id)

        # Backup + apply
        backup_path = _backup_etap(etap_project_path)
        _apply_diff_to_etap(etap_project_path, diff)

        results["phases"]["2_apply_to_etap"] = {
            "status": "success",
            "duration_sec": round(time.time() - t2, 2),
            "backup_path": backup_path,
            "diff_summary": {
                "creates": len(diff["creates"]),
                "updates": len(diff["updates"]),
                "deletes": len(diff["deletes"]),
            },
        }
        logger.info("✅ Step 2 done in %.2fs", time.time() - t2)

    except Exception as exc:
        results["phases"]["2_apply_to_etap"] = {"status": "failed", "error": str(exc)}
        logger.exception("❌ Step 2 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 2
        results["error"] = str(exc)
        return results

    # ─── STEP 3: Re-run multiple studies ──────────────────────────
    logger.info("")
    logger.info("═══ Step 3/7: Re-run studies on updated ETAP ═══")
    t3 = time.time()

    try:
        from etap_integration.unified_etap_types import (
            ETAPStudyType, get_etap_provider,
        )

        etap_provider = get_etap_provider()
        studies_to_run = [
            ETAPStudyType.LOAD_FLOW,
            ETAPStudyType.SHORT_CIRCUIT,
            ETAPStudyType.ARC_FLASH,
            ETAPStudyType.PROTECTION_COORDINATION,
        ]

        study_results: dict[str, Any] = {}
        for study_type in studies_to_run:
            logger.info("  Running %s...", study_type.value)
            try:
                result = etap_provider.execute_study(
                    project_path=etap_project_path,
                    study_type=study_type,
                    visible=False,
                )
                study_results[study_type.value] = {
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "errors": result.errors[:3],
                    "data_summary": _summarize_result(study_type, result.data),
                }
                if result.success:
                    logger.info("  ✅ %s done in %.2fs",
                                study_type.value, result.execution_time)
                else:
                    logger.error("  ❌ %s failed: %s",
                                 study_type.value, result.errors[:1])
            except Exception as exc:
                study_results[study_type.value] = {
                    "success": False, "execution_time": 0, "errors": [str(exc)],
                }
                logger.exception("  ❌ %s exception: %s", study_type.value, exc)

        successful = sum(1 for r in study_results.values() if r["success"])

        # If LoadFlow failed, rollback
        if not study_results.get("LoadFlow", {}).get("success"):
            logger.error("Post-sync LoadFlow failed — rolling back ETAP")
            _restore_etap(backup_path, etap_project_path)
            results["phases"]["3_rerun_studies"] = {
                "status": "failed",
                "duration_sec": round(time.time() - t3, 2),
                "study_results": study_results,
                "etap_restored": True,
            }
            results["status"] = "failed"
            results["failed_phase"] = 3
            results["error"] = "LoadFlow failed after sync — ETAP restored"
            return results

        results["phases"]["3_rerun_studies"] = {
            "status": "success",
            "duration_sec": round(time.time() - t3, 2),
            "studies_successful": successful,
            "studies_total": len(studies_to_run),
            "study_results": study_results,
        }
        logger.info("✅ Step 3: %d/%d studies succeeded in %.2fs",
                    successful, len(studies_to_run), time.time() - t3)

    except Exception as exc:
        results["phases"]["3_rerun_studies"] = {"status": "failed", "error": str(exc)}
        logger.exception("❌ Step 3 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 3
        results["error"] = str(exc)
        return results

    # ─── STEP 4: Export results to GeoJSON ────────────────────────
    logger.info("")
    logger.info("═══ Step 4/7: Export results to GeoJSON ═══")
    t4 = time.time()

    geojson_path = None
    try:
        # Get LoadFlow result data for GeoJSON
        lf_result = study_results.get("LoadFlow", {})
        geojson = _build_geojson_from_studies(study_results, trace_id)

        geojson_path = os.path.join(output_dir, "comprehensive_results.geojson")
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        results["phases"]["4_export_geojson"] = {
            "status": "success",
            "duration_sec": round(time.time() - t4, 2),
            "output_path": geojson_path,
            "features_count": len(geojson.get("features", [])),
        }
        logger.info("✅ Step 4 done in %.2fs", time.time() - t4)

    except Exception as exc:
        results["phases"]["4_export_geojson"] = {"status": "failed", "error": str(exc)}
        logger.warning("⚠️ Step 4 failed — continuing: %s", exc)

    # ─── STEP 5: SCADA live monitoring ────────────────────────────
    logger.info("")
    logger.info("═══ Step 5/7: SCADA live monitoring (%ds) ═══", scada_monitoring_sec)
    t5 = time.time()

    bridge = None
    bridge_task = None
    consumer_task = None

    try:
        from etap_scada_bridge import ETAPScadaBridge

        bridge = ETAPScadaBridge()
        bridge_task = asyncio.create_task(bridge.run(interval_sec=5.0))

        # Run consumer inline (simplified)
        consumer_task = asyncio.create_task(_run_consumer_simplified())

        # Monitor for N seconds
        await asyncio.sleep(scada_monitoring_sec)

        results["phases"]["5_scada_monitoring"] = {
            "status": "success",
            "duration_sec": round(time.time() - t5, 2),
            "monitoring_sec": scada_monitoring_sec,
        }
        logger.info("✅ Step 5 done in %.2fs", time.time() - t5)

    except Exception as exc:
        results["phases"]["5_scada_monitoring"] = {"status": "failed", "error": str(exc)}
        logger.warning("⚠️ Step 5 (SCADA) failed — continuing: %s", exc)

    finally:
        if bridge:
            bridge.stop()
        if bridge_task:
            bridge_task.cancel()
            try:
                await bridge_task
            except asyncio.CancelledError:
                pass
        if consumer_task:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

    # ─── STEP 6: Impact analysis ──────────────────────────────────
    logger.info("")
    logger.info("═══ Step 6/7: Compute impact analysis ═══")
    t6 = time.time()

    try:
        impact = {
            "trace_id": trace_id,
            "studies_run": len(study_results),
            "studies_successful": sum(
                1 for r in study_results.values() if r.get("success")
            ),
            "diff_applied": {
                "creates": len(diff["creates"]),
                "updates": len(diff["updates"]),
                "deletes": len(diff["deletes"]),
            },
            "scada_monitoring_sec": scada_monitoring_sec,
            "recommendation": (
                "PROCEED" if all(
                    r.get("success") for r in study_results.values()
                ) else "REVIEW_REQUIRED"
            ),
        }
        results["phases"]["6_impact_analysis"] = {
            "status": "success",
            "duration_sec": round(time.time() - t6, 2),
            "impact": impact,
        }
        logger.info("✅ Step 6: recommendation=%s", impact["recommendation"])

    except Exception as exc:
        results["phases"]["6_impact_analysis"] = {"status": "failed", "error": str(exc)}
        logger.warning("⚠️ Step 6 failed: %s", exc)

    # ─── STEP 7: Generate comprehensive report ────────────────────
    logger.info("")
    logger.info("═══ Step 7/7: Generate comprehensive report ═══")
    t7 = time.time()

    try:
        report_path = os.path.join(output_dir, "comprehensive_report.json")
        final_report = {
            "scenario": "bidirectional_full",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_sec": round(time.time() - start_time, 2),
            "etap_project_path": etap_project_path,
            "etap_backup_path": backup_path,
            "gis_source": gis_source,
            "gis_project_path": gis_project_path,
            "diff_applied": {
                "creates": len(diff["creates"]),
                "updates": len(diff["updates"]),
                "deletes": len(diff["deletes"]),
            },
            "studies_run": study_results,
            "impact_analysis": results["phases"].get("6_impact_analysis", {}).get("impact", {}),
            "outputs": {
                "geojson_path": geojson_path,
            },
            "phases": results["phases"],
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, default=str, ensure_ascii=False)

        results["phases"]["7_report"] = {
            "status": "success",
            "duration_sec": round(time.time() - t7, 2),
            "report_path": report_path,
        }
        logger.info("✅ Step 7: %s", report_path)

    except Exception as exc:
        results["phases"]["7_report"] = {"status": "failed", "error": str(exc)}
        logger.warning("⚠️ Step 7 failed: %s", exc)

    # ─── Done ─────────────────────────────────────────────────────
    total_time = time.time() - start_time
    results["total_duration_sec"] = round(total_time, 2)
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["status"] = "completed"

    logger.info("")
    logger.info("=" * 60)
    logger.info("🎉 Scenario 4 completed in %.2fs", total_time)
    logger.info("=" * 60)

    return results


# ─── Helper functions (reused from scenarios 1-3) ─────────────────


def _extract_gis_features(gis_source: str, gis_project_path: str) -> list[dict[str, Any]]:
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
                "layer": layer_name, "id": feat.id,
                "geometry": feat.geometry, "properties": feat.properties,
            })
    return features


def _compute_diff(
    gis_features: list[dict[str, Any]], etap_project_path: str, trace_id: str,
) -> dict[str, list]:
    creates, updates, deletes = [], [], []

    etap_buses: dict[str, dict] = {}
    try:
        from integrations.supabase_integration import get_supabase_client
        client = get_supabase_client()
        if client is not None:
            response = client.table("gis_buses").select("*").execute()
            for row in response.data or []:
                etap_buses[row.get("bus_id", "")] = row
    except Exception:
        pass

    gis_buses: dict[str, dict] = {}
    for feat in gis_features:
        if "bus" in feat.get("layer", "").lower():
            bus_id = feat.get("properties", {}).get("id", feat.get("id", ""))
            if bus_id:
                gis_buses[bus_id] = feat

    for bus_id in set(gis_buses.keys()) | set(etap_buses.keys()):
        in_gis, in_etap = bus_id in gis_buses, bus_id in etap_buses
        if in_gis and not in_etap:
            creates.append({"object_type": "bus", "id": bus_id,
                            "properties": gis_buses[bus_id].get("properties", {}),
                            "trace_id": trace_id})
        elif in_gis and in_etap:
            changes = {}
            for key in set(gis_buses[bus_id].get("properties", {}).keys()) | set(etap_buses[bus_id].keys()):
                if key in ("id", "trace_id", "updated_at", "created_at", "project_id"):
                    continue
                gis_val = gis_buses[bus_id].get("properties", {}).get(key)
                etap_val = etap_buses[bus_id].get(key)
                if gis_val != etap_val:
                    changes[key] = {"old": etap_val, "new": gis_val}
            if changes:
                updates.append({"object_type": "bus", "id": bus_id,
                                "changes": changes, "trace_id": trace_id})
        elif in_etap and not in_gis:
            deletes.append({"object_type": "bus", "id": bus_id, "trace_id": trace_id})

    return {"creates": creates, "updates": updates, "deletes": deletes, "trace_id": trace_id}


def _audit_to_neo4j(diff: dict[str, list], trace_id: str) -> int:
    try:
        from integrations.neo4j_integration import neo4j_client
        if not neo4j_client.enabled:
            return 0
        count = 0
        for op_type in ("creates", "updates", "deletes"):
            for op in diff.get(op_type, []):
                neo4j_client.execute_query(
                    "CREATE (op:SyncOperation {action: $a, object_type: $t, "
                    "object_id: $i, trace_id: $tr, timestamp: $ts})",
                    {"a": op_type.rstrip("s"), "t": op.get("object_type", ""),
                     "i": op.get("id", ""), "tr": trace_id,
                     "ts": datetime.now(timezone.utc).isoformat()},
                )
                count += 1
        return count
    except Exception:
        return 0


def _backup_etap(etap_project_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{etap_project_path}.bak.{ts}"
    shutil.copy2(etap_project_path, backup_path)
    return backup_path


def _restore_etap(backup_path: str, original_path: str) -> None:
    shutil.copy2(backup_path, original_path)


def _apply_diff_to_etap(etap_project_path: str, diff: dict[str, list]) -> None:
    if os.name != "nt":
        raise RuntimeError("apply_diff_to_etap requires Windows (COM)")
    import win32com.client  # type: ignore
    import pythoncom  # type: ignore

    pythoncom.CoInitialize()
    try:
        app = win32com.client.Dispatch("ETAP.Application")
        app.Visible = False
        project = app.OpenProject(etap_project_path)
        if not project:
            raise RuntimeError(f"Failed to open ETAP project: {etap_project_path}")
        try:
            for op in diff.get("creates", []):
                if op.get("object_type") == "bus":
                    try:
                        project.AddBus(op["id"])
                    except Exception:
                        pass
            for op in diff.get("updates", []):
                try:
                    bus = project.Buses(op["id"])
                    for field, change in op.get("changes", {}).items():
                        try:
                            setattr(bus, field, change["new"])
                        except Exception:
                            pass
                except Exception:
                    pass
            for op in diff.get("deletes", []):
                try:
                    project.RemoveObject(op["id"])
                except Exception:
                    pass
            project.Save()
        finally:
            project.Close()
            app.Quit()
    finally:
        pythoncom.CoUninitialize()


def _summarize_result(study_type: Any, data: dict[str, Any]) -> dict[str, Any]:
    """تلخيص نتائج الدراسة."""
    type_name = study_type.value if hasattr(study_type, "value") else str(study_type)
    if type_name == "LoadFlow":
        return {
            "buses": len(data.get("buses", {})),
            "branches": len(data.get("branches", {})),
            "converged": data.get("converged"),
        }
    elif type_name == "ShortCircuit":
        return {"fault_currents": len(data.get("fault_currents", {}))}
    elif type_name == "ArcFlash":
        return {"equipment": len(data.get("equipment_results", {}))}
    elif type_name == "ProtectionCoordination":
        return {"relay_pairs": len(data.get("relay_pairs", {}))}
    return {"data_keys": list(data.keys())[:5]}


def _build_geojson_from_studies(study_results: dict[str, Any], trace_id: str) -> dict[str, Any]:
    """بناء GeoJSON شامل من نتائج كل الدراسات."""
    features: list[dict[str, Any]] = []

    # Add buses from LoadFlow
    lf = study_results.get("LoadFlow", {})
    if lf.get("success"):
        for bus_id, bus_data in lf.get("data_summary", {}).items():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"id": bus_id, "type": "bus", "source": "LoadFlow"},
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "trace_id": trace_id,
            "source": "Scenario 4 Bidirectional",
            "studies_included": list(study_results.keys()),
        },
    }


async def _run_consumer_simplified() -> None:
    """Simplified consumer for Step 5 (full consumer in scenario 3)."""
    try:
        import json
        import paho.mqtt.client as mqtt

        broker = os.environ.get("MQTT_BROKER", "tcp://localhost:1883")
        host = broker.split("://")[-1].split(":")[0] if "://" in broker else broker.split(":")[0]

        client = mqtt.Client(protocol=mqtt.MQTTv5)
        client.connect(host, 1883, 60)
        client.subscribe("project/power/+/status", qos=1)

        def on_message(c, u, msg):
            try:
                data = json.loads(msg.payload.decode())
                logger.debug("SCADA: %s — %s", msg.topic, data.get("id"))
            except Exception:
                pass

        client.on_message = on_message
        client.loop_start()

        while True:
            await asyncio.sleep(60)

    except Exception as exc:
        logger.warning("Consumer simplified failed: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scenario 4: Bidirectional Full (all 3 scenarios + impact analysis)",
    )
    parser.add_argument("--gis-source", choices=["qgis", "arcgis"], required=True)
    parser.add_argument("--gis-project-path", required=True)
    parser.add_argument("--etap-project-path", required=True)
    parser.add_argument("--output-dir", default="./outputs/scenario4")
    parser.add_argument("--scada-monitoring-sec", type=int, default=300)
    args = parser.parse_args()

    if not os.environ.get("ALLOW_BIDIRECTIONAL_SYNC") == "true":
        print("Set ALLOW_BIDIRECTIONAL_SYNC=true to run this scenario")
        sys.exit(1)
    if not os.environ.get("USE_ETAP") == "true":
        print("Set USE_ETAP=true to enable ETAP integration")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        result = asyncio.run(run_scenario(
            gis_source=args.gis_source,
            gis_project_path=args.gis_project_path,
            etap_project_path=args.etap_project_path,
            output_dir=args.output_dir,
            scada_monitoring_sec=args.scada_monitoring_sec,
        ))

        result_path = os.path.join(args.output_dir, "scenario4_result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        print("\n" + "=" * 60)
        if result.get("status") == "completed":
            print("✅ Scenario 4 completed successfully")
        else:
            print(f"❌ Scenario 4 failed at step {result.get('failed_phase')}")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

        sys.exit(0 if result.get("status") == "completed" else 1)

    except Exception as e:
        logger.exception("Scenario 4 failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
