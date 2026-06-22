# Velero Backups — Automated with Point-in-Time Recovery

## Backup strategy

The bundle implements a **3-tier** backup strategy:

| Tier          | Tool                              | Schedule           | Retention | Purpose                                            |
|---------------|-----------------------------------|--------------------|-----------|----------------------------------------------------|
| Tier 1: PITR  | CloudNativePG + barman-cloud      | Continuous WAL     | 30 days   | Recover Postgres to any 1-second-granularity point |
| Tier 2: Daily | Velero (snapshots + Restic)       | 02:00 daily        | 30 days   | Recover entire `etap` namespace                    |
| Tier 3: Weekly| Velero (snapshots + cluster-res)  | 01:00 every Sunday | 365 days  | Disaster recovery — entire cluster state           |

## Why both Velero AND CloudNativePG backups?

- **Velero** is great at backing up Kubernetes objects (Deployments, Services,
  ConfigMaps, Secrets) and PVC snapshots, but it can't do granular Postgres
  recovery. If you restore a Velero snapshot of a Postgres PVC, you get the
  state at the exact moment the snapshot was taken — but any transactions
  committed after that snapshot are lost.

- **CloudNativePG's barman-cloud** does continuous WAL archiving. You can
  restore to *any* point in time within the retention window, with
  1-second granularity. This is your "oops I dropped a table at 9:43 AM"
  recovery path.

Together they cover:

- **RPO (Recovery Point Objective)**: ~1 second for Postgres data via PITR;
  up to 24h for non-Postgres PVCs (Redis Cluster PVC, app logs).
- **RTO (Recovery Time Objective)**: < 10 min for namespace restore via Velero;
  < 30 min for full Postgres PITR via CloudNativePG.

## Install

```bash
# 1. Create the Velero namespace
kubectl create namespace velero

# 2. Create the bucket (AWS CLI shown; adapt for your cloud)
aws s3api create-bucket --bucket etap-velero-backups --region us-east-1

# 3. Create an IAM user with the policy below, capture the access key
#    (see credentials-velero.example below)
cat > credentials-velero <<EOF
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
EOF

# 4. Install Velero via Helm
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm upgrade --install velero vmware-tanzu/velero \
    -n velero \
    -f 04-velero-backups/values.yaml \
    --set-file credentials.secretContents.cloud=credentials-velero

# 5. Verify the backup storage location is "Available"
kubectl -n velero get backupstoragelocation
#   NAME      PROVIDER   BUCKET                ACCESS MODE   PHASE       LAST VALIDATED
#   default   aws        etap-velero-backups   ReadWrite     Available   2026-06-21T...

# 6. If you didn't use the Helm chart (installed via CLI instead), apply schedules:
kubectl apply -f 04-velero-backups/backup-schedule.yaml
```

## Verify

```bash
# Schedules
kubectl -n velero get schedules

# Trigger an on-demand backup
velero backup create etap-manual-$(date +%Y%m%d-%H%M%S) \
    --include-namespaces etap \
    --snapshot-volumes=true

# Watch backup progress
velero backup describe <backup-name> --details

# List all backups
velero backup get
```

## Restore

### Restore the entire `etap` namespace from the latest backup

```bash
# Find the latest successful backup
LATEST=$(velero backup get -o json | jq -r '.items | sort_by(.status.startTimestamp) | reverse | .[0].metadata.name')

# Restore into a fresh namespace (recommended — never overwrite in place)
velero restore create etap-restore-$(date +%Y%m%d) \
    --from-backup "$LATEST" \
    --namespace-mappings etap:etap-restored \
    --wait

kubectl -n etap-restored get pods
```

### Restore Postgres to a specific point in time

See `03-postgres-ha/README.md` → PITR section.

## Verification drills (run monthly)

```bash
# 1. Pick a non-critical time and trigger a manual backup
TS=$(date +%Y%m%d-%H%M%S)
velero backup create drill-$TS --include-namespaces etap --snapshot-volumes=true

# 2. Wait for completion
velero backup get drill-$TS --watch

# 3. Restore into a scratch namespace
velero restore create drill-restore-$TS \
    --from-backup drill-$TS \
    --namespace-mappings etap:etap-drill \
    --wait

# 4. Verify pods come up healthy
kubectl -n etap-drill get pods -l app.kubernetes.io/part-of=etap-ai-platform

# 5. Hit the API to verify data integrity
kubectl -n etap-drill port-forward svc/etap-ai-api 18000:8000 &
curl -fsS http://localhost:18000/health
curl -fsS http://localhost:18000/api/projects | jq .

# 6. Clean up
kubectl delete namespace etap-drill
velero backup delete drill-$TS --confirm
```

## Disaster Recovery — full cluster loss

If the entire cluster is lost:

1. Provision a new cluster (Terraform / eksctl / kubeadm).
2. Install Velero in the new cluster pointing at the same S3 bucket.
3. Restore the latest weekly backup:

   ```bash
   velero restore create --from-backup etap-weekly-full-backup-<TIMESTAMP> --wait
   ```

4. CloudNativePG will detect the existing Postgres PVCs and resume operation
   from the snapshot, replaying WALs from S3 to reach the most recent
   consistent state.
5. Update DNS / ingress to point at the new cluster.

Estimated total recovery time: **< 2 hours** for a fully provisioned new cluster.

## Cost considerations

- Velero snapshots use cloud snapshot storage (~$0.05/GB-month for EBS).
- A weekly full backup of a 50GB Postgres + 8GB Redis PVC over 365 days
  costs roughly **$15/month** in snapshot storage.
- CloudNativePG WAL archive is compressed (gzip) — a typical workload
  generates ~1–5 GB of WALs per day. At $0.023/GB-month S3 standard,
  that's **<$5/month**.
- Restic backups of small PVCs (logs, reports) are negligible.

**Total DR cost: ~$20/month** — well under any commercial DR solution.
