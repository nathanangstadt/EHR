from __future__ import annotations

import os

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "ehr",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.task_track_started = True
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True
celery_app.conf.task_always_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER") == "1"
celery_app.conf.task_eager_propagates = True
