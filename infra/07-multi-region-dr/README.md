# Multi-Region Disaster Recovery — Runbook

This document describes how to deploy the ETAP AI platform across **two
regions** for disaster recovery. It is the most ambitious addition to the
bundle; everything else in `00-` through `06-` is a prerequisite.

## Architecture

```
                       ┌──────────────────────────────────┐
                       │     Global Load Balancer          │
                       │   (Route53 / Cloudflare / GCLB)   │
                       │  Weighted routing 80/20           │
                       └───────────┬──────────┬───────────┘
                                   │          │
                  ┌────────────────▼─┐   ┌────▼───────────────┐
                  │  Region A (active)│   │  Region B (passive) │
                  │  us-east-1        │   │  eu-west-1           │
                  │                  │   │                     │
                  │  EKS cluster     │   │  EKS cluster        │
                  │  ┌────────────┐  │   │  ┌────────────┐     │
                  │  │ etap ns    │  │   │  │ etap ns    │     │
                  │  │  - API x5  │  │   │  │  - API x2  │     │
                  │  │  - Worker  │  │   │  │  - Worker  │     │
                  │  │  - Redis   │  │   │  │  - Redis   │     │
                  │  │  - Postgres│  │   │  │  - Postgres│     │
                  │  └────────────┘  │   │  └────────────┘     │
                  │        │         │   │          │           │
                  │        ▼         │   │          ▼           │
                  │  S3 backups      │   │  S3 backups (cross-  │
                  │  bucket          │──▶│  region replicated)  │
                  └──────────────────┘   └─────────────────────┘
```

| Component          | Region A (active)            | Region B (passive)            |
|--------------------|------------------------------|-------------------------------|
| API replicas       | 5 (HPA min)                  | 2 (warm standby)              |
| Worker replicas    | 4 (HPA min)                  | 1 (warm standby)              |
| Redis Cluster      | 6 nodes (3 primary+3 replica)| 6 nodes (independent cluster) |
| Postgres (CNPG)    | 3 instances, primary here    | 3 instances, replica of A via logical replication |
| Velero backups     | Local S3 + cross-region repl | Local S3 + cross-region repl  |
| DNS weight         | 100% (active)                | 0% (idle, ready to promote)   |

## RPO / RTO targets

| Scenario                          | RPO (data loss)         | RTO (recovery time) |
|-----------------------------------|-------------------------|---------------------|
| Single pod failure                | 0 (K8s handles it)      | <60s                |
| Single AZ failure                 | 0 (multi-AZ cluster)    | <60s                |
| Single region failure (failover)  | <5 min (logical repl lag)| <15 min            |
| Full disaster (rebuild from backup)| <24h (backup schedule) | <2h (Velero restore) |

## Prerequisites

1. **Two Kubernetes clusters** in different regions / cloud providers.
2. **S3 buckets with cross-region replication**:
   - `etap-velero-backups-us-east-1` → replicates to `etap-velero-backups-eu-west-1`
   - `etap-postgres-backups-us-east-1` → replicates to `etap-postgres-backups-eu-west-1`
3. **Global DNS** (Route53 latency-based routing or Cloudflare load balancer).
4. **Postgres logical replication** set up between Region A's primary and
   Region B's primary (asynchronously).

## Setup — Region A (active)

```bash
# Switch kubectl context to Region A
export KUBECONFIG=~/.kube/region-a.yaml

# 1. Apply the full bundle in this order
kubectl apply -f 00-prerequisites/namespace.yaml
kubectl apply -f 02-redis-cluster/redis-password-secret.yaml
helm upgrade --install etap-redis-cluster bitnami/redis-cluster -n etap \
    -f 02-redis-cluster/values.yaml
kubectl apply -f 03-postgres-ha/pgbackrest-config-secret.yaml
kubectl apply -f 03-postgres-ha/cnpg-cluster.yaml
helm upgrade --install etap-ai ./01-helm-chart/etap-ai -n etap \
    -f 01-helm-chart/etap-ai/values-production.yaml \
    -f my-region-a-values.yaml     # image tag, ingress host, secrets

# 2. Install Velero
helm upgrade --install velero vmware-tanzu/velero -n velero \
    -f 04-velero-backups/values.yaml \
    --set configuration.backupStorageLocation[0].bucket=etap-velero-backups-us-east-1 \
    --set configuration.backupStorageLocation[0].config.region=us-east-1

# 3. Install KEDA + Chaos Mesh
helm upgrade --install keda keda/keda -n etap-infra -f 05-keda-autoscaling/values.yaml
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh -n etap-infra \
    -f 06-chaos-mesh/values.yaml

# 4. Set up Postgres logical replication publication for DR
kubectl -n etap exec -it etap-postgres-1 -- psql -U etap_user -d etap_db <<'SQL'
CREATE PUBLICATION dr_replication FOR ALL TABLES;
ALTER TABLE public.projects REPLICA IDENTITY FULL;
ALTER TABLE public.studies REPLICA IDENTITY FULL;
-- ... add all critical tables ...
SQL
```

## Setup — Region B (passive / warm standby)

