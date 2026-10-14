"""In-process scheduler: every 5 minutes, run the jobs that are due (service.run_due).

Started with the API (router on_startup) unless M04_SCHEDULER=off or M4 is mocked. Run ONE scheduler process:
with several API workers, set M04_SCHEDULER=off on all but one, or call service.run_due from Celery beat /
a cron instead (jobs are idempotent per user and day, so a double tick never sends a notification twice).
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("m04.scheduler")
_scheduler = None
TICK_MINUTES = int(os.environ.get("M04_TICK_MINUTES", "5"))


def tick() -> None:
    from . import service

    for r in service.run_due():
        log.info("m04 job %s for %s: %s", r.get("job"), r.get("user_id"), "error" if "error" in r else "ok")


def start() -> None:
    global _scheduler
    if _scheduler is not None or os.environ.get("M04_SCHEDULER", "on").lower() in ("off", "0", "false"):
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(tick, "interval", minutes=TICK_MINUTES, id="m04_tick", max_instances=1, coalesce=True)
    _scheduler.start()
    log.info("m04 scheduler started (tick every %s min)", TICK_MINUTES)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def running() -> bool:
    return _scheduler is not None
