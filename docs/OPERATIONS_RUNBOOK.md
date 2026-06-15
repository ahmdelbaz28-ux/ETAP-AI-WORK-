# Operations Runbook

## Table of Contents

1. System Architecture Overview
2. Standard Operating Procedures
3. Monitoring
4. Incident Response
5. Maintenance
6. Disaster Recovery
7. Capacity Planning
8. Contact Information

---

## 1. System Architecture Overview

### Architecture Diagram

```
                                   ┌──────────────┐
                                   │   Clients     │
                                   │ CLI / Web /  │
                                   │   API / MCP   │
                                   └──────┬───────┘
                                          │ HTTPS (443)
                                   ┌──────▼───────┐
                                   │   Nginx       │
                                   │  Reverse Proxy│
                                   └──────┬───────┘
                                          │
                          ┌───────────────┼───────────────┐
                          │               │               │
                   ┌──────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
                   │ Mastra AI   │  │ FastAPI     │  │  Health &   │
                   │ Server      │  │ Python      │  │  Metrics    │
                   │ :3000       │  │ Backend     │  │  :3000/health│
                   │ TypeScript  │  │ :8000       │  └────────────┘
                   │ Agents      │  │ Engines     │
                   └──────┬──────┘  └──────┬──────┘
                          │                │
                          │    ┌───────────▼────────────┐
                          │    │   Agent Orchestrator    │
                          │    │   agents/orchestrator.py│
                          │    └───────────┬────────────┘
                          │                │
              ┌───────────┼───────────┬────┼────┬───────────────┐
              │           │           │    │    │               │
       ┌──────▼────┐ ┌───▼───┐ ┌───▼───┐│┌──▼───┐┌──────▼────┐
       │ Load Flow  │ │ Fault │ │Harmon │││ OPF  ││ Protection │
       │ Engine     │ │Engine │ │Engine │││Engine││ Engine     │
       └──────┬────┘ └───┬───┘ └───┬───┘│└──┬───┘└──────┬────┘
              │           │         │    │   │           │
              └───────────┼─────────┼────┼───┼───────────┘
                          │         │    │   │
                    ┌─────▼─────────▼────▼───▼──────┐
                    │      Validation Agent         │
                    │      + RAG Knowledge Base      │
                    └──────────────┬────────────────┘
                                   │
                          ┌────────▼────────┐
                          │  Report Agent    │
                          │  PDF/DOCX/XLSX   │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │    ETAP COM      │
                          │   Automation     │
                          │  (Windows Only)  │
                          └─────────────────┘
```

### Component Descriptions

| Component | Technology | Port | Purpose | Dependencies |
|-----------|-----------|------|---------|-------------|
| Mastra AI Server | TypeScript/Node.js | 3000 | Agent orchestration, LLM integration, workflow management | OpenAI API, Python Backend |
| Python Backend | Python/FastAPI | 8000 | Calculation engines, system model, RAG, reporting | NumPy, SciPy, PyTorch, ChromaDB |
| Nginx | C | 443/80 | Reverse proxy, SSL termination, load balancing | Configuration files |
| SQLite/DuckDB | C | N/A | Database, vector store | Backend services |
| ETAP (External) | Windows COM | N/A | Power system simulation | ETAP license, Windows OS |

### Data Flow (Request Lifecycle)

```
1. Client sends HTTPS request to Nginx
2. Nginx proxies to Mastra Server (:3000)
3. Mastra Agent decomposes the engineering goal
4. Mastra invokes Python Backend (:8000) via HTTP
5. Python Orchestrator assigns tasks to calculation engines
6. Engines perform computations (Load Flow, Fault, etc.)
7. Results are validated against IEEE/IEC standards via RAG
8. Report Agent generates PDF/DOCX/XLSX output
9. Optionally, ETAP COM is used for validation/execution
10. Consolidated response flows back through Nginx to client
```

---

## 2. Standard Operating Procedures

### 2.1 Starting the System

#### Prerequisites

Before starting, verify:
- `.env` file exists with all required variables
- Ports 3000, 8000 are not in use
- Docker Desktop is running (if using Docker)
- Sufficient disk space (>5GB free)

#### Option A: Docker Deployment (Production)

```
# Step 1: Build images
docker-compose build

# Step 2: Start all services in detached mode
docker-compose up -d

# Step 3: Verify all services are running
docker-compose ps

# Expected output:
#   Name                    Status              Ports
#   etap-platform           Up                  0.0.0.0:3000->3000/tcp, 0.0.0.0:8000->8000/tcp
#   redis                   Up                  0.0.0.0:6379->6379/tcp
#   rabbitmq                Up                  0.0.0.0:5672->5672/tcp, 0.0.0.0:15672->15672/tcp

# Step 4: Run health check
curl http://localhost:3000/health
# Expected: {"status":"healthy","timestamp":"...","version":"1.0.0"}
```

#### Option B: Standalone (Development)

```
# Step 1: Activate Python virtual environment
.\\venv\\Scripts\\activate

# Step 2: Start Python backend
python main.py --port 8000 --log-level INFO
# Keep this terminal open

# Step 3: In a new terminal, start Mastra server
pnpm dev --port 3000

# Step 4: Verify both services
curl http://localhost:3000/health
curl http://localhost:8000/health
```

#### Option C: Windows Service

```
# Install as Windows service
sc create "ETAPPlatform" binPath="C:\Python311\python.exe C:\app\main.py --service" start=auto

# Start the service
net start ETAPPlatform

# Verify service is running
sc query ETAPPlatform
```

### 2.2 Stopping the System

#### Graceful Shutdown

```
# Option A: Docker
docker-compose down
# Use --volumes to also remove data volumes (WILL LOSE DATA):
docker-compose down --volumes

# Option B: Standalone
# Press Ctrl+C in each terminal, or:
taskkill /F /IM python.exe
taskkill /F /IM node.exe

# Option C: Windows Service
net stop ETAPPlatform
```

