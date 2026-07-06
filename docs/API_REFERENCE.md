# AhmedETAP — Full API Reference

## Overview

The AhmedETAP exposes a comprehensive RESTful API and WebSocket interface for power system analysis, agent orchestration, SCADA integration, predictive analytics, and system management. This document provides complete specifications for every endpoint, including request/response schemas, authentication requirements, rate limits, and usage examples.

### Base URLs

| Environment | URL |
|-------------|-----|
| Development | `http://localhost:8000` |
| Production | `https://etap.yourdomain.com` |
| Hugging Face Demo | `https://ahmdelbaz28-ahmedetap-platform.hf.space` |

### API Versioning

All endpoints are versioned under `/api/v1/`. The current version is **v1**.

---

## Authentication

### JWT Token Authentication

All API endpoints (except health checks and login) require a valid JWT token in the `Authorization` header.

**Header Format:**
```
Authorization: Bearer <jwt_token>
```

### API Key Authentication

Alternatively, an API key can be provided via the `X-API-Key` header:
```
X-API-Key: <your-api-key>
```

### POST /api/auth/login

Authenticate and obtain a JWT access token.

**Request:**
```json
{
  "username": "engineer@example.com",
  "password": "your-secure-password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800,
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g...",
  "user": {
    "id": "usr-001",
    "username": "engineer@example.com",
    "role": "engineer",
    "permissions": ["studies:run", "reports:generate", "agents:list"]
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid username or password",
    "timestamp": "2026-03-04T14:30:00Z",
    "request_id": "req-abc123"
  }
}
```

---

## Health & Readiness Endpoints

### GET /health

Full health check with service dependency status.

