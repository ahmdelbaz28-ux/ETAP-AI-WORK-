from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from gis_integration.models import ADMSAsset
from gis_validation.crs_validator import validate_crs_consistency, validate_normalization_applied
from gis_validation.dataset_generator import generate_mixed_crs_assets, generate_synthetic_grid
from gis_validation.failure_injection import (
    inject_broken_crs_metadata,
    inject_corrupted_geometries,
)
from gis_validation.stress_tests import run_large_scale_simulation
from gis_validation.topology_validator import validate_adms_topology


@dataclass(frozen=True)
class ValidationReport:
    status: str  # PASS/FAIL
    classification: str
    details: Dict[str, Any]
    metrics: Dict[str, Any]


def _provider_available(provider: str) -> bool:
    """
    Detect provider availability without hard dependency.
    provider:
      - "qgis"
      - "arcgis"
    """
    try:
        if provider == "qgis":
            importlib.import_module("qgis")
            return True
        if provider == "arcgis":
            importlib.import_module("arcpy")
            return True
    except Exception:
        return False
    return False


def _run_provider_smoke_tests() -> Dict[str, Any]:
    """
    Conditional provider runtime tests.
    Must not falsely fail when GIS binaries are missing.
    """
    results: Dict[str, Any] = {}
    qgis_ok = _provider_available("qgis")
    arc_ok = _provider_available("arcgis")

    results["qgis_available"] = qgis_ok
    results["arcgis_available"] = arc_ok

    # Provider smoke tests are intentionally conservative since full GIS
    # runtime setup is environment-specific.
    # If present, we attempt minimal health checks using provider classes.
    if qgis_ok:
        try:
            from gis_integration.providers.qgis_provider import QGISProvider

            p = QGISProvider()
            results["qgis_health_check"] = p.health_check()
        except Exception as exc:
            results["qgis_health_check"] = False
            results["qgis_error"] = str(exc)

    if arc_ok:
        try:
            from gis_integration.providers.arcgis_provider import ArcGISProvider

            p = ArcGISProvider()
            results["arcgis_health_check"] = p.health_check()
        except Exception as exc:
            results["arcgis_health_check"] = False
            results["arcgis_error"] = str(exc)

    return results


def run_crs_validation_tests(assets: List[ADMSAsset]) -> List[ValidationReport]:
    reports: List[ValidationReport] = []

    ok_norm, issues_norm = validate_normalization_applied(assets)
    reports.append(
        ValidationReport(
            status="PASS" if ok_norm else "FAIL",
            classification="crs.normalization_applied" if ok_norm else "crs.normalization_missing",
            details={"issues": [i.__dict__ for i in issues_norm]},
            metrics={},
        )
    )

    ok_crs, issues_crs = validate_crs_consistency(assets)
    reports.append(
        ValidationReport(
            status="PASS" if ok_crs else "FAIL",
            classification="crs.consistency" if ok_crs else "crs.mixed_or_missing",
            details={"issues": [i.__dict__ for i in issues_crs]},
            metrics={},
        )
    )
    return reports


def run_topology_validation_tests(assets: List[ADMSAsset]) -> List[ValidationReport]:
    ok, issues = validate_adms_topology(assets)
    return [
        ValidationReport(
            status="PASS" if ok else "FAIL",
            classification="adms.topology" if ok else "adms.topology_inconsistent",
            details={"issues": [i.__dict__ for i in issues]},
            metrics={},
        )
    ]


def run_failure_injection_tests() -> List[ValidationReport]:
    base_assets = generate_synthetic_grid(grid_type="urban", seed=1, crs="EPSG:4326")

    results: List[ValidationReport] = []

    # Corrupted geometries should fail CRS normalization/transform or topology validation deterministically.
    corrupted = inject_corrupted_geometries(base_assets, seed=2, corruption_ratio=0.05)
    ok_topo, issues_topo = validate_adms_topology(corrupted)
    results.append(
        ValidationReport(
            status="PASS" if (not ok_topo) else "FAIL",
            classification="failure_injection.corrupted_geometry_detected",
            details={"topology_issues": [i.__dict__ for i in issues_topo]},
            metrics={},
        )
    )

    # Broken CRS metadata must be detected.
    broken_crs = inject_broken_crs_metadata(base_assets, seed=3, contamination_ratio=0.2)
    ok_crs, issues_crs = validate_crs_consistency(broken_crs)
    results.append(
        ValidationReport(
            status="PASS" if (not ok_crs) else "FAIL",
            classification="failure_injection.broken_crs_metadata_detected",
            details={"crs_issues": [i.__dict__ for i in issues_crs]},
            metrics={},
        )
    )

    return results


