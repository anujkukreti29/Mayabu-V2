"""Bounded maintenance jobs for storage, queue, and search health."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection
from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu_db.tasks import cleanup_raw_scrape_items, requeue_stuck_tasks


def _record_start(job_name: str) -> str:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into maintenance_runs(job_name, status) values (%s, 'running') returning id",
                (job_name,),
            )
            return str(cur.fetchone()["id"])


def _record_finish(run_id: str, status: str, stats: dict[str, Any], error: str | None = None) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update maintenance_runs
                set status = %s, stats = %s, error = %s, finished_at = now()
                where id = %s
                """,
                (status, Jsonb(stats), error, run_id),
            )


def cleanup_price_observations(retention_days: int) -> int:
    """Delete old raw observations only after their daily rollup exists."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from price_observations po
                where po.observed_at < now() - make_interval(days => %s)
                  and exists (
                    select 1 from daily_listing_prices d
                    where d.listing_id = po.listing_id and d.date = date(po.observed_at)
                  )
                """,
                (retention_days,),
            )
            return int(cur.rowcount or 0)


def cleanup_completed_tasks(retention_days: int) -> int:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from scrape_tasks
                where status in ('completed','cancelled','dead')
                  and updated_at < now() - make_interval(days => %s)
                """,
                (retention_days,),
            )
            return int(cur.rowcount or 0)


def cleanup_live_verification_events(retention_days: int) -> int:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from live_verification_events
                where created_at < now() - make_interval(days => %s)
                """,
                (retention_days,),
            )
            return int(cur.rowcount or 0)


def cleanup_old_runs(retention_days: int = 90) -> int:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from scrape_runs
                where finished_at is not null
                  and finished_at < now() - make_interval(days => %s)
                  and not exists (select 1 from anomaly_events a where a.run_id = scrape_runs.id and a.status = 'open')
                """,
                (retention_days,),
            )
            return int(cur.rowcount or 0)


def run_maintenance(job: str = "all") -> dict[str, Any]:
    settings = get_app_settings()
    allowed = {"all", "queue", "search", "storage"}
    if job not in allowed:
        raise ValueError(f"Unknown maintenance job: {job}. Allowed: {sorted(allowed)}")
    run_id = _record_start(job)
    stats: dict[str, Any] = {}
    try:
        if job in {"all", "queue"}:
            with db_connection() as conn:
                stats["requeued_stuck_tasks"] = requeue_stuck_tasks(conn)
            stats["deleted_completed_tasks"] = cleanup_completed_tasks(settings.completed_task_retention_days)
        if job in {"all", "search"}:
            stats["search_documents"] = drain_dirty_search_documents(limit=settings.search_document_batch_size)
        if job in {"all", "storage"}:
            with db_connection() as conn:
                stats["deleted_raw_items"] = cleanup_raw_scrape_items(conn, settings.raw_item_retention_days)
            stats["deleted_price_observations"] = cleanup_price_observations(settings.raw_price_retention_days)
            stats["deleted_old_runs"] = cleanup_old_runs()
            stats["deleted_verification_events"] = cleanup_live_verification_events(
                settings.live_verification_event_retention_days
            )
        _record_finish(run_id, "completed", stats)
        return {"run_id": run_id, "status": "completed", **stats}
    except Exception as exc:
        _record_finish(run_id, "failed", stats, str(exc)[:2000])
        raise