#### Emergency Shutdown (System Unresponsive)

```
# Force kill all platform processes
docker-compose down --timeout 0
taskkill /F /FI "IMAGENAME eq python.exe"
taskkill /F /FI "IMAGENAME eq node.exe"
taskkill /F /IM etap.exe  # If ETAP is stuck

# Verify no orphaned processes
tasklist | findstr /I "python node etap"
```

### 2.3 Restarting Services

#### Restart All Services

```
docker-compose restart
```

#### Restart Individual Components

```
# Restart Python backend only
docker-compose restart etap-platform
# Or standalone:
taskkill /F /IM python.exe && python main.py

# Restart Mastra server only
docker-compose restart etap-platform
# Or restart the Node process

# Restart Redis (if used)
docker-compose restart redis
```

#### Rolling Restart (Zero Downtime in Kubernetes)

```
kubectl rollout restart deployment/etap-platform
kubectl rollout status deployment/etap-platform
```

### 2.4 Backup Procedures

#### Database Backup

```
# Create backup directory
mkdir -p ./backups

# Manual backup
copy mastra.db backups\mastra_%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.db

# Automated backup (create a scheduled task)
@echo off
set BACKUP_DIR=.\backups
set TIMESTAMP=%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%
copy mastra.db %BACKUP_DIR%\mastra_%TIMESTAMP%.db
copy mastra.duckdb %BACKUP_DIR%\mastra_%TIMESTAMP%.duckdb
tar -czf %BACKUP_DIR%\knowledge_%TIMESTAMP%.tar.gz knowledge_db\
tar -czf %BACKUP_DIR%\reports_%TIMESTAMP%.tar.gz reports\
copy .env %BACKUP_DIR%\env_%TIMESTAMP%.txt

# Remove backups older than 30 days
forfiles -p %BACKUP_DIR% -m *.db -d -30 -c "cmd /c del @path"
forfiles -p %BACKUP_DIR% -m *.tar.gz -d -30 -c "cmd /c del @path"
```

#### Full System Backup

```
# Backup script: backup.sh / backup.ps1
# This should be run daily via Windows Task Scheduler

$backupRoot = ".\backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $timestamp

New-Item -ItemType Directory -Path $backupDir -Force

# Stop services for consistent backup
docker-compose pause

# Backup databases
Copy-Item "mastra.db" (Join-Path $backupDir "mastra.db")
Copy-Item "mastra.duckdb" (Join-Path $backupDir "mastra.duckdb")

# Backup knowledge base
Compress-Archive -Path "knowledge_db\*" -DestinationPath (Join-Path $backupDir "knowledge_db.zip")

# Backup reports
Compress-Archive -Path "reports\*" -DestinationPath (Join-Path $backupDir "reports.zip")

# Backup environment (redact secrets)
Get-Content ".env.example" | Set-Content (Join-Path $backupDir ".env.example")

# Resume services
docker-compose unpause

# Retention: keep 30 daily backups, 12 monthly
Get-ChildItem $backupRoot | Where-Object { $_.PSIsContainer -and $_.CreationTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Recurse -Force

Write-Host "Backup completed: $timestamp"
```

### 2.5 Restore Procedures

#### Database Restore

```
# Step 1: Stop services
docker-compose down

# Step 2: Backup current state (just in case)
copy mastra.db mastra.db.before_restore

# Step 3: Restore from backup
copy /Y backups\mastra_20260607_020000.db mastra.db

# Step 4: Verify database integrity
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
cursor = conn.execute('PRAGMA integrity_check')
result = cursor.fetchone()
print(f'Integrity check: {result[0]}')
conn.close()
"

# Step 5: Restart services
docker-compose up -d

# Step 6: Verify system is healthy
curl http://localhost:3000/health
```

#### Full System Restore

```
# Step 1: Stop services
docker-compose down

# Step 2: Restore databases
copy /Y backups\20260607_020000\mastra.db .\mastra.db
copy /Y backups\20260607_020000\mastra.duckdb .\mastra.duckdb

# Step 3: Restore knowledge base
Expand-Archive -Path backups\20260607_020000\knowledge_db.zip -DestinationPath .\ -Force

# Step 4: Restore reports
Expand-Archive -Path backups\20260607_020000\reports.zip -DestinationPath .\ -Force

# Step 5: Verify database integrity
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print('Database integrity: OK')
conn.close()
"

# Step 6: Start services
docker-compose up -d

# Step 7: Verify
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
# Check that key tables have data
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print(f'Tables restored: {len(tables)}')
conn.close()
"
```

---

## 3. Monitoring

### 3.1 Key Metrics to Monitor

#### System-Level Metrics

| Metric | Source | Warning Threshold | Critical Threshold | Check Interval |
|--------|--------|------------------|-------------------|----------------|
| CPU Usage | OS / Docker stats | >70% | >90% | 30 seconds |
| Memory Usage | OS / Docker stats | >3GB | >4GB | 30 seconds |
| Disk Usage | OS | >80% | >90% | 5 minutes |
| Disk I/O Wait | OS | >20% | >50% | 60 seconds |
| Network I/O | OS | >100 Mbps | >500 Mbps | 60 seconds |

#### Application-Level Metrics

| Metric | Source | Warning Threshold | Critical Threshold | Check Interval |
|--------|--------|------------------|-------------------|----------------|
| HTTP Request Rate | Prometheus / Nginx | >100 req/min | >500 req/min | 60 seconds |
| HTTP Error Rate | Prometheus / Nginx | >5% | >20% | 60 seconds |
| P95 Response Time | Prometheus | >2000ms | >5000ms | 60 seconds |
| Active Workflows | Python Backend | >5 | >10 | 30 seconds |
| Queue Depth | Celery/RabbitMQ | >50 | >200 | 30 seconds |
| ETAP Connection Status | Python Backend | Disconnected | Timeout >60s | 30 seconds |
| Calculation Convergence Rate | Python Backend | <95% | <90% | Per calculation |
| RAG Query Latency | Python Backend | >500ms | >2000ms | Per query |
| Cache Hit Rate | Python Backend | <80% | <60% | 5 minutes |
| Authentication Failure Rate | Security | >5/min | >20/min | 60 seconds |

