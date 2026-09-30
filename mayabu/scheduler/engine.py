"""Permanent automation scheduler process.

Only the lease holder enqueues recurring discovery/refresh. Workers still
perform network I/O; this process keeps DB transactions short.
"""

from __future__ import annotations

import logging
import signal
import time
from dataclasses import dataclass
from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection
from mayabu.monitoring import instrumentation as metrics
from mayabu.scheduler.lease import SchedulerLease
from mayabu.scheduler.task_materializer import (
    materialize_demand_discovery,
    materialize_enrichment_tasks,
    materialize_overlap_discovery,
    materialize_refresh,
)
from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu_db.scheduler import materialize_due_plans
from mayabu_db.tasks import requeue_stuck_tasks

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TickResult:
    result: str
    jobs_scheduled: int
    refresh_created: int
    discovery_created: int
    demand_created: int
    search_drained: int
    stuck_reaped: int
    error: str | None = None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def tick(lease: SchedulerLease | None = None) -> TickResult:
    """One scheduling cycle. Safe to call from tests with a held lease."""
    settings = get_app_settings()
    if not settings.scheduler_enabled:
        metrics.SCHEDULER_TICK.inc(result="disabled")
        return TickResult("disabled", 0, 0, 0, 0, 0, 0)

    holder = lease or SchedulerLease()
    if not holder.try_acquire(settings.scheduler_lease_seconds):
        metrics.SCHEDULER_TICK.inc(result="standby")
        return TickResult("standby", 0, 0, 0, 0, 0, 0)

    tick_started = time.monotonic()
    refresh_created = discovery_created = demand_created = search_drained = stuck_reaped = 0
    error: str | None = None
    try:
        # Structural: ensure production multi-category discovery plans exist.
        # Idempotent; no tasks enqueued; never enables scheduler itself.
        try:
            from mayabu_db.scheduler import ensure_production_discovery_plans

            ensure_production_discovery_plans()
        except Exception:
            logger.exception("ensure_discovery_plans_failed")

        with db_connection() as conn:
            stuck_reaped = requeue_stuck_tasks(conn)

        refresh_created = materialize_refresh(
            limit=settings.scheduler_max_refresh_per_tick
        )
        metrics.SCHEDULER_TASKS.inc(refresh_created, task_type="refresh_listing")

        if settings.scheduler_max_discovery_per_tick > 0:
            discovery_created = materialize_due_plans(
                limit=settings.scheduler_max_discovery_per_tick
            )
            metrics.SCHEDULER_TASKS.inc(discovery_created, task_type="discovery")

        if settings.scheduler_max_demand_per_tick > 0:
            demand_created = materialize_demand_discovery(
                limit=settings.scheduler_max_demand_per_tick
            )
            metrics.SCHEDULER_TASKS.inc(demand_created, task_type="discovery_demand")

        enrich_created = 0
        if settings.scheduler_max_overlap_per_tick > 0:
            try:
                enrich_created = materialize_overlap_discovery(
                    limit=settings.scheduler_max_overlap_per_tick
                )
                metrics.SCHEDULER_TASKS.inc(enrich_created, task_type="targeted_discovery")
            except Exception:
                logger.exception("materialize_overlap_failed")

        enrich_listing_created = 0
        if settings.scheduler_max_enrich_per_tick > 0:
            try:
                enrich_listing_created = materialize_enrichment_tasks(
                    limit=settings.scheduler_max_enrich_per_tick
                )
                metrics.SCHEDULER_TASKS.inc(enrich_listing_created, task_type="enrich_listing")
            except Exception:
                logger.exception("materialize_enrichment_failed")

        drained = drain_dirty_search_documents(
            limit=settings.scheduler_search_drain_per_tick
        )
        search_drained = _safe_int(drained.get("refreshed")) if isinstance(drained, dict) else 0

        jobs = (
            refresh_created
            + discovery_created
            + demand_created
            + enrich_created
            + enrich_listing_created
        )
        duration_ms = int((time.monotonic() - tick_started) * 1000)
        holder.record_tick(
            ttl_seconds=settings.scheduler_lease_seconds,
            jobs_scheduled=jobs,
            result="ok",
            success=True,
            duration_ms=duration_ms,
        )
        metrics.SCHEDULER_TICK.inc(result="ok")
        return TickResult(
            "ok",
            jobs,
            refresh_created,
            discovery_created,
            demand_created,
            search_drained,
            stuck_reaped,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
        logger.exception("scheduler_tick_failed")
        try:
            holder.record_tick(
                ttl_seconds=settings.scheduler_lease_seconds,
                jobs_scheduled=0,
                result="error",
                error=error,
                success=False,
                duration_ms=int((time.monotonic() - tick_started) * 1000),
            )
        except Exception:
            logger.exception("scheduler_heartbeat_write_failed")
        metrics.SCHEDULER_TICK.inc(result="error")
        return TickResult(
            "error",
            refresh_created + discovery_created + demand_created,
            refresh_created,
            discovery_created,
            demand_created,
            search_drained,
            stuck_reaped,
            error=error,
        )


def run_forever() -> None:
    settings = get_app_settings()
    holder = SchedulerLease()
    stopping = False

    def _stop(signum, _frame) -> None:  # noqa: ANN001
        nonlocal stopping
        stopping = True
        logger.info("scheduler_stop_signal", extra={"signal": int(signum)})

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info(
        "scheduler_start",
        extra={
            "enabled": settings.scheduler_enabled,
            "tick_seconds": settings.scheduler_tick_seconds,
            "holder_id": holder.holder_id,
        },
    )
    try:
        while not stopping:
            started = time.monotonic()
            result = tick(holder)
            logger.info(
                "scheduler_tick",
                extra={
                    "result": result.result,
                    "jobs": result.jobs_scheduled,
                    "refresh": result.refresh_created,
                    "discovery": result.discovery_created,
                    "demand": result.demand_created,
                    "search_drained": result.search_drained,
                    "stuck_reaped": result.stuck_reaped,
                },
            )
            elapsed = time.monotonic() - started
            sleep_for = max(1.0, float(settings.scheduler_tick_seconds) - elapsed)
            deadline = time.monotonic() + sleep_for
            while not stopping and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
    finally:
        holder.release()
