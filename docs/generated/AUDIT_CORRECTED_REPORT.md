# UI Coverage & Configuration Exposure Policy Audit — CORRECTED REPORT

**Project:** AhmedETAP AI Engineering Platform  
**Audit Date:** 2026-07-30  
**Correction Date:** 2026-07-30  
**Status:** CORRECTED — 7 errors found in initial audit, now fixed

---

## Self-Critique: Errors Found and Fixed

| # | Error in Original | Correction |
|---|-------------------|------------|
| 1 | Claimed 87 API endpoints | Actual: ~154 route decorators (some HEAD+GET duplicates, ~120 unique endpoints) |
| 2 | Missed database schemas | 8 tables: users, projects, study_results, sessions, audit_log, security_events, mfa_credentials, study_jobs |
| 3 | Missed feature flags | 4 flags: harmonic_analysis, motor_starting, transient_stability, optimal_power_flow |
| 4 | Missed MFA endpoints | TOTP setup/verify in api/mfa.py |
| 5 | Missed email webhooks | 6 endpoints in api/email_webhooks.py |
| 6 | Missed email dashboard | 7 endpoints in api/email_dashboard.py |
| 7 | Missed digital_twin.py and cua_confirmation_ws.py | Separate routers not cataloged |

---

## Corrected Audit Results

### 1. Complete API Endpoint Catalog (~120 unique endpoints)

#### Core Routes (api/routes.py) — 14 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/studies/run_async | POST | Async study execution | ❌ MISSING |
| /api/v1/studies/task_status/{task_id} | GET | Task status polling | ❌ MISSING |
| /ws/scada/live | WS | SCADA streaming | ScadaIntegration.tsx ✅ |
| /ws/cua/confirmation | WS | CUA dual-confirmation | ❌ MISSING |
| /ws/notifications | WS | Real-time notifications | ❌ MISSING |
| /api/v1/scada/live | GET | SCADA snapshot | ScadaIntegration.tsx ✅ |
| /api/v1/digital-twin/status | GET | Digital twin status | DigitalTwin.tsx ✅ |
| /api/v1/audit/verify | GET | Audit chain verification | ❌ MISSING |
| /admin/cua/kill-switch | GET | Kill switch status | CuaMonitor.tsx ✅ |
| /admin/cua/kill-switch/activate | POST | Activate kill switch | CuaMonitor.tsx ✅ |
| /admin/cua/kill-switch/deactivate | POST | Deactivate kill switch | CuaMonitor.tsx ✅ |
| /admin/cua/rollback | POST | CUA rollback | ❌ MISSING |
| /admin/cua/audit-log | GET | CUA audit log | ❌ MISSING |
| /api/v1/benchmark | GET | Benchmark | ❌ MISSING |

#### Studies (api/studies.py) — 2 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/studies/run | POST | Execute study | StudyRun.tsx ✅ |
| /api/v1/studies/types | GET | List study types | Studies.tsx ✅ |

#### Health (api/health.py) — 10 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| / | GET | Root | ❌ MISSING |
| /healthz | GET/HEAD | Health check | Diagnostics.tsx ✅ |
| /readyz | GET/HEAD | Readiness check | ❌ MISSING |
| /health | GET/HEAD | Health check | Diagnostics.tsx ✅ |
| /ready | GET/HEAD | Readiness check | ❌ MISSING |
| /api/v1/info | GET | Platform info | ❌ MISSING |
| /api/v1/knowledge | GET | Knowledge info | ❌ MISSING |
| /metrics | GET | Metrics | Administration.tsx ✅ |
| /prometheus/metrics | GET | Prometheus metrics | ❌ MISSING |

#### Auth (api/auth.py) — 11 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/auth/register | POST | Register | Register.tsx ✅ |
| /api/v1/auth/login | POST | Login | Login.tsx ✅ |
| /api/v1/auth/refresh | POST | Token refresh | ❌ MISSING |
| /api/v1/auth/logout | POST | Logout | Login.tsx ✅ |
| /api/v1/auth/me | GET | Current user | Administration.tsx ✅ |
| /api/v1/auth/me | PUT | Update profile | ❌ MISSING |
| /api/v1/auth/me/password | PUT | Change password | ❌ MISSING |
| /api/v1/auth/forgot-password | POST | Forgot password | Login.tsx ✅ |
| /api/v1/auth/reset-password | POST | Reset password | ❌ MISSING |
| /api/v1/auth/users | GET | List users | ❌ MISSING |
| /api/v1/auth/users/{user_id} | DELETE | Delete user | ❌ MISSING |

#### MFA (api/mfa.py) — 2 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/auth/totp/setup | POST | TOTP setup | ❌ MISSING |
| /api/v1/auth/totp/verify | POST | TOTP verify | ❌ MISSING |