#### Business-Level Metrics

| Metric | Description | Target | Alert If |
|--------|-------------|--------|----------|
| Successful Studies | Studies completed without error | >95% | <90% over 1 hour |
| Average Study Duration | Time from submission to completion | <30s | >120s |
| Report Generation Rate | Successful reports / total attempts | >98% | <95% |
| ETAP Automation Success | ETAP operations completed | >90% | <80% |
| Data Freshness | Age of latest vector DB update | <24 hours | >48 hours |

### 3.2 Alert Thresholds

#### PagerDuty/On-Call Alerts

```
CRITICAL (P1) - Immediate response required:
- Service completely down (health check fails >5 min)
- Complete ETAP integration failure
- Database corruption detected
- Security breach detected
- Disk full on critical volume

HIGH (P2) - Respond within 1 hour:
- P95 response time >5 seconds
- Error rate >20%
- ETAP COM connection flapping
- Calculation engine failures >50% in 10 min
- Memory usage >90%

WARNING (P3) - Respond within 8 hours:
- P95 response time >2 seconds
- Error rate >5%
- Cache hit rate <70%
- Active workflows >80% of max
- Disk usage >80%

INFO (P4) - Next business day:
- Certificate expiry <30 days
- Backup failure
- Log rotation failure
- Deprecated dependency detected
```

### 3.3 Dashboard Setup

#### Prometheus Metrics Endpoint

The Python backend exposes metrics at `http://localhost:8000/metrics`:

```
# Example Prometheus metrics
http_requests_total{method="POST",endpoint="/api/v1/analyze",status="200"} 1254
http_request_duration_seconds{endpoint="/api/v1/analyze",quantile="0.95"} 2.3
active_workflows 3
etap_connection_status 1
load_flow_convergence_rate 0.97
rag_query_latency_ms 245
cache_hit_ratio 0.85
auth_errors_total 12
```

#### Grafana Dashboard (Recommended Panels)

```
Panel 1: Service Health
- Uptime gauge
- Health check status (green/red)
- Component status indicators (Mastra, Python, ETAP, DB)

Panel 2: Request Metrics
- Request rate (requests/min) - time series
- Error rate (%) - time series
- P50/P95/P99 latency - time series

Panel 3: Workflow Metrics
- Active workflows - gauge
- Study completion rate - time series
- Study duration - heatmap
- Queue depth - time series

Panel 4: System Resources
- CPU usage (%) - time series
- Memory usage (GB) - time series
- Disk usage (%) - gauge
- Network I/O (MB/s) - time series

Panel 5: ETAP Status
- Connection status - state timeline
- Study success/failure - pie chart
- Project count - gauge
- COM operation latency - time series

Panel 6: Business Metrics
- Successful studies (24h) - stat
- Avg study duration - stat
- Reports generated (24h) - stat
- Authenticated users - stat
```

### 3.4 Log File Locations and Formats

#### Log File Index

| Log File | Path | Retention | Format | Key Fields |
|----------|------|-----------|--------|------------|
| Python Backend | `./logs/python-backend.log` | 30 days | JSON | timestamp, level, module, message, task_id |
| Mastra Server | `./logs/mastra-server.log` | 30 days | JSON | timestamp, level, agent, message, workflow_id |
| ETAP COM | `./logs/etap-com.log` | 30 days | JSON | timestamp, level, operation, duration_ms, project |
| Security | `./logs/security.log` | 90 days | JSON | timestamp, level, user, action, ip_address, result |
| Calculation | `./logs/calculation.log` | 30 days | JSON | timestamp, level, engine, study_type, system_size, convergence |
| RAG Engine | `./logs/rag-engine.log` | 30 days | JSON | timestamp, level, query_truncated, sources_count, latency_ms |

#### Log Format (JSON)

```json
{
  "timestamp": "2026-06-08T12:00:00.000Z",
  "level": "ERROR",
  "module": "etap_integration.etap_com",
  "message": "ETAP COM connection failed",
  "error_code": "ERR-001",
  "task_id": "wf_20260608_120000",
  "user": "engineer@example.com",
  "duration_ms": 15342,
  "details": {
    "reason": "ETAP not installed",
    "attempt": 3,
    "last_error": "pythoncom.com_error: (-2147221164, 'Class not registered', None, None)"
  },
  "stack_trace": "Traceback (most recent call last):\n  ..."
}
```

#### Log Query Examples

```
# Find all ERROR level logs in the last hour
Get-Content logs\python-backend.log | Select-String '"level":"ERROR"' | Select-String "2026-06-08T1[2-3]"

# Find all ERR-001 occurrences
Get-Content logs\etap-com.log | Select-String "ERR-001"

# Find logs for a specific task
Get-Content logs\*.log | Select-String "wf_20260608_120000"

# Calculate error rate per minute
Get-Content logs\python-backend.log | Select-String "ERROR" | Group-Object { $_.substring(0, 16) } | Format-Table Count, Name

# Top 10 slowest operations
Get-Content logs\etap-com.log | ConvertFrom-Json | Where-Object { $_.duration_ms -gt 10000 } | Sort-Object duration_ms -Descending | Select-Object -First 10
```

---

## 4. Incident Response

### 4.1 Incident Severity Classification

| Severity | Label | Definition | Response Time | Example |
|----------|-------|------------|---------------|---------|
| P1 | Critical | Complete service outage, data loss, security breach | < 15 min | Platform completely down, database corrupted |
| P2 | High | Major feature degradation, partial outage, performance severe | < 1 hour | ETAP integration down, calculations failing |
| P3 | Medium | Minor feature impact, non-critical degradation | < 4 hours | Report generation slow, some studies non-converging |
| P4 | Low | Cosmetic issues, minor bugs, documentation gaps | < 24 hours | Minor UI issues, non-critical log warnings |

