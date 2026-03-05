"""APScheduler integration for SP-API daily pulls."""

from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pipelines.spapi_pipeline import run_daily_pull


logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _safe_daily_pull() -> None:
    try:
        run_daily_pull()
    except Exception:
        logger.exception("Scheduled SP-API daily pull failed")


def start_scheduler() -> BackgroundScheduler:
    """Start a singleton scheduler that runs daily at 06:00 UTC."""
    global _scheduler

    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _safe_daily_pull,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="spapi_daily_pull",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()

    _scheduler = scheduler
    logger.info("Started SP-API scheduler (daily at 06:00 UTC)")
    return scheduler


def stop_scheduler() -> None:
    """Stop scheduler gracefully (useful in tests)."""
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