**Authentication:** Not required

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-04T14:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "services": {
    "database": "connected",
    "redis": "connected",
    "vector_db": "connected",
    "engineering_engine": "ready"
  },
  "agents_available": 14,
  "active_studies": 2
}
```

### GET /healthz

Lightweight liveness probe for Kubernetes.

**Authentication:** Not required

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

### GET /readyz

Readiness probe that checks all dependencies.

**Authentication:** Not required

**Response (200 OK):**
```json
{
  "ready": true,
  "checks": {
    "engine": "ok",
    "memory": "ok",
    "workers": 4
  }
}
```

### GET /ready

Detailed readiness check with service health information.

**Authentication:** Not required

**Response (200 OK):**
```json
{
  "ready": true,
  "timestamp": "2026-03-04T14:30:00Z",
  "services": {
    "engine": {"status": "ok", "latency_ms": 2.5},
    "etap_provider": {"status": "not_configured", "latency_ms": null},
    "redis": {"status": "ok", "latency_ms": 1.2}
  }
}
```

### GET /metrics

Prometheus-compatible metrics endpoint.

**Authentication:** Required (API key)

**Response (200 OK):**
```json
{
  "request_count": 15234,
  "error_count": 12,
  "avg_response_time_ms": 145.3,
  "studies_run": 456,
  "active_connections": 8,
  "memory_usage_mb": 512.4,
  "cpu_usage_percent": 23.5,
  "agents": {
    "load_flow": {"runs": 120, "avg_time_ms": 85.2, "success_rate": 0.98},
    "short_circuit": {"runs": 89, "avg_time_ms": 42.1, "success_rate": 0.99},
    "arc_flash": {"runs": 67, "avg_time_ms": 120.5, "success_rate": 0.97},
    "harmonic": {"runs": 34, "avg_time_ms": 95.3, "success_rate": 0.96},
    "opf": {"runs": 28, "avg_time_ms": 250.7, "success_rate": 0.93}
  }
}
```

---

## Engineering Study Endpoints

### POST /api/v1/studies/run

Execute a power system engineering study. This is the primary endpoint for running all analysis types through the native Python engine or ETAP COM automation.

**Authentication:** Required

**Rate Limit:** 30 requests/minute (standard), 10 requests/minute (OPF, harmonic)

**Request:**
```json
{
  "study_type": "load_flow",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {
        "bus_id": 1,
        "voltage_magnitude": 1.05,
        "voltage_angle": 0.0,
        "bus_type": "slack",
        "base_kv": 138.0
      },
      {
        "bus_id": 2,
        "voltage_magnitude": 1.0,
        "voltage_angle": 0.0,
        "load_power_real": 50.0,
        "load_power_imag": 20.0,
        "bus_type": "pq",
        "base_kv": 13.8
      },
      {
        "bus_id": 3,
        "voltage_magnitude": 1.02,
        "voltage_angle": 0.0,
        "generation_power_real": 80.0,
        "bus_type": "pv",
        "base_kv": 13.8,
        "q_min": -50.0,
        "q_max": 50.0,
        "voltage_setpoint": 1.02
      }
    ],
    "lines": [
      {
        "line_id": 1,
        "from_bus_id": 1,
        "to_bus_id": 2,
        "r1": 0.01,
        "x1": 0.05,
        "bshunt1": 0.02,
        "rating_mva": 100.0
      },
      {
        "line_id": 2,
        "from_bus_id": 2,
        "to_bus_id": 3,
        "r1": 0.02,
        "x1": 0.08,
        "bshunt1": 0.03,
        "rating_mva": 80.0
      }
    ],
    "transformers": [
      {
        "transformer_id": 1,
        "from_bus_id": 1,
        "to_bus_id": 2,
        "r1": 0.005,
        "x1": 0.05,
        "tap_ratio": 1.0,
        "phase_shift_deg": 0.0
      }
    ],
    "generators": [
      {
        "generator_id": 1,
        "bus_id": 1,
        "x1": 0.2,
        "internal_voltage_mag": 1.05,
        "power_real": 0.0,
        "power_reactive": 0.0
      }
    ],
    "loads": [
      {
        "load_id": 1,
        "bus_id": 2,
        "p_mw": 50.0,
        "q_mvar": 20.0
      }
    ]
  },
  "parameters": {
    "method": "newton_raphson",
    "max_iterations": 50,
    "tolerance": 1e-6
  },
  "task_id": "custom-task-id-001",
  "use_etap": false
}
```

**Supported Study Types:**

| study_type | Description | Engine |
|-----------|-------------|--------|
| `load_flow` | Load flow analysis (NR/FD) | Native |
| `short_circuit` | Short circuit analysis (IEC 60909) | Native |
| `fault` | Alias for short_circuit | Native |
| `arc_flash` | Arc flash hazard analysis (IEEE 1584) | Native |
| `harmonic_analysis` | Harmonic distortion analysis (IEEE 519) | Native |
| `optimal_power_flow` | Optimal power flow (AC/DC) | Native |
| `protection_coordination` | Relay coordination | Native |
| `coordination` | Alias for protection_coordination | Native |
| `motor_starting` | Motor starting analysis | Native |
| `etap_load_flow` | Load flow via ETAP | ETAP |
| `etap_short_circuit` | Short circuit via ETAP | ETAP |
| `etap_arc_flash` | Arc flash via ETAP | ETAP |
| `etap_harmonic_analysis` | Harmonic analysis via ETAP | ETAP |
| `etap_optimal_power_flow` | OPF via ETAP | ETAP |
| `etap_motor_starting` | Motor starting via ETAP | ETAP |
| `etap_protection_coordination` | Protection via ETAP | ETAP |

**Response (200 OK):**
```json
{
  "task_id": "custom-task-id-001",
  "study_type": "load_flow",
  "status": "completed",
  "converged": true,
  "iterations": 5,
  "execution_time_ms": 85.2,
  "results": {
    "buses": {
      "1": {
        "voltage_magnitude_pu": 1.05,
        "voltage_angle_deg": 0.0,
        "power_generated_mw": 55.2,
        "power_generated_mvar": 18.5
      },
      "2": {
        "voltage_magnitude_pu": 0.982,
        "voltage_angle_deg": -5.23,
        "power_consumed_mw": 50.0,
        "power_consumed_mvar": 20.0
      },
      "3": {
        "voltage_magnitude_pu": 1.02,
        "voltage_angle_deg": -3.12,
        "power_generated_mw": 80.0,
        "power_generated_mvar": 12.3
      }
    },
    "lines": {
      "1": {
        "from_bus": 1,
        "to_bus": 2,
        "power_flow_mw": 32.5,
        "power_flow_mvar": 8.2,
        "loading_percent": 33.4,
        "loss_mw": 0.12
      }
    },
    "losses_mw": 0.52,
    "total_generation_mw": 135.2,
    "total_load_mw": 130.0
  },
  "validation": {
    "all_voltages_within_limits": true,
    "all_lines_thermal_ok": true,
    "power_balance_error_mw": 0.001
  },
  "trace_id": "trace-xyz789",
  "timestamp": "2026-03-04T14:30:00Z"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": {
    "code": "STUDY_FAILED",
    "message": "Load flow did not converge after 50 iterations",
    "details": {
      "study_type": "load_flow",
      "iterations": 50,
      "max_mismatch_pu": 0.15,
      "suggestion": "Try increasing max_iterations or check system data for errors"
    },
    "timestamp": "2026-03-04T14:30:00Z",
    "request_id": "req-def456"
  }
}
```

### POST /api/v1/system/validate

Validate a power system model without running a study. Checks data integrity, connectivity, and basic feasibility.

**Authentication:** Required

**Request:**
```json
{
  "base_mva": 100.0,
  "buses": [
    {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
    {"bus_id": 2, "bus_type": "pq", "load_power_real": 50.0}
  ],
  "lines": [
    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
  ]
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "warnings": [],
  "errors": [],
  "statistics": {
    "bus_count": 2,
    "line_count": 1,
    "transformer_count": 0,
    "generator_count": 0,
    "load_count": 0,
    "has_slack_bus": true,
    "connected": true
  },
  "trace_id": "trace-abc123"
}
```

---

## Short Circuit Analysis

### POST /api/v1/studies/run (Short Circuit)

Execute a short circuit analysis compliant with IEC 60909.

**Request (short_circuit study_type):**
```json
{
  "study_type": "short_circuit",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05, "base_kv": 138.0},
      {"bus_id": 2, "bus_type": "pq", "base_kv": 13.8}
    ],
    "lines": [
      {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
    ],
    "generators": [
      {"generator_id": 1, "bus_id": 1, "x1": 0.15, "x2": 0.15, "x0": 0.05}
    ]
  },
  "parameters": {
    "fault_location": 2,
    "fault_type": "three_phase",
    "standards": "iec_60909",
    "voltage_factor_c": 1.1
  }
}
```

**Supported Fault Types:**
- `three_phase` — Three-phase balanced fault (3ph)
- `line_to_line` — Line-to-line fault (L-L)
- `line_to_line_to_ground` — Double line-to-ground fault (L-L-G)
- `single_line_to_ground` — Single line-to-ground fault (L-G)

**Response:**
```json
{
  "task_id": "sc-20260304-001",
  "study_type": "short_circuit",
  "status": "completed",
  "results": {
    "fault_bus": 2,
    "fault_type": "three_phase",
    "symmetrical_fault_current_ka": 25.5,
    "peak_current_ka": 65.2,
    "x_r_ratio": 12.5,
    "dc_component_ka": 8.5,
    "symmetrical_breaking_current_ka": 22.3,
    "asymmetrical_breaking_current_ka": 28.1,
    "sequence_currents": {
      "positive_sequence_ka": 25.5,
      "negative_sequence_ka": 0.0,
      "zero_sequence_ka": 0.0
    },
    "contributions": [
      {
        "source": "Generator 1",
        "current_ka": 18.2,
        "x_r_ratio": 15.3
      },
      {
        "source": "Grid (slack)",
        "current_ka": 7.3,
        "x_r_ratio": 8.2
      }
    ],
    "compliance": {
      "iec_60909": true,
      "voltage_factor_c": 1.1,
      "method": "equivalent_voltage_source"
    }
  }
}
```

---

## Arc Flash Analysis

### POST /api/v1/studies/run (Arc Flash)

Execute an arc flash hazard analysis per IEEE 1584-2018 and NFPA 70E.

**Request (arc_flash study_type):**
```json
{
  "study_type": "arc_flash",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05, "base_kv": 13.8},
      {"bus_id": 2, "bus_type": "pq", "base_kv": 4.16}
    ],
    "lines": [
      {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
    ]
  },
  "parameters": {
    "fault_bus": 2,
    "voltage_kv": 4.16,
    "bolted_fault_current_ka": 20.0,
    "arc_duration_sec": 0.5,
    "working_distance_mm": 610.0,
    "equipment_type": "switchgear",
    "electrode_configuration": "VCB",
    "grounding_type": "solidly_grounded"
  }
}
```

**Supported Electrode Configurations (IEEE 1584-2018):**
- `VCB` — Vertical conductors/electrodes inside a metal box
- `VCBB` — Vertical conductors/electrodes terminated in an insulating barrier inside a metal box
- `HCB` — Horizontal conductors/electrodes inside a metal box
- `VOA` — Vertical conductors/electrodes in open air
- `HOA` — Horizontal conductors/electrodes in open air

**Response:**
```json
{
  "task_id": "af-20260304-001",
  "study_type": "arc_flash",
  "status": "completed",
  "results": {
    "fault_bus": 2,
    "arcing_current_ka": 16.8,
    "arc_current_variation_85_percent_ka": 14.3,
    "incident_energy_cal_cm2": 8.5,
    "arc_flash_boundary_mm": 1500,
    "ppe_level": "Category 2",
    "minimum_ppe_rating_cal_cm2": 8.0,
    "limited_approach_boundary_ft": 3.5,
    "restricted_approach_boundary_ft": 1.0,
    "electrode_configuration": "VCB",
    "working_distance_mm": 610,
    "arc_duration_sec": 0.5,
    "recommendations": [
      "Use Category 2 PPE minimum (8 cal/cm²)",
      "Maintain safe working distance of 610 mm",
      "Arc flash boundary: 1.5 m — barricade required",
      "Two-second rule applied for arc duration > 2s"
    ],
    "compliance": {
      "ieee_1584_2018": true,
      "nfpa_70e": true
    }
  }
}
```

---

## Harmonic Analysis

### POST /api/v1/studies/run (Harmonic)

Execute harmonic distortion analysis per IEEE 519-2022.

**Request (harmonic_analysis study_type):**
```json
{
  "study_type": "harmonic_analysis",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05, "base_kv": 13.8},
      {"bus_id": 5, "bus_type": "pq", "base_kv": 0.48}
    ]
  },
  "parameters": {
    "harmonic_sources": [
      {
        "source_id": "vfd1",
        "bus_id": 5,
        "type": "variable_frequency_drive",
        "harmonics": [
          {"order": 5, "magnitude_pu": 0.15},
          {"order": 7, "magnitude_pu": 0.10},
          {"order": 11, "magnitude_pu": 0.06},
          {"order": 13, "magnitude_pu": 0.04}
        ]
      }
    ],
    "pcc_bus": 5,
    "max_harmonic_order": 50,
    "isc_il_ratio": 120.0
  }
}
```

**Response:**
```json
{
  "task_id": "ha-20260304-001",
  "study_type": "harmonic_analysis",
  "status": "completed",
  "results": {
    "pcc_bus": 5,
    "thd_voltage_percent": 3.2,
    "thd_current_percent": 4.5,
    "tdd_percent": 4.5,
    "individual_harmonics": [
      {"order": 5, "voltage_percent": 2.1, "current_percent": 3.2},
      {"order": 7, "voltage_percent": 1.5, "current_percent": 2.1},
      {"order": 11, "voltage_percent": 0.8, "current_percent": 1.2},
      {"order": 13, "voltage_percent": 0.5, "current_percent": 0.8}
    ],
    "ieee_519_limits": [
      {"order": 5, "voltage_limit_percent": 3.0, "current_limit_percent": 12.0},
      {"order": 7, "voltage_limit_percent": 3.0, "current_limit_percent": 8.0},
      {"order": 11, "voltage_limit_percent": 3.0, "current_limit_percent": 5.0}
    ],
    "resonance_detected": false,
    "resonance_frequencies": [],
    "compliance": {
      "ieee_519_2022": true,
      "thd_voltage_within_limit": true,
      "thd_current_within_limit": true,
      "tdd_within_limit": true,
      "limits_exceeded": []
    }
  }
}
```

---

## Agent Management Endpoints

### GET /api/v1/agents

List all available engineering agents and their capabilities.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "agents": [
    {
      "id": "load-flow-agent",
      "name": "Load Flow Agent",
      "description": "Power flow analysis using Newton-Raphson and Fast Decoupled methods",
      "study_types": ["load_flow"],
      "standards": ["IEEE 141", "IEEE 399"],
      "status": "available"
    },
    {
      "id": "shortcircuit-agent",
      "name": "Short Circuit Agent",
      "description": "Fault current analysis per IEC 60909",
      "study_types": ["short_circuit"],
      "standards": ["IEC 60909", "IEEE C37.010"],
      "status": "available"
    },
    {
      "id": "arcflash-agent",
      "name": "Arc Flash Analysis Agent",
      "description": "Incident energy and PPE calculation per IEEE 1584-2018",
      "study_types": ["arc_flash"],
      "standards": ["IEEE 1584-2018", "NFPA 70E"],
      "status": "available"
    },
    {
      "id": "protection-agent",
      "name": "Protection Coordination Agent",
      "description": "Relay coordination per IEC 60255",
      "study_types": ["protection_coordination"],
      "standards": ["IEC 60255"],
      "status": "available"
    },
    {
      "id": "etap-engineer-agent",
      "name": "ETAP Engineering Agent",
      "description": "ETAP COM automation interface",
      "study_types": ["etap_load_flow", "etap_short_circuit"],
      "standards": [],
      "status": "available"
    },
    {
      "id": "power-system-coordinator-agent",
      "name": "Power System Coordinator Agent",
      "description": "Multi-agent workflow orchestration",
      "study_types": [],
      "standards": [],
      "status": "available"
    }
  ],
  "trace_id": "trace-xyz789"
}
```