#### Magic Links (api/magic_links.py) — 3 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/auth/magic-link/request | POST | Request magic link | ❌ MISSING |
| /api/v1/auth/magic-link/verify | POST | Verify magic link | ❌ MISSING |
| /api/v1/auth/magic-link/invalidate | POST | Invalidate magic link | ❌ MISSING |

#### Email OTP (api/email_otp.py) — 3 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/auth/email-otp/send | POST | Send OTP | ❌ MISSING |
| /api/v1/auth/email-otp/verify | POST | Verify OTP | ❌ MISSING |
| /api/v1/auth/email-otp/invalidate | POST | Invalidate OTP | ❌ MISSING |

#### Projects (api/projects.py) — 9 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/projects | GET | List projects | Projects.tsx ✅ |
| /api/v1/projects | POST | Create project | Projects.tsx ✅ |
| /api/v1/projects/{id} | GET | Get project | Projects.tsx ✅ |
| /api/v1/projects/{id} | PUT | Update project | Projects.tsx ✅ |
| /api/v1/projects/{id} | DELETE | Delete project | Projects.tsx ✅ |
| /api/v1/projects/{id}/studies | POST | Create study in project | ❌ MISSING |
| /api/v1/projects/{id}/studies | GET | List project studies | ❌ MISSING |

#### Study Versions (api/study_versions.py) — 4 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /projects/{pid}/studies/{sid}/versions | GET | List versions | ❌ MISSING |
| /projects/{pid}/studies/{sid}/versions | POST | Save version | ❌ MISSING |
| /projects/{pid}/studies/{sid}/versions/{vid}/rollback | POST | Rollback | ❌ MISSING |
| /projects/{pid}/studies/{sid}/versions/{v1}/compare/{v2} | GET | Compare | ❌ MISSING |

#### Templates (api/templates.py) — 6 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/templates | GET | List templates | ❌ MISSING |
| /api/v1/templates | POST | Create template | ❌ MISSING |
| /api/v1/templates/{id} | GET | Get template | ❌ MISSING |
| /api/v1/templates/{id} | PUT | Update template | ❌ MISSING |
| /api/v1/templates/{id} | DELETE | Delete template | ❌ MISSING |
| /api/v1/templates/{id}/apply | POST | Apply template | ❌ MISSING |

#### Settings (api/settings.py) — 7 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/settings/keys | GET | List keys | Settings.tsx ✅ |
| /api/v1/settings/keys/{provider} | GET | Get key | Settings.tsx ✅ |
| /api/v1/settings/keys/{provider} | POST | Save key | Settings.tsx ✅ |
| /api/v1/settings/keys/{provider} | DELETE | Delete key | Settings.tsx ✅ |
| /api/v1/settings/keys/{provider}/activate | POST | Activate key | Settings.tsx ✅ |
| /api/v1/settings/keys/{provider}/test | POST | Test key | Settings.tsx ✅ |
| /api/v1/settings/health | GET | Storage health | ❌ MISSING |

#### Agents (api/agents.py) — 15 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/agents | GET | List agents | Administration.tsx ✅ |
| /api/v1/agents/{id} | GET | Get agent | ❌ MISSING |
| /api/v1/agents/info | GET | Agents info | ❌ MISSING |
| /api/v1/agents/etap-expert/chat | POST | ETAP Expert chat | ❌ MISSING |
| /api/v1/agents/etap-gui/chat | POST | ETAP GUI chat | ❌ MISSING |
| /api/v1/agents/etap-gui/execute | POST | CUA execution | ❌ MISSING |
| /api/v1/agents/etap-gui/health | GET | GUI health | ❌ MISSING |
| /api/v1/agents/etap-gui/kill-switch/activate | POST | Activate kill switch | ❌ MISSING |
| /api/v1/agents/etap-gui/kill-switch/deactivate | POST | Deactivate kill switch | ❌ MISSING |
| /api/v1/agents/etap-gui/safety/health | GET | Safety status | ❌ MISSING |
| /api/v1/agents/etap-gui/safety/audit/verify | GET | Audit verify | ❌ MISSING |
| /api/v1/agents/etap-gui/siem/health | GET | SIEM health | ❌ MISSING |
| /api/v1/agents/etap-gui/siem/events | GET | SIEM events | ❌ MISSING |
| /api/v1/agents/ahmed-etap/orchestrate | POST | Orchestration | ❌ MISSING |
| /api/v1/agents/ahmed-etap/info | GET | Orchestration info | ❌ MISSING |

#### AI/ML (api/ai_ml.py) — 7 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/ml/capabilities | GET | ML capabilities | ❌ MISSING |
| /api/v1/predict/load | POST | Load forecasting | ❌ MISSING |
| /api/v1/predict/fault | POST | Fault prediction | ❌ MISSING |
| /api/v1/predict/fault/train | POST | Train fault model | ❌ MISSING |
| /api/v1/predict/anomaly | POST | Anomaly detection | ❌ MISSING |
| /api/v1/gnn/predict | POST | GNN prediction | ❌ MISSING |
| /api/v1/rag/query | POST | RAG query | ❌ MISSING |

