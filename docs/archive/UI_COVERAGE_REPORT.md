# UI Coverage & Configuration Exposure Audit Report
**Generated**: 2026-07-31 04:30 UTC
**Version**: 2.1.0
**Coverage Target**: 100%

---

## Executive Summary

| Metric | Count | Coverage |
|--------|-------|----------|
| Total Backend Features (API Endpoints) | 139 | — |
| Total UI Pages | 22 | — |
| Mapped Features (Backend ↔ UI) | 95 | 68.3% |
| Hidden Features (No UI Access) | 44 | 31.7% |
| Dead UI Elements (No Backend) | 0 | 0% |
| Missing Settings Panels | 8 | — |
| Missing CRUD Pages | 5 | — |
| Missing Navigation Items | 6 | — |

**UI Coverage Score: 68.3%** — Below the 100% target. 44 backend features lack UI access.

---

## 1. API Endpoints → UI Page Mapping

### 1.1 Mapped Endpoints (95 endpoints with UI coverage)

| API Endpoint | Method | UI Page | Status |
|-------------|--------|---------|--------|
| `/health` | GET | Sidebar (health indicator) | ✅ |
| `/ready` | GET | Sidebar (health indicator) | ✅ |
| `/healthz` | GET | Sidebar (health indicator) | ✅ |
| `/readyz` | GET | Sidebar (health indicator) | ✅ |
| `/metrics` | GET | Dashboard | ✅ |
| `/api/v1/info` | GET | Dashboard | ✅ |
| `/api/v1/knowledge` | GET | Dashboard | ✅ |
| `/api/v1/studies/run` | POST | StudyRun | ✅ |
| `/api/v1/studies/types` | GET | Studies | ✅ |
| `/api/v1/studies/run_async` | POST | StudyRun | ✅ |
| `/api/v1/studies/task_status/{task_id}` | GET | StudyRun | ✅ |
| `/api/v1/agents` | GET | AIAssistant | ✅ |
| `/api/v1/agents/{agent_id}` | GET | AIAssistant | ✅ |
| `/api/v1/agents/info` | GET | AIAssistant | ✅ |
| `/api/v1/agents/etap-expert/chat` | POST | AIAssistant | ✅ |
| `/api/v1/agents/etap-gui/chat` | POST | AIAssistant | ✅ |
| `/api/v1/agents/etap-gui/execute` | POST | AIAssistant | ✅ |
| `/api/v1/agents/etap-gui/health` | GET | AIAssistant | ✅ |
| `/api/v1/agents/etap-gui/kill-switch/activate` | POST | CuaMonitor | ✅ |
| `/api/v1/agents/etap-gui/kill-switch/deactivate` | POST | CuaMonitor | ✅ |
| `/api/v1/agents/etap-gui/safety/health` | GET | CuaMonitor | ✅ |
| `/api/v1/agents/etap-gui/safety/audit/verify` | GET | CuaMonitor | ✅ |
| `/api/v1/agents/etap-gui/siem/health` | GET | CuaMonitor | ✅ |
| `/api/v1/agents/etap-gui/siem/events` | GET | CuaMonitor | ✅ |
| `/api/v1/agents/ahmed-etap/orchestrate` | POST | AIAssistant | ✅ |
| `/api/v1/agents/ahmed-etap/info` | GET | AIAssistant | ✅ |
| `/api/v1/auth/register` | POST | Register | ✅ |
| `/api/v1/auth/login` | POST | Login | ✅ |
| `/api/v1/auth/refresh` | POST | Login | ✅ |
| `/api/v1/auth/logout` | POST | Login | ✅ |
| `/api/v1/auth/me` | GET | Settings/Profile | ✅ |
| `/api/v1/auth/me` | PUT | Settings/Profile | ✅ |
| `/api/v1/auth/me/password` | PUT | Settings/Profile | ✅ |
| `/api/v1/auth/forgot-password` | POST | Login | ✅ |
| `/api/v1/auth/reset-password` | POST | Login | ✅ |
| `/api/v1/auth/users` | GET | Administration | ✅ |
| `/api/v1/auth/users/{user_id}` | DELETE | Administration | ✅ |
| `/api/v1/auth/email-otp/send` | POST | Login | ✅ |
| `/api/v1/auth/email-otp/verify` | POST | Login | ✅ |
| `/api/v1/auth/email-otp/invalidate` | POST | Login | ✅ |
| `/api/v1/auth/magic-link/request` | POST | Login | ✅ |
| `/api/v1/auth/magic-link/verify` | POST | Login | ✅ |
| `/api/v1/auth/magic-link/invalidate` | POST | Login | ✅ |
| `/api/v1/auth/totp/setup` | POST | Settings/Security | ✅ |
| `/api/v1/auth/totp/verify` | POST | Settings/Security | ✅ |
| `/api/v1/projects` | GET | Projects | ✅ |
| `/api/v1/projects/` | GET | Projects | ✅ |
| `/api/v1/projects` | POST | Projects | ✅ |
| `/api/v1/projects/` | POST | Projects | ✅ |
| `/api/v1/projects/{project_id}` | GET | Projects | ✅ |
| `/api/v1/projects/{project_id}` | PUT | Projects | ✅ |
| `/api/v1/projects/{project_id}` | DELETE | Projects | ✅ |
| `/api/v1/projects/{project_id}/studies` | POST | Studies | ✅ |
| `/api/v1/projects/{project_id}/studies` | GET | Studies | ✅ |
| `/api/v1/studies/{project_id}/studies/{study_id}/versions` | GET | Studies | ✅ |
| `/api/v1/studies/{project_id}/studies/{study_id}/versions` | POST | Studies | ✅ |
| `/api/v1/studies/{project_id}/studies/{study_id}/versions/{version_id}/rollback` | POST | Studies | ✅ |
| `/api/v1/studies/{project_id}/studies/{study_id}/versions/{v1}/compare/{v2}` | GET | Studies | ✅ |
| `/api/v1/settings/keys` | GET | Settings | ✅ |
| `/api/v1/settings/keys/{provider}` | GET | Settings | ✅ |
| `/api/v1/settings/keys/{provider}` | POST | Settings | ✅ |
| `/api/v1/settings/keys/{provider}` | DELETE | Settings | ✅ |
| `/api/v1/settings/keys/{provider}/activate` | POST | Settings | ✅ |
| `/api/v1/settings/keys/{provider}/test` | POST | Settings | ✅ |
| `/api/v1/settings/health` | GET | Settings | ✅ |
| `/api/v1/scada/live` | GET | ScadaIntegration | ✅ |
| `/api/v1/digital-twin/status` | GET | DigitalTwin | ✅ |
| `/api/v1/equipment/categories` | GET | AssetManagement | ✅ |
| `/api/v1/equipment/categories` | POST | AssetManagement | ✅ |
| `/api/v1/equipment/categories/{category_id}` | PUT | AssetManagement | ✅ |
| `/api/v1/equipment/categories/{category_id}` | DELETE | AssetManagement | ✅ |
| `/api/v1/equipment/` | GET | AssetManagement | ✅ |
| `/api/v1/equipment/` | POST | AssetManagement | ✅ |
| `/api/v1/equipment/{equipment_id}` | GET | AssetManagement | ✅ |
| `/api/v1/equipment/{equipment_id}` | PUT | AssetManagement | ✅ |
| `/api/v1/equipment/{equipment_id}` | DELETE | AssetManagement | ✅ |
| `/api/v1/equipment/search` | GET | AssetManagement | ✅ |
| `/api/v1/equipment/import` | POST | DataImport | ✅ |
| `/api/v1/equipment/export` | GET | DataExport | ✅ |
| `/api/v1/export/{project_id}/pdf` | POST | DataExport | ✅ |
| `/api/v1/export/{project_id}/excel` | POST | DataExport | ✅ |
| `/api/v1/export/history` | GET | DataExport | ✅ |
| `/api/v1/data-import/formats` | GET | DataImport | ✅ |
| `/api/v1/data-import/upload` | POST | DataImport | ✅ |
| `/api/v1/validation/validate` | POST | Studies | ✅ |
| `/api/v1/rbac/roles` | GET | Administration | ✅ |
| `/api/v1/rbac/roles` | POST | Administration | ✅ |
| `/api/v1/rbac/roles/{role_id}` | PUT | Administration | ✅ |
| `/api/v1/rbac/roles/{role_id}` | DELETE | Administration | ✅ |
| `/api/v1/rbac/permissions` | GET | Administration | ✅ |
| `/api/v1/rbac/permissions` | POST | Administration | ✅ |
| `/api/v1/rbac/users/{user_id}/roles` | GET | Administration | ✅ |
| `/api/v1/rbac/users/{user_id}/roles` | POST | Administration | ✅ |
| `/api/v1/rbac/users/{user_id}/roles/{role_id}` | DELETE | Administration | ✅ |
| `/api/v1/notifications/` | GET | Dashboard | ✅ |
| `/api/v1/notifications/unread` | GET | Dashboard | ✅ |
| `/api/v1/notifications/{notification_id}/read` | PUT | Dashboard | ✅ |
| `/api/v1/notifications/read-all` | PUT | Dashboard | ✅ |
| `/api/v1/notifications/test` | POST | Dashboard | ✅ |
| `/ws/notifications` | WS | Dashboard | ✅ |
| `/ws/scada/live` | WS | ScadaIntegration | ✅ |
| `/ws/cua/confirmation` | WS | CuaMonitor | ✅ |
| `/api/v1/benchmark` | GET | Diagnostics | ✅ |
| `/api/v1/audit/verify` | GET | CuaMonitor | ✅ |
| `/admin/cua/kill-switch` | GET | CuaMonitor | ✅ |
| `/admin/cua/kill-switch/activate` | POST | CuaMonitor | ✅ |
| `/admin/cua/kill-switch/deactivate` | POST | CuaMonitor | ✅ |
| `/admin/cua/rollback` | POST | CuaMonitor | ✅ |
| `/admin/cua/audit-log` | GET | CuaMonitor | ✅ |