### POST /api/v1/agents/{agent_id}/chat

Send a message to a specific agent for conversational engineering assistance.

**Authentication:** Required

**Request:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What are the IEEE 519 limits for a system with Isc/IL = 120?"
    }
  ],
  "system_prompt_override": null,
  "max_tokens": 2048,
  "temperature": 0.3
}
```

**Response (200 OK):**
```json
{
  "agent_id": "load-flow-agent",
  "response": "For a system with Isc/IL ratio of 120 (between 100 and 1000), IEEE 519-2022 Table 2 specifies the following individual harmonic current distortion limits at the PCC:\n\n| Harmonic Order | Limit (% of IL) |\n|---------------|------------------|\n| h < 11 | 12.0% |\n| 11 ≤ h < 17 | 5.5% |\n| 17 ≤ h < 23 | 5.0% |\n| 23 ≤ h < 35 | 2.0% |\n| 35 ≤ h < 50 | 1.0% |\n| TDD | 15.0% |",
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": 245,
    "completion_tokens": 132,
    "total_tokens": 377
  },
  "trace_id": "trace-chat-abc123"
}
```

---

## Provider Management Endpoints

### GET /api/v1/providers

List configured LLM providers and their health status.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "model": "gpt-4",
      "baseURL": "https://api.openai.com/v1",
      "configured": true,
      "healthy": true,
      "circuit": "closed",
      "avgLatencyMs": 450,
      "failureRate": 0.02
    },
    {
      "id": "nvidia-nim",
      "name": "NVIDIA NIM",
      "model": "meta/llama-3.1-70b-instruct",
      "baseURL": "https://integrate.api.nvidia.com/v1",
      "configured": true,
      "healthy": true,
      "circuit": "closed",
      "avgLatencyMs": 320,
      "failureRate": 0.01
    },
    {
      "id": "mastra",
      "name": "Mastra Backend",
      "model": "proxy",
      "baseURL": "http://localhost:4111",
      "configured": true,
      "healthy": true,
      "circuit": "closed",
      "avgLatencyMs": 0,
      "failureRate": 0
    }
  ],
  "trace_id": "trace-prov-123"
}
```

