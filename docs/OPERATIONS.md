# AhmedETAP Operational Specification: Redis Descope & Single-Replica Policy

## 1. Executive Summary
In accordance with Platform Architecture Review (Round 14), Redis has been officially descoped for the Hugging Face (HF) Space production deployment (`ahmdelbaz28-ahmedetap-platform.hf.space`). The operational status is surfaced honestly as `disabled_by_config` via the `/healthz` endpoint when `REDIS_URL` is omitted.

## 2. Rationale: Why HF Space Does Not Host Redis
1. **Container Topology**: Hugging Face Spaces operate as isolated, single-container environments running application workloads directly without built-in multi-container sidecar orchestration.
2. **Persistence Boundary**: An ephemeral local Redis inside the container would not provide durability across Space restarts and would unnecessarily consume container memory budget (16 GB shared with power-system solvers and ML inference).
3. **External Latency & Reliability**: Provisioning an external managed Redis (e.g. Upstash/Aiven) adds an external network roundtrip on every session/rate-limit check and introduces an external failure mode that could compromise high-availability engineering computations.

## 3. Impact on Distributed Locking & Rate Limiting
- **In-Memory Concurrency & Rate Limiting**: In the single-replica HF Space deployment, rate limiting and token bucket governance fall back gracefully to thread-safe in-memory collections (`api/rate_limiting.py`).
- **Distributed Locking**: Single-process concurrency control uses Python's `threading.Lock` and file-level locks (`filelock`), which are completely sufficient for single-replica execution.
- **Fail-Closed Multi-Replica Guard**: If the system is scaled horizontally to multiple replicas (`DEPLOYMENT_TOPOLOGY=multi_replica` or `REPLICAS > 1`), `api/health.py` enforces fail-closed behavior: `checks["redis"]` fails the readiness probe with HTTP 503 unless a valid, synchronized Redis cluster is provided via `REDIS_URL`.

## 4. Multi-Replica Fail-Closed Operating Requirement
- **Precondition for Scaling**: Any horizontal scaling beyond a single replica requires explicit configuration of `REDIS_URL`.
- **Enforcement**:
  ```python
  if is_prod and multi_replica and not redis_ok:
      status_code = 503  # Strictly reject traffic in multi-replica topology without Redis
  ```

## 5. Health Probe Contract
- **GET /healthz**:
  ```json
  {
    "status": "ok",
    "database": "postgresql",
    "redis": "disabled_by_config"
  }
  ```
  Returns HTTP 200 indicating all critical dependencies (PostgreSQL database and core calculation engine) are fully operational and Redis is deliberately disabled by configuration.
