# Desktop GIS Provider Edit Scope — Descope Document

## Purpose

This document defines the boundaries for desktop GIS SDK dependencies (QGIS/ArcGIS) and
how the platform handles environments where these SDKs are not available.

## Status: ARCHIVED

- **ArcGISProvider**: Archived. Raises `NotImplementedFeature` on all methods.
  - Use `QGISProvider` for desktop QGIS workflows.
  - Use `MockGISProvider` for CI/CD, Hugging Face Spaces, or headless environments.

## QGIS Provider — Desktop Scope

### When QGIS is Available

On a properly configured QGIS desktop installation:

1. **Environment Requirement**:
   - `QGIS_PREFIX_PATH` (optional): Path to QGIS installation.
   - If unset, defaults to `/usr` (Linux) or requires QGIS in PATH (Windows).

2. **Runtime Behavior**:
   - `health_check()` returns `True` when `QgsApplication.instance()` is not None.
   - `_init_qgs()` calls `QgsApplication.setPrefixPath()` and `initQgis()`.

3. **Edit Scope**:
   - Direct `.qgs` / `.qgz` project loading.
   - Layer export to GeoJSON.
   - Feature extraction for topology validation.

### When QGIS is Unavailability

In CI/CD, Headless servers, Hugging Face Spaces:

1. **Feature Flag**: `mock_gis_provider=true`
2. **Environment Variable**: `USE_MOCK_GIS=true`
3. **Fallback**: `get_gis_provider("qgis")` returns `MockGISProvider` with warning.

## MockGISProvider — Safe Default

The mock provider is always available in dev/test environments and returns
synthetic Cairo-area features:

- Substations: 33.3°N, 31.2°E (Cairo East, Helwan Industrial)
- Lines: 220kV transmission corridors
- Switches: 1200A breaker status

## Factory Behavior

| Request | Mock Allowed | Result |
|---------|--------------|--------|
| `"mock"` | True | `MockGISProvider` |
| `"mock"` | False | `RuntimeError` |
| `"qgis"` | health_check=True | `QGISProvider` |
| `"qgis"` | health_check=False, mock=True | `MockGISProvider` (warn) |
| `"qgis"` | health_check=False, mock=False | `RuntimeError` |
| `"arcgis"` | any | `NotImplementedFeature` (archived) |

## CI Usage Notes

- No hard QGIS dependency in CI.
- Tests inject fake `QgsApplication` via `patch.dict("sys.modules", {"qgis.core": mock})`.
- Scenario scripts must guard `_ensure_qgs_application()` → replaced with `_init_qgs()`.

## Ownership

- Primary: `gis_integration/providers/`
- Tests: `tests/test_gis_integration_full.py`
- Scenarios: `scripts/scenarios/run_scenario_1.py` (QGIS generation only)