---

## Audit Logging Endpoints

### GET /api/v1/audit/logs

Retrieve audit log entries for compliance and security review.

**Authentication:** Required (Admin role)

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | today | Filter logs by date (ISO 8601) |
| `action` | string | all | Filter by action type |
| `limit` | integer | 100 | Maximum number of entries |
| `offset` | integer | 0 | Pagination offset |

**Response (200 OK):**
```json
{
  "logs": [
    {
      "timestamp": "2026-03-04T14:30:00Z",
      "traceId": "trace-abc123",
      "clientIp": "203.0.113.45",
      "method": "POST",
      "path": "/api/v1/studies/run",
      "statusCode": 200,
      "userAgent": "ETAP-Client/1.0",
      "action": "RUN_STUDY",
      "authenticated": true,
      "rateLimited": false,
      "apiKeyId": "key-engineer-001",
      "scope": "studies:run"
    }
  ],
  "count": 1,
  "date": "2026-03-04",
  "trace_id": "trace-audit-456"
}
```

---

## SCADA Real-Time Endpoints

### GET /api/v1/scada/measurements

Retrieve real-time measurement data from SCADA integration.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bus_id` | integer | all | Filter by bus ID |
| `measurement_type` | string | all | V, I, P, Q, f |
| `time_range` | string | 5m | Time range (1m, 5m, 15m, 1h, 6h, 24h) |

**Response (200 OK):**
```json
{
  "measurements": [
    {
      "bus_id": 1,
      "logical_node": "MMXU1",
      "timestamp": "2026-03-04T14:30:00.500Z",
      "voltage_kv": 138.2,
      "current_a": 425.5,
      "power_mw": 55.2,
      "power_mvar": 18.5,
      "frequency_hz": 60.01,
      "quality": "good",
      "iec61850_ref": "LD0/LLN0$MX$MMXU1"
    }
  ],
  "data_quality": {
    "total_points": 1,
    "valid_points": 1,
    "stale_points": 0,
    "suspect_points": 0
  },
  "timestamp": "2026-03-04T14:30:01Z"
}
```

### GET /api/v1/scada/alarms

Retrieve active SCADA alarms and events.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "alarms": [
    {
      "alarm_id": "ALM-001",
      "timestamp": "2026-03-04T14:28:30Z",
      "bus_id": 5,
      "severity": "warning",
      "message": "Voltage below 0.95 pu threshold",
      "value": 0.942,
      "threshold": 0.95,
      "logical_node": "MMXU1",
      "acknowledged": false
    }
  ],
  "total_active": 1,
  "timestamp": "2026-03-04T14:30:00Z"
}
```

