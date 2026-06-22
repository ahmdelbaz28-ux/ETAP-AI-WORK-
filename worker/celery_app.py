"""
Celery application for handling heavy engineering tasks asynchronously.
Uses Redis as both broker and result backend.
"""

import os

from celery import Celery

# Configure Celery to use Redis
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery("engineering_tasks", broker=redis_url, backend=redis_url, include=["worker.tasks"])

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # Results expire after 1 hour
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Process one task at a time to handle heavy loads
    task_acks_late=True,  # Acknowledge tasks after completion (re-queue on worker crash)
    task_reject_on_worker_lost=True,  # Re-deliver task if worker dies mid-execution
    broker_visibility_timeout=3600,  # 1 hour — matches result_expires
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    task_time_limit=3600,  # Hard kill after 1 hour
    task_soft_time_limit=3300,  # Soft warning at 55 minutes
    worker_max_tasks_per_child=100,  # Recycle worker after 100 tasks (prevents memory leaks)
)

if __name__ == "__main__":
    app.start()
