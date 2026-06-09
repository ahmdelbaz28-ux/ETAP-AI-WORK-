# ETAP AI Engineering Platform - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the ETAP AI Engineering Platform in production environments.

## Prerequisites

### System Requirements

**Minimum:**
- OS: Windows 10/11 (for ETAP integration) or Linux/macOS (calculations only)
- CPU: 4 cores
- RAM: 8 GB
- Storage: 20 GB
- Python: 3.9+
- Node.js: 18+

**Recommended:**
- OS: Windows Server 2019/2022 or Ubuntu 22.04 LTS
- CPU: 8+ cores
- RAM: 32 GB
- Storage: 100 GB SSD
- Python: 3.11+
- Node.js: 20+

### Software Dependencies

1. **ETAP Software** (optional, for ETAP automation)
   - ETAP v12.0 or later
   - Valid ETAP license
   - COM automation enabled

2. **Python Packages**
   ```bash
   pip install -r requirements.txt
   ```

3. **Node.js Packages**
   ```bash
   pnpm install
   ```

## Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/my-awesome-agent.git
cd my-awesome-agent
```

### Step 2: Configure Environment

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` file with your configuration:
   ```env
   # API Keys
   OPENAI_API_KEY=sk-your-openai-key
   LANGWATCH_API_KEY=sk-lw-your-key
   SMITHERY_API_KEY=REDACTED_SMITHERY_KEY

   # JWT Authentication
   JWT_SECRET_KEY=generate-a-secure-random-key-here

   # Database (if using persistent storage)
   DATABASE_URL=file:./mastra.db

   # ETAP Configuration (Windows only)
   ETAP_INSTALL_PATH=C:\Program Files\ETAP
   ETAP_VERSION=19.0

   # Security Settings
   MAX_REQUESTS_PER_MINUTE=100
   TOKEN_EXPIRY_HOURS=8
   ```

3. Generate secure JWT key:
   ```python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

### Step 3: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Install Node.js Dependencies

```bash
# Install pnpm if not already installed
npm install -g pnpm

# Install dependencies
pnpm install
```

### Step 5: Build TypeScript Components

```bash
# Build Mastra agents
pnpm build
```

### Step 6: Run Validation Tests

```bash
# Run Python validation suite
python validation_suite.py

# Run unit tests
pytest tests/unit_tests.py -v --cov=.

# Run TypeScript tests
pnpm test
```

### Step 7: Start Services

#### Option A: Development Mode

```bash
# Terminal 1: Start Python backend
python main.py

# Terminal 2: Start Mastra dev server
pnpm dev
```

#### Option B: Production Mode

```bash
# Start with PM2 process manager
npm install -g pm2

# Start Python service
pm2 start main.py --name etap-backend --interpreter python

# Start Node.js service
pm2 start npm --name etap-frontend -- start

# Monitor services
pm2 monit
```

### Step 8: Configure Firewall

Open required ports:
- **Port 3000**: Mastra API server
- **Port 8000**: Python calculation engine (if exposed)
- **Port 5432**: PostgreSQL (if using external database)

```bash
# Example for UFW (Linux)
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

### Step 9: Setup SSL/TLS (Production)

For HTTPS, configure reverse proxy with SSL:

**Nginx Configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name etap.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/etap.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/etap.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Step 10: Initialize Database

```bash
# If using persistent storage
python scripts/init_database.py

# Create admin user
python scripts/create_admin.py --username admin --email admin@company.com
```

## Docker Deployment

### Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN npm install -g pnpm

# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Install Node.js dependencies
RUN pnpm install && pnpm build

# Expose port
EXPOSE 3000

