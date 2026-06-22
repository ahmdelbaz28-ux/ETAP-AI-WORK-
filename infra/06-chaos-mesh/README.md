# Chaos Mesh — Resilience Testing for the ETAP AI Platform

## Why chaos engineering?

The ETAP AI platform has all the right components for HA — multiple replicas,
HPA, PDB, Redis Cluster, CloudNativePG with replication, automated backups —
but **none of those guarantees actually work until you've tested them under
failure conditions**. Real-world failure modes that chaos engineering surfaces:

- The HPA config has `minReplicas: 3` and PDB has `minAvailable: 2`, but when
  you kill a pod during a rolling deploy, do both work together? Or does the
  deploy deadlock?
- Redis Cluster is supposed to fail over in <10 seconds. But what if your
  Celery client is configured with a stale connection that doesn't honor the
  `MOVED` redirect? You only find out during the next real failure.
- CloudNativePG promotes a replica when the primary dies. But does the
  application's connection pool actually reconnect, or does it hang on the
  dead socket for 5 minutes?

Chaos Mesh lets you inject these failures in a controlled, scheduled way so
you discover the answers *before* a real outage does.

## Install

```bash
# 1. Install Chaos Mesh in the etap-infra namespace
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
    -n etap-infra --create-namespace \
    -f 06-chaos-mesh/values.yaml

# 2. Verify
kubectl -n etap-infra get pods
#   chaos-controller-manager-<...>   2/2   Running
#   chaos-daemon-<...>               1/1   Running  (one per node)
#   chaos-dashboard-<...>            1/1   Running

# 3. Apply experiments ONE AT A TIME during business hours first
#    (do NOT apply the weekly schedule until each experiment is validated)
kubectl apply -f 06-chaos-mesh/experiments/01-api-pod-kill.yaml

# 4. Watch the API recover
kubectl -n etap get pods -l app.kubernetes.io/component=api -w

# 5. After all individual experiments pass, apply the weekly game-day schedule
kubectl apply -f 06-chaos-mesh/schedules/weekly-chaos-schedule.yaml
```

## Experiment catalog

| #   | File                            | Component  | Failure mode                                | Schedule           |
|-----|---------------------------------|------------|---------------------------------------------|--------------------|
| 1-2 | `01-api-pod-kill.yaml`          | API        | Pod kill, container kill                    | every 10m / 30m    |
| 3-4 | `02-worker-chaos.yaml`          | Worker     | Pod kill, CPU stress                        | every 15m / hourly |
| 5-6 | `03-redis-network-chaos.yaml`   | Redis      | Network latency 200ms, network partition    | 9 AM / Mon 10 AM   |
| 7-8 | `04-postgres-chaos.yaml`        | Postgres   | 20% packet loss, primary kill               | Tue 11 AM / Wed 12 PM |
| 9-10| `05-api-stress.yaml`            | API        | CPU 80%, memory +512MB                      | hourly / Thu 2 PM  |
| 11  | `06-io-chaos.yaml`              | Worker     | IO latency 100ms on /app/reports            | Fri 3 PM           |

Plus a **weekly game-day workflow** (`schedules/weekly-chaos-schedule.yaml`)
that runs experiments 1, 3, 5, 7, 9 in sequence on Saturday 1 AM.

## What "passing" looks like

For each experiment, define a SLO **before** running it. Example SLOs:

| Experiment                  | SLO during experiment                    | SLO after experiment |
|-----------------------------|------------------------------------------|----------------------|
| api-pod-kill                | <0.1% 5xx rate, p95 latency <500ms       | Full recovery <60s   |
| api-cpu-stress              | <1% 5xx rate, p95 latency <2s            | Full recovery <30s   |
| worker-pod-kill             | 0 lost tasks (Celery redelivers)         | Full recovery <60s   |
| redis-network-latency       | <5% 5xx rate, p99 latency <2s            | Full recovery <30s   |
| redis-network-partition     | <10s of `MOVED` errors visible           | Full recovery <30s   |
| postgres-network-loss       | Circuit breaker trips after 5 failures   | Full recovery <60s   |
| postgres-primary-kill       | <15s of write errors                     | Full recovery <30s   |