#### RBAC (api/rbac.py) — 9 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/rbac/roles | GET | List roles | ❌ MISSING |
| /api/v1/rbac/roles | POST | Create role | ❌ MISSING |
| /api/v1/rbac/roles/{id} | PUT | Update role | ❌ MISSING |
| /api/v1/rbac/roles/{id} | DELETE | Delete role | ❌ MISSING |
| /api/v1/rbac/permissions | GET | List permissions | ❌ MISSING |
| /api/v1/rbac/permissions | POST | Create permission | ❌ MISSING |
| /api/v1/rbac/users/{id}/roles | GET | Get user roles | ❌ MISSING |
| /api/v1/rbac/users/{id}/roles | POST | Assign role | ❌ MISSING |
| /api/v1/rbac/users/{id}/roles/{rid} | DELETE | Remove role | ❌ MISSING |

#### Equipment (api/equipment.py) — 11 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/equipment/categories | GET | List categories | ❌ MISSING |
| /api/v1/equipment/categories | POST | Create category | ❌ MISSING |
| /api/v1/equipment/categories/{id} | PUT | Update category | ❌ MISSING |
| /api/v1/equipment/categories/{id} | DELETE | Delete category | ❌ MISSING |
| /api/v1/equipment | GET | List equipment | ❌ MISSING |
| /api/v1/equipment | POST | Create equipment | ❌ MISSING |
| /api/v1/equipment/{id} | GET | Get equipment | ❌ MISSING |
| /api/v1/equipment/{id} | PUT | Update equipment | ❌ MISSING |
| /api/v1/equipment/{id} | DELETE | Delete equipment | ❌ MISSING |
| /api/v1/equipment/search | GET | Search equipment | ❌ MISSING |
| /api/v1/equipment/import | POST | Import equipment | ❌ MISSING |
| /api/v1/equipment/export | GET | Export equipment | ❌ MISSING |

#### Assets (api/assets.py) — 5 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/assets | GET | List assets | AssetManagement.tsx ✅ |
| /api/v1/assets | POST | Create asset | AssetManagement.tsx ✅ |
| /api/v1/assets/{id} | GET | Get asset | AssetManagement.tsx ✅ |
| /api/v1/assets/{id} | PUT | Update asset | AssetManagement.tsx ✅ |
| /api/v1/assets/{id} | DELETE | Delete asset | AssetManagement.tsx ✅ |

#### Notifications (api/notifications.py) — 5 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/notifications | GET | List notifications | ❌ MISSING |
| /api/v1/notifications/unread | GET | Unread count | ❌ MISSING |
| /api/v1/notifications/{id}/read | PUT | Mark read | ❌ MISSING |
| /api/v1/notifications/read-all | PUT | Mark all read | ❌ MISSING |
| /api/v1/notifications/test | POST | Test notification | ❌ MISSING |

#### Data Import (api/data_import.py) — 2 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/data-import/formats | GET | Import formats | DataImport.tsx ✅ |
| /api/v1/data-import/upload | POST | Upload data | DataImport.tsx ✅ |

#### Export (api/export.py) — 3 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/export/{id}/pdf | POST | Export PDF | DataExport.tsx ✅ |
| /api/v1/export/{id}/excel | POST | Export Excel | DataExport.tsx ✅ |
| /api/v1/export/history | GET | Export history | DataExport.tsx ✅ |

#### Validation (api/validation.py) — 1 endpoint
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/validation/validate | POST | Validate study | ❌ MISSING |

#### Context Engine (api/context_engine.py) — 2 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/context/retrieve | POST | Context retrieval | ❌ MISSING |
| /api/v1/context/impact | POST | Impact analysis | ❌ MISSING |

#### SCADA (api/scada.py) — 1 endpoint
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/scada/live | GET | SCADA live data | ScadaIntegration.tsx ✅ |

#### Digital Twin (api/digital_twin.py) — 1 endpoint
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/digital-twin/status | GET | Digital twin status | DigitalTwin.tsx ✅ |

#### Email Webhooks (api/email_webhooks.py) — 6 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/email/webhooks/resend | POST | Resend webhook | ❌ MISSING |
| /api/v1/email/webhooks/endpoints | POST | Create endpoint | ❌ MISSING |
| /api/v1/email/webhooks/endpoints | GET | List endpoints | ❌ MISSING |
| /api/v1/email/webhooks/endpoints/{id} | DELETE | Delete endpoint | ❌ MISSING |
| /api/v1/email/webhooks/endpoints/{id}/test | POST | Test endpoint | ❌ MISSING |
| /api/v1/email/webhooks/events | GET | List events | ❌ MISSING |

