# Postgres HA via CloudNativePG — High Availability & Point-in-Time Recovery

## Why CloudNativePG instead of a StatefulSet?

The upstream `docker-compose.yml` runs a single `postgres:15` container with a
local volume. On Kubernetes, a plain StatefulSet gives you a stable identity but
**no automatic failover, no replication, no PITR**. You'd need to bolt on
Patroni / Stolon / repmgr yourself, plus a separate backup solution.

[CloudNativePG](https://cloudnative-pg.io/) (CNPG) is a CNCF sandbox project
that makes Postgres a first-class Kubernetes workload:

| Capability                          | Plain StatefulSet     | CloudNativePG                |
|-------------------------------------|-----------------------|------------------------------|
| Streaming replication               | ❌ DIY (Patroni)      | ✅ Built-in                  |
| Automatic failover                  | ❌                    | ✅ < 10s, Raft-based          |
| Connection pooler (PgBouncer)       | ❌ DIY                | ✅ Built-in                  |
| WAL archiving to S3                 | ❌ DIY                | ✅ barman-cloud plugin        |
| Point-in-time recovery (PITR)       | ❌ DIY                | ✅ First-class API            |
| Scheduled backups                   | ❌ DIY CronJob        | ✅ Declarative `scheduledBackups` |
| Metrics                             | ❌ DIY exporter       | ✅ Built-in PodMonitor        |
| Major version upgrades              | ❌ Risky              | ✅ In-place via image swap    |

## Install

```bash
# 1. Install the CloudNativePG operator (one-time, cluster-wide)
kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.2.yaml
kubectl -n cnpg-system wait --for=condition=available deploy/cnpg-controller-manager --timeout=180s

# 2. Create the namespace
kubectl apply -f 00-prerequisites/namespace.yaml

# 3. Create the secrets
POSTGRES_PW=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
sed -i "s/REPLACE_ME_WITH_32_CHAR_RANDOM_STRING/$POSTGRES_PW/" 03-postgres-ha/pgbackrest-config-secret.yaml
# Fill in your real AWS creds:
#   edit 03-postgres-ha/pgbackrest-config-secret.yaml — set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
kubectl apply -f 03-postgres-ha/pgbackrest-config-secret.yaml

# 4. Provision the S3 bucket: s3://etap-postgres-backups/
#    (use the AWS CLI or `mc mb` for MinIO)

# 5. Apply the cluster manifest
kubectl apply -f 03-postgres-ha/cnpg-cluster.yaml

# 6. Wait for the cluster to become ready (3 pods, primary elected)
kubectl -n etap wait --for=condition=Ready cluster/etap-postgres --timeout=600s
```

## Verify

```bash
# Cluster status
kubectl -n etap describe cluster etap-postgres

# 3 instances, one designated as PRIMARY, two as STANDBY
kubectl -n etap get pods -l cnpg.io/cluster=etap-postgres

# Services auto-created by the operator
kubectl -n etap get svc -l cnpg.io/cluster=etap-postgres
#   etap-postgres-rw   ClusterIP   10.x.x.x   5432/TCP   <- app writes here
#   etap-postgres-ro   ClusterIP   10.x.x.x   5432/TCP   <- reads
#   etap-postgres-r    ClusterIP   10.x.x.x   5432/TCP   <- any replica

# Test connectivity
POSTGRES_PW=$(kubectl -n etap get secret etap-postgres-app -o jsonpath='{.data.password}' | base64 -d)
kubectl -n etap run pgcli --rm -i --restart=Never --image=postgres:15 -- \
    psql "postgresql://etap_user:$POSTGRES_PW@etap-postgres-rw:5432/etap_db" \
    -c "SELECT version();"
```

## Point-in-Time Recovery (PITR)

WAL archives continuously to S3. To restore to a specific point in time:

```bash
# 1. List available backups
kubectl -n etap get backups

# 2. Create a recovery cluster (from a backup, targeting a specific timestamp)
cat <<EOF | kubectl apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: etap-postgres-pitr
  namespace: etap
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:15.6
  storage:
    size: 50Gi
  bootstrap:
    recovery:
      source: etap-postgres
      recoveryTarget:
        targetTime: "2026-06-21 09:30:00+00"   # ISO 8601 timestamp
  externalClusters:
    - name: etap-postgres
      barmanObjectStore:
        destinationPath: "s3://etap-postgres-backups/"
        endpointURL: "https://s3.amazonaws.com"
        s3Credentials:
          accessKeyId:
            name: etap-postgres-backup
            key: AWS_ACCESS_KEY_ID
          secretAccessKey:
            name: etap-postgres-backup
            key: AWS_SECRET_ACCESS_KEY
EOF

kubectl -n etap wait --for=condition=Ready cluster/etap-postgres-pitr --timeout=1800s
```

## Application-side: use the `-rw` service

The ETAP Helm chart's ConfigMap already sets:

```
DATABASE_URL = postgresql://etap_user@etap-postgres-rw.etap:5432/etap_db
DATABASE_USER = (from secret etap-postgres-app/username)
DATABASE_PASSWORD = (from secret etap-postgres-app/password)
```

If your `core/database.py` reads `DATABASE_URL` from env, no code change needed.
If you need read-replica routing for heavy SELECT workloads (e.g. report
generation), connect to `etap-postgres-ro.etap:5432` instead.

## Failure modes

| Scenario                       | Operator behavior                                  | App impact                          |
|--------------------------------|----------------------------------------------------|-------------------------------------|
| Primary pod dies               | Promotes a replica in 5–10s                        | ~10s write outage, reads continue   |
| Single replica pod dies        | Operator rebuilds it from primary                  | No impact                           |
| All replicas die               | Primary stays up; queue accumulates                | No write impact, failover degraded  |
| All pods die                   | Restore from latest backup + WAL                   | Up to 1 WAL segment (~16MB) data loss |
| S3 unreachable                 | WALs accumulate locally on PVC; resume when S3 back | Backups blocked, no app impact     |
