"""Celery app for heavy jobs (segmentation, try-on rendering)."""

from celery import Celery

from shared.config import settings

celery_app = Celery("dressme", broker=settings.redis_url, backend=settings.redis_url)
celery_app.autodiscover_tasks(["agents.vision", "agents.tryon"], related_name="worker")