The Grafana dashboard in `dashboards/chaos-mesh-grafana.json` visualizes all
these SLOs. Import it into your Grafana:

```bash
# Option 1: kubectl port-forward + Grafana UI
kubectl -n etap port-forward svc/grafana 3000:3000
# Browse to http://localhost:3000 → Dashboards → Import → upload the JSON

# Option 2: provision via ConfigMap
kubectl -n etap create configmap chaos-dashboard \
    --from-file=06-chaos-mesh/dashboards/chaos-mesh-grafana.json
kubectl -n etap label configmap chaos-dashboard grafana_dashboard=1
```

## Reading the dashboard

| Panel                                | What you're looking for during chaos          |
|--------------------------------------|-----------------------------------------------|
| Active Chaos Experiments             | Confirm the experiment you scheduled is Running |
| API 5xx Error Rate                   | Spikes = your retry / circuit breaker is failing |
| API Latency p95/p99                  | Spikes = HPA isn't scaling fast enough OR a downstream is down |
| Deployment Replica Count             | Should oscillate as HPA/KEDA reacts           |
| Redis Cluster Health                 | Size=6 stable; nodes up should never drop below 5 |
| Postgres Cluster Status              | Should stay "Healthy" with 2 active replicas  |

## Game day playbook (for humans)

The automated weekly schedule is the **regression test**. But once a quarter,
run a **manual game day** with the whole team:

1. **Pick a failure combo** the automated schedule doesn't cover, e.g.
   "Redis primary dies + API pod dies + 20% Postgres packet loss" simultaneously.
2. **Notify stakeholders** that the system will be degraded for ~5 minutes.
3. **Apply combined experiments**:
   ```bash
   kubectl apply -f 06-chaos-mesh/experiments/01-api-pod-kill.yaml
   kubectl apply -f 06-chaos-mesh/experiments/03-redis-network-chaos.yaml
   kubectl apply -f 06-chaos-mesh/experiments/04-postgres-chaos.yaml
   ```
4. **Watch the dashboard**. Document any SLO violation.
5. **Run a synthetic load** during the experiment:
   ```bash
   k6 run --vus 50 --duration 5m load-test.js
   ```
6. **Capture the post-mortem** in `docs/incidents/` — what broke, what didn't,
   what config change is needed.

## Common findings (and fixes)

| Finding                                             | Fix                                                    |
|-----------------------------------------------------|--------------------------------------------------------|
| API 5xx spikes when a pod dies                      | Add retry middleware in the ingress (`nginx.ingress.kubernetes.io/retries=3`) |
| Worker pod kill causes lost tasks                   | Set Celery `task_acks_late=True` + `task_reject_on_worker_lost=True` |
| Redis partition causes 30s outage                   | Lower Celery `broker_connection_retry` to 2s          |
| Postgres failover causes 60s outage                 | Reduce SQLAlchemy `pool_recycle` to 60s + `pool_pre_ping=True` |
| API CPU stress triggers OOMKills                    | Bump `api.resources.limits.memory` or fix memory leak  |
| HPA doesn't fire during burst                       | Switch to KEDA (already in this bundle)                |

## Safety: halting an experiment

If an experiment goes wrong (production impact beyond expected SLO):

```bash
# Pause all chaos experiments in the namespace
kubectl -n etap annotate chaosengine --all experiment.chaos-mesh.org/pause=true

# Or pause a single experiment
kubectl -n etap patch podchaos api-pod-kill --type=merge \
    -p '{"metadata":{"annotations":{"experiment.chaos-mesh.org/pause":"true"}}}'

# Delete all running experiments immediately
kubectl -n etap delete podchaos, networkchaos, stresschaos, iochaos --all
```
