"""Run bounded Mayabu v5 maintenance jobs in a dedicated process."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from mayabu.jobs.maintenance import run_maintenance
from mayabu.scheduler.maintenance import run_duplicate_candidate_finder, run_price_rollup_rebuild
from mayabu.search.demand_signal import refresh_demand_counters

logger = logging.getLogger(__name__)


def _safe_job(name: str, fn, *args, **kwargs) -> None:
    try:
        result = fn(*args, **kwargs)
        print({"job": name, "status": "completed", "result": result})
    except Exception as exc:  # a process supervisor captures stdout/stderr
        logger.exception("maintenance_job_failed", extra={"job": name})
        print({"job": name, "status": "failed", "error": str(exc)[:1000]})


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC", job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 300})

    # Fast, bounded operational work.
    scheduler.add_job(_safe_job, "interval", minutes=5, args=["queue", run_maintenance, "queue"], id="queue-maintenance")
    scheduler.add_job(_safe_job, "interval", minutes=2, args=["search-index", run_maintenance, "search"], id="search-index-maintenance")
    scheduler.add_job(_safe_job, "interval", hours=1, args=["demand-counters", refresh_demand_counters], id="demand-counters")

    # Storage and analytical work stays outside peak hours.
    scheduler.add_job(_safe_job, "cron", hour=2, minute=0, args=["storage", run_maintenance, "storage"], id="storage-nightly")
    scheduler.add_job(_safe_job, "cron", hour=2, minute=30, args=["duplicate-candidates", run_duplicate_candidate_finder], id="duplicates-nightly")
    scheduler.add_job(_safe_job, "cron", hour=3, minute=0, args=["price-rollups", run_price_rollup_rebuild], id="price-rollups-nightly")

    print("Mayabu v5 maintenance scheduler started")
    scheduler.start()


if __name__ == "__main__":
    main()
