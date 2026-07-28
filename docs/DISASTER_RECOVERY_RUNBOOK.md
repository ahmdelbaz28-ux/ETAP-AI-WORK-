# AhmedETAP Platform — Disaster Recovery Runbook

**Version**: 2.1.0  
**Maintained by**: Engineering Operations Team  
**RTO Target**: ≤ 30 minutes  
**RPO Target**: ≤ 15 minutes  
**Tested**: Must be tested quarterly (see §8)  

---

## Table of Contents

1. [Alert Triage Matrix](#1-alert-triage-matrix)
2. [Database Recovery](#2-database-recovery)
3. [Redis Recovery](#3-redis-recovery)
4. [Python Engineering Service Recovery](#4-python-engineering-service-recovery)
5. [Celery Worker Recovery](#5-celery-worker-recovery)
6. [ETAP Windows Worker Recovery](#6-etap-windows-worker-recovery)
7. [Full Environment Recovery (Worst Case)](#7-full-environment-recovery-worst-case)
8. [Quarterly DR Test Procedure](#8-quarterly-dr-test-procedure)
9. [Escalation Path](#9-escalation-path)

---

## 1. Alert Triage Matrix

| Alert | Severity | First Responder Action |
|---|---|---|
| `etap_db_unhealthy` | 🔴 P1 | Go to §2 |
| `etap_redis_down` | 🔴 P1 | Go to §3 |
| `etap_engineering_service_down` | 🔴 P1 | Go to §4 |
| `etap_celery_worker_down` | 🟠 P2 | Go to §5 |
| `etap_windows_worker_unreachable` | 🟠 P2 | Go to §6 |
| `etap_coverage_below_80` | 🟡 P3 | Review failing tests; do not merge |
| `etap_container_vuln_critical` | 🔴 P1 | Review Trivy SARIF in Security tab |

---

## 2. Database Recovery

### 2a. Scenario: PostgreSQL pod crashed (data intact)

```bash
# Verify pod status
kubectl get pods -n etap -l app=postgres

# Restart the deployment
kubectl rollout restart deployment/postgres -n etap

# Watch recovery
kubectl rollout status deployment/postgres -n etap

# Verify connection from engineering-service
kubectl exec -it deploy/engineering-service -n etap -- \
  python -c "import asyncio; from api.database import check_db_health; print(asyncio.run(check_db_health()))"
```

### 2b. Scenario: Data loss — restore from backup

```bash
# 1. Identify latest backup
aws s3 ls s3://YOUR-BUCKET/etap-backups/ --recursive | grep ".sql.gz" | sort | tail -5

# 2. Download the latest backup
BACKUP_FILE="etap_db_20260625_143000.sql.gz"
aws s3 cp s3://YOUR-BUCKET/etap-backups/${BACKUP_FILE} /tmp/

# 3. Verify checksum
aws s3 cp s3://YOUR-BUCKET/etap-backups/${BACKUP_FILE}.sha256 /tmp/
sha256sum --check /tmp/${BACKUP_FILE}.sha256

# 4. Stop engineering service to prevent writes during restore
kubectl scale deployment/engineering-service --replicas=0 -n etap

# 5. Restore database
gunzip -c /tmp/${BACKUP_FILE} | psql \
  --host=$POSTGRES_HOST \
  --port=$POSTGRES_PORT \
  --username=$POSTGRES_USER \
  --dbname=$POSTGRES_DB

# 6. Run Alembic to ensure schema is current
kubectl exec -it deploy/engineering-service -n etap -- \
  alembic upgrade head

# 7. Restart engineering service
kubectl scale deployment/engineering-service --replicas=3 -n etap
kubectl rollout status deployment/engineering-service -n etap

# 8. Verify
curl -sf https://your-api-endpoint/health | python -m json.tool
```

**Estimated RTO**: 15–25 minutes depending on database size.

---

## 3. Redis Recovery

> **Note**: Redis is used for: (1) Celery task queue, (2) rate limiting, (3) circuit breaker state, (4) worker heartbeat registry. Circuit breakers will reset to CLOSED on Redis restart — this is safe.

### 3a. Redis pod crashed

```bash
kubectl rollout restart deployment/redis -n etap
kubectl rollout status deployment/redis -n etap

# Confirm Celery worker can reconnect
kubectl logs -l app=celery-worker -n etap --tail=50 | grep -E "connected|error"
```

### 3b. Redis data corruption

```bash
# Flush all Redis data (safe — all Celery tasks will need resubmission)
kubectl exec -it deploy/redis -n etap -- redis-cli FLUSHALL

# Restart Celery workers so they re-register
kubectl rollout restart deployment/celery-worker -n etap
```

**Estimated RTO**: 5 minutes.  
**Data Loss**: Queued Celery tasks are lost — clients must resubmit. In-flight completed results are lost. Study results are in PostgreSQL and are NOT lost.

---

## 4. Python Engineering Service Recovery

### 4a. Pod OOMKilled or CrashLoopBackOff

```bash
# Check pod events
kubectl describe pods -l app=engineering-service -n etap | grep -A 20 Events

# Check recent logs
kubectl logs -l app=engineering-service -n etap --previous --tail=100

# Rolling restart (zero downtime)
kubectl rollout restart deployment/engineering-service -n etap
kubectl rollout status deployment/engineering-service -n etap
```

### 4b. Image corruption — rollback

```bash
# Find previous successful image SHA
kubectl rollout history deployment/engineering-service -n etap

# Rollback to previous version
kubectl rollout undo deployment/engineering-service -n etap

# Or rollback to specific revision
kubectl rollout undo deployment/engineering-service --to-revision=3 -n etap
```

---

## 5. Celery Worker Recovery

```bash
# Check worker health in Redis
redis-cli -u $REDIS_URL keys "etap:worker:heartbeat:*"

# Restart worker fleet
kubectl rollout restart deployment/celery-worker -n etap

# Scale up temporarily if task backlog exists
kubectl scale deployment/celery-worker --replicas=10 -n etap

# Check queue depth
redis-cli -u $REDIS_URL llen celery
```

---

## 6. ETAP Windows Worker Recovery

```bash
# Check which workers are alive
curl -sf https://your-api-endpoint/etap-worker/workers | python -m json.tool

# SSH to Windows host and restart the worker service
# (execute on Windows host)
Restart-Service -Name "ETAPWorker" -Force

# Verify worker re-registers (watch Redis)
watch -n 5 'redis-cli -u $REDIS_URL keys "etap:worker:registry:*"'

# If worker cannot reach Redis, use HTTP heartbeat via the Linux gateway
curl -X POST "https://your-api-endpoint/etap-worker/register?worker_id=etap-win-01&host=192.168.1.100&port=8081"
```

---

## 7. Full Environment Recovery (Worst Case)

> **Scenario**: Entire cluster lost. Restore from scratch.

```bash
# 1. Provision infrastructure (Terraform / Helm)
cd infrastructure/
terraform apply

# 2. Deploy services
helm upgrade --install etap-ai ./helm/etap-ai/ \
  --namespace etap \
  --create-namespace \
  -f helm/etap-ai/values-prod.yaml \
  --wait

# 3. Restore PostgreSQL
./scripts/backup/postgres_backup.sh --dry-run  # verify script
# Follow §2b to restore database

# 4. Verify all services
kubectl get pods -n etap
curl -sf https://your-api-endpoint/health
curl -sf https://your-api-endpoint/ready
curl -sf https://your-api-endpoint/etap-worker/workers/health

# 5. Notify stakeholders
echo "Recovery complete. RTO achieved: $(date)"
```

**Estimated Total RTO**: 25–30 minutes.

---

## 8. Quarterly DR Test Procedure

> **Frequency**: Once per quarter (Jan, Apr, Jul, Oct)  
> **Environment**: Staging (never production)

### Checklist

- [ ] Announce maintenance window to stakeholders
- [ ] Create a database backup: `./scripts/backup/postgres_backup.sh --verbose`
- [ ] Verify checksum file integrity
- [ ] Simulate failure: `kubectl delete pod -l app=postgres -n etap-staging --force`
- [ ] Restore from backup following §2b
- [ ] Verify all `/health` and `/ready` endpoints return 200
- [ ] Verify study execution works end-to-end (submit a load flow study)
- [ ] Record actual RTO achieved
- [ ] Record actual RPO (time of last backup before the test)
- [ ] Update this document if RTO > 30 min or RPO > 15 min
- [ ] Archive test results to `docs/dr-test-results/YYYY-QN.md`

---

## 9. Escalation Path

| Situation | Contact |
|---|---|
| RTO breached (>30 min) | Engineering Lead |
| Data loss confirmed | CTO + Legal |
| Security breach suspected | Security team |
| ETAP license issue | ETAP vendor support |

---

*Last updated: 2026-06-25*