### POST /api/v1/scada/state-estimation

Run state estimation on current SCADA measurements.

**Authentication:** Required

**Request:**
```json
{
  "measurements": [
    {"bus_id": 1, "type": "voltage", "value": 1.05, "sigma": 0.01},
    {"bus_id": 2, "type": "power_real", "value": 50.0, "sigma": 1.0},
    {"bus_id": 2, "type": "power_reactive", "value": 20.0, "sigma": 0.5}
  ],
  "method": "weighted_least_squares",
  "max_iterations": 50,
  "tolerance": 1e-6
}
```

**Response (200 OK):**
```json
{
  "converged": true,
  "iterations": 4,
  "estimated_state": {
    "1": {"voltage_pu": 1.048, "angle_deg": 0.0},
    "2": {"voltage_pu": 0.983, "angle_deg": -5.1}
  },
  "bad_data_detected": false,
  "largest_normalized_residual": 1.2,
  "observable": true,
  "timestamp": "2026-03-04T14:30:00Z"
}
```

---

## Predictive Analytics Endpoints

### POST /api/v1/predictive/load-forecast

Generate load forecast using ML models.

**Authentication:** Required

**Request:**
```json
{
  "historical_data": [45.2, 43.8, 42.1, 41.5, 43.2, 48.5, 55.2],
  "horizon_hours": 24,
  "season": "summer",
  "day_type": "weekday",
  "temperature_forecast": [28, 29, 30, 31, 30, 29, 28]
}
```