```bash
# Switch kubectl context to Region B
export KUBECONFIG=~/.kube/region-b.yaml

# 1. Apply the same bundle BUT with reduced replica counts
#    Create my-region-b-values.yaml based on values-production.yaml:
#      api.replicaCount: 2 (instead of 5)
#      api.autoscaling.minReplicas: 2 (instead of 5)
#      worker.replicaCount: 1
#      worker.autoscaling.minReplicas: 1
#      flower.enabled: false  (only run in active region)
kubectl apply -f 00-prerequisites/namespace.yaml
kubectl apply -f 02-redis-cluster/redis-password-secret.yaml
helm upgrade --install etap-redis-cluster bitnami/redis-cluster -n etap \
    -f 02-redis-cluster/values.yaml
kubectl apply -f 03-postgres-ha/pgbackrest-config-secret.yaml
kubectl apply -f 03-postgres-ha/cnpg-cluster.yaml
helm upgrade --install etap-ai ./01-helm-chart/etap-ai -n etap \
    -f 01-helm-chart/etap-ai/values-production.yaml \
    -f my-region-b-values.yaml

# 2. Install Velero pointing at the cross-region-replicated bucket
helm upgrade --install velero vmware-tanzu/velero -n velero \
    -f 04-velero-backups/values.yaml \
    --set configuration.backupStorageLocation[0].bucket=etap-velero-backups-eu-west-1 \
    --set configuration.backupStorageLocation[0].config.region=eu-west-1

# 3. Set up Postgres SUBSCRIPTION to Region A's primary
#    (use the Region A `etap-postgres-rw` external IP or a peered VPC endpoint)
kubectl -n etap exec -it etap-postgres-1 -- psql -U etap_user -d etap_db <<'SQL'
CREATE SUBSCRIPTION dr_subscription
    CONNECTION 'host=region-a-postgres.example.com port=5432 dbname=etap_db user=replicator password=REPLICA_PASSWORD'
    PUBLICATION dr_replication
    WITH (copy_data = true, create_slot = true, slot_name = 'dr_slot');
SQL
```

## Failover procedure (Region A → Region B)

Trigger this when Region A is unreachable or irreparably degraded.

```bash
# 1. Cut DNS traffic to Region A (Route53 weighted routing 0/100)
aws route53 change-resource-record-sets --hosted-zone-id Z123ABC \
    --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"etap-ai.example.com.","Type":"CNAME","TTL":60,"ResourceRecords":[{"Value":"region-b-lb.example.com"}]}}]}'

# 2. Scale up Region B to full production capacity
helm upgrade etap-ai ./01-helm-chart/etap-ai -n etap \
    -f 01-helm-chart/etap-ai/values-production.yaml \
    -f my-region-b-values.yaml \
    --set api.replicaCount=5 \
    --set api.autoscaling.minReplicas=5 \
    --set worker.replicaCount=4 \
    --set worker.autoscaling.minReplicas=4 \
    --set flower.enabled=true

# 3. Promote Region B's Postgres from subscriber to standalone primary
kubectl -n etap exec -it etap-postgres-1 -- psql -U etap_user -d etap_db <<'SQL'
ALTER SUBSCRIPTION dr_subscription DISABLE;
DROP SUBSCRIPTION dr_subscription;
-- Region B's Postgres is now standalone; writes accepted here.
SQL

# 4. Verify Region B is serving production traffic
curl -fsS https://etap-ai.example.com/health
kubectl -n etap get pods -l app.kubernetes.io/part-of=etap-ai-platform

# 5. Once Region A is repaired, REVERSE the replication direction
#    (Region A becomes the subscriber, Region B the publisher).
#    Then perform another failover to return traffic to Region A.
```

## Testing the DR plan

At least once per quarter:

1. **Tabletop exercise** — walk through this runbook with the team. Identify
   any manual step that requires tribal knowledge and automate it.
2. **Partial failover** — shift 10% of traffic to Region B for 1 hour. Verify
   no errors. Shift back.
3. **Full failover drill** — during a low-traffic window (e.g. Sunday 2 AM),
   perform the complete failover procedure. Measure RTO. File any issues.

## Cost of multi-region

Multi-region DR roughly **doubles** your infrastructure cost — Region B is a
full copy of Region A running at minimum scale. For the ETAP AI workload
(5 API pods + 4 workers + Redis Cluster + Postgres HA + Velero):

| Component              | Region A (active) | Region B (passive) |
|------------------------|-------------------|--------------------|
| EKS control plane      | $73/mo            | $73/mo             |
| Worker nodes (m5.large)| 3 × $70 = $210    | 2 × $70 = $140     |
| EBS volumes            | $25               | $25                |
| S3 backups (50 GB)     | $1                | $1                 |
| Cross-region S3 xfer   | —                 | $5                 |
| Postgres logical repl  | included          | included           |
| DNS / load balancer    | $20               | $20                |
| **Total per region**   | **~$350/mo**      | **~$265/mo**       |

**Combined DR cost: ~$615/month** — far less than the cost of a 4-hour
outage on a critical engineering platform.

## When NOT to do multi-region

Multi-region DR adds operational complexity (replication lag, split-brain
risk, DNS propagation). It's worth it when:

- ✅ Your SLO requires <15 min RTO and you can't tolerate a regional outage
- ✅ You have users in multiple regions and want low latency
- ✅ You're contractually obligated by enterprise customers

Skip it (and stick with single-region + Velero backups) when:

- ❌ You can tolerate 2-4 hour RTO (rebuild from Velero backup)
- ❌ Your traffic is single-region
- ❌ You don't have a dedicated SRE to manage the replication