def run_stress_validation_tests() -> ValidationReport:
    res = run_large_scale_simulation(scenario_id="stress_10k_1m_synthetic")
    return ValidationReport(
        status=res.status,
        classification="stress.pipeline",
        details={"failure_classification": res.failure_classification},
        metrics=res.metrics,
    )


def production_readiness_gate(
    qgis_project_path: str | None = None,
    arcgis_project_path: str | None = None,
    adms_output_path: str | None = None,
) -> bool:
    """
    Single authoritative production validation entry point.

    Deterministic execution: uses only explicit parameters (no env/config).

    Priority order:
      1) Real GIS validations when project paths are provided
      2) ADMS output comparison (placeholder until adms_output_path exists/format is defined)
      3) Synthetic validation only when no real GIS paths are provided

    Real-world failure handling:
      - Any real GIS validation failure returns False (fail fast).
      - Missing GIS binaries do not silently pass when real paths were provided.
    """
    _start = time.time()

    # 1) Real GIS validations (highest priority)
    if qgis_project_path or arcgis_project_path:
        # Lazy import real subsystem.
        from gis_validation_real.ground_truth_validator import validate_real_gis_to_adms
        from gis_validation_real.project_adapters import extract_layers_as_features
        from gis_validation_real.real_gis_loader import load_real_gis_project

        try:
            projects = load_real_gis_project(
                qgis_project_path=qgis_project_path,
                arcgis_project_path=arcgis_project_path,
            )
        except Exception:
            return False

        # Extract features deterministically per provider and validate.
        for proj in projects:
            try:
                extracted = extract_layers_as_features(proj.provider)
                all_features: list = []
                for ex in extracted:
                    all_features.extend(ex.features)
                ok, _report = validate_real_gis_to_adms(extracted_features=all_features)
                if not ok:
                    return False
            except Exception:
                return False

        # adms_output_path comparisons are intentionally not implemented without a
        # concrete ADMS output schema. In production, this must be wired to the real
        # ADMS export format.
        if adms_output_path:
            # Comparison schema is not implemented; fail-closed to avoid silent approval.
            return False

        return True

    # If an ADMS output path is provided without real GIS inputs, fail closed as well.
    if adms_output_path is not None:
        return False

    # 2) Synthetic validation fallback (lowest priority, CI/testing only)
    # Provider runtime smoke tests are conditional and never override synthetic validations.
    _provider_results = _run_provider_smoke_tests()

    # a) CRS + normalization on deterministic synthetic dataset
    assets = generate_synthetic_grid(grid_type="urban", seed=42, crs="EPSG:4326")
    ok_crs, _ = validate_crs_consistency(assets)
    ok_norm, _ = validate_normalization_applied(assets)
    if not (ok_crs and ok_norm):
        return False

    # b) Topology validation on deterministic synthetic dataset
    ok_topo, _ = validate_adms_topology(assets)
    if not ok_topo:
        return False

    # c) Failure injection: detection-only semantics
    try:
        failure_reports = run_failure_injection_tests()
        if any(r.status != "PASS" for r in failure_reports):
            return False
    except Exception:
        return False

    # d) Stress tests
    stress_report = run_stress_validation_tests()
    if stress_report.status != "PASS":
        return False

    # e) Mixed CRS should fail
    mixed = generate_mixed_crs_assets(seed=99, crs_a="EPSG:4326", crs_b="EPSG:3857")
    ok_mixed_crs, _ = validate_crs_consistency(mixed)
    if ok_mixed_crs:
        return False

    _elapsed = time.time() - _start
    return True