**Response (200 OK):**
```json
{
  "forecast": [52.1, 50.8, 49.5, 48.2, 47.5, 49.8, 55.3, 62.5, 68.2, 72.1],
  "confidence_intervals": {
    "lower_80": [48.5, 46.8, 45.2, 43.8, 42.9, 45.1, 50.5, 57.2, 62.5, 66.1],
    "upper_80": [55.7, 54.8, 53.8, 52.6, 52.1, 54.5, 60.1, 67.8, 73.9, 78.1]
  },
  "model_type": "lstm",
  "mape_percent": 2.3,
  "timestamp": "2026-03-04T14:30:00Z"
}
```

### POST /api/v1/predictive/anomaly-detect

Detect anomalies in measurement data streams.

**Authentication:** Required

**Request:**
```json
{
  "measurements": [
    {"timestamp": "2026-03-04T14:00:00Z", "bus_id": 1, "voltage_pu": 1.05, "current_a": 420.0, "power_mw": 55.0},
    {"timestamp": "2026-03-04T14:05:00Z", "bus_id": 1, "voltage_pu": 1.04, "current_a": 415.0, "power_mw": 54.0},
    {"timestamp": "2026-03-04T14:10:00Z", "bus_id": 1, "voltage_pu": 0.82, "current_a": 600.0, "power_mw": 55.0}
  ],
  "contamination": 0.05,
  "sensitivity": "medium"
}
```

**Response (200 OK):**
```json
{
  "anomalies": [
    {
      "index": 2,
      "timestamp": "2026-03-04T14:10:00Z",
      "anomaly_score": -0.85,
      "is_anomaly": true,
      "suspected_cause": "voltage_sag",
      "affected_measurements": ["voltage_pu"],
      "severity": "high"
    }
  ],
  "model_type": "isolation_forest",
  "total_samples": 3,
  "anomaly_count": 1,
  "timestamp": "2026-03-04T14:30:00Z"
}
```

### POST /api/v1/predictive/fault-predict

Predict fault type from measurement signatures.

**Authentication:** Required

**Request:**
```json
{
  "measurements": {
    "voltage_a_pu": 0.95,
    "voltage_b_pu": 0.65,
    "voltage_c_pu": 0.65,
    "current_a_pu": 1.2,
    "current_b_pu": 3.5,
    "current_c_pu": 3.5,
    "zero_sequence_v_pu": 0.12,
    "negative_sequence_v_pu": 0.25
  }
}
```

