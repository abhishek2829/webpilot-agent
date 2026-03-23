"""WebPilot Agent — Celery Application.

Configures the Celery app instance with Redis as broker and result backend.
This module is the entry point for Celery workers:

    celery -A src.tasks.celery_app worker --loglevel=info

Environment variables:
    WEBPILOT_REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("WEBPILOT_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "webpilot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.tasks.worker"],
)

celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,                  # Acknowledge after completion (crash-safe)
    worker_prefetch_multiplier=1,         # One task at a time per worker (browser-bound)
    task_reject_on_worker_lost=True,      # Requeue if worker dies mid-task
    task_track_started=True,              # Track STARTED state transitions

    # Result expiry
    result_expires=86400,                 # 24 hours

    # Task routes — keep workflow execution on dedicated queue
    task_routes={
        "src.tasks.worker.execute_workflow_task": {"queue": "workflows"},
    },
)