# Start application
CMD ["pnpm", "start"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  etap-platform:
    build: .
    ports:
      - "3000:3000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DATABASE_URL=file:/data/mastra.db
    volumes:
      - ./data:/data
      - ./projects:/app/projects
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

Deploy with Docker:

```bash
docker-compose up -d
```

## Kubernetes Deployment

### Create Kubernetes Manifests

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: etap-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: etap-platform
  template:
    metadata:
      labels:
        app: etap-platform
    spec:
      containers:
      - name: etap-platform
        image: your-registry/etap-platform:latest
        ports:
        - containerPort: 3000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: etap-secrets
              key: openai-api-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: etap-platform-service
spec:
  selector:
    app: etap-platform
  ports:
  - port: 80
    targetPort: 3000
  type: LoadBalancer
```

Apply manifests:

```bash
kubectl apply -f deployment.yaml
kubectl get pods
kubectl get services
```

## Monitoring & Observability

### Setup Logging

Configure structured logging in `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/etap-platform/app.log
```

### Metrics Collection

Install Prometheus and Grafana:

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack
```

### Health Checks

The platform exposes health check endpoints:

- `GET /health`: Basic health check
- `GET /health/detailed`: Detailed system status
- `GET /metrics`: Prometheus metrics

## Backup & Disaster Recovery

### Automated Backups

Create backup script `scripts/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/etap-platform"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup database
cp data/mastra.db "$BACKUP_DIR/mastra_$TIMESTAMP.db"

# Backup projects
tar -czf "$BACKUP_DIR/projects_$TIMESTAMP.tar.gz" projects/

# Backup configurations
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" .env prompts/

# Keep only last 30 days of backups
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
```

Schedule with cron:

```cron
0 2 * * * /path/to/scripts/backup.sh
```

### Restore from Backup

```bash
# Stop services
pm2 stop all

# Restore database
cp /backups/etap-platform/mastra_20260604_020000.db data/mastra.db

# Restore projects
tar -xzf /backups/etap-platform/projects_20260604_020000.tar.gz

# Start services
pm2 start all
```

## Security Hardening

### 1. Enable Authentication

Ensure JWT authentication is enabled:

```env
JWT_SECRET_KEY=<strong-random-key>
TOKEN_EXPIRY_HOURS=8
```

### 2. Configure CORS

In `src/mastra/index.ts`:

```typescript
cors: {
  origin: ['https://yourdomain.com'],
  credentials: true
}
```

### 3. Rate Limiting

Configure rate limits in security framework:

```python
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
```

### 4. Input Validation

All inputs are validated by `InputValidator` class. Never disable validation.

### 5. Secrets Management

Use HashiCorp Vault or AWS Secrets Manager for production:

```bash
# Store secrets in Vault
vault kv put secret/etap-platform openai_api_key=sk-...
vault kv put secret/etap-platform jwt_secret_key=...
```

## Performance Tuning

### Python Optimization

1. **Enable NumPy MKL:**
   ```bash
   pip uninstall numpy
   pip install intel-numpy
   ```

2. **Use multiprocessing for parallel calculations:**
   ```python
   from multiprocessing import Pool
   
   def parallel_load_flow(systems):
       with Pool(processes=4) as pool:
           results = pool.map(run_load_flow, systems)
       return results
   ```

### Node.js Optimization

1. **Cluster mode:**
   ```javascript
   const cluster = require('cluster');
   const numCPUs = require('os').cpus().length;

   if (cluster.isMaster) {
     for (let i = 0; i < numCPUs; i++) {
       cluster.fork();
     }
   }
   ```

2. **Enable compression:**
   ```typescript
   import compression from 'compression';
   app.use(compression());
   ```

## Troubleshooting

### Common Issues

**Issue 1: ETAP COM automation fails**
- Ensure ETAP is installed and licensed
- Check that pywin32 is installed: `pip install pywin32`
- Verify ETAP version compatibility (v12.0+)
- Run as administrator on Windows

**Issue 2: Memory errors with large systems**
- Increase Python memory limit
- Use sparse matrices for Ybus
- Enable garbage collection: `gc.collect()`

**Issue 3: Slow load flow convergence**
- Check for ill-conditioned systems
- Adjust tolerance: `tol=1e-8`
- Increase max iterations: `max_iter=200`

**Issue 4: Authentication failures**
- Verify JWT_SECRET_KEY is set
- Check token expiry
- Review user permissions

### Logs Location

- Python logs: `/var/log/etap-platform/python.log`
- Node.js logs: `/var/log/etap-platform/node.log`
- Audit logs: `security_audit.log`
- Mastra logs: `.mastra/logs/`

### Support Contacts

- Technical Support: support@yourcompany.com
- Emergency: +1-XXX-XXX-XXXX
- Documentation: https://docs.yourcompany.com/etap-platform

## Maintenance Procedures

### Regular Maintenance Tasks

**Daily:**
- Check system health: `curl http://localhost:3000/health`
- Review error logs
- Monitor disk space

**Weekly:**
- Run validation suite: `python validation_suite.py`
- Update dependency audit: `pnpm audit`
- Review security logs

**Monthly:**
- Apply security patches
- Rotate API keys
- Test backup restoration
- Performance benchmarking

### Upgrade Procedure

1. **Backup current installation:**
   ```bash
   ./scripts/backup.sh
   ```

2. **Pull latest code:**
   ```bash
   git pull origin main
   ```

3. **Update dependencies:**
   ```bash
   pip install -r requirements.txt --upgrade
   pnpm install
   ```

4. **Run migrations:**
   ```bash
   python scripts/migrate.py
   ```

5. **Restart services:**
   ```bash
   pm2 restart all
   ```

6. **Verify functionality:**
   ```bash
   python validation_suite.py
   pytest tests/
   ```

## Compliance & Certification

### Industry Standards

The platform complies with:
- IEEE 519-2022: Harmonic Control
- IEEE 1584-2018: Arc Flash Hazard Calculations
- IEC 60909: Short-Circuit Currents
- IEC 60255: Protection Relays
- NFPA 70E: Electrical Safety

### Audit Trail

All actions are logged to `security_audit.log` with:
- Timestamp
- User ID
- Action performed
- Success/failure status
- IP address

### Data Privacy

- No personal data stored without consent
- GDPR-compliant data handling
- Encryption at rest and in transit
- Right to deletion supported

---

**Last Updated:** 2026-06-04  
**Version:** 1.0.0  
**Maintained By:** Engineering Team
