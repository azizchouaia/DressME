"""Celery task: heavy work runs here, not in the API process."""

import asyncio

from shared.queue import celery_app

from .agent import VisionAgent


@celery_app.task(name="vision.run")
def run_task(payload: dict) -> dict:
    return asyncio.run(VisionAgent()(payload))
