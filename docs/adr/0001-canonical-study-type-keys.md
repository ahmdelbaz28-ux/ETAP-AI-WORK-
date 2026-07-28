# Use canonical StudyType strings as orchestrator registry keys

The orchestrator agent registry currently uses shorthand keys (`"harmonic"`, `"opf"`, `"protection"`) that diverge from the canonical `StudyType` enum values (`harmonic_analysis`, `optimal_power_flow`, `protection_coordination`). This creates a translation layer that must be maintained whenever adding new agents or routing studies. We adopt the canonical `StudyType` string values as the one true registry key, eliminating the mapping step entirely.

## Status

**Implemented** - Changes made on 2026-07-22

## Changes Applied

### 1. Extended StudyType Enum
Added missing study types to `agents/orchestrator.py`:
- `CABLE_SIZING`
- `EARTH_GRID`
- `RENEWABLE_INTEGRATION`
- `BATTERY_STORAGE`
- `SCADA`
- `ETAP_EXPERT`
- `ETAP_GUI`

### 2. Aligned Agent Registry Keys
Changed in `ChiefEngineeringOrchestrator.__init__`:
- `"harmonic"` → `"harmonic_analysis"` (already correct)
- `"opf"` → `"optimal_power_flow"` (already correct)
- `"protection"` → `"protection_coordination"` (already correct)

### 3. Removed Study Type Aliases
Removed aliases from `api/studies.py`:
- `fault` → use `short_circuit` only
- `coordination` → use `protection_coordination` only

### 4. Updated Study Type Mapping
Removed non-canonical aliases from `get_study_type_mapping()`:
- `"harmonic"` → removed
- `"opf"` → removed
- `"protection"` → removed
- `"protection_coordination"` → maps to `"protection_coordination"`

### 5. Updated Priority Order
Extended priority order to include all study types for deterministic execution.

## Migration Guide for Clients

| Old (Deprecated) | New (Canonical) |
|------------------|-----------------|
| `fault` | `short_circuit` |
| `coordination` | `protection_coordination` |
| `harmonic` | `harmonic_analysis` |
| `opf` | `optimal_power_flow` |

## Files Modified

- `agents/orchestrator.py` - StudyType enum, agent registry, mappings
- `api/studies.py` - Removed aliases from `_STUDIES_REQUIRING_SYSTEM` and `_run_native_study`
- `engine/engine.py` - Updated to use canonical study type names
- `tests/test_langfuse_full_integration.py` - Updated test to use canonical name