**Response (200 OK):**
```json
{
  "predicted_fault_type": "double_line_to_ground",
  "confidence": 0.92,
  "probabilities": {
    "three_phase": 0.03,
    "single_line_to_ground": 0.02,
    "line_to_line": 0.02,
    "double_line_to_ground": 0.92,
    "no_fault": 0.01
  },
  "model_type": "random_forest",
  "timestamp": "2026-03-04T14:30:00Z"
}
```

---

## WebSocket Endpoints

### WS /ws/study/{study_id}

Subscribe to real-time updates for a running study.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/study/task-20260304-001');
```

**Message Types (Server → Client):**

**Progress Update:**
```json
{
  "type": "progress",
  "study_id": "task-20260304-001",
  "progress_percent": 65,
  "current_step": "Running Newton-Raphson iteration 3/5",
  "timestamp": "2026-03-04T14:30:15Z"
}
```

**Study Completed:**
```json
{
  "type": "completed",
  "study_id": "task-20260304-001",
  "status": "completed",
  "converged": true,
  "execution_time_ms": 85.2,
  "timestamp": "2026-03-04T14:30:20Z"
}
```

**Study Failed:**
```json
{
  "type": "failed",
  "study_id": "task-20260304-001",
  "error": "Load flow did not converge after 50 iterations",
  "timestamp": "2026-03-04T14:30:45Z"
}
```

**Agent Status Update:**
```json
{
  "type": "agent_status",
  "study_id": "task-20260304-001",
  "agent_name": "LoadFlowAgent",
  "status": "running",
  "progress": "Building Y-bus matrix",
  "timestamp": "2026-03-04T14:30:12Z"
}
```

**Message Types (Client → Server):**

**Cancel Study:**
```json
{
  "type": "cancel",
  "study_id": "task-20260304-001"
}
```

---

## Report Generation

### POST /api/v1/reports/generate

Generate an engineering report from analysis results.

**Authentication:** Required

**Request:**
```json
{
  "analysis_results": {
    "study_type": "load_flow",
    "converged": true,
    "buses": {"1": {"voltage_magnitude_pu": 1.05}},
    "losses_mw": 0.5
  },
  "formats": ["pdf", "docx", "xlsx"],
  "template": "ieee_standard",
  "title": "Industrial Plant Load Flow Study",
  "include_charts": true,
  "include_recommendations": true,
  "project_info": {
    "project_name": "Industrial Plant Expansion",
    "engineer": "Eng. Ahmed Elbaz",
    "date": "2026-03-04"
  }
}
```

**Response (200 OK):**
```json
{
  "report_id": "rpt-20260304-001",
  "generated_files": {
    "pdf": "reports/rpt-20260304-001.pdf",
    "docx": "reports/rpt-20260304-001.docx",
    "xlsx": "reports/rpt-20260304-001.xlsx"
  },
  "download_urls": {
    "pdf": "/api/v1/reports/download/rpt-20260304-001.pdf",
    "docx": "/api/v1/reports/download/rpt-20260304-001.docx",
    "xlsx": "/api/v1/reports/download/rpt-20260304-001.xlsx"
  },
  "page_count": 15,
  "timestamp": "2026-03-04T14:30:00Z"
}
```

### GET /api/v1/reports/download/{filename}

Download a generated report file.

**Authentication:** Required

**Response:** Binary file download (Content-Type: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, or application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)

---

## Knowledge Base Endpoints

### POST /api/v1/knowledge/search

Search the engineering knowledge base using RAG.

**Authentication:** Required

**Request:**
```json
{
  "query": "What are the IEEE 519 harmonic limits for industrial systems?",
  "top_k": 5,
  "filters": {
    "standard": "ieee_519",
    "topic": "harmonics"
  },
  "include_citations": true
}
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "content": "IEEE 519-2022 Table 1 recommends voltage distortion limits of 5% THD for bus voltages at PCC ≤ 69 kV and 3% for 69 kV < V ≤ 161 kV...",
      "source": "IEEE 519-2022 Standard",
      "relevance_score": 0.95,
      "page": 45,
      "section": "Section 5.1 — Voltage Distortion Limits",
      "citation": "IEEE Std 519-2022, Table 1"
    }
  ],
  "total_results": 5,
  "query_time_ms": 42,
  "trace_id": "trace-kb-789"
}
```

### POST /api/v1/knowledge/add

Add a document to the engineering knowledge base.

**Authentication:** Required (Admin role)

**Request:**
```json
{
  "document": "PDF or text content (base64 encoded for binary)",
  "metadata": {
    "title": "IEEE 519-2022 Standard",
    "source": "IEEE",
    "year": 2022,
    "topics": ["harmonics", "power_quality"],
    "standard_number": "IEEE 519-2022"
  }
}
```

**Response (200 OK):**
```json
{
  "document_id": "doc-ieee519-2022",
  "chunks_created": 45,
  "status": "indexed",
  "timestamp": "2026-03-04T14:30:00Z"
}
```

---

## User Management Endpoints

### POST /api/v1/users/register

Register a new user account.

**Authentication:** Required (Admin role)

**Request:**
```json
{
  "username": "engineer1",
  "email": "engineer@example.com",
  "password": "SecurePassword123!",
  "role": "engineer"
}
```

**Response (201 Created):**
```json
{
  "user_id": "usr-002",
  "username": "engineer1",
  "email": "engineer@example.com",
  "role": "engineer",
  "permissions": ["studies:run", "reports:generate", "agents:list"],
  "created_at": "2026-03-04T14:30:00Z"
}
```

### GET /api/v1/users/profile

Get current user profile information.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "user_id": "usr-001",
  "username": "engineer@example.com",
  "role": "engineer",
  "permissions": ["studies:run", "reports:generate", "agents:list"],
  "last_login": "2026-03-04T08:00:00Z",
  "studies_run": 45
}
```

