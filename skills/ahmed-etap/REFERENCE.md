# AhmedETAP Reference

## SharedContext Schema

```
SharedContext = {
  project: ProjectRef,
  budget: { max_tokens, spent, remaining },
  tasks: [{ agent, status, result, math_guard_passed }],
  standards: ["IEEE 3002.7", "IEC 60909", ...],
  glossary: { /* canonical terms from CONTEXT.md */ },
  errors: [],
  review: { reviewer, verdict, notes }
}
```

## Math Guard Spec

Every numerical output must:
1. Be recomputed by standalone Python script
2. Match agent claim within 0.01% tolerance
3. Pass units check (kV ≠ V, MVA ≠ kVA)

If mismatch → block result, flag for human review.

## Peer Review Matrix

| Lead Agent | Peer Reviewer |
|------------|---------------|
| Load Flow | Short Circuit |
| Short Circuit | Load Flow |
| Arc Flash | Protection Coordination |
| Protection Coordination | Arc Flash |
| Harmonic | Load Flow |
| OPF | Load Flow |
| Motor Starting | Stability |
| Stability | Motor Starting |
| Cable Sizing | Load Flow |
| Earth Grid | Short Circuit |
| Renewable | Load Flow |
| Battery | Renewable |
| SCADA | Digital Twin |
| Digital Twin | SCADA |
| ETAP Expert | Validation Agent |

## Token Budget Defaults

| Workflow Type | Budget (tokens) |
|---------------|-----------------|
| Single study | 8,000 |
| Multi-agent | 16,000 |
| ETAP Expert (full) | 24,000 |

## Canonical Study Types

Use snake_case only: `load_flow`, `short_circuit`, `harmonic_analysis`, `optimal_power_flow`, `protection_coordination`, `motor_starting`, `transient_stability`, `arc_flash`, `cable_sizing`, `earth_grid`, `renewable_integration`, `battery_storage`, `scada`, `etap_expert`, `etap_gui`.

Never use aliases: `fault` → `short_circuit`, `coordination` → `protection_coordination`, `harmonic` → `harmonic_analysis`.