### 4.2 Response Times

| Severity | Initial Response | Status Update | Resolution Target |
|----------|-----------------|---------------|-------------------|
| P1 | 15 minutes | Every 30 minutes | 4 hours |
| P2 | 1 hour | Every 2 hours | 8 hours |
| P3 | 4 hours | Every 8 hours | 24 hours |
| P4 | 24 hours | Every 48 hours | 72 hours |

### 4.3 Escalation Matrix

| Role | Name | Contact | Available | Escalation For |
|------|------|---------|-----------|----------------|
| Primary On-Call Engineer | - | PagerDuty / +1-XXX-XXX-XXXX | 24/7 | P1, P2 |
| Engineering Lead | - | +1-XXX-XXX-XXXX | Business hours | P1 unresolved >1hr |
| DevOps Engineer | - | +1-XXX-XXX-XXXX | 24/7 | Infrastructure issues |
| Security Lead | - | +1-XXX-XXX-XXXX | 24/7 | Security incidents |
| ETAP Support | ETAP Inc. | +1-949-900-1000 | Business hours | ETAP-specific issues |
| VP Engineering | - | +1-XXX-XXX-XXXX | Business hours | P1 unresolved >4hrs |

### 4.4 Incident Response Procedures

#### 4.4.1 Service Outage (P1)

**Symptoms:**
- All health checks fail
- HTTP 502/503 for all endpoints
- No process running on ports 3000/8000
- `docker ps` shows no running containers

**Immediate Actions (First 15 minutes):**
1. **Acknowledge incident** via PagerDuty
2. **Check platform status:**
   ```
   docker-compose ps
   docker logs etap-platform --tail 100
   ```
3. **Attempt quick restart:**
   ```
   docker-compose restart
   ```
4. **Check host system:**
   ```
   systeminfo | findstr "Total Physical Memory"
   dir C:\  # Check disk space
   netstat -ano | findstr ":3000 :8000"
   ```
5. **If restart fails, try rebuild:**
   ```
   docker-compose down --timeout 0
   docker-compose up -d --build
   ```

**Diagnostic Actions (15-60 minutes):**
1. Collect full diagnostic bundle (see Troubleshooting Guide Section 12.2)
2. Check if related to recent deployment:
   ```
   git log --oneline -10
   ```
3. Check resource constraints:
   ```
   docker stats --no-stream
   ```
4. Check ETAP status:
   ```
   tasklist | findstr /I etap
   ```

**Resolution Actions (1-4 hours):**
1. If resource exhaustion: increase limits, kill non-essential processes
2. If code regression: rollback to last known good version:
   ```
   git revert HEAD
   docker-compose up -d --build
   ```
3. If data corruption: restore from latest backup
4. If environment issue: restore `.env` from backup

**Post-Incident:**
1. Update status page
2. Document root cause in post-mortem
3. Add monitoring alert if missing
4. Update runbook with lessons learned

#### 4.4.2 Security Breach (P1)

**Symptoms:**
- Unauthorized API access detected
- Suspicious audit log entries
- Unknown API keys being used
- Data exfiltration alerts
- Multiple failed login attempts from unusual IPs

**Immediate Actions (First 15 minutes):**
1. **Isolate the platform:**
   ```
   # Block all external traffic at Nginx/firewall level
   docker-compose stop
   ```
2. **Preserve evidence:**
   ```
   # Copy logs before they rotate
   copy logs\security.log logs\security_incident_$(date +%Y%m%d_%H%M%S).log
   ```
3. **Rotate all secrets:**
   ```
   # Regenerate JWT_SECRET_KEY
   # Regenerate OPENAI_API_KEY in OpenAI dashboard
   # Update .env file
   ```
4. **Notify security team immediately**

**Investigation Actions (1-4 hours):**
1. Review security logs for the affected period
2. Check for unauthorized database access
3. Review network access logs
4. Identify compromised accounts and revoke access
5. Determine scope of data exposure

**Recovery Actions (4-8 hours):**
1. Restore from pre-incident backup
2. Deploy with new secrets and certificates
3. Enable additional security measures (IP allowlisting)
4. Notify affected users if PII was exposed

**Post-Incident:**
1. Full security audit
2. Implement additional security controls
3. Update incident response plan
4. Legal notification if required

#### 4.4.3 Data Corruption (P1-P2)

**Symptoms:**
- `DATABASE_CORRUPTION` error (ERR-033)
- SQLite integrity check fails
- Reports contain garbage data
- Agent returns nonsensical results
- RAG vector DB returns irrelevant results

**Immediate Actions:**
1. **Stop all write operations:**
   ```
   docker-compose pause
   ```
2. **Backup corrupted data (for investigation):**
   ```
   copy mastra.db mastra.db.corrupted_$(date +%Y%m%d)
   ```
3. **Check what's affected:**
   ```
   python -c "
   import sqlite3
   conn = sqlite3.connect('mastra.db')
   cursor = conn.execute('PRAGMA integrity_check')
   result = cursor.fetchall()
   print(f'Integrity check: {result}')
   conn.close()
   "
   ```

**Restoration Actions:**
1. Identify the latest uncorrupted backup
2. Restore database from backup (see Section 2.5)
3. If RAG vector DB is corrupted, rebuild from source documents:
   ```
   python -c "
   from knowledge.rag_engine import RAGEngine
   engine = RAGEngine()
   engine.rebuild_index(source_documents='knowledge/')
   print('Vector DB rebuilt')
   "
   ```
4. Verify data integrity after restore
5. Resume services

**Prevention:**
- Enable WAL mode for SQLite
- Use UPS with graceful shutdown
- Implement write-ahead logging
- Increase backup frequency

