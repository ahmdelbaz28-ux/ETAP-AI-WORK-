# Redis Cluster — High Availability for the ETAP AI message queue & cache

## Why Redis Cluster instead of standalone Redis?

The upstream `docker-compose.yml` runs a single Redis instance (`redis:7-alpine`)
with `--appendonly yes`. That gives you **persistence** but **NOT high availability**:
if the Redis pod dies, the Celery broker goes dark until the pod restarts, and any
in-flight messages in the queue are lost (AOF is fsynced every second by default,
so up to 1 second of messages can disappear).

Redis Cluster gives you:

| Capability                 | Standalone Redis | Redis Cluster (6 nodes) |
|----------------------------|------------------|--------------------------|
| Broker uptime during pod kill | ❌ 0%          | ✅ ~100% (1 replica per shard) |
| Message durability         | ⚠️ AOF, ~1s loss  | ✅ Replicated to replica   |
| Write throughput           | ~100k ops/s     | ~300k ops/s (3 shards)    |
| Automatic failover         | ❌              | ✅ < 10 seconds            |
| Horizontal scaling         | ❌              | ✅ Add shards at runtime   |

## Install

```bash
# 1. Create the namespace if not already there
kubectl apply -f 00-prerequisites/namespace.yaml

# 2. Pre-create the Redis password secret
# IMPORTANT: generate a real password — do NOT keep the placeholder
REDIS_PW=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
sed -i "s/REPLACE_ME_WITH_32_CHAR_RANDOM_STRING/$REDIS_PW/" 02-redis-cluster/redis-password-secret.yaml
kubectl apply -f 02-redis-cluster/redis-password-secret.yaml

# 3. Add the Bitnami Helm repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# 4. Install the cluster
helm upgrade --install etap-redis-cluster bitnami/redis-cluster \
    -n etap \
    -f 02-redis-cluster/values.yaml

# 5. Wait for all 6 nodes to come up
kubectl -n etap wait --for=condition=ready pod -l app.kubernetes.io/name=redis-cluster \
    --timeout=600s
```

## Verify the cluster is healthy

```bash
# Get the Redis CLI password
REDIS_PW=$(kubectl -n etap get secret etap-redis-cluster -o jsonpath='{.data.redis-password}' | base64 -d)

# Run redis-cli against any node and check cluster info
kubectl -n etap exec -it etap-redis-cluster-0 -- redis-cli \
    -a "$REDIS_PW" --no-auth-warning \
    CLUSTER INFO

# Expected:
#   cluster_state:ok
#   cluster_slots_assigned:16384
#   cluster_slots_ok:16384
#   cluster_known_nodes:6
#   cluster_size:3

# Check the cluster topology
kubectl -n etap exec -it etap-redis-cluster-0 -- redis-cli \
    -a "$REDIS_PW" --no-auth-warning \
    CLUSTER NODES
```

You should see 6 nodes: 3 `master` + 3 `slave`, each master owning one of the
3 hash-slot ranges (0–5460, 5461–10922, 10923–16383).

## Application-side changes

### Python (FastAPI + Celery)

The `requirements.txt` already includes `redis`. Make sure you're on `redis>=4.3`
so `redis.cluster.RedisCluster` is available. For Celery:

```python
# worker/celery_app.py — already in your repo, just update the broker URL
import os

broker_url = os.environ["CELERY_BROKER_URL"]   # wired in by the Helm ConfigMap
result_backend = os.environ["CELERY_RESULT_BACKEND"]
```

The Helm chart's ConfigMap already builds the URL as
`redis://:$(REDIS_PASSWORD)@etap-redis-cluster:6379/0`. Celery will detect
the cluster topology automatically when it sees more than one node.

### Connection pool sizing

```python
# In your Celery config
broker_pool_limit = 10          # one pool per worker process
broker_connection_retry_on_startup = True
broker_connection_max_retries = 5

redis_socket_timeout = 30
redis_socket_keepalive = True
redis_health_check_interval = 30
```

## Failure modes & expected behavior

| Scenario                              | Cluster behavior                                    | Application behavior |
|---------------------------------------|-----------------------------------------------------|----------------------|
| Single replica pod dies               | Master keeps serving; replica rebuilt               | No impact            |
| Single master pod dies                | Replica promoted in <10s                            | ~5s of `MOVED` errors, then resumes |
| Entire AZ lost                        | 2 of 6 pods die; if both are master+replica of same shard, shard unavailable | Partial outage — 2/3 of keys still servable |
| Full cluster wipe                     | Velero restores PVCs from last backup               | Up to 24h of queue messages lost (use Postgres for critical state) |

## Day-2 operations

### Add a shard (horizontal scaling)

```bash
helm upgrade etap-redis-cluster bitnami/redis-cluster \
    -n etap -f 02-redis-cluster/values.yaml \
    --set cluster.nodes=8 --set cluster.replicas=1
# Then rebalance slots:
kubectl -n etap exec -it etap-redis-cluster-0 -- redis-cli -a "$REDIS_PW" \
    --cluster reshard etap-redis-cluster:6379
```

### Trigger a manual failover

```bash
kubectl -n etap exec -it etap-redis-cluster-0 -- redis-cli -a "$REDIS_PW" \
    CLUSTER FAILOVER
```

### Backup (Restic via Velero)

The `persistence.annotations."velero.io/backup": "true"` line tells Velero to
include these PVCs in scheduled backups. See `04-velero-backups/` for schedules.
