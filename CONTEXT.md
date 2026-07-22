# Domain Context: AhmedETAP Platform

This document establishes the **ubiquitous language** for the AhmedETAP power system analysis platform.

## Canonical Domain Terms

### Core Entities

| Term | Definition | Notes |
|------|------------|-------|
| **Agent** | An autonomous computational entity that performs a specific power-system study. Both LLM-powered (Mastra) and numerical (Python) agents. | The canonical term for all executable analysis units. |
| **Study** | A power-system analysis execution (e.g., load flow, short circuit, harmonic analysis). | Top-level work product. Always use `study_type` field in API. |
| **Task** | A unit of work specifying parameters for one or more studies. | `EngineeringTask` in Python, routed to appropriate agents. |
| **Project** | A persisted power-system model container. | Maps to ETAP's `.etap` project file concept. |
| **Result** | The raw structured data returned by a study execution. | Use `data` field, not `results`. |
| **Report** | A formatted document (PDF/DOCX/XLSX) generated from study results. | Created by `ReportGenerationAgent`. |
| **Workflow** | A multi-step orchestrated sequence of studies. | Managed by `ChiefEngineeringOrchestrator`. |

### Study Types (Canonical)

All study types use **snake_case** and are defined in the `StudyType` enum. Use these values consistently across all layers.

| Canonical Value | Registry Key | Agent Class | Standard |
|-----------------|--------------|-------------|----------|
| `load_flow` | `load_flow` | `LoadFlowAgent` | IEEE 3002.7 |
| `short_circuit` | `short_circuit` | `ShortCircuitAgent` | IEC 60909 |
| `harmonic_analysis` | `harmonic_analysis` | `HarmonicAnalysisAgent` | IEEE 519 |
| `optimal_power_flow` | `optimal_power_flow` | `OptimalPowerFlowAgent` | IEEE 3002.7 |
| `protection_coordination` | `protection_coordination` | `ProtectionCoordinationAgent` | IEC 60255 |
| `motor_starting` | `motor_starting` | `MotorStartingAgent` | IEEE 399 |
| `transient_stability` | `transient_stability` | `StabilityAgent` | IEEE 399 |
| `arc_flash` | `arc_flash` | `ArcFlashAgent` | IEEE 1584 |
| `cable_sizing` | `cable_sizing` | `CableSizingAgent` | IEC 60364 |
| `earth_grid` | `earth_grid` | `EarthGridAgent` | IEEE 80 |
| `renewable_integration` | `renewable_integration` | `RenewableAgent` | IEEE 1547 |
| `battery_storage` | `battery_storage` | `BatteryStorageAgent` | IEC 62933 |
| `scada` | `scada` | `SCADAAgent` | IEC 61850 |
| `etap_expert` | `etap_expert` | `ETAPExpertAgent` | All ETAP standards |
| `etap_gui` | `etap_gui` | `ETAPGUIAgent` | Computer Use Agent |

### Status Enum (Canonical)

Use `ExecutionStatus` for all execution state tracking:

| Value | Description |
|-------|-------------|
| `PENDING` | Task/Study has not started |
| `RUNNING` | Task/Study is in progress |
| `COMPLETED` | Task/Study finished successfully |
| `FAILED` | Task/Study failed with errors |
| `VALIDATING` | Results are being validated against standards |

## Term Usage Rules

### Study Type Naming
- **Never** use aliases: `fault` → `short_circuit`, `coordination` → `protection_coordination`
- API accepts only canonical `StudyType` enum values
- Agent registry keys must match canonical values

### Agent vs Worker vs Service vs Orchestrator
| Term | Meaning |
|------|---------|
| `Agent` | Canonical term for any analysis executor |
| `Worker` | Celery background task executor (infrastructure) |
| `Service` | Stateless business logic layer |
| `Coordinator` | Task routing and workflow management (single entity in Mastra) |

### Result vs Report vs Output
| Term | Meaning |
|------|---------|
| `Result` | Raw structured data from study execution |
| `Report` | Formatted document generated from results |
| `Output` | Deprecated - use `Result` or `Report` for clarity |

## Anti-Patterns (Do Not Use)

- `fault` - use `short_circuit`
- `coordination` - use `protection_coordination`
- `harmonic` - use `harmonic_analysis`
- `stability` - use `transient_stability`
- `opf` - use `optimal_power_flow`
- `data` field alongside `results` in StudyResult - pick one