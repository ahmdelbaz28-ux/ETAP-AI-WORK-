# KEDA — Queue-driven autoscaling for the ETAP AI worker fleet

## Why KEDA on top of HPA?

The Helm chart's HPA scales the Celery worker on **CPU and Memory**. That sounds
sensible, but for queue-driven workloads it has two failure modes:

1. **Slow scale-up**: A burst of 100 study tasks lands in the queue. The 2
   running workers are blocked on I/O (waiting for ETAP COM, network, DB) so
   their CPU stays low. The HPA doesn't fire. Queue latency spikes.
2. **Premature scale-down**: After the burst drains, CPU drops. The HPA's
   `stabilizationWindowSeconds` expires and it scales back down. The next burst
   hits cold workers, which need 30–60s to load numpy/scipy/pandas.

KEDA fixes both by exposing **Celery queue depth** as a custom metric to the
HPA. The HPA still owns the actual scaling decision; KEDA just feeds it better
data.

| Metric                         | HPA-only                | HPA + KEDA                          |
|--------------------------------|-------------------------|-------------------------------------|
| Time to react to queue burst   | 60–180s                 | 15s                                 |
| Scale-to-zero when idle        | ❌ (min=2 always)      | ✅ (configurable `idleReplicaCount`) |
| Cost during idle periods       | 100%                    | 20–40%                              |
| Scales on real demand signal   | ❌ (CPU is a proxy)    | ✅ (queue length IS the demand)     |

## Install

```bash
# 1. Install KEDA in the etap-infra namespace
helm repo add keda https://kedacore.github.io/charts
helm repo update
helm upgrade --install keda keda/keda \
    -n etap-infra --create-namespace \
    -f 05-keda-autoscaling/values.yaml

# 2. DISABLE the chart's built-in HPA (otherwise Helm & KEDA will fight)
helm upgrade etap-ai ./01-helm-chart/etap-ai -n etap \
    -f my-values.yaml \
    --set api.autoscaling.enabled=false \
    --set worker.autoscaling.enabled=false

# 3. Apply the ScaledObjects
kubectl apply -f 05-keda-autoscaling/api-scaledobject.yaml
kubectl apply -f 05-keda-autoscaling/worker-scaledobject.yaml

# 4. Verify KEDA recognized the targets
kubectl -n etap get scaledobjects
#   NAME            SCALEDOWNER-KIND    SCALEDOWNER-NAME   MIN   MAX   READY   ACTIVE   TRIGGERS                  ...
#   etap-ai-api     Deployment          etap-ai-api        3     50    True    True     prometheus/cpu/memory     ...
#   etap-ai-worker  Deployment          etap-ai-worker     2     60    True    True     redis/cpu                 ...

kubectl -n etap get triggerauthentications
#   NAME                     SCALEDOWNEROBJECT   TRIGGERNAME   SECRETNAME          ...
#   etap-redis-triggerauth   etap-ai-worker      redis         etap-redis-cluster  ...
```

## Tuning guide

### Worker ScaledObject — the key knobs

| Field                       | Default | What it controls                                |
|-----------------------------|---------|-------------------------------------------------|
| `minReplicaCount`           | 2       | Floor — never go below this even if queue empty |
| `maxReplicaCount`           | 60      | Ceiling — protects against runaway scale-up    |
| `idleReplicaCount`          | 2       | When metric=0, scale down to this              |
| `pollingInterval`           | 15s     | How often KEDA queries Redis                    |
| `cooldownPeriod`            | 600s    | Min time between scale-down events              |
| `triggers[redis].listLength`| 10      | Add 1 pod per N messages in queue               |

The formula KEDA uses:

```
targetReplicas = ceil(currentQueueLength / listLength)
clamped between minReplicaCount and maxReplicaCount
```

So with `listLength=10` and a queue of 87 messages, KEDA targets
`ceil(87/10) = 9` replicas. With `listLength=5` (faster reaction), it would
target 18. With `listLength=50` (cheaper, slower), 2.

### Per-queue scaling (for heterogeneous workloads)

If your `worker/celery_app.py` defines multiple queues (e.g. `study_heavy`
for load-flow studies, `study_light` for short-circuit, `default` for misc),
define one trigger per queue:

```yaml
triggers:
  - type: redis
    metadata:
      listName: study_heavy
      listLength: "2"          # heavy tasks are CPU-bound; 1 pod per 2 msgs
  - type: redis
    metadata:
      listName: study_light
      listLength: "20"         # light tasks are fast; 1 pod per 20 msgs
  - type: redis
    metadata:
      listName: default
      listLength: "10"
```

You'd also need to start the worker with `--queues=study_heavy,study_light,default`
in the deployment command (override via `worker.command` in Helm values).

## Verify autoscaling actually fires

```bash
# 1. Enqueue 200 dummy tasks
kubectl -n etap exec -it deploy/etap-ai-api -- python -c "
from worker.celery_app import app
for i in range(200):
    app.send_task('worker.tasks.ping', args=[i])
print('enqueued')
"

# 2. Watch workers scale up
kubectl -n etap get pods -l app.kubernetes.io/component=worker -w
# You should see new pods spin up within ~30s.

# 3. Watch the ScaledObject status
kubectl -n etap describe scaledobject etap-ai-worker

# 4. Once the queue drains, workers scale back down (after cooldownPeriod=600s)
kubectl -n etap get hpa etap-ai-worker-hpa -w
```

## Cost impact

Typical ETAP AI workload (10 active users, periodic bulk study runs):

| Setting                    | Steady-state pods | Peak pods | Monthly cost (EKS, 2vCPU/4GB) |
|----------------------------|-------------------|-----------|-------------------------------|
| HPA-only (CPU 70%)         | 4 workers         | 8 workers | ~$220                         |
| KEDA (queue depth)         | 1–2 workers       | 12 workers | ~$140                         |

That's a ~35% cost reduction in exchange for ~15s of additional cold-start
latency on burst — usually a great trade.

## Common pitfalls

1. **`redis-py` version too old**: Celery >= 5.3 + redis-py >= 4.3 needed for
   Redis Cluster. Check with `pip show celery redis` inside a worker pod.

2. **KEDA secret mismatch**: The `TriggerAuthentication` must reference the
   same secret + key the chart wired into `REDIS_PASSWORD`. Verify:
   ```bash
   kubectl -n etap get secret etap-redis-cluster -o jsonpath='{.data.redis-password}' | base64 -d
   ```

3. **HPA fight**: If both the Helm-managed HPA and KEDA's HPA exist for the
   same Deployment, scaling will be erratic. Apply with
   `--set worker.autoscaling.enabled=false` (see install steps above).

4. **Queue name mismatch**: Celery's default queue is named literally `celery`.
   If your `worker/celery_app.py` overrides `task_default_queue`, update
   `listName` in the ScaledObject to match.