#### 4.4.4 Performance Degradation (P2-P3)

**Symptoms:**
- Response times exceed P95 threshold >5s
- High CPU/memory usage
- Study completion rate drops below 90%
- Queue depth growing
- Users reporting slow operations

**Diagnostic Flow:**

1. **Identify bottleneck:**
   ```
   # Check CPU/memory per process
   docker stats --no-stream
   
   # Check calculation engine performance
   python -c "
   from load_flow.load_flow import LoadFlowEngine
   engine = LoadFlowEngine()
   engine.benchmark()
   # Compare against known baselines
   "
   
   # Check database query performance
   python -c "
   import sqlite3
   conn = sqlite3.connect('mastra.db')
   import time
   start = time.time()
   conn.execute('SELECT COUNT(*) FROM tasks').fetchone()
   print(f'Query time: {(time.time()-start)*1000:.1f}ms')
   "
   ```

2. **Check for resource contention:**
   ```
   # Number of concurrent studies
   curl http://localhost:8000/metrics | findstr active_workflows
   
   # Queue depth
   curl http://localhost:8000/metrics | findstr queue_depth
   ```

3. **Check for slow ETAP operations:**
   ```
   Get-Content logs\etap-com.log | ConvertFrom-Json | Where-Object { $_.duration_ms -gt 10000 } | Format-Table timestamp, operation, duration_ms -AutoSize
   ```

**Resolution Options:**

| Issue | Solution | Implementation |
|-------|----------|----------------|
| High concurrent load | Scale horizontally | `docker-compose up -d --scale etap-platform=5` |
| Slow calculations | Use fast decoupled method | Set `METHOD=FAST_DECOUPLED` in config |
| Memory pressure | Reduce model size | Switch to `all-MiniLM-L6-v2` embedding |
| Database slow | Add indexes | `CREATE INDEX idx_tasks_status ON tasks(status)` |
| ETAP slow | Reduce COM polling frequency | Increase `COM_POLL_INTERVAL` in .env |
| Queue backed up | Add workers | `docker-compose up -d --scale worker=3` |

#### 4.4.5 ETAP Crash (P2)

**Symptoms:**
- `ETAP_COM_CONNECTION_FAILED` (ERR-001)
- ETAP process no longer in task list
- ETAP windows disappear
- COM operations return "Call was rejected by callee"

**Immediate Actions:**
1. **Check if ETAP process is still running:**
   ```
   tasklist | findstr /I etap
   ```

2. **Check Windows Event Viewer for ETAP errors:**
   ```
   Get-WinEvent -LogName Application | Where-Object { $_.ProviderName -like "*ETAP*" } | Select-Object -First 5
   ```

3. **Restart ETAP:**
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation
   # This will launch a new ETAP instance
   with ETAPAutomation(visible=False) as etap:
       print(f'ETAP restarted: v{etap.get_version()}')
   "
   ```

4. **If restart fails:**
   - Reboot the Windows host: `shutdown /r /t 60`
   - Or manually launch ETAP from Start Menu

**Root Cause Investigation:**
- Check ETAP crash logs: `%APPDATA%\ETAP\*\Logs\`
- Check for Windows crash dumps: `%LOCALAPPDATA%\CrashDumps`
- Verify ETAP license is valid
- Check for ETAP updates or patches

**Prevention:**
- Configure automatic ETAP restart via Windows Task Scheduler
- Implement ETAP health monitoring in the platform
- Use a separate Windows VM/bare metal for ETAP
- Keep ETAP and COM components updated

---

## 5. Maintenance

### 5.1 Regular Maintenance Tasks

| Frequency | Task | Responsibility | Duration | Impact |
|-----------|------|---------------|----------|--------|
| Daily | Verify health check | Operator | 5 min | None |
| Daily | Review error logs | Operator | 10 min | None |
| Daily | Backup databases | Automated | 15 min | Minimal (pause services) |
| Weekly | Review backup integrity | Operator | 15 min | None |
| Weekly | Check disk usage | Automated | 5 min | None |
| Bi-weekly | Update dependencies | DevOps | 1 hour | Requires restart |
| Monthly | Certificate renewal | DevOps | 30 min | Requires restart |
| Monthly | Log rotation verification | Operator | 10 min | None |
| Monthly | Performance benchmark | Engineering | 2 hours | None |
| Quarterly | Full DR test | DevOps + Engineering | 4 hours | Requires downtime |
| Quarterly | Dependency audit | Engineering | 2 hours | None |
| Annually | Security audit | Security + Engineering | 8 hours | Requires downtime |

### 5.2 Database Maintenance

#### SQLite Maintenance

```
# Reclaim disk space after deletions
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
conn.execute('VACUUM')
print('Database vacuum completed')
conn.close()
"

# Rebuild indexes for better performance
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
conn.execute('REINDEX')
print('Indexes rebuilt')
conn.close()
"

# Analyze query optimizer statistics
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
conn.execute('ANALYZE')
print('Query statistics updated')
conn.close()
"
```

#### Scheduled Maintenance Script

```
# Create: maintenance.ps1 (run weekly via Task Scheduler)
Write-Host "=== ETAP Platform Weekly Maintenance ===" -ForegroundColor Cyan

Write-Host "[1/6] Checking disk space..."
$disk = Get-PSDrive C | Select-Object Free, Used
$freeGB = [math]::Round($disk.Free / 1GB, 2)
Write-Host "  Free space: $freeGB GB"
if ($freeGB -lt 10) { Write-Warning "Low disk space!" }

Write-Host "[2/6] Vacuuming database..."
python -c "import sqlite3; sqlite3.connect('mastra.db').execute('VACUUM')"
if ($LASTEXITCODE -eq 0) { Write-Host "  Database vacuum: OK" }

Write-Host "[3/6] Rotating logs..."
Get-ChildItem "logs\*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
Write-Host "  Old logs cleaned"