---

## Webhook Endpoints

### POST /api/v1/webhooks/subscribe

Subscribe to platform events.

**Authentication:** Required

**Request:**
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["study.completed", "study.failed", "report.generated", "alarm.triggered"],
  "secret": "webhook-secret-for-HMAC-signing"
}
```

**Response (200 OK):**
```json
{
  "webhook_id": "wh-001",
  "url": "https://your-server.com/webhook",
  "events": ["study.completed", "study.failed", "report.generated", "alarm.triggered"],
  "created_at": "2026-03-04T14:30:00Z"
}
```

---

## Rate Limiting

All endpoints are subject to rate limiting. Rate limit headers are included in every response:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1709558400
```

| Tier | Limit | Applies To |
|------|-------|------------|
| Standard | 100 req/min | All authenticated endpoints |
| Heavy | 10 req/min | OPF, harmonic analysis |
| Reports | 5 req/min | Report generation |
| Health | Unlimited | `/health`, `/healthz`, `/readyz` |

---

## Error Response Format

All errors follow a consistent JSON structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": [
      {
        "field": "voltage_magnitude",
        "issue": "Must be between 0.9 and 1.1 pu"
      }
    ],
    "timestamp": "2026-03-04T14:30:00Z",
    "request_id": "req-12345"
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTHENTICATION_REQUIRED` | 401 | Missing or invalid authentication token |
| `AUTHENTICATION_FAILED` | 401 | Invalid username or password |
| `FORBIDDEN` | 403 | Insufficient permissions for this action |
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `STUDY_FAILED` | 422 | Analysis calculation failed |
| `PROVIDER_UNAVAILABLE` | 503 | All LLM providers are down |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `CONFLICT` | 409 | Resource already exists |

---

## SDK Examples

### Python

```python
import requests

api_key = "your-api-key"
base_url = "http://localhost:8000/api/v1"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Run load flow
response = requests.post(
    f"{base_url}/studies/run",
    json={
        "study_type": "load_flow",
        "system": {"base_mva": 100, "buses": [...], "lines": [...]},
        "parameters": {"method": "newton_raphson"}
    },
    headers=headers
)
result = response.json()
print(f"Converged: {result['converged']}")

# Check SCADA measurements
response = requests.get(
    f"{base_url}/scada/measurements?bus_id=1",
    headers=headers
)
measurements = response.json()

# Run anomaly detection
response = requests.post(
    f"{base_url}/predictive/anomaly-detect",
    json={"measurements": [...], "contamination": 0.05},
    headers=headers
)
anomalies = response.json()
```

### JavaScript/TypeScript

```typescript
const baseURL = 'http://localhost:8000/api/v1';
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};

// Run arc flash study
const response = await fetch(`${baseURL}/studies/run`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    study_type: 'arc_flash',
    system: { base_mva: 100, buses: [...] },
    parameters: { voltage_kv: 4.16, bolted_fault_current_ka: 20 }
  })
});
const result = await response.json();

// WebSocket for live updates
const ws = new WebSocket(`ws://localhost:8000/ws/study/${result.task_id}`);
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(`Progress: ${update.progress_percent}%`);
};
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-03-04 | Initial API release with all endpoints documented |
