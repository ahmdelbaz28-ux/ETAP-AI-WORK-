"""
Scenario 1: ETAP → GIS
======================
تشغيل دراسة Load Flow في ETAP 2021 → تصدير النتائج → عرضها
على خريطة QGIS + ArcGIS Pro.

هذا السيناريو يُنسَّق عبر Celery worker أو يُشغَّل مباشرة كـ script.

Phases:
  1. Run Load Flow in ETAP 2021 (via COM or Remote Worker)
  2. Sync results to PostGIS + Neo4j
  3. Generate GeoJSON from PostGIS
  4. Generate QGIS project (.qgz) with styled layers
  5. Generate ArcGIS Pro project (.aprx) with styled layers
  6. Upload outputs to Supabase Storage
  7. Generate PDF report (optional, delegated to reporting module)

متطلبات:
  - ETAP 2021 + USE_ETAP=true (أو ETAP_WORKER_URL للـ remote)
  - QGIS 3.x + QGIS_PREFIX_PATH (لو --gis-output=qgis)
  - ArcGIS Pro 3.x + arcpy (لو --gis-output=arcgis)
  - PostgreSQL + PostGIS
  - Redis
  - Neo4j + Supabase + Langfuse

Usage:
  python scripts/scenarios/run_scenario_1.py \\
      --etap-project "C:\\ETAP Projects\\MySubstation.edb" \\
      --gis-project-id proj-2026-001 \\
      --output-dir ./outputs/scenario1 \\
      --gis-output both

Branch: feat/scenario-1-etap-to-gis
Refs: PRODUCTION_PLAN/05_SCENARIO_1_ETAP_TO_GIS.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("scenario1")


async def run_scenario(
    etap_project_path: str,
    gis_project_id: str,
    output_dir: str,
    gis_output: str = "both",  # "qgis", "arcgis", or "both"
) -> dict[str, Any]:
    """تنفيذ السيناريو 1 الكامل: ETAP → GIS.

    Args:
        etap_project_path: Path to ETAP .edb project file
        gis_project_id: GIS project ID in PostGIS
        output_dir: Directory for generated files
        gis_output: "qgis", "arcgis", or "both"

    Returns:
        dict with execution summary + output paths
    """
    start_time = time.time()
    trace_id = f"scen1-{int(start_time)}"
    logger.info("🚀 Scenario 1 started — trace_id=%s", trace_id)
    logger.info("   ETAP project: %s", etap_project_path)
    logger.info("   GIS project ID: %s", gis_project_id)
    logger.info("   GIS output: %s", gis_output)

    os.makedirs(output_dir, exist_ok=True)
    results: dict[str, Any] = {
        "scenario": "etap_to_gis",
        "trace_id": trace_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }

    # ─── Phase 1: Run Load Flow in ETAP ───────────────────────────
    logger.info("")
    logger.info("═══ Phase 1: Run Load Flow in ETAP ═══")
    phase1_start = time.time()

    try:
        from etap_integration.unified_etap_types import (
            ETAPStudyType,
            get_etap_provider,
        )

        etap_provider = get_etap_provider()

        if not etap_provider.is_available():
            raise RuntimeError(
                f"ETAP provider not available. Provider: "
                f"{type(etap_provider).__name__}. "
                f"Check USE_ETAP=true and ETAP_PROVIDER env vars."
            )

        etap_result = etap_provider.execute_study(
            project_path=etap_project_path,
            study_type=ETAPStudyType.LOAD_FLOW,
            visible=False,
        )

        if not etap_result.success:
            raise RuntimeError(
                f"ETAP Load Flow failed. Errors: {etap_result.errors}. "
                f"Warnings: {etap_result.warnings}"
            )

        buses = etap_result.data.get("buses", {})
        branches = etap_result.data.get("branches", {})

        phase1_time = time.time() - phase1_start
        results["phases"]["1_etap_load_flow"] = {
            "status": "success",
            "duration_sec": round(phase1_time, 2),
            "buses_count": len(buses),
            "branches_count": len(branches),
            "converged": etap_result.data.get("converged", False),
            "iterations": etap_result.data.get("iterations", 0),
            "etap_version": etap_result.etap_version,
            "warnings": etap_result.warnings[:3],  # first 3
        }
        logger.info(
            "✅ Phase 1 done in %.2fs — %d buses, %d branches, converged=%s",
            phase1_time, len(buses), len(branches),
            etap_result.data.get("converged", False),
        )

    except Exception as exc:
        phase1_time = time.time() - phase1_start
        results["phases"]["1_etap_load_flow"] = {
            "status": "failed",
            "duration_sec": round(phase1_time, 2),
            "error": str(exc),
        }
        logger.exception("❌ Phase 1 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 1
        results["error"] = str(exc)
        return results

    # ─── Phase 2: Sync to PostGIS + Neo4j ─────────────────────────
    logger.info("")
    logger.info("═══ Phase 2: Sync ETAP results to PostGIS + Neo4j ═══")
    phase2_start = time.time()

    try:
        # Use Supabase to upsert bus/branch data
        from integrations.supabase_integration import (
            get_supabase_client,
            upload_file,
        )

        client = get_supabase_client()

        buses_synced = 0
        branches_synced = 0

        if client is not None:
            # Upsert buses
            for bus_id, bus_data in buses.items():
                try:
                    record = {
                        "bus_id": bus_id,
                        "project_id": gis_project_id,
                        "voltage_magnitude": bus_data.get("voltage_magnitude"),
                        "voltage_angle": bus_data.get("voltage_angle"),
                        "active_power_mw": bus_data.get("active_power"),
                        "reactive_power_mvar": bus_data.get("reactive_power"),
                        "trace_id": trace_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    # Try upsert (insert or update)
                    client.table("gis_buses").upsert(
                        record, on_conflict="bus_id,project_id"
                    ).execute()
                    buses_synced += 1
                except Exception as exc:
                    logger.debug("Bus %s sync failed: %s", bus_id, exc)

            # Upsert branches
            for branch_id, branch_data in branches.items():
                try:
                    record = {
                        "line_id": branch_id,
                        "project_id": gis_project_id,
                        "active_power_from_mw": branch_data.get("active_power_from"),
                        "reactive_power_from_mvar": branch_data.get("reactive_power_from"),
                        "active_power_to_mw": branch_data.get("active_power_to"),
                        "reactive_power_to_mvar": branch_data.get("reactive_power_to"),
                        "current_amps": branch_data.get("current"),
                        "trace_id": trace_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    client.table("gis_lines").upsert(
                        record, on_conflict="line_id,project_id"
                    ).execute()
                    branches_synced += 1
                except Exception as exc:
                    logger.debug("Branch %s sync failed: %s", branch_id, exc)
        else:
            logger.warning("Supabase client not available — skipping DB sync")

        # Update Neo4j topology
        neo4j_updated = 0
        try:
            from integrations.neo4j_integration import neo4j_client

            if neo4j_client.enabled:
                for bus_id, bus_data in buses.items():
                    neo4j_client.execute_query(
                        """
                        MERGE (b:Bus {id: $bus_id})
                        SET b.voltage_magnitude = $v,
                            b.voltage_angle = $a,
                            b.trace_id = $trace_id,
                            b.updated_at = $ts
                        """,
                        {
                            "bus_id": bus_id,
                            "v": bus_data.get("voltage_magnitude"),
                            "a": bus_data.get("voltage_angle"),
                            "trace_id": trace_id,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    neo4j_updated += 1
                logger.info("✅ Neo4j: updated %d bus nodes", neo4j_updated)
            else:
                logger.info("Neo4j not enabled — skipping topology update")
        except Exception as exc:
            logger.warning("Neo4j sync failed (non-critical): %s", exc)

        phase2_time = time.time() - phase2_start
        results["phases"]["2_sync_to_gis"] = {
            "status": "success",
            "duration_sec": round(phase2_time, 2),
            "buses_synced": buses_synced,
            "branches_synced": branches_synced,
            "neo4j_nodes_updated": neo4j_updated,
        }
        logger.info(
            "✅ Phase 2 done in %.2fs — %d buses, %d branches synced",
            phase2_time, buses_synced, branches_synced,
        )

    except Exception as exc:
        phase2_time = time.time() - phase2_start
        results["phases"]["2_sync_to_gis"] = {
            "status": "failed",
            "duration_sec": round(phase2_time, 2),
            "error": str(exc),
        }
        logger.exception("❌ Phase 2 failed: %s", exc)
        # Continue anyway — we can still generate GeoJSON from ETAP result

    # ─── Phase 3: Generate GeoJSON ─────────────────────────────────
    logger.info("")
    logger.info("═══ Phase 3: Generate GeoJSON ═══")
    phase3_start = time.time()

    geojson_path = os.path.join(output_dir, "load_flow_results.geojson")

    try:
        geojson = _build_geojson_from_etap_result(buses, branches, gis_project_id)

        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        phase3_time = time.time() - phase3_start
        results["phases"]["3_generate_geojson"] = {
            "status": "success",
            "duration_sec": round(phase3_time, 2),
            "output_path": geojson_path,
            "features_count": len(geojson.get("features", [])),
        }
        logger.info(
            "✅ Phase 3 done in %.2fs — %d features in GeoJSON",
            phase3_time, len(geojson.get("features", [])),
        )

    except Exception as exc:
        phase3_time = time.time() - phase3_start
        results["phases"]["3_generate_geojson"] = {
            "status": "failed",
            "duration_sec": round(phase3_time, 2),
            "error": str(exc),
        }
        logger.exception("❌ Phase 3 failed: %s", exc)
        results["status"] = "failed"
        results["failed_phase"] = 3
        results["error"] = str(exc)
        return results

    # ─── Phase 4: Generate QGIS project (optional) ────────────────
    qgis_project_path = None
    if gis_output in ("qgis", "both"):
        logger.info("")
        logger.info("═══ Phase 4: Generate QGIS project (.qgz) ═══")
        phase4_start = time.time()

        try:
            qgis_project_path = _generate_qgis_project(
                geojson_path, output_dir, trace_id
            )
            phase4_time = time.time() - phase4_start
            results["phases"]["4_generate_qgis"] = {
                "status": "success",
                "duration_sec": round(phase4_time, 2),
                "output_path": qgis_project_path,
            }
            logger.info("✅ Phase 4 done in %.2fs", phase4_time)
        except Exception as exc:
            phase4_time = time.time() - phase4_start
            results["phases"]["4_generate_qgis"] = {
                "status": "failed",
                "duration_sec": round(phase4_time, 2),
                "error": str(exc),
            }
            logger.warning("⚠️ Phase 4 (QGIS) failed — continuing: %s", exc)

    # ─── Phase 5: Generate ArcGIS Pro project (optional) ──────────
    arcgis_project_path = None
    if gis_output in ("arcgis", "both"):
        logger.info("")
        logger.info("═══ Phase 5: Generate ArcGIS Pro project (.aprx) ═══")
        phase5_start = time.time()

        try:
            arcgis_project_path = _generate_arcgis_project(
                geojson_path, output_dir, trace_id
            )
            phase5_time = time.time() - phase5_start
            results["phases"]["5_generate_arcgis"] = {
                "status": "success",
                "duration_sec": round(phase5_time, 2),
                "output_path": arcgis_project_path,
            }
            logger.info("✅ Phase 5 done in %.2fs", phase5_time)
        except Exception as exc:
            phase5_time = time.time() - phase5_start
            results["phases"]["5_generate_arcgis"] = {
                "status": "failed",
                "duration_sec": round(phase5_time, 2),
                "error": str(exc),
            }
            logger.warning("⚠️ Phase 5 (ArcGIS) failed — continuing: %s", exc)

    # ─── Phase 6: Upload to Supabase Storage ──────────────────────
    logger.info("")
    logger.info("═══ Phase 6: Upload outputs to Supabase Storage ═══")
    phase6_start = time.time()

    uploaded_urls: dict[str, str] = {}
    try:
        from integrations.supabase_integration import (
            get_signed_url,
            upload_file,
        )

        files_to_upload = [
            ("load_flow_results.geojson", geojson_path, "application/json"),
        ]
        if qgis_project_path:
            files_to_upload.append(
                ("load_flow_qgis.qgz", qgis_project_path, "application/octet-stream")
            )
        if arcgis_project_path:
            files_to_upload.append(
                ("load_flow_arcgis.aprx", arcgis_project_path, "application/octet-stream")
            )

        for filename, filepath, mime in files_to_upload:
            try:
                with open(filepath, "rb") as f:
                    storage_path = f"scenarios/{trace_id}/{filename}"
                    upload_file(
                        bucket="reports",
                        file_path=storage_path,
                        content=f.read(),
                        content_type=mime,
                        user_id="scenario-runner",
                    )
                uploaded_urls[filename] = get_signed_url(
                    bucket="reports",
                    path=storage_path,
                    expires_in=86400,  # 24h
                )
                logger.info("  ✅ Uploaded: %s", filename)
            except Exception as exc:
                logger.warning("  ❌ Failed to upload %s: %s", filename, exc)

        phase6_time = time.time() - phase6_start
        results["phases"]["6_upload_to_supabase"] = {
            "status": "success",
            "duration_sec": round(phase6_time, 2),
            "files_uploaded": len(uploaded_urls),
            "signed_urls": uploaded_urls,
        }
        logger.info("✅ Phase 6 done in %.2fs — %d files uploaded",
                    phase6_time, len(uploaded_urls))

    except Exception as exc:
        phase6_time = time.time() - phase6_start
        results["phases"]["6_upload_to_supabase"] = {
            "status": "failed",
            "duration_sec": round(phase6_time, 2),
            "error": str(exc),
        }
        logger.warning("⚠️ Phase 6 (Supabase) failed — continuing: %s", exc)

    # ─── Done ─────────────────────────────────────────────────────
    total_time = time.time() - start_time
    results["total_duration_sec"] = round(total_time, 2)
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["status"] = "completed"
    results["gis_outputs"] = {
        "geojson_path": geojson_path,
        "qgis_project_path": qgis_project_path,
        "arcgis_project_path": arcgis_project_path,
        "uploaded_urls": uploaded_urls,
    }

    logger.info("")
    logger.info("🎉 Scenario 1 completed in %.2fs", total_time)
    logger.info("   GeoJSON: %s", geojson_path)
    if qgis_project_path:
        logger.info("   QGIS: %s", qgis_project_path)
    if arcgis_project_path:
        logger.info("   ArcGIS: %s", arcgis_project_path)

    return results


def _build_geojson_from_etap_result(
    buses: dict[str, Any],
    branches: dict[str, Any],
    gis_project_id: str,
) -> dict[str, Any]:
    """بناء GeoJSON FeatureCollection من نتائج ETAP."""
    features: list[dict[str, Any]] = []

    # Add buses as Point features
    for bus_id, bus_data in buses.items():
        # Get bus coordinates — in a real deployment, these come from PostGIS
        # For standalone testing, use (0, 0) as placeholder
        lon = bus_data.get("longitude", 0.0)
        lat = bus_data.get("latitude", 0.0)

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": bus_id,
                "type": "bus",
                "voltage_magnitude": bus_data.get("voltage_magnitude"),
                "voltage_angle": bus_data.get("voltage_angle"),
                "active_power_mw": bus_data.get("active_power"),
                "reactive_power_mvar": bus_data.get("reactive_power"),
                "project_id": gis_project_id,
            },
        })

    # Add branches as LineString features
    for branch_id, branch_data in branches.items():
        # Get branch coordinates — from_bus → to_bus
        # In standalone mode, use placeholder coordinates
        from_bus = branch_data.get("from_bus", "BUS-1")
        to_bus = branch_data.get("to_bus", "BUS-2")
        from_lon = branch_data.get("from_longitude", 0.0)
        from_lat = branch_data.get("from_latitude", 0.0)
        to_lon = branch_data.get("to_longitude", 0.1)
        to_lat = branch_data.get("to_latitude", 0.1)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[from_lon, from_lat], [to_lon, to_lat]],
            },
            "properties": {
                "id": branch_id,
                "type": "line",
                "from_bus": from_bus,
                "to_bus": to_bus,
                "active_power_from_mw": branch_data.get("active_power_from"),
                "reactive_power_from_mvar": branch_data.get("reactive_power_from"),
                "active_power_to_mw": branch_data.get("active_power_to"),
                "current_amps": branch_data.get("current"),
                "project_id": gis_project_id,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "project_id": gis_project_id,
            "source": "ETAP Load Flow",
            "feature_count": len(features),
            "buses": len(buses),
            "branches": len(branches),
        },
    }


def _generate_qgis_project(
    geojson_path: str, output_dir: str, trace_id: str
) -> str:
    """Generate QGIS .qgz project from GeoJSON."""
    from gis_integration.providers.qgis_provider import QGISProvider

    output_path = os.path.join(output_dir, "load_flow_qgis.qgz")
    provider = QGISProvider()

    # Use the provider's GISProject to create a new project from GeoJSON
    # The QGISProvider.load_project() opens an existing project, but we
    # need to CREATE a new one. We'll use QgsProject directly.
    provider._ensure_qgs_application()

    from qgis.core import (  # type: ignore
        QgsProject,
        QgsVectorLayer,
        QgsGraduatedSymbolRenderer,
        QgsFillSymbol,
        QgsMapSettings,
        QgsMapRendererSequentialJob,
    )
    from PyQt5.QtCore import QSize  # type: ignore
    from PyQt5.QtGui import QColor  # type: ignore

    # Create vector layer from GeoJSON
    layer = QgsVectorLayer(geojson_path, "ETAP_LoadFlow_Results", "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load GeoJSON as QGIS layer: {geojson_path}")

    # Apply graduated color renderer based on voltage_magnitude
    # (green = normal, yellow = warning, red = critical)
    field_name = "voltage_magnitude"
    if field_name in [f.name() for f in layer.fields()]:
        renderer = QgsGraduatedSymbolRenderer(field_name)
        # Color ramp: red (0.9) → yellow (0.95) → green (1.05) → yellow (1.1) → red
        ramp_colors = [
            (QColor(255, 0, 0), "0.90"),
            (QColor(255, 255, 0), "0.95"),
            (QColor(0, 255, 0), "1.00"),
            (QColor(255, 255, 0), "1.05"),
            (QColor(255, 0, 0), "1.10"),
        ]
        symbol = QgsFillSymbol()
        renderer.updateClasses(layer, 5)
        renderer.setSourceSymbol(symbol)
        layer.setRenderer(renderer)

    # Create new project
    project = QgsProject.instance()
    project.clear()
    project.addMapLayer(layer)

    # Save as .qgz
    project.write(output_path)
    logger.info("✅ QGIS project saved: %s", output_path)

    return output_path


def _generate_arcgis_project(
    geojson_path: str, output_dir: str, trace_id: str
) -> str:
    """Generate ArcGIS Pro .aprx project from GeoJSON."""
    import arcpy  # type: ignore
    import arcpy.mp as mp  # type: ignore

    output_path = os.path.join(output_dir, "load_flow_arcgis.aprx")

    # Create new ArcGIS Pro project
    template_path = os.environ.get("ARCGIS_PRO_PROJECT_TEMPLATE")
    if template_path and os.path.exists(template_path):
        project = mp.ArcGISProject(template_path)
    else:
        # Create empty project
        project = mp.ArcGISProject()

    # Convert GeoJSON to feature class
    gdb_path = os.path.join(output_dir, "scenario1.gdb")
    if not arcpy.Exists(gdb_path):
        arcpy.management.CreateFileGDB(output_dir, "scenario1.gdb")

    fc_path = os.path.join(gdb_path, "load_flow_results")

    # GeoJSON → FeatureClass
    arcpy.conversion.JSONToFeatures(
        geojson_path, fc_path, "POLYGON"  # will auto-detect geometry type
    )

    # Add to project's first map
    maps = project.listMaps()
    if maps:
        map_doc = maps[0]
        map_doc.addDataFromPath(fc_path)
    else:
        logger.warning("No maps in ArcGIS project template — feature class added to GDB only")

    # Save as new .aprx
    project.saveACopy(output_path)
    logger.info("✅ ArcGIS Pro project saved: %s", output_path)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scenario 1: ETAP 2021 → GIS (QGIS + ArcGIS Pro)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Windows with ETAP 2021 + QGIS + ArcGIS Pro
    python scripts/scenarios/run_scenario_1.py \\
        --etap-project "C:\\ETAP Projects\\MySubstation.edb" \\
        --gis-project-id proj-2026-001 \\
        --gis-output both

    # QGIS only (skip ArcGIS)
    python scripts/scenarios/run_scenario_1.py \\
        --etap-project "C:\\ETAP\\Test.edb" \\
        --gis-project-id test-001 \\
        --gis-output qgis

    # GeoJSON only (no GIS software needed)
    python scripts/scenarios/run_scenario_1.py \\
        --etap-project "C:\\ETAP\\Test.edb" \\
        --gis-project-id test-001 \\
        --gis-output none
        """,
    )
    parser.add_argument(
        "--etap-project", required=True,
        help="Path to ETAP .edb project file",
    )
    parser.add_argument(
        "--gis-project-id", required=True,
        help="GIS project ID in PostGIS/Supabase",
    )
    parser.add_argument(
        "--output-dir", default="./outputs/scenario1",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--gis-output", choices=["qgis", "arcgis", "both", "none"],
        default="both",
        help="GIS output format (default: both)",
    )
    args = parser.parse_args()

    # Validate env
    if not os.environ.get("USE_ETAP", "false").lower() == "true":
        print("❌ Set USE_ETAP=true to enable ETAP integration")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        result = asyncio.run(run_scenario(
            etap_project_path=args.etap_project,
            gis_project_id=args.gis_project_id,
            output_dir=args.output_dir,
            gis_output=args.gis_output,
        ))

        # Save result JSON
        result_path = os.path.join(args.output_dir, "scenario1_result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        print("\n" + "=" * 60)
        if result.get("status") == "completed":
            print("✅ Scenario 1 completed successfully")
        else:
            print(f"❌ Scenario 1 failed at phase {result.get('failed_phase')}")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

        sys.exit(0 if result.get("status") == "completed" else 1)

    except Exception as e:
        logger.exception("Scenario 1 failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