#### Email Digest (api/email_digest.py) — 4 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/email-digest/config | GET | Digest config | ❌ MISSING |
| /api/v1/email-digest/generate | POST | Generate digest | ❌ MISSING |
| /api/v1/email-digest/preview/{email} | GET | Preview digest | ❌ MISSING |
| /api/v1/email-digest/schedule/run | POST | Run scheduled | ❌ MISSING |

#### Email Dashboard (api/email_dashboard.py) — 7 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/email-dashboard/api/stats | GET | Email stats | ❌ MISSING |
| /api/v1/email-dashboard/api/recent | GET | Recent sends | ❌ MISSING |
| /api/v1/email-dashboard/api/by-day | GET | Daily counts | ❌ MISSING |
| /api/v1/email-dashboard/api/record/{id} | GET | Record detail | ❌ MISSING |
| /api/v1/email-dashboard/api/clear | POST | Clear logs | ❌ MISSING |
| /api/v1/email-dashboard/api/config | GET | Config | ❌ MISSING |
| /api/v1/email-dashboard | GET | Dashboard HTML | ❌ MISSING |

#### Dependencies (api/dependencies.py) — 2 endpoints
| Endpoint | Method | Feature | UI Page |
|----------|--------|---------|---------|
| /api/v1/users/me | GET | Current user | Administration.tsx ✅ |
| /api/v1/users/{id} | DELETE | Delete user | ❌ MISSING |

---

### 2. Database Schema (8 tables)

| Table | Columns | UI Coverage |
|-------|---------|-------------|
| users | id, username, email, password_hash, role, is_active, created_at, updated_at | Login/Register ✅ |
| projects | id, name, description, system_config, created_by, status, created_at, updated_at | Projects.tsx ✅ |
| study_results | id, project_id, study_type, parameters, results, status, created_at | Studies.tsx ✅ |
| sessions | id, user_id, token, expires_at, created_at | ❌ MISSING |
| audit_log | id, user_id, action, resource, details, ip_address, created_at | ❌ MISSING |
| security_events | id, event_type, severity, details, ip_address, created_at | ❌ MISSING |
| mfa_credentials | id, user_id, method, secret, verified, created_at | ❌ MISSING |
| study_jobs | id, study_id, job_type, status, progress, result, created_at | ❌ MISSING |

### 3. Feature Flags (4 flags)

| Flag | Status | Description | UI Coverage |
|------|--------|-------------|-------------|
| harmonic_analysis | beta/disabled | IEEE 519 harmonic analysis | Studies.tsx (shows disabled) ✅ |
| motor_starting | beta/disabled | IEEE 399 motor starting | Studies.tsx (shows disabled) ✅ |
| transient_stability | alpha/disabled | Swing equation stability | Studies.tsx (shows disabled) ✅ |
| optimal_power_flow | alpha/disabled | Economic dispatch OPF | Studies.tsx (shows disabled) ✅ |

---

### 4. Corrected UI Completeness Score

| Metric | Original (Wrong) | Corrected |
|--------|-----------------|-----------|
| Total Backend Features | 87 | ~120 unique endpoints |
| Total UI Pages | 22 | 22 |
| Mapped Features | 34 | 34 |
| Hidden Features | 53 | ~86 |
| Missing Pages | 6 | 6 |
| Missing Settings | 7 | 7 |
| Unused APIs (no UI) | 53 | ~86 |
| Dead Buttons | 0 | 0 |
| **Coverage Percentage** | **39%** | **~28%** |

**The corrected coverage is ~28%, not 39% as originally claimed.** This is because I undercounted the total endpoints.

---

### 5. Corrected Implementation Plan

The implementation plan remains valid but the scope is larger. The 7 new pages (RBACAdmin, Templates, EquipmentLibrary, AILab, StudyVersions, Validation, Notifications) address the most critical gaps. Additional pages needed:

- **Email Dashboard** — for email_webhooks, email_digest, email_dashboard endpoints
- **MFA Settings** — for TOTP setup/verify
- **Session Management** — for sessions table
- **Audit Log Viewer** — for audit_log table
- **Security Events Viewer** — for security_events table

---

### 6. Justified Hidden Features

| Feature | Justification |
|---------|---------------|
| CUA Loop execution | Life-safety critical, requires physical workstation |
| Email OTP/Magic Links | Authentication backend only |
| SIEM endpoints | Operational/integration only |
| Benchmark endpoint | Diagnostic only |
| Prometheus metrics | Infrastructure only |
| Email webhooks | Backend integration only |
| Email digest scheduling | Backend cron only |

---

**AUDIT CORRECTED: Coverage is ~28% (not 39%). Target remains 100%.**