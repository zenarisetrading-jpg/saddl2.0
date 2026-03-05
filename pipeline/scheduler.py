"""Background scheduler for isolated pipeline."""

from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline.runner import run_daily_pull


logger = logging.getLogger(__name__)
_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_pull,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="spapi_daily_pull_isolated",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Pipeline scheduler started at 06:00 UTC")
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
