"""
worker/celery_app.py — Celery application for handling heavy engineering tasks.

Uses Redis as both broker and result backend.

Production features
-------------------
* Autoscaling between MIN_WORKERS and MAX_WORKERS
* Late acknowledgement (task_acks_late) for crash recovery
* One task per prefetch for long-running studies
* Result TTL aligned with task store retention
* Soft/hard time limits for study tasks
* Retry-on-connection-error for Redis broker
"""

from __future__ import annotations

import os

from celery import Celery
from kombu import Queue  # type: ignore

# ---------------------------------------------------------------------------
# Redis connection
# ---------------------------------------------------------------------------

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Separate result backend DB to avoid conflicts with rate-limit KV
result_backend_url = os.environ.get("CELERY_RESULT_BACKEND", redis_url)

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

app = Celery(
    "engineering_tasks",
    broker=redis_url,
    backend=result_backend_url,
    include=["worker.tasks"],
)

# ---------------------------------------------------------------------------
# Queue definitions — enables priority routing
# ---------------------------------------------------------------------------

_HIGH_PRIORITY_QUEUE = Queue("high", routing_key="high")
_DEFAULT_QUEUE = Queue("default", routing_key="default")
_LOW_PRIORITY_QUEUE = Queue("low", routing_key="low")

# ---------------------------------------------------------------------------
# Celery configuration
# ---------------------------------------------------------------------------

app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Result retention (1 hour — matches task store TTL)
    result_expires=3600,
    # Task tracking
    task_track_started=True,
    # Reliability — process one task at a time (studies are CPU-heavy)
    worker_prefetch_multiplier=1,
    # Crash recovery — acknowledge task AFTER completion, not before
    task_acks_late=True,
    # Re-queue tasks if the worker is killed mid-execution
    task_reject_on_worker_lost=True,
    # Time limits per task (soft warning → hard kill)
    task_soft_time_limit=600,  # 10 minutes soft limit
    task_time_limit=900,  # 15 minutes hard kill
    # Queues
    task_queues=[_HIGH_PRIORITY_QUEUE, _DEFAULT_QUEUE, _LOW_PRIORITY_QUEUE],
    task_default_queue="default",
    task_default_routing_key="default",
    # Route ETAP studies to high-priority queue
    task_routes={
        "worker.tasks.execute_engineering_study_task": {"queue": "default"},
    },
    # Autoscaling — controlled by env vars for Kubernetes
    worker_autoscaler="celery.worker.autoscale:Autoscaler",
    worker_min_tasks_per_child=50,
    # Connection retry on startup (prevents crash if Redis isn't ready yet)
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
    # Redis-specific options
    broker_transport_options={
        "visibility_timeout": 3600,  # 1 hour (≥ task_time_limit)
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
    },
    result_backend_transport_options={
        "socket_timeout": 30,
    },
)

# ---------------------------------------------------------------------------
# Autoscale configuration (reads from environment for k8s / docker)
# ---------------------------------------------------------------------------

_MIN_WORKERS = int(os.environ.get("CELERY_MIN_WORKERS", "2"))
_MAX_WORKERS = int(os.environ.get("CELERY_MAX_WORKERS", "8"))

app.conf.update(
    worker_autoscale=f"{_MAX_WORKERS},{_MIN_WORKERS}",
)

# ---------------------------------------------------------------------------
# Health check beat schedule (every 60s — used by monitoring)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    "heartbeat-every-60s": {
        "task": "worker.tasks.celery_heartbeat",
        "schedule": 60.0,
        "options": {"queue": "default"},
    },
}

if __name__ == "__main__":
    app.start()
