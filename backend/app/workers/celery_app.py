"""Celery app instance, Redis broker/backend."""

from celery import Celery

from app.core.config import get_settings
from app.workers.beat_schedule import BEAT_SCHEDULE

settings = get_settings()

celery_app = Celery(
    "calle",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.sweep_tasks", "app.workers.analytics_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule=BEAT_SCHEDULE,
)