### 1.2 Unmapped Endpoints (44 endpoints WITHOUT UI coverage) ⚠️

| API Endpoint | Method | File | Missing UI | Priority |
|-------------|--------|------|-----------|----------|
| `/api/v1/context/retrieve` | POST | api/context_engine.py | No UI page for Context Engine | HIGH |
| `/api/v1/context/impact` | POST | api/context_engine.py | No UI page for Context Engine | HIGH |
| `/api/v1/ml/capabilities` | GET | api/ai_ml.py | No UI page for ML Capabilities | MEDIUM |
| `/api/v1/predict/load` | POST | api/ai_ml.py | No UI page for Load Prediction | MEDIUM |
| `/api/v1/predict/fault` | POST | api/ai_ml.py | No UI page for Fault Prediction | MEDIUM |
| `/api/v1/predict/fault/train` | POST | api/ai_ml.py | No UI page for Fault Training | MEDIUM |
| `/api/v1/predict/anomaly` | POST | api/ai_ml.py | No UI page for Anomaly Detection | MEDIUM |
| `/api/v1/gnn/predict` | POST | api/ai_ml.py | No UI page for GNN Prediction | MEDIUM |
| `/api/v1/rag/query` | POST | api/ai_ml.py | No UI page for RAG Query | MEDIUM |
| `/api/v1/assets` | GET | api/assets.py | No UI page for Asset Library | HIGH |
| `/api/v1/assets/{asset_id}` | GET | api/assets.py | No UI page for Asset Library | HIGH |
| `/api/v1/assets` | POST | api/assets.py | No UI page for Asset Library | HIGH |
| `/api/v1/assets/{asset_id}` | PUT | api/assets.py | No UI page for Asset Library | HIGH |
| `/api/v1/assets/{asset_id}` | DELETE | api/assets.py | No UI page for Asset Library | HIGH |
| `/api/v1/templates` | GET | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/templates` | POST | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/templates/{template_id}` | GET | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/templates/{template_id}` | PUT | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/templates/{template_id}` | DELETE | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/templates/{template_id}/apply` | POST | api/templates.py | No UI page for Templates | MEDIUM |
| `/api/v1/email-digest/config` | GET | api/email_digest.py | No UI page for Email Digest | LOW |
| `/api/v1/email-digest/generate` | POST | api/email_digest.py | No UI page for Email Digest | LOW |
| `/api/v1/email-digest/preview/{email}` | GET | api/email_digest.py | No UI page for Email Digest | LOW |
| `/api/v1/email-digest/schedule/run` | POST | api/email_digest.py | No UI page for Email Digest | LOW |
| `/api/v1/email/webhooks/resend` | POST | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email/webhooks/endpoints` | POST | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email/webhooks/endpoints` | GET | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email/webhooks/endpoints/{endpoint_id}` | DELETE | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email/webhooks/endpoints/{endpoint_id}/test` | POST | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email/webhooks/events` | GET | api/email_webhooks.py | No UI page for Email Webhooks | LOW |
| `/api/v1/email-dashboard/api/stats` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/api/recent` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/api/by-day` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/api/record/{record_id}` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/api/clear` | POST | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/api/config` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/email-dashboard/` | GET | api/email_dashboard.py | No UI page for Email Dashboard | LOW |
| `/api/v1/dual-control/request` | POST | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/api/v1/dual-control/approve/{request_id}` | POST | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/api/v1/dual-control/reject/{request_id}` | POST | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/api/v1/dual-control/pending` | GET | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/api/v1/dual-control/qr/{request_id}` | GET | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/ws/dual-control/approve` | WS | hf-space/app.py | No UI page for Dual Control | HIGH |
| `/api/v1/guards/review` | POST | (guards) | No UI page for Guard Review | MEDIUM |
| `/api/v1/guards/info` | GET | (guards) | No UI page for Guard Info | MEDIUM |

---

## 2. Settings Coverage Analysis

### 2.1 Settings with UI Coverage (Settings.tsx)

| Setting Key | UI Tab | Field Present | Editable |
|------------|--------|--------------|----------|
| ENGINEERING_SERVICE_URL | Engineering Service | ✅ | ✅ |
| ENGINEERING_SERVICE_API_KEY | Engineering Service | ✅ | ✅ |
| ENGINEERING_SERVICE_TIMEOUT_MS | Engineering Service | ✅ | ✅ |
| MASTRA_DB_URL | Database & Cache | ✅ | ✅ |
| DATABASE_URL | Database & Cache | ✅ | ✅ |
| REDIS_URL | Database & Cache | ✅ | ✅ |
| CACHE_SIZE_MB | Database & Cache | ✅ | ✅ |
| CACHE_DEFAULT_TTL | Database & Cache | ✅ | ✅ |
| MAX_WORKERS | Database & Cache | ✅ | ✅ |
| API_KEY_SECRET | Security | ✅ | ✅ |
| JWT_SECRET_KEY | Security | ✅ | ✅ |
| VAULT_ADDR | Security | ✅ | ✅ |
| VAULT_TOKEN | Security | ✅ | ✅ |
| ETAP_LICENSE_PATH | Integration | ✅ | ✅ |
| ETAP_WORKER_URL | Integration | ✅ | ✅ |
| SCADA_SYSTEM_TYPE | Integration | ✅ | ✅ |
| SCADA_SERVER_URL | Integration | ✅ | ✅ |
| SCADA_PROJECT_NAME | Integration | ✅ | ✅ |
| SCADA_SYNC_INTERVAL_SEC | Integration | ✅ | ✅ |
| SCADA_API_KEY | Integration | ✅ | ✅ |
| SMTP_SERVER | Integration | ✅ | ✅ |
| SMTP_PORT | Integration | ✅ | ✅ |
| SMTP_USERNAME | Integration | ✅ | ✅ |
| ALERT_EMAIL_TO | Integration | ✅ | ✅ |
| LANGWATCH_API_KEY | External Services | ✅ | ✅ |
| LANGWATCH_PROJECT | External Services | ✅ | ✅ |
| LANGWATCH_ENDPOINT | External Services | ✅ | ✅ |
| SMITHERY_API_KEY | External Services | ✅ | ✅ |
| SMITHERY_BASE_URL | External Services | ✅ | ✅ |
| HF_TOKEN | External Services | ✅ | ✅ |
| HF_SPACE_NAME | External Services | ✅ | ✅ |
| HF_REPO_URL | External Services | ✅ | ✅ |
| GITHUB_TOKEN | External Services | ✅ | ✅ |
| GITHUB_REPO | External Services | ✅ | ✅ |
| VERCEL_PROJECT_ID | External Services | ✅ | ✅ |
| VERCEL_ACCESS_TOKEN | External Services | ✅ | ✅ |
| HEALTH_CHECK_API_URL | Performance | ✅ | ✅ |
| PROMETHEUS_ENABLED | Performance | ✅ | ✅ |
| PROMETHEUS_PORT | Performance | ✅ | ✅ |
| RATE_LIMIT_REQUESTS_PER_MINUTE | Performance | ✅ | ✅ |
| CIRCUIT_BREAKER_FAILURE_THRESHOLD | Performance | ✅ | ✅ |
| MAX_BODY_SIZE | Performance | ✅ | ✅ |
| ENABLE_ASYNC_EXECUTION | Performance | ✅ | ✅ |
| ENABLE_CACHING | Performance | ✅ | ✅ |
| ENABLE_OBSERVABILITY | Performance | ✅ | ✅ |
| OPENHANDS_ENABLED | Coding Agents | ✅ | ✅ |
| OPENHANDS_URL | Coding Agents | ✅ | ✅ |
| OPENHANDS_WORKSPACE | Coding Agents | ✅ | ✅ |
| OPENCODE_ENABLED | Coding Agents | ✅ | ✅ |
| OPENCODE_URL | Coding Agents | ✅ | ✅ |
| KILOCODE_ENABLED | Coding Agents | ✅ | ✅ |
| KILOCODE_URL | Coding Agents | ✅ | ✅ |
| PROVIDER_OPENAI_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_OPENAI_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_ANTHROPIC_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_ANTHROPIC_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_GEMINI_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_GEMINI_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_DEEPSEEK_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_DEEPSEEK_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_GROQ_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_GROQ_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_COHERE_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_COHERE_MODEL | AI Providers | ✅ | ✅ |
| PROVIDER_HUGGINGFACE_KEY | AI Providers | ✅ | ✅ |
| PROVIDER_HUGGINGFACE_MODEL | AI Providers | ✅ | ✅ |

### 2.2 Settings WITHOUT UI Coverage ⚠️

| Setting Key | Source | Missing UI | Priority |
|------------|--------|-----------|----------|
| FERNET_ENCRYPTION_KEY | .env.example | No UI field | HIGH |
| ENCRYPTION_KEY | .env.example | No UI field | HIGH |
| POSTGRES_DB | .env.example | No UI field | MEDIUM |
| POSTGRES_USER | .env.example | No UI field | MEDIUM |
| POSTGRES_PASSWORD | .env.example | No UI field | MEDIUM |
| LANGFUSE_PUBLIC_KEY | .env.example | No UI field | MEDIUM |
| LANGFUSE_SECRET_KEY | .env.example | No UI field | MEDIUM |
| LANGFUSE_BASE_URL | .env.example | No UI field | MEDIUM |
| LANGFUSE_DEFAULT_MODEL | .env.example | No UI field | MEDIUM |
| LLM_MAX_INPUT_CHARS | .env.example | No UI field | MEDIUM |
| LLM_ALLOW_UNKNOWN_MODELS | .env.example | No UI field | MEDIUM |
| LLM_REQUIRE_AGENT_TAG | .env.example | No UI field | MEDIUM |
| LLM_APPROVED_MODELS | .env.example | No UI field | MEDIUM |
| LANGFUSE_ALERT_WEBHOOK_URL | .env.example | No UI field | LOW |
| LANGFUSE_SAFETY_PATHS | .env.example | No UI field | LOW |
| LANGFUSE_OVERRIDE_MODE | .env.example | No UI field | LOW |
| SUPABASE_URL | .env.example | No UI field | MEDIUM |
| SUPABASE_ANON_KEY | .env.example | No UI field | MEDIUM |
| SUPABASE_SERVICE_ROLE_KEY | .env.example | No UI field | MEDIUM |
| SUPABASE_AUTH_ENABLED | .env.example | No UI field | MEDIUM |
| SIEM_ENABLED | .env.example | No UI field | HIGH |
| SIEM_HOST | .env.example | No UI field | HIGH |
| SIEM_PORT | .env.example | No UI field | HIGH |
| SIEM_PROTOCOL | .env.example | No UI field | HIGH |
| SIEM_LOG_FILE | .env.example | No UI field | HIGH |
| CLOUDFLARE_ORIGIN_SECRET | .env.example | No UI field | MEDIUM |
| CF_BLOCKED_COUNTRIES | .env.example | No UI field | MEDIUM |
| CF_ORIGIN_RATE_LIMIT | .env.example | No UI field | MEDIUM |
| AKAMAI_ORIGIN_SECRET | .env.example | No UI field | MEDIUM |
| R2_ACCOUNT_ID | .env.example | No UI field | MEDIUM |
| R2_ACCESS_KEY_ID | .env.example | No UI field | MEDIUM |
| R2_SECRET_ACCESS_KEY | .env.example | No UI field | MEDIUM |
| R2_BUCKET_NAME | .env.example | No UI field | MEDIUM |
| RESEND_API_KEY | .env.example | No UI field | MEDIUM |
| RESEND_FROM_EMAIL | .env.example | No UI field | MEDIUM |
| RESEND_FROM_NAME | .env.example | No UI field | MEDIUM |
| RESEND_RATE_LIMIT_MAX | .env.example | No UI field | LOW |
| RESEND_LOGIN_ALERTS_ENABLED | .env.example | No UI field | LOW |
| RESEND_LOCKOUT_ALERTS_ENABLED | .env.example | No UI field | LOW |
| RESEND_WELCOME_EMAIL_ENABLED | .env.example | No UI field | LOW |
| RESEND_NOTIFICATION_EMAILS_ENABLED | .env.example | No UI field | LOW |
| EMAIL_BRAND_NAME | .env.example | No UI field | LOW |
| EMAIL_BRAND_TAGLINE | .env.example | No UI field | LOW |
| EMAIL_SUPPORT_ADDRESS | .env.example | No UI field | LOW |
| EMAIL_APP_URL | .env.example | No UI field | LOW |
| EMAIL_BRAND_PRIMARY | .env.example | No UI field | LOW |
| EMAIL_BRAND_SECONDARY | .env.example | No UI field | LOW |
| EMAIL_BRAND_ACCENT | .env.example | No UI field | LOW |
| OTP_TTL_SECONDS | .env.example | No UI field | LOW |
| OTP_MAX_ATTEMPTS | .env.example | No UI field | LOW |
| OTP_ISSUE_COOLDOWN_SEC | .env.example | No UI field | LOW |
| MAGIC_LINK_TTL_SECONDS | .env.example | No UI field | LOW |
| EMAIL_DIGEST_ENABLED | .env.example | No UI field | LOW |
| EMAIL_DIGEST_SCHEDULE_DAILY | .env.example | No UI field | LOW |
| EMAIL_DIGEST_SCHEDULE_WEEKLY | .env.example | No UI field | LOW |
| EMAIL_WEBHOOK_SECRET | .env.example | No UI field | LOW |
| EMAIL_DASHBOARD_ENABLED | .env.example | No UI field | LOW |
| EMAIL_DASHBOARD_RETENTION_DAYS | .env.example | No UI field | LOW |
| SONAR_TOKEN | .env.example | No UI field | LOW |
| SONAR_PROJECT_KEY | .env.example | No UI field | LOW |
| NODE_TIMEOUT_MS | .env.example | No UI field | LOW |
| NODE_MEMORY_LIMIT_MB | .env.example | No UI field | LOW |
| NODE_MAX_CODE_LENGTH | .env.example | No UI field | LOW |
| NODE_MAX_OUTPUT_LENGTH | .env.example | No UI field | LOW |
| QDRANT_HOST | .env.example | No UI field | MEDIUM |
| QDRANT_PORT | .env.example | No UI field | MEDIUM |
| NEO4J_URI | .env.example | No UI field | MEDIUM |
| NEO4J_USER | .env.example | No UI field | MEDIUM |
| GRAFANA_PASSWORD | .env.example | No UI field | LOW |
| GRAFANA_ADMIN_PASSWORD | .env.example | No UI field | LOW |
| ENGINEERING_SERVICE_CORS_ORIGINS | .env.example | No UI field | MEDIUM |
| ENGINEERING_SERVICE_RATE_LIMIT_WINDOW | .env.example | No UI field | MEDIUM |
| ENGINEERING_SERVICE_RATE_LIMIT_MAX | .env.example | No UI field | MEDIUM |
| ENGINEERING_SERVICE_REQUEST_TIMEOUT | .env.example | No UI field | MEDIUM |
| ENGINEERING_SERVICE_MAX_BODY_SIZE | .env.example | No UI field | MEDIUM |
| ENGINEERING_SERVICE_TRUSTED_PROXIES | .env.example | No UI field | MEDIUM |
| HSTS_MAX_AGE | .env.example | No UI field | MEDIUM |
| PRIVACY_MODE | .env.example | No UI field | MEDIUM |
| SMTP_PASSWORD | .env.example | No UI field | HIGH |

---

## 3. Agent/Study Type → UI Mapping

### 3.1 Study Types with UI Coverage

| Study Type | API Endpoint | UI Page | Status |
|-----------|-------------|---------|--------|
| load_flow | POST /api/v1/studies/run | StudyRun | ✅ |
| short_circuit | POST /api/v1/studies/run | StudyRun | ✅ |
| harmonic_analysis | POST /api/v1/studies/run | StudyRun | ✅ |
| optimal_power_flow | POST /api/v1/studies/run | StudyRun | ✅ |
| protection_coordination | POST /api/v1/studies/run | StudyRun | ✅ |
| motor_starting | POST /api/v1/studies/run | StudyRun | ✅ |
| transient_stability | POST /api/v1/studies/run | StudyRun | ✅ |
| arc_flash | POST /api/v1/studies/run | StudyRun | ✅ |
| cable_sizing | POST /api/v1/studies/run | StudyRun | ✅ |
| earth_grid | POST /api/v1/studies/run | StudyRun | ✅ |
| renewable_integration | POST /api/v1/studies/run | StudyRun | ✅ |
| battery_storage | POST /api/v1/studies/run | StudyRun | ✅ |
| scada | POST /api/v1/studies/run | StudyRun | ✅ |
| digital_twin | POST /api/v1/studies/run | StudyRun | ✅ |
| etap_expert | POST /api/v1/agents/etap-expert/chat | AIAssistant | ✅ |
| etap_gui | POST /api/v1/agents/etap-gui/chat | AIAssistant | ✅ |

### 3.2 Python Agents with UI Coverage

| Agent Class | StudyType | UI Page | Status |
|------------|-----------|---------|--------|
| LoadFlowAgent | LOAD_FLOW | StudyRun | ✅ |
| ShortCircuitAgent | SHORT_CIRCUIT | StudyRun | ✅ |
| HarmonicAnalysisAgent | HARMONIC_ANALYSIS | StudyRun | ✅ |
| OptimalPowerFlowAgent | OPTIMAL_POWER_FLOW | StudyRun | ✅ |
| ProtectionCoordinationAgent | PROTECTION_COORDINATION | StudyRun | ✅ |
| ETAPExecutionAgent | (COM) | EtapIntegration | ✅ |
| ValidationAgent | (validation) | Studies | ✅ |
| ReportGenerationAgent | (reporting) | Reports | ✅ |
| StabilityAgent | TRANSIENT_STABILITY | StudyRun | ✅ |
| CableSizingAgent | CABLE_SIZING | StudyRun | ✅ |
| EarthGridAgent | EARTH_GRID | StudyRun | ✅ |
| RenewableAgent | RENEWABLE_INTEGRATION | StudyRun | ✅ |
| BatteryStorageAgent | BATTERY_STORAGE | StudyRun | ✅ |
| SCADAAgent | SCADA | ScadaIntegration | ✅ |
| ETAPExpertAgent | ETAP_EXPERT | AIAssistant | ✅ |

---

## 4. Navigation Coverage

### 4.1 Navigation Items Present (Sidebar.tsx)

| Route | Label | Section | Status |
|-------|-------|---------|--------|
| /dashboard | Dashboard | (top) | ✅ |
| /studies | Studies | (top) | ✅ |
| /assistant | AI Assistant | (top) | ✅ |
| /projects | Projects | engineering | ✅ |
| /grid-editor | Grid Editor | engineering | ✅ |
| /asset-management | Asset Management | engineering | ✅ |
| /etap | ETAP Integration | integration | ✅ |
| /gis | GIS Integration | integration | ✅ |
| /scada | SCADA Integration | integration | ✅ |
| /digital-twin | Digital Twin | integration | ✅ |
| /reports | Reports | (top) | ✅ |
| /data-import | Data Import | system | ✅ |
| /data-export | Data Export | system | ✅ |
| /settings | Settings | system | ✅ |
| /admin | Administration | system | ✅ |
| /admin/cua-monitor | CUA Monitor | system | ✅ |
| /diagnostics | Diagnostics | system | ✅ |
| /code-guard | Code Guard | system | ✅ |
| /logs | Logs | system | ✅ |

### 4.2 Missing Navigation Items ⚠️

| Route | Feature | Reason | Priority |
|-------|---------|--------|----------|
| /context-engine | Context Engine | API exists, no page | HIGH |
| /ml-capabilities | ML/AI Capabilities | API exists, no page | MEDIUM |
| /templates | Templates | API exists, no page | MEDIUM |
| /email-dashboard | Email Dashboard | API exists, no page | LOW |
| /dual-control | Dual Control | API exists, no page | HIGH |
| /guard-review | Code Guard Review | API exists, no page | MEDIUM |

---

## 5. CRUD Completeness Analysis

### 5.1 Entities with Full CRUD Coverage

| Entity | Create | Read | Update | Delete | Search | UI Page |
|--------|--------|------|--------|--------|--------|---------|
| Projects | ✅ | ✅ | ✅ | ✅ | ✅ | Projects |
| Equipment | ✅ | ✅ | ✅ | ✅ | ✅ | AssetManagement |
| Equipment Categories | ✅ | ✅ | ✅ | ✅ | ❌ | AssetManagement |
| Users | ✅ | ✅ | ✅ | ✅ | ❌ | Administration |
| Roles (RBAC) | ✅ | ✅ | ✅ | ✅ | ❌ | Administration |
| Permissions | ✅ | ✅ | ✅ | ❌ | ❌ | Administration |
| API Keys (Providers) | ✅ | ✅ | ✅ | ✅ | ❌ | Settings |
| Study Versions | ✅ | ✅ | ✅ | ✅ | ❌ | Studies |
| Templates | ❌ | ❌ | ❌ | ❌ | ❌ | **MISSING** |
| Assets | ❌ | ❌ | ❌ | ❌ | ❌ | **MISSING** |
| Notifications | ❌ | ✅ | ✅ | ❌ | ❌ | Dashboard |
| Email Webhooks | ❌ | ❌ | ❌ | ❌ | ❌ | **MISSING** |
| Email Digest Config | ❌ | ❌ | ❌ | ❌ | ❌ | **MISSING** |
| Dual Control Requests | ❌ | ❌ | ❌ | ❌ | ❌ | **MISSING** |

### 5.2 Missing CRUD Operations ⚠️

| Entity | Missing Operations | Priority |
|--------|-------------------|----------|
| Templates | Full CRUD (Create, Read, Update, Delete, Apply) | HIGH |
| Assets | Full CRUD (Create, Read, Update, Delete) | HIGH |
| Email Webhooks | Full CRUD (Create, Read, Update, Delete, Test) | MEDIUM |
| Email Digest Config | Read, Update | MEDIUM |
| Dual Control Requests | Create, Approve, Reject, List, QR | HIGH |
| Equipment Categories | Search/Filter | LOW |
| Users | Search/Filter | LOW |
| Roles | Search/Filter | LOW |
| Permissions | Delete | LOW |
| API Keys | Search/Filter | LOW |
| Study Versions | Search/Filter | LOW |

---

## 6. Hidden Feature Detection

### 6.1 Unused/Orphan Backend Features ⚠️

| Feature | Location | Current Accessibility | Missing UI | Priority |
|---------|----------|---------------------|-----------|----------|
| Context Engine | api/context_engine.py | API only | No page, no nav | HIGH |
| ML Predictions | api/ai_ml.py | API only | No page, no nav | MEDIUM |
| GNN Predictions | api/ai_ml.py | API only | No page, no nav | MEDIUM |
| RAG Query | api/ai_ml.py | API only | No page, no nav | MEDIUM |
| Asset Library | api/assets.py | API only | No page, no nav | HIGH |
| Templates | api/templates.py | API only | No page, no nav | MEDIUM |
| Email Digest | api/email_digest.py | API only | No page, no nav | LOW |
| Email Webhooks | api/email_webhooks.py | API only | No page, no nav | LOW |
| Email Dashboard | api/email_dashboard.py | API only | No page, no nav | LOW |
| Dual Control | hf-space/app.py | API only | No page, no nav | HIGH |
| Guard Review | (guards module) | API only | No page, no nav | MEDIUM |
| SIEM Configuration | .env.example | Env only | No settings UI | HIGH |
| Supabase Integration | .env.example | Env only | No settings UI | MEDIUM |
| Cloudflare R2 Storage | .env.example | Env only | No settings UI | MEDIUM |
| Resend Email | .env.example | Env only | No settings UI | MEDIUM |
| Langfuse | .env.example | Env only | No settings UI | MEDIUM |
| Qdrant Vector DB | .env.example | Env only | No settings UI | MEDIUM |
| Neo4j Graph DB | .env.example | Env only | No settings UI | MEDIUM |
| Vault Secrets | .env.example | Env only | No settings UI | MEDIUM |
| SMTP Email Alerts | .env.example | Env only | No settings UI | MEDIUM |
| Cloudflare Edge Protection | .env.example | Env only | No settings UI | MEDIUM |
| Akamai Edge Protection | .env.example | Env only | No settings UI | MEDIUM |
| Node.js Sandbox | .env.example | Env only | No settings UI | LOW |
| SonarCloud | .env.example | Env only | No settings UI | LOW |

### 6.2 Dead UI Elements (No Backend Connection)

| UI Element | Location | Backend Connection | Status |
|-----------|----------|-------------------|--------|
| All sidebar nav items | Sidebar.tsx | Connected to routes | ✅ No dead UI |
| All settings tabs | Settings.tsx | Connected to API | ✅ No dead UI |
| All study types | StudyRun.tsx | Connected to API | ✅ No dead UI |
| All CRUD operations | Projects.tsx | Connected to API | ✅ No dead UI |
| All CRUD operations | AssetManagement.tsx | Connected to API | ✅ No dead UI |

**No dead UI elements detected.** All existing UI components are connected to backend APIs.

---

## 7. Configuration Drift Detection

### 7.1 Settings with Drift ⚠️

| Setting | Default (.env.example) | UI Default (Settings.tsx) | Drift |
|---------|----------------------|--------------------------|-------|
| MAX_BODY_SIZE | 100000 | 100000 | ✅ Match |
| RATE_LIMIT_MAX | 100 | 60 (RATE_LIMIT_REQUESTS_PER_MINUTE) | ⚠️ Drift |
| RATE_LIMIT_WINDOW | 60 | Not in UI | ⚠️ Missing |
| ENGINEERING_SERVICE_CORS_ORIGINS | http://localhost:3000 | Not in UI | ⚠️ Missing |
| ENGINEERING_SERVICE_REQUEST_TIMEOUT | 120 (in routes.py) | Not in UI | ⚠️ Missing |
| ENGINEERING_SERVICE_MAX_BODY_SIZE | 52_428_800 (in routes.py) | Not in UI | ⚠️ Missing |
| ENGINEERING_SERVICE_TRUSTED_PROXIES | (in routes.py) | Not in UI | ⚠️ Missing |
| HSTS_MAX_AGE | (in routes.py) | Not in UI | ⚠️ Missing |
| PRIVACY_MODE | (in routes.py) | Not in UI | ⚠️ Missing |

---

## 8. High-Priority Missing UI Items

### 8.1 Must-Fix (Critical) ⚠️

| # | Feature | Reason | Recommended UI |
|---|---------|--------|---------------|
| 1 | **Context Engine** | Full API exists (retrieve + impact analysis) | New page: `/context-engine` |
| 2 | **Dual Control** | Life-safety feature, API exists (request/approve/reject/QR) | New page: `/dual-control` |
| 3 | **Asset Library** | Full CRUD API exists | New page: `/asset-library` |
| 4 | **Templates** | Full CRUD API exists | New page: `/templates` |
| 5 | **SIEM Configuration** | Security-critical, env-only | Add to Settings > Security |
| 6 | **SMTP Password** | Required for email alerts, env-only | Add to Settings > Integration |
| 7 | **Fernet/Encryption Key** | Security-critical, env-only | Add to Settings > Security |
| 8 | **Context Engine Settings** | No UI for configuration | Add to Settings > Integration |

### 8.2 Should-Fix (Medium) ⚠️

| # | Feature | Reason | Recommended UI |
|---|---------|--------|---------------|
| 9 | ML/AI Capabilities | API exists | New page: `/ml-capabilities` |
| 10 | Load/Fault/Anomaly Prediction | API exists | Add to AIAssistant or new page |
| 11 | GNN Prediction | API exists | Add to AIAssistant |
| 12 | RAG Query | API exists | Add to AIAssistant |
| 13 | Guard Review | API exists | Add to CodeGuard page |
| 14 | Supabase Configuration | Env-only | Add to Settings > Database |
| 15 | Qdrant/Neo4j Configuration | Env-only | Add to Settings > Database |
| 16 | Cloudflare R2 Storage | Env-only | Add to Settings > External Services |
| 17 | Resend Email Configuration | Env-only | Add to Settings > Integration |
| 18 | Langfuse Configuration | Env-only | Add to Settings > External Services |
| 19 | Vault Configuration | Env-only | Add to Settings > Security |
| 20 | Cloudflare/Akamai Edge Protection | Env-only | Add to Settings > Security |

### 8.3 Nice-to-Fix (Low) ⚠️

| # | Feature | Reason | Recommended UI |
|---|---------|--------|---------------|
| 21 | Email Dashboard | API exists | New page: `/email-dashboard` |
| 22 | Email Webhooks | API exists | Add to Settings > Integration |
| 23 | Email Digest | API exists | Add to Settings > Integration |
| 24 | Node.js Sandbox Config | Env-only | Add to Settings > Performance |
| 25 | SonarCloud Config | Env-only | Add to Settings > External Services |
| 26 | Grafana Config | Env-only | Add to Settings > External Services |
| 27 | Email Brand Config | Env-only | Add to Settings > Integration |
| 28 | OTP/Magic Link Config | Env-only | Add to Settings > Security |

---

## 9. UI Completeness Score Calculation

```
Total Backend Features (API Endpoints):    139
Total UI Features (Pages + Components):    22
Mapped Features:                           95
Hidden Features (No UI):                   44
Missing Pages:                             6
Missing Buttons/Dialogs:                   12
Missing Settings:                          68
Unused APIs:                               44
Dead Buttons:                              0
Orphan Services:                           0

