# Standardized Electrical Component Library

Welcome to the AhmedETAP Standardized Component Library repository. This directory houses validated, standardized electrical equipment records complying with international engineering standards (IEC, IEEE, NFPA, ANSI).

---

## Directory Structure

```
data/components/
├── README.md                 # Contribution guide + schema documentation
├── schema.json               # Canonical JSON Schema for Component records
├── cables/
│   └── iec60364/             # Low & Medium Voltage cables per IEC 60364-5-52
│       ├── index.json        # Category manifest
│       └── *.json            # Individual cable specifications
├── transformers/
│   └── ieee_c57/             # Power & Distribution transformers per IEEE C57
│       ├── index.json        # Category manifest
│       └── *.json            # Transformer rating classes
├── breakers/
│   └── iec62271/             # High & Low Voltage switchgear per IEC 62271 / IEC 60947
│       ├── index.json        # Category manifest
│       └── *.json            # Circuit breaker ratings
└── templates/
    ├── index.json            # Template manifest
    └── *.json                # Protection coordination & relay templates
```

---

## Component JSON Schema Specification

Each component definition must conform to `schema.json`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | string (UUID or slug) | Globally unique identifier |
| `type` | string | Equipment class: `cable`, `transformer`, `breaker`, `relay`, `template` |
| `category` | string | Governing standard family (e.g. `IEC 60364`, `IEEE C57`) |
| `subcategory` | string | Specific material/voltage group (e.g. `CU/PVC 1kV`, `Oil Immersed 33kV`) |
| `name` | string | Human-readable name |
| `manufacturer` | string or null | Optional manufacturer name |
| `model_number` | string or null | Optional model designation |
| `specs` | object | Physical and electrical parameters (resistance, reactance, ratings) |
| `standards` | array of strings | Applicable standard clauses (e.g. `["IEC 60364-52"]`) |
| `tags` | array of strings | Search tags |
| `is_verified` | boolean | True for peer-reviewed/standard library entries |
| `source` | string | Data origin (`iec-standard`, `ieee-standard`, `etap-import`, `user`) |
