# AhmedETAP — Production Launch Checklist

> **Version:** v2.1.0
> **Last Updated:** 2026-03-05
> **Status:** Pre-Launch

---

## Table of Contents

1. [Pre-Launch Security](#1-pre-launch-security)
2. [Pre-Launch Testing](#2-pre-launch-testing)
3. [Pre-Launch Infrastructure](#3-pre-launch-infrastructure)
4. [Pre-Launch Configuration](#4-pre-launch-configuration)
5. [Launch Day](#5-launch-day)
6. [Post-Launch](#6-post-launch)
7. [Sign-off](#7-sign-off)

---

## 1. Pre-Launch Security

### CORS & API Security

- [ ] Verify CORS origins in `.env` are restricted to production domains only (no `*` wildcard)
- [ ] Confirm `ENGINEERING_SERVICE_CORS_ORIGINS` does not include `localhost` or `127.0.0.1`
- [ ] Validate all API endpoints require authentication except `/health` and `/docs`
- [ ] Confirm WebSocket endpoint `/ws/scada/live` enforces JWT authentication
- [ ] Verify API key validation uses constant-time comparison (no timing attacks)
- [ ] Test that rate limiting is active and enforced across all endpoints
- [ ] Confirm rate limiting is Redis-backed (not in-memory) for multi-instance deployments

### Credentials & Secrets

- [ ] Run `scripts/security_scan.py` — must pass with zero errors
- [ ] Verify no hardcoded credentials in `docker-compose.yml` or `docker-compose.*.yml`
- [ ] Run: `rg -i "password123|admin123|hardcoded|CHANGE-ME" docker-compose*.yml helm/` — must return no matches
- [ ] Confirm all secrets are injected via environment variables or Kubernetes secrets
- [ ] Verify `ENGINEERING_SERVICE_API_KEY` in `helm/etap-ai/values.yaml` is NOT set to `CHANGE-ME-IN-PRODUCTION`
- [ ] Rotate all API keys and secrets used during development (OpenAI, Anthropic, Google, NVIDIA, GitHub, HF, LangWatch, Smithery)
- [ ] Confirm `.env` is in `.gitignore` and no `.env` file is committed
- [ ] Verify JWT secret key is at least 32 characters of cryptographic randomness
- [ ] Verify Fernet encryption key is a valid Fernet key
- [ ] Confirm PostgreSQL password meets minimum strength requirements (12+ characters, mixed case, digits, symbols)

### Authentication & Authorization

- [ ] Verify JWT token expiration is configured (access token ≤ 15 min, refresh token ≤ 24 hr)
- [ ] Test RBAC enforcement: verify each of the 5 roles can only access authorized endpoints
- [ ] Confirm MFA (TOTP) enrollment and verification works end-to-end
- [ ] Verify WebAuthn is rejected when the `webauthn` library is not installed (no insecure fallback)
- [ ] Confirm Redis-backed token blacklisting is operational (test: invalidate token, verify subsequent request is rejected)
- [ ] Test session management: verify sessions expire after inactivity timeout

### Infrastructure Security

- [ ] Verify Helm chart `securityContext` has `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`
- [ ] Verify Helm chart `podSecurityContext` has `runAsUser: 1000`, `runAsGroup: 1000`, `seccompProfile: RuntimeDefault`
- [ ] Confirm all Kubernetes capabilities are dropped (`capabilities.drop: ALL`)
- [ ] Verify network policies are enabled (`networkPolicy.enabled: true` in `values.yaml`)
- [ ] Confirm Redis authentication is enabled in production Helm values
- [ ] Verify PostgreSQL is not exposed on a public port (no `NodePort` or `LoadBalancer`)
- [ ] Confirm container images are pulled from GHCR with specific tags (no `:latest` in production)
- [ ] Verify TLS certificates are configured for Ingress (uncomment and populate TLS section)

### Network & Transport

- [ ] Confirm HTTPS enforcement in nginx configuration (HTTP → HTTPS redirect)
- [ ] Verify security headers are set: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`
- [ ] Verify no sensitive data is logged (passwords, tokens, API keys filtered in structured logging)
- [ ] Confirm audit log rotation is configured for Docker volumes
- [ ] Verify WAF rules are in place (if deploying behind a WAF)

---

## 2. Pre-Launch Testing

### Unit Tests

- [ ] Run `pytest tests/ -m unit --tb=short` — must pass with zero failures
- [ ] Verify unit test coverage ≥ 80% for core modules (`agents`, `core_model`, `engine`, `load_flow`, `fault_analysis`, `coordination`, `security`)
- [ ] Confirm all property-based tests (Hypothesis) pass: `pytest tests/property_based/`
- [ ] Verify no skipped tests without valid reason markers

### Integration Tests

- [ ] Run `pytest tests/ -m integration --tb=short` — must pass with zero failures
- [ ] Verify API endpoint integration tests pass: `pytest tests/integration/test_api_endpoints.py`
- [ ] Confirm security E2E tests pass: `pytest tests/test_security_e2e.py`
- [ ] Test SCADA WebSocket integration: `pytest tests/test_scada_websocket.py`
- [ ] Verify Celery task integration: `pytest tests/test_celery_tasks.py`
- [ ] Confirm database migration tests pass: `pytest tests/test_core_database.py`

### Scenario & Domain Tests

- [ ] Run all scenario tests: `pytest tests/scenarios/ -v` — all must pass
- [ ] Verify load flow scenario accuracy against IEEE benchmarks
- [ ] Verify short circuit scenario accuracy against IEC 60909 test cases
- [ ] Verify arc flash scenario accuracy against IEEE 1584-2018 test cases
- [ ] Verify harmonic analysis scenario accuracy against IEEE 519-2022 test cases
- [ ] Verify OPF scenario converges with expected objective values
- [ ] Run regression test suite: `pytest tests/regression/`

### End-to-End Tests

- [ ] Run E2E smoke test: `pytest tests/e2e_smoke_test.py`
- [ ] Verify full study lifecycle: create project → configure study → run → view results → export report
- [ ] Verify authentication flow: register → login → MFA setup → MFA verify → session active
- [ ] Verify AI agent chat: send query → receive response → validate study creation
- [ ] Verify GIS integration: load spatial data → validate topology → display on map
- [ ] Verify Digital Twin sync: import model → sync → validate state

### Load & Performance Tests

- [ ] Run k6 load test: `k6 run k6-load-test.js` — p95 response time < 500 ms
- [ ] Run Locust load test: `locust -f locustfile.py` — verify system handles 100 concurrent users
- [ ] Verify no memory leaks under sustained load (monitor for 30 min)
- [ ] Confirm Celery worker queue does not back up under 10x normal load
- [ ] Verify database connection pool does not exhaust under load
- [ ] Run stress test: `npx ts-node tests/stress/stress-test.ts` — verify graceful degradation

### Chaos & Resilience Tests

- [ ] Run chaos test: `npx ts-node tests/chaos/chaos-test.ts` — verify recovery
- [ ] Simulate Redis failure — verify application degrades gracefully (not crashes)
- [ ] Simulate PostgreSQL failure — verify connection retry and recovery
- [ ] Simulate ETAP COM disconnection — verify error recovery agent handles gracefully
- [ ] Verify circuit breaker triggers correctly under downstream failures

---

## 3. Pre-Launch Infrastructure

### Docker

- [ ] Build production image: `docker build -f Dockerfile.engineering-service -t ahmedetap:2.1.0 .` — must succeed
- [ ] Verify image runs with non-root user (UID 1000)
- [ ] Verify image size is reasonable (< 1 GB compressed)
- [ ] Test multi-arch build: `docker buildx build --platform linux/amd64,linux/arm64`
- [ ] Verify no sensitive files are included in the Docker image (check `.dockerignore`)
- [ ] Run full stack locally: `docker-compose up -d` and verify all services start
- [ ] Verify health endpoint responds: `curl http://localhost:8000/health` returns `200`
- [ ] Verify API docs are accessible: `curl http://localhost:8000/docs` returns `200`

### Kubernetes / Helm

- [ ] Verify Helm chart lints cleanly: `helm lint helm/etap-ai/`
- [ ] Dry-run Helm install: `helm install --dry-run etap-ai helm/etap-ai/ -n etap-prod`
- [ ] Verify all Kubernetes resources are created (deployment, service, configmap, secret, networkpolicy, ingress)
- [ ] Confirm resource limits and requests are set for all containers
- [ ] Verify liveness and readiness probes are configured
- [ ] Confirm pod disruption budgets are configured for zero-downtime updates
- [ ] Test Helm upgrade: `helm upgrade etap-ai helm/etap-ai/ -n etap-prod`
- [ ] Verify horizontal pod autoscaling (HPA) is configured or planned

### Terraform

- [ ] Verify Terraform plan for staging: `terraform plan -var-file=environments/staging/terraform.tfvars`
- [ ] Verify Terraform plan for production: `terraform plan -var-file=environments/prod/terraform.tfvars`
- [ ] Confirm remote state backend is configured (not local)
- [ ] Verify state file encryption is enabled
- [ ] Confirm all output values are correct (API endpoint, database endpoint, etc.)

### Monitoring & Alerting

- [ ] Verify Prometheus is scraping metrics from all services
- [ ] Verify Grafana dashboards are provisioned (platform, engineering service, Jaeger traces)
- [ ] Confirm alerting rules are configured for: high error rate, high latency, pod restarts, disk usage, memory pressure
- [ ] Verify Alertmanager is routing alerts to correct channels (email, Slack, PagerDuty)
- [ ] Test alert firing: manually trigger a test alert and confirm notification is received
- [ ] Verify Loki is aggregating logs from all services
- [ ] Confirm Promtail is shipping logs correctly
- [ ] Verify Jaeger tracing is operational (trace propagation across services)

### Backup & Recovery

- [ ] Verify PostgreSQL automated backup is configured (`scripts/backup/postgres_backup.sh`)
- [ ] Test backup restoration: restore from backup and verify data integrity
- [ ] Verify Redis persistence is enabled (`appendonly yes`)
- [ ] Confirm backup retention policy is configured (minimum 30 days)
- [ ] Test disaster recovery procedure: full stack recovery from backup
- [ ] Document RPO (Recovery Point Objective) and RTO (Recovery Time Objective)

---

## 4. Pre-Launch Configuration

### Environment Variables

- [ ] Verify `.env.example` contains all required variables with documentation
- [ ] Confirm production `.env` is populated with real values (no placeholders)
- [ ] Verify all secrets are stored in Kubernetes Secrets or HashiCorp Vault (not ConfigMaps)
- [ ] Confirm `ENVIRONMENT=production` is set
- [ ] Verify `PRIVACY_MODE=true` is set for production
- [ ] Confirm `LOG_LEVEL=INFO` is set (not `DEBUG` in production)
- [ ] Verify `DATABASE_URL` points to PostgreSQL (not SQLite) in production
- [ ] Confirm `REDIS_URL` points to production Redis instance

### API Keys & External Services

- [ ] Verify OpenAI API key is valid and has sufficient quota
- [ ] Verify Anthropic API key is valid and has sufficient quota
- [ ] Verify Google API key is valid (if Gemini models are used)
- [ ] Verify NVIDIA API key is valid (if NIM models are used)
- [ ] Confirm Hugging Face token has write access (for Spaces deployment)
- [ ] Verify LangWatch API key is valid (for LLM observability)
- [ ] Verify Smithery API key is valid (for MCP integration)
- [ ] Confirm GitHub token has correct repository scopes
- [ ] Test each external service connectivity from the production environment

### Database

- [ ] Run Alembic migrations: `alembic upgrade head` — must succeed
- [ ] Verify all migration versions are applied correctly
- [ ] Confirm database indexes and constraints are created (migration 002)
- [ ] Verify MFA credentials table exists (migration 003)
- [ ] Confirm study results composite index exists (migration 004)
- [ ] Verify study jobs table exists (migration 005)
- [ ] Test database connection pool under load

### Email & Notifications (Optional)

- [ ] Verify SMTP configuration is correct (host, port, username, password)
- [ ] Send test email to verify delivery
- [ ] Configure alert email recipients
- [ ] Verify email templates render correctly

---

## 5. Launch Day

### Pre-Launch Window (T-2 hours)

- [ ] Confirm all pre-launch checklist items are completed
- [ ] Notify all stakeholders of launch window
- [ ] Verify monitoring dashboards are visible and operational
- [ ] Confirm on-call rotation is active
- [ ] Prepare rollback plan and document rollback commands
- [ ] Take pre-launch database backup
- [ ] Verify deployment artifacts (Docker images) are available in GHCR

### Deployment (T-0)

- [ ] Merge release branch to `main`
- [ ] Create version tag: `git tag -a v2.1.0 -m "Production launch v2.1.0"`
- [ ] Push tag: `git push origin v2.1.0`
- [ ] Verify CI/CD pipeline triggers automatically
- [ ] Monitor GitHub Actions workflow for successful build and publish
- [ ] Deploy to staging first: `helm upgrade etap-ai helm/etap-ai/ -n etap-staging`
- [ ] Run smoke tests against staging
- [ ] Deploy to production: `helm upgrade etap-ai helm/etap-ai/ -n etap-prod`
- [ ] Wait for rolling update to complete (all pods `Running` and `Ready`)
- [ ] Verify health endpoint in production: `curl https://<prod-domain>/health`
- [ ] Verify API documentation is accessible: `curl https://<prod-domain>/docs`

### Validation (T+15 minutes)

- [ ] Verify no error spikes in Grafana dashboards
- [ ] Confirm all pods are running and healthy: `kubectl get pods -n etap-prod`
- [ ] Verify API response time < 500 ms (p95)
- [ ] Test authentication flow: login with production credentials
- [ ] Test a sample engineering study end-to-end
- [ ] Verify WebSocket connections are established
- [ ] Confirm no sensitive data in application logs
- [ ] Verify SSL/TLS certificate is valid

---

## 6. Post-Launch

### Monitoring (First 24 Hours)

- [ ] Monitor Grafana dashboards for anomalies (error rate, latency, resource usage)
- [ ] Monitor Celery worker queue depth and task processing time
- [ ] Monitor Redis memory usage and connection count
- [ ] Monitor PostgreSQL connection pool, query performance, and replication lag
- [ ] Review application logs for warnings and errors: `kubectl logs -n etap-prod -l app=etap-ai`
- [ ] Monitor LLM API usage and token consumption
- [ ] Verify no cost overruns on cloud infrastructure

### Incident Response

- [ ] Incident response runbook is accessible to on-call team: `docs/INCIDENT_RESPONSE_RUNBOOK.md`
- [ ] Escalation contacts are documented and current
- [ ] Slack/Teams channel is created for launch incidents
- [ ] First responder is designated for the first 48 hours post-launch

### Rollback Plan

If critical issues are discovered:

1. **Immediate Rollback ( Helm ):**
   ```bash
   helm rollback etap-ai <previous-revision> -n etap-prod
   ```

2. **Image Rollback:**
   ```bash
   helm upgrade etap-ai helm/etap-ai/ -n etap-prod \
     --set api.image.tag=<previous-version>
   ```

3. **Database Rollback (if migration was applied):**
   ```bash
   alembic downgrade -1
   ```
   > **WARNING:** Database rollback may cause data loss. Only downgrade if migration is backward-compatible.

4. **Full Stack Rollback:**
   ```bash
   kubectl rollout undo deployment/etap-ai-api -n etap-prod
   kubectl rollout undo deployment/etap-ai-worker -n etap-prod
   ```

5. **DNS Failover (if applicable):**
   - Switch DNS to previous environment endpoint
   - Allow TTL to expire before confirming

- [ ] Rollback commands have been tested in staging
- [ ] Previous version Docker image is available in GHCR for rollback

### Post-Launch Review (T+7 Days)

- [ ] Conduct post-launch retrospective with the team
- [ ] Review all incidents and near-misses
- [ ] Update runbooks based on actual incidents
- [ ] Measure and report on SLO compliance: `docs/SLA_SLO_DOCUMENT.md`
- [ ] Review cost vs. budget
- [ ] Document lessons learned
- [ ] Update roadmap based on launch experience

---

## 7. Sign-off

The following approvals are required before proceeding to production launch:

| Role | Name | Approval | Date |
|---|---|---|---|
| Engineering Lead | _________________ | [ ] Approved | __________ |
| Security Lead | _________________ | [ ] Approved | __________ |
| DevOps / SRE Lead | _________________ | [ ] Approved | __________ |
| QA Lead | _________________ | [ ] Approved | __________ |
| Product Owner | _________________ | [ ] Approved | __________ |
| Stakeholder | _________________ | [ ] Approved | __________ |

**Conditions for Approval:**

- All Critical and High severity checklist items are completed
- All automated tests pass (unit, integration, E2E, scenario)
- Security scan reports zero critical or high vulnerabilities
- Load test results meet performance SLOs
- Rollback plan has been validated in staging
- Monitoring and alerting are operational
- On-call rotation is established

---

> **Note:** This checklist should be reviewed and updated for each release. Items marked as completed should be verified, not assumed.
