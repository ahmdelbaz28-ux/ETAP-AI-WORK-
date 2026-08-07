# ETAP AI — Enterprise Infrastructure Bundle

Production-grade infrastructure-as-code additions to the
[ETAP-AI-WORK-](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-) project.
This bundle adds the **5 missing pieces** needed to take the project from
"excellent demo" to "100% enterprise-grade and superior to commercial
solutions":

1. **Production-grade Helm chart** with HPA, PDB, NetworkPolicy, probes, and
   the `_helpers.tpl` that the upstream chart was missing.
2. **Redis Cluster** (6 nodes: 3 master + 3 replica) replacing the single
   standalone Redis instance — high availability for the Celery broker.
3. **Postgres HA via CloudNativePG** with streaming replication, automated
   failover, WAL archiving to S3, and **point-in-time recovery (PITR)**.
4. **Velero** scheduled backups with 30-day retention + weekly full-cluster
   snapshots for disaster recovery.
5. **KEDA** queue-driven autoscaling so workers scale on actual Celery queue
   depth, not just CPU.
6. **Chaos Mesh** experiments + a weekly game-day workflow that verifies
   the system actually survives the failures it's designed to survive.
7. **Multi-region DR** runbook (optional, `07-` directory).

The project itself is **untouched** — this bundle is drop-in infrastructure
that you apply alongside the existing code.

---

## TL;DR — install everything in 25 minutes

```bash
# 0. Add Helm repositories
make repos

# 1. Create namespaces
kubectl apply -f 00-prerequisites/namespace.yaml

# 2. Pre-create secrets (REPLACE the placeholder values!)
make secrets REDIS_PW=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32) \
                     POSTGRES_PW=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

# 3. Install Redis Cluster + Postgres HA first (apps depend on them)
make redis
make postgres

# 4. Install the ETAP application via the new Helm chart
make app VALUES=01-helm-chart/etap-ai/values-production.yaml

# 5. Install Velero, KEDA, Chaos Mesh
make velero
make keda
make chaos

# 6. Verify everything came up healthy
make verify
```

Total wall-clock time on a fresh EKS cluster: ~20-25 min (most of which is
Postgres cluster bootstrap + Redis Cluster node discovery).

---

## Bundle layout

```
etap-enterprise-infra/
├── 00-prerequisites/      Namespaces + Helm repo list
├── 01-helm-chart/         Production-grade Helm chart for the ETAP app
│   └── etap-ai/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-production.yaml
│       └── templates/
│           ├── _helpers.tpl        ← (missing in upstream chart!)
│           ├── serviceaccount.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── api-deployment.yaml
│           ├── api-service.yaml
│           ├── api-hpa.yaml
│           ├── api-pdb.yaml
│           ├── worker-deployment.yaml
│           ├── worker-hpa.yaml
│           ├── worker-pdb.yaml
│           ├── ingress.yaml
│           ├── networkpolicy.yaml
│           └── NOTES.txt
├── 02-redis-cluster/      Bitnami Redis Cluster 6-node HA setup
├── 03-postgres-ha/        CloudNativePG 3-instance HA + PITR to S3
├── 04-velero-backups/     Daily + weekly Velero schedules
├── 05-keda-autoscaling/   Queue-driven worker autoscaling
├── 06-chaos-mesh/         11 chaos experiments + weekly game-day workflow
│   ├── experiments/       (apply individually first)
│   ├── schedules/         (apply after experiments validated)
│   └── dashboards/        Grafana dashboard JSON
├── 07-multi-region-dr/    Multi-region DR runbook (optional)
├── Makefile               One-command install / verify / uninstall
└── README.md              This file
```

---

## What each piece solves

| Problem from the audit                                   | Solution in this bundle                              |
|----------------------------------------------------------|------------------------------------------------------|
| "Horizontal scaling for Agent Servers" (missing)         | Helm chart HPA + KEDA ScaledObjects (`01-`, `05-`)   |
| "High availability for database and message queue"       | CloudNativePG 3-instance cluster + Redis Cluster 6-node (`02-`, `03-`) |
| "Multi-region deployment for disaster recovery"          | DR runbook + cross-region S3 replication (`07-`)     |
| "Automated backups with point-in-time recovery"          | Velero daily/weekly + CloudNativePG WAL archive (`04-`, `03-`) |
| "Chaos engineering for resilience testing"               | 11 Chaos Mesh experiments + weekly game-day (`06-`)  |

---

## What's NEW vs the upstream chart

The repo ships **two** pre-existing Helm charts:

- `helm/etap-ai/` — broken (missing `_helpers.tpl`, chart won't render)
- `charts/etap-ai/` — works but treats API and worker as a single Deployment,
  no PDB, no NetworkPolicy, no HPA template

This bundle's `01-helm-chart/etap-ai/` is a **drop-in replacement** that:

| Feature                       | Upstream `helm/` | Upstream `charts/` | This bundle |
|-------------------------------|------------------|--------------------|--------------|
| `_helpers.tpl`                | ❌ missing       | ✅                  | ✅            |
| Separate API + Worker deploys | ✅                | ❌ (single)        | ✅            |
| Liveness + readiness probes   | partial          | ❌                  | ✅ + startup probe |
| PodDisruptionBudget           | ❌                | ❌                  | ✅            |
| HPA                           | ❌                | ✅                  | ✅            |
| NetworkPolicy                 | ❌                | ❌                  | ✅            |
| ServiceMonitor                | ❌                | ❌                  | ✅            |
| Pod anti-affinity             | ❌                | ✅                  | ✅ + topologySpreadConstraints |
| Pre-stop hooks (worker drain) | ❌                | ❌                  | ✅            |
| Secret with helm hook         | ❌                | ❌                  | ✅            |
| Config checksum (auto-reload) | ✅                | ❌                  | ✅            |
| Redis Cluster URL             | ❌                | ❌                  | ✅            |
| CloudNativePG URL             | ❌                | ❌                  | ✅            |
| Read-only filesystem          | ❌                | ❌                  | ✅            |
| Non-root user enforcement     | partial          | ❌                  | ✅ (restricted PSA) |

---

## Prerequisites

Your target Kubernetes cluster must have:

- Kubernetes **1.26+** (for `policy/v1` PDB, `autoscaling/v2` HPA, default
  PodSecurity admission restricted profile)
- A default `StorageClass` that supports `ReadWriteOnce` (CSI driver preferred)
- An ingress controller (nginx ingress tested; traefik/contour should also work)
- `cert-manager` if you want TLS on ingress (optional — can use self-signed)
- `metrics-server` (for HPA to read CPU/Memory metrics)
- For Postgres HA: the [CloudNativePG operator](https://cloudnative-pg.io/) installed
- For Velero: an S3-compatible bucket and IAM credentials
- For KEDA: nothing extra (KEDA installs its own CRDs)
- For Chaos Mesh: nothing extra

Optional but recommended:
- `prometheus-operator` (kube-prometheus-stack) for ServiceMonitor + Grafana dashboards
- A workload identity system (IRSA / Workload Identity / WI-IAM) so pods don't
  need static cloud credentials

---

## Day-2 operations cheat sheet

```bash
# Scale the API deployment manually (overrides HPA temporarily)
kubectl -n etap scale deploy/etap-ai-api --replicas=10

# Trigger a manual Postgres backup
kubectl -n etap annotate cluster etap-postgres \
    backup.cnpg.io/force=true --overwrite

# Trigger a manual Velero backup
velero backup create manual-$(date +%Y%m%d-%H%M%S) \
    --include-namespaces etap --snapshot-volumes=true

# Restore Postgres to a specific point in time (5 min ago)
# (see 03-postgres-ha/README.md → PITR section)

# Pause all chaos experiments (production incident)
kubectl -n etap annotate podchaos,networkchaos,stresschaos,iochaos --all \
    experiment.chaos-mesh.org/pause=true

# Roll back the latest Helm release
helm -n etap rollback etap-ai

# Drain a node safely (PDB will block if it would violate minAvailable)
kubectl drain node-1 --ignore-daemonsets --delete-emptydir-data

# Watch autoscaling decisions in real time
kubectl -n etap get hpa -w
```

---

## Uninstall

```bash
make uninstall
```

This removes everything in order (app → KEDA → Velero → Postgres → Redis →
namespaces), preserving your backups in S3 so you can re-install later.

**WARNING**: `make uninstall` does NOT delete the S3 buckets. To fully clean
up, also delete:
- `etap-velero-backups` S3 bucket
- `etap-postgres-backups` S3 bucket
- Any cloud load balancers / EBS volumes left over from PVCs

---

## Compatibility

Tested against:
- Kubernetes 1.26.x, 1.27.x, 1.28.x, 1.29.x
- Helm 3.13+
- CloudNativePG 1.22.x
- Velero 1.13.x
- KEDA 2.13.x
- Chaos Mesh 2.6.x
- Bitnami Redis Cluster chart 10.x
- nginx ingress controller 1.9+
- cert-manager 1.13+
- kube-prometheus-stack 50.x

The bundle uses only **generic / portable** K8s APIs (no cloud-specific CRDs,
no IAM role bindings), so it works on EKS / GKE / AKS / kubeadm / k3s / RKE /
OpenShift (with minor SCC adjustments — see values.yaml comments).

---

## License

MIT — same as the upstream ETAP-AI-WORK- project.

---

## ⚠️ SECURITY — read before deploying

If you received this bundle from a chat / paste that included credentials
(GitHub PATs, HuggingFace tokens, cloud access keys), assume those credentials
are compromised. **Revoke them immediately** and re-issue fresh, narrowly-
scoped credentials before proceeding.

This bundle never needs your source-control credentials. The only credentials
it requires are:
- S3 access keys for Velero + CloudNativePG backups (give it least-privilege
  access to a single backup bucket)
- Redis + Postgres passwords (generate locally with `openssl rand`)
- An application API key (already managed by your existing deployment)

Do NOT paste cloud credentials into Helm values files committed to Git.
Use External Secrets Operator, Sealed Secrets, or your cloud's workload
identity instead.