Write-Host "[4/6] Cleaning old reports..."
Get-ChildItem "reports\*" -Directory | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | Remove-Item -Recurse -Force
Get-ChildItem "reports\*.pdf","reports\*.docx","reports\*.xlsx" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
Write-Host "  Old reports cleaned"

Write-Host "[5/6] Verifying database integrity..."
python -c "import sqlite3; c=sqlite3.connect('mastra.db'); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; print('  Integrity: OK')"

Write-Host "[6/6] Taking weekly backup..."
& ".\backup.ps1"

Write-Host "=== Maintenance Complete ===" -ForegroundColor Green
```

### 5.3 Log Rotation

#### Configuration (logging.conf or environment variables)

```
# Python logging rotation (in main.py or logging config)
LOGGING_MAX_BYTES=10485760      # 10MB per log file
LOGGING_BACKUP_COUNT=30         # Keep 30 rotated files
LOGGING_FORMAT=json             # JSON format for structured logging
```

#### Docker Log Rotation

```yaml
# In docker-compose.yml
services:
  etap-platform:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

#### Manual Log Rotation

```
# Compress and archive logs older than 7 days
Compress-Archive -Path "logs\*.log" -DestinationPath "logs\archive_$(Get-Date -Format yyyyMMdd).zip"
Remove-Item "logs\*.log" -Exclude "python-backend.log"  # Keep current

# Remove archives older than 90 days
Get-ChildItem "logs\archive_*.zip" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | Remove-Item
```

### 5.4 Certificate Renewal

#### SSL/TLS Certificate Renewal (Nginx)

```
# Step 1: Obtain new certificate (Let's Encrypt)
certbot renew --nginx

# Step 2: Verify certificate
certbot certificates

# Step 3: Reload Nginx to apply new certificate
docker exec etap-nginx nginx -s reload

# Step 4: Verify the new certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com < /dev/null 2>/dev/null | openssl x509 -noout -dates
```

#### Self-Signed Certificate Renewal

```
# Step 1: Generate new self-signed cert
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/etap-platform.key \
    -out nginx/ssl/etap-platform.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=etap-platform.local"

# Step 2: Reload Nginx
docker exec etap-nginx nginx -s reload

# Step 3: Verify
openssl x509 -in nginx/ssl/etap-platform.crt -text -noout | grep "Not After"
```

### 5.5 Dependency Updates

#### Python Dependencies

```
# Step 1: Check for outdated packages
pip list --outdated

# Step 2: Update specific packages
pip install --upgrade numpy scipy pandas

# Step 3: Update all packages
pip freeze > requirements-pinned.txt
pip install --upgrade -r requirements.txt

# Step 4: Run tests to verify compatibility
pytest tests/ -v

# Step 5: Update requirements.txt with new versions
pip freeze > requirements.txt
```

#### Node.js Dependencies

```
# Step 1: Check for outdated packages
pnpm outdated

# Step 2: Update all dependencies
pnpm update

# Step 3: Run build to verify
pnpm build

# Step 4: Run tests
pnpm test

# Step 5: Update lockfile
pnpm install --frozen-lockfile
```

#### Docker Image Updates

```
# Step 1: Rebuild with security updates
docker-compose build --no-cache

# Step 2: Run security scan
docker scan etap-platform:latest

# Step 3: Deploy updated images
docker-compose up -d
```

---

## 6. Disaster Recovery

### Recovery Objectives

| Metric | Target | Description |
|--------|--------|-------------|
| Recovery Point Objective (RPO) | 1 hour | Maximum acceptable data loss |
| Recovery Time Objective (RTO) | 4 hours | Maximum acceptable downtime |

### 6.1 Recovery Procedures

#### Scenario 1: Complete Infrastructure Loss

**Trigger:** Total loss of primary server, all data inaccessible.

**Recovery Steps:**

1. **Provision new server (30 min):**
   ```
   # Deploy new VM/cloud instance with:
   # - Windows Server 2019 or later
   # - Docker Desktop
   # - ETAP x.x (Windows-only component)
   # - Python 3.11
   # - Node.js 18+
   ```

2. **Restore code from repository (15 min):**
   ```
   git clone https://github.com/your-org/etap-ai-platform.git
   cd etap-ai-platform
   git checkout production
   ```

3. **Restore secrets (10 min):**
   - Copy `.env` from secure vault (LastPass, 1Password, Azure Key Vault)
   - Verify all API keys are valid

4. **Restore data from backup (30 min):**
   ```
   # Restore database from latest backup
   copy /Y \\backup-server\etap-backups\latest\mastra.db .\mastra.db
   copy /Y \\backup-server\etap-backups\latest\mastra.duckdb .\mastra.duckdb

   # Restore knowledge base
   Expand-Archive -Path \\backup-server\etap-backups\latest\knowledge_db.zip -DestinationPath .\

   # Restore reports
   Expand-Archive -Path \\backup-server\etap-backups\latest\reports.zip -DestinationPath .\
   ```

5. **Build and start services (30 min):**
   ```
   docker-compose build
   docker-compose up -d
   ```

6. **Verify recovery (15 min):**
   ```
   curl http://localhost:3000/health
   python -c "
   import sqlite3
   conn = sqlite3.connect('mastra.db')
   count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
   print(f'Recovered {count} tasks')
   "
   python -c "
   from knowledge.rag_engine import RAGEngine
   rag = RAGEngine()
   result = rag.query('test query', use_llm=False)
   print(f'RAG restored: {len(result[\"sources\"])} sources')
   "
   ```

7. **Total RTO: ~2 hours** (under RTO of 4 hours)

#### Scenario 2: Database Only Loss

**Trigger:** Database file corrupted or deleted.

**Recovery Steps:**

1. **Identify latest valid backup:**
   ```
   dir backups\*.db | Sort-Object LastWriteTime -Descending | Select-Object -First 5
   ```

