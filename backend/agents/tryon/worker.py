"""Celery task: heavy work runs here, not in the API process."""

import asyncio

from shared.queue import celery_app

from .agent import TryOnAgent


@celery_app.task(name="tryon.run")
def run_task(payload: dict) -> dict:
    return asyncio.run(TryOnAgent()(payload))
