# Rollback Procedure for AhmedETAP v2.1.0

This document defines the emergency rollback protocols for the **v2.1.0** production deployment of the AhmedETAP platform.

---

## 1. Rollback Criteria & Triggers

Initiate this rollback procedure immediately upon any of the following conditions:
- **P0 Alert**: SCADA telemetry failure or unexpected systemwide HTTP 500 rate > 2% over 5 minutes.
- **Data Integrity Hazard**: Any migration inconsistency, unhandled database locks/deadlocks on `study_versions`.
- **Fatal Container CrashLoop**: Inability of `ahmetap/api:v2.1.0` or `ahmetap/ui:v2.1.0` to pass container health checks (`/readyz`).
- **Authorization Bypass**: Any regression in fail-closed RBAC or Maker-Checker guards.

---

## 2. Emergency Incident Roles

| Role | Responsibility | Contact |
|---|---|---|
| **Incident Commander (IC)** | Declares rollback, oversees execution | On-Call Lead Engineer |
| **Database Administrator** | Executes migration downgrades & backups | DB Reliability Engineer |
| **Platform Ops Engineer** | Handles container redeployment & traffic rerouting | DevOps Engineer |
| **QA / Validation Lead** | Runs post-rollback verification suite | Test Lead |

---

## 3. Quick Container Rollback (< 5 minutes)

When the issue is code-level (frontend UI or backend logic) and does not require reversing database schema changes:

```bash
# Step 1: Re-tag production images to previous stable release (v2.0.9)
docker tag ahmetap/api:v2.0.9 ahmetap/api:latest
docker tag ahmetap/ui:v2.0.9 ahmetap/ui:latest

# Step 2: Force recreate services with previous images
docker compose -f docker-compose.yml up -d --force-recreate engineering-service ui

# Step 3: Verify container health status
docker compose ps
curl -fsS https://api.prod.ahmetap.com/readyz
curl -fsS https://app.prod.ahmetap.com/healthz
```

---

## 4. Database Migration Rollback

If the issue stems from database schema modifications introduced in v2.1.0 (`011_add_hardening_tables.py`):

```bash
# Step 1: Pre-rollback snapshot (Safety first - preserve any newly written data)
pg_dump -h $DB_HOST -U $DB_USER -d etap_platform -Fc -f /tmp/etap_rollback_snapshot_$(date +%Y%m%d%H%M%S).dump

# Step 2: Downgrade Alembic to v2.0.9 schema head (010_add_results_store)
alembic downgrade 010_add_results_store

# Step 3: Verify schema state
alembic current
# Expected output: 010_add_results_store (head)

# Step 4: Verify schema compatibility
psql $DATABASE_URL -c "\dt"
```

> [!NOTE]
> `011_add_hardening_tables.py` drops `project_solver_parameters`, `study_versions`, and `export_history` cleanly upon downgrade without touching pre-existing tables (`users`, `projects`, `results`, `roles`).

---

## 5. Post-Rollback Verification Checklist

Immediately after rollback, the QA / Validation Lead must verify:

- [ ] **Health Endpoints**: `GET /healthz` and `GET /readyz` return HTTP 200 OK.
- [ ] **Authentication & Sessions**: Users can log in, JWT validation succeeds.
- [ ] **Projects API**: `GET /api/v1/projects` returns active project list.
- [ ] **Study Execution**: Basic load flow calculation runs successfully.
- [ ] **Web UI Accessibility**: SPA loads cleanly without missing bundle assets or console errors.
- [ ] **SCADA Telemetry**: Returns expected baseline telemetry or status.
- [ ] **Monitoring Reset**: All firing Prometheus alerts auto-resolve.

---

## 6. Post-Mortem & Escalation

1. Notify `#incident-alerts` Slack channel that rollback is complete and platform is stable.
2. Preserve all container logs:
   ```bash
   docker logs ahmetap-api > /var/log/incident_v2.1.0_api.log
   docker logs ahmetap-ui > /var/log/incident_v2.1.0_ui.log
   ```
3. Schedule post-mortem review within 24 hours to address root cause before rescheduling v2.1.0 release.