2. **Restore database:**
   ```
   copy /Y backups\mastra_20260607_020000.db mastra.db
   ```

3. **Verify integrity:**
   ```
   python -c "
   import sqlite3
   conn = sqlite3.connect('mastra.db')
   result = conn.execute('PRAGMA integrity_check').fetchone()
   assert result[0] == 'ok', f'Corrupted: {result}'
   tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
   print(f'Database restored with {len(tables)} tables')
   "
   ```

4. **Restart services:**
   ```
   docker-compose restart
   ```

5. **Total RTO: ~30 minutes**

#### Scenario 3: ETAP Server Loss

**Trigger:** Windows server running ETAP is unavailable.

**Recovery Steps:**

1. **Provision new Windows server with ETAP:**
   - Install ETAP from installation media
   - Apply license file
   - Register COM components: `regsvr32 ETAPAutomation.dll`

2. **Copy ETAP project files:**
   ```
   copy /Y \\backup-server\etap-projects\* "C:\Projects\"
   ```

3. **Update platform configuration:**
   ```
   # Update .env with new ETAP server hostname
   ETAP_HOST=new-etap-server.domain.com
   ```

4. **Test ETAP connection:**
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation
   with ETAPAutomation(visible=False) as etap:
       print(f'ETAP reconnected: v{etap.get_version()}')
   "
   ```

5. **Total RTO: ~4 hours** (dominated by ETAP installation)

### 6.2 DR Testing Schedule

| Test Type | Frequency | Scope | Success Criteria |
|-----------|-----------|-------|------------------|
| Database restore | Monthly | Restore from backup to test environment | All data intact, integrity check OK |
| Full DR failover | Quarterly | Provision new server, restore all components | RTO < 4 hrs, RPO < 1 hr |
| ETAP recovery | Quarterly | Rebuild ETAP server from scratch | ETAP COM operational within 2 hrs |
| Backup validation | Weekly | Verify backup files are not corrupted | All backup files pass checksum |
| Secret rotation | Quarterly | Rotate all API keys and certificates | New secrets work without errors |

#### DR Test Procedure

```
# Pre-test: Document current state
echo "Pre-test state captured at $(Get-Date)" > dr-test-log.txt
python -c "
import sqlite3
conn = sqlite3.connect('mastra.db')
count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
print(f'Tasks in production: {count}')" >> dr-test-log.txt

# Test 1: Backup restore (in test environment)
# - Take a backup
# - Restore to test database
# - Verify data integrity and count

# Test 2: Full failover (in test environment)
# - Stop production analog
# - Provision new environment
# - Restore code, data, configuration
# - Start services
# - Verify health check
# - Run a test workflow

# Test 3: Measure RTO
$startTime = Get-Date
# [Execute DR procedure]
$endTime = Get-Date
$rto = ($endTime - $startTime).TotalMinutes
Write-Host "Measured RTO: $rto minutes"
if ($rto -gt 240) { Write-Warning "RTO exceeds 4 hour target!" }

# Test 4: Measure RPO
# Compare backup timestamp with last data change
# Verify data loss is within 1 hour window

# Post-test: Document results
echo "DR test completed at $(Get-Date)" >> dr-test-log.txt
echo "RTO: $rto minutes" >> dr-test-log.txt
```

---

## 7. Capacity Planning

### 7.1 Current Capacity Limits

| Resource | Current Limit | Unit | Components |
|----------|---------------|------|------------|
| System size | 500 | buses | Recommended maximum for interactive use |
| Concurrent workflows | 10 | workflows | Limited by ETAP single-instance constraint |
| Concurrent users | 100 | users | With horizontal scaling |
| Request throughput | 10 | workflows/min | With 3 Docker replicas |
| Database size | 10 | GB | Before performance impact |
| Log storage | 30 | days | At current log volume |
| Report storage | 1000 | reports | Before disk cleanup needed |
| RAG vector DB | 10000 | documents | Before query latency increases |
| Max file upload | 50 | MB | Per file |

### 7.2 Scaling Triggers

| Trigger Metric | Threshold | Action | Lead Time |
|---------------|-----------|--------|-----------|
| CPU usage > 80% | 5 min sustained | Scale up CPU allocation | Immediate |
| Memory > 85% | 10 min sustained | Scale up memory, review leaks | 1 hour |
| P95 latency > 5s | 15 min sustained | Add more replicas | 30 min |
| Error rate > 10% | 10 min sustained | Investigate, rollback if needed | 30 min |
| Queue depth > 100 | 5 min sustained | Add workers | 15 min |
| Disk usage > 85% | N/A | Clean old data, increase volume | 1 week |
| Concurrent workflows > 15 | 10 min sustained | Scale horizontally | 30 min |
| ETAP failures > 5/min | 5 min window | ETAP license check, restart | 15 min |

### 7.3 Growth Projections

| Quarter | Expected Workload | Required Capacity | Scaling Plan |
|---------|------------------|-------------------|--------------|
| Q3 2026 | 100 studies/day | 2 replicas, 200 bus avg | Current setup sufficient |
| Q4 2026 | 250 studies/day | 3 replicas, 300 bus avg | Add 1 replica, optimize solvers |
| Q1 2027 | 500 studies/day | 5 replicas, 400 bus avg | Add 2 replicas, consider K8s |
| Q2 2027 | 1000 studies/day | 10 replicas, 500 bus avg | Full K8s migration, database sharding |
| Q3 2027 | 2000 studies/day | 15 replicas, 600 bus avg | Multi-region deployment |

#### Capacity Upgrade Procedures

```
# Scale up Docker replicas (horizontal)
docker-compose up -d --scale etap-platform=5

# Scale up Kubernetes (horizontal)
kubectl scale deployment etap-platform --replicas=10

# Increase resource limits (vertical, in docker-compose.yml)
services:
  etap-platform:
    deploy:
      resources:
        limits:
          memory: 8g
          cpus: '4'

