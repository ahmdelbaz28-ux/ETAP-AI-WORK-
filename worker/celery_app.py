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
    task_acks_late=True,  # Acknowledge tasks after completion
)

if __name__ == "__main__":
    app.start()
