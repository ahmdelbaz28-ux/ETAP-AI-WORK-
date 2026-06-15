# ETAP AI Engineering Platform - API Documentation

## Base URL
```
Development: http://localhost:3000
Production: https://etap.yourdomain.com
```

## Authentication

All API endpoints (except `/health` and `/api/auth/login`) require JWT authentication.

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "engineer@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### Use Token
Include the token in the Authorization header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## Health Check

### GET /health
Check platform health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-06-04T14:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "vector_db": "connected"
  }
}
```

---

## Power System Analysis

### POST /api/analysis/load-flow
Execute Load Flow analysis.

**Request:**
```json
{
  "system_data": {
    "base_mva": 100.0,
    "buses": [
      {
        "bus_id": 1,
        "voltage_magnitude": 1.05,
        "bus_type": "slack"
      },
      {
        "bus_id": 2,
        "voltage_magnitude": 1.0,
        "bus_type": "pq"
      }
    ],
    "generators": [...],
    "loads": [...],
    "lines": [...]
  },
  "method": "newton_raphson",
  "max_iterations": 50,
  "tolerance": 1e-6
}
```

**Response:**
```json
{
  "converged": true,
  "iterations": 5,
  "results": {
    "buses": {
      "1": {
        "voltage_magnitude_pu": 1.05,
        "voltage_angle_deg": 0.0,
        "power_generated_mw": 55.2,
        "power_generated_mvar": 18.5
      },
      "2": {
        "voltage_magnitude_pu": 0.98,
        "voltage_angle_deg": -5.2,
        "power_consumed_mw": 50.0,
        "power_consumed_mvar": 20.0
      }
    },
    "lines": {...},
    "losses_mw": 0.5
  },
  "validation": {
    "all_voltages_within_limits": true,
    "all_lines_thermal_ok": true
  }
}
```

### POST /api/analysis/short-circuit
Execute Short Circuit analysis (IEC 60909).

**Request:**
```json
{
  "system_data": {...},
  "fault_location": 2,
  "fault_type": "three_phase",
  "standards": "iec_60909"
}
```

**Response:**
```json
{
  "fault_current_ka": 25.5,
  "x_r_ratio": 12.5,
  "peak_current_ka": 65.2,
  "dc_component_ka": 8.5,
  "symmetrical_breaking_current_ka": 22.3,
  "compliance": {
    "iec_60909": true,
    "notes": []
  }
}
```

### POST /api/analysis/arc-flash
Execute Arc Flash analysis (IEEE 1584-2018).

**Request:**
```json
{
  "voltage_kv": 4.16,
  "bolted_fault_current_ka": 20.0,
  "arc_duration_sec": 0.5,
  "working_distance_mm": 610.0,
  "equipment_type": "switchgear",
  "grounding_type": "solidly_grounded"
}
```

**Response:**
```json
{
  "incident_energy_cal_cm2": 8.5,
  "arc_flash_boundary_mm": 1500,
  "ppe_level": "Category 2",
  "minimum_ppe_rating_cal_cm2": 8.0,
  "recommendations": [
    "Use Category 2 PPE minimum",
    "Maintain safe distance of 1.5m"
  ]
}
```

### POST /api/analysis/harmonics
Execute Harmonic analysis (IEEE 519-2022).

**Request:**
```json
{
  "system_data": {...},
  "harmonic_sources": [
    {
      "source_id": "vfd1",
      "bus_id": 5,
      "type": "variable_frequency_drive",
      "harmonics": [
        {"order": 5, "magnitude_pu": 0.15},
        {"order": 7, "magnitude_pu": 0.10}
      ]
    }
  ],
  "max_harmonic_order": 50
}
```

**Response:**
```json
{
  "thd_voltage_percent": 3.2,
  "thd_current_percent": 4.5,
  "individual_harmonics": [
    {"order": 5, "voltage_percent": 2.1, "current_percent": 3.2},
    {"order": 7, "voltage_percent": 1.5, "current_percent": 2.1}
  ],
  "compliance": {
    "ieee_519_2022": true,
    "limits_exceeded": []
  },
  "resonance_detected": false
}
```

### POST /api/analysis/opf
Execute Optimal Power Flow.

**Request:**
```json
{
  "system_data": {...},
  "objective": "minimize_cost",
  "constraints": {
    "voltage_limits": [0.95, 1.05],
    "line_thermal_limits": true
  },
  "generator_costs": [
    {
      "generator_id": 1,
      "cost_coefficients": [100, 20, 0.5]
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "total_generation_mw": 150.5,
  "total_cost_per_hour": 2850.50,
  "optimal_dispatch": [
    {"generator_id": 1, "p_mw": 80.2, "q_mvar": 25.0},
    {"generator_id": 2, "p_mw": 70.3, "q_mvar": 20.5}
  ],
  "savings_vs_base_case": 450.25
}
```

---

## Multi-Agent Workflows

### POST /api/workflow/autonomous
Execute autonomous engineering workflow.

**Request:**
```json
{
  "user_goal": "Optimize this industrial power network for efficiency",
  "system_data": {...},
  "constraints": {
    "max_budget_usd": 100000,
    "required_standards": ["ieee", "iec"]
  }
}
```

**Response:**
```json
{
  "task_id": "wf-20260604-001",
  "status": "completed",
  "studies_performed": [
    "load_flow",
    "loss_analysis",
    "opf",
    "capacitor_placement",
    "fault_analysis"
  ],
  "results": {...},
  "recommendations": [
    "Install 5 MVAR capacitor bank at Bus 5",
    "Upgrade transformer T1 to reduce losses",
    "Expected annual savings: $45,000"
  ],
  "reports_generated": [
    "reports/wf-20260604-001.pdf",
    "reports/wf-20260604-001.xlsx"
  ]
}
```

### GET /api/workflow/{task_id}/status
Check workflow status.

**Response:**
```json
{
  "task_id": "wf-20260604-001",
  "status": "running",
  "progress_percent": 65,
  "current_step": "Running OPF optimization",
  "steps_completed": ["load_flow", "fault_analysis"],
  "steps_remaining": ["report_generation"]
}
```

---

## Report Generation

### POST /api/reports/generate
Generate engineering report.

**Request:**
```json
{
  "analysis_results": {...},
  "formats": ["pdf", "docx", "xlsx"],
  "template": "standard",
  "include_charts": true,
  "include_recommendations": true
}
```

**Response:**
```json
{
  "report_id": "rpt-20260604-001",
  "generated_files": {
    "pdf": "reports/rpt-20260604-001.pdf",
    "docx": "reports/rpt-20260604-001.docx",
    "xlsx": "reports/rpt-20260604-001.xlsx"
  },
  "download_urls": {
    "pdf": "/api/reports/download/rpt-20260604-001.pdf",
    "docx": "/api/reports/download/rpt-20260604-001.docx"
  }
}
```

### GET /api/reports/download/{filename}
Download generated report.

---

## Knowledge Base (RAG)

### POST /api/knowledge/search
Search engineering knowledge base.

**Request:**
```json
{
  "query": "What are the IEEE 519 harmonic limits for industrial systems?",
  "top_k": 5,
  "filters": {
    "standard": "ieee_519",
    "topic": "harmonics"
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "IEEE 519-2022 specifies voltage THD limits...",
      "source": "IEEE 519-2022 Standard",
      "relevance_score": 0.95,
      "page": 45
    }
  ]
}
```

### POST /api/knowledge/add
Add document to knowledge base.

**Request:**
```json
{
  "document": "PDF or text content",
  "metadata": {
    "title": "IEEE 519-2022 Standard",
    "source": "IEEE",
    "year": 2022,
    "topics": ["harmonics", "power_quality"]
  }
}
```

---

## ETAP Integration

### POST /api/etap/connect
Connect to ETAP application.

**Request:**
```json
{
  "etap_path": "C:\\Program Files\\ETAP\\ETAP.exe",
  "visible": false
}
```

**Response:**
```json
{
  "connected": true,
  "etap_version": "19.0",
  "session_id": "etap-sess-001"
}
```

### POST /api/etap/run-study
Execute ETAP study.

**Request:**
```json
{
  "session_id": "etap-sess-001",
  "study_type": "load_flow",
  "project_path": "C:\\Projects\\industrial.etap"
}
```

**Response:**
```json
{
  "success": true,
  "study_completed": true,
  "results_available": true,
  "export_path": "exports/study-results-001.csv"
}
```

---

## User Management

### POST /api/users/register
Register new user.

**Request:**
```json
{
  "username": "engineer1",
  "email": "engineer@example.com",
  "password": "secure_password",
  "role": "engineer"
}
```

### GET /api/users/profile
Get current user profile.

### PUT /api/users/profile
Update user profile.

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": [
      {
        "field": "voltage_magnitude",
        "issue": "Must be between 0.9 and 1.1 pu"
      }
    ],
    "timestamp": "2026-06-04T14:30:00Z",
    "request_id": "req-12345"
  }
}
```

### Common Error Codes
- `AUTHENTICATION_REQUIRED`: Missing or invalid token
- `VALIDATION_ERROR`: Invalid input data
- `NOT_FOUND`: Resource not found
- `INTERNAL_ERROR`: Server error
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `STUDY_FAILED`: Analysis calculation failed

---

## Rate Limiting

- Default: 100 requests per minute per user
- Heavy operations (OPF, harmonic): 10 requests per minute
- Report generation: 5 requests per minute

Rate limit headers included in response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1622815800
```

---

## Webhooks

Subscribe to events:

```json
POST /api/webhooks/subscribe
{
  "url": "https://your-server.com/webhook",
  "events": ["workflow.completed", "report.generated"],
  "secret": "webhook-secret-for-signing"
}
```

---

## SDK Examples

### Python
```python
import requests

api_key = "your-api-key"
base_url = "http://localhost:3000/api"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Run load flow
response = requests.post(
    f"{base_url}/analysis/load-flow",
    json={"system_data": {...}},
    headers=headers
)

result = response.json()
print(f"Converged: {result['converged']}")
```

### JavaScript
```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:3000/api',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// Run workflow
const result = await api.post('/workflow/autonomous', {
  user_goal: 'Optimize power system',
  system_data: {...}
});

console.log(result.data.recommendations);
```

---

## Versioning

API version is included in the URL path:
```
/api/v1/analysis/load-flow
```

Current version: v1

---

## Support

- Documentation: https://docs.etap-platform.com
- Email: support@etap-platform.com
- GitHub Issues: https://github.com/your-org/etap-platform/issues