# Add database read replicas (if using PostgreSQL)
# Configure in .env:
DATABASE_URL=postgresql://master:5432/etap
DATABASE_READ_REPLICA_URL=postgresql://replica:5432/etap
```

---

## 8. Contact Information

### 8.1 Internal Contacts

| Role | Name | Email | Phone | Coverage |
|------|------|-------|-------|----------|
| Engineering On-Call | Rotating | oncall@yourcompany.com | +1-XXX-XXX-XXXX | 24/7 |
| Engineering Lead | - | eng-lead@yourcompany.com | +1-XXX-XXX-XXXX | Business hours |
| DevOps Engineer | - | devops@yourcompany.com | +1-XXX-XXX-XXXX | 24/7 |
| Security Team | - | security@yourcompany.com | +1-XXX-XXX-XXXX | 24/7 |
| QA Lead | - | qa@yourcompany.com | +1-XXX-XXX-XXXX | Business hours |
| Product Manager | - | pm@yourcompany.com | +1-XXX-XXX-XXXX | Business hours |

### 8.2 External Contacts

| Organization | Contact | Phone | Email | Purpose |
|-------------|---------|-------|-------|---------|
| ETAP Support | ETAP Inc. | +1-949-900-1000 | support@etap.com | ETAP software/license issues |
| OpenAI | Support Portal | - | https://support.openai.com | API key/rate limit issues |
| Docker | Support Portal | - | https://support.docker.com | Docker licensing issues |
| Microsoft Azure (if used) | Azure Support | - | https://portal.azure.com | Cloud infrastructure |
| Cloudflare (if used) | Support Portal | - | https://support.cloudflare.com | CDN/DDoS protection |

### 8.3 Escalation Path

```
User reports issue
    │
    ▼
L1: On-Call Engineer
    │  Contact: PagerDuty / +1-XXX-XXX-XXXX
    │  Response: 15 min (P1), 1 hour (P2)
    │
    ├── Resolved → Close
    │
    ▼
L2: Engineering Lead
    │  Contact: +1-XXX-XXX-XXXX
    │  Response: 1 hour
    │
    ├── Resolved → Post-mortem → Update runbook
    │
    ▼
L3: VP Engineering
    │  Contact: +1-XXX-XXX-XXXX
    │  Response: Immediate for P1
    │
    ▼
L4: Executive / Crisis Team
       Contact: emergency@yourcompany.com
       Response: Immediate
```

### 8.4 Communication Channels

| Channel | Purpose | URL/Details |
|---------|---------|-------------|
| Incident Alerts | P1/P2 notifications | PagerDuty integration |
| Status Page | Public service status | https://status.yourcompany.com |
| Slack | Team communication | #etap-platform-alerts |
| Email | Formal notifications | ops@yourcompany.com |
| Jira | Issue tracking | https://yourcompany.atlassian.net/projects/ETAP |
| Confluence | Documentation | https://yourcompany.atlassian.net/wiki/spaces/ETAP |
| Video Conferencing | Incident bridge | https://meet.yourcompany.com/incident-bridge |

### 8.5 On-Call Schedule

```
Weekly rotation: Engineering team (4 engineers)
Shift: Mon-Fri 9am-6pm (business hours)
After-hours: On-call engineer carries pager 24/7
Weekend: Dedicated on-call engineer
Holiday: Pre-arranged coverage with compensation

Primary On-Call:
- Current: [NAME] - [DATE RANGE]
- Phone: +1-XXX-XXX-XXXX

Secondary On-Call:
- Current: [NAME] - [DATE RANGE]
- Phone: +1-XXX-XXX-XXXX
```

### 8.6 Escalation Notification Templates

#### P1 Incident Notification (SMS/Pager)

```
[P1] ETAP Platform - [BRIEF DESCRIPTION]
Impact: [SERVICE IMPACT]
Affected: [COMPONENT/S]
Status: Investigating / Resolved
Time: [TIMESTAMP]
Lead: [ENGINEER NAME]
Bridge: [CONFERENCE LINK]
```

#### Status Page Update

```
Title: [Minor / Major / Critical] - [SERVICE NAME] - [INCIDENT TYPE]
Status: Investigating / Identified / Monitoring / Resolved
Description: [TECHNICAL DESCRIPTION IN PLAIN ENGLISH]
Impact: [USER-FACING IMPACT]
Start Time: [START TIME]
Estimated Resolution: [ESTIMATE OR "N/A"]
Components: [LIST OF AFFECTED COMPONENTS]
```

---

## Appendix: Quick Command Reference

### Startup & Shutdown
```
docker-compose up -d                    # Start all services
docker-compose down                     # Stop all services
docker-compose restart                  # Restart all services
docker-compose logs -f                  # Follow all logs
```

### Health Checks
```
curl http://localhost:3000/health       # Basic health
curl http://localhost:8000/metrics      # Prometheus metrics
docker-compose ps                       # Container status
```

### Backup & Restore
```
.\backup.ps1                            # Run backup script
copy backups\latest\mastra.db .         # Restore database
```

### Diagnostics
```
Get-Content logs\*.log | Select-String "ERROR"  # Find errors
docker stats --no-stream                         # Resource usage
docker-compose logs etap-platform --tail 100     # Last 100 lines
```

### Maintenance
```
python -c "import sqlite3; sqlite3.connect('mastra.db').execute('VACUUM')"  # DB maintenance
pip list --outdated                                                         # Check updates
pnpm outdated                                                                 # Check updates
```

### Scaling
```
docker-compose up -d --scale etap-platform=5    # Scale horizontally
kubectl scale deployment etap-platform --replicas=10  # Scale in K8s
```

---

**Document Version:** 1.0  
**Last Updated:** June 8, 2026  
**Maintained By:** Engineering Team  
**Classification:** Internal - Operations  
**Review Frequency:** Quarterly  
**DR Test Required:** Yes - Quarterly