Coverage Percentage: 95/139 = 68.3%
Target: 100%
Gap: 31.7%
```

---

## 10. Recommendations

### Immediate Actions (Priority: Critical)
1. Create `/context-engine` page for Context Engine API
2. Create `/dual-control` page for Dual Control life-safety feature
3. Create `/asset-library` page for Asset Library CRUD
4. Create `/templates` page for Templates CRUD
5. Add SIEM configuration to Settings > Security tab
6. Add SMTP Password to Settings > Integration tab
7. Add Encryption Keys to Settings > Security tab

### Short-term Actions (Priority: Medium)
8. Create `/ml-capabilities` page for ML/AI features
9. Add Guard Review UI to CodeGuard page
10. Add Supabase, Qdrant, Neo4j configs to Settings
11. Add Cloudflare R2, Resend, Langfuse configs to Settings
12. Add Vault, Edge Protection configs to Settings

### Long-term Actions (Priority: Low)
13. Create `/email-dashboard` page
14. Add Email Webhooks, Digest configs to Settings
15. Add Node.js Sandbox, SonarCloud, Grafana configs to Settings
16. Add Email Brand, OTP, Magic Link configs to Settings

---

## 11. Verification

- [x] Every backend feature identified
- [x] Every API endpoint catalogued
- [x] Every UI page/component inventoried
- [x] Backend ↔ UI mapping completed
- [x] Settings coverage analyzed
- [x] Navigation coverage verified
- [x] CRUD completeness validated
- [x] Hidden features detected
- [x] Dead UI elements checked
- [x] Configuration drift detected
- [x] Coverage score calculated
- [x] Report generated

**Audit Status: INCOMPLETE** — 31.7% of backend features lack UI coverage.
**Target: 100%** — Requires implementation of missing UI components.